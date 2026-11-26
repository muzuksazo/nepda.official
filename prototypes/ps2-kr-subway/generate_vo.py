"""Generate 7 Hero Korean Voiceover lines via Inworld TTS (snowy-otter-1773__leesiu_docu_kr)
plus 2 Seoul Metro PA announcements via edge-tts + bandpass filter, with non-clipped pacing.
Reads INWORLD_AUTH strictly from environment (never stored on disk).
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import subprocess
import urllib.request
import wave
from typing import Dict, List

import edge_tts
import numpy as np

ROOT = "/Users/yun-yeowon/workspace/ad-studio/ps2-kr-subway"
VO_DIR = os.path.join(ROOT, "audio", "vo")
TIMELINE_JSON = os.path.join(ROOT, "audio", "vo_timeline.json")
SR = 48000

INWORLD_VOICE_ID = "snowy-otter-1773__leesiu_docu_kr"
VOICE_PA = "ko-KR-SunHiNeural"

SLOTS: List[Dict] = [
    {
        "id": "v1_cocky",
        "text": "한국 이호선? 에이, 설마 못 타겠어?",
        "caption": "한국 2호선? 에이, 설마 못 타겠어?",
        "speaker": "민수",
        "start": 0.06,
        "max_end": 2.12,
        "pa": False,
    },
    {
        "id": "v2_shock",
        "text": "어? 여기 완전 사람 벽인데?!",
        "caption": "어? 여기 완전 사람 벽인데?!",
        "speaker": "민수",
        "start": 2.16,
        "max_end": 3.58,
        "pa": False,
    },
    {
        "id": "v3_push",
        "text": "실례합니다! 좀 밀겠습니다!",
        "caption": "실례합니다! 좀 밀겠습니다!",
        "speaker": "민수",
        "start": 3.62,
        "max_end": 5.02,
        "pa": False,
    },
    {
        "id": "v4_bounce",
        "text": "아악! 튕겨 나왔어! 이거 보스전이야?!",
        "caption": "아악! 튕겨 나왔어! 이거 보스전이야?!",
        "speaker": "민수",
        "start": 5.06,
        "max_end": 6.74,
        "pa": False,
    },
    {
        "id": "v5_pa_close",
        "text": "출입문 닫습니다.",
        "caption": "[안내방송] 출입문 닫습니다.",
        "speaker": "안내방송",
        "start": 6.78,
        "max_end": 7.80,
        "pa": True,
    },
    {
        "id": "v6_rush",
        "text": "지각이야! 아 몰라, 등부터 밀어!",
        "caption": "지각이야! 아 몰라, 등부터 밀어!",
        "speaker": "민수",
        "start": 7.84,
        "max_end": 9.85,
        "pa": False,
    },
    {
        "id": "v7_relief",
        "text": "휴... 겨우 탔다... 살았다...",
        "caption": "휴... 겨우 탔다... 살았다...",
        "speaker": "민수",
        "start": 10.10,
        "max_end": 12.06,
        "pa": False,
    },
    {
        "id": "v8_pa_twist",
        "text": "이 열차는 반대 방향, 성수행입니다.",
        "caption": "[안내방송] 이 열차는 반대 방향, 성수행입니다.",
        "speaker": "안내방송",
        "start": 12.10,
        "max_end": 13.78,
        "pa": True,
    },
    {
        "id": "v9_scream",
        "text": "뭐?! 반대 방향이라고?!",
        "caption": "뭐?! 반대 방향이라고?!",
        "speaker": "민수",
        "start": 13.82,
        "max_end": 14.96,
        "pa": False,
    },
]


def synth_inworld(text: str, out_mp3: str, auth: str) -> None:
    payload = json.dumps({
        "text": text,
        "voiceId": INWORLD_VOICE_ID,
        "modelId": "inworld-tts-2",
        "audioConfig": {"audioEncoding": "MP3"},
    }, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        "https://api.inworld.ai/tts/v1/voice",
        data=payload,
        headers={
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/json",
            "User-Agent": "Antigravity-PS2Story/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        res = json.loads(resp.read().decode("utf-8"))
    raw = base64.b64decode(res["audioContent"])
    with open(out_mp3, "wb") as f:
        f.write(raw)


async def synth_all_mp3() -> None:
    os.makedirs(VO_DIR, exist_ok=True)
    auth = os.environ.get("INWORLD_AUTH", "").strip()
    if not auth:
        raise RuntimeError("Missing INWORLD_AUTH environment variable!")

    for slot in SLOTS:
        mp3_path = os.path.join(VO_DIR, f"{slot['id']}.mp3")
        if slot["pa"]:
            comm = edge_tts.Communicate(slot["text"], VOICE_PA, rate="+18%", pitch="+0Hz")
            await comm.save(mp3_path)
        else:
            synth_inworld(slot["text"], mp3_path, auth)


def trim_and_prepare() -> None:
    timeline: List[Dict] = []
    for slot in SLOTS:
        mp3_path = os.path.join(VO_DIR, f"{slot['id']}.mp3")
        raw_wav = os.path.join(VO_DIR, f"{slot['id']}_raw.wav")
        trim_wav = os.path.join(VO_DIR, f"{slot['id']}_trim.wav")
        out_wav = os.path.join(VO_DIR, f"{slot['id']}.wav")

        subprocess.run([
            "ffmpeg", "-y", "-i", mp3_path, "-ac", "1", "-ar", str(SR), raw_wav,
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

        with wave.open(raw_wav, "rb") as wf:
            pcm = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
        nz = np.where(np.abs(pcm) > 0.015)[0]
        i0 = max(0, int(nz[0] - 0.020 * SR)) if len(nz) else 0
        i1 = min(len(pcm), int(nz[-1] + 0.045 * SR)) if len(nz) else len(pcm)
        trimmed = pcm[i0:i1]
        trim_dur = len(trimmed) / float(SR)

        with wave.open(trim_wav, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SR)
            wf.writeframes((np.clip(trimmed, -0.99, 0.99) * 32767.0).astype(np.int16).tobytes())

        max_dur = max(0.35, slot["max_end"] - slot["start"] - 0.02)
        tempo = max(1.0, min(1.56, trim_dur / max_dur))
        af_parts = [f"atempo={tempo:.4f}"] if tempo > 1.01 else []
        if slot["pa"]:
            af_parts.append("highpass=f=480,lowpass=f=2700,acompressor=threshold=-16dB:ratio=4,aecho=0.8:0.7:40:0.25")

        cmd = ["ffmpeg", "-y", "-i", trim_wav]
        if af_parts:
            cmd += ["-filter:a", ",".join(af_parts)]
        cmd += ["-ac", "1", "-ar", str(SR), out_wav]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

        with wave.open(out_wav, "rb") as wf:
            final_dur = wf.getnframes() / float(SR)

        for p in (raw_wav, trim_wav):
            if os.path.exists(p):
                os.remove(p)

        timeline.append({
            "id": slot["id"],
            "wav": out_wav,
            "start": round(slot["start"], 3),
            "end": round(min(15.0, slot["start"] + final_dur), 3),
            "dur": round(final_dur, 3),
            "speaker": slot["speaker"],
            "caption": slot["caption"],
            "pa": slot["pa"],
        })
        src_tag = "edge-PA" if slot["pa"] else "Inworld"
        print(f"[vo:{src_tag}] {slot['id']}: {slot['start']:.2f}s -> {slot['start'] + final_dur:.2f}s (dur={final_dur:.2f}s, tempo={tempo:.2f}x) | {slot['caption']}", flush=True)

    with open(TIMELINE_JSON, "w", encoding="utf-8") as f:
        json.dump(timeline, f, ensure_ascii=False, indent=2)
    print(f"[vo] Saved timeline: {TIMELINE_JSON}", flush=True)


if __name__ == "__main__":
    if not all(os.path.exists(os.path.join(VO_DIR, f"{s['id']}.mp3")) for s in SLOTS):
        asyncio.run(synth_all_mp3())
    trim_and_prepare()
