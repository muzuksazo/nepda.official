"""공통 훅 렌더: 시나리오 → (영상 모델 클립 + 나레이션 + 자막) → 계약 규격 파일.

결과 (`OUTPUT_DIR/{project_id}/{hook_id}/`, WORKER_CONTRACT.md 4절):
    hook.mp4  1080x1920, 30fps, H.264, 소리 -14 LUFS
    tts.mp3   나레이션 트랙 (나레이션이 있을 때만)
    hook.srt  자막
    scenario.json  채택된 시나리오 원문
    storyboard_NN.png  장면별 대표 화면

어느 유형(A·B·C) 시나리오든 같은 길로 만든다. 유형별 차이는 prompts.py 의 화면 톤과 제품 장면 판정뿐이다.
"""

from __future__ import annotations

import json
import logging
import math
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

from .captions import build_srt
from .media import (
    AUDIO_ENCODE_ARGS,
    AUDIO_RATE,
    TARGET_LUFS,
    VIDEO_ENCODE_ARGS,
    MediaError,
    MediaTools,
    fill_filter,
    find_tools,
    measure_lufs,
    probe,
    run_ffmpeg,
)
from .prompts import beat_prompt, ordered_beats, product_beat_orders, reference_image_prompt

logger = logging.getLogger("hookpipe.render")

MIN_CLIP_SEC, MAX_CLIP_SEC = 3, 15
NARRATION_TAIL_SEC = 0.15  # 나레이션이 끝난 뒤 다음 장면으로 넘어가기 전 숨 고르는 시간
NORMAL_TEMPO_MAX = 1.3
HARD_TEMPO_MAX = 1.6


class HookRenderError(RuntimeError):
    """훅을 만들 수 없을 때 (입력 문제, 과금 상한, 생성 실패)."""


@dataclass
class BeatPlan:
    order: int
    role: str
    caption: str
    narration: str
    scenario_sec: float
    duration: float = 0.0  # 실제 화면 길이 (나레이션에 맞춰 늘어날 수 있다)
    start: float = 0.0
    clip_sec: int = 0  # 영상 모델에 요청하는 길이
    shows_product: bool = False
    narration_path: Optional[Path] = None
    narration_sec: float = 0.0
    tempo: float = 1.0
    clip_path: Optional[Path] = None
    prompt: str = ""


@dataclass
class HookRenderResult:
    out_dir: Path
    files: Dict[str, Any]
    duration_sec: float
    lufs: Optional[float]
    captions_burned: bool
    beats: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def write_scenario_and_srt(scenario: Dict[str, Any], out_dir: Path) -> Dict[str, Any]:
    """과금 호출 없이 만들 수 있는 두 파일만 쓴다 (dry_run 모드에서도 사용)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "scenario.json").write_text(json.dumps(scenario, ensure_ascii=False, indent=2), encoding="utf-8")
    cues = []
    cursor = 0.0
    for beat in ordered_beats(scenario):
        dur = float(beat.get("duration_sec") or 0.0)
        text = str(beat.get("caption") or beat.get("narration") or "").strip()
        cues.append((cursor, cursor + dur, text))
        cursor += dur
    (out_dir / "hook.srt").write_text(build_srt(cues), encoding="utf-8")
    return {"scenario_json": "scenario.json", "subtitles_srt": "hook.srt"}


def extract_reference_frames(
    videos: Sequence[str | Path],
    out_dir: Path,
    tools: MediaTools,
    *,
    max_frames: int = 2,
) -> List[Path]:
    """촬영 영상에서 제품 참고 이미지를 뽑는다 (제품 사진이 없을 때 쓰는 기본 방법)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    frames: List[Path] = []
    usable = [Path(v) for v in videos if Path(v).is_file()]
    if not usable:
        return frames
    # 영상이 하나면 그 안의 여러 지점, 여러 개면 영상마다 가운데 근처 한 지점
    if len(usable) == 1:
        picks = [(usable[0], spot) for spot in (0.3, 0.65, 0.5, 0.85)]
    else:
        picks = [(video, 0.4) for video in usable]
    for video, spot in picks:
        if len(frames) >= max_frames:
            break
        try:
            info = probe(tools, video)
        except MediaError:
            continue
        if not info.has_video or info.duration <= 0:
            continue
        target = out_dir / f"product_ref_{len(frames) + 1:02d}.jpg"
        try:
            run_ffmpeg(
                tools,
                ["-ss", f"{info.duration * spot:.3f}", "-i", str(video), "-frames:v", "1",
                 "-vf", "scale=-2:1280", "-q:v", "3", str(target)],
                timeout=120.0,
            )
        except MediaError as exc:
            logger.warning("참고 이미지 추출 실패 (%s): %s", video.name, exc)
            continue
        if target.is_file() and target.stat().st_size > 0:
            frames.append(target)
    return frames


def _plan_beats(scenario: Dict[str, Any], max_hook_sec: float) -> List[BeatPlan]:
    beats = ordered_beats(scenario)
    if not beats:
        raise HookRenderError("시나리오에 장면(beats)이 없습니다.")
    product_orders = set(product_beat_orders(scenario))
    plans: List[BeatPlan] = []
    for beat in beats:
        dur = float(beat.get("duration_sec") or 0.0)
        if dur <= 0:
            raise HookRenderError(f"장면 {beat.get('order')} 의 길이가 0초 이하입니다.")
        order = int(beat.get("order") or len(plans) + 1)
        plans.append(
            BeatPlan(
                order=order,
                role=str(beat.get("role") or ""),
                caption=str(beat.get("caption") or "").strip(),
                narration=str(beat.get("narration") or "").strip(),
                scenario_sec=dur,
                duration=dur,
                shows_product=order in product_orders,
            )
        )
    total = sum(p.scenario_sec for p in plans)
    if total > max_hook_sec + 0.05:
        raise HookRenderError(f"훅 길이 {total:.1f}초가 상한 {max_hook_sec:.0f}초를 넘습니다.")
    return plans


def _fit_timing(plans: List[BeatPlan], max_hook_sec: float, warnings: List[str]) -> None:
    """나레이션이 장면보다 길면 조금 빠르게 읽히고(최대 1.3배), 그래도 길면 장면을 늘린다.

    전체가 상한을 넘으면 1.6배까지 올리고, 그래도 넘으면 장면 길이를 시나리오 값으로 되돌려 나레이션 끝을 자른다.
    """

    def apply(tempo_max: float) -> float:
        for plan in plans:
            plan.duration, plan.tempo = plan.scenario_sec, 1.0
            if plan.narration_sec <= 0:
                continue
            room = max(0.2, plan.scenario_sec - NARRATION_TAIL_SEC)
            plan.tempo = min(tempo_max, max(1.0, plan.narration_sec / room))
            plan.duration = max(plan.scenario_sec, plan.narration_sec / plan.tempo + NARRATION_TAIL_SEC)
        return sum(p.duration for p in plans)

    total = apply(NORMAL_TEMPO_MAX)
    if total > max_hook_sec + 0.05:
        total = apply(HARD_TEMPO_MAX)
    if total > max_hook_sec + 0.05:
        warnings.append("나레이션이 길어 일부 장면에서 끝부분이 잘릴 수 있습니다.")
        for plan in plans:
            plan.duration = plan.scenario_sec
    cursor = 0.0
    for plan in plans:
        plan.duration = round(plan.duration, 3)
        plan.start = round(cursor, 3)
        cursor += plan.duration
        plan.clip_sec = max(MIN_CLIP_SEC, min(MAX_CLIP_SEC, math.ceil(plan.duration - 1e-6)))


def _subtitle_style() -> str:
    # SRT 는 384x288 기준 좌표로 변환된다. 8.8 ≈ 1920 높이에서 59px: 한글 22자 한 줄(약 970px)이 1080 폭에 들어가는 크기.
    return (
        "FontName=Noto Sans CJK KR,FontSize=8.8,Bold=1,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
        "BorderStyle=1,Outline=0.9,Shadow=0,Alignment=2,MarginL=4,MarginR=4,MarginV=42"
    )


def _assemble(
    plans: List[BeatPlan],
    out_dir: Path,
    tools: MediaTools,
    *,
    burn_captions: bool,
) -> bool:
    """클립과 나레이션을 hook.mp4 로 합친다. 자막을 구웠으면 True."""
    total = sum(p.duration for p in plans)
    args: List[str] = []
    filters: List[str] = []
    for index, plan in enumerate(plans):
        args += ["-i", str(plan.clip_path)]
        info = probe(tools, plan.clip_path)  # type: ignore[arg-type]
        chain = f"[{index}:v]"
        short = plan.duration - info.duration
        steps: List[str] = []
        if short > 0.02:
            if tools.has_filter("tpad"):
                steps.append(f"tpad=stop_mode=clone:stop_duration={short + 0.1:.3f}")
            else:
                steps.append(f"setpts={plan.duration / max(info.duration, 0.1):.4f}*PTS")
        steps.append(f"trim=0:{plan.duration:.3f}")
        steps.append("setpts=PTS-STARTPTS")
        filters.append(f"{chain}{','.join(steps)}[t{index}]")
        filters.append(fill_filter(f"t{index}", f"v{index}"))
    concat_in = "".join(f"[v{i}]" for i in range(len(plans)))
    filters.append(f"{concat_in}concat=n={len(plans)}:v=1:a=0[vcat]")

    burned = False
    video_label = "vcat"
    if burn_captions and (out_dir / "hook.srt").stat().st_size > 0:
        if tools.has_filter("subtitles"):
            # cwd 를 out_dir 로 두고 파일 이름만 넘겨서 윈도우 경로(C:\) 이스케이프 문제를 피한다
            filters.append(f"[vcat]subtitles=hook.srt:force_style='{_subtitle_style()}'[vsub]")
            video_label = "vsub"
            burned = True
        else:
            logger.warning("이 ffmpeg 에는 subtitles 필터가 없어 자막을 굽지 않습니다 (hook.srt 는 그대로 저장).")

    narrated = [p for p in plans if p.narration_path is not None]
    base_index = len(plans)
    args += ["-f", "lavfi", "-t", f"{total:.3f}", "-i", f"anullsrc=r={AUDIO_RATE}:cl=stereo"]
    mix_inputs = [f"[{base_index}:a]"]
    for offset, plan in enumerate(narrated):
        input_index = base_index + 1 + offset
        args += ["-i", str(plan.narration_path)]
        steps = []
        if plan.tempo > 1.001:
            steps.append(f"atempo={plan.tempo:.4f}")
        steps.append(f"atrim=0:{plan.duration:.3f}")
        steps.append(f"aresample={AUDIO_RATE}")
        steps.append("aformat=channel_layouts=stereo")
        steps.append(f"adelay={int(round(plan.start * 1000))}:all=1")
        filters.append(f"[{input_index}:a]{','.join(steps)}[n{offset}]")
        mix_inputs.append(f"[n{offset}]")
    if narrated:
        filters.append(f"{''.join(mix_inputs)}amix=inputs={len(mix_inputs)}:duration=first:normalize=0[narr]")
        filters.append("[narr]asplit=2[narr_a][narr_b]")
        filters.append(f"[narr_a]loudnorm=I={TARGET_LUFS}:TP=-1.5:LRA=11,aresample={AUDIO_RATE}[aout]")
        audio_label = "aout"
    else:
        audio_label = f"{base_index}:a"

    cmd = [*args, "-filter_complex", ";".join(filters), "-map", f"[{video_label}]"]
    cmd += ["-map", f"[{audio_label}]" if narrated else audio_label]
    cmd += [*VIDEO_ENCODE_ARGS, *AUDIO_ENCODE_ARGS, "-t", f"{total:.3f}", "hook.mp4"]
    if narrated:
        mp3_codec = ["-c:a", "libmp3lame", "-q:a", "3"] if tools.has_encoder("libmp3lame") else ["-c:a", "mp3"]
        cmd += ["-map", "[narr_b]", *mp3_codec, "-ar", str(AUDIO_RATE), "-t", f"{total:.3f}", "tts.mp3"]

    def attempt(command: List[str]) -> None:
        run_ffmpeg(tools, command, cwd=out_dir)

    try:
        attempt(cmd)
    except MediaError:
        if not burned:
            raise
        # 글꼴이나 libass 문제로 자막 굽기만 실패하는 경우가 있어, 자막 없이 한 번 더 만든다
        logger.warning("자막을 구운 인코딩이 실패해 자막 없이 다시 만듭니다.")
        retry = list(cmd)
        retry[retry.index("-filter_complex") + 1] = ";".join(f for f in filters if "subtitles=" not in f)
        attempt([("[vcat]" if a == "[vsub]" else a) for a in retry])
        burned = False
    return burned


def _write_storyboards(plans: List[BeatPlan], out_dir: Path, tools: MediaTools) -> List[str]:
    names: List[str] = []
    for plan in plans:
        name = f"storyboard_{plan.order:02d}.png"
        at = plan.start + plan.duration * 0.5
        try:
            run_ffmpeg(tools, ["-ss", f"{at:.3f}", "-i", "hook.mp4", "-frames:v", "1", name], cwd=out_dir, timeout=120.0)
        except MediaError as exc:
            logger.warning("콘티 이미지 %s 추출 실패: %s", name, exc)
            continue
        if (out_dir / name).is_file():
            names.append(name)
    return names


def render_hook(
    scenario: Dict[str, Any],
    product: Dict[str, Any],
    out_dir: str | Path,
    *,
    provider: Any,
    settings: Any,
    tts_enabled: bool = True,
    voice: Optional[str] = None,
    product_refs: Sequence[str | Path] = (),
    tools: Optional[MediaTools] = None,
    progress: Optional[Callable[[str], None]] = None,
) -> HookRenderResult:
    """훅 하나를 만든다. provider 는 `app.genai_provider.GenAIMediaProvider` (또는 같은 모양의 대역)."""
    target = Path(out_dir)
    work = target / "_work"
    work.mkdir(parents=True, exist_ok=True)
    media = tools or find_tools(getattr(settings, "ffmpeg_bin", None), getattr(settings, "ffprobe_bin", None))
    say = progress or (lambda _msg: None)
    warnings: List[str] = []
    max_hook_sec = float(getattr(settings, "hook_max_sec", 20.0))

    plans = _plan_beats(scenario, max_hook_sec)
    (target / "scenario.json").write_text(json.dumps(scenario, ensure_ascii=False, indent=2), encoding="utf-8")

    # 1) 나레이션 먼저 (싸고, 장면 길이를 정하는 데 필요하다)
    if tts_enabled:
        say("TTS")
        for plan in plans:
            if not plan.narration:
                continue
            wav = work / f"narration_{plan.order:02d}.wav"
            provider.generate_tts_beat(plan.narration, wav, voice_name=voice or None)
            info = probe(media, wav)
            if info.duration <= 0:
                raise HookRenderError(f"장면 {plan.order} 나레이션 음성이 비어 있습니다.")
            plan.narration_path, plan.narration_sec = wav, info.duration
    _fit_timing(plans, max_hook_sec, warnings)

    # 2) 과금 방어: 요청할 클립 길이 합이 상한을 넘으면 영상 모델을 부르기 전에 멈춘다
    requested = sum(p.clip_sec for p in plans)
    limit = int(getattr(settings, "hook_max_clip_sec_per_hook", 45))
    if requested > limit:
        raise HookRenderError(
            f"영상 모델에 요청할 클립 길이 합({requested}초)이 상한({limit}초)을 넘습니다. "
            "장면 수나 길이를 줄이거나 HOOK_MAX_CLIP_SEC_PER_HOOK 을 올려 주세요."
        )

    # 3) 참고 이미지: 제품 장면은 촬영본에서 뽑은 컷, 나머지는 톤·주인공 참고 이미지 한 장
    refs = [Path(p) for p in product_refs if Path(p).is_file()]
    style_ref: Optional[Path] = None
    if any(not p.shows_product or not refs for p in plans):
        say("REFERENCE")
        candidate = work / "style_ref.png"
        try:
            provider.generate_reference_image(reference_image_prompt(scenario), candidate, aspect_ratio="9:16")
            if candidate.is_file() and candidate.stat().st_size > 0:
                style_ref = candidate
        except Exception as exc:  # 참고 이미지는 품질 보조라, 실패해도 클립 생성은 계속한다
            warnings.append(f"톤 참고 이미지를 만들지 못해 참고 이미지 없이 진행했습니다: {exc}")

    # 4) 장면 클립
    resolution = str(getattr(settings, "hook_clip_resolution", "720p"))
    for index, plan in enumerate(plans, start=1):
        say(f"CLIP {index}/{len(plans)}")
        use_product_refs = plan.shows_product and bool(refs)
        beat = next(b for b in ordered_beats(scenario) if int(b.get("order") or 0) == plan.order)
        plan.prompt = beat_prompt(
            scenario,
            beat,
            index,
            len(plans),
            product=product,
            shows_product=plan.shows_product,
            has_product_reference=use_product_refs,
            has_style_reference=style_ref is not None,
        )
        clip = work / f"beat_{plan.order:02d}.mp4"
        reference_paths = refs if use_product_refs else ([style_ref] if style_ref else [])
        provider.generate_video_clip(
            plan.prompt,
            clip,
            aspect_ratio="9:16",
            duration_sec=plan.clip_sec,
            resolution=resolution,
            reference_paths=reference_paths,
        )
        info = probe(media, clip)
        if not info.has_video or info.duration <= 0:
            raise HookRenderError(f"장면 {plan.order} 클립에 영상이 없습니다.")
        plan.clip_path = clip

    # 5) 자막 → 조립 → 콘티 이미지
    cues = [(p.start, p.start + p.duration, p.caption or p.narration) for p in plans]
    (target / "hook.srt").write_text(build_srt(cues), encoding="utf-8")
    say("ASSEMBLE")
    burned = _assemble(plans, target, media, burn_captions=bool(getattr(settings, "hook_burn_captions", True)))
    storyboards = _write_storyboards(plans, target, media)

    final = probe(media, target / "hook.mp4")
    has_tts = (target / "tts.mp3").is_file()
    lufs = measure_lufs(media, target / "hook.mp4") if has_tts else None
    beats_meta = [
        {
            "order": p.order,
            "start": p.start,
            "duration": p.duration,
            "clip_sec": p.clip_sec,
            "shows_product": p.shows_product,
            "narration_sec": round(p.narration_sec, 3),
            "tempo": round(p.tempo, 3),
            "prompt": p.prompt,
        }
        for p in plans
    ]
    meta = {
        "scenario_id": scenario.get("scenario_id"),
        "type": scenario.get("type"),
        "video_model": getattr(settings, "video_model", None),
        "tts_model": getattr(settings, "tts_model", None) if has_tts else None,
        "duration_sec": round(final.duration, 3),
        "lufs": lufs,
        "captions_burned": burned,
        "product_refs": [p.name for p in refs],
        "style_ref": bool(style_ref),
        "requested_clip_sec": requested,
        "beats": beats_meta,
        "warnings": warnings,
    }
    (target / "render_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    files: Dict[str, Any] = {
        "hook_video": "hook.mp4",
        "tts_audio": "tts.mp3" if has_tts else None,
        "subtitles_srt": "hook.srt",
        "scenario_json": "scenario.json",
        "storyboard_images": storyboards,
    }
    return HookRenderResult(
        out_dir=target,
        files=files,
        duration_sec=round(final.duration, 3),
        lufs=lufs,
        captions_burned=burned,
        beats=beats_meta,
        warnings=warnings,
    )


def clean_work_dir(out_dir: str | Path) -> None:
    """중간 파일(_work)을 지운다. 다시 만들 때 클립을 재사용하려면 지우지 않는다."""
    shutil.rmtree(Path(out_dir) / "_work", ignore_errors=True)
