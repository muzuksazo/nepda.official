"""Offline regression coverage organized by PRD area."""
from tests.support.production import (
    CampaignRequest,
    GenAIMediaProvider,
    JobStore,
    LintFailedError,
    Path,
    ProductionPipeline,
    ProductionPipelineAndAPICase,
    Settings,
    SimpleNamespace,
    _FakeInteractions,
    _FakeModels,
    tempfile,
)
from tests.support.tempdirs import temporary_directory
from urllib.parse import urlsplit
from urllib.request import url2pathname


class TestProductionPipelineAndAPI(ProductionPipelineAndAPICase):
    def test_end_to_end_pipeline_gate_a_render_and_reskin_block(self) -> None:
        with temporary_directory() as td:
            root = Path(td)
            settings = Settings(
                gemini_api_key="dummy",
                work_root=str(root / "work"),
                db_path=str(root / "jobs.db"),
                poll_interval_sec=0.0,
            )
            store = JobStore(settings.db_path)
            fake_client = SimpleNamespace(
                interactions=_FakeInteractions(png_bytes=self.png_bytes, mp4_bytes=self.mp4_bytes),
                models=_FakeModels(return_wav=True),
            )
            provider = GenAIMediaProvider(settings, client=fake_client)
            pipeline = ProductionPipeline(settings, store, provider_factory=lambda _: provider)

            # 1) Bad spec blocked BEFORE paid calls
            bad_dir = root / "bad"
            bad_dir.mkdir()
            bad_src, bad_facts, bad_spec = self._write_valid_campaign_inputs(bad_dir, bad_c_hook=True)
            with self.assertRaises(LintFailedError):
                pipeline.run_campaign(
                    CampaignRequest(
                        campaign_id="bad-camp",
                        source_video=str(bad_src),
                        facts_path=str(bad_facts),
                        spec_path=str(bad_spec),
                    )
                )
            self.assertEqual(len(fake_client.interactions.created), 0)

            # 2) Valid campaign renders real MP4 + SRT + QA strip + records archetype
            good_dir = root / "good"
            good_dir.mkdir()
            src1, facts1, spec1 = self._write_valid_campaign_inputs(good_dir, a_genre="noir_interrogation")
            res = pipeline.run_campaign(
                CampaignRequest(
                    campaign_id="good-camp-1",
                    source_video=str(src1),
                    facts_path=str(facts1),
                    spec_path=str(spec1),
                )
            )
            self.assertEqual(res["status"], "QC_READY")
            rendered = res["artifacts"]["rendered"][0]
            self.assertTrue(rendered["master_mp4"].startswith("file://"))
            master_file = Path(url2pathname(urlsplit(rendered["master_mp4"]).path))
            self.assertTrue(master_file.exists())
            self.assertGreater(master_file.stat().st_size, 10_000)

            # 3) Second campaign reusing identical a_genre_archetype is blocked by --compare-campaigns
            reskin_dir = root / "reskin"
            reskin_dir.mkdir()
            src2, facts2, spec2 = self._write_valid_campaign_inputs(reskin_dir, a_genre="noir_interrogation")
            with self.assertRaises(LintFailedError):
                pipeline.run_campaign(
                    CampaignRequest(
                        campaign_id="good-camp-2",
                        source_video=str(src2),
                        facts_path=str(facts2),
                        spec_path=str(spec2),
                    )
                )
