"""``securefabric-cdk``: the connector developer's tools (docs/plan/05-connector-sdk.md, section 4).

    securefabric-cdk validate [DIR...]          manifests against the schema + semantic checks (CDK-02)
    securefabric-cdk new VENDOR [--dir D]       scaffold a connector (CDK-08)
    securefabric-cdk capabilities DIR [--check] values_emitted + field coverage from golden output (CAT-03, CDK-09)
    securefabric-cdk scan-fixtures DIR...       fail on secrets or scrubbed fields in fixtures
    securefabric-cdk lint-imports DIR           connectors import only securefabric_cdk/schema (CDK-03)
    securefabric-cdk schema                     print the manifest JSON Schema

Dry runs and recording need a live connection and the vault, so they live in
``securefabric-admin dryrun`` / ``securefabric-admin record``.
"""

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import Any

from securefabric_cdk.manifest import Manifest, load_manifest, manifest_json_schema

ALLOWED_IMPORT_ROOTS = {"securefabric_cdk", "securefabric_schema", "securefabric_connectors"}
STDLIB = set(sys.stdlib_module_names)
TRISTATE = ("has_fix", "exploitable", "reachability")
COVERAGE_FIELDS = (
    "title",
    "description",
    "severity",
    "state_changed_at",
    "has_fix",
    "exploitable",
    "reachability",
    "remediation",
    "analytic",
    "product",
    "resource_related",
    "vulnerabilities",
    "cve_ids",
)


def connector_dirs(paths: list[str]) -> list[Path]:
    out: list[Path] = []
    for p in map(Path, paths):
        if (p / "manifest.yaml").exists():
            out.append(p)
        else:
            out.extend(sorted(d.parent for d in p.glob("*/manifest.yaml")))
    return out


def cmd_validate(paths: list[str]) -> int:
    failures = 0
    for d in connector_dirs(paths):
        try:
            m = load_manifest(d / "manifest.yaml")
            print(f"ok    {m.id}@{m.version} ({len(m.streams)} streams)")
        except Exception as exc:
            failures += 1
            print(f"FAIL  {d}: {exc}")
    return 1 if failures else 0


def imports_of(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.extend((node.lineno, a.name) for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            out.append((node.lineno, node.module))
    return out


def lint_imports(root: Path) -> list[str]:
    """CDK-03: connector source may import only the CDK, the schema, itself and the stdlib."""
    bad = []
    for py in sorted(root.rglob("*.py")):
        if "tests" in py.parts:
            continue
        for line, mod in imports_of(py):
            top = mod.split(".")[0]
            if top in ALLOWED_IMPORT_ROOTS or top in STDLIB:
                continue
            bad.append(
                f"{py}:{line}: imports {mod!r} (connectors may import only securefabric_cdk and securefabric_schema)"
            )
    return bad


def cmd_lint_imports(path: str) -> int:
    bad = lint_imports(Path(path))
    for b in bad:
        print(b)
    print("import boundary ok" if not bad else f"{len(bad)} violation(s)")
    return 1 if bad else 0


def capabilities(directory: Path) -> dict[str, Any]:
    """Compute what each finding stream actually emits from its golden output."""
    manifest = load_manifest(directory / "manifest.yaml")
    out: dict[str, Any] = {"connector": manifest.id, "version": manifest.version, "streams": {}}
    for spec in manifest.streams:
        golden = directory / "golden" / f"{spec.name}.json"
        if not golden.exists():
            continue
        records = [
            r for r in json.loads(golden.read_text()) if "natural_key" in r and "skip" not in r
        ]
        if records:
            out["streams"][spec.name] = stream_capabilities(spec.object, records)
    return out


def stream_capabilities(object_type: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    """Values emitted and field coverage of normalised records (JSON-mode dumps).
    Used on golden output in CI and on live records by ``securefabric-admin dryrun``."""
    stream: dict[str, Any] = {"records": len(records), "values_emitted": {}, "coverage": {}}
    if not records:
        return stream
    if object_type == "vulnerability_finding":
        for f in ("severity", "state", "type", *TRISTATE):
            stream["values_emitted"][f] = sorted(
                {str(r.get(f)) for r in records if r.get(f) is not None}
            )
        fields: tuple[str, ...] = tuple(COVERAGE_FIELDS)
    else:
        stream["values_emitted"]["type"] = sorted({r["type"] for r in records})
        stream["values_emitted"]["state"] = sorted({r["state"] for r in records})
        fields = ("name", "url", "groups", "tags", "data", "cloud_metadata")
    for f in fields:
        filled = sum(1 for r in records if r.get(f) not in (None, [], {}, ""))
        stream["coverage"][f] = round(filled / len(records), 3)
    return stream


def check_capabilities(manifest: Manifest, caps: dict[str, Any]) -> list[str]:
    """CAT-03: a supported field must be emitted by some fixture; an unsupported one never."""
    problems = []
    for spec in manifest.streams:
        s = caps["streams"].get(spec.name)
        if s is None or spec.object != "vulnerability_finding":
            continue
        for field, cap in spec.capabilities.items():
            emitted = s["values_emitted"].get(field)
            if emitted is None:
                continue
            if cap.supported and not emitted:
                problems.append(
                    f"{spec.name}.{field}: declared supported but no fixture emits a value"
                )
            if not cap.supported and emitted and field in TRISTATE:
                problems.append(
                    f"{spec.name}.{field}: declared unsupported but fixtures emit {emitted}"
                )
    return problems


def cmd_capabilities(path: str, check: bool) -> int:
    d = Path(path)
    caps = capabilities(d)
    target = d / "capabilities.json"
    rendered = json.dumps(caps, indent=2, sort_keys=True) + "\n"
    problems = check_capabilities(load_manifest(d / "manifest.yaml"), caps)
    for p in problems:
        print(p)
    if check:
        if not target.exists() or target.read_text() != rendered:
            print(f"{target} is stale; run securefabric-cdk capabilities {path}")
            return 1
    else:
        target.write_text(rendered)
        print(f"wrote {target}")
    return 1 if problems else 0


def cmd_scan_fixtures(paths: list[str], fields: list[str]) -> int:
    from securefabric_cdk.fixtures import find_secrets

    hits: list[str] = []
    for p in paths:
        for f in sorted(Path(p).rglob("*.json")):
            data = json.loads(f.read_text())
            hits.extend(f"{f}: {h}" for h in find_secrets(data, fields))
    for h in hits:
        print(h)
    print("fixtures clean" if not hits else f"{len(hits)} secret-like value(s) in fixtures")
    return 1 if hits else 0


SCAFFOLD_MANIFEST = """# {name}: generated by `securefabric-cdk new`. Fill in auth, streams and permissions.
id: {id}
version: 0.1.0
display_name: {name}
description: ""
categories: [vulnerability_management]
status: beta

auth:
  mode: API_KEY
  connect: form

credentials:
  type: object
  required: [api_key]
  properties:
    api_key: {{title: API key, type: string, x-secret: true}}

options:
  type: object
  properties: {{}}

regions:
  - {{id: default, api_base: "https://api.example.com"}}

http:
  retry:
    statuses: [429, "5xx"]
    retry_after_header: retry-after
  budget:
    key: "{{connection_id}}"
    per_hour: 3600
    max_concurrency: 2

permissions:
  - {{name: "Read findings", access: read, streams: [findings]}}

streams:
  - name: findings
    object: vulnerability_finding
    finding_types: [HOST]
    sync_mode: incremental
    interval: {{default: 3600, min: 900, max: 86400}}
    full_every: 604800
    deletion: vendor_reported
    natural_key: "finding:{{id}}"
    capabilities:
      severity: {{supported: true}}
      has_fix: {{supported: false}}
      exploitable: {{supported: false}}
      reachability: {{supported: false}}
"""

SCAFFOLD_CONNECTOR = '''"""The {id} connector. See docs/plan/05-connector-sdk.md."""

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from securefabric_cdk import (
    Checkpoint, Connector, Context, NormalizeContext, Page, RawItem, Stream, VerifyResult, load_manifest,
    offset_pages,
)
from securefabric_schema import FindingRecord, FindingState, FindingType, Mode, Severity

MANIFEST = load_manifest(Path(__file__).with_name("manifest.yaml"))


class FindingsStream(Stream):
    name = "findings"

    async def read(self, ctx: Context, checkpoint: Checkpoint, mode: Mode) -> AsyncIterator[Page]:
        offset = int((checkpoint or {{}}).get("offset") or 0)
        async for page in offset_pages(ctx.http, "/findings", offset=offset):
            yield Page(items=page.items, checkpoint={{"offset": page.resume}} if page.resume is not None else {{}})

    def normalize(self, raw: RawItem, nctx: NormalizeContext) -> FindingRecord:
        return FindingRecord(natural_key=f"finding:{{raw['id']}}", type=FindingType.HOST, title=raw.get("title"),
                             severity=Severity.UNKNOWN, state=FindingState.OPEN)


class {cls}Connector(Connector):
    manifest = MANIFEST
    stream_classes = (FindingsStream,)

    async def verify(self, ctx: Context) -> VerifyResult:
        me: Any = await ctx.http.get_json("/me")
        return VerifyResult(tenant_identity=str(me["id"]))
'''


def cmd_new(vendor: str, directory: str) -> int:
    vid = vendor.upper().replace("-", "_")
    pkg = Path(directory) / vid.lower()
    if pkg.exists():
        print(f"{pkg} already exists")
        return 1
    (pkg / "fixtures").mkdir(parents=True)
    (pkg / "golden").mkdir()
    name = vendor.replace("_", " ").title()
    (pkg / "__init__.py").write_text(f'"""{name} connector."""\n')
    (pkg / "manifest.yaml").write_text(SCAFFOLD_MANIFEST.format(id=vid, name=name))
    (pkg / "connector.py").write_text(
        SCAFFOLD_CONNECTOR.format(id=vid, cls="".join(p.title() for p in vid.split("_")))
    )
    (pkg / "mapping.py").write_text('"""Vendor → canonical mapping tables, as data."""\n')
    (pkg / "docs.md").write_text(f"# {name}\n\n## Permissions\n\n## Mapping\n\n## Notes\n")
    print(
        f"created {pkg}: fill in manifest.yaml, connector.py, record fixtures, commit golden output"
    )
    return cmd_validate([str(pkg)])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="securefabric-cdk")
    sub = parser.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate")
    v.add_argument("paths", nargs="*", default=["packages/connectors/src/securefabric_connectors"])
    n = sub.add_parser("new")
    n.add_argument("vendor")
    n.add_argument("--dir", default="packages/connectors/src/securefabric_connectors")
    c = sub.add_parser("capabilities")
    c.add_argument("path")
    c.add_argument("--check", action="store_true")
    s = sub.add_parser("scan-fixtures")
    s.add_argument("paths", nargs="+")
    s.add_argument("--field", action="append", default=["secret"])
    li = sub.add_parser("lint-imports")
    li.add_argument("path", nargs="?", default="packages/connectors/src/securefabric_connectors")
    sub.add_parser("schema")
    dg = sub.add_parser("docs", help="render docs/connectors/<id>.md from manifest + mapping")
    dg.add_argument("path")
    dg.add_argument("--out", default="docs/connectors")
    dg.add_argument("--check", action="store_true")
    a = parser.parse_args(argv)
    if a.cmd == "validate":
        return cmd_validate(a.paths)
    if a.cmd == "new":
        return cmd_new(a.vendor, a.dir)
    if a.cmd == "capabilities":
        return cmd_capabilities(a.path, a.check)
    if a.cmd == "scan-fixtures":
        return cmd_scan_fixtures(a.paths, a.field)
    if a.cmd == "lint-imports":
        return cmd_lint_imports(a.path)
    if a.cmd == "schema":
        json.dump(manifest_json_schema(), sys.stdout, indent=2)
        return 0
    if a.cmd == "docs":
        from securefabric_cdk.docs import write_docs

        target, current = write_docs(Path(a.path), Path(a.out), check=a.check)
        if a.check and not current:
            print(f"{target} is stale: run securefabric-cdk docs {a.path}")
            return 1
        print(f"{target} {'up to date' if a.check else 'written'}")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
