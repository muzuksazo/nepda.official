"""본편 붙이기 (FR-010): 훅 영상 뒤에 사용자가 올린 촬영 영상을 이어 붙인다.

1차 범위: 길이 자르기 + 화면 규격 맞추기 + 소리 크기 맞추기. 본편용 나레이션·자막은 만들지 않는다.
어느 유형의 훅이든, 다른 곳에서 만든 hook.mp4 든 그대로 받을 수 있다.
"""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Sequence

from .media import (
    AUDIO_ENCODE_ARGS,
    AUDIO_RATE,
    OUT_FPS,
    OUT_H,
    OUT_W,
    TARGET_LUFS,
    VIDEO_ENCODE_ARGS,
    MediaError,
    MediaTools,
    fill_filter,
    measure_lufs,
    probe,
    run_ffmpeg,
)

logger = logging.getLogger("hookpipe.body")

MIN_SEGMENT_SEC = 1.0
LANDSCAPE_RATIO = 0.92  # 가로/세로 비율이 이보다 크면 가로 영상으로 보고 흐린 배경 위에 얹는다


class BodyAttachError(RuntimeError):
    """본편을 붙일 수 없을 때."""


@dataclass
class BodyAttachResult:
    path: Path
    duration_sec: float
    hook_sec: float
    body_sec: float
    lufs: Optional[float]
    segments: List[dict] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def plan_body_segments(durations: Sequence[float], limit_sec: Optional[float]) -> List[float]:
    """클립마다 쓸 길이. 합이 limit 을 넘으면 각 클립의 앞부분을 같은 비율로 줄인다."""
    usable = [max(0.0, float(d)) for d in durations]
    total = sum(usable)
    if not limit_sec or limit_sec <= 0 or total <= limit_sec:
        return usable
    ratio = limit_sec / total
    return [round(d * ratio, 3) for d in usable]


def _video_chain(index: int, seconds: float, landscape: bool, tools: MediaTools) -> List[str]:
    src = f"[{index}:v]trim=0:{seconds:.3f},setpts=PTS-STARTPTS"
    if landscape and tools.has_filter("overlay") and tools.has_filter("boxblur"):
        return [
            f"{src},split=2[bg{index}][fg{index}]",
            f"[bg{index}]scale={OUT_W}:{OUT_H}:force_original_aspect_ratio=increase,crop={OUT_W}:{OUT_H},"
            f"boxblur=24:2[bgb{index}]",
            f"[fg{index}]scale={OUT_W}:-2[fgs{index}]",
            f"[bgb{index}][fgs{index}]overlay=(W-w)/2:(H-h)/2,fps={OUT_FPS},setsar=1,format=yuv420p[v{index}]",
        ]
    return [f"{src}[s{index}]", fill_filter(f"s{index}", f"v{index}")]


def build_body(
    clips: Sequence[str | Path],
    out_path: str | Path,
    *,
    tools: MediaTools,
    limit_sec: Optional[float] = None,
) -> BodyAttachResult:
    """촬영 클립들을 1080x1920 30fps, -14 LUFS 본편 하나로 만든다."""
    target = Path(out_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    warnings: List[str] = []
    sources = []
    for clip in clips:
        path = Path(clip)
        info = probe(tools, path)
        if not info.has_video or info.duration <= 0:
            warnings.append(f"{path.name}: 영상이 없어 건너뜁니다.")
            continue
        sources.append((path, info))
    if not sources:
        raise BodyAttachError("붙일 수 있는 본편 영상이 없습니다.")

    lengths = plan_body_segments([info.duration for _, info in sources], limit_sec)
    kept = [(path, info, sec) for (path, info), sec in zip(sources, lengths) if sec >= MIN_SEGMENT_SEC]
    if not kept:
        kept = [(sources[0][0], sources[0][1], min(sources[0][1].duration, limit_sec or sources[0][1].duration))]
    if sum(lengths) < sum(info.duration for _, info in sources) - 0.05:
        warnings.append(f"본편을 {sum(sec for _, _, sec in kept):.1f}초로 줄였습니다 (각 클립의 앞부분 사용).")

    args: List[str] = []
    filters: List[str] = []
    segments: List[dict] = []
    has_any_audio = any(info.has_audio for _, info, _ in kept)
    for index, (path, info, seconds) in enumerate(kept):
        args += ["-i", str(path)]
        landscape = info.height > 0 and (info.width / info.height) > LANDSCAPE_RATIO
        filters += _video_chain(index, seconds, landscape, tools)
        if info.has_audio:
            filters.append(
                f"[{index}:a]atrim=0:{seconds:.3f},asetpts=PTS-STARTPTS,aresample={AUDIO_RATE},"
                f"aformat=channel_layouts=stereo,apad=whole_dur={seconds:.3f}[a{index}]"
            )
        else:
            # 소리 없는 클립은 같은 길이의 무음으로 채운다
            filters.append(f"anullsrc=r={AUDIO_RATE}:cl=stereo,atrim=0:{seconds:.3f}[a{index}]")
        segments.append({"file": path.name, "seconds": round(seconds, 3), "landscape": landscape, "has_audio": info.has_audio})
    pairs = "".join(f"[v{i}][a{i}]" for i in range(len(kept)))
    filters.append(f"{pairs}concat=n={len(kept)}:v=1:a=1[vout][acat]")
    if has_any_audio:
        filters.append(f"[acat]loudnorm=I={TARGET_LUFS}:TP=-1.5:LRA=11,aresample={AUDIO_RATE}[aout]")
    else:
        filters.append("[acat]anull[aout]")
    total = sum(sec for _, _, sec in kept)
    run_ffmpeg(
        tools,
        [*args, "-filter_complex", ";".join(filters), "-map", "[vout]", "-map", "[aout]",
         *VIDEO_ENCODE_ARGS, *AUDIO_ENCODE_ARGS, "-t", f"{total:.3f}", str(target)],
    )
    info = probe(tools, target)
    return BodyAttachResult(
        path=target,
        duration_sec=round(info.duration, 3),
        hook_sec=0.0,
        body_sec=round(info.duration, 3),
        lufs=measure_lufs(tools, target) if has_any_audio else None,
        segments=segments,
        warnings=warnings,
    )


def join_hook_and_body(
    hook_mp4: str | Path,
    body_mp4: str | Path,
    out_path: str | Path,
    *,
    tools: MediaTools,
) -> BodyAttachResult:
    """훅 + 본편 → 최종 영상. 두 영상 모두 다시 인코딩해 규격을 하나로 맞춘다."""
    hook, body, target = Path(hook_mp4), Path(body_mp4), Path(out_path)
    hook_info, body_info = probe(tools, hook), probe(tools, body)
    if not hook_info.has_video:
        raise BodyAttachError("훅 영상에 화면이 없습니다.")
    filters = [fill_filter("0:v", "v0"), fill_filter("1:v", "v1")]
    args = ["-i", str(hook), "-i", str(body)]
    for index, info in ((0, hook_info), (1, body_info)):
        if info.has_audio:
            filters.append(
                f"[{index}:a]aresample={AUDIO_RATE},aformat=channel_layouts=stereo,"
                f"apad=whole_dur={info.duration:.3f}[a{index}]"
            )
        else:
            filters.append(f"anullsrc=r={AUDIO_RATE}:cl=stereo,atrim=0:{info.duration:.3f}[a{index}]")
    filters.append("[v0][a0][v1][a1]concat=n=2:v=1:a=1[vout][aout]")
    total = hook_info.duration + body_info.duration
    run_ffmpeg(
        tools,
        [*args, "-filter_complex", ";".join(filters), "-map", "[vout]", "-map", "[aout]",
         *VIDEO_ENCODE_ARGS, *AUDIO_ENCODE_ARGS, "-t", f"{total:.3f}", str(target)],
    )
    info = probe(tools, target)
    return BodyAttachResult(
        path=target,
        duration_sec=round(info.duration, 3),
        hook_sec=round(hook_info.duration, 3),
        body_sec=round(body_info.duration, 3),
        lufs=measure_lufs(tools, target),
    )


def attach_body(
    hook_mp4: str | Path,
    body_clips: Sequence[str | Path],
    out_path: str | Path,
    *,
    tools: MediaTools,
    limit_sec: Optional[float] = None,
    hook_srt: Optional[str | Path] = None,
) -> BodyAttachResult:
    """훅 뒤에 본편을 붙여 out_path 를 만든다. 자막 파일이 있으면 같은 이름의 .srt 로 복사한다(훅 구간 자막)."""
    target = Path(out_path)
    if not Path(hook_mp4).is_file():
        raise BodyAttachError(f"훅 영상이 없습니다: {hook_mp4}")
    body_path = target.with_name(f"{target.stem}_body.mp4")
    try:
        body = build_body(body_clips, body_path, tools=tools, limit_sec=limit_sec)
        joined = join_hook_and_body(hook_mp4, body_path, target, tools=tools)
    except MediaError as exc:
        raise BodyAttachError(str(exc)) from exc
    joined.segments = body.segments
    joined.warnings = body.warnings
    if hook_srt and Path(hook_srt).is_file():
        shutil.copyfile(hook_srt, target.with_suffix(".srt"))
    return joined
