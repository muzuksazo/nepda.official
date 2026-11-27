"""FR-001 · Safe source_url SSRF protection and HTML candidate fact extraction tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.product_enrichment import (  # noqa: E402
    enrich_product_with_source_url,
    extract_candidate_facts_from_html,
    is_safe_public_url,
)
from tests.support.projects_api import build_test_client, login_client  # noqa: E402
from tests.support.tempdirs import temporary_directory  # noqa: E402


class TestProductEnrichment(unittest.TestCase):
    def test_blocks_ssrf_private_and_loopback_urls(self) -> None:
        self.assertFalse(is_safe_public_url("http://127.0.0.1:8080/admin"))
        self.assertFalse(is_safe_public_url("http://169.254.169.254/latest/meta-data/"))
        self.assertFalse(is_safe_public_url("http://localhost:5000/"))
        self.assertFalse(is_safe_public_url("http://10.0.0.5/secret"))
        self.assertFalse(is_safe_public_url("file:///etc/passwd"))
        self.assertTrue(is_safe_public_url("https://8.8.8.8/product"))

        called = False

        def _fetcher(_url: str) -> str:
            nonlocal called
            called = True
            return "<p>Should never be called</p>"

        res = enrich_product_with_source_url(
            {"name": "타이머", "category": "stationery", "verified_facts": []},
            "http://127.0.0.1/internal",
            fetcher=_fetcher,
        )
        self.assertFalse(called)
        self.assertEqual(res["verified_facts"], [])

    def test_extracts_clean_facts_and_falls_back_on_error(self) -> None:
        html = """
        <html>
          <head>
            <title>60분 비주얼 아날로그 타이머 공식 스토어</title>
            <meta name="description" content="다이얼을 돌리면 빨간 부채꼴 원판이 남은 시간을 보여줍니다" />
          </head>
          <body>
            <ul>
              <li>100% 무조건 효과 보장 최저가 할인</li>
              <li>실리콘 보호 커버로 책상 미끄럼 방지</li>
              <li>실리콘 보호 커버로 책상 미끄럼 방지</li>
              <li>짧음</li>
            </ul>
          </body>
        </html>
        """
        facts = extract_candidate_facts_from_html(html)
        self.assertIn("다이얼을 돌리면 빨간 부채꼴 원판이 남은 시간을 보여줍니다", facts)
        self.assertIn("실리콘 보호 커버로 책상 미끄럼 방지", facts)
        self.assertFalse(any("최저가" in f for f in facts))

        enriched = enrich_product_with_source_url(
            {"name": "아날로그 타이머", "category": "stationery", "verified_facts": ["60분 설정 가능"]},
            "https://8.8.8.8/timer",
            fetcher=lambda _u: html,
        )
        self.assertGreaterEqual(len(enriched["verified_facts"]), 3)
        self.assertEqual(enriched["verified_facts"][0], "60분 설정 가능")

        # Graceful fallback on fetch exception
        fallback = enrich_product_with_source_url(
            {"name": "아날로그 타이머", "category": "stationery", "verified_facts": ["60분 설정 가능"]},
            "https://8.8.8.8/timer",
            fetcher=lambda _u: (_ for _ in ()).throw(RuntimeError("network timeout")),
        )
        self.assertEqual(fallback["verified_facts"], ["60분 설정 가능"])

    def test_product_info_api_persists_cached_entry(self) -> None:
        with temporary_directory() as td:
            client = build_test_client(Path(td))
            login_client(client)
            resp = client.post(
                "/v1/product-info",
                json={
                    "product": {
                        "name": "실리콘 배수구 트랩",
                        "category": "living",
                        "verified_facts": ["물 빠짐 시 자동 개폐", "역류 악취 차단"],
                    },
                    "source_url": "http://127.0.0.1/blocked",
                },
            )
            self.assertEqual(resp.status_code, 200, resp.text)
            self.assertEqual(
                resp.json()["product"]["verified_facts"],
                ["물 빠짐 시 자동 개폐", "역류 악취 차단"],
            )
