"""공유 영상의 만든 사람 이름: 세션만 있고 users 행이 없어도 이름이 뜬다 (2026-11-29)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.auth import AuthenticatedUser, SESSION_COOKIE_NAME, issue_session_token  # noqa: E402
from app.config import Settings  # noqa: E402
from app.project_store import ProjectStore  # noqa: E402
from app.server import create_app  # noqa: E402
from app.storage import LocalStorageBackend  # noqa: E402
from tests.support.projects_api import fake_google_verifier  # noqa: E402
from tests.support.tempdirs import temporary_directory  # noqa: E402


class TestCommunityCreatorName(unittest.TestCase):
    def test_session_without_user_row_still_shows_the_name(self) -> None:
        with temporary_directory() as td:
            root = Path(td)
            settings = Settings(
                _env_file=None, gemini_api_key="dummy-key", google_client_id="client-id",
                session_secret="test-session-secret-0123456789abcdef", hook_render_mode="dry_run",
                work_root=str(root / "work"), output_dir=str(root / "outputs"), db_path=str(root / "napda.db"),
            )
            store = ProjectStore(settings.db_path)
            app = create_app(settings, project_store=store, storage=LocalStorageBackend(root / "storage"),
                             google_token_verifier=fake_google_verifier)
            # 구글 로그인 없이 세션만 있는 사용자 (DB 가 새로 시작된 뒤 로그인이 유지된 경우)
            user = AuthenticatedUser(user_id="usr_kept", email="kept@gmail.com", name="이시우")
            client = TestClient(app)
            tok, _ = issue_session_token(user, settings.session_secret)
            client.cookies.set(SESSION_COOKIE_NAME, tok)
            proj = store.create_project("prj_pub", "usr_kept", product={"name": "스펀지", "category": "kitchen", "verified_facts": ["가볍다"]},
                                        selected_types=["A"], flow_mode="guide_first")
            store.set_project_public(proj["project_id"], True)
            self.assertEqual(store.list_public_projects()[0]["creator_name"], "크리에이터")  # 고치기 전 모습

            self.assertEqual(client.get("/v1/projects").status_code, 200)  # 아무 요청이나 한 번
            self.assertEqual(store.list_public_projects()[0]["creator_name"], "이시우")

            # 이미 있는 이름은 덮어쓰지 않는다
            store.ensure_user(AuthenticatedUser(user_id="usr_kept", email="other@gmail.com", name="다른 이름"))
            self.assertEqual(store.list_public_projects()[0]["creator_name"], "이시우")


if __name__ == "__main__":
    unittest.main()
