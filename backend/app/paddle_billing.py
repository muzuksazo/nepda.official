"""Paddle Billing v2 API client, catalog specs, and webhook signature verification."""

from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol

import httpx

from .config import Settings


@dataclass(frozen=True)
class CreditPackageSpec:
    """Credit pack definition backed by a Paddle Price ID."""

    id: str
    credits: int
    price: int
    currency: str
    is_popular: bool
    paddle_price_id: Optional[str]


def get_credit_packages(settings: Settings) -> List[CreditPackageSpec]:
    """Return NAPDA credit packages paired with configured Paddle Price IDs."""
    return [
        CreditPackageSpec(
            id="c30",
            credits=30,
            price=4900,
            currency="KRW",
            is_popular=False,
            paddle_price_id=(settings.paddle_price_c30 or "").strip() or None,
        ),
        CreditPackageSpec(
            id="c100",
            credits=100,
            price=12900,
            currency="KRW",
            is_popular=True,
            paddle_price_id=(settings.paddle_price_c100 or "").strip() or None,
        ),
        CreditPackageSpec(
            id="c300",
            credits=300,
            price=33000,
            currency="KRW",
            is_popular=False,
            paddle_price_id=(settings.paddle_price_c300 or "").strip() or None,
        ),
    ]


class PaddleApiError(RuntimeError):
    """Raised when Paddle Billing API returns an HTTP or payload error."""

    def __init__(self, message: str, *, status_code: int = 502, detail: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail or {}


class PaddleApiClient(Protocol):
    """Minimal Paddle Billing v2 API surface needed for credit checkouts."""

    def create_transaction(
        self,
        *,
        price_id: str,
        custom_data: Dict[str, Any],
        customer_email: Optional[str] = None,
    ) -> Dict[str, Any]: ...

    def get_transaction(self, transaction_id: str) -> Dict[str, Any]: ...


class HttpxPaddleApiClient:
    """Paddle Billing v2 REST client over httpx."""

    def __init__(self, settings: Settings, *, timeout_sec: float = 15.0) -> None:
        self._settings = settings
        self._timeout_sec = timeout_sec

    def _headers(self) -> Dict[str, str]:
        api_key = (self._settings.paddle_api_key or "").strip()
        if not api_key:
            raise PaddleApiError("PADDLE_API_KEY is not configured", status_code=503)
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def create_transaction(
        self,
        *,
        price_id: str,
        custom_data: Dict[str, Any],
        customer_email: Optional[str] = None,
    ) -> Dict[str, Any]:
        base = self._settings.resolved_paddle_api_base_url
        payload: Dict[str, Any] = {
            "collection_mode": "automatic",
            "items": [{"price_id": price_id, "quantity": 1}],
            "custom_data": custom_data,
        }
        _ = customer_email  # Passed to Paddle.Checkout.open({ customer: { email } }) on frontend.
        with httpx.Client(timeout=self._timeout_sec) as client:
            resp = client.post(f"{base}/transactions", headers=self._headers(), json=payload)
        if resp.status_code >= 400:
            raise PaddleApiError(
                f"Paddle transaction creation failed (HTTP {resp.status_code})",
                status_code=502,
                detail={"paddle_status": resp.status_code, "body": resp.text[:500]},
            )
        body = resp.json()
        data = body.get("data") if isinstance(body, dict) else None
        if not isinstance(data, dict) or not data.get("id"):
            raise PaddleApiError("Paddle transaction response missing data.id", status_code=502)
        return data

    def get_transaction(self, transaction_id: str) -> Dict[str, Any]:
        base = self._settings.resolved_paddle_api_base_url
        with httpx.Client(timeout=self._timeout_sec) as client:
            resp = client.get(f"{base}/transactions/{transaction_id}", headers=self._headers())
        if resp.status_code >= 400:
            raise PaddleApiError(
                f"Paddle transaction lookup failed (HTTP {resp.status_code})",
                status_code=502,
                detail={"paddle_status": resp.status_code, "body": resp.text[:500]},
            )
        body = resp.json()
        data = body.get("data") if isinstance(body, dict) else None
        if not isinstance(data, dict):
            raise PaddleApiError("Paddle transaction lookup missing data", status_code=502)
        return data


def verify_paddle_webhook_signature(
    raw_body: bytes,
    signature_header: Optional[str],
    secret: str,
    *,
    now_epoch: Optional[int] = None,
    tolerance_sec: int = 300,
) -> bool:
    """Verify Paddle-Signature (`ts=...;h1=...`) HMAC-SHA256 header with replay protection."""
    if not raw_body or not signature_header or not secret or not secret.strip():
        return False

    ts_str: Optional[str] = None
    signatures: List[str] = []
    for part in signature_header.split(";"):
        if "=" not in part:
            continue
        key, val = part.split("=", 1)
        key = key.strip()
        val = val.strip()
        if key == "ts" and val:
            ts_str = val
        elif key == "h1" and val:
            signatures.append(val.lower())

    if not ts_str or not signatures:
        return False

    try:
        event_ts = int(ts_str)
    except ValueError:
        return False

    cur_ts = int(now_epoch if now_epoch is not None else time.time())
    if abs(cur_ts - event_ts) > max(1, int(tolerance_sec)):
        return False

    signed_payload = f"{ts_str}:".encode("ascii") + raw_body
    expected_hex = hmac.new(secret.strip().encode("utf-8"), signed_payload, hashlib.sha256).hexdigest().lower()
    return any(hmac.compare_digest(expected_hex, sig) for sig in signatures)
