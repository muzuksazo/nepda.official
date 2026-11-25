#!/usr/bin/env python3
"""Audio-first VO silence trimmer, beat concatenator, and timestamp JSON builder.

Supports two workflows:
  1. Single long VO take (`--input raw_vo.mp4|wav`): trims excess dead air cleanly
     down to `--keep-gap` (default 0.12s) and writes `vo_master.wav` + `vo_segments.json`.
  2. Multi-part VO manifest (`--manifest vo_plan.json` or comma-separated `--inputs`):
     extracts/speeds/trims leading-trailing silence of each spoken beat, inserts
     exact inter-beat pauses (e.g. 0.25s twist pause), and exports locked
     `vo_master.wav` + `vo_segments.json` (`start`, `end`, `duration` per beat).

Uses ffmpeg + numpy + stdlib wave ONLY (safe on macOS without loudnorm/scipy).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tempfile
import wave
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


def decode_audio_f32(
    input_path: str,
    *,
    sample_rate: int = 48000,
    channels: int = 2,
    speed: float = 1.0,
    start_sec: Optional[float] = None,
    end_sec: Optional[float] = None,
) -> np.ndarray:
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", input_path]
    af_parts = []
    if start_sec is not None or end_sec is not None:
        trim_args: List[str] = []
        if start_sec is not None:
            trim_args.append(f"start={float(start_sec):.6f}")
        if end_sec is not None:
            trim_args.append(f"end={float(end_sec):.6f}")
        af_parts.append("atrim=" + ":".join(trim_args))
        af_parts.append("asetpts=PTS-STARTPTS")
    if abs(speed - 1.0) > 1e-3:
        af_parts.append(f"atempo={speed:.4f}")
    if af_parts:
        cmd.extend(["-af", ",".join(af_parts)])
    cmd.extend([
        "-f", "f32le",
        "-acodec", "pcm_f32le",
        "-ac", str(channels),
        "-ar", str(sample_rate),
        "pipe:1",
    ])
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg decode failed for {input_path}: {proc.stderr.decode('utf-8', 'ignore')}")
    arr = np.frombuffer(proc.stdout, dtype=np.float32)
    frames = len(arr) // channels
    return arr[: frames * channels].reshape((frames, channels))


def write_wav_pcm16(out_path: str, samples: np.ndarray, sample_rate: int = 48000) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    clipped = np.clip(samples, -0.9999, 0.9999)
    pcm = (clipped * 32767.0).astype(np.int16)
    with wave.open(out_path, "wb") as wf:
        wf.setnchannels(pcm.shape[1])
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())


def measure_ebur128_i(audio_path: str) -> Optional[float]:
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", audio_path, "-af", "ebur128", "-vn", "-f", "null", "-"],
        capture_output=True,
        text=True,
    )
    txt = proc.stderr or ""
    matches = re.findall(r"^\s*I:\s*(-?[0-9]+(?:\.[0-9]+)?|inf|-inf)\s+LUFS", txt, flags=re.MULTILINE)
    if not matches:
        return None
    s = matches[-1]
    if "inf" in s.lower():
        return None
    val = float(s)
    return val if -65.0 <= val <= 0.0 else None


def _detect_islands(
    audio: np.ndarray,
    *,
    sample_rate: int = 48000,
    silence_db: float = -38.0,
    min_silence: float = 0.28,
) -> List[Tuple[int, int]]:
    hop = int(sample_rate * 0.01)
    n_hops = audio.shape[0] // hop
    if n_hops == 0:
        return []
    mono = np.mean(audio[: n_hops * hop], axis=1).reshape((n_hops, hop))
    rms = np.sqrt(np.mean(mono * mono, axis=1) + 1e-12)
    db = 20.0 * np.log10(rms)
    active = db >= silence_db

    pre_hops = 4
    post_hops = 7
    raw_islands: List[Tuple[int, int]] = []
    in_seg = False
    seg_s = 0
    for i, flag in enumerate(active):
        if flag and not in_seg:
            in_seg = True
            seg_s = max(0, i - pre_hops)
        elif not flag and in_seg:
            in_seg = False
            raw_islands.append((seg_s, min(n_hops, i + post_hops)))
    if in_seg:
        raw_islands.append((seg_s, n_hops))

    if not raw_islands:
        return []

    min_sil_hops = int(min_silence / 0.01)
    merged: List[Tuple[int, int]] = [raw_islands[0]]
    for s, e in raw_islands[1:]:
        ps, pe = merged[-1]
        if s - pe < min_sil_hops:
            merged[-1] = (ps, max(pe, e))
        else:
            merged.append((s, e))
    return merged


def _fade_chunk(chunk: np.ndarray, sample_rate: int = 48000, fade_ms: float = 12.0) -> np.ndarray:
    c = chunk.copy()
    xfade = int(sample_rate * (fade_ms / 1000.0))
    f_len = min(xfade, len(c) // 4)
    if f_len > 1:
        c[:f_len] *= np.linspace(0.0, 1.0, f_len, dtype=np.float32)[:, None]
        c[-f_len:] *= np.linspace(1.0, 0.0, f_len, dtype=np.float32)[:, None]
    return c


def _normalize_chunk_rms(chunk: np.ndarray, target_rms: float = 0.14) -> np.ndarray:
    rms = float(np.sqrt(np.mean(chunk * chunk) + 1e-12))
    if rms < 1e-5:
        return chunk
    gain = min(6.0, max(0.25, target_rms / rms))
    out = chunk * gain
    peak = float(np.max(np.abs(out)))
    if peak > 0.89:
        out = out * (0.89 / peak)
    return out


def trim_single_vo(
    input_path: str,
    out_wav: str,
    out_json: str,
    *,
    silence_db: float = -38.0,
    min_silence: float = 0.28,
    keep_gap: float = 0.12,
    act_gap: float = 0.25,
    act_threshold: float = 0.85,
    speed: float = 1.0,
    sample_rate: int = 48000,
) -> Dict[str, Any]:
    audio = decode_audio_f32(input_path, sample_rate=sample_rate, channels=2, speed=speed)
    raw_dur = audio.shape[0] / sample_rate
    merged = _detect_islands(audio, sample_rate=sample_rate, silence_db=silence_db, min_silence=min_silence)
    if not merged:
        raise RuntimeError(f"No speech detected above {silence_db} dB in {input_path}")

    hop = int(sample_rate * 0.01)
    out_chunks: List[np.ndarray] = []
    segments_meta: List[Dict[str, Any]] = []
    cur_sample = 0

    for idx, (sh, eh) in enumerate(merged):
        s_idx = sh * hop
        e_idx = min(audio.shape[0], eh * hop)
        chunk = _fade_chunk(audio[s_idx:e_idx], sample_rate=sample_rate)
        out_chunks.append(chunk)
        seg_start_s = cur_sample / sample_rate
        cur_sample += len(chunk)
        seg_end_s = cur_sample / sample_rate

        gap_after = 0.0
        if idx + 1 < len(merged):
            raw_gap_s = (merged[idx + 1][0] - eh) * 0.01
            gap_after = act_gap if raw_gap_s >= act_threshold else keep_gap
            gap_samples = int(round(gap_after * sample_rate))
            if gap_samples > 0:
                out_chunks.append(np.zeros((gap_samples, 2), dtype=np.float32))
                cur_sample += gap_samples

        segments_meta.append({
            "index": idx + 1,
            "start": round(seg_start_s, 3),
            "end": round(seg_end_s, 3),
            "duration": round(seg_end_s - seg_start_s, 3),
            "raw_start": round(s_idx / sample_rate, 3),
            "raw_end": round(e_idx / sample_rate, 3),
            "gap_after": round(gap_after, 3),
        })

    trimmed = _normalize_chunk_rms(np.vstack(out_chunks), target_rms=0.14)
    write_wav_pcm16(out_wav, trimmed, sample_rate=sample_rate)
    payload = {
        "mode": "single",
        "input_file": input_path,
        "output_wav": os.path.abspath(out_wav),
        "raw_duration": round(raw_dur, 3),
        "total_duration": round(len(trimmed) / sample_rate, 3),
        "segment_count": len(segments_meta),
        "lufs_i": measure_ebur128_i(out_wav),
        "segments": segments_meta,
    }
    os.makedirs(os.path.dirname(os.path.abspath(out_json)), exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return payload


def probe_islands(
    input_path: str,
    *,
    silence_db: float = -39.0,
    min_silence: float = 0.08,
    speed: float = 1.0,
    sample_rate: int = 48000,
) -> Dict[str, Any]:
    """Probe exact spoken speech islands and inter-phrase gaps without writing WAVs."""
    audio = decode_audio_f32(input_path, sample_rate=sample_rate, channels=2, speed=speed)
    raw_dur = audio.shape[0] / sample_rate
    merged = _detect_islands(audio, sample_rate=sample_rate, silence_db=silence_db, min_silence=min_silence)
    islands: List[Dict[str, Any]] = []
    for idx, (sh, eh) in enumerate(merged):
        st = round(sh * 0.01, 3)
        en = round(min(raw_dur, eh * 0.01), 3)
        next_st = round(merged[idx + 1][0] * 0.01, 3) if idx + 1 < len(merged) else round(raw_dur, 3)
        islands.append({
            "index": idx,
            "start": st,
            "end": en,
            "duration": round(en - st, 3),
            "gap_after": round(max(0.0, next_st - en), 3),
        })
    return {
        "file": os.path.abspath(input_path),
        "duration": round(raw_dur, 3),
        "silence_db": silence_db,
        "min_silence": min_silence,
        "speed": speed,
        "island_count": len(islands),
        "islands": islands,
    }


def build_manifest_vo(
    manifest_path: str,
    out_wav: str,
    out_json: str,
    *,
    default_gap: float = 0.12,
    silence_db: float = -40.0,
    min_silence: float = 0.25,
    sample_rate: int = 48000,
) -> Dict[str, Any]:
    with open(manifest_path, "r", encoding="utf-8") as f:
        plan = json.load(f)
    base_dir = os.path.dirname(os.path.abspath(manifest_path))
    beats = plan.get("beats") if isinstance(plan, dict) else (plan if isinstance(plan, list) else [])
    if not beats:
        raise RuntimeError(f"Empty beats in VO manifest: {manifest_path}")

    hop = int(sample_rate * 0.01)
    out_chunks: List[np.ndarray] = []
    segments_meta: List[Dict[str, Any]] = []
    cur_sample = 0

    for idx, b in enumerate(beats):
        fpath = b["file"]
        if not os.path.isabs(fpath):
            fpath = os.path.join(base_dir, fpath)
        speed = float(b.get("speed", 1.0) or 1.0)
        gain_db = float(b.get("gain_db", 0.0) or 0.0)
        start_sec = float(b["start_sec"]) if b.get("start_sec") is not None else None
        end_sec = float(b["end_sec"]) if b.get("end_sec") is not None else None
        if start_sec is not None and end_sec is not None and end_sec <= start_sec:
            raise RuntimeError(f"Invalid sub-slice [{start_sec}, {end_sec}] for beat {b.get('id', idx)}")
        audio = decode_audio_f32(
            fpath,
            sample_rate=sample_rate,
            channels=2,
            speed=speed,
            start_sec=start_sec,
            end_sec=end_sec,
        )

        if b.get("trim_edges", True):
            islands = _detect_islands(audio, sample_rate=sample_rate, silence_db=silence_db, min_silence=min_silence)
            if islands:
                parts: List[np.ndarray] = []
                for j, (sh, eh) in enumerate(islands):
                    parts.append(_fade_chunk(audio[sh * hop : min(audio.shape[0], eh * hop)], sample_rate=sample_rate))
                    if j + 1 < len(islands):
                        inner_gap = float(b.get("inner_gap_sec", 0.08))
                        if inner_gap > 0:
                            parts.append(np.zeros((int(round(inner_gap * sample_rate)), 2), dtype=np.float32))
                chunk = np.vstack(parts)
            else:
                chunk = _fade_chunk(audio, sample_rate=sample_rate)
        else:
            chunk = _fade_chunk(audio, sample_rate=sample_rate)

        chunk = _normalize_chunk_rms(chunk, target_rms=0.145)
        if abs(gain_db) > 0.05:
            chunk = chunk * (10.0 ** (gain_db / 20.0))

        gap_before = float(b.get("gap_before", 0.0) or 0.0)
        if gap_before > 0:
            out_chunks.append(np.zeros((int(round(gap_before * sample_rate)), 2), dtype=np.float32))
            cur_sample += int(round(gap_before * sample_rate))

        seg_start_s = cur_sample / sample_rate
        out_chunks.append(chunk)
        cur_sample += len(chunk)
        seg_end_s = cur_sample / sample_rate

        gap_after = float(b.get("gap_after", default_gap if idx + 1 < len(beats) else 0.0) or 0.0)
        if gap_after > 0:
            out_chunks.append(np.zeros((int(round(gap_after * sample_rate)), 2), dtype=np.float32))
            cur_sample += int(round(gap_after * sample_rate))

        segments_meta.append({
            "id": b.get("id", f"VO_{idx+1:02d}"),
            "text": b.get("text", ""),
            "file": fpath,
            "start": round(seg_start_s, 3),
            "end": round(seg_end_s, 3),
            "duration": round(seg_end_s - seg_start_s, 3),
            "gap_after": round(gap_after, 3),
        })

    master = np.vstack(out_chunks)
    peak = float(np.max(np.abs(master)))
    if peak > 0.89:
        master = master * (0.89 / peak)
    write_wav_pcm16(out_wav, master, sample_rate=sample_rate)

    payload = {
        "mode": "manifest",
        "output_wav": os.path.abspath(out_wav),
        "total_duration": round(len(master) / sample_rate, 3),
        "segment_count": len(segments_meta),
        "lufs_i": measure_ebur128_i(out_wav),
        "segments": segments_meta,
    }
    os.makedirs(os.path.dirname(os.path.abspath(out_json)), exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return payload


def main() -> None:
    p = argparse.ArgumentParser(description="Prepare VO master WAV and locked spoken-beat timestamps")
    p.add_argument("--input", default=None, help="Single VO video/audio file to trim dead air")
    p.add_argument("--manifest", default=None, help="JSON manifest of ordered VO beat files")
    p.add_argument("--out-wav", default=None, help="Output WAV path (required unless --probe-islands)")
    p.add_argument("--out-json", default=None, help="Output segments JSON path (required unless --probe-islands)")
    p.add_argument("--probe-islands", action="store_true", help="Inspect speech islands and inter-phrase gaps only")
    p.add_argument("--silence-db", type=float, default=-38.0)
    p.add_argument("--min-silence", type=float, default=0.28)
    p.add_argument("--keep-gap", type=float, default=0.12)
    p.add_argument("--act-gap", type=float, default=0.25)
    p.add_argument("--speed", type=float, default=1.0)
    args = p.parse_args()

    if args.probe_islands:
        if not args.input:
            raise SystemExit("--probe-islands requires --input")
        eff_sil_db = args.silence_db if args.silence_db != -38.0 else -39.0
        eff_min_sil = args.min_silence if args.min_silence != 0.28 else 0.08
        res = probe_islands(
            args.input,
            silence_db=eff_sil_db,
            min_silence=eff_min_sil,
            speed=args.speed,
        )
        if args.out_json:
            os.makedirs(os.path.dirname(os.path.abspath(args.out_json)), exist_ok=True)
            with open(args.out_json, "w", encoding="utf-8") as f:
                json.dump(res, f, ensure_ascii=False, indent=2)
    elif args.manifest:
        if not args.out_wav or not args.out_json:
            raise SystemExit("--manifest requires both --out-wav and --out-json")
        res = build_manifest_vo(
            args.manifest,
            args.out_wav,
            args.out_json,
            default_gap=args.keep_gap,
            silence_db=args.silence_db,
            min_silence=args.min_silence,
        )
    elif args.input:
        if not args.out_wav or not args.out_json:
            raise SystemExit("--input requires both --out-wav and --out-json")
        res = trim_single_vo(
            args.input,
            args.out_wav,
            args.out_json,
            silence_db=args.silence_db,
            min_silence=args.min_silence,
            keep_gap=args.keep_gap,
            act_gap=args.act_gap,
            speed=args.speed,
        )
    else:
        raise SystemExit("Provide --probe-islands --input, --input, or --manifest")
    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
