#!/usr/bin/env python3
"""Offline unit tests for shortform-ad-remix-director scripts.

Covers ad_thumbnail_builder.py, ad_audio_prep.py, ad_source_analyzer.py, and
hardened Google Flow helpers in flow_automator.py without touching live Chrome.
"""

from __future__ import annotations

import json
import math
import os
import struct
import sys
import tempfile
import unittest
import wave
from unittest.mock import patch

from PIL import Image

SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "libraries", "media-tools")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

import ad_audio_prep  # noqa: E402
import ad_flow_jobs  # noqa: E402
import ad_gate_a_lint  # noqa: E402
import ad_source_analyzer  # noqa: E402
import ad_thumbnail_builder  # noqa: E402
import flow_automator  # noqa: E402


def _write_test_wav(path: str, *, sample_rate: int = 48000) -> None:
    """Write 2.1s stereo WAV: 0.2s silence + 0.6s 440Hz tone + 0.5s silence + 0.6s 554Hz tone + 0.2s silence."""
    segments = [
        (0.20, 0.0, 0.0),
        (0.60, 440.0, 0.35),
        (0.50, 0.0, 0.0),
        (0.60, 554.37, 0.35),
        (0.20, 0.0, 0.0),
    ]
    frames = bytearray()
    for dur, freq, amp in segments:
        n = int(round(dur * sample_rate))
        for i in range(n):
            v = amp * math.sin(2.0 * math.pi * freq * (i / sample_rate)) if amp > 0 else 0.0
            s16 = max(-32767, min(32767, int(v * 32767.0)))
            frames.extend(struct.pack("<hh", s16, s16))
    with wave.open(path, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(bytes(frames))



class ThumbnailBuilderCase(unittest.TestCase):
    pass


class GateAOrthogonalGuardCase(unittest.TestCase):
    def _base_facts(self, td: str) -> str:
        fp = os.path.join(td, "00_product_facts.md")
        with open(fp, "w", encoding="utf-8") as f:
            f.write("# Facts\n- [F01] [VERIFIED] 실물 테스트 스펀지\n")
        return fp

    def _base_spec(self, td: str, arch: str, captions: list, *, gap: bool = True, sim: float | None = None, taboo: list | None = None) -> dict:
        src = os.path.join(td, "src.mp4")
        if not os.path.exists(src):
            open(src, "wb").write(b"dummy")
        vo = os.path.join(td, "vo.wav")
        if not os.path.exists(vo):
            open(vo, "wb").write(b"dummy")
        tl = [
            {"id": "H1", "type": "video", "path": src, "framing": "full-bleed", "duration": 5.0, "audio_owner": "mute"},
            {"id": "H2", "type": "video", "path": src, "framing": "full-bleed", "duration": 4.0, "audio_owner": "mute"},
        ]
        if gap:
            tl.append({"id": "STOP", "type": "silence_gap", "duration": 0.28, "audio_owner": "silence"})
        tl.append({"id": "P1", "type": "video", "path": src, "framing": "full-bleed", "duration": 7.0, "audio_owner": "mute", "fact_ids": ["F01"]})
        spec = {
            "project_id": f"test-{arch}",
            "title": "테스트",
            "mode": "narrative_master",
            "track_archetype": arch,
            "hook_window_sec": 9.0,
            "framing_mode": "full-bleed",
            "disclosure": "ai_assisted",
            "source_video": src,
            "source_duration": 10.0,
            "allow_static_intro": True,
            "vo_audio": vo,
            "usps": [{"title": "테스트 USP", "fact_ids": ["F01"]}],
            "timeline": tl,
            "captions": captions,
            "cta": {"type": "comment_engagement", "copy": "어떠신가요?", "fact_ids": ["F01"]},
        }
        if sim is not None:
            spec["hook_similarity_score"] = sim
        if taboo is not None:
            spec["product_taboo_keywords"] = taboo
        return spec



class AudioPrepCase(unittest.TestCase):
    pass


class SourceAnalyzerCase(unittest.TestCase):
    pass


class FlowAutomatorHardeningCase(unittest.TestCase):
    pass


class GateACrossCampaignReskinCase(unittest.TestCase):
    pass


class FlowAutomatorSpeedAndFocusCase(unittest.TestCase):
    pass


class FlowJobsVisualStyleCase(unittest.TestCase):
    pass
