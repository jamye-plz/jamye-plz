"""Groups router — group CRUD and membership management."""

from fastapi import APIRouter

from app.core.deps import CurrentUser, DbSession
from app.schemas.group import GroupCreate, GroupOut, MembershipOut
from app.services.group_service import GroupService

router = APIRouter(prefix="/groups", tags=["groups"])


async def _to_group_out(svc: GroupService, group) -> GroupOut:
    """Serialize a Group with its derived main chatroom id."""
    out = GroupOut.model_validate(group)
    out.main_chatroom_id = await svc.get_main_chatroom_id(group.id)
    out.member_count = await svc.get_member_count(group.id)
    return out


@router.post("", response_model=GroupOut, status_code=201)
async def create_group(body: GroupCreate, current_user: CurrentUser, db: DbSession):
    svc = GroupService(db)
    group = await svc.create_group(name=body.name, owner_id=current_user.id)
    return await _to_group_out(svc, group)


@router.get("", response_model=list[GroupOut])
async def list_my_groups(current_user: CurrentUser, db: DbSession):
    svc = GroupService(db)
    groups = await svc.list_user_groups(current_user.id)
    return [await _to_group_out(svc, g) for g in groups]


@router.get("/{group_id}", response_model=GroupOut)
async def get_group(group_id: str, current_user: CurrentUser, db: DbSession):
    svc = GroupService(db)
    group = await svc.get_group_or_404(group_id)
    await svc.require_membership(group_id, current_user.id)
    return await _to_group_out(svc, group)


@router.get("/{group_id}/members", response_model=list[MembershipOut])
async def list_group_members(group_id: str, current_user: CurrentUser, db: DbSession):
    svc = GroupService(db)
    await svc.require_membership(group_id, current_user.id)
    return await svc.list_members(group_id)
