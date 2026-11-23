"""``securefabric-admin``: operator commands.

securefabric-admin bootstrap     catalogue, platform GitHub Apps, App webhook URLs
securefabric-admin seed          a development account, API key and SANDBOX connection
securefabric-admin operator EMAIL  grant the operator flag (break-glass, audited)
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import httpx2

from securefabric_cdk.auth import github_app_jwt
from securefabric_core import configure_logging
from securefabric_db import fetch_one, system_tx, tenant_tx
from securefabric_domain.catalog import bootstrap_platform_apps
from securefabric_domain.registry import sync_catalog
from securefabric_domain.runtime import Platform, build_platform
from securefabric_domain.vault import open_vendor_app_secrets


async def set_github_hook_urls(platform: Platform) -> list[dict[str, Any]]:
    """Point each platform GitHub App's webhook at ``PUBLIC_API_URL/v1/ingress/github/<id>``."""
    out = []
    base = platform.settings.public_api_url.rstrip("/")
    async with system_tx(platform.sys_pool) as conn:
        apps = await conn.execute(
            "select * from control.vendor_app where environment_id is null and connector_id = 'GITHUB' "
            "and deleted_at is null"
        )
        from psycopg.rows import dict_row

        apps.row_factory = dict_row
        rows = await apps.fetchall()
        for app in rows:
            secrets = await open_vendor_app_secrets(platform, conn, app)
            jwt, _ = github_app_jwt(app["config"]["app_id"], secrets["private_key"])
            url = f"{base}/v1/ingress/github/{app['id']}"
            async with httpx2.AsyncClient(timeout=20) as c:
                r = await c.patch(
                    f"{app['config']['api_base_url']}/app/hook/config",
                    headers={
                        "Authorization": f"Bearer {jwt}",
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28",
                    },
                    json={"url": url, "content_type": "json", "insecure_ssl": "0"},
                )
            out.append({"app": app["config"]["slug"], "url": url, "status": r.status_code})
    return out


async def bootstrap(platform: Platform, *, hooks: bool) -> dict[str, Any]:
    loaded = await sync_catalog(platform.sys_pool, platform.registry)
    apps = await bootstrap_platform_apps(platform)
    result: dict[str, Any] = {
        "connectors": loaded,
        "vendor_apps": [{"id": str(a["id"]), "name": a["name"]} for a in apps],
    }
    if hooks and apps:
        result["hooks"] = await set_github_hook_urls(platform)
    return result


async def seed(platform: Platform, *, name: str) -> dict[str, Any]:
    """Idempotent: reuses the account, organization and connection; mints a new key each run."""
    from securefabric_domain import connections, tenancy

    async with platform.pool.connection() as conn:
        existing = await fetch_one(
            conn, "select id from control.account where slug = %s", (tenancy.slugify(name),)
        )
    if existing:
        account_id = existing["id"]
    else:
        account_id = (
            await tenancy.provision_account(
                platform, name=name, workos_organization_id=None, admin_user_id=None
            )
        )["id"]
    env = next(
        e for e in await tenancy.account_environments(platform, account_id) if e["slug"] == "dev"
    )
    principal = tenancy.system_principal(env["id"], account_id)
    _, key = await tenancy.create_api_key(platform, principal, name="development", scopes=None)
    async with tenant_tx(platform.pool, env["id"]) as conn:
        org = await fetch_one(
            conn,
            "select id from control.organization where identifier = 'demo-customer' and deleted_at is null",
        )
        conn_row = await fetch_one(
            conn,
            "select id from control.connection where identifier = 'sandbox' and deleted_at is null",
        )
    if org is None:
        org = await tenancy.create_organization(
            platform, principal, identifier="demo-customer", name="Demo Customer"
        )
    if conn_row is None:
        conn_row = await connections.create_connection(
            platform,
            principal,
            organization_id=org["id"],
            vendor="SANDBOX",
            credentials={"api_key": "sbx_demo_development"},
            identifier="sandbox",
            options={"finding_count": 250, "host_count": 40, "image_count": 15},
        )
    return {
        "account_id": str(account_id),
        "environment_id": str(env["id"]),
        "api_key": key,
        "organization_id": str(org["id"]),
        "connection_id": str(conn_row["id"]),
    }


async def grant_operator(platform: Platform, email: str) -> dict[str, Any]:
    from securefabric_domain.tenancy import SYSTEM, audit

    async with system_tx(platform.sys_pool) as conn:
        row = await fetch_one(
            conn,
            "update control.app_user set is_operator = true where email = %s returning id",
            (email,),
        )
        if row is None:
            raise SystemExit(f"no user {email}")
        await audit(
            conn,
            SYSTEM,
            "operator.granted",
            target_kind="user",
            target_id=row["id"],
            detail={"break_glass": True},
        )
    return {"user_id": str(row["id"])}


async def _main(args: argparse.Namespace) -> Any:
    platform = build_platform("maintenance")
    await platform.open()
    try:
        if args.cmd == "bootstrap":
            return await bootstrap(platform, hooks=not args.no_hooks)
        if args.cmd == "seed":
            return await seed(platform, name=args.name)
        if args.cmd == "operator":
            return await grant_operator(platform, args.email)
        if args.cmd in ("dryrun", "record"):
            from uuid import UUID

            from securefabric_domain import devtools
            from securefabric_schema import Mode

            common = {"pages": args.pages, "mode": Mode(args.mode)}
            if args.cmd == "dryrun":
                return await devtools.dryrun(
                    platform, UUID(args.connection), args.stream, sample=args.sample, **common
                )
            return await devtools.record(
                platform,
                UUID(args.connection),
                args.stream,
                out_dir=Path(args.out) if args.out else None,
                **common,
            )
    finally:
        await platform.close()
    return None


def main(argv: list[str] | None = None) -> int:
    configure_logging("WARNING")
    parser = argparse.ArgumentParser(prog="securefabric-admin")
    sub = parser.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("bootstrap")
    b.add_argument(
        "--no-hooks", action="store_true", help="do not repoint the GitHub App webhook URLs"
    )
    s = sub.add_parser("seed")
    s.add_argument("--name", default="SecureFabric Dev")
    o = sub.add_parser("operator")
    o.add_argument("email")
    for name, helptext in (
        ("dryrun", "read a few pages of a live connection's stream; persists nothing"),
        ("record", "record a live stream's responses (scrubbed) as connector fixtures"),
    ):
        d = sub.add_parser(name, help=helptext)
        d.add_argument("--connection", required=True)
        d.add_argument("--stream", required=True)
        d.add_argument("--pages", type=int, default=3)
        d.add_argument("--mode", default="full", choices=["full", "incremental", "backfill"])
        if name == "dryrun":
            d.add_argument("--sample", type=int, default=3, help="records to print")
        else:
            d.add_argument("--out", help="directory (default: the connector's fixtures/)")
    result = asyncio.run(_main(parser.parse_args(argv)))
    json.dump(result, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")
    return 0
