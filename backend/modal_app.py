"""백엔드(영상 파이프라인 포함)를 Modal 에 올린다. 내부 시연용.

배포 (저장소 루트에서):
    modal deploy backend/modal_app.py

- 이미지: backend/Dockerfile 그대로 (ffmpeg, 한글 글꼴, Node, A·B·C 작업자)
- 키·설정: Modal Secret "napda-backend" (환경변수로 들어간다). 이 파일과 이미지에는 키가 없다
- DB·작업 파일: Modal Volume "napda-data" 를 /app/data 에 붙인다 (재배포해도 남는다)
- 영상 생성은 요청에 먼저 답하고 같은 컨테이너에서 뒤이어 돈다. 컨테이너를 1개로 두고, 마지막 요청 뒤
  20분 동안 내리지 않아 훅 생성(3~5분)이 중간에 끊기지 않게 한다.
"""

from pathlib import Path

import modal

ROOT = Path(__file__).resolve().parents[1]

image = modal.Image.from_dockerfile(ROOT / "backend" / "Dockerfile", context_dir=ROOT).env(
    {
        "PYTHONPATH": "/app",
        "WORK_ROOT": "/app/data/jobs",
        "OUTPUT_DIR": "/app/data/outputs",
        "DB_PATH": "/app/data/jobs.db",
        "HOOK_ASSETS_DIR": "/app/data/hook_assets",
        # 콘티·장면 클립을 자체 모델(FLUX·MiniMax, 같은 워크스페이스 Modal 앱)로 만든다
        "HOOK_MEDIA_ENGINE": "selfhosted",
        # 크레딧 정책이 정해지기 전까지 렌더 무료 (결제 연결 뒤 이 줄을 뺀다)
        "CREDITS_PER_VIDEO": "0",
        # 렌더마다 이 중 하나를 같은 확률로 (목소리 선택 화면이 생기면 요청 값이 우선)
        "INWORLD_VOICE_IDS": "crafty-mocha-3599__gangsangyun,crafty-mocha-3599__yunyeowon,crafty-mocha-3599__isiu,crafty-mocha-3599__heohyejeong",
    }
)
data = modal.Volume.from_name("napda-data", create_if_missing=True)

app = modal.App("napda-backend")


@app.function(
    image=image,
    # 뒤의 Secret 이 같은 이름을 덮는다: 시나리오·본편 글 모델은 승인된 구성(Claude)으로 (Secret 에는 gemini 가 들어 있다).
    # 요청별 A/B(provider 지정)는 그대로 동작한다
    secrets=[
        modal.Secret.from_name("napda-backend"),
        modal.Secret.from_name("napda-hook-a-r2"),
        modal.Secret.from_dict({"HOOK_WORKER_LLM": "claude-opus-5-5", "BODY_LLM": "claude-opus-5-5"}),
    ],
    volumes={"/app/data": data},
    cpu=2.0,
    memory=4096,
    timeout=3600,
    min_containers=0,  # 안 쓸 때는 0개 (무료 크레딧 아끼기)
    max_containers=1,  # 작업 상태가 컨테이너 안(SQLite·스레드)에 있어 1개만
    scaledown_window=1200,  # 마지막 요청 뒤 20분 유지: 뒤에서 도는 영상 생성이 끊기지 않게
)
@modal.concurrent(max_inputs=20)
@modal.asgi_app()
def api():
    import sys

    if "/app" not in sys.path:
        sys.path.insert(0, "/app")
    from app.server import app as fastapi_app

    return fastapi_app
