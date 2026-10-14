import logging
import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter, Histogram

from app.api.v1 import health
from app.core.config import get_settings
from app.core.correlation import correlation_id_var, new_correlation_id
from app.core.errors import install_error_handlers
from app.core.logging import configure_logging

log = logging.getLogger("app")
REQUESTS = Counter("http_requests_total", "HTTP requests", ["method", "status"])
LATENCY = Histogram("http_request_seconds", "HTTP latency", ["method"])


def create_app() -> FastAPI:
    settings = get_settings()  # fail fast on bad config
    configure_logging(settings.log_level)
    app = FastAPI(title="Voice Agent Platform API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.app_origin],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT"],
        allow_headers=["Content-Type", "X-Correlation-ID"],
    )

    @app.middleware("http")
    async def correlation(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        cid = request.headers.get("x-correlation-id") or new_correlation_id()
        token = correlation_id_var.set(cid)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            correlation_id_var.reset(token)
        response.headers["X-Correlation-ID"] = cid
        REQUESTS.labels(request.method, str(response.status_code)).inc()
        LATENCY.labels(request.method).observe(time.perf_counter() - start)
        return response

    install_error_handlers(app)
    app.include_router(health.router)
    app.include_router(health.router, prefix="/api/v1")
    return app
