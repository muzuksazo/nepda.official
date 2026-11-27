"""Paddle Sandbox billing config, checkout, webhook signature, and idempotent credit ledger tests."""

from __future__ import annotations

import hashlib
import hmac
import json
import sys
import time
import unittest
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi.testclient import TestClient

from tests.support.projects_api import fake_google_verifier, login_client
from tests.support.tempdirs import temporary_directory

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.config import Settings  # noqa: E402
from app.server import create_app  # noqa: E402


class FakePaddleClient:
    def __init__(self) -> None:
        self.created: list[Dict[str, Any]] = []
        self.statuses: Dict[str, str] = {}
        self.custom_data_by_txn: Dict[str, Dict[str, Any]] = {}

    def create_transaction(
        self,
        *,
        price_id: str,
        custom_data: Dict[str, Any],
        customer_email: Optional[str] = None,
    ) -> Dict[str, Any]:
        txn_id = f"txn_test_{len(self.created) + 1:04d}"
        self.created.append(
            {
                "txn_id": txn_id,
                "price_id": price_id,
                "custom_data": custom_data,
                "customer_email": customer_email,
            }
        )
        self.statuses[txn_id] = "ready"
        self.custom_data_by_txn[txn_id] = dict(custom_data)
        return {
            "id": txn_id,
            "status": "ready",
            "checkout": {"url": f"https://sandbox-buy.paddle.com/checkout/{txn_id}"},
        }

    def get_transaction(self, transaction_id: str) -> Dict[str, Any]:
        return {
            "id": transaction_id,
            "status": self.statuses.get(transaction_id, "ready"),
            "custom_data": self.custom_data_by_txn.get(transaction_id, {}),
        }


def _sign_paddle_payload(raw_body: bytes, secret: str, ts: Optional[int] = None) -> str:
    stamp = str(ts if ts is not None else int(time.time()))
    signed = f"{stamp}:".encode("ascii") + raw_body
    digest = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    return f"ts={stamp};h1={digest}"


def _build_billing_client(
    root: Path,
    *,
    paddle_client: Optional[FakePaddleClient] = None,
    configured: bool = True,
) -> TestClient:
    settings = Settings(
        _env_file=None,
        gemini_api_key="dummy-key",
        google_client_id="dummy-client-id.apps.googleusercontent.com",
        session_secret="test-session-secret-32bytes-minimum",
        work_root=str(root / "work"),
        output_dir=str(root / "outputs"),
        db_path=str(root / "napda.db"),
        paddle_environment="sandbox",
        paddle_api_key="pdl_sdbx_apikey_dummy" if configured else None,
        paddle_client_token="test_dummy_client_token" if configured else None,
        paddle_webhook_secret="pdl_ntfset_dummy_secret" if configured else None,
        paddle_price_c30="pri_c30_dummy" if configured else None,
        paddle_price_c100="pri_c100_dummy" if configured else None,
        paddle_price_c300="pri_c300_dummy" if configured else None,
    )
    app = create_app(
        settings=settings,
        google_token_verifier=fake_google_verifier,
        paddle_client=paddle_client,
    )
    return TestClient(app)


class TestPaddleBillingAPI(unittest.TestCase):
    def test_billing_config_and_unconfigured_guard(self) -> None:
        with temporary_directory() as td:
            client = _build_billing_client(Path(td), configured=False)
            cfg = client.get("/v1/billing/config")
            self.assertEqual(cfg.status_code, 200, cfg.text)
            body = cfg.json()
            self.assertEqual(body["provider"], "paddle")
            self.assertEqual(body["environment"], "sandbox")
            self.assertFalse(body["enabled"])
            self.assertEqual(len(body["packages"]), 3)

            login_client(client, "bill-u0:dudnjsckrgo@gmail.com")
            blocked = client.post("/v1/billing/checkout", json={"package_id": "c100"})
            self.assertEqual(blocked.status_code, 503)
            self.assertEqual(blocked.json()["detail"]["error"]["code"], "BILLING_NOT_CONFIGURED")

    def test_checkout_webhook_signature_and_idempotent_crediting(self) -> None:
        with temporary_directory() as td:
            fake_paddle = FakePaddleClient()
            client = _build_billing_client(Path(td), paddle_client=fake_paddle, configured=True)

            cfg = client.get("/v1/billing/config").json()
            self.assertTrue(cfg["enabled"])
            self.assertEqual(cfg["client_token"], "test_dummy_client_token")

            login_client(client, "bill-u1:dudnjsckrgo@gmail.com")
            w0 = client.get("/v1/billing/wallet")
            self.assertEqual(w0.status_code, 200, w0.text)
            self.assertEqual(w0.json()["credits"], 0)
            self.assertTrue(w0.json()["has_free_video"])

            chk = client.post("/v1/billing/checkout", json={"package_id": "c100"})
            self.assertEqual(chk.status_code, 200, chk.text)
            chk_body = chk.json()
            self.assertEqual(chk_body["amount_krw"], 12900)
            self.assertEqual(chk_body["credits"], 100)
            self.assertEqual(chk_body["paddle_environment"], "sandbox")
            self.assertEqual(chk_body["paddle_price_id"], "pri_c100_dummy")
            self.assertEqual(chk_body["customer_email"], "dudnjsckrgo@gmail.com")
            order_id = chk_body["order_id"]
            txn_id = chk_body["paddle_transaction_id"]

            # Invalid signature -> 401
            payload = {
                "event_id": "evt_001",
                "event_type": "transaction.completed",
                "data": {
                    "id": txn_id,
                    "status": "completed",
                    "custom_data": {"order_id": order_id},
                },
            }
            raw = json.dumps(payload).encode("utf-8")
            bad_sig = client.post(
                "/v1/billing/webhooks/paddle",
                content=raw,
                headers={"Paddle-Signature": "ts=1700000000;h1=deadbeef", "Content-Type": "application/json"},
            )
            self.assertEqual(bad_sig.status_code, 401)

            # Stale timestamp -> 401
            stale_ts = int(time.time()) - 900
            stale_sig = _sign_paddle_payload(raw, "pdl_ntfset_dummy_secret", ts=stale_ts)
            stale_resp = client.post(
                "/v1/billing/webhooks/paddle",
                content=raw,
                headers={"Paddle-Signature": stale_sig, "Content-Type": "application/json"},
            )
            self.assertEqual(stale_resp.status_code, 401)

            # Valid signature -> credits once
            valid_sig = _sign_paddle_payload(raw, "pdl_ntfset_dummy_secret")
            ok_resp = client.post(
                "/v1/billing/webhooks/paddle",
                content=raw,
                headers={"Paddle-Signature": valid_sig, "Content-Type": "application/json"},
            )
            self.assertEqual(ok_resp.status_code, 200, ok_resp.text)
            self.assertTrue(ok_resp.json()["credited"])
            self.assertEqual(ok_resp.json()["order_id"], order_id)

            # Duplicate webhook delivery -> credited=False, balance stays 100
            dup_resp = client.post(
                "/v1/billing/webhooks/paddle",
                content=raw,
                headers={"Paddle-Signature": valid_sig, "Content-Type": "application/json"},
            )
            self.assertEqual(dup_resp.status_code, 200, dup_resp.text)
            self.assertFalse(dup_resp.json()["credited"])

            # Subsequent order sync must not double credit either
            fake_paddle.statuses[txn_id] = "completed"
            ord_resp = client.get(f"/v1/billing/orders/{order_id}?sync=true")
            self.assertEqual(ord_resp.status_code, 200, ord_resp.text)
            self.assertEqual(ord_resp.json()["status"], "completed")
            self.assertEqual(ord_resp.json()["wallet"]["credits"], 100)

    def test_order_polling_sync_credits_once_and_isolates_users(self) -> None:
        with temporary_directory() as td:
            fake_paddle = FakePaddleClient()
            client = _build_billing_client(Path(td), paddle_client=fake_paddle, configured=True)

            token1 = login_client(client, "bill-u1:u1@example.com")
            chk = client.post("/v1/billing/checkout", json={"package_id": "c30"}).json()
            order_id = chk["order_id"]
            txn_id = chk["paddle_transaction_id"]

            # Still pending before Paddle completes
            pending = client.get(f"/v1/billing/orders/{order_id}?sync=true")
            self.assertEqual(pending.status_code, 200)
            self.assertEqual(pending.json()["status"], "pending")
            self.assertEqual(pending.json()["wallet"]["credits"], 0)

            # Paddle finishes transaction -> sync completes order & grants 30 credits
            fake_paddle.statuses[txn_id] = "completed"
            done = client.get(f"/v1/billing/orders/{order_id}?sync=true")
            self.assertEqual(done.status_code, 200)
            self.assertEqual(done.json()["status"], "completed")
            self.assertEqual(done.json()["wallet"]["credits"], 30)

            # Second poll stays at 30
            done2 = client.get(f"/v1/billing/orders/{order_id}?sync=true")
            self.assertEqual(done2.json()["wallet"]["credits"], 30)

            # Other user cannot read order_id
            login_client(client, "bill-u2:u2@example.com")
            other = client.get(f"/v1/billing/orders/{order_id}")
            self.assertEqual(other.status_code, 404)

            # Original user still sees 30 credits
            w1 = client.get("/v1/billing/wallet", headers={"Authorization": f"Bearer {token1}"})
            self.assertEqual(w1.status_code, 200)
            self.assertEqual(w1.json()["credits"], 30)
