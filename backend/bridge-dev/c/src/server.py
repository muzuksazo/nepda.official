"""C 훅 작업자 로컬 서버. bridge-dev 더미 화면(index.html)이 부르는 API 를 이 작업자 코드로 처리한다.

    cd backend/bridge-dev/c
    python -m src.server            # http://127.0.0.1:8080
    브라우저: http://127.0.0.1:8080/?preset=<이름>          (C 유형·실제 호출·제품 정보가 채워진 화면. 이름 = examples 의 폴더 이름)
              http://127.0.0.1:8080/?preset=<이름>&run=1    (열자마자 "처음부터 끝까지" 실행)

개발용이다. 인증을 확인하지 않고 상태는 메모리에만 둔다 (서버를 끄면 프로젝트 목록이 사라지고 결과 파일은 남는다).
화면은 같은 서버가 내주므로 CORS 설정이 필요 없다. 다른 주소에서 여는 경우를 위해 CORS 헤더도 붙인다.

화면이 보내지 않는 값은 환경변수로 받는다:
  C_PRODUCT_FOOTAGE   실물 제품 영상 경로            C_PROBLEM_TEMPLATE  문제 장면 템플릿 (예: drain_smell)
  C_SCENARIO_FILES    ANTHROPIC_API_KEY 가 없을 때 회차마다 돌려 쓸 시나리오 응답 JSON 경로(쉼표 구분).
                      이것도 없으면 사실 문장으로 만든 오프라인 초안을 낸다.
"""
from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import re
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import quote, unquote
from functools import cached_property

from . import tts as tts_mod
from .check import check_scenario
from .cli import load_env
from .generate import generate_scenarios
from .render import render_hook, storyboard
from .schema import InputError, parse_worker_input
from .storage import DeliveryStorage, StorageError

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))          # c/
INDEX_HTML = os.path.join(os.path.dirname(HERE), "index.html")               # bridge-dev/index.html
DB: dict = {"infos": {}, "projects": {}, "hooks": {}}
LOCK = threading.Lock()
RENDER_LOCK = threading.Lock()                                               # Blender·ffmpeg 는 한 번에 하나만



def presets() -> dict[str, str]:
    """프리셋 이름 → 작업자 입력 JSON 경로. examples/<이름>/ 폴더마다 하나씩 생긴다 (코드에 제품을 적지 않는다).

    폴더에 preset.json {"input": "파일이름"} 이 있으면 그 파일을, 없으면 이름순으로 첫 *worker-input*.json 을 쓴다.
    """
    found = {}
    root = os.path.join(HERE, "examples")
    for name in sorted(os.listdir(root)) if os.path.isdir(root) else []:
        folder = os.path.join(root, name)
        if not os.path.isdir(folder):
            continue
        pick = None
        try:
            pick = json.load(open(os.path.join(folder, "preset.json"), encoding="utf-8")).get("input")
        except (OSError, ValueError):
            pass
        files = [pick] if pick else sorted(f for f in os.listdir(folder) if "worker-input" in f and f.endswith(".json"))
        if files and os.path.isfile(os.path.join(folder, files[0])):
            found[name] = os.path.join(folder, files[0])
    return found

# 화면(index.html)은 건드리지 않고, 내줄 때만 붙이는 스크립트: 프리셋 채우기, 자동 실행, 완성된 훅 영상 재생기.
INJECT = """
<script>
(function () {
  var q = new URLSearchParams(location.search), preset = __PRESET__;
  if (preset) {
    document.getElementById("mock").checked = false;
    document.getElementById("base").value = location.origin;
    var c = document.querySelector('input[name="htype"][value="C"]'); if (c) { c.checked = true; c.dispatchEvent(new Event("change", {bubbles: true})); }
    document.getElementById("pname").value = preset.name;
    var cat = document.getElementById("pcat");
    if (!Array.prototype.some.call(cat.options, function (o) { return o.value === preset.category; })) cat.add(new Option(preset.category, preset.category));
    cat.value = preset.category;
    document.getElementById("pfacts").value = preset.facts.join("\\n");
    if (typeof refreshBadge === "function") refreshBadge();
    if (q.get("run") === "1") setTimeout(function () { document.getElementById("bAll").click(); }, 600);
  }
  var seen = {};
  new MutationObserver(function () {
    var urls = [];
    document.getElementById("results").querySelectorAll(".files").forEach(function (files) {
      files.childNodes.forEach(function (node) {
        var m = node.nodeType === 3 && node.textContent.match(/^hook_video: (https?:\\/\\/\\S+)$/);
        if (m) urls.push(m[1]);
      });
    });
    urls.forEach(function (url) {
      var key = url.split("?")[0];
      if (seen[key]) return; seen[key] = true;
      var box = document.getElementById("cPlayer") || (function () {
        var s = document.createElement("section"); s.id = "cPlayer"; s.innerHTML = "<h2>완성된 훅 영상 <small>C 작업자 로컬 서버</small></h2>";
        document.getElementById("resSec").after(s); return s; })();
      var v = document.createElement("video"); v.src = url; v.controls = true; v.style.cssText = "width:270px;border-radius:12px;margin:6px 10px 6px 0;background:#000";
      box.appendChild(v);
    });
  }).observe(document.getElementById("results"), {childList: true, subtree: true});
})();
</script>
"""


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + "Z"


def later(sec: int) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(time.time() + sec)) + "Z"


def output_root() -> str:
    return os.path.abspath(os.environ.get("OUTPUT_DIR", "output"))


def uploads_root() -> str:
    return os.path.join(output_root(), "_uploads")


# 실제 프론트(frontend/)를 이 서버에 붙였을 때 쓰는 값. 개발용이라 로그인과 크레딧을 확인하지 않는다.
DEV_USER = {"user_id": "dev-user", "email": "dev@example.invalid", "name": "개발용 계정", "picture": None}
MAX_UPLOAD_BYTES = 500 * 1024 * 1024


def quota() -> dict:
    return {"daily_limit": 99, "used_today": 0, "remaining_today": 99, "resets_at": later(86400)}


def web_path(path: str, storage: "DeliveryStorage | None" = None) -> str:
    """결과 파일 경로 → 브라우저가 열 주소. 로컬 파일은 같은 서버의 /dev-files/… 경로로 준다 (프론트 개발 서버가 넘겨 주는 경로)."""
    if path.startswith("s3://"):
        return (storage or DeliveryStorage()).download_url(path)
    return "/dev-files/" + quote(os.path.relpath(os.path.abspath(path), output_root()).replace("\\", "/"))


def split_facts(product: dict) -> dict:
    """프론트의 제품 소개 칸은 글 한 덩어리로 온다. 줄과 문장 단위로 나눠 사실 목록으로 만든다."""
    facts = [f.strip() for f in product.get("verified_facts") or [] if isinstance(f, str) and f.strip()]
    if len(facts) == 1:
        parts = [x.strip(" .") for x in re.split(r"\n+|(?<=[.!?])\s+", facts[0]) if len(x.strip(" .")) >= 2]
        facts = parts or facts
    return {**product, "verified_facts": facts}


def summary(pid: str, p: dict) -> dict:
    product = p["product"]
    return {"project_id": pid, "status": p["status"], "flow_mode": p["flow_mode"], "product_name": product["name"], "category": product.get("category"),
            "selected_types": ["C"], "selected_scenario_id": p["selected"], "latest_job_id": ("job_" + p["hook"][5:]) if p.get("hook") else None,
            "expires_at": p["expires_at"], "created_at": p["created_at"], "updated_at": p["updated_at"]}


def touch(p: dict, status: str | None = None) -> None:
    p["updated_at"] = now()
    if status:
        p["status"] = status


def start_hook(pid: str, p: dict, sid: str, tts: dict | None, deliver: bool = False) -> str:
    """훅 렌더를 작업 스레드로 시작하고 hook_id 를 돌려준다. deliver=True 면 끝났을 때 프로젝트 상태도 바꾼다 (프론트의 renders 흐름)."""
    hid = "hook_" + uuid.uuid4().hex[:8]
    DB["hooks"][hid] = {"project": pid, "scenario": sid, "tts": tts or {"enabled": True}, "status": "queued", "files": {},
                        "dir": os.path.join(output_root(), pid, hid), "error": None, "deliver": deliver}
    p["hook"] = hid
    threading.Thread(target=run_hook, args=(hid,), daemon=True).start()
    return hid


def filming_shots(scenario: dict) -> list[dict]:
    """촬영 가이드. C 훅은 첫 장면(문제)만 생성 영상이고, 둘째 장면부터는 올린 실물 영상 한 컷을 이어서 쓴다."""
    shots = []
    for beat in scenario["beats"][1:]:
        ref = re.search(r"\[(F\d+)\]", beat.get("visual") or "")
        title = re.sub(r"\s*\[F\d+\]", "", beat.get("visual") or beat.get("caption") or "").strip()
        shots.append({"shot_no": len(shots) + 1, "title": title, "duration_sec": beat["duration_sec"],
                      "framing_tip": "세로로, 끊지 않고 앞 장면에 이어서 찍어요", "fact_ref": ref.group(1) if ref else ""})
    return shots


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def default_assets() -> dict:
    return {"product_footage": os.environ.get("C_PRODUCT_FOOTAGE") or None, "problem_template": os.environ.get("C_PROBLEM_TEMPLATE") or None,
            "problem_engine": os.environ.get("C_PROBLEM_ENGINE") or None}


def project(pid: str) -> dict:
    p = DB["projects"].get(pid)
    if not p:
        raise ApiError(404, "PROJECT_NOT_FOUND", "프로젝트를 찾을 수 없습니다")
    return p


def scenario_of(p: dict, sid: str) -> dict:
    for s in p["scenarios"]:
        if s["scenario_id"] == sid:
            return s
    raise ApiError(404, "SCENARIO_NOT_FOUND", "시나리오를 찾을 수 없습니다")


def new_scenarios(pid: str, p: dict, count: int) -> list[dict]:
    """다음 회차 시나리오. Claude 키가 있으면 생성하고, 없으면 준비된 응답 파일이나 오프라인 초안을 쓴다."""
    round_no = p["round"] + 1
    data = {"hook_type": "C", "project_id": pid, "round": round_no, "count": count, "product_info": p["product"],
            "assets": p["assets"], "previous_scenarios": p["scenarios"]}
    has_key = bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))
    files = [f.strip() for f in os.environ.get("C_SCENARIO_FILES", "").split(",") if f.strip()]
    if not has_key and files:
        src = json.load(open(files[(round_no - 1) % len(files)], encoding="utf-8"))["scenarios"][:count]
        out = []
        for i, s in enumerate(src):
            s = json.loads(json.dumps(s))
            s["scenario_id"], s["round"] = f"sc_{pid[-6:]}_C{round_no}_{i + 1:02d}", round_no
            out.append(s)
        p["source"] = "준비된 시나리오 파일"
    else:
        run = generate_scenarios(data, offline=not has_key, log=lambda m: print(m, file=sys.stderr))
        out = run["response"]["scenarios"]
        p["source"] = "Claude 생성" if has_key else "오프라인 초안"
    p["round"] = round_no
    for s in out:
        s["checks"] = check_scenario(s, p["product"])
    return out


def run_hook(hid: str) -> None:
    h = DB["hooks"][hid]
    p = DB["projects"][h["project"]]
    h["status"] = "running"
    try:
        storage = DeliveryStorage()
        with RENDER_LOCK:
            tts = dict(h["tts"])
            if tts.get("enabled", True) and not tts_mod.available():
                tts["enabled"] = False
                h["note"] = "INWORLD_API_KEY 가 없어 음성 없이 만들었습니다."
            files = render_hook(scenario_of(p, h["scenario"]), p["assets"], h["dir"], tts=tts, log=lambda m: print(m, file=sys.stderr),
                                product_name=p["product"].get("name"))
        h["engine"] = files.pop("problem_engine", None)
        h["files"] = files
        files = storage.publish_files(files)
        h["files"], h["status"] = files, "done"
        if h.get("deliver"):
            touch(p, "DELIVERABLE_READY")
    except Exception as e:          # 작업 스레드에서 난 오류는 폴링 응답으로 알려야 한다
        h["status"], h["error"] = "failed", {"code": e.code if isinstance(e, StorageError) else "HOOK_RENDER_FAILED", "message": str(e)[:600]}
        if h.get("deliver"):
            touch(p, "FAILED")
        print(f"hook {hid} failed: {e}", file=sys.stderr)


class Handler(BaseHTTPRequestHandler):
    server_version = "CWorker/0.1"

    def log_message(self, fmt, *args):
        print("%s %s" % (self.command, self.path), file=sys.stderr)

    # ---------- 응답 ----------
    def cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, OPTIONS")

    def send_json(self, status: int, body) -> None:
        raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.cors()
        self.end_headers()
        self.wfile.write(raw)

    def fail(self, e: ApiError) -> None:
        self.send_json(e.status, {"detail": {"error": {"code": e.code, "message": e.message, "details": {}}}})

    def url_for(self, path: str) -> str:
        """결과 파일 경로 → 이 서버의 주소."""
        if path.startswith("s3://"):
            return self.storage.download_url(path)
        rel = os.path.relpath(os.path.abspath(path), output_root()).replace("\\", "/")
        return f"http://{self.headers.get('Host', '127.0.0.1:8080')}/files/{rel}"

    @cached_property
    def storage(self) -> DeliveryStorage:
        return DeliveryStorage()

    def body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except ValueError as e:
            raise ApiError(422, "VALIDATION_ERROR", "본문이 JSON 이 아닙니다") from e

    # ---------- 화면과 파일 ----------
    def send_index(self, query: str) -> None:
        html = open(INDEX_HTML, encoding="utf-8").read()
        m = re.search(r"preset=([\w-]+)", query)
        preset = None
        known = presets()
        if m and m.group(1) in known:
            src = json.load(open(known[m.group(1)], encoding="utf-8"))["product_info"]
            preset = {"name": src["name"], "category": src.get("category", "living"), "facts": src["verified_facts"]}
        inject = INJECT.replace("__PRESET__", json.dumps(preset, ensure_ascii=False))
        raw = html.replace("</body>", inject + "</body>").encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def send_file(self, rel: str) -> None:
        root = output_root()
        path = os.path.abspath(os.path.join(root, rel))
        if not path.startswith(root + os.sep) or not os.path.isfile(path):
            raise ApiError(404, "NOT_FOUND", "파일이 없습니다")
        size = os.path.getsize(path)
        start, end = 0, size - 1
        m = re.match(r"bytes=(\d*)-(\d*)", self.headers.get("Range") or "")
        if m and (m.group(1) or m.group(2)):
            if m.group(1):
                start, end = int(m.group(1)), int(m.group(2)) if m.group(2) else size - 1
            else:
                start = max(0, size - int(m.group(2)))
            end = min(end, size - 1)
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        else:
            self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(path)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Accept-Ranges", "bytes")
        self.cors()
        self.end_headers()
        with open(path, "rb") as f:
            f.seek(start)
            left = end - start + 1
            while left > 0:
                chunk = f.read(min(1 << 16, left))
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                except (ConnectionError, OSError):
                    return
                left -= len(chunk)

    # ---------- 라우팅 ----------
    def do_OPTIONS(self):
        self.send_response(204)
        self.cors()
        self.end_headers()

    def do_GET(self):
        self.route("GET")

    def do_POST(self):
        self.route("POST")

    def do_PUT(self):
        self.route("PUT")

    def upload_target(self, object_key: str) -> str:
        root = uploads_root()
        path = os.path.abspath(os.path.join(root, object_key.lstrip("/")))
        if not object_key or not path.startswith(root + os.sep):
            raise ApiError(400, "VALIDATION_ERROR", "object_key 가 올바르지 않습니다")
        return path

    def save_upload(self, object_key: str) -> dict:
        """브라우저가 올린 촬영 영상을 받아 둔다 (scripts/dev_backend.py 의 /dev-uploads 와 같은 약속)."""
        dest = self.upload_target(object_key)
        size = int(self.headers.get("Content-Length") or 0)
        if size <= 0:
            raise ApiError(411, "VALIDATION_ERROR", "Content-Length 가 필요합니다")
        if size > MAX_UPLOAD_BYTES:
            raise ApiError(413, "VALIDATION_ERROR", f"파일이 {MAX_UPLOAD_BYTES} 바이트 상한을 넘었습니다")
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        left = size
        with open(dest, "wb") as out:
            while left > 0:
                chunk = self.rfile.read(min(1 << 16, left))
                if not chunk:
                    break
                out.write(chunk)
                left -= len(chunk)
        if left:
            os.remove(dest)
            raise ApiError(400, "VALIDATION_ERROR", "업로드가 중간에 끊겼습니다")
        return {"object_key": object_key, "size_bytes": size, "local_path": dest}

    def route(self, method: str) -> None:
        path, _, query = self.path.partition("?")
        try:
            if method == "GET" and path in ("/", "/index.html"):
                return self.send_index(query)
            for prefix in ("/files/", "/dev-files/"):
                if method == "GET" and path.startswith(prefix):
                    return self.send_file(unquote(path[len(prefix):]))
            if method == "PUT" and path.startswith("/dev-uploads/"):
                return self.send_json(200, self.save_upload(unquote(path[len("/dev-uploads/"):])))
            if method == "GET" and path == "/health":
                return self.send_json(200, {"status": "ok", "worker": "C"})
            if method == "GET" and path == "/favicon.ico":
                self.send_response(204)
                self.end_headers()
                return
            status, data = self.api(method, path)
            self.send_json(status, data)
        except ApiError as e:
            self.fail(e)
        except InputError as e:
            self.fail(ApiError(422, "VALIDATION_ERROR", str(e)))
        except StorageError as e:
            self.fail(ApiError(502, e.code, str(e)))
        except RuntimeError as e:
            self.fail(ApiError(502, "UPSTREAM_ERROR", str(e)[:600]))

    def api(self, method: str, path: str) -> tuple[int, dict]:
        if method == "GET" and path == "/v1/auth/me":
            return 200, {"user": DEV_USER, "quota": quota()}
        if method == "POST" and path == "/v1/auth/logout":
            return 200, {"status": "ok"}
        if method == "POST" and path == "/v1/auth/google":
            return 200, {"user": DEV_USER, "quota": quota()}
        if method == "GET" and path == "/v1/billing/config":
            return 200, {"provider": "paddle", "environment": "sandbox", "enabled": False, "client_token": None, "credits_per_video": 12, "packages": []}
        if method == "GET" and path == "/v1/billing/wallet":
            return 200, {"credits": 100, "has_free_video": True, "free_videos_remaining": 1}
        if method == "GET" and path == "/v1/projects":
            rows = sorted(DB["projects"].items(), key=lambda kv: kv[1]["created_at"], reverse=True)
            return 200, {"projects": [summary(pid, p) for pid, p in rows], "quota": quota(), "total": len(rows), "offset": 0, "limit": max(50, len(rows)),
                         "has_more": False, "next_offset": None}

        if method == "POST" and path == "/v1/uploads/presign":
            key = str(self.body().get("object_key") or "")
            self.upload_target(key)
            return 200, {"upload_url": "/dev-uploads/" + quote(key.lstrip("/")), "object_key": key}

        if method == "POST" and path == "/v1/product-info":
            body = self.body()
            product = split_facts(body.get("product") or {})
            if not product.get("name") or not product.get("category"):
                raise ApiError(422, "VALIDATION_ERROR", "product.name, product.category 는 필수입니다")
            key = hashlib.sha256(json.dumps(product, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]
            with LOCK:
                hit = key in DB["infos"]
                if not hit:
                    DB["infos"][key] = {"product_info_id": "pinfo_" + uuid.uuid4().hex[:8], "product": product, "cached_at": now(), "expires_at": later(3600)}
                rec = DB["infos"][key]
            return 200, {**rec, "cached": hit}

        if method == "POST" and path == "/v1/projects":
            body = self.body()
            product = split_facts(body["product"]) if body.get("product") else None
            inline = bool(product)
            if not product:
                rec = next((r for r in DB["infos"].values() if r["product_info_id"] == body.get("product_info_id")), None)
                if not rec:
                    raise ApiError(404, "PRODUCT_INFO_NOT_FOUND", "product_info_id 가 없거나 캐시가 만료되었습니다")
                product = rec["product"]
            types = body.get("selected_types") or ["C"]
            if types != ["C"] and not inline:          # 제품을 함께 보내는 프론트는 유형을 고르기 전에 프로젝트를 만든다. 유형은 시나리오 요청에서 확인한다
                raise ApiError(422, "VALIDATION_ERROR", "이 서버는 C 유형만 처리합니다. 훅 유형에서 C 를 고르세요.")
            parse_worker_input({"project_id": "x", "product_info": product})          # 사실이 비어 있으면 여기서 걸린다
            pid = "proj_" + uuid.uuid4().hex[:8]
            DB["projects"][pid] = {"product": product, "scenarios": [], "round": 0, "selected": None, "assets": default_assets(), "status": "PRODUCT_SAVED",
                                   "flow_mode": body.get("flow_mode") or "guide_first", "frames": {}, "guide": None, "hook": None,
                                   "expires_at": later(7 * 86400), "created_at": now(), "updated_at": now()}
            return 201, summary(pid, DB["projects"][pid])

        m = re.fullmatch(r"/v1/projects/([^/]+)", path)
        if m and method == "GET":
            p = project(m.group(1))
            scenarios = [{**s, "storyboard_frames": p["frames"][s["scenario_id"]]} if s["scenario_id"] in p["frames"] else s for s in p["scenarios"]]
            h = DB["hooks"].get(p.get("hook") or "")
            job = None
            if h and h.get("deliver"):
                state = {"done": "QC_READY", "failed": "FAILED", "queued": "QUEUED"}.get(h["status"], "RUNNING")
                job = {"job_id": "job_" + p["hook"][5:], "status": state, "stage": "GENERATING" if state in ("QUEUED", "RUNNING") else state,
                       "error": (h.get("error") or {}).get("message")}
            return 200, {**summary(m.group(1), p), "product": p["product"], "scenarios": scenarios, "filming_guide": p["guide"], "latest_job": job}

        m = re.fullmatch(r"/v1/projects/([^/]+)/scenarios", path)
        if m and method == "POST":
            p = project(m.group(1))
            body = self.body()
            if body.get("types") and "C" not in body["types"]:
                raise ApiError(422, "VALIDATION_ERROR", "이 서버는 C 유형만 처리합니다. 훅 유형에서 C 를 고르세요.")
            count = max(1, min(5, int(body.get("count") or 1)))
            with LOCK:
                p["scenarios"] += new_scenarios(m.group(1), p, count)
                touch(p, "SCENARIOS_READY")
            return 200, {"project_id": m.group(1), "status": "SCENARIOS_READY", "round": p["round"], "scenarios": p["scenarios"],
                         "scenario_source": p.get("source")}

        m = re.fullmatch(r"/v1/projects/([^/]+)/scenarios/([^/]+)/storyboard", path)
        if m and method == "POST":
            p = project(m.group(1))
            s = scenario_of(p, m.group(2))
            storage = self.storage
            with RENDER_LOCK:
                frames = storyboard(s, p["assets"], os.path.join(output_root(), m.group(1), m.group(2)), lambda t: print(t, file=sys.stderr))
            frames = storage.publish_storyboard(frames)
            for f in frames:
                f["image_url"] = web_path(f["image_url"], storage)
            p.setdefault("frames", {})[m.group(2)] = frames
            touch(p, "STORYBOARD_READY")
            return 200, {"project_id": m.group(1), "scenario_id": m.group(2), "status": "STORYBOARD_READY", "frames": frames}

        m = re.fullmatch(r"/v1/projects/([^/]+)/scenarios/([^/]+)/select", path)
        if m and method == "POST":
            p = project(m.group(1))
            scenario_of(p, m.group(2))
            p["selected"] = m.group(2)
            touch(p)
            return 200, {"project_id": m.group(1), "selected_scenario_id": m.group(2)}

        m = re.fullmatch(r"/v1/projects/([^/]+)/hooks", path)
        if m and method == "POST":
            p = project(m.group(1))
            body = self.body()
            if not body.get("scenario_id"):
                raise ApiError(422, "VALIDATION_ERROR", "scenario_id 가 필요합니다")
            if p["selected"] != body["scenario_id"]:
                raise ApiError(409, "INVALID_STATE", "먼저 해당 시나리오를 select 해야 합니다")
            self.storage                 # 설정 누락은 유료 렌더를 시작하기 전에 알린다.
            hid = start_hook(m.group(1), p, body["scenario_id"], body.get("tts"))
            return 202, {"hook_id": hid, "job_id": "job_" + hid[5:], "status": "queued"}

        m = re.fullmatch(r"/v1/projects/([^/]+)/hooks/([^/]+)", path)
        if m and method == "GET":
            h = DB["hooks"].get(m.group(2))
            if not h or h["project"] != m.group(1):
                raise ApiError(404, "HOOK_NOT_FOUND", "훅을 찾을 수 없습니다")
            files = {k: ([self.url_for(x) for x in v] if isinstance(v, list) else self.url_for(v)) for k, v in h["files"].items()}
            out = {"hook_id": m.group(2), "status": h["status"], "files": files, "output_dir": os.path.relpath(h["dir"]).replace("\\", "/"), "error": h["error"]}
            for k in ("engine", "note"):
                if h.get(k):
                    out["problem_engine" if k == "engine" else k] = h[k]
            return 200, out

        # ---------- 실제 프론트(frontend/)가 쓰는 흐름: 촬영 가이드 → 견적 → 영상 올리기 → 만들기 → 결과 ----------
        m = re.fullmatch(r"/v1/projects/([^/]+)/filming-guide", path)
        if m and method == "POST":
            p = project(m.group(1))
            sid = self.body().get("scenario_id") or p["selected"]
            s = scenario_of(p, sid)
            p["selected"] = sid
            p["guide"] = {"project_id": m.group(1), "status": "GUIDE_READY", "selected_scenario_id": sid,
                          "target_body_duration_sec": round(sum(b["duration_sec"] for b in s["beats"][1:]), 2), "shots": filming_shots(s)}
            touch(p, "GUIDE_READY")
            return 200, p["guide"]

        m = re.fullmatch(r"/v1/projects/([^/]+)/estimate", path)
        if m and method == "POST":
            project(m.group(1))
            return 200, {"project_id": m.group(1), "resolution": "720p", "total_estimated_credits": 0,
                         "stages": [{"stage": "hook", "description": "로컬 C 작업자 (크레딧을 쓰지 않습니다)", "estimated_credits": 0}], "quota": quota()}

        m = re.fullmatch(r"/v1/projects/([^/]+)/uploads/complete", path)
        if m and method == "POST":
            p = project(m.group(1))
            clips = self.body().get("clips") or []
            if not clips:
                raise ApiError(422, "VALIDATION_ERROR", "clips 가 비어 있습니다")
            clip = clips[0]
            footage = self.upload_target(str(clip.get("object_key") or ""))
            if not os.path.isfile(footage):
                raise ApiError(404, "UPLOAD_NOT_FOUND", "올린 영상을 찾지 못했습니다. 다시 올려 주세요")
            p["assets"] = {**p["assets"], "product_footage": footage}          # 올린 촬영 영상이 둘째 장면부터의 실물 영상이 된다
            touch(p, "UPLOADS_READY")
            return 200, {"project_id": m.group(1), "status": "UPLOADS_READY", "upload_status": "VALIDATED",
                         "total_duration_sec": float(clip.get("duration_sec") or 0), "warnings": [], "metadata": []}

        m = re.fullmatch(r"/v1/projects/([^/]+)/renders", path)
        if m and method == "POST":
            p = project(m.group(1))
            sid = self.body().get("scenario_id") or p["selected"]
            if not sid:                                   # 시안 없이 바로 만들기: 시나리오를 하나 만들어 그것으로 간다
                with LOCK:
                    p["scenarios"] += new_scenarios(m.group(1), p, 1)
                sid = p["scenarios"][-1]["scenario_id"]
            scenario_of(p, sid)
            if not p["assets"].get("product_footage"):
                raise ApiError(409, "INVALID_STATE", "먼저 촬영한 영상을 올려 주세요")
            p["selected"] = sid
            self.storage                 # 설정 누락은 렌더를 시작하기 전에 알린다.
            hid = start_hook(m.group(1), p, sid, None, deliver=True)
            touch(p, "RENDERING")
            return 202, {"project_id": m.group(1), "job_id": "job_" + hid[5:], "status": "RENDERING", "selected_type": "C", "estimated_credits": 0,
                         "quota": quota(), "expires_at": p["expires_at"]}

        m = re.fullmatch(r"/v1/projects/([^/]+)/deliverables", path)
        if m and method == "GET":
            p = project(m.group(1))
            h = DB["hooks"].get(p.get("hook") or "")
            if not h:
                raise ApiError(404, "DELIVERABLE_NOT_FOUND", "아직 만든 영상이 없습니다")
            out = {"project_id": m.group(1), "job_id": "job_" + p["hook"][5:], "status": {"done": "QC_READY", "failed": "FAILED"}.get(h["status"], "RENDERING"),
                   "video": None, "thumbnail": None, "expires_at": p["expires_at"],
                   "ai_disclosure": {"has_ai_generated_media": True, "label_text": "AI 생성 영상 포함",
                                     "instagram_guide": "첫 장면은 AI 로 만든 영상입니다. 올릴 때 AI 생성 콘텐츠 표시를 켜 주세요."}}
            if h["status"] == "done":
                files, s = h["files"], scenario_of(p, h["scenario"])
                video = web_path(files["hook_video"], self.storage)
                out["video"] = {"stream_url": video, "download_url": video, "clean_download_url": None,
                                "srt_url": web_path(files["subtitles_srt"], self.storage) if files.get("subtitles_srt") else None,
                                "duration_sec": s["hook_duration_sec"], "width": 1080, "height": 1920, "lufs": None}
                frames = files.get("storyboard_images") or []
                if frames:
                    thumb = web_path(frames[min(1, len(frames) - 1)], self.storage)
                    out["thumbnail"] = {"image_url": thumb, "download_url": thumb, "safe_zone_1_1_ok": None, "headline_lines": [s["hook_title"]]}
            return 200, out

        m = re.fullmatch(r"/v1/projects/([^/]+)/thumbnail", path)
        if m and method == "POST":
            p = project(m.group(1))
            h = DB["hooks"].get(p.get("hook") or "")
            frames = (h or {}).get("files", {}).get("storyboard_images") or []
            if not frames:
                raise ApiError(404, "DELIVERABLE_NOT_FOUND", "아직 만든 영상이 없습니다")
            thumb = web_path(frames[min(1, len(frames) - 1)], self.storage)
            return 200, {"project_id": m.group(1), "image_url": thumb, "download_url": thumb}

        m = re.fullmatch(r"/v1/projects/([^/]+)/outputs", path)
        if m and method == "GET":
            project(m.group(1))
            return 200, {"project_id": m.group(1), "outputs": [{"hook_id": k, "output_dir": os.path.relpath(h["dir"]).replace("\\", "/")}
                                                               for k, h in DB["hooks"].items() if h["project"] == m.group(1)]}
        raise ApiError(404, "NOT_FOUND", f"정의되지 않은 경로 {method} {path}")


def main() -> int:
    load_env()
    try:
        storage = DeliveryStorage()
    except StorageError as e:
        print(str(e), file=sys.stderr)
        return 1
    port = int(os.environ.get("C_SERVER_PORT", "8080"))
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    names = list(presets())
    print(f"C 훅 작업자 서버: http://127.0.0.1:{port}/" + (f"?preset={names[0]}" if names else "") + "   (끝내려면 Ctrl+C)", file=sys.stderr)
    if names:
        print("프리셋(examples 폴더 이름): " + ", ".join(names), file=sys.stderr)
    print(f"결과 저장소: {storage.backend}", file=sys.stderr)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
