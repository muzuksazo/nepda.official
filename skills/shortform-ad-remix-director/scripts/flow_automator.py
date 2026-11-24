#!/usr/bin/env python3
"""Programmatic Google Flow browser automator & visual QC sheet builder.

Story-agnostic CLI runner built on top of `ugot-browser` (`backend="extension"`),
`PIL`, `ffmpeg`/`ffprobe`, and `sips` to eliminate interactive browser loops and
minimize LLM token consumption.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont, ImageOps

DEFAULT_BACKEND = "extension"
DOWNLOAD_TIMEOUT_MS = 45000
POLICY_REFUSAL_TERMS = (
    "policy",
    "violat",
    "생성할 수 없",
    "정책",
    "unable to generate",
    "can't generate",
    "blocked",
)
IGNORED_TILE_ARIA = {
    "",
    "즐겨찾기",
    "프롬프트 재사용",
    "옵션 더보기",
    "생성 시작",
    "설정 트리거",
    "Flow 에이전트",
    "프롬프트 상자에 소재 추가",
    "프롬프트 지우기",
    "소재",
    "시작",
    "종료",
    "첫 번째 프레임과 마지막 프레임 바꾸기",
}


# ---------------------------------------------------------------------------
# ugot-browser & shell helpers
# ---------------------------------------------------------------------------

def ugot(tool: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    cmd = ["ugot-browser", "call", tool, "--json", json.dumps(payload, ensure_ascii=False)]
    last_err = ""
    for attempt in range(4):
        proc = subprocess.run(cmd, capture_output=True, text=True)
        raw_out = f"{proc.stdout.strip()} {proc.stderr.strip()}".strip()
        if proc.returncode == 0:
            data = json.loads(proc.stdout)
            if not data.get("isError"):
                sc = data.get("structuredContent")
                if sc is not None:
                    return sc
                content = data.get("content") or []
                if content and isinstance(content[0], dict) and "text" in content[0]:
                    return json.loads(content[0]["text"])
                return data
            last_err = f"ugot {tool} isError: {data}"
            sc_err = (data.get("structuredContent") or {}).get("error") or {}
            is_retry_tool = bool(sc_err.get("retrySafe")) or tool in ("read_page", "evaluate")
            is_doc_changed = is_retry_tool and "document_changed" in raw_out.lower()
            retryable = is_doc_changed or (
                bool(sc_err.get("retrySafe")) and ("timeout" in str(sc_err.get("code", "")).lower() or "did not answer" in raw_out.lower())
            )
        else:
            last_err = f"ugot {tool} rc={proc.returncode}: {raw_out}"
            is_retry_tool = '"retrySafe":true' in raw_out or '"retrySafe": true' in raw_out or tool in ("read_page", "evaluate")
            is_doc_changed = is_retry_tool and "document_changed" in raw_out.lower()
            retryable = is_doc_changed or (
                is_retry_tool
                and ("timeout" in raw_out.lower() or "did not answer" in raw_out.lower())
            )
        if retryable and attempt < 3:
            wait_s = 1.0 * (attempt + 1) if is_doc_changed else 2.0 * (attempt + 1)
            print(f"[ugot-retry] {tool} transient error (attempt {attempt + 1}/3); sleeping {wait_s:.0f}s...", flush=True)
            time.sleep(wait_s)
            continue
        raise RuntimeError(last_err)
    raise RuntimeError(last_err)


def read_dom(tab_id: int) -> Dict[str, Any]:
    return ugot("read_page", {"backend": DEFAULT_BACKEND, "tabId": tab_id})


def read_text(tab_id: int) -> str:
    res = ugot("read_page", {"backend": DEFAULT_BACKEND, "tabId": tab_id, "format": "text"})
    return res.get("text", "")


def evaluate_js(tab_id: int, code: str) -> Any:
    res = ugot("evaluate", {"backend": DEFAULT_BACKEND, "tabId": tab_id, "code": code})
    return res.get("result")


def click_xy(tab_id: int, x: int, y: int) -> None:
    ugot("click", {"backend": DEFAULT_BACKEND, "tabId": tab_id, "x": int(x), "y": int(y)})


def click_ref(tab_id: int, ref: str) -> None:
    ugot("click", {"backend": DEFAULT_BACKEND, "tabId": tab_id, "ref": ref})


def press_key(tab_id: int, key: str) -> None:
    ugot("press_key", {"backend": DEFAULT_BACKEND, "tabId": tab_id, "key": key})


def find_ref(
    dom: Dict[str, Any],
    *,
    role: Optional[str] = None,
    name: Optional[str] = None,
    name_contains: Optional[str] = None,
) -> Optional[str]:
    for el in dom.get("elements", []):
        if role is not None and el.get("role") != role:
            continue
        el_name = el.get("name", "")
        if name is not None and el_name.strip() != name:
            continue
        if name_contains is not None and name_contains not in el_name:
            continue
        return el.get("ref")
    return None


def require_ref(
    dom: Dict[str, Any],
    *,
    role: Optional[str] = None,
    name: Optional[str] = None,
    name_contains: Optional[str] = None,
    label: str = "element",
) -> str:
    ref = find_ref(dom, role=role, name=name, name_contains=name_contains)
    if not ref:
        raise RuntimeError(f"Could not find {label} (role={role}, name={name}, contains={name_contains})")
    return ref


def close_overlays(tab_id: int) -> None:
    """Dismiss any open settings popup, account drawer, or asset picker popover."""
    for _ in range(4):
        dom = read_dom(tab_id)
        els = dom.get("elements", [])
        acct_close = find_ref(dom, role="button", name="계정 패널 닫기")
        if acct_close:
            click_ref(tab_id, acct_close)
            time.sleep(0.35)
            continue
        has_settings = any(el.get("role") == "radio" and ("이미지" in el.get("name", "") or "동영상" in el.get("name", "")) for el in els)
        has_picker = any(el.get("role") == "option" for el in els) or (
            find_ref(dom, role="button", name="닫기") is not None
            and find_ref(dom, role="textbox", name="애셋 검색") is not None
        )
        has_backdrop = bool(
            evaluate_js(
                tab_id,
                "!!document.querySelector('.cdk-overlay-backdrop, [role=\"dialog\"], [role=\"menu\"]')",
            )
        )
        if has_settings or has_picker or has_backdrop:
            evaluate_js(
                tab_id,
                "document.querySelector('.cdk-overlay-backdrop')?.click(); "
                "document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',code:'Escape',bubbles:true}))",
            )
            try:
                press_key(tab_id, "Escape")
            except RuntimeError as exc:
                msg = str(exc)
                if "stale_ref" not in msg and "obscured" not in msg:
                    raise
            time.sleep(0.45)
        else:
            break


def _settings_popover_open(dom: Dict[str, Any]) -> bool:
    return any(
        el.get("role") == "radio" and ("이미지" in el.get("name", "") or "동영상" in el.get("name", ""))
        for el in dom.get("elements", [])
    )


def open_settings_popover(tab_id: int) -> Dict[str, Any]:
    radio_cnt = int(evaluate_js(tab_id, 'document.querySelectorAll(\'[role="radio"]\').length') or 0)
    if radio_cnt == 0:
        evaluate_js(
            tab_id,
            """(() => {
              const b = document.querySelector('[aria-label="설정 트리거"]');
              if (b) {
                b.focus();
                b.dispatchEvent(new MouseEvent('mousedown', {bubbles: true}));
                b.click();
              }
            })()""",
        )
        for _ in range(4):
            time.sleep(0.25)
            if int(evaluate_js(tab_id, 'document.querySelectorAll(\'[role="radio"]\').length') or 0) > 0:
                break
        else:
            dom_tmp = read_dom(tab_id)
            trig = find_ref(dom_tmp, name="설정 트리거")
            if trig and int(evaluate_js(tab_id, 'document.querySelectorAll(\'[role="radio"]\').length') or 0) == 0:
                try:
                    click_ref(tab_id, trig)
                except RuntimeError:
                    pass
                for _ in range(3):
                    time.sleep(0.25)
                    if int(evaluate_js(tab_id, 'document.querySelectorAll(\'[role="radio"]\').length') or 0) > 0:
                        break
    return read_dom(tab_id)


# ---------------------------------------------------------------------------
# Flow URL / grid inspection
# ---------------------------------------------------------------------------

def extract_src_key(src: Optional[str]) -> Optional[str]:
    if not src:
        return None
    for pat in (r"/asb/([^=?&/]+)", r"/image/([^=?&/]+)", r"/video/([^=?&/]+)"):
        m = re.search(pat, src)
        if m:
            return m.group(1)
    return src.split("?")[0]


def get_page_url(tab_id: int) -> str:
    return str(evaluate_js(tab_id, "location.href") or "")


def ensure_tab_active(tab_id: int) -> None:
    """Bring the dedicated Flow Chrome tab to active focus so actions never stall 90s."""
    try:
        ugot("switch_tab", {"backend": DEFAULT_BACKEND, "tabId": tab_id})
    except Exception:
        pass


def ensure_grid_view(tab_id: int) -> None:
    ensure_tab_active(tab_id)
    url = get_page_url(tab_id)
    if "/edit/" in url:
        dom = read_dom(tab_id)
        back = find_ref(dom, name="이전 페이지로 이동하는 뒤로 버튼")
        if back:
            click_ref(tab_id, back)
        else:
            press_key(tab_id, "Escape")
        for _ in range(15):
            time.sleep(0.4)
            if "/edit/" not in get_page_url(tab_id):
                time.sleep(0.6)
                return
        raise RuntimeError(f"Still on edit view after attempting back: {get_page_url(tab_id)}")


def scroll_grid_top(tab_id: int) -> None:
    js = """(() => {
      const nodes = [...document.querySelectorAll("img, video")].filter(el => {
        const r = el.getBoundingClientRect();
        return r.width > 60 && r.height > 60;
      });
      if (nodes.length) {
        let p = nodes[0].parentElement;
        while (p) {
          if (p.scrollTop > 0) p.scrollTop = 0;
          p = p.parentElement;
        }
      }
      window.scrollTo(0, 0);
      return true;
    })()"""
    evaluate_js(tab_id, js)


def poll_wave_snapshot(tab_id: int, max_items: int = 24) -> Dict[str, Any]:
    """Scroll to grid top and read text, running status, policy hits, and tile keys in 1 JS call."""
    terms_js = json.dumps(list(POLICY_REFUSAL_TERMS), ensure_ascii=False)
    js = f"""(() => {{
      const nodes = [...document.querySelectorAll("img, video")].filter(el => {{
        const r = el.getBoundingClientRect();
        return r.width > 60 && r.height > 60;
      }});
      if (nodes.length) {{
        let p = nodes[0].parentElement;
        while (p) {{
          if (p.scrollTop > 0) p.scrollTop = 0;
          p = p.parentElement;
        }}
      }}
      window.scrollTo(0, 0);

      const seen = new Set();
      const rawSrcs = [];
      for (const el of document.querySelectorAll("img, video")) {{
        const s = el.currentSrc || el.src || el.poster || "";
        if (!s) continue;
        if (el.tagName === "IMG") {{
          if (!(s.includes("/asb/") || s.startsWith("blob:"))) continue;
          if ((el.className || "").includes("detail-preview")) continue;
        }}
        const r = el.getBoundingClientRect();
        if (r.width <= 60 || r.height <= 60) continue;
        if (!seen.has(s)) {{
          seen.add(s);
          rawSrcs.push(s);
          if (rawSrcs.length >= {int(max_items)}) break;
        }}
      }}

      const txt = (document.body && document.body.innerText) ? document.body.innerText : "";
      const terms = {terms_js};
      let policyCount = 0;
      for (const line of txt.split(/\\r?\\n/)) {{
        const low = line.toLowerCase();
        if (terms.some(t => low.includes(t))) policyCount++;
      }}
      const stillRunning = /\\b\\d+%/.test(txt) || /생성\\s*중|대기\\s*중|Generating|Queued/i.test(txt);
      return {{ text: txt, policy_count: policyCount, still_running: stillRunning, srcs: rawSrcs }};
    }})()"""
    snap = evaluate_js(tab_id, js) or {}
    if not isinstance(snap, dict):
        snap = {}
    keys: List[str] = []
    seen_k = set()
    for src in snap.get("srcs") or []:
        sk = extract_src_key(str(src))
        if sk and sk not in seen_k:
            seen_k.add(sk)
            keys.append(sk)
    return {
        "text": str(snap.get("text") or ""),
        "policy_count": int(snap.get("policy_count") or 0),
        "still_running": bool(snap.get("still_running")),
        "keys": keys,
    }


def get_media_state(tab_id: int) -> Dict[str, Any]:
    ignored_js = json.dumps(sorted(IGNORED_TILE_ARIA), ensure_ascii=False)
    js = f"""(() => {{
      const ignored = new Set({ignored_js});
      const btns = [...document.querySelectorAll("button[aria-label]")].map(b => {{
        const r = b.getBoundingClientRect();
        return {{aria: b.getAttribute("aria-label") || "", left: r.left, right: r.right, top: r.top, bottom: r.bottom, w: r.width, h: r.height}};
      }}).filter(b => b.w > 40 && !ignored.has(b.aria));

      function inferTitle(r) {{
        const cx = r.left + r.width / 2;
        const cy = r.top + r.height / 2;
        for (const b of btns) {{
          if (cx >= b.left - 8 && cx <= b.right + 8 && cy >= b.top - 8 && cy <= b.bottom + 8) {{
            return b.aria;
          }}
        }}
        // Also check button directly below tile center
        for (const b of btns) {{
          const bx = (b.left + b.right) / 2;
          if (Math.abs(bx - cx) < 120 && b.top >= r.bottom - 10 && b.top <= r.bottom + 60) {{
            return b.aria;
          }}
        }}
        return "";
      }}

      const tiles = [];
      const imgs = [...document.querySelectorAll("img")].filter(i => {{
        if (!i.src) return false;
        if (!(i.src.includes("/asb/") || i.src.startsWith("blob:"))) return false;
        const r = i.getBoundingClientRect();
        return r.width > 60 && r.height > 60 && !i.className.includes("detail-preview");
      }});
      for (const el of imgs) {{
        const r = el.getBoundingClientRect();
        tiles.push({{
          kind: "image",
          src: el.src,
          alt: el.alt || "",
          title: inferTitle(r),
          w: Math.round(r.width),
          h: Math.round(r.height),
          nw: el.naturalWidth || 0,
          nh: el.naturalHeight || 0,
          top: Math.round(r.top),
          left: Math.round(r.left),
          x: Math.round(r.left + r.width / 2),
          y: Math.round(r.top + r.height / 2)
        }});
      }}
      const vids = [...document.querySelectorAll("video")].filter(v => {{
        const s = v.currentSrc || v.src || v.poster || "";
        const r = v.getBoundingClientRect();
        return s && r.width > 60 && r.height > 60;
      }});
      for (const v of vids) {{
        const r = v.getBoundingClientRect();
        tiles.push({{
          kind: "video",
          src: v.currentSrc || v.src || v.poster || "",
          alt: v.getAttribute("aria-label") || "",
          title: inferTitle(r),
          w: Math.round(r.width),
          h: Math.round(r.height),
          nw: v.videoWidth || 0,
          nh: v.videoHeight || 0,
          top: Math.round(r.top),
          left: Math.round(r.left),
          x: Math.round(r.left + r.width / 2),
          y: Math.round(r.top + r.height / 2)
        }});
      }}
      tiles.sort((a, b) => (Math.abs(a.top - b.top) > 30 ? a.top - b.top : a.left - b.left));
      const dedup = [];
      for (const t of tiles) {{
        const dupIdx = dedup.findIndex(d => Math.abs(d.left - t.left) < 15 && Math.abs(d.top - t.top) < 15);
        if (dupIdx >= 0) {{
          if (t.kind === "video" && dedup[dupIdx].kind !== "video") dedup[dupIdx] = t;
        }} else {{
          dedup.push(t);
        }}
      }}
      const first = dedup[0] || null;
      return {{
        url: location.href,
        count: dedup.length,
        firstSrc: first ? first.src : null,
        firstKey: null,
        firstKind: first ? first.kind : null,
        firstBox: first,
        items: dedup
      }};
    }})()"""
    st = evaluate_js(tab_id, js) or {"count": 0, "items": []}
    for it in st.get("items", []):
        it["src_key"] = extract_src_key(it.get("src"))
    if st.get("firstSrc"):
        st["firstKey"] = extract_src_key(st["firstSrc"])
    return st


# ---------------------------------------------------------------------------
# Project ledger & logging
# ---------------------------------------------------------------------------

_JOBS_FILE_OVERRIDE: Optional[str] = None


def _resolve_jobs_path(project_dir: str, jobs_file: Optional[str] = None) -> str:
    cand = jobs_file or _JOBS_FILE_OVERRIDE
    if cand:
        return cand if os.path.isabs(cand) else os.path.join(project_dir, cand)
    for name in ("06_jobs.json", "05_jobs.json"):
        p = os.path.join(project_dir, name)
        if os.path.exists(p):
            return p
    return os.path.join(project_dir, "06_jobs.json")


def load_jobs(project_dir: str, jobs_file: Optional[str] = None) -> Dict[str, Any]:
    path = _resolve_jobs_path(project_dir, jobs_file)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _all_image_assets(jobs: Dict[str, Any]) -> List[Dict[str, Any]]:
    return list(jobs.get("references", [])) + list(jobs.get("plates", []))


def ledger_path(project_dir: str) -> str:
    return os.path.join(project_dir, "refs", ".flow_assets.json")


def load_ledger(project_dir: str) -> Dict[str, Any]:
    lp = ledger_path(project_dir)
    if os.path.exists(lp):
        with open(lp, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_ledger(project_dir: str, data: Dict[str, Any]) -> None:
    lp = ledger_path(project_dir)
    os.makedirs(os.path.dirname(lp), exist_ok=True)
    with open(lp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def append_generation_log(
    project_dir: str,
    *,
    unit_id: str,
    take: str,
    platform_cfg: str,
    credits_str: str,
    result_file: str,
    status: str,
    notes: str,
) -> None:
    log_path = os.path.join(project_dir, "08_generation_log.md")
    if not os.path.exists(log_path):
        return
    row = f"| {unit_id} | {take} | {platform_cfg} | {credits_str} | `{result_file}` | {status} | {notes} |\n"
    with open(log_path, "r", encoding="utf-8") as f:
        content = f.read()
    if f"| {unit_id} | {take} |" in content and f"`{result_file}`" in content:
        return
    if content and not content.endswith("\n"):
        content += "\n"
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(content + row)


# ---------------------------------------------------------------------------
# Lightbox Download (hover-free!)
# ---------------------------------------------------------------------------

def convert_or_move_image(src_path: str, out_file: str) -> Tuple[int, Tuple[int, int]]:
    os.makedirs(os.path.dirname(out_file), exist_ok=True)
    ext = os.path.splitext(src_path)[1].lower()
    if ext == ".png":
        shutil.copy2(src_path, out_file)
    else:
        subprocess.run(
            ["sips", "-s", "format", "png", src_path, "--out", out_file],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    if os.path.exists(src_path) and os.path.abspath(src_path) != os.path.abspath(out_file):
        os.remove(src_path)
    sz = os.path.getsize(out_file)
    if sz <= 0:
        raise RuntimeError(f"Zero-byte image saved at {out_file}")
    with Image.open(out_file) as im:
        dims = im.size
    return sz, dims


def ffprobe_info(video_path: str) -> Dict[str, Any]:
    cmd = [
        "ffprobe",
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        video_path,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffprobe failed on {video_path}: {proc.stderr}")
    data = json.loads(proc.stdout)
    streams = data.get("streams", [])
    vstreams = [s for s in streams if s.get("codec_type") == "video"]
    astreams = [s for s in streams if s.get("codec_type") == "audio"]
    if not vstreams:
        raise RuntimeError(f"No video stream in {video_path}")
    vs = vstreams[0]
    dur = float(data.get("format", {}).get("duration") or vs.get("duration") or 0.0)
    if dur <= 0.0:
        raise RuntimeError(f"Zero/invalid duration in {video_path}: {dur}")
    r_fps = vs.get("r_frame_rate", "24/1")
    num, den = (int(x) for x in r_fps.split("/")) if "/" in r_fps else (int(r_fps), 1)
    fps = round(num / max(den, 1), 2)
    return {
        "width": int(vs.get("width", 0)),
        "height": int(vs.get("height", 0)),
        "duration": dur,
        "fps": fps,
        "has_audio": len(astreams) > 0,
        "bytes": os.path.getsize(video_path),
    }


_DL_EXCLUDE_MENU_WORDS = (
    "미디어 다운로드",
    "즐겨찾기",
    "공유",
    "휴지통",
    "삭제",
    "신고",
    "재사용",
    "프롬프트",
)
_DL_VIDEO_QUAL_WORDS = ("360p", "720p", "1080p", "원본", "다운로드")
_DL_IMAGE_QUAL_WORDS = ("1K", "2K", "4K", "원본", "다운로드")


def _open_lightbox_download_menu(tab_id: int, *, media: str = "video") -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Open download submenu inside Flow /edit/ lightbox, handling compact viewport collapse."""
    dom = read_dom(tab_id)
    dl_btn = find_ref(dom, role="button", name="미디어 다운로드")
    if dl_btn:
        try:
            click_ref(tab_id, dl_btn)
        except RuntimeError:
            evaluate_js(
                tab_id,
                'document.querySelector(\'button[aria-label="미디어 다운로드"]\')?.click()',
            )
        time.sleep(0.45)
        dom2 = read_dom(tab_id)
    else:
        more_btn = find_ref(dom, role="button", name="옵션 더보기")
        if more_btn:
            try:
                click_ref(tab_id, more_btn)
            except RuntimeError:
                evaluate_js(
                    tab_id,
                    'document.querySelector(\'button[aria-label="옵션 더보기"]\')?.click()',
                )
        else:
            clicked_more = evaluate_js(
                tab_id,
                """(() => {
                  const b = document.querySelector('button[aria-label="옵션 더보기"]');
                  if (!b) return false;
                  b.click();
                  return true;
                })()""",
            )
            if not clicked_more:
                raise RuntimeError("Neither '미디어 다운로드' nor '옵션 더보기' button found in /edit/ lightbox")
        time.sleep(0.45)
        dom_more = read_dom(tab_id)
        dl_item = find_ref(dom_more, role="menuitem", name_contains="미디어 다운로드") or find_ref(
            dom_more, role="menuitem", name_contains="다운로드"
        )
        if dl_item:
            try:
                click_ref(tab_id, dl_item)
            except RuntimeError:
                evaluate_js(
                    tab_id,
                    """(() => {
                      const items = [...document.querySelectorAll('[role="menuitem"]')];
                      const hit = items.find(i => (i.innerText || '').includes('미디어 다운로드'))
                        || items.find(i => (i.innerText || '').includes('다운로드'));
                      if (hit) hit.click();
                    })()""",
                )
        else:
            clicked_item = evaluate_js(
                tab_id,
                """(() => {
                  const items = [...document.querySelectorAll('[role="menuitem"]')];
                  const hit = items.find(i => (i.innerText || '').includes('미디어 다운로드'))
                    || items.find(i => (i.innerText || '').includes('다운로드'));
                  if (!hit) return false;
                  hit.click();
                  return true;
                })()""",
            )
            if not clicked_item:
                raise RuntimeError("No '미디어 다운로드' menuitem inside '옵션 더보기' menu")
        time.sleep(0.45)
        dom2 = read_dom(tab_id)

    qual_words = _DL_VIDEO_QUAL_WORDS if media == "video" else _DL_IMAGE_QUAL_WORDS
    raw_items = [el for el in dom2.get("elements", []) if el.get("role") == "menuitem"]
    filtered: List[Dict[str, Any]] = []
    for el in raw_items:
        nm = (el.get("name") or "").strip()
        if any(bad in nm for bad in _DL_EXCLUDE_MENU_WORDS):
            continue
        if any(kw in nm for kw in qual_words):
            filtered.append(el)
    return dom2, filtered


def _open_tile_to_lightbox(tab_id: int, box: Dict[str, Any], src_key: Optional[str], label: str) -> None:
    """Click grid tile using upper safe band with stale_ref/JS ancestor fallback until /edit/ opens."""
    ensure_tab_active(tab_id)
    safe_y = int(box.get("top", 0)) + min(48, max(20, int(box.get("h", 120)) // 5))
    try:
        click_xy(tab_id, box["x"], safe_y if box.get("top") is not None else box["y"])
    except RuntimeError as exc:
        print(f"[tile-open] click_xy fallback for {label}: {exc}", flush=True)

    for _ in range(8):
        time.sleep(0.35)
        if "/edit/" in get_page_url(tab_id):
            return

    if src_key:
        sk_js = json.dumps(src_key[:40], ensure_ascii=False)
        evaluate_js(
            tab_id,
            f"""(() => {{
              const imgs = Array.from(document.querySelectorAll('img, video'));
              const hit = imgs.find(i => (i.currentSrc || i.src || i.poster || '').includes({sk_js}));
              if (hit) hit.click();
            }})()""",
        )
        for _ in range(4):
            time.sleep(0.35)
            if "/edit/" in get_page_url(tab_id):
                return
        evaluate_js(
            tab_id,
            f"""(() => {{
              const imgs = Array.from(document.querySelectorAll('img, video'));
              const hit = imgs.find(i => (i.currentSrc || i.src || i.poster || '').includes({sk_js}));
              const anc = hit && hit.closest('a, button, [role="button"]');
              if (anc) anc.click(); else if (hit && hit.parentElement) hit.parentElement.click();
            }})()""",
        )
        for _ in range(8):
            time.sleep(0.4)
            if "/edit/" in get_page_url(tab_id):
                return

    raise RuntimeError(f"Clicking {label} did not navigate to /edit/ lightbox")


def _download_open_video_lightbox(
    tab_id: int,
    project_dir: str,
    rel_out: str,
    *,
    upscale_1080p: bool = False,
    src_key: Optional[str] = None,
    grid_title: str = "",
) -> Dict[str, Any]:
    """Download video while /edit/ Lightbox is already open, probe with ffprobe, and return to grid."""
    ensure_tab_active(tab_id)
    dom = read_dom(tab_id)
    title = grid_title
    for el in dom.get("elements", []):
        if el.get("role") == "textbox" and el.get("name") == "수정 가능한 텍스트":
            title = el.get("value", "") or title
            break

    dom2, menu_items = _open_lightbox_download_menu(tab_id, media="video")
    out_file = os.path.join(project_dir, rel_out)
    os.makedirs(os.path.dirname(out_file), exist_ok=True)

    menu_names = [el.get("name", "") for el in menu_items]
    print(f"[lightbox-video] download menuitems: {menu_names}", flush=True)

    chosen_ref = None
    chosen_label = ""
    upscale_used = False

    if upscale_1080p:
        for el in menu_items:
            nm = el.get("name", "")
            # Free 1080p upscale must NOT show a nonzero credit price like '5 크레딧'
            if "1080p" in nm and not re.search(r"[1-9]\d*\s*크레딧", nm):
                chosen_ref = el["ref"]
                chosen_label = nm
                upscale_used = True
                break

    if not chosen_ref:
        for kw in ("원본", "360p", "720p", "다운로드"):
            for el in menu_items:
                nm = el.get("name", "")
                if kw in nm:
                    chosen_ref = el["ref"]
                    chosen_label = nm
                    break
            if chosen_ref:
                break

    if not chosen_ref and menu_items:
        chosen_ref = menu_items[0]["ref"]
        chosen_label = menu_items[0].get("name", "")

    if not chosen_ref:
        raise RuntimeError(f"No video download menuitem found; menuitems={menu_items}")

    fn = None
    try:
        dl_res = ugot(
            "click_and_download",
            {"backend": DEFAULT_BACKEND, "tabId": tab_id, "ref": chosen_ref, "timeoutMs": DOWNLOAD_TIMEOUT_MS},
        )
        fn = dl_res.get("filename")
    except Exception as exc:
        # If 1080p triggered async server-side upscale, wait up to 90s for download or re-open menu for 1080p/fallback
        if upscale_used:
            print(f"[lightbox-video] '{chosen_label}' queued async upscale ({exc}); polling up to 90s...", flush=True)
            for _ in range(30):
                time.sleep(3.0)
                txt = read_text(tab_id)
                if not re.search(r"\b\d+%", txt) and "업스케일" not in txt:
                    break
            dom_m2, m2 = _open_lightbox_download_menu(tab_id, media="video")
            fallback_ref = None
            for kw in ("1080p", "원본", "720p", "360p"):
                hit = next((el["ref"] for el in m2 if kw in el.get("name", "")), None)
                if hit:
                    fallback_ref = hit
                    break
            if not fallback_ref and m2:
                fallback_ref = m2[0]["ref"]
            if fallback_ref:
                dl_res2 = ugot(
                    "click_and_download",
                    {"backend": DEFAULT_BACKEND, "tabId": tab_id, "ref": fallback_ref, "timeoutMs": DOWNLOAD_TIMEOUT_MS},
                )
                fn = dl_res2.get("filename")
        else:
            raise

    if not fn or not os.path.exists(fn):
        raise RuntimeError(f"Downloaded video file missing after click '{chosen_label}'")

    shutil.move(fn, out_file)
    try:
        info = ffprobe_info(out_file)
    except Exception:
        rej_dir = os.path.join(project_dir, "clips", "_rejected")
        os.makedirs(rej_dir, exist_ok=True)
        shutil.move(out_file, os.path.join(rej_dir, os.path.basename(out_file)))
        ensure_grid_view(tab_id)
        raise

    ensure_grid_view(tab_id)
    return {
        "file": rel_out,
        "abs_file": out_file,
        "src_key": src_key,
        "title": title,
        "media": "video",
        "menu_options": menu_names,
        "download_label": chosen_label,
        "upscaled_1080p": upscale_used,
        **info,
    }


def download_top_lightbox(
    tab_id: int,
    project_dir: str,
    rel_out: str,
    *,
    media: str = "image",
    upscale_1080p: bool = False,
    idx: int = 0,
) -> Dict[str, Any]:
    ensure_grid_view(tab_id)
    scroll_grid_top(tab_id)
    time.sleep(0.3)
    st = get_media_state(tab_id)
    items = st.get("items") or []
    box = items[idx] if 0 <= idx < len(items) else st.get("firstBox")
    if not box:
        raise RuntimeError(f"No media tile found in grid at idx={idx} (count={len(items)})!")

    src_key = box.get("src_key") or st.get("firstKey")
    grid_title = box.get("title", "")
    _open_tile_to_lightbox(tab_id, box, src_key, f"top tile idx={idx}")

    time.sleep(0.6)
    if media == "video":
        return _download_open_video_lightbox(
            tab_id,
            project_dir,
            rel_out,
            upscale_1080p=upscale_1080p,
            src_key=src_key,
            grid_title=grid_title,
        )

    dom = read_dom(tab_id)
    title = grid_title
    for el in dom.get("elements", []):
        if el.get("role") == "textbox" and el.get("name") == "수정 가능한 텍스트":
            title = el.get("value", "") or title
            break

    dom2, menu_items = _open_lightbox_download_menu(tab_id, media="image")
    out_file = os.path.join(project_dir, rel_out)
    os.makedirs(os.path.dirname(out_file), exist_ok=True)

    target_ref = None
    for kw in ("1K", "2K", "원본", "다운로드"):
        hit = next((el["ref"] for el in menu_items if kw in el.get("name", "")), None)
        if hit:
            target_ref = hit
            break
    if not target_ref and menu_items:
        target_ref = menu_items[0]["ref"]
    if not target_ref:
        raise RuntimeError(f"No image download menuitem found; menuitems={menu_items}")
    dl_res = ugot(
        "click_and_download",
        {"backend": DEFAULT_BACKEND, "tabId": tab_id, "ref": target_ref, "timeoutMs": DOWNLOAD_TIMEOUT_MS},
    )
    fn = dl_res.get("filename")
    if not fn or not os.path.exists(fn):
        raise RuntimeError(f"Downloaded file missing: {dl_res}")
    sz, dims = convert_or_move_image(fn, out_file)
    ensure_grid_view(tab_id)
    return {
        "file": rel_out,
        "abs_file": out_file,
        "bytes": sz,
        "width": dims[0],
        "height": dims[1],
        "src_key": src_key,
        "title": title,
        "media": "image",
    }


# ---------------------------------------------------------------------------
# Attachments & Library Picker Selection
# ---------------------------------------------------------------------------

def _norm_title(s: str) -> str:
    s = re.sub(r"\s+(이미지|동영상)$", "", (s or "").strip())
    return s.rstrip("…").strip().lower()


def clear_attachments(tab_id: int) -> bool:
    """Clear attached chips/frames and any stale prompt text via Flow's clear button."""
    close_overlays(tab_id)
    dom = read_dom(tab_id)
    cleared = False
    clr_ref = find_ref(dom, role="button", name="프롬프트 지우기")
    if clr_ref:
        try:
            click_ref(tab_id, clr_ref)
        except RuntimeError:
            evaluate_js(
                tab_id,
                """(() => {
                  const b = document.querySelector('[aria-label="프롬프트 지우기"]')
                    || Array.from(document.querySelectorAll('button')).find(e => (e.innerText || e.getAttribute('aria-label') || '').includes('프롬프트 지우기'));
                  if (b) b.click();
                })()""",
            )
        time.sleep(0.35)
        cleared = True
    # Also remove any lingering individual chip remove buttons if present
    for _ in range(6):
        dom2 = read_dom(tab_id)
        rem = None
        rem_name = ""
        for el in dom2.get("elements", []):
            if el.get("role") == "button":
                nm = el.get("name", "")
                if any(k in nm for k in ("소재 제거", "이미지 제거", "프레임 제거", "첨부 삭제", "Remove")):
                    rem = el["ref"]
                    rem_name = nm
                    break
        if not rem:
            break
        try:
            click_ref(tab_id, rem)
        except RuntimeError:
            evaluate_js(
                tab_id,
                f"""(() => {{
                  const kw = {json.dumps(rem_name, ensure_ascii=False)};
                  const b = Array.from(document.querySelectorAll('button')).find(e => (e.getAttribute('aria-label') || e.innerText || '').includes(kw));
                  if (b) b.click();
                }})()""",
            )
        time.sleep(0.25)
        cleared = True
    return cleared


def _resolve_target_title(
    target_id: str,
    ledger: Dict[str, Any],
    grid_items: List[Dict[str, Any]],
) -> Tuple[Optional[str], Optional[int]]:
    meta = ledger.get(target_id, {})
    src_key = meta.get("src_key")
    saved_title = meta.get("title", "")
    if src_key:
        for idx, it in enumerate(grid_items):
            if it.get("src_key") == src_key:
                return it.get("title") or saved_title, idx
    return saved_title or None, None


def _pick_from_open_modal_or_upload(
    tab_id: int,
    trigger_ref: str,
    target_id: str,
    ledger: Dict[str, Any],
    grid_items: List[Dict[str, Any]],
    project_dir: str,
) -> None:
    try:
        click_ref(tab_id, trigger_ref)
        time.sleep(0.45)
        dp = read_dom(tab_id)
        opts = [el for el in dp.get("elements", []) if el.get("role") == "option"]
    except RuntimeError:
        dp = {"elements": []}
        opts = []
    if not opts and find_ref(dp, role="textbox", name="애셋 검색") is None and find_ref(dp, role="button", name_contains="미디어 업로드") is None:
        close_overlays(tab_id)
        evaluate_js(
            tab_id,
            """(() => {
              const b = document.querySelector('[aria-label="프롬프트 상자에 소재 추가"]')
                || Array.from(document.querySelectorAll('button')).find(e => {
                  const a = e.getAttribute('aria-label') || '';
                  const t = (e.innerText || '').trim();
                  return a === '프롬프트 상자에 소재 추가' || t === '시작' || t === '종료' || t.endsWith('소재');
                });
              if (b) {
                b.dispatchEvent(new PointerEvent('pointerdown', {bubbles: true}));
                b.click();
              }
            })()""",
        )
        time.sleep(0.55)
        dp = read_dom(tab_id)
        opts = [el for el in dp.get("elements", []) if el.get("role") == "option"]

    target_title, grid_idx = _resolve_target_title(target_id, ledger, grid_items)
    norm_t = _norm_title(target_title or "")

    def _match_opt(options: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not options:
            return None
        if norm_t:
            for o in options:
                no = _norm_title(o.get("name", ""))
                if no and no == norm_t:
                    return o
            t_trunc = (target_title or "").strip().endswith("…")
            for o in options:
                raw_o = re.sub(r"\s+(이미지|동영상)$", "", (o.get("name") or "").strip())
                o_trunc = raw_o.endswith("…")
                no = _norm_title(raw_o)
                if not no:
                    continue
                if (t_trunc or o_trunc) and (norm_t.startswith(no) or no.startswith(norm_t)):
                    return o
                if len(norm_t) >= 10 and len(no) >= 10 and (norm_t.startswith(no[:14]) or no.startswith(norm_t[:14])):
                    return o
        return None

    chosen_opt = _match_opt(opts)

    if chosen_opt is None and opts and norm_t:
        # Retry once after modal list finishes hydrating or filter by 애셋 검색
        time.sleep(0.5)
        dp_r = read_dom(tab_id)
        opts_r = [el for el in dp_r.get("elements", []) if el.get("role") == "option"]
        chosen_opt = _match_opt(opts_r)
        if chosen_opt is None:
            search_ref = find_ref(dp_r, role="textbox", name="애셋 검색")
            if search_ref:
                ugot(
                    "type",
                    {"backend": DEFAULT_BACKEND, "tabId": tab_id, "ref": search_ref, "text": norm_t[:18], "clear": True},
                )
                time.sleep(0.6)
                dp = read_dom(tab_id)
                opts = [el for el in dp.get("elements", []) if el.get("role") == "option"]
                chosen_opt = _match_opt(opts)

    if chosen_opt is None and opts and grid_idx is not None and 0 <= grid_idx < len(opts) and len(opts) == len(grid_items):
        chosen_opt = opts[grid_idx]

    if chosen_opt is not None:
        print(f"  [attach] {target_id} -> '{chosen_opt.get('name')}'", flush=True)
        pre_imgs = int(evaluate_js(tab_id, 'document.querySelectorAll(".base-prompt-box img").length') or 0)
        try:
            click_ref(tab_id, chosen_opt["ref"])
        except RuntimeError:
            pass
        time.sleep(0.45)
        post_imgs = int(evaluate_js(tab_id, 'document.querySelectorAll(".base-prompt-box img").length') or 0)
        dp_after = read_dom(tab_id)
        if post_imgs <= pre_imgs and any(el.get("role") == "option" for el in dp_after.get("elements", [])):
            match_kw = re.sub(r"\s+(이미지|동영상)$", "", (chosen_opt.get("name") or "")).rstrip("…").strip()[:22]
            kw_js = json.dumps(match_kw, ensure_ascii=False)
            evaluate_js(
                tab_id,
                f"""(() => {{
                  const kw = {kw_js}.toLowerCase();
                  const hit = Array.from(document.querySelectorAll('[role="option"]')).find(e =>
                    ((e.innerText || e.getAttribute('aria-label') || '').replace(/\\s+/g, ' ').trim().toLowerCase()).includes(kw)
                  );
                  if (hit) {{
                    hit.dispatchEvent(new PointerEvent('pointerdown', {{bubbles: true}}));
                    hit.click();
                  }}
                }})()""",
            )
            time.sleep(0.45)
            dp_after = read_dom(tab_id)
        if any(el.get("role") == "option" for el in dp_after.get("elements", [])):
            add_btn = find_ref(dp_after, role="button", name="프롬프트에 추가")
            if add_btn:
                try:
                    click_ref(tab_id, add_btn)
                except RuntimeError:
                    evaluate_js(
                        tab_id,
                        """(() => {
                          const b = Array.from(document.querySelectorAll('button')).find(e =>
                            (e.innerText || e.getAttribute('aria-label') || '').includes('프롬프트에 추가')
                          );
                          if (b) {
                            b.dispatchEvent(new PointerEvent('pointerdown', {bubbles: true}));
                            b.click();
                          }
                        })()""",
                    )
                time.sleep(0.45)
            close_overlays(tab_id)
        post_imgs = int(evaluate_js(tab_id, 'document.querySelectorAll(".base-prompt-box img").length') or 0)
        dom_post = read_dom(tab_id)
        chips = [el.get("name", "") for el in dom_post.get("elements", []) if el.get("role") == "button" and el.get("name") in ("소재", "이미지 소재", "배경", "인물", "프롬프트 지우기")]
        print(f"  [attach-post] {target_id} imgs={pre_imgs}->{post_imgs} composer markers={chips}", flush=True)
        if post_imgs <= pre_imgs:
            raise RuntimeError(f"Failed to attach {target_id} into composer (imgs stayed {post_imgs})")
        return

    # Local upload fallback (handles fresh empty Flow project & un-uploaded extracted frames)
    meta = ledger.get(target_id, {})
    rel_file = meta.get("file")
    if rel_file:
        abs_file = rel_file if os.path.isabs(rel_file) else os.path.join(project_dir, rel_file)
        if os.path.exists(abs_file):
            abs_file = os.path.abspath(abs_file)
            prev_keys = {it.get("src_key") for it in grid_items if it.get("src_key")}
            prev_opts_count = len(opts)
            dp2 = read_dom(tab_id)
            file_input = find_ref(dp2, role="file")
            if file_input:
                ugot("upload_files", {"backend": DEFAULT_BACKEND, "tabId": tab_id, "ref": file_input, "mode": "input", "paths": [abs_file]})
            else:
                file_input_count = evaluate_js(
                    tab_id,
                    'document.querySelectorAll(\'input[type="file"]\').length',
                )
                if file_input_count != 1:
                    close_overlays(tab_id)
                    raise RuntimeError(
                        f"Expected unique <input type=\"file\"> mounted in DOM for local upload of {target_id}, found {file_input_count!r}"
                    )
                try:
                    ugot(
                        "upload_files",
                        {
                            "backend": DEFAULT_BACKEND,
                            "tabId": tab_id,
                            "mode": "input",
                            "selector": 'input[type="file"]',
                            "includeHidden": True,
                            "paths": [abs_file],
                        },
                    )
                except RuntimeError as exc:
                    msg = str(exc)
                    if "includeHidden" in msg or "unrecognized_keys" in msg.lower() or "invalid_target" in msg.lower():
                        raise RuntimeError(
                            f"Hidden <input type=\"file\"> upload requires ugot-browser-bridge >= 0.2.26 "
                            f"and ugot-browser-agent-extension >= 0.1.18 ({msg})"
                        ) from exc
                    raise

            print(f"  [attach-upload] uploaded {target_id} from {abs_file}, waiting for Flow picker...", flush=True)
            uploaded_attached = False
            for _ in range(18):
                time.sleep(1.0)
                dp_u = read_dom(tab_id)
                new_opts = [el for el in dp_u.get("elements", []) if el.get("role") == "option"]
                if new_opts and len(new_opts) > prev_opts_count:
                    newest = new_opts[0]
                    print(f"  [attach-uploaded-opt] {target_id} -> '{newest.get('name')}'", flush=True)
                    click_ref(tab_id, newest["ref"])
                    time.sleep(0.45)
                    dp_a = read_dom(tab_id)
                    add_btn = find_ref(dp_a, role="button", name="프롬프트에 추가")
                    if add_btn:
                        click_ref(tab_id, add_btn)
                        time.sleep(0.4)
                    close_overlays(tab_id)
                    uploaded_attached = True
                    break
                # If modal auto-closed and composer attached uploaded file
                has_picker = find_ref(dp_u, role="button", name_contains="미디어 업로드") is not None
                if not has_picker:
                    chips = [el.get("name", "") for el in dp_u.get("elements", []) if el.get("role") == "button" and el.get("name") in ("소재", "이미지 소재", "배경", "인물", "프롬프트 지우기")]
                    if "프롬프트 지우기" in chips or any(c != "프롬프트 지우기" for c in chips):
                        uploaded_attached = True
                        break
            if uploaded_attached:
                st_new = get_media_state(tab_id)
                for it in st_new.get("items", []):
                    if it.get("src_key") and it["src_key"] not in prev_keys:
                        ledger[target_id] = {**(ledger.get(target_id) or {}), "src_key": it["src_key"], "title": it.get("title") or target_id}
                        save_ledger(project_dir, ledger)
                        break
                return
            raise RuntimeError(f"Uploaded {abs_file} for {target_id}, but Flow picker did not confirm attachment within timeout.")

    close_overlays(tab_id)
    raise RuntimeError(
        f"Could not match or upload {target_id} in Flow picker (title={target_title!r}, opts={[o.get('name') for o in opts[:8]]}, rel_file={rel_file!r})"
    )


def attach_assets(
    tab_id: int,
    project_dir: str,
    asset_ids: List[str],
    ledger: Dict[str, Any],
) -> None:
    if not asset_ids:
        return
    scroll_grid_top(tab_id)
    grid_items = get_media_state(tab_id).get("items", [])
    for aid in asset_ids:
        close_overlays(tab_id)
        dom = read_dom(tab_id)
        plus_ref = require_ref(dom, role="button", name="프롬프트 상자에 소재 추가", label="프롬프트 상자에 소재 추가")
        _pick_from_open_modal_or_upload(tab_id, plus_ref, aid, ledger, grid_items, project_dir)


def attach_frames(
    tab_id: int,
    project_dir: str,
    first_id: Optional[str],
    last_id: Optional[str],
    ledger: Dict[str, Any],
) -> None:
    scroll_grid_top(tab_id)
    grid_items = get_media_state(tab_id).get("items", [])
    if first_id:
        close_overlays(tab_id)
        dom = read_dom(tab_id)
        start_ref = find_ref(dom, role="button", name="시작")
        if not start_ref:
            raise RuntimeError("Could not find '시작' frame slot button (check if mode is '프레임').")
        _pick_from_open_modal_or_upload(tab_id, start_ref, first_id, ledger, grid_items, project_dir)
    if last_id:
        close_overlays(tab_id)
        dom = read_dom(tab_id)
        end_ref = find_ref(dom, role="button", name="종료")
        if not end_ref:
            raise RuntimeError("Could not find '종료' frame slot button.")
        _pick_from_open_modal_or_upload(tab_id, end_ref, last_id, ledger, grid_items, project_dir)


# ---------------------------------------------------------------------------
# Image settings & generation (`Nano Banana 2 Lite`, strictly 0 credits)
# ---------------------------------------------------------------------------

def clean_prompt_text(prompt: str, ar: str, strip_face_anchors: bool) -> str:
    is_char_sheet = (
        "Character turnaround model sheet" in prompt
        or "expression insets" in prompt
        or "front view, 3/4 view, side profile" in prompt
    )
    if strip_face_anchors and not is_char_sheet:
        for snippet in (
            ", normal human eyes, NO shadows on faces so expressions remain evenly bright and clear on mobile screens",
            "while characters' faces stay evenly lit, bright, and completely free of shadows (NO shadows on faces) for clean mobile readability; ",
        ):
            prompt = prompt.replace(snippet, "")
    if ar == "1:1":
        prompt = prompt.replace("9:16 vertical frame, ", "1:1 square frame, ").replace("16:9 widescreen frame, ", "1:1 square frame, ")
    elif ar == "16:9":
        prompt = prompt.replace("9:16 vertical frame, ", "16:9 widescreen frame, ")
    elif ar == "9:16":
        prompt = prompt.replace("16:9 widescreen frame, ", "9:16 vertical frame, ")
    return prompt


def ensure_image_settings(tab_id: int, ar: str) -> None:
    open_settings_popover(tab_id)

    _select_settings_radio(tab_id, "이미지", label="이미지 radio")
    _select_settings_radio(tab_id, "x1", exact=True, label="x1 radio")
    _select_settings_radio(tab_id, ar, label=f"aspect_ratio {ar}")
    time.sleep(0.25)

    dom = read_dom(tab_id)
    txt = read_text(tab_id)
    if "Nano Banana 2 Lite" not in txt:
        mbtn = find_ref(dom, role="button", name="모델 제품군 선택")
        if mbtn:
            click_ref(tab_id, mbtn)
            time.sleep(0.35)
            dom_m = read_dom(tab_id)
            opt_nb = find_ref(dom_m, role="menuitem", name_contains="Nano Banana 2 Lite") or find_ref(dom_m, role="option", name_contains="Nano Banana 2 Lite")
            if opt_nb:
                click_ref(tab_id, opt_nb)
                time.sleep(0.35)
                dom = read_dom(tab_id)
                txt = read_text(tab_id)

    credits_found = [el.get("name", "") for el in dom.get("elements", []) if "크레딧" in el.get("name", "")]
    if not any(c.strip() == "0 크레딧" for c in credits_found) and "0 크레딧" not in txt:
        close_overlays(tab_id)
        raise RuntimeError(f"Expected strictly '0 크레딧' for reference generation, saw: {credits_found}")

    if "Nano Banana 2 Lite" not in txt:
        close_overlays(tab_id)
        raise RuntimeError("Selected image model is not Nano Banana 2 Lite!")

    close_overlays(tab_id)


def generate_ref(
    tab_id: int,
    project_dir: str,
    ref_obj: Dict[str, Any],
    *,
    prompt_override: Optional[str] = None,
    ar_override: Optional[str] = None,
    attach_ids: Optional[List[str]] = None,
    strip_face_anchors: bool = False,
    write_log: bool = False,
) -> Dict[str, Any]:
    rid = ref_obj["id"]
    ar = ar_override or ref_obj["settings"]["aspect_ratio"]
    raw_prompt = prompt_override if prompt_override is not None else ref_obj["prompt"]
    prompt = clean_prompt_text(raw_prompt, ar, strip_face_anchors)

    ensure_grid_view(tab_id)
    scroll_grid_top(tab_id)
    prev_state = get_media_state(tab_id)
    prev_keys = {it["src_key"] for it in prev_state.get("items", []) if it.get("src_key")}
    if prev_state.get("firstKey"):
        prev_keys.add(prev_state["firstKey"])

    ledger = load_ledger(project_dir)
    clear_attachments(tab_id)
    ensure_image_settings(tab_id, ar)

    eff_attach = attach_ids if attach_ids is not None else (ref_obj.get("attach_ids") or None)
    if eff_attach:
        attach_assets(tab_id, project_dir, eff_attach, ledger)
    attach_ids = eff_attach

    prompt = re.sub(r"\s*\n+\s*", " ", prompt).strip()
    dom = read_dom(tab_id)
    tb = require_ref(dom, role="textbox", name="무엇을 만들고 싶으신가요?", label="prompt textbox")
    ugot("type", {"backend": DEFAULT_BACKEND, "tabId": tab_id, "ref": tb, "text": prompt, "clear": False})
    time.sleep(0.35)

    txt = read_text(tab_id)
    tail = prompt[-30:] if len(prompt) >= 30 else prompt
    if tail not in txt:
        raise RuntimeError(f"{rid} prompt truncation check failed! Tail not visible: {tail!r}")

    pre_txt_low = read_text(tab_id).lower()
    pre_policy_hits = sum(pre_txt_low.count(term) for term in POLICY_REFUSAL_TERMS)
    dom = read_dom(tab_id)
    gen_btn = require_ref(dom, name="생성 시작", label="생성 시작")
    try:
        click_ref(tab_id, gen_btn)
    except RuntimeError:
        pass
    time.sleep(0.7)
    rem_len = int(
        evaluate_js(
            tab_id,
            '(document.querySelector(".base-prompt-box [contenteditable], .base-prompt-box textarea")?.innerText || "").trim().length',
        )
        or 0
    )
    if rem_len > 20:
        evaluate_js(
            tab_id,
            """(() => {
              const b = document.querySelector('[aria-label="생성 시작"]');
              if (b && !b.disabled) {
                b.dispatchEvent(new PointerEvent('pointerdown', {bubbles: true}));
                b.click();
              }
            })()""",
        )
    print(f"[{rid}] submitted (Nano Banana 2 Lite, ar={ar}, attach={attach_ids or []}, 0cr)", flush=True)

    time.sleep(3.0)
    for _ in range(45):
        txt = read_text(tab_id)
        low = txt.lower()
        cur_policy_hits = sum(low.count(term) for term in POLICY_REFUSAL_TERMS)
        if cur_policy_hits > pre_policy_hits:
            hit_terms = [term for term in POLICY_REFUSAL_TERMS if low.count(term) > pre_txt_low.count(term)]
            raise RuntimeError(f"Policy refusal / error for {rid}: hit {hit_terms}")
        scroll_grid_top(tab_id)
        st = get_media_state(tab_id)
        cur_key = st.get("firstKey")
        still_running = bool(
            re.search(r"\b\d+%", txt)
            or re.search(r"생성\s*중|대기\s*중|Generating|Queued", txt)
        )
        if cur_key and cur_key not in prev_keys and not still_running:
            time.sleep(0.6)
            break
        time.sleep(2.5)
    else:
        raise TimeoutError(f"Timeout waiting for {rid}")

    res = download_top_lightbox(tab_id, project_dir, ref_obj["file"], media="image")
    ledger[rid] = {
        "file": res["file"],
        "src_key": res["src_key"],
        "ar": ar,
        "media_type": "image",
        "width": res["width"],
        "height": res["height"],
        "bytes": res["bytes"],
        "title": res["title"],
    }
    save_ledger(project_dir, ledger)

    if write_log:
        notes = f"1K→PNG {res['width']}x{res['height']} ({res['bytes']:,}B)"
        if attach_ids:
            notes += f"; refs={','.join(attach_ids)}"
        append_generation_log(
            project_dir,
            unit_id=rid,
            take="t1",
            platform_cfg=f"Google Flow · Nano Banana 2 Lite · {ar} · x1",
            credits_str="0",
            result_file=res["file"],
            status="성공",
            notes=notes,
        )

    print(f"[{rid}] SAVED {res['file']} ({res['width']}x{res['height']}, {res['bytes']} B, title={res['title']!r})", flush=True)
    return res


# ---------------------------------------------------------------------------
# Video settings & generation (`Omni 1.2 Flash`, strict credit guard)
# ---------------------------------------------------------------------------

def _parse_credits_from_dom(dom: Dict[str, Any]) -> Optional[int]:
    for el in dom.get("elements", []):
        nm = el.get("name", "")
        m = re.search(r"(\d+)\s*크레딧", nm)
        if m:
            return int(m.group(1))
    return None


def _select_settings_radio(tab_id: int, kw: str, *, exact: bool = False, label: str = "radio") -> None:
    """Click a Radix [role=radio] inside Flow settings popover and verify aria-checked=true."""
    kw_js = json.dumps(kw, ensure_ascii=False)
    match_expr = f"txt === {kw_js}" if exact else f"txt.includes({kw_js})"
    res = evaluate_js(
        tab_id,
        f"""(() => {{
          const list = Array.from(document.querySelectorAll('[role="radio"]'));
          const el = list.find(e => {{
            const txt = (e.innerText || '').trim();
            return {match_expr};
          }});
          if (!el) return 'NOT_FOUND';
          if (el.getAttribute('aria-checked') !== 'true') {{
            el.click();
          }}
          return el.getAttribute('aria-checked') || 'clicked';
        }})()""",
    )
    if res == "NOT_FOUND":
        raise RuntimeError(f"Could not find {label} (kw={kw!r}, exact={exact})")
    time.sleep(0.22)
    chk = evaluate_js(
        tab_id,
        f"""(() => {{
          const list = Array.from(document.querySelectorAll('[role="radio"]'));
          const el = list.find(e => {{
            const txt = (e.innerText || '').trim();
            return {match_expr};
          }});
          return el ? el.getAttribute('aria-checked') : 'MISSING';
        }})()""",
    )
    if chk != "true":
        # One more explicit JS click + wait in case panel transitioned
        evaluate_js(
            tab_id,
            f"""(() => {{
              const list = Array.from(document.querySelectorAll('[role="radio"]'));
              const el = list.find(e => {{
                const txt = (e.innerText || '').trim();
                return {match_expr};
              }});
              if (el) el.click();
            }})()""",
        )
        time.sleep(0.3)


def ensure_video_settings_and_read_cost(
    tab_id: int,
    *,
    mode: str,
    ar: str,
    res: str,
    duration: int,
    model_name: str = "Omni 1.2 Flash",
) -> Tuple[int, str]:
    if not (3 <= duration <= 15):
        raise RuntimeError(f"Invalid Flow video duration {duration}s (must be 3..15)")

    open_settings_popover(tab_id)
    _select_settings_radio(tab_id, "동영상", label="동영상 radio")
    time.sleep(0.15)

    # Verify / select model family first so model swap cannot reset resolution/duration
    cur_model = evaluate_js(tab_id, '(() => { const b = document.querySelector("[aria-label=\\"모델 제품군 선택\\"]"); return b ? b.innerText.trim() : ""; })()') or ""
    if model_name not in cur_model:
        dom = read_dom(tab_id)
        mbtn = require_ref(dom, role="button", name="모델 제품군 선택", label="모델 선택")
        click_ref(tab_id, mbtn)
        time.sleep(0.35)
        dom_m = read_dom(tab_id)
        opt_m = find_ref(dom_m, role="menuitem", name_contains=model_name) or find_ref(dom_m, role="option", name_contains=model_name)
        if not opt_m:
            close_overlays(tab_id)
            raise RuntimeError(f"Target video model '{model_name}' not found in menu (current={cur_model!r})")
        click_ref(tab_id, opt_m)
        time.sleep(0.3)

    mode_kw = "소재" if mode == "ingredients" else "프레임"
    _select_settings_radio(tab_id, mode_kw, label=f"mode {mode_kw}")
    _select_settings_radio(tab_id, ar, label=f"aspect_ratio {ar}")
    _select_settings_radio(tab_id, res, label=f"resolution {res}")
    _select_settings_radio(tab_id, "x1", exact=True, label="x1 radio")

    # Set duration slider: slider_value = duration - 3 (min=0 -> 3s, max=12 -> 15s)
    slider_val = duration - 3
    evaluate_js(
        tab_id,
        f"""(() => {{
          const s = document.querySelector('input[aria-label="길이"]');
          if (!s) throw new Error("Duration slider input[aria-label='길이'] not found");
          const proto = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set;
          proto.call(s, "{slider_val}");
          s.dispatchEvent(new Event("input", {{bubbles: true}}));
          s.dispatchEvent(new Event("change", {{bubbles: true}}));
          return s.value;
        }})()""",
    )
    time.sleep(0.35)

    dom_chk = read_dom(tab_id)
    summary = evaluate_js(tab_id, '(() => { const b = document.querySelector("[aria-label=\\"설정 트리거\\"]"); return b ? b.innerText.replace(/\\n+/g, " ").trim() : ""; })()') or ""
    if res not in summary or f"{duration}초" not in summary or "x1" not in summary:
        close_overlays(tab_id)
        raise RuntimeError(f"Settings verification failed! Expected {res}/{duration}초/x1, got summary={summary!r}")

    displayed_cost = _parse_credits_from_dom(dom_chk)
    close_overlays(tab_id)
    if displayed_cost is None:
        raise RuntimeError(f"Could not parse displayed credit cost from DOM in video settings! summary={summary!r}")
    return displayed_cost, summary


def _parse_job_video_params(
    args: argparse.Namespace,
    unit: Dict[str, Any],
) -> Dict[str, Any]:
    settings = unit.get("settings") or {}
    mode_arg = getattr(args, "mode", None)
    if not mode_arg:
        raw_mode = str(unit.get("mode", "")).lower()
        mode_arg = "frames" if "frame" in raw_mode else "ingredients"

    raw_res = getattr(args, "res", None) or str(settings.get("resolution", "360p"))
    m_res = re.search(r"(360p|720p)", raw_res)
    res_arg = m_res.group(1) if m_res else "360p"

    duration_arg = getattr(args, "duration", None) or int(settings.get("duration_sec", 4))
    ar_arg = getattr(args, "ar", None) or str(settings.get("aspect_ratio", "9:16"))

    raw_model = getattr(args, "model", None) or str(unit.get("model", "Omni 1.2 Flash"))
    model_arg = "Omni 1.2 Flash" if "omni" in raw_model.lower() else raw_model

    est_arg = getattr(args, "est_credits", None)
    if est_arg is None:
        raw_est = unit.get("est_credits")
        if isinstance(raw_est, (int, float)):
            est_arg = int(raw_est)
        else:
            est_arg = duration_arg * (3 if res_arg == "720p" else 1)

    prompt_file = getattr(args, "prompt_file", None)
    if prompt_file:
        with open(prompt_file, "r", encoding="utf-8") as f:
            prompt = f.read().strip()
    else:
        prompt = str(unit.get("prompt", "")).strip()

    return {
        "mode": mode_arg,
        "res": res_arg,
        "duration": int(duration_arg),
        "ar": ar_arg,
        "model": model_arg,
        "est_credits": int(est_arg),
        "prompt": prompt,
        "rel_out": getattr(args, "out", None) or unit["outputs"][0],
    }


QUEUE_LIMIT_TERMS = ("동시", "concurrent", "too many", "limit reached", "잠시 후", "queue is full")


def _count_policy_cards(txt: str) -> int:
    low = (txt or "").lower()
    return sum(low.count(pat) for pat in ("정책을 위반", "violat", "unable to generate", "can't generate", "생성할 수 없"))


def extract_first_frame(
    project_dir: str,
    video_path: str,
    asset_id: str,
    *,
    rel_out: Optional[str] = None,
    time_sec: float = 0.0,
) -> Dict[str, Any]:
    """Extract clean target frame from an MP4 clip (e.g. real source bridge) and register in ledger."""
    abs_vid = video_path if os.path.isabs(video_path) else os.path.join(project_dir, video_path)
    info = ffprobe_info(abs_vid)
    ts = min(max(0.0, time_sec), max(0.0, info["duration"] - 0.05))
    rel_file = rel_out or f"refs/{asset_id}.png"
    abs_out = rel_file if os.path.isabs(rel_file) else os.path.join(project_dir, rel_file)
    os.makedirs(os.path.dirname(abs_out), exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-ss", f"{ts:.3f}", "-i", abs_vid, "-frames:v", "1", abs_out],
        check=True,
    )
    sz = os.path.getsize(abs_out)
    if sz <= 0:
        raise RuntimeError(f"Extracted empty frame at {abs_out}")
    with Image.open(abs_out) as im:
        w, h = im.size
    ar = "9:16" if h > w else ("16:9" if w > h else "1:1")
    ledger = load_ledger(project_dir)
    ledger[asset_id] = {
        "file": rel_file,
        "src_key": None,
        "ar": ar,
        "media_type": "image",
        "width": w,
        "height": h,
        "bytes": sz,
        "title": asset_id,
        "source_video": abs_vid,
        "timestamp_sec": round(ts, 3),
    }
    save_ledger(project_dir, ledger)
    return ledger[asset_id]


def extract_last_frame(
    project_dir: str,
    video_path: str,
    asset_id: str,
    *,
    rel_out: Optional[str] = None,
    offset: float = 0.15,
) -> Dict[str, Any]:
    """Extract clean final frame from an MP4 clip and register it in refs/.flow_assets.json."""
    abs_vid = video_path if os.path.isabs(video_path) else os.path.join(project_dir, video_path)
    info = ffprobe_info(abs_vid)
    ts = max(0.0, info["duration"] - max(0.02, offset))
    rel_file = rel_out or f"refs/{asset_id}.png"
    abs_out = rel_file if os.path.isabs(rel_file) else os.path.join(project_dir, rel_file)
    os.makedirs(os.path.dirname(abs_out), exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-ss", f"{ts:.3f}", "-i", abs_vid, "-frames:v", "1", abs_out],
        check=True,
    )
    sz = os.path.getsize(abs_out)
    if sz <= 0:
        raise RuntimeError(f"Extracted empty last frame at {abs_out}")
    with Image.open(abs_out) as im:
        w, h = im.size
    ar = "9:16" if h > w else ("16:9" if w > h else "1:1")
    ledger = load_ledger(project_dir)
    ledger[asset_id] = {
        "file": rel_file,
        "src_key": None,
        "ar": ar,
        "media_type": "image",
        "width": w,
        "height": h,
        "bytes": sz,
        "title": asset_id,
        "source_video": abs_vid,
        "timestamp_sec": round(ts, 3),
    }
    save_ledger(project_dir, ledger)
    return ledger[asset_id]


def _submit_video_unit_to_flow(
    tab_id: int,
    project_dir: str,
    unit: Dict[str, Any],
    cfg: Dict[str, Any],
    ledger: Dict[str, Any],
    max_credits: int,
    *,
    attach_ids_override: Optional[List[str]] = None,
    first_frame_override: Optional[str] = None,
    last_frame_override: Optional[str] = None,
    settings_cache: Optional[Dict[str, Any]] = None,
) -> Tuple[int, str]:
    uid = unit["id"]
    prompt = cfg["prompt"]
    if not prompt:
        raise RuntimeError(f"Empty prompt for unit {uid}")

    ensure_tab_active(tab_id)
    ensure_grid_view(tab_id)
    clear_attachments(tab_id)

    settings_sig = (cfg["mode"], cfg["ar"], cfg["res"], cfg["duration"], cfg["model"])
    verified_cost: Optional[int] = None
    summary = ""
    if settings_cache is not None and settings_cache.get("sig") == settings_sig:
        trig_sum = str(
            evaluate_js(
                tab_id,
                'document.querySelector("[aria-label=\\"설정 트리거\\"]")?.innerText.replace(/\\n+/g, " ").trim() || ""',
            )
            or ""
        )
        if cfg["res"] in trig_sum and f"{cfg['duration']}초" in trig_sum and "x1" in trig_sum:
            verified_cost = int(settings_cache["cost"])
            summary = trig_sum

    if verified_cost is None:
        verified_cost, summary = ensure_video_settings_and_read_cost(
            tab_id,
            mode=cfg["mode"],
            ar=cfg["ar"],
            res=cfg["res"],
            duration=cfg["duration"],
            model_name=cfg["model"],
        )
        if settings_cache is not None and verified_cost is not None:
            settings_cache["sig"] = settings_sig
            settings_cache["cost"] = int(verified_cost)

    if cfg["mode"] == "ingredients":
        attach_ids = attach_ids_override if attach_ids_override else list(unit.get("reference_ids", []))
        attach_assets(tab_id, project_dir, attach_ids, ledger)
    else:
        first_id = first_frame_override or unit.get("first_frame") or (unit.get("reference_ids") or [None])[0]
        if not first_id and unit.get("last_frame_from"):
            prev_uid = unit["last_frame_from"]
            lf_id = f"LF_{prev_uid}"
            if lf_id not in ledger:
                prev_clip = (ledger.get(prev_uid) or {}).get("file") or f"clips/{prev_uid}_t1.mp4"
                extract_last_frame(project_dir, prev_clip, lf_id)
                ledger = load_ledger(project_dir)
            first_id = lf_id
        last_id = (
            last_frame_override
            or unit.get("last_frame")
            or ((unit.get("reference_ids") or [None, None])[1] if len(unit.get("reference_ids", [])) > 1 else None)
        )
        if not first_id:
            raise RuntimeError("Frames mode requires at least first_frame (or last_frame_from)")
        attach_frames(tab_id, project_dir, first_id, last_id, ledger)

    live_sum = str(
        evaluate_js(
            tab_id,
            'document.querySelector("[aria-label=\\"설정 트리거\\"]")?.innerText.replace(/\\n+/g, " ").trim() || ""',
        )
        or ""
    )
    if cfg["res"] in live_sum and f"{cfg['duration']}초" in live_sum and "x1" in live_sum:
        displayed_cost = verified_cost
        summary = live_sum
    else:
        displayed_cost, summary = ensure_video_settings_and_read_cost(
            tab_id,
            mode=cfg["mode"],
            ar=cfg["ar"],
            res=cfg["res"],
            duration=cfg["duration"],
            model_name=cfg["model"],
        )
    if displayed_cost is None:
        raise RuntimeError("Aborted: unable to verify credit cost immediately prior to submit.")
    max_allowed_est = cfg["est_credits"] * 1.20
    if displayed_cost > max_allowed_est or displayed_cost > max_credits:
        raise RuntimeError(
            f"CREDIT GUARD ABORT for {uid}: displayed={displayed_cost} cr > limit "
            f"(est*1.2={max_allowed_est:.1f}, max_credits={max_credits})"
        )

    collapsed = re.sub(r"\s*\n+\s*", " ", prompt).strip()
    dom = read_dom(tab_id)
    tb = require_ref(dom, role="textbox", name="무엇을 만들고 싶으신가요?", label="prompt textbox")
    ugot("type", {"backend": DEFAULT_BACKEND, "tabId": tab_id, "ref": tb, "text": collapsed, "clear": False})
    time.sleep(0.3)

    post_type = evaluate_js(
        tab_id,
        """(() => {
          const hasOptions = !!document.querySelector('[role="option"]');
          const box = document.querySelector('.base-prompt-box [contenteditable], .base-prompt-box textarea, [role="textbox"][aria-label*="무엇을"]');
          const promptText = box ? (box.value !== undefined ? box.value : (box.innerText || "")) : "";
          return { hasOptions, promptText };
        })()""",
    ) or {}
    if isinstance(post_type, dict) and post_type.get("hasOptions"):
        press_key(tab_id, "Escape")
        time.sleep(0.25)

    txt = str((post_type.get("promptText") if isinstance(post_type, dict) else "") or "")
    if not txt:
        txt = read_text(tab_id)
    tail = collapsed[-30:] if len(collapsed) >= 30 else collapsed
    m_q = re.search(r'"([^"]+)"', collapsed)
    if tail not in txt:
        raise RuntimeError(f"{uid} prompt truncation check failed! Tail not visible: {tail!r}")
    if m_q and m_q.group(1)[:8] not in txt:
        raise RuntimeError(f"{uid} Korean dialogue guard failed before submit! Missing snippet: {m_q.group(1)[:8]!r}")

    dom = read_dom(tab_id)
    gen_btn = require_ref(dom, name="생성 시작", label="생성 시작")
    print(
        f"[{uid}] SUBMITTING {cfg['model']} ({cfg['mode']}, {summary}, cost={displayed_cost} cr / cap={max_credits} cr)",
        flush=True,
    )
    try:
        click_ref(tab_id, gen_btn)
    except RuntimeError:
        pass
    time.sleep(0.9)
    rem_len = int(
        evaluate_js(
            tab_id,
            '(document.querySelector(".base-prompt-box [contenteditable], .base-prompt-box textarea")?.innerText || "").trim().length',
        )
        or 0
    )
    if rem_len > 20:
        evaluate_js(
            tab_id,
            """(() => {
              const b = document.querySelector('[aria-label="생성 시작"]');
              if (b && !b.disabled) {
                b.dispatchEvent(new PointerEvent('pointerdown', {bubbles: true}));
                b.click();
              }
            })()""",
        )
        time.sleep(1.2)
        rem_len = int(
            evaluate_js(
                tab_id,
                '(document.querySelector(".base-prompt-box [contenteditable], .base-prompt-box textarea")?.innerText || "").trim().length',
            )
            or 0
        )
    if rem_len > 20:
        raise RuntimeError(f"{uid}: submit click did not dispatch Flow generation (composer textLen={rem_len})")
    return displayed_cost, summary


def _finalize_video_unit(
    project_dir: str,
    uid: str,
    cfg: Dict[str, Any],
    displayed_cost: int,
    dl_res: Dict[str, Any],
    ledger: Dict[str, Any],
    *,
    write_log: bool = False,
) -> Dict[str, Any]:
    strip_rel = f"clips/_qc/{uid}_strip.png"
    strip_abs = os.path.join(project_dir, strip_rel)
    _, _ = build_video_strip(dl_res["abs_file"], strip_abs, frames=5)

    ledger[uid] = {
        "file": dl_res["file"],
        "src_key": dl_res["src_key"],
        "ar": cfg["ar"],
        "media_type": "video",
        "width": dl_res["width"],
        "height": dl_res["height"],
        "duration": dl_res["duration"],
        "bytes": dl_res["bytes"],
        "credits": displayed_cost,
        "upscaled_1080p": dl_res.get("upscaled_1080p", False),
        "strip": strip_rel,
    }
    save_ledger(project_dir, ledger)
    _update_jobs_unit(project_dir, uid, displayed_cost, dl_res)

    if write_log:
        notes = (
            f"{dl_res['width']}x{dl_res['height']} {dl_res['duration']:.2f}s {dl_res['fps']}fps "
            f"audio={'yes' if dl_res['has_audio'] else 'no'} dl={dl_res.get('download_label')!r} "
            f"menu={dl_res.get('menu_options')}; strip={strip_rel}"
        )
        append_generation_log(
            project_dir,
            unit_id=uid,
            take="t1",
            platform_cfg=f"Google Flow · {cfg['model']} · {cfg['mode']} · {cfg['res']} · {cfg['duration']}s · {cfg['ar']} · x1",
            credits_str=str(displayed_cost),
            result_file=dl_res["file"],
            status="성공",
            notes=notes,
        )

    out_payload = {"id": uid, "credits_spent": displayed_cost, **dl_res, "strip": strip_rel}
    print(
        f"[{uid}] DONE -> {dl_res['file']} ({dl_res['width']}x{dl_res['height']}, {dl_res['duration']:.2f}s, "
        f"cost={displayed_cost} cr, strip={strip_rel})",
        flush=True,
    )
    return out_payload


def run_video_unit(
    tab_id: int,
    project_dir: str,
    unit: Dict[str, Any],
    *,
    mode: str,
    res: str,
    duration: int,
    ar: str,
    model_name: str,
    est_credits: int,
    max_credits: int,
    prompt: str,
    rel_out: str,
    attach_ids_override: Optional[List[str]] = None,
    first_frame_override: Optional[str] = None,
    last_frame_override: Optional[str] = None,
    upscale_1080p: bool = False,
    write_log: bool = False,
) -> Dict[str, Any]:
    uid = unit["id"]
    cfg = {
        "mode": mode,
        "res": res,
        "duration": duration,
        "ar": ar,
        "model": model_name,
        "est_credits": est_credits,
        "prompt": prompt,
        "rel_out": rel_out,
    }
    ensure_grid_view(tab_id)
    scroll_grid_top(tab_id)
    prev_state = get_media_state(tab_id)
    prev_key = prev_state.get("firstKey")
    prev_count = prev_state.get("count", 0)
    pre_policy = _count_policy_cards(read_text(tab_id))
    ledger = load_ledger(project_dir)

    displayed_cost, _ = _submit_video_unit_to_flow(
        tab_id,
        project_dir,
        unit,
        cfg,
        ledger,
        max_credits,
        attach_ids_override=attach_ids_override,
        first_frame_override=first_frame_override,
        last_frame_override=last_frame_override,
    )

    time.sleep(5.0)
    for _ in range(75):
        txt = read_text(tab_id)
        if _count_policy_cards(txt) > pre_policy:
            raise RuntimeError(f"Policy refusal / error for {uid} (new policy/refund card on grid)")
        scroll_grid_top(tab_id)
        st = get_media_state(tab_id)
        new_arrived = (
            st.get("count", 0) > prev_count
            or (st.get("firstKey") and st["firstKey"] != prev_key)
        )
        still_running = bool(
            re.search(r"\b\d+%", txt)
            or re.search(r"생성\s*중|대기\s*중|Generating|Queued", txt)
        )
        if new_arrived and not still_running:
            time.sleep(1.5)
            break
        time.sleep(4.0)
    else:
        raise TimeoutError(f"Timeout waiting for video {uid} completion (300s)")

    dl_res = download_top_lightbox(
        tab_id,
        project_dir,
        rel_out,
        media="video",
        upscale_1080p=upscale_1080p,
    )
    return _finalize_video_unit(project_dir, uid, cfg, displayed_cost, dl_res, ledger, write_log=write_log)


def _match_lightbox_unit(
    lb_txt: str,
    pending_map: Dict[str, Tuple[Dict[str, Any], Dict[str, Any], int]],
) -> str:
    norm_lb = re.sub(r"\s+", " ", lb_txt or "")
    scores: List[Tuple[int, str]] = []
    for uid, (_, cfg, _) in pending_map.items():
        raw_p = cfg["prompt"]
        norm_p = re.sub(r"\s+", " ", raw_p).strip()
        quotes = [q for q in re.findall(r'"([^"]+)"', norm_p) if q]
        matched_quotes = sum(1 for q in quotes if q in norm_lb)
        if quotes and matched_quotes == 0:
            scores.append((0, uid))
            continue
        sc = matched_quotes * 5
        m_sfx = re.search(r"SFX:\s*([^.\n]+)", raw_p)
        if m_sfx:
            sfx_snip = re.sub(r"\s+", " ", m_sfx.group(1)).strip()[:50]
            if sfx_snip and sfx_snip in norm_lb:
                sc += 4
        slices = [(280, 360), (360, 440), (440, 520)]
        if not quotes:
            slices.append((180, 260))
        for s_idx, e_idx in slices:
            sl = norm_p[s_idx:e_idx]
            if len(sl) >= 20 and sl in norm_lb:
                sc += 2
        scores.append((sc, uid))

    scores.sort(reverse=True)
    best_sc, best_uid = scores[0]
    winners = [uid for sc, uid in scores if sc == best_sc]
    if best_sc < 4 or len(winners) != 1:
        raise RuntimeError(
            f"Ambiguous Lightbox prompt match (best_score={best_sc}, winners={winners}): lb={norm_lb[:220]!r}"
        )
    return best_uid


def _scroll_tile_into_view(tab_id: int, src_key: str) -> None:
    key_js = json.dumps(src_key)
    js = f"""(() => {{
      const k = {key_js};
      const el = [...document.querySelectorAll("img, video")].find(
        n => (n.currentSrc || n.src || n.poster || "").includes(k)
      );
      if (!el) return false;
      let p = el.parentElement;
      while (p) {{
        const cs = getComputedStyle(p);
        if ((cs.overflowY === "auto" || cs.overflowY === "scroll") && p.scrollHeight > p.clientHeight + 20) {{
          const r = el.getBoundingClientRect();
          p.scrollTop += (r.top - 90);
          return true;
        }}
        p = p.parentElement;
      }}
      el.scrollIntoView({{block: "start"}});
      return true;
    }})()"""
    evaluate_js(tab_id, js)


def run_video_wave(
    tab_id: int,
    project_dir: str,
    wave_items: List[Tuple[Dict[str, Any], Dict[str, Any]]],
    *,
    max_credits: int,
    upscale_1080p: bool = False,
    write_log: bool = False,
) -> Tuple[List[Dict[str, Any]], int, List[str], bool]:
    ensure_tab_active(tab_id)
    ensure_grid_view(tab_id)
    close_overlays(tab_id)
    pre_snap = poll_wave_snapshot(tab_id, max_items=32)
    pre_keys = set(pre_snap["keys"])
    pre_policy = pre_snap["policy_count"]
    ledger = load_ledger(project_dir)

    submitted: Dict[str, Tuple[Dict[str, Any], Dict[str, Any], int]] = {}
    submit_failed: List[str] = []
    submit_policy_hits = 0
    reserved = 0
    queue_capped = False
    settings_cache: Dict[str, Any] = {}

    for unit, cfg in wave_items:
        uid = unit["id"]
        rem = max_credits - reserved
        if rem <= 0 or cfg["est_credits"] > rem:
            break
        cost, _ = _submit_video_unit_to_flow(
            tab_id,
            project_dir,
            unit,
            cfg,
            ledger,
            rem,
            settings_cache=settings_cache,
        )
        time.sleep(1.6)
        post_snap = poll_wave_snapshot(tab_id, max_items=12)
        low = post_snap["text"].lower()
        cur_policy = post_snap["policy_count"]
        if cur_policy > pre_policy + submit_policy_hits:
            submit_policy_hits = cur_policy - pre_policy
            print(f"[wave] WARNING: immediate Flow policy/refund card on {uid}; stopping wave submit cleanly", flush=True)
            submit_failed.append(uid)
            clear_attachments(tab_id)
            break
        if len(submitted) >= 1 and any(term in low for term in QUEUE_LIMIT_TERMS):
            print(f"[wave] concurrency cap hit at {uid}, waiting for {len(submitted)} active jobs first", flush=True)
            queue_capped = True
            clear_attachments(tab_id)
            break
        submitted[uid] = (unit, cfg, cost)
        reserved += cost
        print(
            f"[wave] QUEUED {uid} ({len(submitted)}/{len(wave_items)}, cost={cost} cr, wave_reserved={reserved} cr)",
            flush=True,
        )

    if not submitted:
        return [], 0, submit_failed, queue_capped

    new_keys: List[str] = []
    idle_polls = 0
    max_idle = 6 if any(c["duration"] >= 8 for _, c, _ in submitted.values()) else 3
    warned_policy = False
    for poll_idx in range(110):
        ensure_tab_active(tab_id)
        snap = poll_wave_snapshot(tab_id, max_items=max(16, len(submitted) * 4))
        new_policy = max(0, snap["policy_count"] - pre_policy - submit_policy_hits)
        if new_policy > 0 and not warned_policy:
            warned_policy = True
            print(f"[wave] WARNING: {new_policy} unit(s) hit Flow policy/refund card during poll; waiting for active renders...", flush=True)
        seen_nk = set()
        new_keys = []
        for nk in snap["keys"]:
            if nk and nk not in pre_keys and nk not in seen_nk:
                seen_nk.add(nk)
                new_keys.append(nk)
        still_running = snap["still_running"]
        idle_polls = idle_polls + 1 if (poll_idx >= 2 and not still_running) else 0
        if (len(new_keys) + new_policy >= len(submitted) and not still_running) or (
            idle_polls >= max_idle and (len(new_keys) > 0 or new_policy > 0)
        ):
            if new_policy > 0:
                print(
                    f"[wave] WARNING: {new_policy} unit(s) hit Flow policy/refund card; "
                    f"downloading {len(new_keys)} succeeded clip(s)...",
                    flush=True,
                )
            time.sleep(1.2)
            break
        time.sleep(3.5)
    else:
        raise TimeoutError(f"Timeout waiting for wave completion (~385s); submitted={list(submitted.keys())}")

    unmatched = dict(submitted)
    results: List[Dict[str, Any]] = []
    actual_spent = 0

    for nk in new_keys:
        if not unmatched:
            break
        ensure_grid_view(tab_id)
        close_overlays(tab_id)
        scroll_grid_top(tab_id)
        time.sleep(0.35)
        st = get_media_state(tab_id)
        tile = next((it for it in st.get("items", []) if it.get("src_key") == nk), None)
        if not tile or tile["top"] < 60 or tile["y"] > 300:
            _scroll_tile_into_view(tab_id, nk)
            time.sleep(0.35)
            st = get_media_state(tab_id)
            tile = next((it for it in st.get("items", []) if it.get("src_key") == nk), None)
        if not tile:
            raise RuntimeError(f"Tile {nk[:24]} vanished from grid before download")

        _open_tile_to_lightbox(tab_id, tile, nk, f"wave tile {nk[:24]}")

        time.sleep(0.6)
        lb_txt = read_text(tab_id)
        uid = _match_lightbox_unit(lb_txt, unmatched)
        unit, cfg, cost = unmatched.pop(uid)

        dl_res = _download_open_video_lightbox(
            tab_id,
            project_dir,
            cfg["rel_out"],
            upscale_1080p=upscale_1080p,
            src_key=nk,
            grid_title=tile.get("title", ""),
        )
        payload = _finalize_video_unit(project_dir, uid, cfg, cost, dl_res, ledger, write_log=write_log)
        actual_spent += cost
        results.append(payload)
        print(
            f"[wave-done] {uid} -> {cfg['rel_out']} ({dl_res['width']}x{dl_res['height']}, "
            f"{dl_res['duration']:.2f}s, cost={cost} cr)",
            flush=True,
        )

    return results, actual_spent, submit_failed + list(unmatched.keys()), queue_capped


def _update_jobs_unit(project_dir: str, uid: str, credits_spent: int, dl_res: Dict[str, Any]) -> None:
    jobs_file = _resolve_jobs_path(project_dir)
    if not os.path.exists(jobs_file):
        return
    with open(jobs_file, "r", encoding="utf-8") as f:
        jobs_data = json.load(f)
    for bucket in ("units", "fallbacks"):
        for item in jobs_data.get(bucket, []):
            if item.get("id") == uid:
                item["status"] = "completed"
                item["actual_credits"] = int(credits_spent)
                item["actual_duration_sec"] = round(float(dl_res["duration"]), 3)
                item["actual_resolution"] = f"{dl_res['width']}x{dl_res['height']}"
                with open(jobs_file, "w", encoding="utf-8") as fw:
                    json.dump(jobs_data, fw, ensure_ascii=False, indent=2)
                return


def cmd_video(args: argparse.Namespace) -> None:
    jobs = load_jobs(args.project)
    unit_map = {u["id"]: u for u in jobs.get("units", []) + jobs.get("fallbacks", [])}
    if args.id not in unit_map:
        raise RuntimeError(f"Unknown unit ID {args.id} in 06_jobs.json")
    unit = unit_map[args.id]
    cfg = _parse_job_video_params(args, unit)
    attach_ov = [x.strip() for x in (args.attach or "").split(",") if x.strip()] or None
    out_payload = run_video_unit(
        args.tab,
        args.project,
        unit,
        mode=cfg["mode"],
        res=cfg["res"],
        duration=cfg["duration"],
        ar=cfg["ar"],
        model_name=cfg["model"],
        est_credits=cfg["est_credits"],
        max_credits=args.max_credits,
        prompt=cfg["prompt"],
        rel_out=cfg["rel_out"],
        attach_ids_override=attach_ov,
        first_frame_override=args.first_frame,
        last_frame_override=args.last_frame,
        upscale_1080p=args.upscale_1080p,
        write_log=args.log,
    )
    print(json.dumps(out_payload, ensure_ascii=False))


def cmd_video_batch(args: argparse.Namespace) -> None:
    jobs = load_jobs(args.project)
    unit_map = {u["id"]: u for u in jobs.get("units", []) + jobs.get("fallbacks", [])}
    req_ids = [x.strip() for x in args.ids.split(",") if x.strip()]

    pending: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
    for uid in req_ids:
        if uid not in unit_map:
            raise RuntimeError(f"Unknown unit ID {uid} in 06_jobs.json")
        unit = unit_map[uid]
        if unit.get("status") == "completed" and not args.force:
            print(f"[{uid}] SKIP already completed in 06_jobs.json", flush=True)
            continue
        cfg = _parse_job_video_params(argparse.Namespace(out=None), unit)
        out_abs = os.path.join(args.project, cfg["rel_out"])
        if not args.force and os.path.exists(out_abs) and os.path.getsize(out_abs) > 50_000:
            print(f"[{uid}] SKIP existing output file {cfg['rel_out']}", flush=True)
            continue
        pending.append((unit, cfg))

    spent = 0
    results: List[Dict[str, Any]] = []
    failed_ids: List[str] = []

    if args.concurrency <= 1:
        for unit, cfg in pending:
            uid = unit["id"]
            remaining_cap = args.max_credits - spent
            if remaining_cap <= 0 or cfg["est_credits"] > remaining_cap:
                print(
                    f"[video-batch] STOP before {uid}: est={cfg['est_credits']} cr > remaining_cap={remaining_cap} cr (spent={spent})",
                    flush=True,
                )
                break
            res = run_video_unit(
                args.tab,
                args.project,
                unit,
                mode=cfg["mode"],
                res=cfg["res"],
                duration=cfg["duration"],
                ar=cfg["ar"],
                model_name=cfg["model"],
                est_credits=cfg["est_credits"],
                max_credits=remaining_cap,
                prompt=cfg["prompt"],
                rel_out=cfg["rel_out"],
                upscale_1080p=args.upscale_1080p,
                write_log=args.log,
            )
            spent += int(res["credits_spent"])
            results.append(res)
    else:
        cur_conc = args.concurrency
        queue = list(pending)
        while queue:
            remaining_cap = args.max_credits - spent
            if remaining_cap <= 0 or queue[0][1]["est_credits"] > remaining_cap:
                print(
                    f"[video-batch] STOP before {queue[0][0]['id']}: est={queue[0][1]['est_credits']} cr > remaining_cap={remaining_cap} cr (spent={spent})",
                    flush=True,
                )
                break
            wave: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
            wave_est = 0
            for item in queue[:cur_conc]:
                if wave_est + item[1]["est_credits"] > remaining_cap:
                    break
                wave.append(item)
                wave_est += item[1]["est_credits"]
            if not wave:
                break
            w_res, w_spent, w_failed, q_capped = run_video_wave(
                args.tab,
                args.project,
                wave,
                max_credits=remaining_cap,
                upscale_1080p=args.upscale_1080p,
                write_log=args.log,
            )
            spent += int(w_spent)
            results.extend(w_res)
            failed_ids.extend(w_failed)
            handled = {r["id"] for r in w_res} | set(w_failed)
            if not handled:
                raise RuntimeError(f"Wave made zero progress on {[u['id'] for u, _ in wave]}")
            queue = [item for item in queue if item[0]["id"] not in handled]
            if q_capped and len(w_res) >= 1:
                cur_conc = min(cur_conc, len(w_res))

    print(
        json.dumps(
            {
                "completed": len(results),
                "failed": failed_ids,
                "total_credits_spent": spent,
                "remaining_cap": args.max_credits - spent,
            },
            ensure_ascii=False,
        )
    )


# ---------------------------------------------------------------------------
# Visual QC Contact Sheet & Video Strip Builders (1-image token optimization)
# ---------------------------------------------------------------------------

def _load_font(size: int) -> ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/SFNS.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()


def build_contact_sheet(
    project_dir: str,
    out_rel: str,
    *,
    ids: Optional[List[str]] = None,
    cols: int = 4,
    thumb_w: int = 360,
) -> Tuple[str, int, int, int]:
    jobs = load_jobs(project_dir)
    refs = _all_image_assets(jobs)
    ledger = load_ledger(project_dir)
    ref_by_id = {r["id"]: r for r in refs}
    for lid, lmeta in ledger.items():
        if lid not in ref_by_id and lmeta.get("media_type") == "image" and lmeta.get("file"):
            refs.append({"id": lid, "file": lmeta["file"]})

    if ids:
        id_set = {x: i for i, x in enumerate(ids)}
        selected = [r for r in refs if r["id"] in id_set]
        selected.sort(key=lambda r: id_set[r["id"]])
    else:
        selected = refs

    items: List[Tuple[str, str]] = []
    for r in selected:
        p = os.path.join(project_dir, r["file"])
        if os.path.exists(p) and os.path.getsize(p) > 0:
            items.append((r["id"], p))
    if not items:
        raise RuntimeError("No existing reference PNG files found to build contact sheet.")

    pad = 16
    hdr_h = 34
    cell_w = thumb_w
    with Image.open(items[0][1]) as im0:
        s_w, s_h = im0.size
    aspect = s_h / max(s_w, 1)
    cell_h = int(thumb_w * aspect + 12) if aspect < 0.9 else int(thumb_w * 1.15)

    rows = (len(items) + cols - 1) // cols
    sheet_w = pad + cols * (cell_w + pad)
    sheet_h = pad + rows * (cell_h + hdr_h + pad)
    canvas = Image.new("RGB", (sheet_w, sheet_h), (24, 27, 34))
    draw = ImageDraw.Draw(canvas)
    font = _load_font(18)

    for idx, (rid, path) in enumerate(items):
        r_idx = idx // cols
        c_idx = idx % cols
        x0 = pad + c_idx * (cell_w + pad)
        y0 = pad + r_idx * (cell_h + hdr_h + pad)

        draw.rectangle([x0, y0, x0 + cell_w, y0 + hdr_h + cell_h], fill=(38, 42, 52), outline=(72, 78, 94), width=1)
        draw.rectangle([x0, y0, x0 + cell_w, y0 + hdr_h], fill=(48, 54, 68))

        with Image.open(path) as im:
            ow, oh = im.size
            im_rgb = im.convert("RGB")
            fitted = ImageOps.contain(im_rgb, (cell_w - 8, cell_h - 8))
        draw.text((x0 + 10, y0 + 7), f"{rid}  ({ow}x{oh})", fill=(242, 245, 250), font=font)
        fx = x0 + (cell_w - fitted.width) // 2
        fy = y0 + hdr_h + (cell_h - fitted.height) // 2
        canvas.paste(fitted, (fx, fy))

    out_abs = os.path.join(project_dir, out_rel)
    os.makedirs(os.path.dirname(out_abs), exist_ok=True)
    canvas.save(out_abs, format="PNG")
    return out_abs, len(items), sheet_w, sheet_h


def build_video_strip(video_path: str, out_path: str, *, frames: int = 5) -> Tuple[str, Dict[str, Any]]:
    info = ffprobe_info(video_path)
    dur = info["duration"]
    ratios = [(i + 0.5) / frames for i in range(frames)]
    timestamps = [min(max(0.05, dur * r), max(0.05, dur - 0.05)) for r in ratios]

    tmp_dir = tempfile.mkdtemp(prefix="flow_strip_")
    try:
        frame_imgs: List[Tuple[float, Image.Image]] = []
        for idx, ts in enumerate(timestamps):
            fp = os.path.join(tmp_dir, f"f_{idx}.png")
            subprocess.run(
                ["ffmpeg", "-y", "-v", "error", "-ss", f"{ts:.3f}", "-i", video_path, "-frames:v", "1", fp],
                check=True,
            )
            with Image.open(fp) as im:
                frame_imgs.append((ts, im.convert("RGB")))

        target_w = 270
        sample_w, sample_h = frame_imgs[0][1].size
        target_h = int(target_w * sample_h / max(sample_w, 1))
        pad = 12
        top_hdr = 42
        sub_hdr = 28
        w_total = pad + frames * (target_w + pad)
        h_total = top_hdr + sub_hdr + target_h + pad

        canvas = Image.new("RGB", (w_total, h_total), (20, 23, 30))
        draw = ImageDraw.Draw(canvas)
        f_title = _load_font(18)
        f_sub = _load_font(15)

        header = (
            f"{os.path.basename(video_path)}  |  {info['width']}x{info['height']}  |  "
            f"{dur:.2f}s  |  {info['fps']}fps  |  audio={'yes' if info['has_audio'] else 'no'}"
        )
        draw.text((pad, 10), header, fill=(245, 247, 250), font=f_title)

        for idx, (ts, im) in enumerate(frame_imgs):
            x = pad + idx * (target_w + pad)
            y = top_hdr
            draw.rectangle([x, y, x + target_w, y + sub_hdr + target_h], fill=(35, 39, 48), outline=(72, 78, 94))
            draw.text((x + 8, y + 5), f"F{idx+1}  t={ts:.2f}s", fill=(215, 224, 240), font=f_sub)
            resized = im.resize((target_w, target_h), Image.Resampling.LANCZOS)
            canvas.paste(resized, (x, y + sub_hdr))

        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        canvas.save(out_path, format="PNG")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    return out_path, info


# ---------------------------------------------------------------------------
# CLI Entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Programmatic Google Flow automator & QC contact-sheet builder")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_insp = sub.add_parser("inspect", help="Inspect current Flow tab tiles and state")
    p_insp.add_argument("--tab", type=int, required=True)

    p_sync = sub.add_parser("sync-ledger", help="Map current grid tiles top-left-first to IDs in refs/.flow_assets.json")
    p_sync.add_argument("--tab", type=int, required=True)
    p_sync.add_argument("--project", required=True)
    p_sync.add_argument("--order", required=True, help="Comma-separated IDs matching current top-left-first grid order")

    p_dl = sub.add_parser("download-top", help="Download top-left Flow tile via Lightbox (no hover)")
    p_dl.add_argument("--tab", type=int, required=True)
    p_dl.add_argument("--project", required=True)
    p_dl.add_argument("--id", required=True)
    p_dl.add_argument("--out", default=None, help="Override relative output path")
    p_dl.add_argument("--media", choices=["image", "video"], default="image")
    p_dl.add_argument("--idx", type=int, default=0)
    p_dl.add_argument("--upscale-1080p", action="store_true")
    p_dl.add_argument("--credits", default="0")
    p_dl.add_argument("--log", action="store_true")

    p_refs = sub.add_parser("refs", help="Generate and download reference sheets via Nano Banana 2 Lite (0 credits)")
    p_refs.add_argument("--tab", type=int, required=True)
    p_refs.add_argument("--project", required=True)
    p_refs.add_argument("--ids", required=True, help="Comma-separated ref IDs, e.g. R07,R08,R09")
    p_refs.add_argument("--attach", default=None, help="Comma-separated asset IDs to attach")
    p_refs.add_argument("--prompt-file", default=None, help="Override prompt from file (single-ID only)")
    p_refs.add_argument("--ar", default=None, help="Override aspect ratio (e.g. 9:16, 1:1, 16:9)")
    p_refs.add_argument("--strip-face-anchors", action="store_true")
    p_refs.add_argument("--log", action="store_true")

    p_cs = sub.add_parser("contact-sheet", help="Stitch reference PNGs into 1 labeled QC PNG")
    p_cs.add_argument("--project", required=True)
    p_cs.add_argument("--out", required=True, help="Relative output PNG path inside project")
    p_cs.add_argument("--ids", default=None, help="Comma-separated subset of IDs")
    p_cs.add_argument("--cols", type=int, default=4)
    p_cs.add_argument("--thumb-w", type=int, default=360)

    p_vs = sub.add_parser("video-strip", help="Extract N frames from MP4 and stitch 1 QC strip PNG")
    p_vs.add_argument("--video", required=True)
    p_vs.add_argument("--out", required=True)
    p_vs.add_argument("--frames", type=int, default=5)

    p_ff = sub.add_parser("extract-first-frame", help="Extract frame PNG from MP4 at exact timestamp for Flow bridge")
    p_ff.add_argument("--project", required=True)
    p_ff.add_argument("--video", required=True)
    p_ff.add_argument("--id", required=True)
    p_ff.add_argument("--out", default=None)
    p_ff.add_argument("--time", type=float, default=0.0)

    p_lf = sub.add_parser("extract-last-frame", help="Extract clean final frame PNG from MP4 and register in Flow ledger")
    p_lf.add_argument("--project", required=True)
    p_lf.add_argument("--video", required=True)
    p_lf.add_argument("--id", required=True)
    p_lf.add_argument("--out", default=None)
    p_lf.add_argument("--offset", type=float, default=0.15)

    p_vid = sub.add_parser("video", help="Generate Omni 1.2 Flash video clip with hard credit guard")
    p_vid.add_argument("--tab", type=int, required=True)
    p_vid.add_argument("--project", required=True)
    p_vid.add_argument("--id", required=True)
    p_vid.add_argument("--mode", choices=["ingredients", "frames"], default=None)
    p_vid.add_argument("--model", default=None)
    p_vid.add_argument("--ar", default=None)
    p_vid.add_argument("--attach", default=None)
    p_vid.add_argument("--first-frame", default=None)
    p_vid.add_argument("--last-frame", default=None)
    p_vid.add_argument("--duration", type=int, default=None)
    p_vid.add_argument("--res", default=None)
    p_vid.add_argument("--est-credits", type=int, default=None)
    p_vid.add_argument("--max-credits", type=int, required=True)
    p_vid.add_argument("--prompt-file", default=None)
    p_vid.add_argument("--out", default=None)
    p_vid.add_argument("--upscale-1080p", action="store_true")
    p_vid.add_argument("--log", action="store_true")

    p_vb = sub.add_parser("video-batch", help="Batch-run pending video units from 06_jobs.json within cumulative credit cap")
    p_vb.add_argument("--tab", type=int, required=True)
    p_vb.add_argument("--project", required=True)
    p_vb.add_argument("--ids", required=True, help="Comma-separated unit IDs in 06_jobs.json")
    p_vb.add_argument("--concurrency", type=int, default=3, help="Max concurrent submissions per wave in Flow (e.g. 3-4)")
    p_vb.add_argument("--max-credits", type=int, required=True)
    p_vb.add_argument("--upscale-1080p", action="store_true")
    p_vb.add_argument("--force", action="store_true", help="Re-run even if status==completed in 06_jobs.json")
    p_vb.add_argument("--log", action="store_true")

    args = parser.parse_args()

    if args.cmd == "inspect":
        st = get_media_state(args.tab)
        summary = {
            "url": st.get("url"),
            "count": st.get("count"),
            "items": [
                {
                    "idx": i,
                    "kind": it["kind"],
                    "title": it.get("title", ""),
                    "w": it["w"],
                    "h": it["h"],
                    "nw": it["nw"],
                    "nh": it["nh"],
                    "src_key": it["src_key"],
                }
                for i, it in enumerate(st.get("items", []))
            ],
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))

    elif args.cmd == "sync-ledger":
        ensure_grid_view(args.tab)
        close_overlays(args.tab)
        scroll_grid_top(args.tab)
        st = get_media_state(args.tab)
        ids = [x.strip() for x in args.order.split(",") if x.strip()]
        items = st.get("items", [])
        if len(items) < len(ids):
            raise RuntimeError(f"Grid has {len(items)} tiles, fewer than --order ({len(ids)}): {ids}")

        # Capture exact Flow picker titles in newest-first order
        picker_titles: List[str] = []
        dom_s = read_dom(args.tab)
        p_trig = find_ref(dom_s, role="button", name="프롬프트 상자에 소재 추가") or find_ref(dom_s, role="button", name="시작")
        if p_trig:
            click_ref(args.tab, p_trig)
            time.sleep(0.45)
            dom_opts = read_dom(args.tab)
            picker_titles = [_norm_title(el.get("name", "")) for el in dom_opts.get("elements", []) if el.get("role") == "option"]
            close_overlays(args.tab)

        jobs = load_jobs(args.project)
        ref_map = {r["id"]: r for r in _all_image_assets(jobs)}
        unit_map = {u["id"]: u for u in jobs.get("units", [])}
        ledger = load_ledger(args.project)
        for idx, (rid, it) in enumerate(zip(ids, items)):
            meta = ref_map.get(rid) or unit_map.get(rid) or {}
            rel_file = meta.get("file") or (meta.get("outputs", [None])[0] if meta else "")
            ar = (meta.get("settings") or {}).get("aspect_ratio", "")
            inferred_title = it.get("title") or (picker_titles[idx] if len(picker_titles) == len(items) else "") or (ledger.get(rid) or {}).get("title", "")
            ledger[rid] = {
                **(ledger.get(rid) or {}),
                "file": rel_file,
                "src_key": it["src_key"],
                "title": inferred_title,
                "ar": ar,
                "media_type": it["kind"],
            }
        save_ledger(args.project, ledger)
        print(json.dumps({"synced": ids, "titles_captured": len(picker_titles), "ledger": ledger_path(args.project)}, ensure_ascii=False))

    elif args.cmd == "download-top":
        jobs = load_jobs(args.project)
        ref_map = {r["id"]: r for r in _all_image_assets(jobs)}
        unit_map = {u["id"]: u for u in jobs.get("units", [])}
        rel_out = args.out
        if not rel_out:
            if args.id in ref_map:
                rel_out = ref_map[args.id]["file"]
            elif args.id in unit_map:
                rel_out = unit_map[args.id]["outputs"][0]
            else:
                raise RuntimeError(f"ID {args.id} not found in 06_jobs.json and --out not provided")
        res = download_top_lightbox(
            args.tab,
            args.project,
            rel_out,
            media=args.media,
            upscale_1080p=args.upscale_1080p,
            idx=args.idx,
        )
        ledger = load_ledger(args.project)
        ar = ((ref_map.get(args.id) or unit_map.get(args.id) or {}).get("settings") or {}).get("aspect_ratio", "")
        ledger[args.id] = {
            "file": res["file"],
            "src_key": res["src_key"],
            "ar": ar,
            "media_type": args.media,
            "width": res["width"],
            "height": res["height"],
            "bytes": res["bytes"],
            "title": res.get("title", ""),
        }
        save_ledger(args.project, ledger)
        if args.log:
            notes = f"Lightbox 1K→PNG {res['width']}x{res['height']} ({res['bytes']:,}B)"
            append_generation_log(
                args.project,
                unit_id=args.id,
                take="t1",
                platform_cfg=f"Google Flow · Nano Banana 2 Lite · {ar or '9:16'} · x1",
                credits_str=str(args.credits),
                result_file=res["file"],
                status="성공",
                notes=notes,
            )
        print(json.dumps(res, ensure_ascii=False))

    elif args.cmd == "refs":
        jobs = load_jobs(args.project)
        ref_map = {r["id"]: r for r in _all_image_assets(jobs)}
        req_ids = [x.strip() for x in args.ids.split(",") if x.strip()]
        if args.prompt_file and len(req_ids) != 1:
            raise RuntimeError("--prompt-file can only be used with a single ID in --ids")
        prompt_override = None
        if args.prompt_file:
            with open(args.prompt_file, "r", encoding="utf-8") as f:
                prompt_override = f.read().strip()
        attach_ids = [x.strip() for x in args.attach.split(",") if x.strip()] if args.attach else None
        for rid in req_ids:
            if rid not in ref_map:
                raise RuntimeError(f"Unknown ref ID: {rid}")
            generate_ref(
                args.tab,
                args.project,
                ref_map[rid],
                prompt_override=prompt_override,
                ar_override=args.ar,
                attach_ids=attach_ids,
                strip_face_anchors=args.strip_face_anchors,
                write_log=args.log,
            )

    elif args.cmd == "contact-sheet":
        sub_ids = [x.strip() for x in args.ids.split(",") if x.strip()] if args.ids else None
        out_abs, count, sw, sh = build_contact_sheet(
            args.project, args.out, ids=sub_ids, cols=args.cols, thumb_w=args.thumb_w
        )
        print(json.dumps({"out": out_abs, "tiles": count, "width": sw, "height": sh}, ensure_ascii=False))

    elif args.cmd == "video-strip":
        out_abs, info = build_video_strip(args.video, args.out, frames=args.frames)
        print(json.dumps({"out": out_abs, "info": info}, ensure_ascii=False))

    elif args.cmd == "extract-first-frame":
        res = extract_first_frame(args.project, args.video, args.id, rel_out=args.out, time_sec=args.time)
        print(json.dumps(res, ensure_ascii=False))

    elif args.cmd == "extract-last-frame":
        res = extract_last_frame(args.project, args.video, args.id, rel_out=args.out, offset=args.offset)
        print(json.dumps(res, ensure_ascii=False))

    elif args.cmd == "video":
        cmd_video(args)

    elif args.cmd == "video-batch":
        cmd_video_batch(args)


if __name__ == "__main__":
    main()
