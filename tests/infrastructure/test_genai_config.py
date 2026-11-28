"""Offline regression coverage organized by PRD area."""
from tests.support.production import (
    GenAIClientFactoryCase,
    Settings,
    build_genai_client,
    patch,
)
from unittest.mock import ANY

from tests.support.tempdirs import temporary_directory


class TestGenAIClientFactory(GenAIClientFactoryCase):
    def test_build_client_ai_studio_vs_vertex_ai(self) -> None:
        with patch("app.genai_provider.genai.Client") as m_client:
            s_key = Settings(_env_file=None, gemini_api_key="AIzaDummyKey", google_genai_use_vertexai=False)
            build_genai_client(s_key)
            m_client.assert_called_once_with(api_key="AIzaDummyKey", http_options=ANY)

        with patch("app.genai_provider.genai.Client") as m_client:
            s_vtx = Settings(
                _env_file=None,
                google_genai_use_vertexai=True,
                google_cloud_project="my-gcp-proj",
                google_cloud_location="us-central1",
            )
            build_genai_client(s_vtx)
            m_client.assert_called_once_with(
                vertexai=True,
                project="my-gcp-proj",
                location="us-central1",
                http_options=ANY,
            )

        with self.assertRaises(ValueError):
            build_genai_client(Settings(_env_file=None, gemini_api_key=None, google_genai_use_vertexai=False))
        with self.assertRaises(ValueError):
            build_genai_client(Settings(_env_file=None, google_genai_use_vertexai=True, google_cloud_project=None))

    def test_build_client_vertex_api_key_express_mode(self) -> None:
        with patch("app.genai_provider.genai.Client") as m_client:
            s_vtx_key = Settings(
                _env_file=None,
                google_genai_use_vertexai=True,
                google_vertex_api_key="AQ.DummyVertexKey",
                google_cloud_project=None,
            )
            build_genai_client(s_vtx_key)
            m_client.assert_called_once_with(
                vertexai=True,
                api_key="AQ.DummyVertexKey",
                http_options=ANY,
            )

    def test_build_client_vercel_wif_credentials(self) -> None:
        provider = (
            "projects/123456789012/locations/global/workloadIdentityPools/"
            "vercel-napda-pool/providers/vercel-provider"
        )
        sa_email = "napda-vercel-wif@my-gcp-project.iam.gserviceaccount.com"
        s_wif = Settings(
            _env_file=None,
            google_genai_use_vertexai=True,
            google_cloud_project="my-gcp-project",
            google_cloud_location="us-central1",
            gcp_workload_identity_provider=provider,
            gcp_service_account_email=sa_email,
        )

        with patch.dict("os.environ", {"VERCEL_OIDC_TOKEN": "eyJ.test.oidc"}, clear=False):
            with patch("app.genai_provider.genai.Client") as m_client:
                build_genai_client(s_wif)
                self.assertEqual(m_client.call_count, 1)
                kwargs = m_client.call_args.kwargs
                self.assertTrue(kwargs["vertexai"])
                self.assertEqual(kwargs["project"], "my-gcp-project")
                self.assertEqual(kwargs["location"], "us-central1")
                creds = kwargs["credentials"]
                self.assertEqual(creds._audience, f"//iam.googleapis.com/{provider}")
                self.assertEqual(
                    creds._service_account_impersonation_url,
                    f"https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/{sa_email}:generateAccessToken",
                )
                self.assertEqual(
                    creds._subject_token_supplier.get_subject_token(None, None),
                    "eyJ.test.oidc",
                )

        with patch.dict("os.environ", {}, clear=True):
            with patch("app.genai_provider.genai.Client") as m_client:
                build_genai_client(s_wif)
                m_client.assert_called_once_with(
                    vertexai=True,
                    project="my-gcp-project",
                    location="us-central1",
                    http_options=ANY,
                )

    def test_build_client_vercel_wif_from_request_header_context(self) -> None:
        from app.genai_provider import bind_vercel_oidc_token, reset_vercel_oidc_token

        provider = (
            "projects/123456789012/locations/global/workloadIdentityPools/"
            "vercel-napda-pool/providers/vercel-napda-api"
        )
        sa_email = "napda-vercel-wif@my-gcp-project.iam.gserviceaccount.com"
        s_wif = Settings(
            _env_file=None,
            google_genai_use_vertexai=True,
            google_cloud_project="my-gcp-project",
            google_cloud_location="us-central1",
            gcp_workload_identity_provider=provider,
            gcp_service_account_email=sa_email,
        )

        with patch.dict("os.environ", {}, clear=True):
            reset_tok = bind_vercel_oidc_token("eyJ.header.oidc")
            try:
                with patch("app.genai_provider.genai.Client") as m_client:
                    build_genai_client(s_wif)
                    creds = m_client.call_args.kwargs["credentials"]
                    self.assertEqual(
                        creds._subject_token_supplier.get_subject_token(None, None),
                        "eyJ.header.oidc",
                    )
            finally:
                reset_vercel_oidc_token(reset_tok)

            with patch("app.genai_provider.genai.Client") as m_client:
                build_genai_client(s_wif)
                m_client.assert_called_once_with(
                    vertexai=True,
                    project="my-gcp-project",
                    location="us-central1",
                    http_options=ANY,
                )

    def test_build_client_modal_oidc_wif_credentials(self) -> None:
        from pathlib import Path

        provider = (
            "projects/94766443061/locations/global/workloadIdentityPools/"
            "vercel-napda-pool/providers/modal-dltldn333"
        )
        sa_email = "napda-vercel-wif@gentle-voltage-464223-h6.iam.gserviceaccount.com"
        s_wif = Settings(
            _env_file=None,
            google_genai_use_vertexai=True,
            google_cloud_project="gentle-voltage-464223-h6",
            google_cloud_location="us-central1",
            gcp_workload_identity_provider=provider,
            gcp_service_account_email=sa_email,
        )

        with patch.dict("os.environ", {"MODAL_IDENTITY_TOKEN": "eyJ.modal.env"}, clear=True):
            with patch("app.genai_provider.genai.Client") as m_client:
                build_genai_client(s_wif)
                creds = m_client.call_args.kwargs["credentials"]
                self.assertEqual(
                    creds._subject_token_supplier.get_subject_token(None, None),
                    "eyJ.modal.env",
                )

        with temporary_directory() as tmp:
            tok_file = Path(tmp) / "oidc_token"
            tok_file.write_text("eyJ.modal.file\n", encoding="utf-8")
            with patch.dict("os.environ", {"MODAL_IDENTITY_TOKEN_FILE": str(tok_file)}, clear=True):
                with patch("app.genai_provider.genai.Client") as m_client:
                    build_genai_client(s_wif)
                    creds = m_client.call_args.kwargs["credentials"]
                    self.assertEqual(
                        creds._subject_token_supplier.get_subject_token(None, None),
                        "eyJ.modal.file",
                    )

    def test_vertex_multi_profile_round_robin_and_failover(self) -> None:
        import json
        from types import SimpleNamespace

        from app.genai_provider import reset_vertex_profile_pool

        reset_vertex_profile_pool()
        try:
            profiles_cfg = json.dumps(
                [
                    {"name": "dev1", "project": "proj-dev1", "location": "global"},
                    {"name": "dev2", "project": "proj-dev2", "location": "global"},
                ]
            )
            settings = Settings(
                _env_file=None,
                google_genai_use_vertexai=True,
                gcp_vertex_profiles_json=profiles_cfg,
                gcp_vertex_routing_mode="round_robin",
                gcp_vertex_cooldown_sec=300.0,
            )

            calls: list[str] = []
            fail_projects: set[str] = set()
            err_kind = {"mode": "quota"}

            class _QuotaErr(RuntimeError):
                def __init__(self, msg: str, code: int) -> None:
                    super().__init__(msg)
                    self.code = code

            def _fake_client(*, project: str, **_kw):
                class _Models:
                    def generate_content(self, **_k):
                        calls.append(project)
                        if project in fail_projects:
                            if err_kind["mode"] == "bad_arg":
                                raise _QuotaErr("400 INVALID_ARGUMENT bad prompt", 400)
                            if err_kind["mode"] == "billing":
                                raise _QuotaErr("403 BILLING_DISABLED on account", 403)
                            raise _QuotaErr("429 RESOURCE_EXHAUSTED quota exceeded", 429)
                        return SimpleNamespace(text=f"ok:{project}")

                return SimpleNamespace(models=_Models(), interactions=SimpleNamespace())

            with patch("app.genai_provider.genai.Client", side_effect=_fake_client):
                client = build_genai_client(settings)
                self.assertEqual(client.models.generate_content(model="m", contents="p").text, "ok:proj-dev1")
                self.assertEqual(client.models.generate_content(model="m", contents="p").text, "ok:proj-dev2")
                self.assertEqual(client.models.generate_content(model="m", contents="p").text, "ok:proj-dev1")

                # Next round-robin turn is dev2; make dev2 fail with 429 -> fails over to dev1 and cools down dev2
                fail_projects.add("proj-dev2")
                self.assertEqual(client.models.generate_content(model="m", contents="p").text, "ok:proj-dev1")
                # Subsequent calls skip cooled-down dev2 without even calling it
                calls_before = len(calls)
                self.assertEqual(client.models.generate_content(model="m", contents="p").text, "ok:proj-dev1")
                self.assertEqual(calls[calls_before:], ["proj-dev1"])

                # Non-failover 400 INVALID_ARGUMENT must raise immediately without failing over
                reset_vertex_profile_pool()
                fail_projects.clear()
                fail_projects.add("proj-dev1")
                err_kind["mode"] = "bad_arg"
                calls.clear()
                with self.assertRaises(RuntimeError):
                    client.models.generate_content(model="m", contents="p")
                self.assertEqual(calls, ["proj-dev1"])

                # 403 BILLING_DISABLED fails over cleanly to dev2
                reset_vertex_profile_pool()
                err_kind["mode"] = "billing"
                calls.clear()
                self.assertEqual(client.models.generate_content(model="m", contents="p").text, "ok:proj-dev2")
                self.assertEqual(calls, ["proj-dev1", "proj-dev2"])
        finally:
            reset_vertex_profile_pool()

    def test_vertex_multi_profile_interactions_pin_polling_to_creator(self) -> None:
        import json
        from types import SimpleNamespace

        from app.genai_provider import reset_vertex_profile_pool

        reset_vertex_profile_pool()
        try:
            settings = Settings(
                _env_file=None,
                google_genai_use_vertexai=True,
                gcp_vertex_routing_mode="round_robin",
                gcp_vertex_profiles_json=json.dumps(
                    [
                        {"name": "dev1", "project": "proj-dev1", "location": "global"},
                        {"name": "dev2", "project": "proj-dev2", "location": "global"},
                    ]
                ),
            )
            created: list[str] = []
            polled: list[str] = []

            def _fake_client(*, project: str, **_kw):
                class _Interactions:
                    def create(self, **_k):
                        created.append(project)
                        return SimpleNamespace(id=f"int_{project}_1")

                    def get(self, *, id: str):
                        polled.append(f"{project}:{id}")
                        return SimpleNamespace(id=id, status="completed")

                return SimpleNamespace(models=SimpleNamespace(), interactions=_Interactions())

            with patch("app.genai_provider.genai.Client", side_effect=_fake_client):
                client = build_genai_client(settings)
                inter = client.interactions.create(model="veo", input="hi")
                self.assertEqual(created, ["proj-dev1"])
                # Even in round_robin, polling this interaction ID stays pinned to proj-dev1
                res1 = client.interactions.get(id=inter.id)
                res2 = client.interactions.get(id=inter.id)
                self.assertEqual(res1.status, "completed")
                self.assertEqual(res2.status, "completed")
                self.assertEqual(polled, ["proj-dev1:int_proj-dev1_1", "proj-dev1:int_proj-dev1_1"])
        finally:
            reset_vertex_profile_pool()

    def test_vertex_multi_profile_wif_per_profile(self) -> None:
        import json
        from types import SimpleNamespace

        from app.genai_provider import reset_vertex_profile_pool

        reset_vertex_profile_pool()
        try:
            p1 = "projects/111/locations/global/workloadIdentityPools/pool1/providers/modal1"
            p2 = "projects/222/locations/global/workloadIdentityPools/pool2/providers/modal2"
            sa1 = "sa1@proj-dev1.iam.gserviceaccount.com"
            sa2 = "sa2@proj-dev2.iam.gserviceaccount.com"
            settings = Settings(
                _env_file=None,
                google_genai_use_vertexai=True,
                gcp_vertex_routing_mode="round_robin",
                gcp_vertex_profiles_json=json.dumps(
                    [
                        {"name": "dev1", "project": "proj-dev1", "wif_provider": p1, "service_account_email": sa1},
                        {"name": "dev2", "project": "proj-dev2", "wif_provider": p2, "service_account_email": sa2},
                    ]
                ),
            )
            seen: list[tuple[str, str]] = []

            def _fake_client(*, project: str, credentials=None, **_kw):
                seen.append((project, credentials._audience))
                return SimpleNamespace(
                    models=SimpleNamespace(generate_content=lambda **_k: SimpleNamespace(text=project)),
                    interactions=SimpleNamespace(),
                )

            with patch.dict("os.environ", {"MODAL_IDENTITY_TOKEN": "eyJ.modal.jwt"}, clear=True):
                with patch("app.genai_provider.genai.Client", side_effect=_fake_client):
                    client = build_genai_client(settings)
                    self.assertEqual(client.models.generate_content(model="m", contents="a").text, "proj-dev1")
                    self.assertEqual(client.models.generate_content(model="m", contents="b").text, "proj-dev2")
            self.assertEqual(
                seen,
                [
                    ("proj-dev1", f"//iam.googleapis.com/{p1}"),
                    ("proj-dev2", f"//iam.googleapis.com/{p2}"),
                ],
            )
        finally:
            reset_vertex_profile_pool()
