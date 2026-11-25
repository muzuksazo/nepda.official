"""Offline regression coverage organized by PRD area."""
from tests.support.media_tools import (
    FlowJobsVisualStyleCase,
    ad_flow_jobs,
)
from tests.support.tempdirs import temporary_directory


class TestFlowJobsVisualStyle(FlowJobsVisualStyleCase):
    def test_visual_style_presets_inject_blender_3d_for_timeline_and_variants(self) -> None:
        timeline_spec = {
            "project_id": "test-b3d-tl",
            "mode": "narrative_master",
            "aspect_ratio": "9:16",
            "visual_style": "blender_clay_diorama",
            "timeline": [
                {
                    "id": "A1_b3d",
                    "type": "flow_video",
                    "flow_unit_id": "A1_b3d",
                    "flow_ref_id": "R_A1_b3d",
                    "duration": 5.0,
                    "flow_ref_prompt": "Miniature noir detective beside dry bathroom tiles.",
                    "flow_video_prompt": "Slow camera push across bone-dry clay floor.",
                },
                {"id": "STOP", "type": "silence_gap", "duration": 0.25},
            ],
        }
        jobs_tl = ad_flow_jobs.build_flow_jobs(timeline_spec, res="720p")
        self.assertEqual(jobs_tl["visual_style"], "blender_clay_diorama")
        self.assertEqual(len(jobs_tl["references"]), 1)
        self.assertEqual(len(jobs_tl["units"]), 1)
        self.assertIn("Blender Cycles 3D", jobs_tl["references"][0]["prompt"])
        self.assertIn("zero readable text", jobs_tl["references"][0]["prompt"].lower())
        self.assertIn("Blender Cycles 3D", jobs_tl["units"][0]["prompt"])
        self.assertEqual(jobs_tl["units"][0]["est_credits"], 15)

        var_spec = {
            "project_id": "test-b3d-var",
            "aspect_ratio": "9:16",
            "variants": {
                "B": {
                    "visual_style": "blender_3d_cutaway",
                    "hook_segments": [
                        {
                            "type": "flow_video",
                            "flow_unit_id": "G_B",
                            "flow_ref_id": "R_B",
                            "duration": 5.0,
                            "flow_ref_prompt": "Porous cube cross-section with blue water droplets.",
                            "flow_video_prompt": "Already authored Blender 3D orbit push-in.",
                        }
                    ],
                }
            },
        }
        jobs_var = ad_flow_jobs.build_flow_jobs(var_spec, res="360p")
        self.assertIn("Blender Cycles 3D scientific", jobs_var["references"][0]["prompt"])
        # Idempotent when prompt already mentions Blender
        self.assertTrue(jobs_var["units"][0]["prompt"].startswith("Already authored Blender"))
