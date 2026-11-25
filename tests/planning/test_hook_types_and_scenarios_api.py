"""FR-002·003·005 · Hook types catalog and scenario generation API tests."""

import unittest
from pathlib import Path

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
