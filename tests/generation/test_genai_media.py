"""Offline regression coverage organized by PRD area."""
from tests.support.production import (
    GenAIMediaProvider,
    GenAIMediaProviderCase,
    Path,
    Settings,
    SimpleNamespace,
    _FakeInteractions,
    _FakeModels,
    tempfile,
    wave,
)
from tests.support.tempdirs import temporary_directory


class TestGenAIMediaProvider(GenAIMediaProviderCase):
    def test_image_video_polling_and_tts_wav_synthesis(self) -> None:
        with temporary_directory() as td:
            anchor = Path(td) / "anchor.png"
            anchor.write_bytes(self.png_bytes)

            fake_client = SimpleNamespace(
                interactions=_FakeInteractions(png_bytes=self.png_bytes, mp4_bytes=self.mp4_bytes),
                models=_FakeModels(return_wav=False),
            )
            settings = Settings(gemini_api_key="dummy", poll_interval_sec=0.0, video_timeout_sec=10.0)
            provider = GenAIMediaProvider(settings, client=fake_client)

            ref_path = Path(td) / "refs" / "R_A1.png"
            r1 = provider.generate_reference_image(
                "Noir office desk, zero readable text.",
                ref_path,
                anchor_paths=[anchor],
            )
            self.assertFalse(r1.skipped)
            self.assertTrue(ref_path.exists())
            # input list should include text + anchor image
            img_call = fake_client.interactions.created[0]
            self.assertEqual(img_call["model"], "gemini-nano-banana-2.1")
            self.assertEqual(img_call["response_format"]["aspect_ratio"], "9:16")
            self.assertEqual(len(img_call["input"]), 2)

            # Second call should hit idempotency cache without calling API again
            r2 = provider.generate_reference_image("prompt", ref_path, skip_existing=True)
            self.assertTrue(r2.skipped)
            self.assertEqual(len(fake_client.interactions.created), 1)

            # Background video polling
            vid_path = Path(td) / "clips" / "G_A1.mp4"
            v1 = provider.generate_video_clip(
                "Camera pushes toward wet bathroom tiles, zero readable text.",
                vid_path,
                duration_sec=5,
                resolution="720p",
                reference_paths=[ref_path],
                sleep_fn=lambda _: None,
            )
            self.assertFalse(v1.skipped)
            self.assertTrue(vid_path.exists())
            vid_call = fake_client.interactions.created[1]
            self.assertTrue(vid_call["background"])
            self.assertEqual(vid_call["response_format"]["duration"], "5s")

            # Failed status raises loudly
            fail_client = SimpleNamespace(
                interactions=_FakeInteractions(png_bytes=self.png_bytes, mp4_bytes=self.mp4_bytes, fail_video=True),
                models=_FakeModels(),
            )
            fail_provider = GenAIMediaProvider(settings, client=fail_client)
            with self.assertRaises(RuntimeError):
                fail_provider.generate_video_clip(
                    "prompt",
                    Path(td) / "clips" / "fail.mp4",
                    sleep_fn=lambda _: None,
                )

            # Raw PCM L16 TTS gets wrapped into a valid WAV container
            tts_path = Path(td) / "audio" / "beat_01.wav"
            t_res = provider.generate_tts_beat("형사님, 현장에 물 흔적이 사라졌습니다.", tts_path)
            self.assertGreater(t_res.bytes_written, 44)
            with wave.open(str(tts_path), "rb") as wf:
                self.assertEqual(wf.getframerate(), 24000)
                self.assertEqual(wf.getnchannels(), 1)
                self.assertGreater(wf.getnframes(), 1000)

    def test_vertex_billing_labels_only_attached_in_vertex_mode(self) -> None:
        class _RecordingModels:
            def __init__(self) -> None:
                self.configs = []

            def generate_content(self, *, model, contents, config=None):
                self.configs.append((model, config))
                if getattr(config, "response_mime_type", None) == "application/json":
                    return SimpleNamespace(text='{"project_id": "p1"}')
                pcm = b"\x00\x00\x01\x00" * 600
                return SimpleNamespace(
                    candidates=[
                        SimpleNamespace(
                            content=SimpleNamespace(
                                parts=[
                                    SimpleNamespace(
                                        inline_data=SimpleNamespace(
                                            data=pcm,
                                            mime_type="audio/L16;rate=24000",
                                        )
                                    )
                                ]
                            )
                        )
                    ]
                )

        with temporary_directory() as td:
            sheet = Path(td) / "sheet.png"
            sheet.write_bytes(self.png_bytes)

            vtx_models = _RecordingModels()
            vtx_client = SimpleNamespace(
                interactions=_FakeInteractions(png_bytes=self.png_bytes, mp4_bytes=self.mp4_bytes),
                models=vtx_models,
            )
            vtx_settings = Settings(
                google_genai_use_vertexai=True,
                google_cloud_project="gentle-voltage-464223-h6",
                google_cloud_location="us-central1",
            )
            vtx_provider = GenAIMediaProvider(vtx_settings, client=vtx_client)
            vtx_provider.generate_tts_beat("테스트 내레이션", Path(td) / "vtx.wav")
            vtx_provider.plan_ad_spec("facts", {"duration": 15.0}, sheet)

            self.assertEqual(len(vtx_models.configs), 2)
            self.assertEqual(vtx_models.configs[0][1].labels, {"app": "napda", "component": "tts"})
            self.assertEqual(vtx_models.configs[1][1].labels, {"app": "napda", "component": "planner"})

            key_models = _RecordingModels()
            key_client = SimpleNamespace(
                interactions=_FakeInteractions(png_bytes=self.png_bytes, mp4_bytes=self.mp4_bytes),
                models=key_models,
            )
            key_settings = Settings(gemini_api_key="dummy", google_genai_use_vertexai=False)
            key_provider = GenAIMediaProvider(key_settings, client=key_client)
            key_provider.generate_tts_beat("테스트 내레이션", Path(td) / "key.wav")
            key_provider.plan_ad_spec("facts", {"duration": 15.0}, sheet)

            self.assertEqual(len(key_models.configs), 2)
            self.assertIsNone(key_models.configs[0][1].labels)
            self.assertIsNone(key_models.configs[1][1].labels)
