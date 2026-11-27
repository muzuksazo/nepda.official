"""자체 호스팅 모델로 콘티(스틸컷)와 장면 클립을 만든다 (HOOK_MEDIA_ENGINE=selfhosted).

- 스틸컷: FLUX klein (Modal 앱 napda-flux3-klein). 장면 프롬프트를 Claude 가 영어 그림 묘사로 바꿔 넣는다.
  장면 1을 먼저 그리고 나머지 장면은 장면 1을 참고 컷으로 쓴다 (같은 인물·장소가 이어진다).
- 클립: MiniMax-H3 터보 8단계 (Modal 앱 napda-minimax). 움직임 묘사는 Claude 가 영어로만 쓴다
  (한글이 들어가면 화면에 글자를 그린다).
- 2026-11-28 시험 실행기(backend/selfhosted/hook_cycle.py)에서 확정한 구성을 서버 API 로 옮긴 것.

Modal 함수는 같은 워크스페이스의 백엔드 컨테이너 안에서 부른다 (modal 패키지 필요). 테스트는 flux/minimax/caption/motion 을
가짜로 넣는다.
"""

from __future__ import annotations

import base64
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from .prompts import beat_prompt, ordered_beats, product_beat_orders

logger = logging.getLogger("hookpipe.selfhosted")

FLUX_APP, FLUX_CLASS = "napda-flux3-klein", "Flux3KleinService"
MINIMAX_APP, MINIMAX_CLASS = "napda-minimax", "MiniMax"
STILL_W, STILL_H = 576, 1024  # MiniMax 클립과 같은 크기
CLIP_STEPS = 8  # 터보 LoRA
CLIP_EXTRA_SEC = 1.0  # 나레이션에 맞춰 장면이 늘어날 여유
# 장면 1을 참고 컷으로 넣을 때: 인물·색·재질만 가져오고 구도는 장면 설명대로 (구도까지 베끼던 문제)
STYLE_REF_LEAD = (
    "Use the reference image only for the character design, colors and materials. "
    "Build a completely new composition, pose, setting detail and camera angle as described: "
)

# 컷마다 달라 보이게 장면 순서마다 촬영 크기를 배정한다 (참고 컷 구도를 그대로 따라가 4장이 같은 그림이 됐다, 2026-11-27)
SHOT_PLAN = [
    "wide establishing shot that shows the whole place, subject small in the frame, seen from a high angle",
    "medium shot from a low side angle, subject from the waist up, a different part of the place in the background",
    "extreme close-up on the single key detail of the idea, shallow depth of field, background fully blurred",
    "over-the-shoulder or top-down view of the action, a fresh angle not used before",
]
SHOT_PRODUCT = "hero close-up of the product filling the middle of the frame, eye level, clean background"


def clip_frames(seconds: float) -> int:
    """MiniMax 공식 템플릿의 17k+5 프레임 규칙 (24fps)."""
    n = max(5, round(seconds * 24))
    return n + (5 - n % 17) % 17


def _modal_cls(app: str, name: str) -> Any:
    import modal

    return modal.Cls.from_name(app, name)()


class SelfHostedMedia:
    def __init__(
        self,
        settings: Any,
        *,
        flux: Any = None,
        minimax: Any = None,
        caption_fn: Optional[Callable[[str], str]] = None,
        motion_fn: Optional[Callable[[str], str]] = None,
    ) -> None:
        self.settings = settings
        self._flux = flux
        self._minimax = minimax
        if caption_fn is None or motion_fn is None:
            from .flux_caption import claude_caption, motion_prompt_for_video

            caption_fn = caption_fn or claude_caption
            motion_fn = motion_fn or motion_prompt_for_video
        self._caption = caption_fn
        self._motion = motion_fn

    @property
    def flux(self) -> Any:
        if self._flux is None:
            self._flux = _modal_cls(FLUX_APP, FLUX_CLASS)
        return self._flux

    @property
    def minimax(self) -> Any:
        if self._minimax is None:
            self._minimax = _modal_cls(MINIMAX_APP, MINIMAX_CLASS)
        return self._minimax

    # ---- 미리 깨우기 (기다리지 않는다) ------------------------------------

    def warm_flux(self) -> None:
        try:
            self.flux.run_generate.spawn({"prompt": "a plain grey square", "reference_images": [], "width": 256,
                                          "height": 256, "steps": 1, "seed": 1, "use_pup": False, "safety": False,
                                          "output_format": "png"})
        except Exception as exc:  # 깨우기는 보조라 실패해도 본 작업은 그대로
            logger.warning("FLUX 미리 깨우기 실패: %s", exc)

    def warm_clips(self, count: int) -> None:
        """콘티 확인 화면이 뜰 때: MiniMax GPU 를 count 대 켜 모델을 올려 둔다 (2분 유지). 서버는 비용 때문에 1대만 켠다."""
        try:
            for slot in range(max(1, count)):
                self.minimax.warm.spawn(slot)
        except Exception as exc:
            logger.warning("MiniMax 미리 켜기 실패: %s", exc)

    # ---- 콘티 --------------------------------------------------------------

    def storyboard(self, scenario: Dict[str, Any], product: Dict[str, Any],
                   product_refs: Sequence[bytes] = ()) -> List[Dict[str, Any]]:
        """장면마다 {beat_order, png(bytes), caption_prompt, motion_prompt, spec, product} 를 돌려준다."""
        beats = ordered_beats(scenario)
        if not beats:
            return []
        product_orders = set(product_beat_orders(scenario))
        refs_b64 = [base64.b64encode(r).decode("ascii") for r in product_refs]
        plans: List[Tuple[int, Dict[str, Any], bool, str]] = []
        for i, beat in enumerate(beats, start=1):
            order = int(beat.get("order") or i)
            shows = order in product_orders
            use_product = shows and bool(refs_b64)
            spec = beat_prompt(scenario, beat, i, len(beats), product=product, shows_product=shows,
                               has_product_reference=use_product, has_style_reference=not use_product and i > 1)
            spec += "\nSHOT SIZE: " + (SHOT_PRODUCT if shows else SHOT_PLAN[(i - 1) % len(SHOT_PLAN)])
            plans.append((order, beat, use_product, spec))

        t0 = time.monotonic()
        # 장면 묘사·움직임 묘사는 서로 기다릴 필요가 없어 한꺼번에 부른다. 그림은 켜진 GPU 한 대에서 순서대로
        with ThreadPoolExecutor(max_workers=max(2, 2 * len(plans)), thread_name_prefix="caption") as pool:
            captions = {order: pool.submit(self._caption, spec) for order, _, _, spec in plans}
            motions = {order: pool.submit(self._motion, spec) for order, _, _, spec in plans}
            frames: List[Dict[str, Any]] = []
            first_b64: Optional[str] = None
            for order, beat, use_product, spec in plans:
                caption = captions[order].result()
                refs = refs_b64 if use_product else ([first_b64] if first_b64 else [])
                prompt = (STYLE_REF_LEAD + caption) if (first_b64 and not use_product) else caption
                res = self.flux.run_generate.remote({
                    "prompt": prompt, "reference_images": refs, "width": STILL_W, "height": STILL_H,
                    "seed": 1, "use_pup": False, "safety": True, "output_format": "png",
                })
                png_b64 = res["image_base64"]
                if first_b64 is None and not use_product:
                    first_b64 = png_b64
                frames.append({
                    "beat_order": order,
                    "png": base64.b64decode(png_b64),
                    "caption_prompt": prompt,
                    "motion_prompt": motions[order].result(),
                    "product": use_product,
                    "spec": spec,
                })
        logger.info("콘티 %d장 %.0f초", len(frames), time.monotonic() - t0)
        return frames

    # ---- 장면 클립 ------------------------------------------------------------

    def clips(self, items: Sequence[Tuple[bytes, str, float]]) -> List[bytes]:
        """(첫 프레임 png, 움직임 묘사, 장면 길이 초) → 클립 mp4. 장면마다 GPU 가 동시에 만든다."""
        calls = [(png, motion, STILL_W, STILL_H, clip_frames(seconds + CLIP_EXTRA_SEC), CLIP_STEPS, 1)
                 for png, motion, seconds in items]
        return list(self.minimax.render.starmap(calls))
