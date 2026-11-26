"""Step 1b: Synthesize 3-cast Korean Voiceover for Remarried Empress Office Parody:
- Boss (Team Leader): Inworld TTS (snowy-otter-1773__leesiu_docu_kr)
- Ace Employee ("Empress"): edge-tts ko-KR-SunHiNeural (icy calm authority)
- Rival CEO ("Prince"): edge-tts ko-KR-InJoonNeural (confident charismatic)
Reads INWORLD_AUTH strictly from environment (never persisted to disk).
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

ROOT = "/Users/yun-yeowon/workspace/ad-studio/ps2-remarried-office"
VO_DIR = os.path.join(ROOT, "audio", "vo")
TIMELINE_JSON = os.path.join(ROOT, "audio", "vo_timeline.json")
SR = 48000

INWORLD_VOICE_ID = "snowy-otter-1773__leesiu_docu_kr"

SLOTS: List[Dict] = [
    {
        "id": "v1_boss_fire",
        "text": "자네, 이번 분기까지만 하고... 회사를 떠나주게.",
        "caption": "자네, 이번 분기까지만 하고 회사를 떠나주게.",
        "speaker": "꼰대 팀장",
        "engine": "inworld",
        "start": 0.08,
        "max_end": 2.65,
    },
    {
        "id": "v2_boss_smug",
        "text": "자네 없어도 회사는 잘 돌아가니까!",
        "caption": "자네 없어도 회사는 잘 돌아가니까!",
        "speaker": "꼰대 팀장",
        "engine": "inworld",
        "start": 2.70,
        "max_end": 4.55,
    },
    {
        "id": "v3_ace_accept",
        "text": "권고사직을 받아들이겠습니다.",
        "caption": "권고사직을 받아들이겠습니다.",
        "speaker": "에이스 과장",
        "engine": "edge",
        "voice": "ko-KR-HyunsuMultilingualNeural",
        "rate": "+12%",
        "pitch": "+2Hz",
        "start": 4.85,
        "max_end": 6.32,
    },
    {
        "id": "v4_ace_remarry",
        "text": "그리고 경쟁사 연봉 두 배, 이직 승인을 요구합니다!",
        "caption": "그리고 경쟁사 연봉 두 배, 이직 승인을 요구합니다!",
        "speaker": "에이스 과장",
        "engine": "edge",
        "voice": "ko-KR-HyunsuMultilingualNeural",
        "rate": "+14%",
        "pitch": "+3Hz",
        "start": 6.38,
        "max_end": 8.65,
    },
    {
        "id": "v5_ceo_scout",
        "text": "과장님, 연봉 두 배에 임원 대우 준비했습니다. 바로 가시죠!",
        "caption": "과장님, 연봉 두 배에 임원 대우 준비했습니다. 바로 가시죠!",
        "speaker": "경쟁사 대표",
        "engine": "edge",
        "voice": "ko-KR-InJoonNeural",
        "rate": "+24%",
        "pitch": "-5Hz",
        "start": 8.88,
        "max_end": 11.82,
    },
    {
        "id": "v6_boss_meltdown",
        "text": "뭐?! 연봉 두 배?! 자네가 가면 우리 팀 실적은 어쩌라고!!",
        "caption": "뭐?! 연봉 두 배?! 자네가 가면 우리 팀 실적은 어쩌라고!!",
        "speaker": "꼰대 팀장",
        "engine": "inworld",
        "start": 11.88,
        "max_end": 14.96,
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
            "User-Agent": "Antigravity-RemarriedParody/1.0",
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
    missing = [s for s in SLOTS if not os.path.exists(os.path.join(VO_DIR, f"{s['id']}.mp3"))]
    if not missing:
        return
    auth = os.environ.get("INWORLD_AUTH", "").strip()
    if any(s["engine"] == "inworld" for s in missing) and not auth:
        raise RuntimeError("Missing INWORLD_AUTH environment variable!")

    for slot in missing:
        mp3_path = os.path.join(VO_DIR, f"{slot['id']}.mp3")
        if slot["engine"] == "inworld":
            synth_inworld(slot["text"], mp3_path, auth)
        else:
            comm = edge_tts.Communicate(
                slot["text"], slot["voice"],
                rate=slot["rate"], pitch=slot["pitch"],
            )
            await comm.save(mp3_path)


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

        max_dur = max(0.35, slot["max_end"] - slot["start"] - 0.03)
        tempo = max(1.0, min(1.52, trim_dur / max_dur))
        cmd = ["ffmpeg", "-y", "-i", trim_wav]
        if tempo > 1.01:
            cmd += ["-filter:a", f"atempo={tempo:.4f}"]
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
        })
        print(f"[vo:{slot['engine']}] {slot['id']}: {slot['start']:.2f}s -> {slot['start'] + final_dur:.2f}s (dur={final_dur:.2f}s, tempo={tempo:.2f}x) | {slot['caption']}", flush=True)

    with open(TIMELINE_JSON, "w", encoding="utf-8") as f:
        json.dump(timeline, f, ensure_ascii=False, indent=2)
    print(f"[vo] Saved timeline: {TIMELINE_JSON}", flush=True)


if __name__ == "__main__":
    asyncio.run(synth_all_mp3())
    trim_and_prepare()
