import uuid

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import ACCESS_COOKIE, CSRF_HEADER, SAFE_METHODS, csrf_ok, read_token
from app.core.config import Settings, get_settings
from app.core.errors import Forbidden, Unauthorized
from app.db.models import User
from app.db.session import get_session


async def optional_user(request: Request, session: AsyncSession, settings: Settings) -> User | None:
    """Token present, valid, untampered, unexpired, and the user still exists; otherwise None."""
    uid = read_token(request.cookies.get(ACCESS_COOKIE), settings)
    return await session.get(User, uid) if uid else None


def check_csrf(request: Request, settings: Settings) -> None:
    if request.method in SAFE_METHODS:
        return
    if not csrf_ok(request.cookies.get(ACCESS_COOKIE), request.headers.get(CSRF_HEADER), settings):
        raise Forbidden("CSRF check failed")


async def get_current_user(
    request: Request, session: AsyncSession = Depends(get_session), settings: Settings = Depends(get_settings)
) -> User:
    user = await optional_user(request, session, settings)
    if user is None:
        raise Unauthorized("Not authenticated")
    check_csrf(request, settings)
    return user


async def get_user_for_uid(uid: uuid.UUID, user: User = Depends(get_current_user)) -> User:
    """For `/users/{uid}/...` routes: the uid in the URL must be the token's uid."""
    if user.uid != uid:
        raise Forbidden("Not your resource")
    return user
