"""NAPDA 영상 파이프라인: A·B·C 시나리오 → 영상 모델 훅 → 본편 붙이기.

코어(`backend/app`)는 이 패키지의 세 가지만 쓴다.
- `make_scenario_generator`: 유형별 작업자(`bridge-dev/{a,b,c}`)로 시나리오 만들기
- `HookPipeline.process_hook`: 훅 영상 만들기
- `HookPipeline.process_render`: 훅 뒤에 본편을 붙여 최종 영상 만들기
"""

from .body import BodyAttachError, attach_body
from .render import HookRenderError, render_hook
from .service import HookPipeline, is_worker_scenario
from .workers import WORKERS, WorkerError, make_scenario_generator

__all__ = [
    "WORKERS",
    "BodyAttachError",
    "HookPipeline",
    "HookRenderError",
    "WorkerError",
    "attach_body",
    "is_worker_scenario",
    "make_scenario_generator",
    "render_hook",
]
