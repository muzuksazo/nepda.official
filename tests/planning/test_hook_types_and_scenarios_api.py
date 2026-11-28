"""FR-002·003·005 · Hook types catalog and scenario generation API tests."""

import unittest
from pathlib import Path

from app.config import Settings
from app.projects_router import (
    _build_beats_from_spec,
    _load_track_a_manifest_entries,
    _safe_beat_caption,
    _select_track_a_template,
)
from tests.support.projects_api import build_test_client, login_client
from tests.support.tempdirs import temporary_directory


class TestHookTypesAndScenariosAPI(unittest.TestCase):
    def test_hook_types_catalog_and_scenario_generation(self) -> None:
        with temporary_directory() as td:
            client = build_test_client(Path(td))
            login_client(client)

            ht = client.get("/v1/hook-types")
            self.assertEqual(ht.status_code, 200)
            types_list = ht.json()["types"]
            self.assertEqual([t["type"] for t in types_list], ["A", "B", "C"])

            proj = client.post(
                "/v1/projects",
                json={
                    "product": {
                        "name": "주방용 실리콘 수세미",
                        "category": "kitchen",
                        "verified_facts": ["끓는 물 소독 가능"],
                    },
                    "selected_types": ["A", "C"],
                },
            ).json()

            scn_resp = client.post(
                f"/v1/projects/{proj['project_id']}/scenarios",
                json={"provider": "anthropic"},
            )
            self.assertEqual(scn_resp.status_code, 200, scn_resp.text)
            data = scn_resp.json()
            self.assertEqual(data["status"], "SCENARIOS_READY")
            self.assertEqual([s["type"] for s in data["scenarios"]], ["A", "C"])

    def test_build_beats_skips_silence_gap_computes_source_duration_and_hides_internal_ids(self) -> None:
        spec = {
            "timeline": [
                {"id": "hook_1", "type": "video", "duration": 4.9, "flow_ref_prompt": "3D 도미노 시작"},
                {"id": "hook_2", "type": "video", "duration": 4.98, "flow_ref_prompt": "50층 도미노 낙하"},
                {"id": "twist_gap", "type": "silence_gap", "duration": 0.25},
                {"id": "payoff_1", "type": "source", "src_start": 0.0, "src_end": 6.5},
            ],
            "captions": [
                {"start": 0.0, "end": 4.8, "text": "1cm 도미노를 2배씩 키우면"},
                {"start": 4.9, "end": 9.8, "text": "마지막 조각은 아파트 50층 높이"},
                {"start": 10.2, "end": 16.5, "text": "물기 즉시 흡수, 댓글로 링크 받기"},
            ],
        }
        beats = _build_beats_from_spec(spec, product_name="초흡수 PVA 물걸레 스펀지")
        self.assertEqual(len(beats), 4)

        # silence_gap must NOT consume spoken captions or leak twist_gap
        gap_beat = beats[2]
        self.assertEqual(gap_beat["role"], "silence_gap")
        self.assertEqual(gap_beat["duration_sec"], 0.25)
        self.assertEqual(gap_beat["caption"], "")
        self.assertEqual(gap_beat["narration"], "")
        self.assertNotIn("twist_gap", gap_beat["visual"])

        # payoff_1 gets the 3rd spoken caption, src_end - src_start = 6.5s, and never leaks payoff_1
        payoff_beat = beats[3]
        self.assertEqual(payoff_beat["role"], "source")
        self.assertAlmostEqual(payoff_beat["duration_sec"], 6.5, places=2)
        self.assertEqual(payoff_beat["caption"], "물기 즉시 흡수, 댓글로 링크 받기")
        self.assertEqual(payoff_beat["narration"], "물기 즉시 흡수, 댓글로 링크 받기")
        self.assertNotIn("payoff_1", payoff_beat["visual"])

        # _safe_beat_caption rejects raw internal IDs even from legacy scenarios
        self.assertEqual(_safe_beat_caption({"caption": "", "narration": "", "visual": "payoff_1"}), "")
        self.assertEqual(_safe_beat_caption({"caption": "", "narration": "", "visual": "twist_gap"}), "")
        self.assertEqual(
            _safe_beat_caption({"caption": "", "narration": "", "visual": "물기 즉시 흡수 시연"}),
            "물기 즉시 흡수 시연",
        )

    def test_track_a_manifest_integrity_and_affinity_varied_selection(self) -> None:
        settings = Settings(_env_file=None)
        entries = _load_track_a_manifest_entries(settings)
        if entries:
            self.assertGreaterEqual(len(entries), 10)
            ids = set()
            for entry in entries:
                tid = str(entry.get("id") or "").strip()
                self.assertTrue(tid)
                self.assertNotIn(tid, ids)
                ids.add(tid)
                mp4 = Path(entry["path"])
                self.assertTrue(mp4.is_file(), f"Missing Track A template MP4: {mp4}")
                self.assertLessEqual(mp4.stat().st_size, 12 * 1024 * 1024, f"Template > 12MB: {mp4}")
                self.assertGreater(float(entry.get("duration_sec") or 0), 2.0, tid)
                self.assertTrue(str(entry.get("visual_summary") or "").strip(), tid)
                self.assertGreaterEqual(len(entry.get("tags") or []), 4, tid)
                self.assertGreaterEqual(len(entry.get("default_hook_captions") or []), 2, tid)
        else:
            # Clean CI checkout where gitignored backend/data/templates/track_a/ is absent
            entries = [
                {"id": "a_domino_docu_3d", "tags": ["도미노", "연쇄", "스케일", "domino"]},
                {"id": "a_jet_umbrella_3d", "tags": ["우산", "강풍", "태풍", "방풍", "wind", "umbrella"]},
                {"id": "a_pendulum_wave_3d", "tags": ["타이머", "집중", "루틴", "시간", "timer", "focus"]},
                {"id": "a_hydraulic_crush_3d", "tags": ["내구성", "충격", "압력", "강화", "케이스", "crush", "durability"]},
                {"id": "a_scale_drop_3d", "tags": ["무게", "하중", "낙하", "weight", "drop"]},
                {"id": "a_ragdoll_launch_3d", "tags": ["탄성", "반발", "점프", "launch", "bounce"]},
                {"id": "a_dam_tape_3d", "tags": ["물기", "흡수", "스펀지", "걸레", "누수", "water", "leak", "dam"]},
                {"id": "a_ps2_subway_rush", "tags": ["출근", "지하철", "통근", "commute", "subway"]},
                {"id": "a_ps2_eoljukah_cafe", "tags": ["텀블러", "얼음", "보냉", "커피", "tumbler", "coffee"]},
                {"id": "a_office_revenge_drama", "tags": ["사무", "오피스", "책상", "문구", "office", "desk"]},
            ]

        # Product affinity routing
        water_proj = {
            "project_id": "prj_water_1",
            "product": {
                "name": "초흡수 PVA 물걸레 스펀지",
                "category": "living",
                "verified_facts": ["바닥 물기 3초 즉시 흡수", "욕실 누수 청소"],
            },
        }
        self.assertEqual(_select_track_a_template(entries, water_proj)["id"], "a_dam_tape_3d")

        wind_proj = {
            "project_id": "prj_wind_1",
            "product": {
                "name": "초강력 방풍 자동 우산",
                "category": "living",
                "verified_facts": ["태풍급 강풍에도 뒤집히지 않음"],
            },
        }
        self.assertEqual(_select_track_a_template(entries, wind_proj)["id"], "a_jet_umbrella_3d")

        crush_proj = {
            "project_id": "prj_crush_1",
            "product": {
                "name": "방탄 강화 충격 보호 케이스",
                "category": "stationery",
                "verified_facts": ["극한 압력 내구성 테스트 통과"],
            },
        }
        self.assertEqual(_select_track_a_template(entries, crush_proj)["id"], "a_hydraulic_crush_3d")

        timer_proj = {
            "project_id": "prj_timer_1",
            "product": {
                "name": "60분 집중 비주얼 타이머",
                "category": "stationery",
                "verified_facts": ["공부 루틴 시간 관리"],
            },
        }
        self.assertEqual(_select_track_a_template(entries, timer_proj)["id"], "a_pendulum_wave_3d")

        # Explicit requested_template_id overrides affinity
        explicit = _select_track_a_template(
            entries, water_proj, requested_template_id="a_ps2_eoljukah_cafe"
        )
        self.assertEqual(explicit["id"], "a_ps2_eoljukah_cafe")

        # Generic projects with no keyword matches diversify across >= 3 distinct templates and stay reproducible
        picked_generic = set()
        for i in range(15):
            generic_proj = {
                "project_id": f"prj_generic_seed_{i:02d}",
                "product": {"name": "신제품 테스트 아이템", "category": "living", "verified_facts": ["특징 확인"]},
            }
            first_pick = _select_track_a_template(entries, generic_proj)["id"]
            second_pick = _select_track_a_template(entries, generic_proj)["id"]
            self.assertEqual(first_pick, second_pick)
            picked_generic.add(first_pick)
        self.assertGreaterEqual(len(picked_generic), 3, picked_generic)
