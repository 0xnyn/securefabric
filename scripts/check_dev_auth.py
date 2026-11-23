"""Preflight for `make dev`: are the dashboard and the API set up for the same sign-in?

The API reads the root ``.env``; the dashboard (Next.js) reads only
``apps/dash/.env.local``. Both must name the same WorkOS client, or sign-in
succeeds at WorkOS and every API call is then rejected. This checks the two
files agree before anything starts, and says how to fix what doesn't.

    uv run python scripts/check_dev_auth.py          # exit 1 on a hard problem
    uv run python scripts/check_dev_auth.py --quiet  # print only problems
"""

import argparse
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
ROOT_ENV = ROOT / ".env"
DASH_ENV = ROOT / "apps" / "dash" / ".env.local"
DASH_EXAMPLE = "apps/dash/.env.example"
MIN_COOKIE_PASSWORD = 32


def read_env(path: Path) -> dict[str, str]:
    """KEY=value lines; inline `# comments` and surrounding quotes dropped."""
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.split(" #", 1)[0].split("\t#", 1)[0].strip().strip("'\"")
        out[key.strip()] = value
    return out


def effective(files: dict[str, str], key: str) -> str:
    """What the process will see: an exported variable wins over the file."""
    return os.environ.get(key) or files.get(key, "")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check the dashboard and API agree on sign-in.")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    api = read_env(ROOT_ENV)
    dash = read_env(DASH_ENV)
    errors: list[str] = []
    warnings: list[str] = []

    if effective(dash, "SF_DEV_API_KEY") or effective(dash, "NEXT_PUBLIC_SF_DEV_API_KEY"):
        if not args.quiet:
            print("dash auth: dev API key mode (SF_DEV_API_KEY); WorkOS sign-in is skipped")
        return 0

    if not DASH_ENV.exists():
        errors.append(
            f"apps/dash/.env.local is missing. Copy {DASH_EXAMPLE} to it and fill in the "
            "WorkOS values (the same as the root .env), or set SF_DEV_API_KEY to skip sign-in."
        )

    dash_client = effective(dash, "WORKOS_CLIENT_ID")
    dash_key = effective(dash, "WORKOS_API_KEY")
    password = effective(dash, "WORKOS_COOKIE_PASSWORD")
    api_client = effective(api, "WORKOS_CLIENT_ID")
    api_key = effective(api, "WORKOS_API_KEY")

    dash_workos = bool(dash_client and dash_key and password)
    if DASH_ENV.exists() and not dash_workos:
        missing = [
            k
            for k, v in (
                ("WORKOS_CLIENT_ID", dash_client),
                ("WORKOS_API_KEY", dash_key),
                ("WORKOS_COOKIE_PASSWORD", password),
            )
            if not v
        ]
        errors.append(
            f"apps/dash/.env.local has no {', '.join(missing)}: the dashboard can't sign "
            "anyone in. Fill them in, or set SF_DEV_API_KEY to skip sign-in."
        )

    if dash_workos:
        if len(password) < MIN_COOKIE_PASSWORD:
            errors.append(
                f"WORKOS_COOKIE_PASSWORD in apps/dash/.env.local is {len(password)} characters; "
                f"it needs at least {MIN_COOKIE_PASSWORD} (openssl rand -base64 32)."
            )
        if not (api_client and api_key):
            errors.append(
                "The root .env has no WORKOS_CLIENT_ID / WORKOS_API_KEY, so the API refuses "
                "dashboard sessions (sessions_disabled). Copy them from apps/dash/.env.local."
            )
        elif dash_client != api_client:
            errors.append(
                "WORKOS_CLIENT_ID differs between the root .env (API) and apps/dash/.env.local "
                "(dashboard): you would sign in to one WorkOS client and the API would reject "
                "its tokens. Use the same value in both."
            )
        elif dash_key != api_key:
            warnings.append(
                "WORKOS_API_KEY differs between the root .env and apps/dash/.env.local. "
                "Both should be the key of the same WorkOS environment."
            )
        if effective(dash, "WORKOS_API_URL") != effective(api, "WORKOS_API_URL"):
            warnings.append(
                "WORKOS_API_URL is set for only one of the API and the dashboard; "
                "tokens from one WorkOS won't verify against the other."
            )
        redirect = effective(dash, "NEXT_PUBLIC_WORKOS_REDIRECT_URI")
        port = effective(api, "DASH_PORT") or "3000"
        if redirect:
            u = urlparse(redirect)
            if u.path != "/callback" or str(u.port or "") != port:
                warnings.append(
                    f"NEXT_PUBLIC_WORKOS_REDIRECT_URI is {redirect}; the dashboard runs on "
                    f"port {port} and handles /callback. It must also be listed under "
                    "Redirects in the WorkOS dashboard."
                )
            elif u.hostname not in ("localhost", None):
                warnings.append(
                    f"NEXT_PUBLIC_WORKOS_REDIRECT_URI uses {u.hostname}: open the dashboard on "
                    f"that same host, or the sign-in state cookie won't match."
                )
            if not args.quiet:
                print(f"dash auth: WorkOS sign-in, open the dashboard at {u.scheme}://{u.netloc}")

    for w in warnings:
        print(f"⚠ {w}", file=sys.stderr)
    for e in errors:
        print(f"✘ {e}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
