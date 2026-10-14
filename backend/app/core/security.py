"""Workspace identity and internal auth.

The anonymous signed workspace cookie is isolated behind `get_workspace_id`,
so real authentication (JWT/OIDC) can replace it without touching domain code.
"""

import hmac
import uuid

from fastapi import Depends, Header, HTTPException, Request, Response
from itsdangerous import BadSignature, URLSafeSerializer

from app.core.config import Settings, get_settings

COOKIE_NAME = "workspace_id"


def _serializer(settings: Settings) -> URLSafeSerializer:
    return URLSafeSerializer(settings.workspace_cookie_secret, salt="workspace")


def sign_workspace(workspace_id: uuid.UUID, settings: Settings) -> str:
    return _serializer(settings).dumps(str(workspace_id))


def read_workspace_cookie(value: str | None, settings: Settings) -> uuid.UUID | None:
    if not value:
        return None
    try:
        return uuid.UUID(_serializer(settings).loads(value))
    except (BadSignature, ValueError):
        return None


async def require_internal_token(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    expected = f"Bearer {settings.internal_api_token}"
    if not authorization or not hmac.compare_digest(authorization, expected):
        raise HTTPException(status_code=401, detail="invalid internal token")


def set_workspace_cookie(response: Response, workspace_id: uuid.UUID, settings: Settings) -> None:
    response.set_cookie(
        COOKIE_NAME,
        sign_workspace(workspace_id, settings),
        httponly=True,
        samesite="lax",
        secure=settings.env == "prod",
        max_age=60 * 60 * 24 * 365,
    )


def cookie_value(request: Request) -> str | None:
    return request.cookies.get(COOKIE_NAME)
