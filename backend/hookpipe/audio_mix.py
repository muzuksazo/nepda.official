"""Studio-grade 3-bus BGM + transition SFX mixer with VO sidechain ducking for hookpipe."""

from __future__ import annotations

import logging
import os
import shutil
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from .media import (
    AUDIO_ENCODE_ARGS,
    AUDIO_RATE,
    MediaError,
    MediaTools,
    gain_filter,
    gain_to_target,
    measure_lufs,
    probe,
    run_ffmpeg,
)

logger = logging.getLogger("hookpipe.audio_mix")

_CACHE_LOCK = threading.Lock()

HOOK_BGM_FILES: Dict[str, str] = {
    "A": "bgm_hook_a.mp3",
    "B": "bgm_hook_b.mp3",
    "C": "bgm_hook_c.mp3",
}
BODY_BGM_FILE = "bgm_body.mp3"
TRANSITION_SFX_FILE = "sfx_transition.mp3"
OUTRO_SFX_FILE = "sfx_outro.mp3"
DEFAULT_AUDIO_LOCATION = "storage:assets/audio"


@dataclass
class AudioPack:
    """Resolved local audio stems for a single hook+body render."""

    hook_bgm: Optional[Path] = None
    body_bgm: Optional[Path] = None
    transition_sfx: Optional[Path] = None
    outro_sfx: Optional[Path] = None

    def is_empty(self) -> bool:
        return not (self.hook_bgm or self.body_bgm or self.transition_sfx or self.outro_sfx)


def _fetch_audio_file(
    filename: str,
    *,
    location: str,
    storage: Any,
    cache_dir: Path,
) -> Optional[Path]:
    if location.startswith("storage:"):
        if storage is None or not hasattr(storage, "download_file"):
            return None
        prefix = location[len("storage:") :].strip("/")
        key = f"{prefix}/{filename}" if prefix else filename
        dest = (cache_dir / filename).resolve()
        if dest.is_file() and dest.stat().st_size > 0:
            return dest
        with _CACHE_LOCK:
            if dest.is_file() and dest.stat().st_size > 0:
                return dest
            dest.parent.mkdir(parents=True, exist_ok=True)
            tmp_dest = dest.with_suffix(f"{dest.suffix}.tmp")
            try:
                storage.download_file(key, tmp_dest)
                if tmp_dest.is_file() and tmp_dest.stat().st_size > 0:
                    os.replace(tmp_dest, dest)
                    return dest
            except Exception as exc:
                logger.debug("Optional audio stem unavailable (%s): %s", key, exc)
                tmp_dest.unlink(missing_ok=True)
        return None

    candidate = (Path(location).expanduser() / filename).resolve()
    return candidate if candidate.is_file() and candidate.stat().st_size > 0 else None


def resolve_audio_pack(
    settings: Any,
    storage: Any,
    *,
    hook_type: str,
    cache_dir: Path,
) -> AudioPack:
    """Resolve hook BGM, body BGM, and transition SFX from configured R2 prefix or local folder."""
    if not bool(getattr(settings, "hook_bgm_enabled", True)):
        return AudioPack()
    location = str(getattr(settings, "hook_audio_location", "") or DEFAULT_AUDIO_LOCATION).strip()
    if not location:
        return AudioPack()

    htype = str(hook_type or "A").strip().upper()
    hook_name = HOOK_BGM_FILES.get(htype, HOOK_BGM_FILES["A"])
    hook_bgm = _fetch_audio_file(hook_name, location=location, storage=storage, cache_dir=cache_dir)
    if hook_bgm is None and hook_name != HOOK_BGM_FILES["A"]:
        hook_bgm = _fetch_audio_file(
            HOOK_BGM_FILES["A"], location=location, storage=storage, cache_dir=cache_dir
        )

    body_bgm = _fetch_audio_file(BODY_BGM_FILE, location=location, storage=storage, cache_dir=cache_dir)
    transition_sfx = _fetch_audio_file(
        TRANSITION_SFX_FILE, location=location, storage=storage, cache_dir=cache_dir
    )
    outro_sfx = _fetch_audio_file(OUTRO_SFX_FILE, location=location, storage=storage, cache_dir=cache_dir)
    return AudioPack(
        hook_bgm=hook_bgm,
        body_bgm=body_bgm,
        transition_sfx=transition_sfx,
        outro_sfx=outro_sfx,
    )


def mix_bgm_and_sfx(
    video_mp4: Path,
    *,
    hook_sec: float,
    twist_sec: Optional[float] = None,
    tools: MediaTools,
    pack: AudioPack,
    tmp_dir: Path,
    hook_bgm_db: float = -17.0,
    endcard_sec: float = 0.0,
) -> Optional[float]:
    """Mix 2-stage BGM (with twist dead-stop), transition/outro SFX, and VO-keyed sidechain ducking onto `video_mp4`.

    Returns measured integrated LUFS after mastering, or `None` if skipped/no audio stems.
    """
    if pack.is_empty() or not video_mp4.is_file():
        return None

    info = probe(tools, video_mp4)
    total = float(info.duration or 0.0)
    if total <= 0.5:
        return None

    pivot_sec = float(twist_sec) if (twist_sec is not None and float(twist_sec) > 0.0) else float(hook_sec)
    ec_sec = max(0.0, float(endcard_sec or 0.0))
    if ec_sec > 0.0:
        fade_out_d = min(1.15, max(0.80, ec_sec * 0.45))
        fade_curve = ":curve=exp"
    else:
        fade_out_d = 0.45
        fade_curve = ""

    tmp_dir.mkdir(parents=True, exist_ok=True)
    pre_mix = tmp_dir / "pre_mix.mp4"
    mastered = tmp_dir / "mastered.mp4"

    cmd: List[str] = ["-i", str(video_mp4)]
    filters: List[str] = []
    mix_labels: List[str] = []
    idx = 1

    has_vo = bool(info.has_audio)
    has_bgm = bool(pack.hook_bgm or pack.body_bgm)
    vo_key_lbl: Optional[str] = None
    if has_vo:
        vo_base = (
            f"[0:a]highpass=f=85,aresample={AUDIO_RATE},aformat=channel_layouts=stereo,"
            f"apad=whole_dur={total:.3f},atrim=0:{total:.3f}"
        )
        if has_bgm and tools.has_filter("sidechaincompress"):
            filters.append(f"{vo_base},asplit=2[avo][avokey]")
            vo_key_lbl = "[avokey]"
        else:
            filters.append(f"{vo_base}[avo]")
    else:
        filters.append(f"anullsrc=r={AUDIO_RATE}:cl=stereo,atrim=0:{total:.3f}[avo]")
    mix_labels.append("[avo]")

    # Bus 2: 2-stage BGM (Act 1 -> 0.30s twist dead-stop -> Act 2 lift) or continuous single-loop fallback
    bgm_raw_lbl: Optional[str] = None
    if pack.hook_bgm and pack.body_bgm and pivot_sec >= 2.0 and total > pivot_sec + 1.0:
        gap_sec = 0.30
        act1_end = max(0.5, pivot_sec - gap_sec)
        act2_dur = max(0.5, total - pivot_sec)
        act1_fade_out_st = max(0.0, act1_end - 0.06)
        act2_fade_d = min(fade_out_d, act2_dur)
        act2_fade_out_st = max(0.0, act2_dur - act2_fade_d)
        twist_ms = int(round(pivot_sec * 1000))

        cmd.extend(["-stream_loop", "-1", "-i", str(pack.hook_bgm)])
        idx_h = idx
        idx += 1
        cmd.extend(["-stream_loop", "-1", "-i", str(pack.body_bgm)])
        idx_b = idx
        idx += 1

        filters.append(
            f"[{idx_h}:a]atrim=0:{act1_end:.3f},asetpts=PTS-STARTPTS,"
            f"volume={hook_bgm_db:.1f}dB,afade=t=in:st=0:d=0.08,afade=t=out:st={act1_fade_out_st:.3f}:d=0.06,"
            f"aresample={AUDIO_RATE},aformat=channel_layouts=stereo,"
            f"apad=whole_dur={total:.3f},atrim=0:{total:.3f}[abgm1]"
        )
        filters.append(
            f"[{idx_b}:a]atrim=0:{act2_dur:.3f},asetpts=PTS-STARTPTS,"
            f"volume=-15.5dB,afade=t=in:st=0:d=0.06,afade=t=out:st={act2_fade_out_st:.3f}:d={act2_fade_d:.2f}{fade_curve},"
            f"aresample={AUDIO_RATE},aformat=channel_layouts=stereo,"
            f"adelay={twist_ms}:all=1,apad=whole_dur={total:.3f},atrim=0:{total:.3f}[abgm2]"
        )
        filters.append("[abgm1][abgm2]amix=inputs=2:duration=first:normalize=0[abgm_raw]")
        bgm_raw_lbl = "[abgm_raw]"
    elif pack.hook_bgm or pack.body_bgm:
        single_bgm = pack.hook_bgm or pack.body_bgm
        single_fade_d = min(fade_out_d, total)
        fade_out_st = max(0.0, total - single_fade_d)
        cmd.extend(["-stream_loop", "-1", "-i", str(single_bgm)])
        idx_s = idx
        idx += 1
        filters.append(
            f"[{idx_s}:a]atrim=0:{total:.3f},asetpts=PTS-STARTPTS,"
            f"volume=-16dB,afade=t=in:st=0:d=0.08,afade=t=out:st={fade_out_st:.3f}:d={single_fade_d:.2f}{fade_curve},"
            f"aresample={AUDIO_RATE},aformat=channel_layouts=stereo,"
            f"apad=whole_dur={total:.3f},atrim=0:{total:.3f}[abgm_raw]"
        )
        bgm_raw_lbl = "[abgm_raw]"

    if bgm_raw_lbl:
        if vo_key_lbl and tools.has_filter("sidechaincompress"):
            filters.append(
                f"{bgm_raw_lbl}{vo_key_lbl}sidechaincompress="
                f"threshold=0.022:ratio=6:attack=12:release=260:makeup=1[abgm]"
            )
            mix_labels.append("[abgm]")
        else:
            mix_labels.append(bgm_raw_lbl)

    # Bus 3: Transition SFX hit right at the twist dead-stop
    if pack.transition_sfx and pivot_sec >= 2.0 and total > pivot_sec + 0.5:
        sfx_ms = int(round(max(0.0, pivot_sec - 0.30) * 1000))
        cmd.extend(["-i", str(pack.transition_sfx)])
        idx_sfx = idx
        idx += 1
        delay_stage = f"adelay={sfx_ms}:all=1," if sfx_ms > 0 else ""
        filters.append(
            f"[{idx_sfx}:a]volume=-11dB,aresample={AUDIO_RATE},aformat=channel_layouts=stereo,"
            f"{delay_stage}apad=whole_dur={total:.3f},atrim=0:{total:.3f}[asfx]"
        )
        mix_labels.append("[asfx]")

    # Bus 4: Outro SFX hit right at the packshot end-card entry
    if ec_sec > 0.0 and pack.outro_sfx and total > ec_sec + 0.5:
        outro_ms = int(round(max(0.0, total - ec_sec) * 1000))
        cmd.extend(["-i", str(pack.outro_sfx)])
        idx_outro = idx
        idx += 1
        outro_delay = f"adelay={outro_ms}:all=1," if outro_ms > 0 else ""
        filters.append(
            f"[{idx_outro}:a]volume=-14dB,aresample={AUDIO_RATE},aformat=channel_layouts=stereo,"
            f"{outro_delay}apad=whole_dur={total:.3f},atrim=0:{total:.3f}[aoutro]"
        )
        mix_labels.append("[aoutro]")

    filters.append(f"{''.join(mix_labels)}amix=inputs={len(mix_labels)}:duration=first:normalize=0[amix]")
    cmd.extend([
        "-filter_complex",
        ";".join(filters),
        "-map",
        "0:v",
        "-map",
        "[amix]",
        "-c:v",
        "copy",
        *AUDIO_ENCODE_ARGS,
        "-t",
        f"{total:.3f}",
        str(pre_mix),
    ])
    run_ffmpeg(tools, cmd)

    measured = measure_lufs(tools, pre_mix)
    gain_db = gain_to_target(measured)
    if measured is not None and abs(gain_db) > 0.05:
        run_ffmpeg(
            tools,
            [
                "-i",
                str(pre_mix),
                "-map",
                "0:v",
                "-map",
                "0:a",
                "-c:v",
                "copy",
                "-af",
                gain_filter(tools, gain_db),
                *AUDIO_ENCODE_ARGS,
                str(mastered),
            ],
        )
        final_src = mastered
    else:
        final_src = pre_mix

    if not final_src.is_file() or final_src.stat().st_size <= 0:
        raise MediaError("3-Bus 오디오 마스터링 출력 파일이 비어 있습니다.")

    try:
        os.replace(final_src, video_mp4)
    except OSError:
        shutil.move(str(final_src), str(video_mp4))
    pre_mix.unlink(missing_ok=True)
    mastered.unlink(missing_ok=True)
    return measure_lufs(tools, video_mp4)
