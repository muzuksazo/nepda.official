#!/usr/bin/env python3
"""개발용 세션 토큰 발급기 (표준 라이브러리만 사용).

backend/app/auth.py 의 issue_session_token 과 같은 형식(HMAC-SHA256 서명)으로 토큰을 만든다.
Google 로그인 없이 backend/bridge-dev/index.html 의 'Bearer 토큰' 칸에 넣을 값을 얻기 위한 것이다.

    python backend/bridge-dev/dev_token.py                       # 기본 secret (backend 기본값)
    SESSION_SECRET=내비밀 python backend/bridge-dev/dev_token.py   # backend/.env 의 SESSION_SECRET 과 같아야 함
    python backend/bridge-dev/dev_token.py --user abc-worker-b --email b@example.com

주의: 개발 전용이다. 운영 서버에서는 SESSION_SECRET 을 반드시 바꾸고 이 스크립트를 쓰지 않는다.
"""
import argparse
import base64
import hashlib
import hmac
import json
import os
import time

DEFAULT_SECRET = "dev-insecure-change-me"  # backend/app/config.py 의 session_secret 기본값


def b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def issue(secret: str, user_id: str, email: str, ttl_days: int) -> str:
    now = int(time.time())
    payload = {
        "uid": user_id,
        "email": email,
        "name": None,
        "picture": None,
        "iat": now,
        "exp": now + max(1, ttl_days) * 86400,
    }
    body = b64url(json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    sig = hmac.new(secret.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest()
    return f"{body}.{b64url(sig)}"


def main() -> None:
    ap = argparse.ArgumentParser(description="NAPDA 개발용 세션 토큰 발급")
    ap.add_argument("--secret", default=os.environ.get("SESSION_SECRET", DEFAULT_SECRET))
    ap.add_argument("--user", default="dev-user", help="uid (프로젝트 소유자 구분용)")
    ap.add_argument("--email", default="dev@example.com")
    ap.add_argument("--ttl-days", type=int, default=7)
    a = ap.parse_args()
    print(issue(a.secret, a.user, a.email, a.ttl_days))


if __name__ == "__main__":
    main()
