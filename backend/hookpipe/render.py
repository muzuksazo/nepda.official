"""공통 훅 렌더: 시나리오 → (영상 모델 클립 + 나레이션 + 자막) → 계약 규격 파일.

결과 (`OUTPUT_DIR/{project_id}/{hook_id}/`, WORKER_CONTRACT.md 4절):
    hook.mp4  1080x1920, 30fps, H.264, 소리 -14 LUFS
    tts.mp3   나레이션 트랙 (나레이션이 있을 때만)
    hook.srt  자막
    scenario.json  채택된 시나리오 원문
    storyboard_NN.png  장면별 대표 화면

어느 유형(A·B·C) 시나리오든 같은 길로 만든다. 유형별 차이는 prompts.py 의 화면 톤과 제품 장면 판정뿐이다.

미리 만들어 둔 영상을 쓰는 장면(A 유형의 제품과 무관한 앞부분 등)은 장면에 `prebuilt_clip`
(필요하면 `prebuilt_narration`)을 적어 주면 영상 모델·TTS 를 부르지 않고 그 파일을 쓴다.

과금으로 받은 파일(나레이션, 참고 이미지, 클립)은 cache_dir 에 내용 해시 이름으로 둔다.
같은 문장·목소리·프롬프트·길이·참고 이미지면 다시 사지 않고, 하나라도 바뀌면 새로 만든다.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from .captions import build_srt
from .media import (
    AUDIO_ENCODE_ARGS,
    AUDIO_RATE,
    VIDEO_ENCODE_ARGS,
    MediaError,
    MediaTools,
    fill_filter,
    find_tools,
    gain_filter,
    gain_to_target,
    measure_lufs,
    probe,
    run_ffmpeg,
)
from .prompts import beat_prompt, ordered_beats, product_beat_orders, reference_image_prompt, soften_prompt

logger = logging.getLogger("hookpipe.render")

MIN_CLIP_SEC, MAX_CLIP_SEC = 3, 15
# 영상 모델에 보내는 참고 이미지 규격: 긴 변 1280 이하 JPEG.
# 이미지 모델이 준 768x1376 원본을 그대로 붙이면 INVALID_ARGUMENT 로 거절된 일이 있었다 (2026-11-27 실측).
REF_SCALE = "scale='if(gt(iw,ih),1280,-2)':'if(gt(iw,ih),-2,1280)'"
NARRATION_TAIL_SEC = 0.15  # 나레이션이 끝난 뒤 다음 장면으로 넘어가기 전 숨 고르는 시간
HOLD_MAX_SEC = 1.0  # 이보다 짧고 나레이션이 없는 장면은 클립을 사지 않고 앞 장면의 마지막 화면을 멈춰 둔다
NORMAL_TEMPO_MAX = 1.3
HARD_TEMPO_MAX = 1.6
REVEAL_PAUSE_SEC = 0.8  # "그래서 ~가 뭐냐고요?" 앞의 뜸 (두 문장이 쉬지 않고 붙어 반전감이 없었다, 2026-11-27)
REVEAL_PAUSE_AFTER_SEC = 0.6  # 그 질문 뒤 본편으로 넘어가기 전 여운
TTS_PARALLEL = 4  # 장면별 나레이션을 동시에 만든다

# 장면 나레이션 끝의 "그래서 …?" 질문 한 문장 (B 반전 장면의 마무리 질문)
_REVEAL_Q = re.compile(r"(그래서[^.!?。]*\?)\s*$")


def split_reveal(narration: str) -> Optional[Tuple[str, str]]:
    """마지막 문장이 '그래서 …?' 질문이고 그 앞에 다른 문장이 있으면 (앞부분, 질문)으로 나눈다."""
    text = (narration or "").strip()
    m = _REVEAL_Q.search(text)
    if not m:
        return None
    head = text[: m.start()].strip()
    if not head:
        return None
    return head, m.group(1).strip()


def _join_with_pause(first: Path, second: Path, out: Path, pause: float, after: float, tools: MediaTools) -> None:
    """앞부분 + 무음(pause) + 질문 + 무음(after) 으로 이어 붙인다 (wav)."""
    fmt = f"aresample={AUDIO_RATE},aformat=sample_fmts=s16:channel_layouts=stereo"
    silence = f"anullsrc=r={AUDIO_RATE}:cl=stereo"
    run_ffmpeg(tools, [
        "-i", str(first),
        "-f", "lavfi", "-t", f"{max(pause, 0.01):.3f}", "-i", silence,
        "-i", str(second),
        "-f", "lavfi", "-t", f"{max(after, 0.01):.3f}", "-i", silence,
        "-filter_complex",
        f"[0:a]{fmt}[a];[1:a]{fmt}[p];[2:a]{fmt}[b];[3:a]{fmt}[q];[a][p][b][q]concat=n=4:v=0:a=1[out]",
        "-map", "[out]", "-c:a", "pcm_s16le", str(out),
    ])


class HookRenderError(RuntimeError):
    """훅을 만들 수 없을 때 (입력 문제, 과금 상한, 생성 실패)."""


@dataclass
class BeatPlan:
    order: int
    beat: Dict[str, Any]
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
    hold: bool = False  # 앞 장면의 마지막 화면에서 멈춤 (A 유형의 '패턴 인터럽트' 같은 아주 짧은 무음 장면)
    prebuilt: bool = False  # 미리 만들어 둔 영상을 쓰는 장면 (영상 모델을 부르지 않는다)
    prompt: str = ""
    reused: List[str] = field(default_factory=list)


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
    """과금 호출 없이 만들 수 있는 두 파일만 쓴다 (dry_run 모드와 planner-api 시나리오에서 사용)."""
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
                 "-vf", REF_SCALE, "-q:v", "3", str(target)],
                timeout=120.0,
            )
        except MediaError as exc:
            logger.warning("참고 이미지 추출 실패 (%s): %s", video.name, exc)
            continue
        if target.is_file() and target.stat().st_size > 0:
            frames.append(target)
    return frames


def _normalize_reference(source: Path, tools: MediaTools) -> Path:
    """참고 이미지를 긴 변 1280 이하 JPEG 으로 다시 저장한다. 실패하면 원본을 그대로 쓴다."""
    target = source.with_name(f"{source.stem}_ref.jpg")
    if _ready(target):
        return target
    try:
        run_ffmpeg(tools, ["-i", str(source), "-vf", REF_SCALE, "-q:v", "3", str(target)], timeout=60.0)
    except MediaError as exc:
        logger.warning("참고 이미지 규격 맞추기 실패, 원본을 씁니다: %s", exc)
        return source
    return target if _ready(target) else source


def _digest(*parts: Any) -> str:
    joined = "\x1f".join(str(p) for p in parts)
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()[:16]


def _file_digest(path: Path) -> str:
    return hashlib.sha1(path.read_bytes()).hexdigest()[:12]


def _ready(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 0


def _clip_seconds(duration: float) -> int:
    return max(MIN_CLIP_SEC, min(MAX_CLIP_SEC, math.ceil(duration - 1e-6)))


def generate_clip_with_retries(
    provider: Any,
    prompt: str,
    clip: Path,
    *,
    clip_sec: int,
    resolution: str,
    reference_paths: Sequence[Path],
) -> tuple:
    """영상 모델로 클립 하나. INVALID_ARGUMENT 로 거절되면 (실패한 요청은 과금되지 않음) 조건을 낮춰 다시 보낸다:
    1) 그대로  2) 참고 이미지 없이  3) 단면·해부 묘사를 바깥에서 본 장면으로 바꿔서.
    2026-11-27 실측: 참고 이미지 원본 크기, '고래 입안 … 단면 시각화' 장면이 각각 거절됐다.
    돌려주는 값: (다시 만든 방법 태그 또는 "", 실제로 쓴 프롬프트)
    """
    attempts = [("", prompt, list(reference_paths))]
    if reference_paths:
        attempts.append(("retried_without_reference", prompt, []))
    softened = soften_prompt(prompt)
    if softened != prompt:
        attempts.append(("retried_outside_view", softened, []))
    for position, (tag, prompt_text, refs_to_send) in enumerate(attempts):
        try:
            provider.generate_video_clip(
                prompt_text,
                clip,
                aspect_ratio="9:16",
                duration_sec=clip_sec,
                resolution=resolution,
                reference_paths=refs_to_send,
            )
        except Exception as exc:
            if "INVALID_ARGUMENT" not in str(exc) or position == len(attempts) - 1:
                raise
            continue
        return tag, prompt_text
    raise HookRenderError("영상 클립을 만들지 못했습니다.")


def _plan_beats(scenario: Dict[str, Any], max_hook_sec: float) -> List[BeatPlan]:
    beats = ordered_beats(scenario)
    if not beats:
        raise HookRenderError("시나리오에 장면(beats)이 없습니다.")
    orders = [b.get("order") for b in beats]
    if any(not isinstance(o, int) or isinstance(o, bool) or o < 1 for o in orders) or len(set(orders)) != len(orders):
        raise HookRenderError(f"장면 번호(order)는 1 이상의 서로 다른 정수여야 합니다: {orders}")
    product_orders = set(product_beat_orders(scenario))
    plans: List[BeatPlan] = []
    for beat in beats:
        dur = float(beat.get("duration_sec") or 0.0)
        if dur <= 0:
            raise HookRenderError(f"장면 {beat.get('order')} 의 길이가 0초 이하입니다.")
        order = int(beat["order"])
        plans.append(
            BeatPlan(
                order=order,
                beat=beat,
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
    for index, plan in enumerate(plans):
        plan.hold = index > 0 and plan.scenario_sec < HOLD_MAX_SEC and not plan.narration
    return plans


def _check_clip_budget(requested: int, limit: int) -> None:
    if requested > limit:
        raise HookRenderError(
            f"영상 모델에 요청할 클립 길이 합({requested}초)이 상한({limit}초)을 넘습니다. "
            "장면 수나 길이를 줄이거나 HOOK_MAX_CLIP_SEC_PER_HOOK 을 올려 주세요."
        )


def _fit_timing(plans: List[BeatPlan], max_hook_sec: float, warnings: List[str]) -> None:
    """나레이션이 장면보다 길면 조금 빠르게 읽히고(최대 1.3배), 그래도 길면 장면을 늘린다.

    전체가 상한을 넘으면 1.6배까지 올리고, 그래도 넘으면 늘린 만큼에서 넘친 몫만 같은 비율로 덜어 낸다
    (그 장면들은 나레이션 끝이 조금 잘린다). 장면이 시나리오 길이보다 짧아지는 일은 없다.
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
        extended = sum(p.duration - p.scenario_sec for p in plans)
        keep = max(0.0, 1.0 - (total - max_hook_sec) / extended) if extended > 0 else 0.0
        for plan in plans:
            plan.duration = plan.scenario_sec + (plan.duration - plan.scenario_sec) * keep
        cut = [str(p.order) for p in plans if p.narration_sec / p.tempo > p.duration + 0.05]
        if cut:
            warnings.append(
                f"나레이션이 장면 길이보다 많이 길어 훅 상한({max_hook_sec:.0f}초)에 맞추느라 "
                f"장면 {', '.join(cut)} 의 나레이션 끝이 잘립니다. 시나리오의 나레이션을 줄이는 것이 좋습니다."
            )
    cursor = 0.0
    for plan in plans:
        plan.duration = round(plan.duration, 3)
        plan.start = round(cursor, 3)
        cursor += plan.duration
        plan.clip_sec = 0 if (plan.hold or plan.prebuilt) else _clip_seconds(plan.duration)


def _subtitle_style() -> str:
    # SRT 는 384x288 기준 좌표로 변환된다 (1920 높이 기준 ×6.67).
    # 2026-11-28 사용자 선택(자막 후보 P3): Pretendard ExtraBold 약 133px, 흰 글자 + 뒤로 비켜 놓은 검은 글자(2레이어),
    # 아주 얇은 검은 테두리(약 2px), 아래에서 약 300px. 글꼴은 서버 이미지에 넣는다(backend/assets/fonts).
    return (
        "FontName=Pretendard ExtraBold,FontSize=20,Bold=0,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
        "BackColour=&H00000000,BorderStyle=1,Outline=0.3,Shadow=1.5,Spacing=-0.6,Alignment=2,"
        "MarginL=6,MarginR=6,MarginV=45"
    )


def _mix_narration(plans: List[BeatPlan], work: Path, tools: MediaTools, total: float) -> Optional[Path]:
    """장면별 나레이션을 제자리에 놓은 한 줄 트랙(wav). 나레이션이 없으면 None."""
    narrated = [p for p in plans if p.narration_path is not None]
    if not narrated:
        return None
    args: List[str] = []
    filters = [f"anullsrc=r={AUDIO_RATE}:cl=stereo,atrim=0:{total:.3f}[base]"]
    labels = ["[base]"]
    for index, plan in enumerate(narrated):
        args += ["-i", str(plan.narration_path)]
        steps = []
        if plan.tempo > 1.001:
            steps.append(f"atempo={plan.tempo:.4f}")
        steps += [
            f"atrim=0:{plan.duration:.3f}",
            f"aresample={AUDIO_RATE}",
            "aformat=channel_layouts=stereo",
            f"adelay={int(round(plan.start * 1000))}:all=1",
        ]
        filters.append(f"[{index}:a]{','.join(steps)}[n{index}]")
        labels.append(f"[n{index}]")
    filters.append(f"{''.join(labels)}amix=inputs={len(labels)}:duration=first:normalize=0[mix]")
    target = work / "narration_mix.wav"
    run_ffmpeg(
        tools,
        [*args, "-filter_complex", ";".join(filters), "-map", "[mix]", "-c:a", "pcm_s16le",
         "-ar", str(AUDIO_RATE), "-t", f"{total:.3f}", str(target)],
    )
    return target


def _assemble(
    plans: List[BeatPlan],
    out_dir: Path,
    tools: MediaTools,
    *,
    burn_captions: bool,
    narration_mix: Optional[Path],
) -> bool:
    """클립과 나레이션을 hook.mp4 로 합친다. 자막을 구웠으면 True."""
    total = sum(p.duration for p in plans)
    args: List[str] = []
    filters: List[str] = []
    shots = [p for p in plans if not p.hold]
    for index, plan in enumerate(shots):
        # 바로 뒤에 이어지는 '멈춤' 장면만큼 이 클립의 마지막 화면을 더 붙잡아 둔다
        position = plans.index(plan)
        freeze = 0.0
        for later in plans[position + 1:]:
            if not later.hold:
                break
            freeze += later.duration
        args += ["-i", str(plan.clip_path)]
        info = probe(tools, plan.clip_path)  # type: ignore[arg-type]
        short = plan.duration - info.duration
        steps: List[str] = []
        if short > 0.02:
            if tools.has_filter("tpad"):
                steps.append(f"tpad=stop_mode=clone:stop_duration={short + 0.1:.3f}")
            else:
                steps.append(f"setpts={plan.duration / max(info.duration, 0.1):.4f}*PTS")
        steps.append(f"trim=0:{plan.duration:.3f}")
        steps.append("setpts=PTS-STARTPTS")
        if freeze > 0:
            if tools.has_filter("tpad"):
                steps.append(f"tpad=stop_mode=clone:stop_duration={freeze + 0.1:.3f}")
                steps.append(f"trim=0:{plan.duration + freeze:.3f}")
            else:  # tpad 가 없는 ffmpeg: 멈추는 대신 조금 느리게 늘린다
                steps.append(f"setpts={(plan.duration + freeze) / plan.duration:.4f}*PTS")
            steps.append("setpts=PTS-STARTPTS")
        filters.append(f"[{index}:v]{','.join(steps)}[t{index}]")
        filters.append(fill_filter(f"t{index}", f"v{index}"))
    concat_in = "".join(f"[v{i}]" for i in range(len(shots)))
    filters.append(f"{concat_in}concat=n={len(shots)}:v=1:a=0[vcat]")

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

    audio_index = len(shots)
    if narration_mix is not None:
        # 한 번 재고 그 차이만큼만 올린다: 나레이션이 일부 장면에만 있어도 -14 LUFS 에 맞는다
        gain = gain_to_target(measure_lufs(tools, narration_mix))
        args += ["-i", str(narration_mix)]
        filters.append(f"[{audio_index}:a]{gain_filter(tools, gain)},aresample={AUDIO_RATE},asplit=2[aout][narr_b]")
        audio_map = "[aout]"
    else:
        args += ["-f", "lavfi", "-t", f"{total:.3f}", "-i", f"anullsrc=r={AUDIO_RATE}:cl=stereo"]
        audio_map = f"{audio_index}:a"

    cmd = [*args, "-filter_complex", ";".join(filters), "-map", f"[{video_label}]", "-map", audio_map]
    cmd += [*VIDEO_ENCODE_ARGS, *AUDIO_ENCODE_ARGS, "-t", f"{total:.3f}", "hook.mp4"]
    if narration_mix is not None:
        mp3_codec = ["-c:a", "libmp3lame", "-q:a", "3"] if tools.has_encoder("libmp3lame") else ["-c:a", "mp3"]
        cmd += ["-map", "[narr_b]", *mp3_codec, "-ar", str(AUDIO_RATE), "-t", f"{total:.3f}", "tts.mp3"]

    try:
        run_ffmpeg(tools, cmd, cwd=out_dir)
    except MediaError:
        if not burned:
            raise
        # 글꼴이나 libass 문제로 자막 굽기만 실패하는 경우가 있어, 자막 없이 한 번 더 만든다
        logger.warning("자막을 구운 인코딩이 실패해 자막 없이 다시 만듭니다.")
        retry = list(cmd)
        retry[retry.index("-filter_complex") + 1] = ";".join(f for f in filters if "subtitles=" not in f)
        run_ffmpeg(tools, [("[vcat]" if a == "[vsub]" else a) for a in retry], cwd=out_dir)
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


def _call_with_deadline(fn: Callable[[], Any], seconds: float, label: str) -> Any:
    """fn 을 따로 돌리고 seconds 안에 안 끝나면 기다리지 않는다 (TimeoutError).

    2026-11-27 Modal 에서 이미지 모델 호출이 응답 없이 멈추는 일이 반복됐고, SDK 의 시간 제한은 재시도와 겹쳐
    지켜지지 않았다. 멈춘 호출은 뒤에서 SDK 시간 제한에 걸려 스스로 끝난다 (daemon 스레드라 종료도 막지 않는다).
    """
    box: Dict[str, Any] = {}
    done = threading.Event()

    def run() -> None:
        try:
            box["value"] = fn()
        except BaseException as exc:  # 호출한 쪽으로 그대로 넘긴다
            box["error"] = exc
        finally:
            done.set()

    threading.Thread(target=run, name=f"deadline:{label}", daemon=True).start()
    if not done.wait(seconds):
        raise TimeoutError(f"{label}: {seconds:.0f}초 안에 응답이 없었습니다.")
    if "error" in box:
        raise box["error"]
    return box.get("value")


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
    cache_dir: Optional[str | Path] = None,
    resolve_asset: Optional[Callable[[str], Optional[Path]]] = None,
    progress: Optional[Callable[[str], None]] = None,
    on_usage: Optional[Callable[..., None]] = None,
) -> HookRenderResult:
    """훅 하나를 만든다. provider 는 `app.genai_provider.GenAIMediaProvider` (또는 같은 모양의 대역).

    cache_dir: 과금으로 받은 파일을 두는 곳. 같은 시나리오를 다시 만들 때 같은 곳을 주면 이미 받은 것은 다시 사지 않는다.
    resolve_asset: 장면의 `prebuilt_clip` / `prebuilt_narration` 값을 실제 파일 경로로 바꿔 주는 함수.
    """
    import time

    record_usage = on_usage if callable(on_usage) else (lambda **_kw: None)
    target = Path(out_dir)
    work = target / "_work"
    work.mkdir(parents=True, exist_ok=True)
    cache = Path(cache_dir) if cache_dir else work / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    media = tools or find_tools(getattr(settings, "ffmpeg_bin", None), getattr(settings, "ffprobe_bin", None))
    say = progress or (lambda _msg: None)
    warnings: List[str] = []
    max_hook_sec = float(getattr(settings, "hook_max_sec", 20.0))
    clip_limit = int(getattr(settings, "hook_max_clip_sec_per_hook", 45))

    plans = _plan_beats(scenario, max_hook_sec)
    # 미리 만든 파일을 쓰는 장면: 파일이 없으면 아무것도 사기 전에 멈춘다
    prebuilt_audio: Dict[int, Path] = {}
    for plan in plans:
        for key in ("prebuilt_clip", "prebuilt_narration"):
            ref = str(plan.beat.get(key) or "").strip()
            if not ref:
                continue
            found = resolve_asset(ref) if resolve_asset else None
            if found is None or not _ready(Path(found)):
                raise HookRenderError(f"장면 {plan.order} 의 미리 만든 파일을 찾지 못했습니다: {ref}")
            info = probe(media, found)
            if key == "prebuilt_clip":
                if not info.has_video or info.duration <= 0:
                    raise HookRenderError(f"장면 {plan.order} 의 미리 만든 영상에 화면이 없습니다: {ref}")
                plan.clip_path, plan.prebuilt, plan.hold = Path(found), True, False
            else:
                if not info.has_audio or info.duration <= 0:
                    raise HookRenderError(f"장면 {plan.order} 의 미리 만든 나레이션에 소리가 없습니다: {ref}")
                prebuilt_audio[plan.order] = Path(found)
    # 과금 방어 1: 시나리오 길이만으로도 상한을 넘으면 나레이션을 사기 전에 멈춘다
    _check_clip_budget(
        sum(_clip_seconds(p.scenario_sec) for p in plans if not p.hold and not p.prebuilt), clip_limit
    )
    (target / "scenario.json").write_text(json.dumps(scenario, ensure_ascii=False, indent=2), encoding="utf-8")
    # 같은 폴더로 다시 만들 때 예전 결과가 섞이지 않게 지운다
    for stale in [target / "hook.mp4", target / "tts.mp3", *target.glob("storyboard_*.png")]:
        stale.unlink(missing_ok=True)

    # 1) 나레이션 먼저 (싸고, 장면 길이를 정하는 데 필요하다)
    if tts_enabled:
        say("TTS")
        voice_name = voice or getattr(settings, "tts_default_voice", None)
        # 공급자가 정하는 파일 형식과 이름표 (Inworld 는 mp3). 공급자가 바뀌면 캐시도 따로 쓴다.
        tts_ext = getattr(provider, "tts_extension", ".wav")
        tts_label = getattr(provider, "tts_label", "") or getattr(settings, "tts_model", "")
        tts_provider_name = "inworld" if str(tts_label).startswith("inworld:") else "google"
        tts_model_name = (
            str(tts_label).split(":", 2)[1]
            if str(tts_label).startswith("inworld:") and ":" in str(tts_label)
            else str(tts_label or getattr(settings, "tts_model", "") or "gemini-tts")
        )
        pause_before = float(getattr(settings, "hook_reveal_pause_sec", REVEAL_PAUSE_SEC))
        pause_after = float(getattr(settings, "hook_reveal_pause_after_sec", REVEAL_PAUSE_AFTER_SEC))
        usage_lock = threading.Lock()

        def _speak(text: str, plan: BeatPlan) -> Path:
            """문장 하나를 읽는다 (내용·목소리·공급자로 캐시)."""
            order = plan.order
            out_path = cache / f"tts_{_digest(text, voice_name, tts_label)}{tts_ext}"
            if _ready(out_path):
                plan.reused.append("tts")
                with usage_lock:
                    record_usage(stage="tts", step_name=f"beat_{order}", provider=tts_provider_name,
                                 model=tts_model_name, media_unit="char", media_qty=float(len(text)),
                                 cache_hit=True, latency_ms=0)
                return out_path
            t_tts = time.monotonic()
            tts_status = "ok"
            try:
                provider.generate_tts_beat(text, out_path, voice_name=voice_name)
            except Exception:
                tts_status = "error"
                raise
            finally:
                with usage_lock:
                    record_usage(stage="tts", step_name=f"beat_{order}", provider=tts_provider_name,
                                 model=tts_model_name, media_unit="char", media_qty=float(len(text)),
                                 cache_hit=False, latency_ms=int((time.monotonic() - t_tts) * 1000),
                                 status=tts_status)
            return out_path

        def _narrate(plan: BeatPlan) -> Optional[Path]:
            prebuilt = prebuilt_audio.get(plan.order)
            if prebuilt is not None:
                plan.reused.append("prebuilt_narration")
                return prebuilt
            if not plan.narration:
                return None
            reveal = split_reveal(plan.narration) if (pause_before > 0 or pause_after > 0) else None
            if reveal is None:
                return _speak(plan.narration, plan)
            # 반전 질문 앞뒤로 뜸: 앞부분 / 무음 / "그래서 …?" / 무음
            head, question = reveal
            joined = cache / f"tts_{_digest(plan.narration, voice_name, tts_label, pause_before, pause_after)}_pause.wav"
            if _ready(joined):
                plan.reused.append("tts")
            else:
                _join_with_pause(_speak(head, plan), _speak(question, plan), joined, pause_before, pause_after, media)
            plan.reused.append("reveal_pause")
            return joined

        # 장면별 나레이션은 서로 기다릴 필요가 없어 동시에 만든다
        with ThreadPoolExecutor(max_workers=TTS_PARALLEL, thread_name_prefix="tts") as pool:
            wavs = list(pool.map(_narrate, plans))
        for plan, wav in zip(plans, wavs):
            if wav is None:
                continue
            info = probe(media, wav)
            if info.duration <= 0:
                raise HookRenderError(f"장면 {plan.order} 나레이션 음성이 비어 있습니다.")
            plan.narration_path, plan.narration_sec = wav, info.duration
    _fit_timing(plans, max_hook_sec, warnings)

    # 과금 방어 2: 나레이션에 맞춰 장면이 늘어난 뒤의 클립 길이 합
    requested = sum(p.clip_sec for p in plans)
    _check_clip_budget(requested, clip_limit)

    # 2) 참고 이미지: 제품 장면은 촬영본에서 뽑은 컷, 나머지는 톤·주인공 참고 이미지 한 장
    refs = [Path(p) for p in product_refs if Path(p).is_file()]
    style_ref: Optional[Path] = None
    image_model_name = str(getattr(settings, "image_model", "") or "unknown")
    if any((not p.shows_product or not refs) and not p.hold and not p.prebuilt for p in plans):
        say("REFERENCE")
        ref_prompt = reference_image_prompt(scenario)
        # 실제 호출로 통과한 형식(JPEG)으로 받는다 (B 의 gclips 기록)
        candidate = cache / f"style_{_digest(ref_prompt, getattr(settings, 'image_model', ''))}.jpg"
        try:
            if _ready(candidate):
                record_usage(
                    stage="ref_image",
                    step_name="style_ref",
                    provider="google",
                    model=image_model_name,
                    media_unit="image",
                    media_qty=1.0,
                    cache_hit=True,
                    latency_ms=0,
                )
            else:
                t_ref = time.monotonic()
                ref_status = "ok"
                try:
                    _call_with_deadline(
                        lambda: provider.generate_reference_image(
                            ref_prompt, candidate, aspect_ratio="9:16", mime_type="image/jpeg"
                        ),
                        float(getattr(settings, "reference_image_timeout_sec", 90.0)),
                        "톤 참고 이미지",
                    )
                except Exception:
                    ref_status = "error"
                    raise
                finally:
                    record_usage(
                        stage="ref_image",
                        step_name="style_ref",
                        provider="google",
                        model=image_model_name,
                        media_unit="image",
                        media_qty=1.0,
                        cache_hit=False,
                        latency_ms=int((time.monotonic() - t_ref) * 1000),
                        status=ref_status,
                    )
            if _ready(candidate):
                style_ref = _normalize_reference(candidate, media)
        except Exception as exc:  # 참고 이미지는 품질 보조라, 실패해도 클립 생성은 계속한다
            warnings.append(f"톤 참고 이미지를 만들지 못해 참고 이미지 없이 진행했습니다: {exc}")

    # 3) 장면 클립
    resolution = str(getattr(settings, "hook_clip_resolution", "720p"))
    video_model = getattr(settings, "video_model", "")
    for index, plan in enumerate(plans, start=1):
        if plan.hold:
            plan.prompt = "(클립 없음: 앞 장면의 마지막 화면에서 멈춤)"
            continue
        if plan.prebuilt:
            plan.prompt = f"(미리 만든 영상: {plan.beat.get('prebuilt_clip')})"
            plan.reused.append("prebuilt_clip")
            continue
        say(f"CLIP {index}/{len(plans)}")
        use_product_refs = plan.shows_product and bool(refs)
        plan.prompt = beat_prompt(
            scenario,
            plan.beat,
            index,
            len(plans),
            product=product,
            shows_product=plan.shows_product,
            has_product_reference=use_product_refs,
            has_style_reference=style_ref is not None,
        )
        reference_paths = refs if use_product_refs else ([style_ref] if style_ref else [])
        key = _digest(plan.prompt, plan.clip_sec, resolution, video_model, *[_file_digest(p) for p in reference_paths])
        clip = cache / f"clip_{key}.mp4"
        if _ready(clip):
            plan.reused.append("clip")
            record_usage(
                stage="video_clip",
                step_name=f"beat_{plan.order}",
                provider="google",
                model=str(video_model or "unknown"),
                media_unit="sec",
                media_qty=float(plan.clip_sec),
                cache_hit=True,
                latency_ms=0,
            )
        else:
            t_clip = time.monotonic()
            clip_status = "ok"
            try:
                tag, used_prompt = generate_clip_with_retries(
                    provider, plan.prompt, clip, clip_sec=plan.clip_sec, resolution=resolution, reference_paths=reference_paths
                )
            except Exception:
                clip_status = "error"
                raise
            finally:
                record_usage(
                    stage="video_clip",
                    step_name=f"beat_{plan.order}",
                    provider="google",
                    model=str(video_model or "unknown"),
                    media_unit="sec",
                    media_qty=float(plan.clip_sec),
                    cache_hit=False,
                    latency_ms=int((time.monotonic() - t_clip) * 1000),
                    status=clip_status,
                )
            if tag:
                plan.reused.append(tag)
                plan.prompt = used_prompt
                what = "참고 이미지 없이" if tag == "retried_without_reference" else "단면 묘사를 바깥 장면으로 바꿔"
                warnings.append(f"장면 {plan.order}: 영상 모델이 요청을 거절해 {what} 다시 만들었습니다.")
        info = probe(media, clip)
        if not info.has_video or info.duration <= 0:
            raise HookRenderError(f"장면 {plan.order} 클립에 영상이 없습니다.")
        plan.clip_path = clip

    # 4) 자막 → 조립 → 콘티 이미지
    total = sum(p.duration for p in plans)
    cues = [(p.start, p.start + p.duration, p.caption or p.narration) for p in plans]
    (target / "hook.srt").write_text(build_srt(cues), encoding="utf-8")
    say("ASSEMBLE")
    narration_mix = _mix_narration(plans, work, media, total)
    burned = _assemble(
        plans,
        target,
        media,
        burn_captions=bool(getattr(settings, "hook_burn_captions", True)),
        narration_mix=narration_mix,
    )
    storyboards = _write_storyboards(plans, target, media)

    final = probe(media, target / "hook.mp4")
    has_tts = narration_mix is not None
    lufs = measure_lufs(media, target / "hook.mp4") if has_tts else None
    if narration_mix is not None:
        narration_mix.unlink(missing_ok=True)
    beats_meta = [
        {
            "order": p.order,
            "start": p.start,
            "duration": p.duration,
            "clip_sec": p.clip_sec,
            "shows_product": p.shows_product,
            "hold": p.hold,
            "prebuilt": p.prebuilt,
            "narration_sec": round(p.narration_sec, 3),
            "tempo": round(p.tempo, 3),
            "reused": p.reused,
            "prompt": p.prompt,
        }
        for p in plans
    ]
    meta = {
        "scenario_id": scenario.get("scenario_id"),
        "type": scenario.get("type"),
        "video_model": video_model or None,
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
