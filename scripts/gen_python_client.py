"""`make generate-python-client`: the Python client, generated from the OpenAPI document.

Operation ids are ``<tag>:<function>`` (stable for the TypeScript client); the Python
generator would mangle them into names like ``organizationslist_organizations``, so
they are shortened to the function name (unique across the API) first.
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    from securefabric_api.openapi import build_schema

    schema = build_schema()
    seen: set[str] = set()
    for item in schema["paths"].values():
        for op in item.values():
            if isinstance(op, dict) and "operationId" in op:
                short = op["operationId"].split(":", 1)[-1]
                if short in seen:
                    sys.exit(f"duplicate operation name {short!r}: keep route names unique")
                seen.add(short)
                op["operationId"] = short
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(schema, f)
    return subprocess.call(  # noqa: S603 - fixed toolchain call
        [  # noqa: S607
            "uvx", "--from", "openapi-python-client", "openapi-python-client", "generate",
            "--path", f.name, "--meta", "uv", "--overwrite",
            "--config", str(ROOT / "clients" / "python-client.yaml"),
            "--output-path", str(ROOT / "clients" / "python"),
        ],
        cwd=ROOT,
    )  # fmt: skip


if __name__ == "__main__":
    sys.exit(main())
