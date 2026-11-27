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
            s_key = Settings(gemini_api_key="AIzaDummyKey", google_genai_use_vertexai=False)
            build_genai_client(s_key)
            m_client.assert_called_once_with(api_key="AIzaDummyKey", http_options=ANY)

        with patch("app.genai_provider.genai.Client") as m_client:
            s_vtx = Settings(
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
            build_genai_client(Settings(gemini_api_key=None, google_genai_use_vertexai=False))
        with self.assertRaises(ValueError):
            build_genai_client(Settings(google_genai_use_vertexai=True, google_cloud_project=None))

    def test_build_client_vercel_wif_credentials(self) -> None:
        provider = (
            "projects/94766443061/locations/global/workloadIdentityPools/"
            "vercel-napda-pool/providers/vercel-provider"
        )
        sa_email = "napda-vercel-wif@gentle-voltage-464223-h6.iam.gserviceaccount.com"
        s_wif = Settings(
            google_genai_use_vertexai=True,
            google_cloud_project="gentle-voltage-464223-h6",
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
                self.assertEqual(kwargs["project"], "gentle-voltage-464223-h6")
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
                    project="gentle-voltage-464223-h6",
                    location="us-central1",
                    http_options=ANY,
                )

    def test_build_client_vercel_wif_from_request_header_context(self) -> None:
        from app.genai_provider import bind_vercel_oidc_token, reset_vercel_oidc_token

        provider = (
            "projects/94766443061/locations/global/workloadIdentityPools/"
            "vercel-napda-pool/providers/vercel-napda-api"
        )
        sa_email = "napda-vercel-wif@gentle-voltage-464223-h6.iam.gserviceaccount.com"
        s_wif = Settings(
            google_genai_use_vertexai=True,
            google_cloud_project="gentle-voltage-464223-h6",
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
                    project="gentle-voltage-464223-h6",
                    location="us-central1",
                    http_options=ANY,
                )
