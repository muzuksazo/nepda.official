"""ffmpeg / ffprobe 실행 도우미. hookpipe 의 모든 영상·소리 처리는 여기를 거친다."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

OUT_W, OUT_H, OUT_FPS = 1080, 1920, 30
TARGET_LUFS = -14.0
AUDIO_RATE = 48000


class MediaError(RuntimeError):
    """ffmpeg 를 찾지 못했거나 실행이 실패했을 때."""


@dataclass
class MediaInfo:
    duration: float
    width: int
    height: int
    has_video: bool
    has_audio: bool


@dataclass
class MediaTools:
    ffmpeg: str
    ffprobe: Optional[str] = None
    _filters: Optional[set] = field(default=None, repr=False)
    _encoders: Optional[set] = field(default=None, repr=False)

    def has_filter(self, name: str) -> bool:
        if self._filters is None:
            self._filters = _list_names(self.ffmpeg, "-filters")
        return name in self._filters

    def has_encoder(self, name: str) -> bool:
        if self._encoders is None:
            self._encoders = _list_names(self.ffmpeg, "-encoders")
        return name in self._encoders


def _list_names(ffmpeg: str, flag: str) -> set:
    proc = subprocess.run([ffmpeg, "-hide_banner", flag], capture_output=True, text=True, encoding="utf-8", errors="replace")
    names = set()
    for line in (proc.stdout or "").splitlines():
        parts = line.split()
        if len(parts) >= 2 and not parts[0].startswith("-") and parts[0] != "=":
            names.add(parts[1])
    return names


def find_tools(ffmpeg_bin: Optional[str] = None, ffprobe_bin: Optional[str] = None) -> MediaTools:
    """설정값 → 환경변수(FFMPEG_BIN, FFPROBE_BIN) → PATH 순서로 찾는다. ffprobe 는 없어도 된다."""
    ffmpeg = ffmpeg_bin or os.environ.get("FFMPEG_BIN") or shutil.which("ffmpeg")
    if not ffmpeg or not (shutil.which(ffmpeg) or Path(ffmpeg).is_file()):
        raise MediaError("ffmpeg 를 찾지 못했습니다. 설치하거나 FFMPEG_BIN 에 실행 파일 경로를 넣어 주세요.")
    ffprobe = ffprobe_bin or os.environ.get("FFPROBE_BIN") or shutil.which("ffprobe")
    if ffprobe and not (shutil.which(ffprobe) or Path(ffprobe).is_file()):
        ffprobe = None
    return MediaTools(ffmpeg=str(ffmpeg), ffprobe=str(ffprobe) if ffprobe else None)


def run_ffmpeg(
    tools: MediaTools,
    args: Sequence[str],
    *,
    cwd: Optional[Path] = None,
    timeout: float = 1800.0,
) -> str:
    """ffmpeg 를 실행하고 stderr 를 돌려준다. 실패하면 stderr 끝부분을 담아 MediaError."""
    cmd = [tools.ffmpeg, "-hide_banner", "-nostdin", "-y", *[str(a) for a in args]]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise MediaError(f"ffmpeg 가 {timeout:.0f}초 안에 끝나지 않았습니다.") from exc
    if proc.returncode != 0:
        tail = "\n".join((proc.stderr or "").strip().splitlines()[-12:])
        raise MediaError(f"ffmpeg 실패 (종료 코드 {proc.returncode}):\n{tail}")
    return proc.stderr or ""


def _apply_rotation(width: int, height: int, rotation: float) -> tuple[int, int]:
    return (height, width) if int(abs(round(rotation))) % 180 == 90 else (width, height)


def probe(tools: MediaTools, path: str | Path) -> MediaInfo:
    """길이·크기·소리 유무. 세로로 찍은 휴대폰 영상의 회전 정보는 반영한 크기를 돌려준다."""
    target = str(path)
    if not Path(target).is_file():
        raise MediaError(f"파일이 없습니다: {target}")
    if tools.ffprobe:
        proc = subprocess.run(
            [tools.ffprobe, "-v", "error", "-show_format", "-show_streams", "-of", "json", target],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if proc.returncode == 0:
            return _info_from_ffprobe(json.loads(proc.stdout or "{}"))
    proc = subprocess.run(
        [tools.ffmpeg, "-hide_banner", "-nostdin", "-i", target],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return _info_from_banner(proc.stderr or "", target)


def _info_from_ffprobe(raw: Dict[str, Any]) -> MediaInfo:
    streams: List[Dict[str, Any]] = raw.get("streams") or []
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    duration = float((raw.get("format") or {}).get("duration") or 0.0)
    width = height = 0
    if video:
        width, height = int(video.get("width") or 0), int(video.get("height") or 0)
        rotation = 0.0
        for side in video.get("side_data_list") or []:
            if "rotation" in side:
                rotation = float(side["rotation"])
        tag_rotate = (video.get("tags") or {}).get("rotate")
        if tag_rotate and not rotation:
            rotation = float(tag_rotate)
        width, height = _apply_rotation(width, height, rotation)
        if not duration:
            duration = float(video.get("duration") or 0.0)
    return MediaInfo(duration=duration, width=width, height=height, has_video=video is not None, has_audio=audio is not None)


_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")
_VIDEO_RE = re.compile(r"Stream #.*Video:.*?[ ,](\d{2,5})x(\d{2,5})[ ,\[]")
_ROTATION_RE = re.compile(r"rotation of (-?\d+(?:\.\d+)?) degrees")


def _info_from_banner(text: str, target: str) -> MediaInfo:
    """ffprobe 가 없을 때 `ffmpeg -i` 출력에서 읽는다."""
    dur_match = _DURATION_RE.search(text)
    if not dur_match and "Stream #" not in text:
        raise MediaError(f"영상 정보를 읽지 못했습니다: {target}")
    duration = 0.0
    if dur_match:
        duration = int(dur_match.group(1)) * 3600 + int(dur_match.group(2)) * 60 + float(dur_match.group(3))
    video = _VIDEO_RE.search(text)
    width = height = 0
    if video:
        width, height = int(video.group(1)), int(video.group(2))
        rot = _ROTATION_RE.search(text)
        if rot:
            width, height = _apply_rotation(width, height, float(rot.group(1)))
    has_audio = bool(re.search(r"Stream #.*Audio:", text))
    return MediaInfo(duration=duration, width=width, height=height, has_video=video is not None, has_audio=has_audio)


def measure_lufs(tools: MediaTools, path: str | Path) -> Optional[float]:
    """통합 음량(LUFS)을 잰다. 소리가 없거나 잴 수 없으면 None."""
    try:
        stderr = run_ffmpeg(
            tools,
            ["-i", str(path), "-vn", "-af", "loudnorm=print_format=json", "-f", "null", "-"],
            timeout=600.0,
        )
    except MediaError:
        return None
    start = stderr.rfind("{")
    end = stderr.rfind("}")
    if start < 0 or end < start:
        return None
    try:
        value = float(json.loads(stderr[start : end + 1]).get("input_i"))
    except (ValueError, TypeError):
        return None
    return None if value != value or value in (float("inf"), float("-inf")) else round(value, 2)


def fill_filter(label_in: str, label_out: str) -> str:
    """어떤 크기의 영상이든 1080x1920 30fps 로 꽉 채운다 (넘치는 쪽은 가운데를 기준으로 자른다)."""
    return (
        f"[{label_in}]scale={OUT_W}:{OUT_H}:force_original_aspect_ratio=increase,"
        f"crop={OUT_W}:{OUT_H},fps={OUT_FPS},setsar=1,format=yuv420p[{label_out}]"
    )


VIDEO_ENCODE_ARGS = [
    "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
    "-r", str(OUT_FPS), "-movflags", "+faststart",
]
AUDIO_ENCODE_ARGS = ["-c:a", "aac", "-b:a", "192k", "-ar", str(AUDIO_RATE), "-ac", "2"]
