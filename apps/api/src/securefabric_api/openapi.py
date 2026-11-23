"""OpenAPI schema generation: the contract the TypeScript client is generated from.

    uv run securefabric-openapi > openapi.json

``@securefabric/client`` pipes this into openapi-typescript (``pnpm generate``), so
every path, parameter, body and response in the dash is typed from the same
pydantic models FastAPI validates with. CI regenerates it and fails on drift
(``pnpm check-generated``).
"""

import json
import os
import sys
from typing import Any

from fastapi.routing import APIRoute


def generate_unique_id(route: APIRoute) -> str:
    """Stable ``operationId``: ``<tag>:<function name>``, e.g. ``tenants:provision_tenant``.

    FastAPI's default mixes in the path and method (``provision_tenant_api_v1_tenants_post``),
    which churns the generated client whenever a route moves. This mirrors Polar's
    convention and keeps ``operations["tenants:provision_tenant"]`` readable on the TS side.
    """
    tags = [str(tag) for tag in route.tags]
    return ":".join([*tags[:1], route.name])


def build_schema() -> dict[str, Any]:
    # Pin anything that leaks into the schema so the output is identical on every
    # machine (and in CI), regardless of the developer's .env.
    os.environ["API_ENVIRONMENT"] = "test"
    os.environ["API_DOCS_ENABLED"] = "true"
    os.environ["API_ROOT_PATH"] = ""

    from securefabric_api.config import ApiSettings
    from securefabric_api.main import create_app

    return create_app(settings=ApiSettings(_env_file=None)).openapi()


def main() -> None:
    json.dump(build_schema(), sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
