"""Shared helpers for offline NAPDA PRD API contract tests."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from fastapi.testclient import TestClient  # noqa: E402

from app.auth import AuthenticatedUser, AuthenticationError  # noqa: E402
from app.config import Settings  # noqa: E402
from app.projects_router import _build_default_ad_spec  # noqa: E402
from app.server import create_app  # noqa: E402


def fake_google_verifier(credential: str, client_id: str) -> AuthenticatedUser:
    _ = client_id
    if credential == "bad-token":
        raise AuthenticationError("Invalid Google credential")
    if ":" in credential:
        uid, email = credential.split(":", 1)
    else:
        uid, email = "user-default", "seller@example.com"
    return AuthenticatedUser(user_id=uid, email=email, name="테스트 셀러", picture=None)


def fake_scenario_generator(project: Dict[str, Any], hook_types: List[str], provider: str) -> List[Dict[str, Any]]:
    _ = provider
    out: List[Dict[str, Any]] = []
    for ht in hook_types:
        spec = _build_default_ad_spec(
            project,
            ht,
            source_video="source/sample.mp4",
            source_duration=15.0,
            voice_id="Kore",
        )
        out.append(
            {
                "scenario_id": f"scn_{ht}_01",
                "type": ht,
                "hook_title": f"{project['product']['name']} {ht}안",
                "hook_duration_sec": float(spec["hook_window_sec"]),
                "body_duration_sec": 15.0,
                "replacement_test_note": f"{ht}안 교체 테스트 메모",
                "beats": [
                    {
                        "order": 1,
                        "role": "hook",
                        "duration_sec": 5.0,
                        "visual": f"{ht}안 오프닝 컷",
                        "narration": "첫 줄 대사",
                        "caption": "첫 줄 자막",
                    },
                    {
                        "order": 2,
                        "role": "payoff",
                        "duration_sec": 10.0,
                        "visual": "본편 시연 컷",
                        "narration": "제품 설명",
                        "caption": "제품 설명",
                    },
                ],
                "storyboard_frames": [],
                "ad_spec": spec,
            }
        )
    return out


def fake_storyboard_generator(
    project: Dict[str, Any], scenario: Dict[str, Any], visual_style: str
) -> List[Dict[str, Any]]:
    return [
        {
            "beat_order": int(b["order"]),
            "image_url": f"https://cdn.example.com/{project['project_id']}/{scenario['scenario_id']}/f{b['order']}.png?style={visual_style}",
            "caption": b.get("caption", ""),
        }
        for b in scenario.get("beats") or []
    ]


def build_test_client(root: Path, *, daily_render_limit: int = 3) -> TestClient:
    settings = Settings(
        _env_file=None,
        gemini_api_key="dummy-key",
        google_client_id="dummy-client-id.apps.googleusercontent.com",
        session_secret="test-session-secret-32bytes-minimum",
        daily_render_limit=daily_render_limit,
        hook_render_mode="dry_run",  # 과금 호출 없이 scenario.json·hook.srt 만 (영상 생성은 tests/hookpipe 에서 대역으로 검증)
        work_root=str(root / "work"),
        output_dir=str(root / "outputs"),
        db_path=str(root / "napda.db"),
    )
    app = create_app(
        settings=settings,
        google_token_verifier=fake_google_verifier,
        scenario_generator=fake_scenario_generator,
        storyboard_generator=fake_storyboard_generator,
    )
    return TestClient(app)


def login_client(client: TestClient, credential: str = "seller-1:seller1@example.com") -> str:
    resp = client.post("/v1/auth/google", json={"credential": credential})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]
