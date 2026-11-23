"""Team members and their roles."""

from fastapi import APIRouter, Response, status

from securefabric_api.api.v1._util import no_content
from securefabric_api.dependencies import ConnDep
from securefabric_domain import service
from securefabric_domain.models import Created, MemberInvite, MemberPatch

router = APIRouter(prefix="/members", tags=["members"])


@router.post("", name="invite_member", status_code=status.HTTP_201_CREATED)
async def invite_member(body: MemberInvite, conn: ConnDep) -> Created:
    return Created(id=await service.invite_member(conn, body))


@router.patch("/{member_id}", name="set_member_role", status_code=status.HTTP_204_NO_CONTENT)
async def set_member_role(member_id: str, body: MemberPatch, conn: ConnDep) -> Response:
    await service.set_member_role(conn, member_id, body)
    return no_content()


@router.delete("/{member_id}", name="remove_member", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(member_id: str, conn: ConnDep) -> Response:
    await service.remove_member(conn, member_id)
    return no_content()
