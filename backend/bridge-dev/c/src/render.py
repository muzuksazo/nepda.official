"""FR-004 콘티 이미지와 FR-005 훅 영상(+TTS) 만들기.

장면별 화면 소재:
  - 문제 장면(첫 장면): assets.problem_template 이 있으면 생성 영상, 없으면 다음 소재로.
      engine "veo"     Blender 가 렌더한 첫 프레임 → Google Veo(Vertex AI)가 영상으로 생성 (veo.py)
      engine "blender" Blender 물리 시뮬레이션을 전 프레임 렌더
      engine "auto"    GOOGLE_CLOUD_PROJECT 가 있으면 veo, 없거나 실패하면 blender (기본)
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

from . import tts as tts_mod
from . import veo
from .assets import assets_dir

FPS = 24
W, H = 1080, 1920
HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATES = {
    "spill_diffuser": {"script": os.path.join(HERE, "blender_scene.py"), "frames": 84, "impact_sec": 1.25},
    "evaporate_diffuser": {"script": os.path.join(HERE, "blender_scene_evaporate.py"), "frames": 96, "impact_sec": None},
    "drain_smell": {"script": os.path.join(HERE, "blender_scene_drain.py"), "frames": 240, "impact_sec": None},
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
    out = os.path.join(assets_dir(), "cache", template)
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
    full = os.path.join(assets_dir(), "cache", template, "p_0001.jpg")
    if os.path.exists(full) and os.path.getsize(full) > 10000:
        return full
    out = os.path.join(assets_dir(), "cache", template + "_first")
    path = os.path.join(out, "p_0001.jpg")
    if not (os.path.exists(path) and os.path.getsize(path) > 10000):
        log(f"Blender 로 문제 장면 '{template}' 의 첫 프레임 렌더 중…")
        shutil.rmtree(out, ignore_errors=True)
        os.makedirs(out, exist_ok=True)
        _run([_blender(), "-b", "-P", TEMPLATES[template]["script"], "--", out, assets_dir(), os.environ.get("C_RENDER_PERCENT", "100"), "1", "1"])
        if not os.path.exists(path):
            raise RenderError("문제 장면 첫 프레임 렌더에 실패했습니다.")
    return path


def problem_engine(assets: dict) -> str:
    engine = str(assets.get("problem_engine") or os.environ.get("C_PROBLEM_ENGINE") or "auto").strip().lower()
    if engine not in ("auto", "veo", "blender"):
        raise RenderError(f"problem_engine 은 auto · veo · blender 중 하나여야 합니다: {engine}")
    return engine


def problem_source(src: dict, seconds: float, log: Callable[[str], None] = print, *, generate: bool = True) -> dict:
    """문제 장면에 실제로 쓸 소재를 정한다 → {"kind": "clip", "path"} (Veo) 또는 {"kind": "frames", "dir"} (Blender).

    generate=False 면 과금되는 Veo 호출을 하지 않고, 이미 만든 영상이 있을 때만 그것을 쓴다 (콘티용).
    """
    template, engine = src["template"], src["engine"]
    if engine == "veo" or (engine == "auto" and veo.configured()):
        cache = os.path.join(assets_dir(), "cache", "veo")
        try:
            image = first_frame(template, log)
            clip = veo.generate(template, image, cache, seconds, log=log) if generate else veo.cached(cache, template, image, seconds)
            if clip:
                return {"kind": "clip", "path": clip, "engine": f"veo:{veo.model()}"}
        except veo.VeoError as e:
            if engine == "veo":
                raise RenderError(str(e)) from e
            log(f"  Veo 를 쓰지 못해 Blender 렌더로 대신합니다: {e}")
    return {"kind": "frames", "dir": problem_frames(template, log), "engine": "blender"}


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
    for i, b in enumerate(beats):
        if i < lead:
            plan.append({"kind": "template", "template": template, "engine": engine, "offset": offset, "span": span})
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
    return plan


def _segment(index: int, beat: dict, src: dict, inputs: list[str], filters: list[str], log) -> None:
    n = int(round(beat["duration_sec"] * FPS))
    pad = f"tpad=stop_mode=clone:stop_duration={beat['duration_sec'] + 1:.2f},trim=end_frame={n},setpts=PTS-STARTPTS,setsar=1,format=yuv420p"
    k = len(inputs_index(inputs))
    if src["kind"] == "template":
        got = problem_source(src, src["span"], log)
        src["resolved"] = got
        if got["kind"] == "clip":
            # Veo 는 4·6·8초로만 나온다. 문제 장면 전체 길이에 맞춰 속도를 조절한다 (0.75~1.6배속, 넘치면 뒤를 자르고 모자라면 마지막 화면 정지).
            speed = max(0.75, min(1.6, _duration(got["path"]) / src["span"]))
            inputs += ["-ss", f"{src['offset'] * speed:.3f}", "-i", got["path"]]
            filters.append(f"[{k}:v]setpts=(PTS-STARTPTS)/{speed:.3f},fps={FPS},"
                           f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H},{pad}[s{index}]")
        else:
            start = min(TEMPLATES[src["template"]]["frames"], 1 + int(round(src["offset"] * FPS)))
            inputs += ["-framerate", str(FPS), "-start_number", str(start), "-i", os.path.join(got["dir"], "p_%04d.jpg")]
            filters.append(f"[{k}:v]scale={W}:{H}:flags=lanczos,eq=saturation=1.1:brightness=0.02,noise=alls=3:allf=t,{pad}[s{index}]")
    elif src["kind"] == "footage":
        inputs += ["-ss", str(src["start"]), "-t", f"{beat['duration_sec'] + 1:.2f}", "-i", src["path"]]
        zoom = f"crop=iw/{src['zoom']}:ih/{src['zoom']}," if src["zoom"] != 1.0 else ""
        filters.append(f"[{k}:v]setpts=(PTS-STARTPTS)/{src['speed']:.3f},fps={FPS},{zoom}"
                       f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H},{pad}[s{index}]")
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
                inp = ["-ss", f"{min(clip_len - 0.1, at * max(0.75, min(1.6, clip_len / src['span']))):.2f}", "-i", got["path"]]
                pre = f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H}"
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


def render_hook(scenario: dict, assets: dict, out_dir: str, *, tts: dict | None = None,
                log: Callable[[str], None] = print) -> dict:
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
        for a, b_, text in chunks:
            a = 0.0 if first else a            # 0프레임부터 문제 상황 자막이 보이게
            ass += f"Dialogue: 0,{_ts(a)},{_ts(b_)},Big,,0,0,0,,{{\\pos({W // 2},1340){'' if first else pop}}}{text}\n"
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
    pad = ("aevalsrc='0.10*sin(2*PI*146.83*t)+0.07*sin(2*PI*220*t)+0.05*sin(2*PI*277.18*t)"
           "+0.045*sin(2*PI*329.63*t)*(0.6+0.4*sin(2*PI*0.11*t))+0.03*sin(2*PI*440*t)*(0.5+0.5*sin(2*PI*0.07*t+1))':s=48000:d=40,"
           f"aecho=0.8:0.7:90|180:0.35|0.25,lowpass=f=2200,afade=t=in:st={max(0.0, t1 - 0.2):.2f}:d=1.2,volume=0.26")
    sfx = [pad,
           "aevalsrc='0.9*sin(2*PI*(110-70*t)*t)*exp(-9*t)+0.25*(random(0)-0.5)*exp(-30*t)':s=48000:d=0.6",
           "anoisesrc=d=0.8:c=pink:a=0.6:r=48000,bandpass=f=1600:w=1400,afade=t=in:d=0.5,afade=t=out:st=0.55:d=0.25",
           "aevalsrc='0.20*sin(2*PI*1174.66*t)*exp(-3*t)+0.12*sin(2*PI*1760*t)*exp(-3.5*t)+0.07*sin(2*PI*2349.3*t)*exp(-4*t)':s=48000:d=2.5"]
    bed = os.path.join(work, "bed.wav")
    _run([ffmpeg, "-v", "error", "-y", *sum((["-f", "lavfi", "-i", x] for x in sfx), []), "-filter_complex",
          f"[1:a]adelay={int((thud or 0) * 1000)}:all=1,volume={0.8 if thud is not None else 0}[th];"
          f"[2:a]adelay={int(max(0.0, t1 - 0.5) * 1000)}:all=1,volume=0.45[w];[3:a]adelay={int(cta_at * 1000)}:all=1[c];"
          f"[0:a][th][w][c]amix=inputs=4:normalize=0,atrim=0:{total}[a]", "-map", "[a]", "-ar", "48000", bed])

    # 4) 합치기
    flash = f"eq=brightness='0.45*max(0,1-abs(t-{t1})/0.18)':eval=frame," if plan[0]["kind"] == "template" else ""
    graph = ";".join(filters) + ";" + "".join(f"[s{i}]" for i in range(n_video)) + \
        f"concat=n={n_video}:v=1:a=0,{flash}ass=c.ass,fade=t=out:st={total - 0.4}:d=0.4[v];" \
        f"[{n_video}:a][{n_video + 1}:a]amix=inputs=2:normalize=0,atrim=0:{total},afade=t=out:st={total - 0.6}:d=0.6[a]"
    hook = os.path.join(out_dir, "hook.mp4")
    _run([ffmpeg, "-v", "error", "-y", *inputs, "-i", vo_wav, "-i", bed, "-filter_complex", graph, "-map", "[v]", "-map", "[a]",
          "-r", str(FPS), "-c:v", "libx264", "-crf", "21", "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
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
