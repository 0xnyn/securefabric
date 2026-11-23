"""The workspace snapshot: everything the dash renders, in one read."""

from fastapi import APIRouter

from securefabric_api.dependencies import ConnDep
from securefabric_domain import ensure_seeded, load_workspace, seed
from securefabric_domain.models import Workspace

router = APIRouter(prefix="/workspace", tags=["workspace"])


async def _snapshot(conn: ConnDep) -> Workspace:
    workspace = await load_workspace(conn)
    assert workspace is not None  # noqa: S101 (seeded just before)
    return workspace


@router.get("", name="get_workspace", summary="The whole workspace (seeds a demo on first read)")
async def get_workspace(conn: ConnDep) -> Workspace:
    await ensure_seeded(conn)
    return await _snapshot(conn)


@router.post("/reset", name="reset_workspace", summary="Wipe and re-seed the demo workspace")
async def reset_workspace(conn: ConnDep) -> Workspace:
    await seed(conn, reset=True)
    return await _snapshot(conn)
