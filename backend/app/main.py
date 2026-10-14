import asyncio
import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram
from slowapi.errors import RateLimitExceeded

from app.api.v1 import agent_profiles, calls, health, internal
from app.core.config import get_settings
from app.core.correlation import correlation_id_var, new_correlation_id
from app.core.errors import install_error_handlers
from app.core.logging import configure_logging
from app.core.ratelimit import limiter

log = logging.getLogger("app")
REQUESTS = Counter("http_requests_total", "HTTP requests", ["method", "status"])
LATENCY = Histogram("http_request_seconds", "HTTP latency", ["method"])


async def _rate_limit_handler(_: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(status_code=429, content={"error": {"code": "rate_limited", "message": "Too many requests"}})


def create_app() -> FastAPI:
    settings = get_settings()  # fail fast on bad config
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        task = None
        if settings.env != "test" and settings.gemini_api_key:
            from app.api.v1.agent_profiles import get_generator
            from app.db.session import get_sessionmaker
            from app.workers.sweeper import run_forever

            task = asyncio.create_task(run_forever(get_sessionmaker(), get_generator(), settings.gemini_text_model))
        yield
        if task:
            task.cancel()

    app = FastAPI(title="Voice Agent Platform API", version="0.1.0", lifespan=lifespan)

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
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)  # type: ignore[arg-type]
    app.include_router(health.router)
    api_v1 = APIRouter(prefix="/api/v1")
    for r in (health.router, agent_profiles.router, calls.router):
        api_v1.include_router(r)
    app.include_router(api_v1)
    app.include_router(internal.router)  # /internal: never routed through public nginx
    return app
