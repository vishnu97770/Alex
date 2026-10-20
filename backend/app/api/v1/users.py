import os
import uuid
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth_deps import get_user_for_uid
from app.api.v1.auth import user_out
from app.core.config import Settings, get_settings
from app.core.errors import AppError, NotFound
from app.db.models import User
from app.db.session import get_session
from app.schemas.account import UserOut

router = APIRouter(prefix="/users/{uid}", tags=["users"])

# magic bytes -> (extension, media type); the client-declared content type is never trusted
_SNIFF = (
    (b"\x89PNG\r\n\x1a\n", "png", "image/png"),
    (b"\xff\xd8\xff", "jpg", "image/jpeg"),
    (b"GIF87a", "gif", "image/gif"),
    (b"GIF89a", "gif", "image/gif"),
)
_MEDIA = {"png": "image/png", "jpg": "image/jpeg", "gif": "image/gif", "webp": "image/webp"}


class BadImage(AppError):
    status_code, code = 422, "bad_image"


def _avatar_dir(settings: Settings) -> Path:
    d = Path(settings.upload_dir) / "avatars"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _sniff(data: bytes) -> str | None:
    for magic, ext, _ in _SNIFF:
        if data.startswith(magic):
            return ext
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


@router.get("", response_model=UserOut)
async def get_user(user: User = Depends(get_user_for_uid), session: AsyncSession = Depends(get_session)) -> UserOut:
    return await user_out(session, user)


@router.put("/avatar", response_model=UserOut)
async def upload_avatar(
    request: Request,
    user: User = Depends(get_user_for_uid),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> UserOut:
    """Raw image bytes in the body (png, jpeg, gif or webp, up to AVATAR_MAX_BYTES)."""
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > settings.avatar_max_bytes:
        raise BadImage("Image is too large")
    data = bytearray()
    async for chunk in request.stream():
        data += chunk
        if len(data) > settings.avatar_max_bytes:
            raise BadImage("Image is too large")
    ext = _sniff(bytes(data))
    if ext is None:
        raise BadImage("Only PNG, JPEG, GIF or WebP images are allowed")
    name = f"{uuid.uuid4().hex}.{ext}"  # non-guessable, never derived from user input
    (_avatar_dir(settings) / name).write_bytes(bytes(data))
    old = user.avatar_path
    user.avatar_path, user.avatar_updated_at = name, datetime.now(UTC)
    await session.commit()
    if old:
        (_avatar_dir(settings) / os.path.basename(old)).unlink(missing_ok=True)
    return await user_out(session, user)


@router.get("/avatar")
async def get_avatar(
    user: User = Depends(get_user_for_uid), settings: Settings = Depends(get_settings)
) -> FileResponse:
    if not user.avatar_path:
        raise NotFound("No avatar")
    path = _avatar_dir(settings) / os.path.basename(user.avatar_path)
    if not path.is_file():
        raise NotFound("No avatar")
    return FileResponse(
        path,
        media_type=_MEDIA.get(path.suffix.lstrip("."), "application/octet-stream"),
        headers={"Cache-Control": "private, max-age=3600", "X-Content-Type-Options": "nosniff"},
    )
