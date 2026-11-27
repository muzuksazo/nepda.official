"""FR-004 콘티 이미지와 FR-005 훅 영상(+TTS) 만들기.

장면별 화면 소재:
  - 문제 장면(첫 장면): assets.problem_template 이 있으면 생성 영상, 없으면 다음 소재로.
      engine "omni"    Blender 가 렌더한 첫 프레임 → Google Gemini Omni 가 영상으로 생성, 3~15초 (omni.py)
      engine "veo"     같은 방식으로 Google Veo 가 생성, 4·6·8초 (veo.py)
      (블록아웃 템플릿은 Veo·Omni 에 넘기기 전에 Nano Banana 가 첫 프레임을 같은 구도의 실사 사진으로 바꾼다. nanobanana.py)
      engine "minimax" 같은 방식으로 MiniMax(Hailuo, MiniMax-H3 계열)가 생성, 4~15초 (minimax.py). MINIMAX_API_KEY 가 필요하다
      engine "blender" Blender 물리 시뮬레이션을 전 프레임 렌더
      engine "auto"    C_GENERATOR 로 고른 모델(기본 veo)의 설정이 있으면 그 모델, 없거나 실패하면 blender (기본)
  - 그 밖의 장면: assets.product_footage(실물 제품 영상)를 장면 길이 비율로 나눠 이어 쓴다. 증명은 실물만 보여 준다.
  - 소재가 없으면 자막만 있는 단색 카드.
필요한 프로그램: ffmpeg(자막 번인용 libass 포함), 문제 장면 템플릿을 쓸 때는 Blender 4.2 이상.
"""
from __future__ import annotations

import glob
import json
import os
import shutil
import subprocess
import sys
from typing import Callable

from . import minimax
from . import nanobanana
from . import omni
from . import tts as tts_mod
from . import veo
from .assets import assets_dir

FPS = 24
W, H = 1080, 1920
HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATES = {
    "spill_diffuser": {"script": os.path.join(HERE, "blender_scene.py"), "frames": 84, "impact_sec": 1.25},
    # 같은 테이블·디퓨저 장면에서 시작하되 생성 모델에는 "고양이가 쳐서 쓰러뜨린다"로 시킨다. Blender 로 대신하면 손이 친다.
    "cat_spill_diffuser": {"script": os.path.join(HERE, "blender_scene.py"), "frames": 84, "impact_sec": 1.25, "cache": "spill_diffuser"},
    "spray_panic": {"script": os.path.join(HERE, "blender_scene.py"), "frames": 84, "impact_sec": 1.25, "cache": "spill_diffuser"},
    "carry_drip": {"script": os.path.join(HERE, "blender_scene.py"), "frames": 84, "impact_sec": 1.25, "cache": "spill_diffuser"},
    "reed_flip": {"script": os.path.join(HERE, "blender_scene.py"), "frames": 84, "impact_sec": 1.25, "cache": "spill_diffuser"},
    "evaporate_diffuser": {"script": os.path.join(HERE, "blender_scene_evaporate.py"), "frames": 96, "impact_sec": None},
    # script 가 None 인 템플릿은 Blender 장면 없이 생성 모델(Veo · Gemini Omni)이 글만으로 만든다.
    "phone_distract": {"script": None, "frames": 0, "impact_sec": None},
    # 같은 장면의 Blender 블록아웃. 회색 상자 수준이라 그대로 쓰는 화면이 아니고, 구도·카메라·동작 타이밍을 생성 모델에 넘기는 용도다.
    "phone_distract_blockout": {"script": os.path.join(HERE, "blender_scene_desk.py"), "frames": 96, "impact_sec": None, "blockout": True},
    # 같은 책상 장면의 실사용 첫 프레임 (손 없음). Google Veo 가 이 화면에서 이어 만든다.
    "phone_distract_desk": {"script": os.path.join(HERE, "blender_scene_desk_real.py"), "frames": 96, "impact_sec": None},
    "closet_musty": {"script": os.path.join(HERE, "blender_scene_closet.py"), "frames": 96, "impact_sec": None, "still": 36},
    "drain_smell": {"script": os.path.join(HERE, "blender_scene_drain.py"), "frames": 240, "impact_sec": None, "sfx": [("spray", 4.5)], "still": 10},
}
# 템플릿 장면에 붙는 효과음 (ffmpeg 로 합성). Blender 렌더일 때만 넣는다: 그때만 동작 시점을 안다.
SFX = {
    "spray": "anoisesrc=d=1.8:c=white:a=0.55:r=48000,highpass=f=3200,lowpass=f=9500,"
             "volume='0.55+0.45*sin(2*PI*5.3*t)':eval=frame,afade=t=in:d=0.04,afade=t=out:st=1.6:d=0.2,volume=0.5",
}
GOLD, WHITE = "&H0047E0FF&", "&H00FFFFFF&"


class RenderError(RuntimeError):
    pass


def _run(cmd: list[str], cwd: str | None = None) -> None:
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        raise RenderError(f"{os.path.basename(cmd[0])} 실패:\n{(p.stderr or p.stdout)[-1500:]}")


def _tool(name: str, env: str) -> str:
    path = os.environ.get(env) or shutil.which(name)
    if not path:
        raise RenderError(f"{name} 을(를) 찾지 못했습니다. PATH 에 넣거나 {env} 에 경로를 지정하세요.")
    return path


def _blender() -> str:
    path = os.environ.get("BLENDER_BIN") or shutil.which("blender")
    if not path and sys.platform == "win32":
        found = sorted(glob.glob(r"C:\Program Files\Blender Foundation\Blender *\blender.exe"))
        path = found[-1] if found else None
    if not path:
        raise RenderError("Blender 를 찾지 못했습니다. BLENDER_BIN 에 실행 파일 경로를 지정하세요.")
    return path


def _font() -> str:
    return os.environ.get("C_FONT") or ("Malgun Gothic" if sys.platform == "win32" else "Noto Sans CJK KR")


def _duration(path: str) -> float:
    out = subprocess.run([_tool("ffprobe", "FFPROBE_BIN"), "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                         capture_output=True, text=True)
    try:
        return float(out.stdout.strip())
    except ValueError as e:
        raise RenderError(f"영상 길이를 읽지 못했습니다: {path}") from e


def problem_frames(template: str, log: Callable[[str], None] = print) -> str:
    """문제 장면 템플릿을 렌더해 프레임 폴더를 돌려준다. 한 번 만들면 assets/cache 에 두고 다시 쓴다."""
    if template not in TEMPLATES:
        raise RenderError(f"모르는 문제 장면 템플릿: {template} (사용 가능: {', '.join(TEMPLATES)})")
    spec = TEMPLATES[template]
    out = os.path.join(assets_dir(), "cache", spec.get("cache", template))
    done = len([f for f in glob.glob(os.path.join(out, "p_*.jpg")) if os.path.getsize(f) > 10000])
    if done >= spec["frames"]:
        return out
    log(f"Blender 로 문제 장면 '{template}' 렌더 중 (물리 계산 + {spec['frames']}프레임, 수 분 걸립니다)…")
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out, exist_ok=True)
    _run([_blender(), "-b", "-P", spec["script"], "--", out, assets_dir(), os.environ.get("C_RENDER_PERCENT", "100")])
    done = len(glob.glob(os.path.join(out, "p_*.jpg")))
    if done < spec["frames"]:
        raise RenderError(f"문제 장면 렌더가 끝나지 않았습니다 ({done}/{spec['frames']}프레임).")
    return out


def first_frame(template: str, log: Callable[[str], None] = print) -> str:
    """문제 장면의 첫 프레임(Veo 의 시작 이미지). 전체 렌더가 이미 있으면 그 1번 프레임을 쓰고, 없으면 한 장만 렌더한다."""
    if template not in TEMPLATES:
        raise RenderError(f"모르는 문제 장면 템플릿: {template} (사용 가능: {', '.join(TEMPLATES)})")
    still = int(TEMPLATES[template].get("still", 1))          # 생성 모델에 넘길 프레임 (불이 켜진 뒤처럼 장면이 잘 보이는 때)
    cache_name = TEMPLATES[template].get("cache", template)          # 같은 Blender 장면을 쓰는 템플릿은 렌더 결과를 함께 쓴다
    full = os.path.join(assets_dir(), "cache", cache_name, f"p_{still:04d}.jpg")
    if os.path.exists(full) and os.path.getsize(full) > 10000:
        return _still_png(full)
    out = os.path.join(assets_dir(), "cache", cache_name + "_first")
    path = os.path.join(out, f"p_{still:04d}.jpg")
    if not (os.path.exists(path) and os.path.getsize(path) > 10000):
        log(f"Blender 로 문제 장면 '{template}' 의 첫 프레임 렌더 중…")
        shutil.rmtree(out, ignore_errors=True)
        os.makedirs(out, exist_ok=True)
        _run([_blender(), "-b", "-P", TEMPLATES[template]["script"], "--", out, assets_dir(), os.environ.get("C_RENDER_PERCENT", "100"),
              str(still), str(still)])
        if not os.path.exists(path):
            raise RenderError("문제 장면 첫 프레임 렌더에 실패했습니다.")
    return _still_png(path)


def refined_first_frame(template: str, image: str, log: Callable[[str], None] = print, *, generate: bool = True) -> str | None:
    """블록아웃 첫 프레임을 Nano Banana 로 실사화한 720x1280 PNG. 실사화 지시가 없는 템플릿은 받은 화면을 그대로 돌려준다.

    generate=False 면 과금 호출 없이 이미 만든 것만 찾고, 없으면 None.
    """
    prompt = nanobanana.REFINE.get(template)
    if not prompt or os.environ.get("C_FIRST_FRAME_REFINE", "").strip().lower() in ("0", "off", "no", "false"):
        return image
    cache = os.path.join(assets_dir(), "cache", "nanobanana")
    jpg = nanobanana.generate(prompt, image, cache, template, log=log) if generate else nanobanana.cached(prompt, image, cache, template)
    if not jpg:
        return None
    png = jpg[:-4] + "_720.png"
    if not (os.path.exists(png) and os.path.getmtime(png) >= os.path.getmtime(jpg)):
        _run([_tool("ffmpeg", "FFMPEG_BIN"), "-v", "error", "-y", "-i", jpg, "-vf", "scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280", png])
    return png


def playblast_path(template: str) -> str:
    return os.path.join(assets_dir(), "cache", TEMPLATES[template].get("cache", template), "playblast.mp4")


def playblast(template: str, log: Callable[[str], None] = print) -> str:
    """Blender 블록아웃의 플레이블라스트(720x1280 mp4). 생성 모델에 구도·동작 참조로 넘긴다. 한 번 만들면 다시 쓴다."""
    path = playblast_path(template)
    if not (os.path.exists(path) and os.path.getsize(path) > 10000):
        frames = problem_frames(template, log)
        _run([_tool("ffmpeg", "FFMPEG_BIN"), "-v", "error", "-y", "-framerate", str(FPS), "-i", os.path.join(frames, "p_%04d.jpg"),
              "-vf", "scale=720:1280", "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart", path])
    return path


def _has_audio(path: str) -> bool:
    out = subprocess.run([_tool("ffprobe", "FFPROBE_BIN"), "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", path],
                         capture_output=True, text=True).stdout
    return bool(out.strip())


def _still_png(jpg: str) -> str:
    """생성 모델에 보낼 720x1280 PNG. Blender 가 낸 JPEG 을 그대로 보내면 Gemini Omni 가 "파일을 해석할 수 없다"며 실패했다."""
    png = jpg[:-4] + "_720.png"
    if not (os.path.exists(png) and os.path.getmtime(png) >= os.path.getmtime(jpg)):
        _run([_tool("ffmpeg", "FFMPEG_BIN"), "-v", "error", "-y", "-i", jpg, "-vf", "scale=720:1280", png])
    return png


def problem_engine(assets: dict) -> str:
    engine = str(assets.get("problem_engine") or os.environ.get("C_PROBLEM_ENGINE") or "auto").strip().lower()
    if engine not in ("auto", "omni", "veo", "minimax", "blender"):
        raise RenderError(f"problem_engine 은 auto · omni · veo · minimax · blender 중 하나여야 합니다: {engine}")
    return engine


GENERATORS = {"omni": omni, "veo": veo, "minimax": minimax}          # 영상 생성 모델 (Google Cloud 둘, MiniMax 하나)
# auto 가 쓰는 모델. Veo 는 Google Cloud 무료 체험 계정에서도 생성됐고, Gemini Omni 는 "유료 결제 계정이 필요하다"로 거절됐다.
# 유료 계정이면 C_GENERATOR=omni 로 바꾼다 (Omni 는 3~15초를 한 번에 만든다). MiniMax 로 만들려면 C_GENERATOR=minimax.
DEFAULT_GENERATOR = os.environ.get("C_GENERATOR", "veo").strip().lower() if os.environ.get("C_GENERATOR", "veo").strip().lower() in GENERATORS else "veo"


def problem_source(src: dict, seconds: float, log: Callable[[str], None] = print, *, generate: bool = True) -> dict:
    """문제 장면에 실제로 쓸 소재를 정한다 → {"kind": "clip", "path"} (Omni·Veo) 또는 {"kind": "frames", "dir"} (Blender).

    generate=False 면 과금되는 생성 호출을 하지 않고, 이미 만든 영상이 있을 때만 그것을 쓴다 (콘티용).
    """
    template, engine = src["template"], src["engine"]
    if engine in GENERATORS or (engine == "auto" and GENERATORS[DEFAULT_GENERATOR].configured()):
        name = engine if engine in GENERATORS else DEFAULT_GENERATOR
        gen = GENERATORS[name]
        cache = os.path.join(assets_dir(), "cache", name)
        try:
            image = first_frame(template, log) if TEMPLATES[template]["script"] else None
            extra = {}
            # MiniMax 는 블록아웃을 첫 프레임이 아니라 참조 영상으로 받는다 (첫 프레임으로 주면 회색 상자 화면이 그대로 이어진다).
            if name == "minimax" and image and (TEMPLATES[template].get("blockout") or os.environ.get("C_MINIMAX_MODE", "").strip().lower() == "reference"):
                ref = playblast(template, log) if generate else playblast_path(template)
                extra = {"reference_video": ref} if os.path.exists(ref) else {"reference_video": None}
            # Veo·Omni 는 첫 프레임에서 그대로 이어 만든다. 블록아웃이면 먼저 Nano Banana 로 같은 구도의 실사 사진으로 바꾼다.
            if name != "minimax" and image:
                image = refined_first_frame(template, image, log, generate=generate)
            if (extra and extra["reference_video"] is None) or (TEMPLATES[template]["script"] and image is None):
                clip = None                                   # 콘티 단계: 참조 영상이나 실사 첫 프레임이 아직 없으면 만든 영상도 없다
            else:
                clip = gen.generate(template, image, cache, seconds, log=log, **extra) if generate else gen.cached(cache, template, image, seconds, **extra)
            if clip:
                return {"kind": "clip", "path": clip, "engine": f"{name}:{gen.model()}", "audio": bool(getattr(gen, "audio", lambda: False)())}
        except veo.VeoError as e:                 # OmniError, MinimaxError 도 여기에 들어온다
            if engine in GENERATORS:
                raise RenderError(str(e)) from e
            if not TEMPLATES[template]["script"]:
                raise RenderError(str(e)) from e
            log(f"  {name} 를 쓰지 못해 Blender 렌더로 대신합니다: {e}")
    if not TEMPLATES[template]["script"]:
        raise RenderError(f"템플릿 {template} 은 Blender 장면이 없습니다. GOOGLE_CLOUD_PROJECT(Veo·Omni) 나 MINIMAX_API_KEY(MiniMax) 를 설정해 먼저 생성하세요.")
    if not generate and engine != "blender":
        # 콘티 단계이고 생성 영상이 아직 없다. 전 프레임을 렌더하지 않고(수 분) 생성 모델에 넘길 첫 프레임 한 장만 쓴다.
        spec = TEMPLATES[template]
        done = len(glob.glob(os.path.join(assets_dir(), "cache", spec.get("cache", template), "p_*.jpg")))
        if done < spec["frames"]:
            return {"kind": "still", "path": first_frame(template, log), "engine": "blender"}
    return {"kind": "frames", "dir": problem_frames(template, log), "engine": "blender"}


def _clip_speed(clip_len: float, span: float) -> float:
    """생성 영상의 재생 속도 (0.75~1.6배속). C_CLIP_MAX_SPEED 로 상한을 낮추면 긴 영상의 앞부분만 제 속도로 쓴다."""
    top = float(os.environ.get("C_CLIP_MAX_SPEED", "1.6") or 1.6)
    return max(0.75, min(top, clip_len / span))


def plan_sources(scenario: dict, assets: dict) -> list[dict]:
    """장면마다 무엇을 화면에 쓸지 정한다."""
    beats = scenario["beats"]
    template = assets.get("problem_template")
    engine = problem_engine(assets)
    footage = assets.get("product_footage")
    footage = os.path.abspath(footage) if footage else None
    if footage and not os.path.exists(footage):
        raise RenderError(f"실물 영상이 없습니다: {footage}")
    plan = []
    footage_beats = []
    # 문제 장면은 첫 장면부터, role 이 "문제"인 장면이 이어지는 동안 한 영상으로 계속 쓴다 (긴 훅: 문제 장면 여러 개).
    lead = 1 if template else 0
    while template and lead < len(beats) and any(k in str(beats[lead].get("role", "")) for k in ("문제", "problem")):
        lead += 1
    span = sum(b["duration_sec"] for b in beats[:lead])
    offset = 0.0
    shared: dict = {}
    for i, b in enumerate(beats):
        if i < lead:
            plan.append({"kind": "template", "template": template, "engine": engine, "offset": offset, "span": span, "shared": shared})
            offset += b["duration_sec"]
        elif footage:
            plan.append({"kind": "footage", "path": footage})
            footage_beats.append(i)
        else:
            plan.append({"kind": "card"})
    if footage_beats:
        total = _duration(footage)
        need = sum(beats[i]["duration_sec"] for i in footage_beats)
        speed = max(0.85, min(1.0, total / need))            # 소재가 짧으면 0.85배속까지만 늘리고 나머지는 정지 화면
        pos = 0.0
        for n, i in enumerate(footage_beats):
            length = beats[i]["duration_sec"] * speed
            plan[i].update({"start": round(min(pos, max(0.0, total - 0.2)), 3), "speed": speed, "zoom": 1.22 if n % 2 == 1 else 1.0})
            pos += length
    # 컷 편집: assets.footage_cuts 가 있으면 실물 장면을 1.6초 안팎의 컷으로 나누고, 목록의 구도(시점·확대·중심)를 차례로 쓴다.
    cuts = [c for c in (assets.get("footage_cuts") or []) if isinstance(c, dict)]
    if footage_beats and cuts:
        ci = 0
        for i in footage_beats:
            d = beats[i]["duration_sec"]
            count = max(1, int(round(d / 1.6)))
            sub = []
            for _ in range(count):
                c = cuts[ci % len(cuts)]
                ci += 1
                focus = c.get("focus") or [0.5, 0.5]
                sub.append({"t": max(0.0, min(float(c.get("t", 0)), total - 0.3)), "zoom": max(1.0, float(c.get("zoom", 1.0))),
                            "focus": (float(focus[0]), float(focus[1]))})
            plan[i].update({"cuts": sub, "start": sub[0]["t"], "speed": 1.0, "zoom": 1.0, "fit": str(assets.get("footage_fit") or "cover")})
    return plan


def _size(path: str) -> tuple[int, int]:
    out = subprocess.run([_tool("ffprobe", "FFPROBE_BIN"), "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                          "-of", "csv=p=0", path], capture_output=True, text=True)
    try:
        w, h = out.stdout.strip().split(",")[:2]
        return int(w), int(h)
    except ValueError as e:
        raise RenderError(f"영상 크기를 읽지 못했습니다: {path}") from e


def _segment(index: int, beat: dict, src: dict, inputs: list[str], filters: list[str], log) -> None:
    n = int(round(beat["duration_sec"] * FPS))
    pad = f"tpad=stop_mode=clone:stop_duration={beat['duration_sec'] + 1:.2f},trim=end_frame={n},setpts=PTS-STARTPTS,setsar=1,format=yuv420p"
    k = len(inputs_index(inputs))
    if src["kind"] == "template":
        # 문제 장면이 여러 장면에 걸쳐도 소재는 한 번만 정한다 (생성 호출이 장면마다 다시 나가거나 소재가 섞이지 않게).
        got = src["shared"].get("got") or problem_source(src, src["span"], log)
        src["shared"]["got"] = src["resolved"] = got
        if got["kind"] == "clip":
            # Veo 는 4·6·8초로만 나온다. 문제 장면 전체 길이에 맞춰 속도를 조절한다 (0.75~1.6배속, 넘치면 뒤를 자르고 모자라면 마지막 화면 정지).
            speed = _clip_speed(_duration(got["path"]), src["span"])
            inputs += ["-ss", f"{src['offset'] * speed:.3f}", "-i", got["path"]]
            filters.append(f"[{k}:v]setpts=(PTS-STARTPTS)/{speed:.3f},fps={FPS},"
                           f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H},{pad}[s{index}]")
        else:
            start = min(TEMPLATES[src["template"]]["frames"], 1 + int(round(src["offset"] * FPS)))
            inputs += ["-framerate", str(FPS), "-start_number", str(start), "-i", os.path.join(got["dir"], "p_%04d.jpg")]
            filters.append(f"[{k}:v]scale={W}:{H}:flags=lanczos,eq=saturation=1.1:brightness=0.02,noise=alls=3:allf=t,{pad}[s{index}]")
    elif src["kind"] == "footage" and src.get("cuts"):
        sw, sh = _size(src["path"])
        grade = "eq=contrast=1.05:saturation=1.12,unsharp=5:5:0.6:5:5:0.0"
        labels = []
        for j, c in enumerate(src["cuts"]):
            nf = n // len(src["cuts"]) + (1 if j < n % len(src["cuts"]) else 0)
            kk = len(inputs_index(inputs))
            inputs += ["-ss", f"{c['t']:.3f}", "-t", f"{nf / FPS + 1:.2f}", "-i", src["path"]]
            cw, ch = int(sw / c["zoom"]) // 2 * 2, int(sh / c["zoom"]) // 2 * 2
            x = max(0, min(sw - cw, int(c["focus"][0] * sw - cw / 2)))
            y = max(0, min(sh - ch, int(c["focus"][1] * sh - ch / 2)))
            z = f"1+0.06*on/{nf}" if j % 2 == 0 else f"1.06-0.06*on/{nf}"          # 컷마다 다가가기·물러나기를 번갈아
            if src.get("fit") == "blur":
                # 세로가 아닌 실물 영상: 자르지 않고 가로를 꽉 채워 놓고, 위아래는 같은 화면을 흐리게 깔아 채운다.
                filters.append(f"[{kk}:v]fps={FPS},crop={cw}:{ch}:{x}:{y},split[b{index}_{j}][f{index}_{j}];"
                               f"[b{index}_{j}]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},gblur=sigma=42,eq=brightness=-0.10:saturation=0.9[bb{index}_{j}];"
                               f"[f{index}_{j}]scale={W * 2}:-2:flags=lanczos,zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={W}x{W * ch // cw // 2 * 2}:fps={FPS}[ff{index}_{j}];"
                               f"[bb{index}_{j}][ff{index}_{j}]overlay=0:(H-h)/2,{grade},"
                               f"tpad=stop_mode=clone:stop_duration=2,trim=end_frame={nf},setpts=PTS-STARTPTS,setsar=1,format=yuv420p[c{index}_{j}]")
                labels.append(f"[c{index}_{j}]")
                continue
            filters.append(f"[{kk}:v]fps={FPS},crop={cw}:{ch}:{x}:{y},scale={W * 2}:{H * 2}:force_original_aspect_ratio=increase:flags=lanczos,"
                           f"crop={W * 2}:{H * 2},zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={W}x{H}:fps={FPS},{grade},"
                           f"tpad=stop_mode=clone:stop_duration=2,trim=end_frame={nf},setpts=PTS-STARTPTS,setsar=1,format=yuv420p[c{index}_{j}]")
            labels.append(f"[c{index}_{j}]")
        filters.append("".join(labels) + f"concat=n={len(labels)}:v=1:a=0,setsar=1,format=yuv420p[s{index}]")
    elif src["kind"] == "footage":
        inputs += ["-ss", str(src["start"]), "-t", f"{beat['duration_sec'] + 1:.2f}", "-i", src["path"]]
        zoom = f"crop=iw/{src['zoom']}:ih/{src['zoom']}," if src["zoom"] != 1.0 else ""
        # 실물 컷: 천천히 다가가는 움직임(2배로 키운 뒤 확대해 떨림을 줄인다), 약한 색 보정과 선명도.
        push = (f"scale={W * 2}:{H * 2}:flags=bicubic,zoompan=z='1+0.07*on/{n}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                f":d=1:s={W}x{H}:fps={FPS},eq=contrast=1.05:saturation=1.12,unsharp=5:5:0.5:5:5:0.0")
        filters.append(f"[{k}:v]setpts=(PTS-STARTPTS)/{src['speed']:.3f},fps={FPS},{zoom}"
                       f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H},{push},{pad}[s{index}]")
    else:
        inputs += ["-f", "lavfi", "-t", f"{beat['duration_sec']:.2f}", "-i", f"color=c=0x1f3d30:s={W}x{H}:r={FPS}"]
        filters.append(f"[{k}:v]{pad}[s{index}]")


def inputs_index(inputs: list[str]) -> list[int]:
    return [i for i, a in enumerate(inputs) if a == "-i"]


def _ts(x: float, srt: bool = False) -> str:
    h, m, s = int(x // 3600), int(x % 3600 // 60), x % 60
    if srt:
        return f"{h:02d}:{m:02d}:{int(s):02d},{int(round((s % 1) * 1000)) % 1000:03d}"
    return f"{h}:{m:02d}:{s:05.2f}"


def _ass_head() -> str:
    font = _font()
    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Big,{font},100,&H00FFFFFF,&H00FFFFFF,&H00101010,&H80000000,-1,0,0,0,100,100,0,0,1,7,3,5,40,40,40,1
Style: Pov,{font},50,&H00FFFFFF,&H00FFFFFF,&H00101010,&H80000000,-1,0,0,0,100,100,0,0,1,4,1,5,40,40,40,1
Style: Card,{font},56,&H00201C18,&H00201C18,&H00FFFFFF,&H00000000,-1,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1
Style: CardLabel,{font},36,&H004E8A1A,&H004E8A1A,&H00FFFFFF,&H00000000,-1,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1
Style: Badge,{font},30,&H00FFFFFF,&H00FFFFFF,&H90000000,&H90000000,0,0,0,0,100,100,1,0,3,10,0,7,40,40,40,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _starts(beats: list[dict]) -> list[float]:
    out, t = [], 0.0
    for b in beats:
        out.append(t)
        t += b["duration_sec"]
    return out


def write_srt(path: str, beats: list[dict]) -> None:
    """가이드 규칙: beats[].caption 을 장면 시작·끝 시각에 맞춘다."""
    starts = _starts(beats)
    with open(path, "w", encoding="utf-8") as f:
        for b, s in zip(beats, starts):
            f.write(f"{b['order']}\n{_ts(s, True)} --> {_ts(s + b['duration_sec'], True)}\n{b['caption']}\n\n")


def storyboard(scenario: dict, assets: dict, out_dir: str, log: Callable[[str], None] = print) -> list[dict]:
    """장면마다 대표 화면 한 장에 자막을 얹어 storyboard_NN.png 로 저장한다."""
    out_dir = os.path.abspath(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    ffmpeg = _tool("ffmpeg", "FFMPEG_BIN")
    plan = plan_sources(scenario, assets)
    frames = []
    for beat, src in zip(scenario["beats"], plan):
        name = f"storyboard_{beat['order']:02d}.png"
        ass = _ass_head() + f"Dialogue: 0,{_ts(0)},{_ts(10)},Big,,0,0,0,,{{\\pos({W // 2},1340)\\fs84}}" + beat["caption"].replace("\n", "\\N") + "\n"
        open(os.path.join(out_dir, "_sb.ass"), "w", encoding="utf-8").write(ass)
        if src["kind"] == "template":
            got = problem_source(src, src["span"], log, generate=False)      # 콘티는 과금 호출을 하지 않는다
            at = src["offset"] + beat["duration_sec"] * 0.75
            if got["kind"] == "clip":
                clip_len = _duration(got["path"])
                inp = ["-ss", f"{min(clip_len - 0.1, at * _clip_speed(clip_len, src['span'])):.2f}", "-i", got["path"]]
                pre = f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H}"
            elif got["kind"] == "still":
                inp = ["-i", got["path"]]
                pre = f"scale={W}:{H}:flags=lanczos"
            else:
                spec = TEMPLATES[src["template"]]
                frame_no = min(spec["frames"], int(at * FPS) + 1)
                inp = ["-i", os.path.join(got["dir"], f"p_{frame_no:04d}.jpg")]
                pre = f"scale={W}:{H}:flags=lanczos"
        elif src["kind"] == "footage":
            inp = ["-ss", f"{src['start'] + beat['duration_sec'] * src['speed'] * 0.5:.2f}", "-i", src["path"]]
            pre = f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H}"
        else:
            inp = ["-f", "lavfi", "-i", f"color=c=0x1f3d30:s={W}x{H}"]
            pre = "null"
        _run([ffmpeg, "-v", "error", "-y", *inp, "-vf", f"{pre},ass=_sb.ass", "-frames:v", "1", name], cwd=out_dir)
        frames.append({"beat_order": beat["order"], "image_url": os.path.relpath(os.path.join(out_dir, name)).replace("\\", "/"),
                       "caption": beat["caption"].replace("\n", " ")})
    os.remove(os.path.join(out_dir, "_sb.ass"))
    return frames


def _wrap(text: str, width: int) -> list[str]:
    """width 자 안팎으로 줄을 나누되, 마지막 줄에 한 단어만 남지 않게 줄 길이를 고르게 맞춘다."""
    width = max(4, -(-len(text) // max(1, -(-len(text) // width))) + 1)
    lines, cur = [], ""
    for word in text.split():
        if cur and len(cur) + 1 + len(word) > width:
            lines.append(cur)
            cur = word
        else:
            cur = (cur + " " + word).strip()
    return lines + ([cur] if cur else [])


def _quote_card(caption: str, start: float, end: float) -> str:
    """자막에 “따옴표 인용”이 있으면 화면 위쪽에 후기 카드를 띄운다. 따옴표 앞 문구가 카드 머리글이 된다."""
    flat = caption.replace("\n", " ")
    if "“" not in flat or "”" not in flat:
        return ""
    label = flat.split("“")[0].strip() or "실제 구매 후기"
    lines = _wrap(flat.split("“")[1].split("”")[0].strip(), 15)
    lines[0] = "“" + lines[0]
    return _card(label, lines, start, end, closing="”")


def _card(label: str, lines: list[str], start: float, end: float, closing: str = "") -> str:
    """화면 위쪽의 흰 카드: 작은 머리글 + 본문 몇 줄."""
    x, y, w, h, r = 90, 400, W - 180, 150 + 76 * len(lines), 36
    box = (f"m {r} 0 l {w - r} 0 b {w} 0 {w} 0 {w} {r} l {w} {h - r} b {w} {h} {w} {h} {w - r} {h} "
           f"l {r} {h} b 0 {h} 0 {h} 0 {h - r} l 0 {r} b 0 0 0 0 {r} 0")
    t = f"{_ts(start)},{_ts(end)}"
    fad = "\\fad(160,140)"
    out = f"Dialogue: 0,{t},Card,,0,0,0,,{{\\an7\\pos({x},{y}){fad}\\p1\\1c&HFFFFFF&\\1a&H12&\\shad10\\4c&H000000&\\4a&HB0&}}{box}{{\\p0}}\n"
    out += f"Dialogue: 1,{t},CardLabel,,0,0,0,,{{\\an7\\pos({x + 48},{y + 40}){fad}}}{label}\n"
    out += f"Dialogue: 1,{t},Card,,0,0,0,,{{\\an7\\pos({x + 48},{y + 100}){fad}}}" + "\\N".join(lines) + closing + "\n"
    return out


def _caption_chunks(words: list[tuple], start: float, end: float, t0: float, tempo: float, lead: float) -> list[tuple[float, float, str]]:
    """음성 타임스탬프에 맞춰 2어절 안팎으로 끊은 화면 자막."""
    at = lambda t: start + lead + (t - t0) / tempo
    out, cur = [], []
    for k, (w, s, e) in enumerate(words):
        if cur and (len(cur) >= 2 or sum(len(x[0]) for x in cur) + len(w) > 9):
            out.append((at(cur[0][1]), at(s), " ".join(x[0] for x in cur)))
            cur = []
        cur.append((w, s, e))
        if w[-1] in ",.?!":
            nxt = words[k + 1][1] if k + 1 < len(words) else e + 0.45
            out.append((at(cur[0][1]), at(nxt), " ".join(x[0] for x in cur)))
            cur = []
    if cur:
        out.append((at(cur[0][1]), end, " ".join(x[0] for x in cur)))
    if out:
        out[-1] = (out[-1][0], min(max(out[-1][1], out[-1][0] + 0.4), end - 0.03), out[-1][2])
    return out


def _music(t1: float) -> str:
    """배경음(합성). 문제 장면에서는 낮게 깔리는 긴장음과 초침 소리, 해결부터는 104BPM 의 밝은 리듬.

    저작권이 걸린 음원을 쓰지 않으려고 ffmpeg 수식으로 만든다. u 는 해결 구간이 시작된 뒤의 시간이다.
    """
    b = 60 / 104
    u = f"(t-{t1:.3f})"
    tension = ("0.15*sin(2*PI*55*t)*(0.7+0.3*sin(2*PI*0.5*t))+0.06*sin(2*PI*58.27*t)"
               "+0.09*sin(2*PI*1400*t)*exp(-50*mod(t,0.5))")
    notes = (523.25, 659.25, 783.99, 880.0)                                   # 도 미 솔 라
    pluck = "+".join(f"eq(mod(floor({u}/{b:.4f}),4),{k})*(sin(2*PI*{f}*{u})+0.3*sin(2*PI*{f * 2}*{u}))" for k, f in enumerate(notes))
    groove = (f"0.50*sin(2*PI*(48+70*exp(-30*mod({u},{b:.4f})))*mod({u},{b:.4f}))*exp(-8*mod({u},{b:.4f}))"
              f"+0.06*(random(0)*2-1)*exp(-55*mod({u}+{b / 2:.4f},{b:.4f}))"
              f"+0.11*({pluck})*exp(-7*mod({u},{b / 2:.4f}))"
              f"+0.16*sin(2*PI*65.41*{u})*exp(-2.5*mod({u},{b * 2:.4f}))")
    return (f"aevalsrc='lt(t,{t1:.3f})*({tension})*min(1,({t1:.3f}-t)/0.25)+gte(t,{t1:.3f})*({groove})':s=48000:d=60,"
            "lowpass=f=7000,aecho=0.8:0.5:70:0.2,volume=0.42")


def render_hook(scenario: dict, assets: dict, out_dir: str, *, tts: dict | None = None,
                log: Callable[[str], None] = print, product_name: str | None = None) -> dict:
    """선택된 시나리오로 hook.mp4 · tts.mp3 · hook.srt · scenario.json · storyboard_NN.png 를 out_dir 에 만든다."""
    tts = tts or {"enabled": True}
    ffmpeg = _tool("ffmpeg", "FFMPEG_BIN")
    out_dir = os.path.abspath(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    work = os.path.join(out_dir, "_work")
    os.makedirs(work, exist_ok=True)
    beats = scenario["beats"]
    starts = _starts(beats)
    total = sum(b["duration_sec"] for b in beats)
    plan = plan_sources(scenario, assets)

    # 1) 화면
    inputs: list[str] = []
    filters: list[str] = []
    for i, (beat, src) in enumerate(zip(beats, plan)):
        _segment(i, beat, src, inputs, filters, log)
    n_video = len(beats)

    # 2) 음성 + 화면 자막
    lead = 0.12
    use_tts = bool(tts.get("enabled", True))
    ass = _ass_head() + f"Dialogue: 2,{_ts(0)},{_ts(total)},Badge,,0,0,0,,{{\\pos(64,186)}}AI 연출 포함\n"
    pov = (scenario.get("ad_spec") or {}).get("pov_label")
    if pov and plan[0]["kind"] == "template":
        ass += f"Dialogue: 1,{_ts(0)},{_ts(plan[0]['span'] - 0.05)},Pov,,0,0,0,,{{\\pos({W // 2},340)}}*{pov}*\n"
    pop = "\\fscx84\\fscy84\\t(0,110,\\fscx100\\fscy100)"
    vo_inputs: list[str] = []
    vo_filters: list[str] = []
    first = True
    for i, (beat, s) in enumerate(zip(beats, starts)):
        e = s + beat["duration_sec"]
        chunks = [(s, e - 0.03, beat["caption"].replace("\n", "\\N"))]
        if use_tts and beat["narration"].strip():
            mp3 = os.path.join(work, f"n{beat['order']}.mp3")
            words = tts_mod.synthesize(beat["narration"], mp3, tts.get("voice"))
            if words:
                t0, t1 = max(0.0, words[0][1] - 0.03), words[-1][2] + 0.10
                tempo = max(1.0, (t1 - t0) / (beat["duration_sec"] - 0.30))
                if tempo > 1.25:
                    log(f"  장면 {beat['order']}: 나레이션이 길어 {tempo:.2f}배속으로 맞춥니다. 문장을 줄이는 편이 좋습니다.")
                k = len(vo_inputs) // 2
                vo_inputs += ["-i", mp3]
                vo_filters.append(f"[{k}:a]atrim={t0:.3f}:{t1:.3f},asetpts=PTS-STARTPTS,atempo={min(tempo, 2.0):.3f},"
                                  f"aresample=48000,adelay={int((s + lead) * 1000)}:all=1[v{k}]")
                chunks = _caption_chunks(words, s, e, t0, tempo, lead)
        ass += _quote_card(beat["caption"], s + 0.25, e - 0.05)
        if product_name and "CTA" in beat["role"].upper():                 # 마무리 카드: 제품명과 댓글 유도
            ass += _card("댓글로 알려 주세요", _wrap(product_name, 15), s + 0.2, e)
        for n_chunk, (a, b_, text) in enumerate(chunks):
            a = 0.0 if first else a            # 0프레임부터 문제 상황 자막이 보이게
            gold = "\\1c&H47E0FF&" if len(chunks) > 1 and n_chunk == len(chunks) - 1 else ""      # 장면의 마지막 말을 강조
            ass += f"Dialogue: 0,{_ts(a)},{_ts(b_)},Big,,0,0,0,,{{\\pos({W // 2},1340){gold}{'' if first else pop}}}{text}\n"
            first = False
    open(os.path.join(work, "c.ass"), "w", encoding="utf-8").write(ass)

    vo_wav = os.path.join(work, "vo.wav")
    if vo_inputs:
        n = len(vo_inputs) // 2
        graph = ";".join(vo_filters) + ";" + "".join(f"[v{k}]" for k in range(n)) + \
            f"amix=inputs={n}:normalize=0,apad=whole_dur={total},atrim=0:{total},volume=1.5,alimiter=limit=0.85[a]"
        _run([ffmpeg, "-v", "error", "-y", *vo_inputs, "-filter_complex", graph, "-map", "[a]", vo_wav])
    else:
        _run([ffmpeg, "-v", "error", "-y", "-f", "lavfi", "-t", f"{total}", "-i", "anullsrc=r=48000:cl=mono", vo_wav])
    _run([ffmpeg, "-v", "error", "-y", "-i", vo_wav, "-c:a", "libmp3lame", "-b:a", "160k", os.path.join(out_dir, "tts.mp3")])

    # 3) 배경음(합성): 문제 장면이 끝난 뒤 잔잔한 패드, 쓰러지는 순간 쿵, 전환 휙, CTA 차임
    t1 = plan[0]["span"] if plan[0]["kind"] == "template" else beats[0]["duration_sec"]      # 문제 장면이 끝나는 시각
    cta_at = next((s for b, s in zip(beats, starts) if "CTA" in b["role"].upper()), max(0.0, total - 4))
    resolved = plan[0].get("resolved") or {}
    # 쿵 소리는 쓰러지는 시점을 아는 Blender 렌더에만 넣는다. Veo 영상은 그 시점이 매번 다르다.
    thud = TEMPLATES[plan[0]["template"]]["impact_sec"] if resolved.get("kind") == "frames" else None      # 충격이 없는 템플릿은 None
    sfx = [_music(t1),
           "aevalsrc='0.9*sin(2*PI*(110-70*t)*t)*exp(-9*t)+0.25*(random(0)-0.5)*exp(-30*t)':s=48000:d=0.6",
           "anoisesrc=d=0.8:c=pink:a=0.6:r=48000,bandpass=f=1600:w=1400,afade=t=in:d=0.5,afade=t=out:st=0.55:d=0.25",
           "aevalsrc='0.20*sin(2*PI*1174.66*t)*exp(-3*t)+0.12*sin(2*PI*1760*t)*exp(-3.5*t)+0.07*sin(2*PI*2349.3*t)*exp(-4*t)':s=48000:d=2.5"]
    extra = [(SFX[kind], at) for kind, at in (TEMPLATES[plan[0]["template"]].get("sfx") or [])
             if resolved.get("kind") == "frames" and at < t1] if plan[0]["kind"] == "template" else []
    sfx += [x for x, _ in extra]
    extra_graph = "".join(f"[{4 + i}:a]adelay={int(at * 1000)}:all=1[x{i}];" for i, (_, at) in enumerate(extra))
    extra_pads = "".join(f"[x{i}]" for i in range(len(extra)))
    bed = os.path.join(work, "bed.wav")
    _run([ffmpeg, "-v", "error", "-y", *sum((["-f", "lavfi", "-i", x] for x in sfx), []), "-filter_complex",
          f"[1:a]adelay={int((thud or 0) * 1000)}:all=1,volume={0.8 if thud is not None else 0}[th];"
          f"[2:a]adelay={int(max(0.0, t1 - 0.5) * 1000)}:all=1,volume=0.45[w];[3:a]adelay={int(cta_at * 1000)}:all=1[c];{extra_graph}"
          f"[0:a][th][w][c]{extra_pads}amix=inputs={4 + len(extra)}:normalize=0,atrim=0:{total}[a]", "-map", "[a]", "-ar", "48000", bed])

    # 생성 영상에 소리가 들어 있으면(MiniMax, C_MINIMAX_AUDIO=1) 문제 장면 구간의 배경음에 섞는다.
    if resolved.get("kind") == "clip" and resolved.get("audio") and _has_audio(resolved["path"]):
        speed = _clip_speed(_duration(resolved["path"]), plan[0]["span"])
        mixed = os.path.join(work, "bed_clip.wav")
        _run([ffmpeg, "-v", "error", "-y", "-i", bed, "-i", resolved["path"], "-filter_complex",
              f"[1:a]atempo={speed:.3f},atrim=0:{t1:.2f},afade=t=out:st={max(0.0, t1 - 0.3):.2f}:d=0.3,aresample=48000,volume=0.9[c];"
              f"[0:a][c]amix=inputs=2:normalize=0,atrim=0:{total}[a]", "-map", "[a]", "-ar", "48000", mixed])
        bed = mixed

    # 4) 합치기
    flash = f"eq=brightness='0.45*max(0,1-abs(t-{t1})/0.18)':eval=frame," if plan[0]["kind"] == "template" else ""
    n_in = len(inputs_index(inputs))            # 화면 입력 수. 컷 편집을 하면 장면 수보다 많다. 음성·배경음 입력은 그 뒤에 온다.
    graph = ";".join(filters) + ";" + "".join(f"[s{i}]" for i in range(n_video)) + \
        f"concat=n={n_video}:v=1:a=0,{flash}vignette=PI/6,ass=c.ass,fade=t=out:st={total - 0.4}:d=0.4[v];" \
        f"[{n_in}:a]asplit=2[vo1][vo2];" \
        f"[{n_in + 1}:a][vo1]sidechaincompress=threshold=0.02:ratio=5:attack=12:release=260[bd];" \
        f"[vo2][bd]amix=inputs=2:normalize=0,atrim=0:{total},afade=t=out:st={total - 0.6}:d=0.6[a]"      # 말할 때 배경음을 낮춘다
    hook = os.path.join(out_dir, "hook.mp4")
    _run([ffmpeg, "-v", "error", "-y", *inputs, "-i", vo_wav, "-i", bed, "-filter_complex", graph, "-map", "[v]", "-map", "[a]",
          "-r", str(FPS), "-c:v", "libx264", "-crf", "18", "-preset", "slow", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
          "-ac", "2", "-t", f"{total}", "-movflags", "+faststart", hook], cwd=work)

    # 5) 자막 파일, 시나리오, 콘티
    write_srt(os.path.join(out_dir, "hook.srt"), beats)
    json.dump(scenario, open(os.path.join(out_dir, "scenario.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    frames = storyboard(scenario, assets, out_dir, log)
    shutil.rmtree(work, ignore_errors=True)
    rel = lambda p: os.path.relpath(p).replace("\\", "/")
    return {
        "hook_video": rel(hook),
        "tts_audio": rel(os.path.join(out_dir, "tts.mp3")),
        "subtitles_srt": rel(os.path.join(out_dir, "hook.srt")),
        "scenario_json": rel(os.path.join(out_dir, "scenario.json")),
        "storyboard_images": [f["image_url"] for f in frames],
        "problem_engine": resolved.get("engine"),      # 문제 장면을 만든 쪽: "veo:<모델>" · "blender" · None(생성 장면 없음)
    }
