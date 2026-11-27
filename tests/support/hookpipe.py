"""hookpipe 테스트용 대역: 과금 호출 대신 ffmpeg 로 작은 영상·음성·이미지를 만든다."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from hookpipe.media import MediaError, MediaTools, find_tools, run_ffmpeg  # noqa: E402


def tools_or_none() -> Optional[MediaTools]:
    try:
        tools = find_tools()
    except MediaError:
        return None
    needed = ("testsrc", "sine", "color", "concat", "loudnorm", "scale", "crop", "fps", "trim")
    return tools if all(tools.has_filter(name) for name in needed) else None


def make_video(
    tools: MediaTools,
    path: Path,
    *,
    seconds: float,
    width: int = 360,
    height: int = 640,
    audio: bool = True,
    fps: int = 24,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    args = ["-f", "lavfi", "-i", f"testsrc=size={width}x{height}:rate={fps}:duration={seconds}"]
    if audio:
        args += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}"]
    args += ["-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p"]
    if audio:
        args += ["-c:a", "aac", "-shortest"]
    run_ffmpeg(tools, [*args, str(path)])
    return path


class FakeMediaProvider:
    """GenAIMediaProvider 와 같은 세 메서드를 가진 대역. 호출 내용을 기록한다."""

    def __init__(self, tools: MediaTools, *, seconds_per_char: float = 0.09, fail_image: bool = False) -> None:
        self.tools = tools
        self.seconds_per_char = seconds_per_char
        self.fail_image = fail_image
        self.tts_calls: List[Dict[str, Any]] = []
        self.image_calls: List[Dict[str, Any]] = []
        self.video_calls: List[Dict[str, Any]] = []

    def generate_tts_beat(self, text: str, out_wav_path: Any, *, voice_name: Optional[str] = None, **_: Any) -> None:
        seconds = max(0.4, round(len(text) * self.seconds_per_char, 2))
        self.tts_calls.append({"text": text, "voice": voice_name, "seconds": seconds})
        target = Path(out_wav_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        run_ffmpeg(
            self.tools,
            ["-f", "lavfi", "-i", f"sine=frequency=330:duration={seconds}", "-ar", "24000", "-ac", "1", str(target)],
        )

    def generate_reference_image(self, prompt: str, out_path: Any, **kwargs: Any) -> None:
        self.image_calls.append({"prompt": prompt, **kwargs})
        if self.fail_image:
            raise RuntimeError("image model unavailable")
        target = Path(out_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        run_ffmpeg(self.tools, ["-f", "lavfi", "-i", "color=c=teal:s=180x320", "-frames:v", "1", str(target)])

    def generate_video_clip(
        self,
        prompt: str,
        out_path: Any,
        *,
        aspect_ratio: str = "9:16",
        duration_sec: int = 5,
        resolution: str = "720p",
        reference_paths: Any = None,
        **_: Any,
    ) -> None:
        self.video_calls.append(
            {
                "prompt": prompt,
                "aspect_ratio": aspect_ratio,
                "duration_sec": duration_sec,
                "resolution": resolution,
                "reference_paths": [str(p) for p in (reference_paths or [])],
            }
        )
        make_video(self.tools, Path(out_path), seconds=float(duration_sec), audio=False)


def fake_body_writer(prompt: str, frames: Any) -> Dict[str, Any]:
    """본편 대본·컷 고르기 대역: 문장 2개, 클립 1·2번 앞부분."""
    clips = sorted({f["clip"] for f in frames})
    second = clips[1] if len(clips) > 1 else clips[0]
    return {"lines": [
        {"narration": "물기제거 스펀지는 한 손에 쥐어지는 회색 스펀지입니다.", "caption": "한 손에 쥐는\n물기제거 스펀지",
         "shots": [{"clip": clips[0], "start": 0.5, "end": 3.0}]},
        {"narration": "적셔서 짠 뒤 가장자리 물기를 문질러 닦습니다.", "caption": "적셔 짜고\n쓱 닦기",
         "shots": [{"clip": second, "start": 0.0, "end": 2.0}, {"clip": clips[0], "start": 2.0, "end": 4.0}]},
    ]}


def worker_scenario(hook_type: str = "B", scenario_id: str = "sc_demo_B1_01") -> Dict[str, Any]:
    """작업자가 돌려주는 모양의 시나리오 (ad_spec 에 timeline 이 없다)."""
    return {
        "scenario_id": scenario_id,
        "round": 1,
        "type": hook_type,
        "hook_title": "문어는 심장이 세 개입니다",
        "hook_duration_sec": 9.0,
        "body_duration_sec": 10.0,
        "replacement_test_note": "반전 장면만 바꾸면 다른 제품에도 붙는다",
        "beats": [
            {"order": 1, "role": "어긋난 시작", "duration_sec": 3.0, "visual": "바닷속 문어 한 마리",
             "narration": "문어는 심장이 세 개입니다.", "caption": "심장이 세 개"},
            {"order": 2, "role": "브리지", "duration_sec": 3.0, "visual": "심장 세 개가 번갈아 뛴다",
             "narration": "두 개는 아가미로 피를 보냅니다.", "caption": "두 개는 아가미로"},
            {"order": 3, "role": "반전: 제품 첫 등장", "duration_sec": 3.0, "visual": "책상 위 타이머가 등장한다",
             "narration": "집중도 나눠 써야 오래갑니다.", "caption": "집중도 나눠 써야"},
        ],
        "ad_spec": {
            "track_archetype": "B_info_hook_offset",
            "product_first_mention_beat": 3,
            "visual_style": "soft diorama",
        },
    }
