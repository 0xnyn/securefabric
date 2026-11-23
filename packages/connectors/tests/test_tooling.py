"""CI gates (part 9 section 4): manifests valid, import boundary, generated capabilities
current, fixtures clean, and the M8 claim: a scaffolded connector runs through the real
engine with no change outside its own directory."""

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

from securefabric_cdk import cli
from securefabric_cdk.golden import assert_golden, normalize_all
from securefabric_cdk.inprocess import InProcessTransport, VendorRequest, VendorResponse
from securefabric_cdk.manifest import load_manifest
from securefabric_cdk.types import NormalizeContext
from securefabric_connectors.sandbox.connector import SandboxConnector
from securefabric_connectors.sandbox.vendor import VendorState

ROOT = Path(__file__).parents[1] / "src/securefabric_connectors"


def test_manifests_validate() -> None:
    assert cli.cmd_validate([str(ROOT)]) == 0


def test_import_boundary() -> None:
    assert cli.lint_imports(ROOT) == []


def test_import_boundary_catches_violations(tmp_path: Path) -> None:
    (tmp_path / "bad.py").write_text(
        "import httpx2\nimport psycopg\nfrom securefabric_domain import x\nimport json\n"
    )
    bad = cli.lint_imports(tmp_path)
    assert len(bad) == 3 and all("bad.py" in b for b in bad)


def test_sandbox_golden() -> None:
    connector = SandboxConnector()
    st = VendorState.generate("t_golden", seed=11, hosts=6, images=4, findings=24)
    nctx = NormalizeContext(options={}, config={}, stream="")
    assert_golden(
        ROOT / "sandbox/golden/findings.json",
        normalize_all(connector.stream("findings"), list(st.findings.values()), nctx),
    )
    assert_golden(
        ROOT / "sandbox/golden/hosts.json",
        normalize_all(connector.stream("hosts"), list(st.hosts.values()), nctx),
    )
    assert_golden(
        ROOT / "sandbox/golden/images.json",
        normalize_all(connector.stream("images"), list(st.images.values()), nctx),
    )


@pytest.mark.parametrize("name", ["github", "sandbox"])
def test_generated_capabilities_are_current_and_honest(name: str) -> None:
    d = ROOT / name
    caps = cli.capabilities(d)
    assert cli.check_capabilities(load_manifest(d / "manifest.yaml"), caps) == []
    assert json.loads((d / "capabilities.json").read_text()) == caps, (
        f"run: securefabric-cdk capabilities {d}"
    )


def test_fixtures_and_golden_carry_no_secrets() -> None:
    assert cli.cmd_scan_fixtures([str(ROOT)], ["secret"]) == 0


class ToyVendor:
    def __call__(self, req: VendorRequest) -> VendorResponse:
        if req.headers.get("authorization") != "Bearer toy-key-123":
            return VendorResponse(401, {"error": "nope"})
        if req.path.endswith("/me"):
            return VendorResponse(200, {"id": "toy-tenant"})
        if req.path.endswith("/findings"):
            items = [{"id": i, "title": f"toy {i}"} for i in range(7)]
            off, lim = int(req.query.get("offset", 0)), int(req.query.get("limit", 100))
            return VendorResponse(200, {"items": items[off : off + lim], "total": len(items)})
        return VendorResponse(404, {})


@pytest.mark.integration
async def test_a_scaffolded_connector_runs_through_the_real_engine(
    database_url: str, tmp_path: Path
) -> None:
    """M8's central claim, mechanically: `securefabric-cdk new`, point it at an API, and the
    platform runs it (verify, sync, conformance) with zero changes outside its directory."""
    from securefabric_domain import conformance as c
    from securefabric_domain.registry import ConnectorRegistry, default_registry
    from securefabric_domain.testing import build_test_platform, make_tenant

    assert cli.cmd_new("toyvendor", str(tmp_path)) == 0
    spec = importlib.util.spec_from_file_location(
        "toyvendor_connector", tmp_path / "toyvendor/connector.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    toy = mod.ToyvendorConnector()
    platform = build_test_platform(
        database_url, registry=ConnectorRegistry([*default_registry().all(), toy])
    )
    await platform.open()
    try:
        tenant = await make_tenant(platform)
        target = c.Target(
            connector_id="TOYVENDOR",
            credentials={"api_key": "toy-key-123"},
            options={},
            config={},
            streams=["findings"],
            transport=lambda: InProcessTransport(ToyVendor()),
            remove_one=_noop,
            empty_listing=_noop_s,
            restore=_noop_r,
            inject=lambda s, st: InProcessTransport(lambda r: VendorResponse(st, {})),
            samples=lambda s: [],
            secrets=["toy-key-123"],
        )
        await c.check_idempotent(platform, tenant, target)
        await c.check_stable_ids(platform, tenant, target)
        await c.check_quiet(platform, tenant, target)
        await c.check_classified(platform, tenant, target, "findings")
    finally:
        await platform.close()


async def _noop(stream: str) -> str:
    return ""


async def _noop_s(stream: str) -> None:
    return None


async def _noop_r() -> None:
    return None


_: Any = None


@pytest.mark.parametrize("name", ["github", "sandbox"])
def test_generated_connector_docs_are_current(name: str) -> None:
    from securefabric_cdk.docs import write_docs

    docs = ROOT.parents[3] / "docs" / "connectors"
    target, current = write_docs(ROOT / name, docs, check=True)
    assert current, f"{target} is stale: run make docs-connectors"
