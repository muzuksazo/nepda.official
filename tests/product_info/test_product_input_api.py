"""FR-001 · Product input contract tests."""

import unittest
from pathlib import Path

from tests.support.projects_api import build_test_client, login_client
from tests.support.tempdirs import temporary_directory


class TestProductInputAPI(unittest.TestCase):
    def test_requires_minimum_product_fields_and_allows_optional_offer(self) -> None:
        with temporary_directory() as td:
            client = build_test_client(Path(td))
            login_client(client)

            # Minimal valid payload (price_or_offer & target_audience omitted)
            ok_resp = client.post(
                "/v1/projects",
                json={
                    "product": {
                        "name": "대형 PVA 스펀지",
                        "category": "living",
                        "verified_facts": ["1,000원대 대형 블록 소분 사용"],
                    },
                    "selected_types": ["A", "B"],
                },
            )
            self.assertEqual(ok_resp.status_code, 201, ok_resp.text)
            body = ok_resp.json()
            self.assertEqual(body["status"], "PRODUCT_SAVED")
            self.assertEqual(body["selected_types"], ["A", "B"])

            # Empty verified_facts -> 422
            bad_facts = client.post(
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
            self.assertEqual(bad_facts.status_code, 422)

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
