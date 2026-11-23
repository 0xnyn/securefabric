"""Application factory.

Run with ``uvicorn --factory securefabric_api.main:create_app`` (or ``make run-api``).
"""

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
from securefabric_core import configure_logging, get_logger
from securefabric_db import DatabaseSettings, create_pool
from securefabric_tasks import AbsurdSettings

log = get_logger(__name__)


def create_app(
    settings: ApiSettings | None = None,
    db_settings: DatabaseSettings | None = None,
    absurd_settings: AbsurdSettings | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    db_settings = db_settings or DatabaseSettings()
    absurd_settings = absurd_settings or AbsurdSettings()

    configure_logging(settings.log_level, settings.log_format)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        pool = create_pool(db_settings)
        # wait=False: boot even if Postgres is still starting; /health/ready reports it.
        await pool.open(wait=False)
        app.state.pool = pool
        log.info("startup", environment=settings.environment, version=__version__)
        try:
            yield
        finally:
            await pool.close()
            log.info("shutdown")

    app = FastAPI(
        title="SecureFabric API",
        version=__version__,
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
    app.state.absurd_settings = absurd_settings
    app.dependency_overrides[get_settings] = lambda: settings

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["x-request-id"],
        )
    app.add_middleware(RequestContextMiddleware)

    register_exception_handlers(app)
    app.include_router(root_router)
    return app
