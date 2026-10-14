import uuid

from fastapi import Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.security import cookie_value, read_workspace_cookie, set_workspace_cookie
from app.db.models import Workspace
from app.db.session import get_session


async def get_optional_workspace_id(
    request: Request, session: AsyncSession = Depends(get_session), settings: Settings = Depends(get_settings)
) -> uuid.UUID | None:
    """Read-only paths must not create workspaces (an error response would also drop the Set-Cookie)."""
    wid = read_workspace_cookie(cookie_value(request), settings)
    if wid is not None and await session.get(Workspace, wid) is not None:
        return wid
    return None


async def get_workspace_id(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> uuid.UUID:
    """Swap this dependency for JWT/OIDC later; every route only sees a workspace id."""
    wid = read_workspace_cookie(cookie_value(request), settings)
    if wid is not None and await session.get(Workspace, wid) is not None:
        return wid
    ws = Workspace()
    session.add(ws)
    await session.commit()
    set_workspace_cookie(response, ws.id, settings)
    return ws.id
