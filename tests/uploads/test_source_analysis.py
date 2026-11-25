"""Offline regression coverage organized by PRD area."""
from tests.support.media_tools import (
    SourceAnalyzerCase,
    ad_source_analyzer,
    json,
    patch,
)
from tests.support.tempdirs import temporary_directory


class TestSourceAnalyzer(SourceAnalyzerCase):
    def test_aspect_framing_recommendations(self) -> None:
        cases = [
            (532, 532, "1:1", "blur-bleed"),
            (960, 1280, "960:1280", "smart-crop"),
            (720, 1280, "9:16", "full-bleed"),
            (1920, 1080, "16:9", "blur-bleed"),
        ]
        for w, h, exp_aspect, exp_framing in cases:
            payload = {
                "format": {"duration": "8.0", "size": "100000", "bit_rate": "500000"},
                "streams": [
                    {
                        "codec_type": "video",
                        "codec_name": "h264",
                        "width": w,
                        "height": h,
                        "r_frame_rate": "30/1",
                    }
                ],
            }
            with patch.object(ad_source_analyzer.subprocess, "run") as m_run:
                m_run.return_value.stdout = json.dumps(payload)
                meta = ad_source_analyzer.ffprobe_metadata("/tmp/dummy.mp4")
                self.assertEqual(meta["aspect_label"], exp_aspect)
                self.assertEqual(meta["recommended_framing"], exp_framing)
