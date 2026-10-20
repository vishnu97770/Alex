import asyncio
import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth_deps import get_current_user
from app.core.auth import clear_auth_cookies, set_auth_cookies, verify_password
from app.core.config import Settings, get_settings
from app.core.errors import Conflict, Unauthorized
from app.core.ratelimit import limiter
from app.db.models import User
from app.db.session import get_session
from app.schemas.account import AuthConfigOut, LoginIn, RegisterIn, UserOut
from app.services import account_service, audit_service

log = logging.getLogger("auth")
router = APIRouter(prefix="/auth", tags=["auth"])

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_CERTS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = ("https://accounts.google.com", "accounts.google.com")
OAUTH_COOKIE = "oauth_state"


async def user_out(s: AsyncSession, user: User) -> UserOut:
    return UserOut(
        uid=str(user.uid),
        username=user.username,
        email=user.email,
        avatar_url=account_service.avatar_url(user),
        agent_count=await account_service.agent_count(s, user.uid),
    )


@router.get("/config", response_model=AuthConfigOut)
async def auth_config(settings: Settings = Depends(get_settings)) -> AuthConfigOut:
    return AuthConfigOut(google=settings.google_enabled)


@router.post("/register", response_model=UserOut, status_code=201)
@limiter.limit(lambda: get_settings().rate_limit_auth)
async def register(
    request: Request,
    response: Response,
    body: RegisterIn,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> UserOut:
    user = await account_service.create_user(session, username=body.username, email=body.email, password=body.password)
    set_auth_cookies(response, user.uid, settings)
    return await user_out(session, user)


@router.post("/login", response_model=UserOut)
@limiter.limit(lambda: get_settings().rate_limit_auth)
async def login(
    request: Request,
    response: Response,
    body: LoginIn,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> UserOut:
    user = await account_service.get_by_email(session, body.email)
    # one generic message for unknown email / wrong password / Google-only account
    if not verify_password(user.password_hash if user else None, body.password) or user is None:
        raise Unauthorized("Incorrect email or password")
    await audit_service.record(
        session, "user.login", actor="user", workspace_id=user.workspace_id, payload={"uid": str(user.uid)}
    )
    await session.commit()
    set_auth_cookies(response, user.uid, settings)
    return await user_out(session, user)


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)) -> UserOut:
    return await user_out(session, user)


@router.post("/logout")
async def logout(response: Response) -> dict[str, str]:
    clear_auth_cookies(response)
    return {"status": "logged_out"}


def _fail(settings: Settings, reason: str) -> RedirectResponse:
    r = RedirectResponse(f"{settings.app_origin.rstrip('/')}/checkin?error={reason}", status_code=302)
    r.delete_cookie(OAUTH_COOKIE, path="/")
    return r


@router.get("/google/start")
async def google_start(settings: Settings = Depends(get_settings)) -> RedirectResponse:
    if not settings.google_enabled:
        return _fail(settings, "google_not_configured")
    state, nonce = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "nonce": nonce,
        "prompt": "select_account",
    }
    r = RedirectResponse(f"{GOOGLE_AUTH_URL}?{urlencode(params)}", status_code=302)
    cookie = jwt.encode(
        {"state": state, "nonce": nonce, "exp": datetime.now(UTC) + timedelta(minutes=10)},
        settings.auth_jwt_secret,
        algorithm="HS256",
    )
    r.set_cookie(
        OAUTH_COOKIE, cookie, httponly=True, samesite="lax", secure=settings.env == "prod", max_age=600, path="/"
    )
    return r


def _verify_google_id_token(id_token: str, settings: Settings) -> dict[str, object]:
    key = jwt.PyJWKClient(GOOGLE_CERTS_URL).get_signing_key_from_jwt(id_token).key
    return jwt.decode(
        id_token,
        key,
        algorithms=["RS256"],
        audience=settings.google_client_id,
        issuer=list(GOOGLE_ISSUERS),
        options={"require": ["exp", "iss", "aud", "sub"]},
    )


@router.get("/google/callback")
async def google_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    if not settings.google_enabled:
        return _fail(settings, "google_not_configured")
    try:
        saved = jwt.decode(request.cookies.get(OAUTH_COOKIE, ""), settings.auth_jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        return _fail(settings, "google_failed")
    if not code or not state or not secrets.compare_digest(state, str(saved.get("state"))):
        return _fail(settings, "google_failed")
    try:
        async with httpx.AsyncClient(timeout=10) as http:
            tok = await http.post(
                GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "redirect_uri": settings.google_redirect,
                    "grant_type": "authorization_code",
                },
            )
        tok.raise_for_status()
        claims = await asyncio.to_thread(_verify_google_id_token, tok.json()["id_token"], settings)
        if not secrets.compare_digest(str(claims.get("nonce", "")), str(saved.get("nonce"))):
            raise ValueError("nonce mismatch")
        if claims.get("email_verified") is not True or not claims.get("email"):
            raise ValueError("email not verified")
    except Exception:
        log.warning("google sign-in failed", exc_info=True)
        return _fail(settings, "google_failed")

    email, sub = str(claims["email"]).lower(), str(claims["sub"])
    user = await session.scalar(select(User).where(User.google_sub == sub))
    if user is None:
        user = await account_service.get_by_email(session, email)
        if user is not None and user.google_sub not in (None, sub):
            return _fail(settings, "google_failed")
        if user is not None:  # verified Google email matches an existing account: link it
            user.google_sub = sub
            await session.commit()
    if user is None:
        try:
            user = await account_service.create_user(
                session,
                username=str(claims.get("name") or account_service.username_from_email(email))[:40],
                email=email,
                google_sub=sub,
            )
        except Conflict:
            return _fail(settings, "google_failed")
    r = RedirectResponse(f"{settings.app_origin.rstrip('/')}/dashboard/{uuid.UUID(str(user.uid))}", status_code=302)
    set_auth_cookies(r, user.uid, settings)
    r.delete_cookie(OAUTH_COOKIE, path="/")
    return r
