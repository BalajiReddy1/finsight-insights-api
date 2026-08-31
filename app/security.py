"""Authentication.

Two modes, one dependency:

- DEV_AUTH (default on): a stranger can run the whole service with no Firebase
  project. Any request carrying `Authorization: Bearer <DEV_AUTH_TOKEN>` is the
  demo user.
- Firebase: when DEV_AUTH is off, the bearer token must be a valid Firebase ID
  token. Signature, audience and issuer are all checked; the reason a token was
  rejected is logged but never returned, because it tells an attacker which
  part of a forged token to fix next.

Protected routes read the user id from `Depends(current_user)` and never from
the request body or query string.
"""

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app import config

bearer_scheme = HTTPBearer(auto_error=False)


def _verify_firebase(token: str) -> str:
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token

    if not config.FIREBASE_PROJECT_ID:
        raise HTTPException(500, detail="FIREBASE_PROJECT_ID is not configured")

    try:
        claims = id_token.verify_firebase_token(
            token, google_requests.Request(), audience=config.FIREBASE_PROJECT_ID
        )
    except Exception as exc:  # expired, malformed, wrong audience, bad signature
        print(f"[auth] token rejected: {exc}")
        raise HTTPException(401, detail="Invalid or expired token")

    issuer = f"https://securetoken.google.com/{config.FIREBASE_PROJECT_ID}"
    if not claims or claims.get("iss") != issuer:
        print(f"[auth] token rejected: issuer {claims.get('iss') if claims else None!r}")
        raise HTTPException(401, detail="Invalid or expired token")

    uid = (claims.get("sub") or "").strip()
    if not uid:
        raise HTTPException(401, detail="Invalid or expired token")
    return uid


def current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> str:
    if creds is None or not creds.credentials:
        raise HTTPException(401, detail="Access token required")
    token = creds.credentials

    if config.DEV_AUTH:
        if token != config.DEV_AUTH_TOKEN:
            raise HTTPException(401, detail="Invalid or expired token")
        return config.DEV_USER_ID

    return _verify_firebase(token)
