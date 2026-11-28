"""본편 편집 (FR-009): 올린 촬영 영상 → 10초 설명 영상(나레이션 + 자막). A·B·C 훅이 함께 쓴다.

B 트랙의 본편 단계(bridge-dev/b/src/body.ts)를 Python + ffmpeg 로 옮긴 것이다.
  1) 클립마다 프레임 5장을 뽑아 글 모델에 보여 준다
  2) 모델이 제품 사실만으로 2~3문장 대본을 쓰고, 문장마다 맞는 컷(클립 번호와 시작·끝 초)을 고른다
  3) 문장별 나레이션 → 음성 길이에 맞춰 컷을 자르고, 전체를 정확히 target_sec 으로 맞춘다
  4) 1080x1920 30fps, 자막 번인, 소리 -14 LUFS 의 body.mp4 와 body.srt
결과는 프로젝트마다 한 번 만들어 두고(같은 촬영본·제품 정보·설정이면 재사용) 모든 훅 유형에 붙인다.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

from .captions import build_srt
from .media import (
    AUDIO_ENCODE_ARGS,
    AUDIO_RATE,
    OUT_FPS,
    OUT_H,
    OUT_W,
    VIDEO_ENCODE_ARGS,
    MediaError,
    MediaTools,
    fill_filter,
    gain_filter,
    gain_to_target,
    measure_lufs,
    probe,
    run_ffmpeg,
)

logger = logging.getLogger("hookpipe.body_edit")

FRAME_SPOTS = (0.1, 0.3, 0.5, 0.7, 0.9)
LINE_GAP_SEC = 0.3  # 문장 사이 숨
MAX_TEMPO = 1.3
MIN_SHOT_SEC = 0.8
LANDSCAPE_RATIO = 0.92

BODY_SCRIPT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["lines"],
    "properties": {
        "cta_badge": {"type": "string"},
        "lines": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["narration", "caption", "shots"],
                "properties": {
                    "narration": {"type": "string"},
                    "caption": {"type": "string"},
                    "shots": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["clip", "start", "end"],
                            "properties": {
                                "clip": {"type": "integer"},
                                "start": {"type": "number"},
                                "end": {"type": "number"},
                            },
                        },
                    },
                },
            },
        },
    },
}

ScriptWriter = Callable[[str, List[Dict[str, Any]]], Dict[str, Any]]


class BodyEditError(RuntimeError):
    """본편을 만들 수 없을 때."""


@dataclass
class Clip:
    index: int
    path: Path
    duration: float
    width: int
    height: int


@dataclass
class BodyEditResult:
    video: Path
    srt: Path
    duration_sec: float
    lufs: Optional[float]
    script: Dict[str, Any]
    reused: bool = False
    warnings: List[str] = field(default_factory=list)


def body_cache_key(
    clips: Sequence[Path],
    product: Dict[str, Any],
    settings: Any,
    voice: Optional[str] = None,
    opening_callback: Optional[str] = None,
) -> str:
    """같은 촬영본·제품 정보·설정·목소리·도입 콜백이면 같은 본편을 쓴다."""
    parts: List[str] = ["body_v2_commercial_cta"]
    if voice:
        parts.append(f"voice:{voice}")
    cb = str(opening_callback or "").strip()
    if cb:
        parts.append(f"callback:{cb}")
    for path in clips:
        stat = Path(path).stat()
        parts.append(f"{Path(path).name}:{stat.st_size}:{int(stat.st_mtime)}")
    parts.append(
        json.dumps(
            {k: product.get(k) for k in ("name", "call_name", "verified_facts", "price_or_offer")},
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    for name in ("body_target_sec", "body_llm", "tts_provider", "inworld_voice_id", "tts_default_voice"):
        parts.append(str(getattr(settings, name, "")))
    return hashlib.sha1("\x1f".join(parts).encode("utf-8")).hexdigest()[:16]


def _body_prompt(
    product: Dict[str, Any],
    clips: List[Clip],
    target: float,
    *,
    opening_callback: Optional[str] = None,
) -> str:
    name = product.get("call_name") or product.get("name") or "제품"
    facts = [str(f) for f in (product.get("verified_facts") or []) if str(f).strip()]
    offer = str(product.get("price_or_offer") or "").strip()
    syllables = int(round(target * 5.5))
    ranges = ", ".join(f"{c.index}번 0~{c.duration:.1f}초" for c in clips)
    cb = str(opening_callback or "").strip()
    if cb:
        intro_clause = (
            "이 본편은 A안 반전 훅 직후 바로 이어집니다. 첫 문장(lines[0].narration)은 아래 반전 전환 콜백 문구로 "
            f"자연스럽게 열어 제품 이름(\"{name}\")과 바로 연결하세요.\n"
            f"반전 전환 콜백 오프닝: \"{cb}\"\n"
        )
        line1_rule = (
            f"- Line 1 (전환 & 제품명): 위 반전 전환 콜백(\"{cb}\")을 자연스럽게 살려 "
            f"정확한 제품 이름(\"{name}\")을 부르고 무엇인지 소개합니다.\n"
        )
    else:
        intro_clause = "이 본편은 어떤 훅 영상 뒤에도 붙으므로, 훅 내용과 상관없이 제품만 설명합니다.\n"
        line1_rule = f"- Line 1 (도입 & 제품명): 정확한 제품 이름(\"{name}\")을 부르고 무엇인지 소개합니다.\n"
    offer_line = f"가격/혜택(입력된 내용만 사용): {offer}\n" if offer else ""
    offer_closer = f" + 입력된 가격/혜택(\"{offer}\") 반영" if offer else ""
    cta_offer_hint = ", 입력된 가격/혜택이 있으면 짧게 반영 가능" if offer else ""
    return (
        f"판매자가 직접 찍은 제품 촬영 영상으로 {target:g}초짜리 상업용 제품 설명 영상(본편)을 만듭니다. "
        + intro_clause
        + f"제품: {product.get('name', '')} (나레이션에서 부르는 이름: \"{name}\")\n"
        + offer_line
        + "제품 사실(이것만 말합니다):\n" + "\n".join(f"- {f}" for f in facts) + "\n\n"
        + "대본 규칙 (3단 커머셜 본편 구조, lines 길이 3):\n"
        + f"- 정확히 3문장(lines 3개), 나레이션 전체 {syllables}음절 이내. 짧고 또렷하게, '~습니다'체.\n"
        + line1_rule
        + "- Line 2 (검증된 핵심 효능): 위 제품 사실(verified_facts)에 있는 핵심 효능만 말합니다.\n"
        + f"- Line 3 (클로징 / CTA): 제품 이름(\"{name}\")을 다시 각인하며 훅을 깔끔하게 회수하는 클로징 펀치"
        + offer_closer
        + " + 행동 유도(예: \"지금 프로필 링크에서 확인해 보세요.\" 또는 재치 있는 마감).\n"
        + "- 입력되지 않은 가격·할인이나 제품 사실에 없는 과장·기능은 절대 지어내지 않습니다.\n"
        + "- caption: 짧은 구어 자막, 한 줄 12자 안팎, 최대 2줄(\\n).\n"
        + f"- cta_badge: 엔드카드 CTA 필에 들어갈 8~14자 짧은 문구 (이모지 금지, 예: \"프로필 링크에서 확인 →\"{cta_offer_hint}).\n"
        + "컷 규칙:\n"
        + "- 아래 프레임에는 클립 번호와 시각(초)이 붙어 있습니다. 문장마다 그 말과 가장 잘 맞는 장면을 "
        + "클립 번호와 시작·끝 초로 고릅니다(문장당 1~2개, 한 컷 1.5초 이상).\n"
        + "- 흔들리거나 흐린 부분, 손이 제품을 가리는 부분, 제품이 안 보이는 부분은 피합니다. 같은 장면을 반복하지 않습니다.\n"
        + f"- 시작·끝은 그 클립 길이 안에서: {ranges}."
    )


def gemini_script_writer(settings: Any) -> ScriptWriter:
    """글 모델(Gemini)로 대본과 컷을 고른다. 프레임 이미지를 함께 보낸다."""

    def _write(prompt: str, frames: List[Dict[str, Any]]) -> Dict[str, Any]:
        import time
        from google.genai import types

        from app.genai_provider import build_genai_client

        client = build_genai_client(settings)  # 변수에 담아 둔다 (요청 도중 닫히지 않게)
        model_id = str(getattr(settings, "body_llm", "") or "gemini-4-hydrogen")
        parts: List[Any] = [types.Part.from_text(text=prompt)]
        for frame in frames:
            parts.append(types.Part.from_text(text=f"클립 {frame['clip']}번 {frame['t']:.1f}초"))
            parts.append(types.Part.from_bytes(data=Path(frame["path"]).read_bytes(), mime_type="image/jpeg"))
        budget = int(getattr(settings, "llm_thinking_budget", 1024) or 0)
        config_kwargs: Dict[str, Any] = {
            "response_mime_type": "application/json",
            "response_json_schema": BODY_SCRIPT_SCHEMA,
        }
        if budget > 0 and hasattr(types, "ThinkingConfig"):
            config_kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=budget)
        t0 = time.monotonic()
        response = client.models.generate_content(
            model=model_id,
            contents=[types.Content(role="user", parts=parts)],
            config=types.GenerateContentConfig(**config_kwargs),
        )
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        text = getattr(response, "text", None) or ""
        on_usage = getattr(settings, "_on_usage", None)
        if callable(on_usage):
            usage = getattr(response, "usage_metadata", None)
            on_usage(
                stage="body_script",
                step_name="body_cuts_script",
                provider="google",
                model=model_id,
                input_tokens=int(getattr(usage, "prompt_token_count", 0) or 0),
                output_tokens=int(getattr(usage, "candidates_token_count", 0) or 0),
                cached_tokens=int(getattr(usage, "cached_content_token_count", 0) or 0),
                thinking_tokens=int(getattr(usage, "thoughts_token_count", 0) or 0),
                latency_ms=elapsed_ms,
                metadata={"prompt_preview": prompt[:500], "response_preview": text[:800]},
            )
        try:
            return json.loads(text)
        except ValueError as exc:
            raise BodyEditError(f"본편 대본 응답을 읽지 못했습니다: {text[:200]!r}") from exc

    return _write


def claude_script_writer(settings: Any) -> ScriptWriter:
    """글 모델(Claude)로 대본과 컷을 고른다. 프레임 이미지를 함께 보내고, 출력은 같은 JSON 스키마로 받는다."""

    def _write(prompt: str, frames: List[Dict[str, Any]]) -> Dict[str, Any]:
        import base64
        import time

        import anthropic

        content: List[Dict[str, Any]] = [{"type": "text", "text": prompt}]
        for frame in frames:
            content.append({"type": "text", "text": f"클립 {frame['clip']}번 {frame['t']:.1f}초"})
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": base64.standard_b64encode(Path(frame["path"]).read_bytes()).decode("ascii"),
                },
            })
        client = anthropic.Anthropic()  # ANTHROPIC_API_KEY
        model_id = str(getattr(settings, "body_llm", "") or "claude-opus-5-5")
        t0 = time.monotonic()
        response = client.messages.create(
            model=model_id,
            max_tokens=8000,
            messages=[{"role": "user", "content": content}],
            output_config={"format": {"type": "json_schema", "schema": BODY_SCRIPT_SCHEMA}},
        )
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        text = "".join(block.text for block in response.content if getattr(block, "type", "") == "text")
        on_usage = getattr(settings, "_on_usage", None)
        if callable(on_usage):
            usage = getattr(response, "usage", None)
            on_usage(
                stage="body_script",
                step_name="body_cuts_script",
                provider="anthropic",
                model=str(getattr(response, "model", None) or model_id),
                input_tokens=int(getattr(usage, "input_tokens", 0) or 0),
                output_tokens=int(getattr(usage, "output_tokens", 0) or 0),
                cached_tokens=int(getattr(usage, "cache_read_input_tokens", 0) or 0),
                latency_ms=elapsed_ms,
                metadata={"prompt_preview": prompt[:500], "response_preview": text[:800]},
            )
        if response.stop_reason == "refusal":
            raise BodyEditError("Claude 가 본편 대본 요청을 거절했습니다.")
        try:
            return json.loads(text)
        except ValueError as exc:
            raise BodyEditError(f"본편 대본 응답을 읽지 못했습니다: {text[:200]!r}") from exc

    return _write


def default_script_writer(settings: Any) -> ScriptWriter:
    """BODY_LLM 이 claude-… 면 Claude, 아니면 Gemini."""
    model = str(getattr(settings, "body_llm", "") or "").strip().lower()
    return claude_script_writer(settings) if model.startswith("claude") else gemini_script_writer(settings)


def _clean_script(raw: Dict[str, Any], clips: List[Clip]) -> List[Dict[str, Any]]:
    lines = []
    for line in (raw or {}).get("lines") or []:
        narration = str(line.get("narration") or "").strip()
        if not narration:
            continue
        shots = []
        for shot in (line.get("shots") or [])[:2]:
            clip = next((c for c in clips if c.index == int(shot.get("clip") or 0)), None)
            if clip is None:
                continue
            start = max(0.0, min(float(shot.get("start") or 0.0), max(0.0, clip.duration - MIN_SHOT_SEC)))
            end = max(start + MIN_SHOT_SEC, min(float(shot.get("end") or start + 2.0), clip.duration))
            shots.append({"clip": clip.index, "start": round(start, 3), "end": round(end, 3)})
        if not shots:  # 모델이 컷을 못 고르면 순서대로 돌려 쓴다
            clip = clips[len(lines) % len(clips)]
            shots = [{"clip": clip.index, "start": 0.0, "end": min(clip.duration, 3.0)}]
        lines.append({"narration": narration, "caption": str(line.get("caption") or "").strip(), "shots": shots})
    if not lines:
        raise BodyEditError("본편 대본이 비어 있습니다.")
    return lines[:3]


def _plan_shots(lines: List[Dict[str, Any]], clips: List[Clip]) -> List[Dict[str, Any]]:
    """문장마다 정해진 길이(line['duration'])를 그 문장의 컷들에 나눠 준다. 클립 끝을 넘지 않게 시작점을 당긴다."""
    shots: List[Dict[str, Any]] = []
    for line in lines:
        wants = [max(0.5, s["end"] - s["start"]) for s in line["shots"]]
        total_want = sum(wants)
        for shot, want in zip(line["shots"], wants):
            clip = next(c for c in clips if c.index == shot["clip"])
            seconds = line["duration"] * want / total_want
            start = shot["start"]
            if start + seconds > clip.duration:
                start = max(0.0, clip.duration - seconds)
            seconds = min(seconds, clip.duration - start)
            shots.append({"clip": clip, "start": round(start, 3), "seconds": round(seconds, 3)})
    # 클립이 짧아 모자란 길이는 마지막 컷의 끝 화면으로 채운다
    return shots


def _render(
    shots: List[Dict[str, Any]],
    narration_mix: Optional[Path],
    out_dir: Path,
    total: float,
    tools: MediaTools,
    *,
    burn_captions: bool,
    subtitle_style: str,
) -> bool:
    args: List[str] = []
    filters: List[str] = []
    for index, shot in enumerate(shots):
        clip: Clip = shot["clip"]
        args += ["-ss", f"{shot['start']:.3f}", "-t", f"{shot['seconds'] + 0.2:.3f}", "-i", str(clip.path)]
        src = f"[{index}:v]trim=0:{shot['seconds']:.3f},setpts=PTS-STARTPTS"
        landscape = clip.height > 0 and clip.width / clip.height > LANDSCAPE_RATIO
        if landscape and tools.has_filter("boxblur") and tools.has_filter("overlay"):
            filters += [
                f"{src},split=2[bg{index}][fg{index}]",
                f"[bg{index}]scale={OUT_W}:{OUT_H}:force_original_aspect_ratio=increase,crop={OUT_W}:{OUT_H},boxblur=24:2[bgb{index}]",
                f"[fg{index}]scale={OUT_W}:-2[fgs{index}]",
                f"[bgb{index}][fgs{index}]overlay=(W-w)/2:(H-h)/2,fps={OUT_FPS},setsar=1,format=yuv420p[v{index}]",
            ]
        else:
            filters += [f"{src}[s{index}]", fill_filter(f"s{index}", f"v{index}")]
    filters.append(f"{''.join(f'[v{i}]' for i in range(len(shots)))}concat=n={len(shots)}:v=1:a=0[vcat]")
    last = "vcat"
    if tools.has_filter("tpad"):
        filters.append(f"[vcat]tpad=stop_mode=clone:stop_duration=2,trim=0:{total:.3f}[vfit]")
        last = "vfit"
    burned = False
    if burn_captions and tools.has_filter("subtitles") and (out_dir / "body.srt").stat().st_size > 0:
        filters.append(f"[{last}]subtitles=body.srt:force_style='{subtitle_style}'[vsub]")
        last, burned = "vsub", True
    audio_index = len(shots)
    if narration_mix is not None:
        gain = gain_to_target(measure_lufs(tools, narration_mix))
        args += ["-i", str(narration_mix)]
        filters.append(f"[{audio_index}:a]{gain_filter(tools, gain)},aresample={AUDIO_RATE}[aout]")
        audio_map = "[aout]"
    else:
        args += ["-f", "lavfi", "-t", f"{total:.3f}", "-i", f"anullsrc=r={AUDIO_RATE}:cl=stereo"]
        audio_map = f"{audio_index}:a"
    cmd = [*args, "-filter_complex", ";".join(filters), "-map", f"[{last}]", "-map", audio_map,
           *VIDEO_ENCODE_ARGS, *AUDIO_ENCODE_ARGS, "-t", f"{total:.3f}", "body.mp4"]
    try:
        run_ffmpeg(tools, cmd, cwd=out_dir)
    except MediaError:
        if not burned:
            raise
        logger.warning("본편 자막 굽기가 실패해 자막 없이 다시 만듭니다.")
        retry = list(cmd)
        retry[retry.index("-filter_complex") + 1] = ";".join(f for f in filters if "subtitles=" not in f)
        prev = "vfit" if tools.has_filter("tpad") else "vcat"
        run_ffmpeg(tools, [(f"[{prev}]" if a == "[vsub]" else a) for a in retry], cwd=out_dir)
        burned = False
    return burned


def make_body(
    clip_paths: Sequence[str | Path],
    product: Dict[str, Any],
    out_dir: str | Path,
    *,
    provider: Any,
    settings: Any,
    tools: MediaTools,
    writer: Optional[ScriptWriter] = None,
    voice: Optional[str] = None,
    subtitle_style: str = "",
    opening_callback: Optional[str] = None,
) -> BodyEditResult:
    """촬영 영상들 → body.mp4 + body.srt (out_dir 에). 이미 같은 결과가 있으면 그대로 돌려준다."""
    target = float(getattr(settings, "body_target_sec", 10.0) or 10.0)
    out = Path(out_dir)
    done = out / "body.json"
    if done.is_file() and (out / "body.mp4").is_file():
        meta = json.loads(done.read_text(encoding="utf-8"))
        script_meta = dict(meta.get("script") or {})
        if not str(script_meta.get("cta_badge") or "").strip():
            script_meta["cta_badge"] = str(product.get("price_or_offer") or "").strip()[:16] or "프로필 링크에서 확인 →"
        return BodyEditResult(video=out / "body.mp4", srt=out / "body.srt", duration_sec=meta["duration_sec"],
                              lufs=meta.get("lufs"), script=script_meta, reused=True, warnings=meta.get("warnings", []))
    work = out / "_work"
    (work / "frames").mkdir(parents=True, exist_ok=True)
    warnings: List[str] = []

    clips: List[Clip] = []
    for path in clip_paths:
        info = probe(tools, path)
        if info.has_video and info.duration > 0.5:
            clips.append(Clip(len(clips) + 1, Path(path), info.duration, info.width, info.height))
    if not clips:
        raise BodyEditError("본편으로 쓸 수 있는 촬영 영상이 없습니다.")

    # 1) 프레임
    frames: List[Dict[str, Any]] = []
    for clip in clips:
        for spot in FRAME_SPOTS:
            t = round(clip.duration * spot, 2)
            target_jpg = work / "frames" / f"clip{clip.index}_{t:.2f}.jpg"
            if not target_jpg.is_file():
                run_ffmpeg(tools, ["-ss", f"{t:.3f}", "-i", str(clip.path), "-frames:v", "1", "-vf", "scale=270:-2",
                                   "-q:v", "4", str(target_jpg)], timeout=60.0)
            frames.append({"clip": clip.index, "t": t, "path": str(target_jpg)})

    # 2) 대본·컷
    script_raw = (writer or default_script_writer(settings))(
        _body_prompt(product, clips, target, opening_callback=opening_callback),
        frames,
    )
    lines = _clean_script(script_raw, clips)

    # 3) 문장별 나레이션 → 길이 맞추기
    tts_ext = getattr(provider, "tts_extension", ".wav")
    voice_name = voice or getattr(settings, "tts_default_voice", None)
    on_usage = getattr(settings, "_on_usage", None)
    publish_artifact = getattr(settings, "_publish_artifact", None)
    tts_label = getattr(provider, "tts_label", "") or getattr(settings, "tts_model", "")
    tts_provider_name = "inworld" if str(tts_label).startswith("inworld:") else "google"
    tts_model_name = (
        str(tts_label).split(":", 2)[1]
        if str(tts_label).startswith("inworld:") and ":" in str(tts_label)
        else str(tts_label or getattr(settings, "tts_model", "") or "gemini-tts")
    )
    for index, line in enumerate(lines, start=1):
        audio = work / f"line_{index:02d}{tts_ext}"
        t_tts = time.monotonic()
        tts_status = "ok"
        try:
            provider.generate_tts_beat(line["narration"], audio, voice_name=voice_name)
        except Exception:
            tts_status = "error"
            raise
        finally:
            if callable(on_usage):
                obj_key: Optional[str] = None
                if tts_status == "ok" and callable(publish_artifact) and audio.is_file():
                    try:
                        obj_key = publish_artifact("body_tts", f"line_{index}", audio)
                    except Exception:
                        obj_key = None
                ev_meta: Dict[str, Any] = {"text": str(line["narration"])[:300], "voice": str(voice_name or "")}
                if obj_key:
                    ev_meta["object_key"] = obj_key
                on_usage(
                    stage="body_tts",
                    step_name=f"line_{index}",
                    provider=tts_provider_name,
                    model=tts_model_name,
                    media_unit="char",
                    media_qty=float(len(line["narration"])),
                    cache_hit=False,
                    latency_ms=int((time.monotonic() - t_tts) * 1000),
                    status=tts_status,
                    metadata=ev_meta,
                )
        line["audio"] = audio
        line["voice_sec"] = probe(tools, audio).duration
    spoken = sum(line["voice_sec"] for line in lines) + LINE_GAP_SEC * len(lines)
    tempo = 1.0
    if spoken > target:
        tempo = min(MAX_TEMPO, spoken / target)
        if spoken / tempo > target + 0.05:
            warnings.append(f"본편 나레이션이 길어 {target:g}초 안에 다 들어가지 않습니다 (끝이 잘림).")
    natural = [line["voice_sec"] / tempo + LINE_GAP_SEC for line in lines]
    spare = max(0.0, target - sum(natural))
    for line, base in zip(lines, natural):  # 남는 시간은 문장 길이 비율로 나눠 준다
        line["duration"] = base + spare * base / sum(natural)
    scale = target / sum(line["duration"] for line in lines)
    cursor = 0.0
    for line in lines:
        line["duration"] = round(line["duration"] * scale, 3)
        line["start"] = round(cursor, 3)
        cursor += line["duration"]

    # 자막 + 나레이션 트랙
    (out / "body.srt").write_text(
        build_srt([(line["start"], line["start"] + line["duration"], line["caption"] or line["narration"]) for line in lines]),
        encoding="utf-8",
    )
    mix_args: List[str] = []
    mix_filters = [f"anullsrc=r={AUDIO_RATE}:cl=stereo,atrim=0:{target:.3f}[base]"]
    labels = ["[base]"]
    for index, line in enumerate(lines):
        mix_args += ["-i", str(line["audio"])]
        steps = [f"atempo={tempo:.4f}"] if tempo > 1.001 else []
        steps += [f"atrim=0:{line['duration']:.3f}", f"aresample={AUDIO_RATE}", "aformat=channel_layouts=stereo",
                  f"adelay={int(round(line['start'] * 1000))}:all=1"]
        mix_filters.append(f"[{index}:a]{','.join(steps)}[n{index}]")
        labels.append(f"[n{index}]")
    mix_filters.append(f"{''.join(labels)}amix=inputs={len(labels)}:duration=first:normalize=0[mix]")
    narration_mix = work / "narration_mix.wav"
    run_ffmpeg(tools, [*mix_args, "-filter_complex", ";".join(mix_filters), "-map", "[mix]", "-c:a", "pcm_s16le",
                       "-ar", str(AUDIO_RATE), "-t", f"{target:.3f}", str(narration_mix)])

    # 4) 조립
    shots = _plan_shots(lines, clips)
    burned = _render(shots, narration_mix, out, target, tools,
                     burn_captions=bool(getattr(settings, "hook_burn_captions", True)), subtitle_style=subtitle_style)
    info = probe(tools, out / "body.mp4")
    lufs = measure_lufs(tools, out / "body.mp4")
    default_cta = str(product.get("price_or_offer") or "").strip()[:16] or "프로필 링크에서 확인 →"
    cta_badge = str((script_raw or {}).get("cta_badge") or "").strip() or default_cta
    script = {"lines": [{k: v for k, v in line.items() if k in ("narration", "caption", "shots", "start", "duration")}
                        for line in lines], "tempo": round(tempo, 3), "cta_badge": cta_badge}
    meta = {"duration_sec": round(info.duration, 3), "lufs": lufs, "captions_burned": burned, "script": script,
            "clips": [{"index": c.index, "file": c.path.name, "seconds": round(c.duration, 2)} for c in clips],
            "warnings": warnings}
    if str(opening_callback or "").strip():
        meta["opening_callback"] = str(opening_callback).strip()
    done.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return BodyEditResult(video=out / "body.mp4", srt=out / "body.srt", duration_sec=round(info.duration, 3),
                          lufs=lufs, script=script, warnings=warnings)
