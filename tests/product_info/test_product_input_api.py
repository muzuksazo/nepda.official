"""FR-001 · Product input contract tests."""

import unittest
from pathlib import Path

from tests.support.projects_api import build_test_client, login_client
from tests.support.tempdirs import temporary_directory


class TestProductInputAPI(unittest.TestCase):
    def test_requires_name_and_category_and_allows_optional_details(self) -> None:
        with temporary_directory() as td:
            client = build_test_client(Path(td))
            login_client(client)

            # Minimal valid payload (verified_facts, price_or_offer & target_audience all optional)
            ok_resp = client.post(
                "/v1/projects",
                json={
                    "product": {
                        "name": "대형 PVA 스펀지",
                        "category": "living",
                    },
                    "selected_types": ["A", "B"],
                },
            )
            self.assertEqual(ok_resp.status_code, 201, ok_resp.text)
            body = ok_resp.json()
            self.assertEqual(body["status"], "PRODUCT_SAVED")
            self.assertEqual(body["selected_types"], ["A", "B"])

            detail_resp = client.get(f"/v1/projects/{body['project_id']}")
            self.assertEqual(detail_resp.status_code, 200)
            self.assertEqual(detail_resp.json()["product"]["verified_facts"], [])

            # Blank verified_facts normalizes to [] and still produces a fallback [F01] [VERIFIED] line
            blank_facts = client.post(
                "/v1/projects",
                json={
                    "product": {
                        "name": "대형 PVA 스펀지",
                        "category": "living",
                        "verified_facts": ["   "],
                    },
                    "selected_types": ["A"],
                },
            )
            self.assertEqual(blank_facts.status_code, 201, blank_facts.text)
            from app.projects_router import _product_to_facts_md

            facts_md = _product_to_facts_md({"name": "대형 PVA 스펀지", "category": "living", "verified_facts": []})
            self.assertIn("[F01] [VERIFIED]", facts_md)

            # Blank name -> 422
            bad_name = client.post(
                "/v1/projects",
                json={
                    "product": {
                        "name": "   ",
                        "category": "living",
                    },
                    "selected_types": ["A"],
                },
            )
            self.assertEqual(bad_name.status_code, 422)

            # Unsupported category -> 422
            bad_cat = client.post(
                "/v1/projects",
                json={
                    "product": {
                        "name": "테스트",
                        "category": "apparel",
                        "verified_facts": ["특징 1"],
                    },
                    "selected_types": ["A"],
                },
            )
            self.assertEqual(bad_cat.status_code, 422)
