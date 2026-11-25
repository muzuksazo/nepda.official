"""Offline regression coverage organized by PRD area."""
from tests.support.production import (
    GenAIClientFactoryCase,
    Settings,
    build_genai_client,
    patch,
)
from tests.support.tempdirs import temporary_directory


class TestGenAIClientFactory(GenAIClientFactoryCase):
    def test_build_client_ai_studio_vs_vertex_ai(self) -> None:
        with patch("app.genai_provider.genai.Client") as m_client:
            s_key = Settings(gemini_api_key="AIzaDummyKey", google_genai_use_vertexai=False)
            build_genai_client(s_key)
            m_client.assert_called_once_with(api_key="AIzaDummyKey")

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
            )

        with self.assertRaises(ValueError):
            build_genai_client(Settings(gemini_api_key=None, google_genai_use_vertexai=False))
        with self.assertRaises(ValueError):
            build_genai_client(Settings(google_genai_use_vertexai=True, google_cloud_project=None))
