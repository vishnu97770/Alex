from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.correlation import get_correlation_id


class AppError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class NotFound(AppError):
    status_code, code = 404, "not_found"


class Unauthorized(AppError):
    status_code, code = 401, "unauthorized"


class Forbidden(AppError):
    status_code, code = 403, "forbidden"


class PaymentRejected(AppError):
    status_code, code = 402, "payment_rejected"


class Conflict(AppError):
    status_code, code = 409, "conflict"


class IllegalTransition(AppError):
    status_code, code = 409, "illegal_transition"


class NotConfigured(AppError):
    status_code, code = 503, "not_configured"


class UpstreamError(AppError):
    status_code, code = 502, "upstream_error"


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message, "correlation_id": get_correlation_id()}},
        )
