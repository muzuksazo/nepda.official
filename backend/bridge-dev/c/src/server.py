"""C 훅 작업자 로컬 서버. bridge-dev 더미 화면(index.html)이 부르는 API 를 이 작업자 코드로 처리한다.

    cd backend/bridge-dev/c
    python -m src.server            # http://127.0.0.1:8080
    브라우저: http://127.0.0.1:8080/?preset=piev          (C 유형·실제 호출·제품 정보가 채워진 화면)
              http://127.0.0.1:8080/?preset=piev&run=1    (열자마자 "처음부터 끝까지" 실행)

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

from . import tts as tts_mod
from .check import check_scenario
from .cli import load_env
from .generate import generate_scenarios
from .render import render_hook, storyboard
from .schema import InputError, parse_worker_input

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))          # c/
INDEX_HTML = os.path.join(os.path.dirname(HERE), "index.html")               # bridge-dev/index.html
DB: dict = {"infos": {}, "projects": {}, "hooks": {}}
LOCK = threading.Lock()
RENDER_LOCK = threading.Lock()                                               # Blender·ffmpeg 는 한 번에 하나만

PRESETS = {
    "piev": {
        "name": "피에브 에어워셔 피톤치드",
        "facts_from": os.path.join(HERE, "examples", "piev", "05_worker-input.round3.json"),
    },
}

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
    var m = (document.getElementById("results").textContent || "").match(/hook_video: (http\\S+?\\.mp4)/g) || [];
    m.forEach(function (t) {
      var url = t.replace("hook_video: ", "");
      if (seen[url]) return; seen[url] = true;
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
        with RENDER_LOCK:
            tts = dict(h["tts"])
            if tts.get("enabled", True) and not tts_mod.available():
                tts["enabled"] = False
                h["note"] = "INWORLD_API_KEY 가 없어 음성 없이 만들었습니다."
            files = render_hook(scenario_of(p, h["scenario"]), p["assets"], h["dir"], tts=tts, log=lambda m: print(m, file=sys.stderr))
        h["engine"] = files.pop("problem_engine", None)
        h["files"], h["status"] = files, "done"
    except Exception as e:          # 작업 스레드에서 난 오류는 폴링 응답으로 알려야 한다
        h["status"], h["error"] = "failed", {"code": "HOOK_RENDER_FAILED", "message": str(e)[:600]}
        print(f"hook {hid} failed: {e}", file=sys.stderr)


class Handler(BaseHTTPRequestHandler):
    server_version = "CWorker/0.1"

    def log_message(self, fmt, *args):
        print("%s %s" % (self.command, self.path), file=sys.stderr)

    # ---------- 응답 ----------
    def cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

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
        rel = os.path.relpath(os.path.abspath(path), output_root()).replace("\\", "/")
        return f"http://{self.headers.get('Host', '127.0.0.1:8080')}/files/{rel}"

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
        if m and m.group(1) in PRESETS:
            src = json.load(open(PRESETS[m.group(1)]["facts_from"], encoding="utf-8"))["product_info"]
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

    def route(self, method: str) -> None:
        path, _, query = self.path.partition("?")
        try:
            if method == "GET" and path in ("/", "/index.html"):
                return self.send_index(query)
            if method == "GET" and path.startswith("/files/"):
                from urllib.parse import unquote
                return self.send_file(unquote(path[len("/files/"):]))
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
        except RuntimeError as e:
            self.fail(ApiError(502, "UPSTREAM_ERROR", str(e)[:600]))

    def api(self, method: str, path: str) -> tuple[int, dict]:
        if method == "POST" and path == "/v1/product-info":
            body = self.body()
            product = body.get("product") or {}
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
            product = body.get("product")
            if not product:
                rec = next((r for r in DB["infos"].values() if r["product_info_id"] == body.get("product_info_id")), None)
                if not rec:
                    raise ApiError(404, "PRODUCT_INFO_NOT_FOUND", "product_info_id 가 없거나 캐시가 만료되었습니다")
                product = rec["product"]
            types = body.get("selected_types") or ["C"]
            if types != ["C"]:
                raise ApiError(422, "VALIDATION_ERROR", "이 서버는 C 유형만 처리합니다. 훅 유형에서 C 를 고르세요.")
            parse_worker_input({"project_id": "x", "product_info": product})          # 사실이 비어 있으면 여기서 걸린다
            pid = "proj_" + uuid.uuid4().hex[:8]
            DB["projects"][pid] = {"product": product, "scenarios": [], "round": 0, "selected": None, "assets": default_assets()}
            return 201, {"project_id": pid, "status": "PRODUCT_SAVED", "flow_mode": body.get("flow_mode") or "guide_first", "product_name": product["name"],
                         "category": product.get("category"), "selected_types": types, "selected_scenario_id": None, "latest_job_id": None,
                         "expires_at": later(7 * 86400), "created_at": now(), "updated_at": now()}

        m = re.fullmatch(r"/v1/projects/([^/]+)/scenarios", path)
        if m and method == "POST":
            p = project(m.group(1))
            count = max(1, min(5, int(self.body().get("count") or 1)))
            with LOCK:
                p["scenarios"] += new_scenarios(m.group(1), p, count)
            return 200, {"project_id": m.group(1), "status": "SCENARIOS_READY", "round": p["round"], "scenarios": p["scenarios"],
                         "scenario_source": p.get("source")}

        m = re.fullmatch(r"/v1/projects/([^/]+)/scenarios/([^/]+)/storyboard", path)
        if m and method == "POST":
            p = project(m.group(1))
            s = scenario_of(p, m.group(2))
            with RENDER_LOCK:
                frames = storyboard(s, p["assets"], os.path.join(output_root(), m.group(1), m.group(2)), lambda t: print(t, file=sys.stderr))
            for f in frames:
                f["image_url"] = self.url_for(f["image_url"])
            return 200, {"project_id": m.group(1), "scenario_id": m.group(2), "status": "STORYBOARD_READY", "frames": frames}

        m = re.fullmatch(r"/v1/projects/([^/]+)/scenarios/([^/]+)/select", path)
        if m and method == "POST":
            p = project(m.group(1))
            scenario_of(p, m.group(2))
            p["selected"] = m.group(2)
            return 200, {"project_id": m.group(1), "selected_scenario_id": m.group(2)}

        m = re.fullmatch(r"/v1/projects/([^/]+)/hooks", path)
        if m and method == "POST":
            p = project(m.group(1))
            body = self.body()
            if not body.get("scenario_id"):
                raise ApiError(422, "VALIDATION_ERROR", "scenario_id 가 필요합니다")
            if p["selected"] != body["scenario_id"]:
                raise ApiError(409, "INVALID_STATE", "먼저 해당 시나리오를 select 해야 합니다")
            hid = "hook_" + uuid.uuid4().hex[:8]
            DB["hooks"][hid] = {"project": m.group(1), "scenario": body["scenario_id"], "tts": body.get("tts") or {"enabled": True}, "status": "queued",
                                "files": {}, "dir": os.path.join(output_root(), m.group(1), hid), "error": None}
            threading.Thread(target=run_hook, args=(hid,), daemon=True).start()
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

        m = re.fullmatch(r"/v1/projects/([^/]+)/outputs", path)
        if m and method == "GET":
            project(m.group(1))
            return 200, {"project_id": m.group(1), "outputs": [{"hook_id": k, "output_dir": os.path.relpath(h["dir"]).replace("\\", "/")}
                                                               for k, h in DB["hooks"].items() if h["project"] == m.group(1)]}
        raise ApiError(404, "NOT_FOUND", f"정의되지 않은 경로 {method} {path}")


def main() -> int:
    load_env()
    port = int(os.environ.get("C_SERVER_PORT", "8080"))
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"C 훅 작업자 서버: http://127.0.0.1:{port}/?preset=piev   (끝내려면 Ctrl+C)", file=sys.stderr)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
