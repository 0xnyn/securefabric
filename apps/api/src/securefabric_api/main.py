"""Application factory. ``uvicorn --factory securefabric_api.main:create_app``."""

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from securefabric_api import __version__
from securefabric_api.api.router import root_router
from securefabric_api.config import ApiSettings, get_settings
from securefabric_api.errors import register_exception_handlers
from securefabric_api.middleware import RequestContextMiddleware
from securefabric_api.openapi import generate_unique_id
from securefabric_api.ratelimit import RateLimiter
from securefabric_core import configure_logging, get_logger
from securefabric_core.telemetry import configure_telemetry
from securefabric_db import DatabaseSettings
from securefabric_domain.runtime import Platform, build_platform
from securefabric_domain.workos import WorkOSClient, build_workos

log = get_logger(__name__)


def create_app(
    settings: ApiSettings | None = None,
    db_settings: DatabaseSettings | None = None,
    platform: Platform | None = None,
    workos: WorkOSClient | None = None,
    rate_limit_per_minute: int | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, settings.log_format)
    configure_telemetry("securefabric-api", environment=settings.environment)  # OTLP if configured

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        p = platform or build_platform("api", db=db_settings or DatabaseSettings())
        await p.open()
        app.state.platform = p
        app.state.workos = workos if workos is not None else build_workos(p)
        limiter = RateLimiter(
            p.pool, per_minute=rate_limit_per_minute or settings.rate_limit_per_minute
        )
        app.state.rate_limiter = limiter
        limiter.start()
        try:
            from securefabric_domain.registry import sync_catalog

            await sync_catalog(p.pool, p.registry)
        except Exception as exc:  # the API must boot even if Postgres is still starting
            log.warning("catalog_sync_deferred", error=type(exc).__name__)
        log.info("startup", environment=settings.environment, version=__version__)
        try:
            yield
        finally:
            await limiter.stop()
            if platform is None:
                await p.close()
            log.info("shutdown")

    app = FastAPI(
        title="SecureFabric API",
        version=__version__,
        description="Unified security data API. Leen V2 wire-compatible; see docs/plan/07-public-api-and-events.md.",
        debug=settings.debug,
        lifespan=lifespan,
        root_path=settings.root_path,
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url="/redoc" if settings.docs_enabled else None,
        openapi_url="/openapi.json" if settings.docs_enabled else None,
        generate_unique_id_function=generate_unique_id,
    )
    app.state.settings = settings
    app.state.started_at = time.monotonic()
    app.dependency_overrides[get_settings] = lambda: settings
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=[
                "x-request-id",
                "x-ratelimit-limit",
                "x-ratelimit-remaining",
                "x-ratelimit-reset",
                "x-unsupported-filters",
                "idempotent-replayed",
            ],
        )
    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(app)
    app.include_router(root_router)
    return app
