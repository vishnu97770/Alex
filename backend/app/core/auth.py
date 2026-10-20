"""User authentication primitives: password hashing, signed access tokens, CSRF double-submit."""

import hashlib
import hmac
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Response

from app.core.config import Settings

ACCESS_COOKIE = "access_token"
CSRF_COOKIE = "csrf_token"
CSRF_HEADER = "x-csrf-token"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

_ph = PasswordHasher()
_DUMMY_HASH = _ph.hash("not-a-real-password")


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    """Always does one hash verification so unknown emails and wrong passwords cost the same."""
    try:
        return _ph.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerificationError, InvalidHashError):
        return False


def issue_token(uid: uuid.UUID, settings: Settings) -> str:
    now = datetime.now(UTC)
    claims = {"sub": str(uid), "iat": now, "exp": now + timedelta(seconds=settings.access_token_ttl_seconds)}
    return jwt.encode(claims, settings.auth_jwt_secret, algorithm="HS256")


def read_token(token: str | None, settings: Settings) -> uuid.UUID | None:
    """None for a missing, expired, tampered or malformed token."""
    if not token:
        return None
    try:
        claims = jwt.decode(
            token, settings.auth_jwt_secret, algorithms=["HS256"], options={"require": ["exp", "sub", "iat"]}
        )
        return uuid.UUID(claims["sub"])
    except (jwt.PyJWTError, ValueError):
        return None


def csrf_for(access_token: str, settings: Settings) -> str:
    return hmac.new(settings.auth_jwt_secret.encode(), access_token.encode(), hashlib.sha256).hexdigest()


def csrf_ok(access_token: str | None, header: str | None, settings: Settings) -> bool:
    return bool(access_token and header) and hmac.compare_digest(csrf_for(access_token or "", settings), header or "")


def set_auth_cookies(response: Response, uid: uuid.UUID, settings: Settings) -> None:
    token = issue_token(uid, settings)
    secure = settings.env == "prod"
    max_age = settings.access_token_ttl_seconds
    response.set_cookie(ACCESS_COOKIE, token, httponly=True, samesite="lax", secure=secure, max_age=max_age, path="/")
    # Readable by the SPA on purpose: it echoes this value in X-CSRF-Token (HMAC of the access token).
    response.set_cookie(
        CSRF_COOKIE, csrf_for(token, settings), httponly=False, samesite="lax", secure=secure, max_age=max_age, path="/"
    )


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")
