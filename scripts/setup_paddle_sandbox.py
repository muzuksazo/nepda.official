#!/usr/bin/env python3
"""Create or verify NAPDA credit catalog (1 Product + 3 KRW Prices) on Paddle Sandbox."""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

ROOT = Path(__file__).resolve().parents[1]
BACKEND_ENV = ROOT / "backend" / ".env"
BACKEND_ENV_EXAMPLE = ROOT / "backend" / ".env.example"

SANDBOX_BASE_URL = "https://sandbox-api.paddle.com"

NAPDA_PACKAGES = (
    {"id": "c30", "credits": 30, "amount": "4900", "env_key": "PADDLE_PRICE_C30", "label": "30 크레딧"},
    {"id": "c100", "credits": 100, "amount": "12900", "env_key": "PADDLE_PRICE_C100", "label": "100 크레딧"},
    {"id": "c300", "credits": 300, "amount": "33000", "env_key": "PADDLE_PRICE_C300", "label": "300 크레딧"},
)


def _load_env_file(path: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k:
            values[k] = v
    return values


def _upsert_env_file(path: Path, updates: Dict[str, str]) -> None:
    if not path.exists():
        if BACKEND_ENV_EXAMPLE.is_file():
            path.write_text(BACKEND_ENV_EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            path.write_text("", encoding="utf-8")

    lines = path.read_text(encoding="utf-8").splitlines()
    remaining = dict(updates)
    new_lines: List[str] = []
    for raw in lines:
        stripped = raw.strip()
        matched_key: Optional[str] = None
        if stripped and not stripped.startswith("#") and "=" in stripped:
            matched_key = stripped.split("=", 1)[0].strip()
        elif stripped.startswith("#"):
            candidate = stripped.lstrip("#").strip()
            if "=" in candidate:
                k_cand = candidate.split("=", 1)[0].strip()
                if k_cand in remaining:
                    matched_key = k_cand
        if matched_key and matched_key in remaining:
            new_lines.append(f"{matched_key}={remaining.pop(matched_key)}")
        else:
            new_lines.append(raw)

    for k, v in remaining.items():
        new_lines.append(f"{k}={v}")

    path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def _list_all(client: httpx.Client, url: str) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    next_url: Optional[str] = url
    while next_url:
        resp = client.get(next_url)
        if resp.status_code >= 400:
            raise RuntimeError(f"GET {next_url} failed ({resp.status_code}): {resp.text}")
        body = resp.json()
        items.extend(body.get("data") or [])
        next_url = (body.get("meta") or {}).get("pagination", {}).get("next")
        if next_url and not body.get("meta", {}).get("pagination", {}).get("has_more"):
            next_url = None
    return items


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-key", help="Paddle Sandbox API key (defaults to PADDLE_API_KEY in env or backend/.env)")
    parser.add_argument("--base-url", default=SANDBOX_BASE_URL, help="Paddle API base URL")
    parser.add_argument("--allow-non-sandbox", action="store_true", help="Allow non-sandbox API key/URL")
    parser.add_argument("--write-env", action="store_true", help="Write resolved PADDLE_PRICE_* into backend/.env")
    args = parser.parse_args()

    file_env = _load_env_file(BACKEND_ENV)
    api_key = (args.api_key or os.environ.get("PADDLE_API_KEY") or file_env.get("PADDLE_API_KEY") or "").strip()
    base_url = args.base_url.rstrip("/")

    if not api_key:
        print("Error: PADDLE_API_KEY is required (pass --api-key or set in backend/.env).", file=sys.stderr)
        return 1

    if not args.allow_non_sandbox:
        if "sandbox" not in base_url:
            print(f"Error: Refusing non-sandbox URL {base_url} without --allow-non-sandbox", file=sys.stderr)
            return 1
        if not api_key.startswith("pdl_sdbx_"):
            print("Error: Expected a Sandbox API key starting with 'pdl_sdbx_'.", file=sys.stderr)
            return 1

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    with httpx.Client(headers=headers, timeout=20.0) as client:
        products = _list_all(client, f"{base_url}/products?per_page=100")
        napda_product = next(
            (
                p
                for p in products
                if (p.get("custom_data") or {}).get("app") == "napda"
                or p.get("name") == "NAPDA 크레딧"
            ),
            None,
        )
        if not napda_product:
            resp = client.post(
                f"{base_url}/products",
                json={
                    "name": "NAPDA 크레딧",
                    "description": "냅다(NAPDA) 숏폼 광고 영상 제작용 크레딧",
                    "tax_category": "standard",
                    "custom_data": {"app": "napda"},
                },
            )
            if resp.status_code >= 400:
                print(f"Error creating product ({resp.status_code}): {resp.text}", file=sys.stderr)
                return 1
            napda_product = resp.json()["data"]
            print(f"Created product: {napda_product['id']} ({napda_product['name']})")
        else:
            print(f"Reusing product: {napda_product['id']} ({napda_product['name']})")

        product_id = napda_product["id"]
        prices = _list_all(client, f"{base_url}/prices?product_id={product_id}&per_page=100")

        resolved_prices: Dict[str, str] = {}
        for pkg in NAPDA_PACKAGES:
            existing = next(
                (
                    pr
                    for pr in prices
                    if (pr.get("custom_data") or {}).get("package_id") == pkg["id"]
                    and (pr.get("unit_price") or {}).get("currency_code") == "KRW"
                    and (pr.get("unit_price") or {}).get("amount") == pkg["amount"]
                    and pr.get("status") == "active"
                ),
                None,
            )
            if not existing:
                resp = client.post(
                    f"{base_url}/prices",
                    json={
                        "product_id": product_id,
                        "description": f"NAPDA {pkg['label']} ({pkg['id']})",
                        "name": f"NAPDA {pkg['label']}",
                        "unit_price": {
                            "amount": pkg["amount"],
                            "currency_code": "KRW",
                        },
                        "quantity": {"minimum": 1, "maximum": 1},
                        "custom_data": {
                            "app": "napda",
                            "package_id": pkg["id"],
                            "credits": pkg["credits"],
                        },
                    },
                )
                if resp.status_code >= 400:
                    print(
                        f"Error creating price {pkg['id']} ({resp.status_code}): {resp.text}",
                        file=sys.stderr,
                    )
                    return 1
                existing = resp.json()["data"]
                print(f"Created price {pkg['id']}: {existing['id']} ({pkg['amount']} KRW)")
            else:
                print(f"Reusing price {pkg['id']}: {existing['id']} ({pkg['amount']} KRW)")

            resolved_prices[pkg["env_key"]] = existing["id"]

    print("\nResolved env values:")
    for k, v in resolved_prices.items():
        print(f"{k}={v}")

    if args.write_env:
        _upsert_env_file(
            BACKEND_ENV,
            {
                "PADDLE_ENVIRONMENT": "sandbox",
                "PADDLE_ACCOUNT_EMAIL": "dudnjsckrgo@gmail.com",
                **resolved_prices,
            },
        )
        print(f"\nUpdated {BACKEND_ENV.relative_to(ROOT)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
