"""``python -m securefabric_api`` / ``securefabric-api`` entrypoint."""

import uvicorn

from securefabric_api.config import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "securefabric_api.main:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
        workers=None if settings.reload else settings.workers,
        reload=settings.reload,
        reload_dirs=["apps", "packages"] if settings.reload else None,
        proxy_headers=True,
        forwarded_allow_ips="*",
        log_config=None,  # logging is configured by the app (structlog)
        server_header=False,
    )


if __name__ == "__main__":
    main()
