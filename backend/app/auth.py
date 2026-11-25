"""Google One Tap ID-token verification and HMAC-SHA256 session cookies."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

SESSION_COOKIE_NAME = "napda_session"


class AuthenticationError(ValueError):
    """Raised when Google ID-token verification or session validation fails."""


@dataclass(frozen=True)
class AuthenticatedUser:
    """Verified end-user identity attached to a Google account."""

    user_id: str
    email: str
    name: Optional[str] = None
    picture: Optional[str] = None


def verify_google_id_token(credential: str, client_id: str) -> AuthenticatedUser:
    """Verify a Google One Tap / GIS JWT credential using Google's public certs."""
    if not credential or not credential.strip():
        raise AuthenticationError("Google credential is required")
    if not client_id or not client_id.strip():
        raise AuthenticationError("GOOGLE_CLIENT_ID is not configured on the server")
    try:
        idinfo = google_id_token.verify_oauth2_token(
            credential.strip(),
            google_requests.Request(),
            client_id.strip(),
        )
    except Exception as exc:
        raise AuthenticationError(f"Invalid Google ID token: {exc}") from exc

    sub = str(idinfo.get("sub") or "").strip()
    email = str(idinfo.get("email") or "").strip()
    if not sub or not email:
        raise AuthenticationError("Google ID token missing sub or email claim")

    return AuthenticatedUser(
        user_id=sub,
        email=email,
        name=idinfo.get("name"),
        picture=idinfo.get("picture"),
    )


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64url_decode(val: str) -> bytes:
    pad = "=" * (-len(val) % 4)
    return base64.urlsafe_b64decode(val + pad)


def issue_session_token(
    user: AuthenticatedUser,
    secret: str,
    *,
    ttl_days: int = 7,
    now: Optional[datetime] = None,
) -> Tuple[str, str]:
    """Issue a signed session token + ISO-8601 expiration timestamp."""
    if not secret:
        raise ValueError("session_secret must not be empty")
    issued_at = now or datetime.now(timezone.utc)
    expires_at = issued_at + timedelta(days=max(1, int(ttl_days)))
    payload = {
        "uid": user.user_id,
        "email": user.email,
        "name": user.name,
        "picture": user.picture,
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    body = _b64url_encode(json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    sig = hmac.new(secret.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest()
    return f"{body}.{_b64url_encode(sig)}", expires_at.isoformat()


def verify_session_token(
    token: str,
    secret: str,
    *,
    now: Optional[datetime] = None,
) -> AuthenticatedUser:
    """Validate signature & expiration of a signed NAPDA session token."""
    if not token or "." not in token:
        raise AuthenticationError("Malformed session token")
    body, sig_b64 = token.split(".", 1)
    expected_sig = _b64url_encode(
        hmac.new(secret.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest()
    )
    if not hmac.compare_digest(sig_b64, expected_sig):
        raise AuthenticationError("Invalid session signature")
    try:
        payload = json.loads(_b64url_decode(body).decode("utf-8"))
    except Exception as exc:
        raise AuthenticationError("Corrupt session payload") from exc

    cur_ts = int((now or datetime.now(timezone.utc)).timestamp())
    if int(payload.get("exp") or 0) <= cur_ts:
        raise AuthenticationError("Session token expired")

    uid = str(payload.get("uid") or "").strip()
    email = str(payload.get("email") or "").strip()
    if not uid or not email:
        raise AuthenticationError("Session token missing user identity")

    return AuthenticatedUser(
        user_id=uid,
        email=email,
        name=payload.get("name"),
        picture=payload.get("picture"),
    )
