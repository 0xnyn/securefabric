"""SANDBOX passes the conformance suite (M2 exit criterion)."""

from typing import Any

import httpx2
import pytest

from securefabric_cdk.inprocess import InProcessTransport, VendorRequest, VendorResponse
from securefabric_connectors.sandbox.vendor import SandboxVendor, reset_registry, vendor_for
from securefabric_domain import conformance as c

pytestmark = pytest.mark.integration

API_KEY = "sbx_conformance_key"
OPTIONS: dict[str, Any] = {
    "seed": 7,
    "host_count": 23,
    "image_count": 26,
    "finding_count": 64,
    "page_size": 10,
}
ROUTES = {"hosts": "/v1/hosts", "images": "/v1/images", "findings": "/v1/findings"}


class SandboxTarget(c.Target):
    pass


def make_target() -> c.Target:
    state = {"scenario": "none"}

    def transport() -> httpx2.AsyncBaseTransport:
        return InProcessTransport(SandboxVendor({**OPTIONS, "scenario": state["scenario"]}))

    def vendor() -> Any:
        return vendor_for(API_KEY, OPTIONS)

    async def remove_one(stream: str) -> str:
        v = vendor()
        if stream == "hosts":
            hid = sorted(v.hosts)[3]
            v.delete_host(hid)
            return f"host:{hid}"
        if stream == "images":
            iid = sorted(v.images)[2]
            kind = v.images.pop(iid)["kind"]
            return f"{kind}:{iid}"
        fid = sorted(v.findings)[5]
        v.purge_finding(fid)
        return f"finding:{fid}"

    async def empty_listing(stream: str) -> None:
        state["scenario"] = "empty_listing"

    async def restore() -> None:
        state["scenario"] = "none"
        reset_registry()

    def inject(stream: str, status: int) -> httpx2.AsyncBaseTransport:
        inner = SandboxVendor(OPTIONS)

        def handler(req: VendorRequest) -> VendorResponse:
            if req.path.endswith(ROUTES[stream]):
                headers = {"retry-after": "1200"} if status == 429 else {}
                return VendorResponse(status, {"error": f"injected {status}"}, headers)
            return inner(req)

        return InProcessTransport(handler)

    def samples(stream: str) -> list[dict[str, Any]]:
        v = vendor()
        return list({"hosts": v.hosts, "images": v.images, "findings": v.findings}[stream].values())

    return c.Target(
        connector_id="SANDBOX",
        credentials={"api_key": API_KEY},
        options=OPTIONS,
        config={},
        streams=["hosts", "images", "findings"],
        transport=transport,
        remove_one=remove_one,
        empty_listing=empty_listing,
        restore=restore,
        inject=inject,
        samples=samples,
        minimal={
            "findings": {"id": "f-min", "kind": "misc", "status": "open"},
            "hosts": {"id": "h-min", "status": "active"},
        },
        secrets=[API_KEY],
    )


async def test_1_idempotent(platform, tenant) -> None:
    await c.check_idempotent(platform, tenant, make_target())


@pytest.mark.parametrize("stream", ["hosts", "images", "findings"])
async def test_2_resumable(platform, tenant, stream) -> None:
    await c.check_resumable(platform, tenant, make_target(), stream)


async def test_3_stable_ids(platform, tenant) -> None:
    await c.check_stable_ids(platform, tenant, make_target())


@pytest.mark.parametrize("stream", ["hosts", "images", "findings"])
async def test_4_sweep_correct(platform, tenant, stream) -> None:
    await c.check_sweep(platform, tenant, make_target(), stream)


@pytest.mark.parametrize("stream", ["hosts", "findings"])
async def test_5_guarded(platform, tenant, stream) -> None:
    await c.check_guarded(platform, tenant, make_target(), stream)


def test_6_tristate_honest(platform) -> None:
    c.check_tristate(platform, make_target())


def test_7_never_fabricates(platform) -> None:
    c.check_never_fabricates(platform, make_target())


@pytest.mark.parametrize("stream", ["hosts", "findings"])
async def test_8_classified(platform, tenant, stream) -> None:
    await c.check_classified(platform, tenant, make_target(), stream)


async def test_9_linked(platform, tenant) -> None:
    await c.check_linked(platform, tenant, make_target())


async def test_10_bounded(platform, tenant) -> None:
    await c.check_bounded(platform, tenant, make_target(), "findings")


async def test_11_quiet(platform, tenant) -> None:
    await c.check_quiet(platform, tenant, make_target())
