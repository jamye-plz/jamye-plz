"""Groups router — group CRUD and membership management."""

from fastapi import APIRouter

from app.core.deps import CurrentUser, DbSession
from app.schemas.group import GroupCreate, GroupMemberOut, GroupOut, GroupUpdate, MemberRoleUpdate
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


@router.get("/{group_id}/members", response_model=list[GroupMemberOut])
async def list_group_members(group_id: str, current_user: CurrentUser, db: DbSession):
    svc = GroupService(db)
    await svc.require_membership(group_id, current_user.id)
    return await svc.list_members_out(group_id)


@router.patch("/{group_id}", response_model=GroupOut)
async def update_group(group_id: str, body: GroupUpdate, current_user: CurrentUser, db: DbSession):
    svc = GroupService(db)
    group = await svc.update_group_name(group_id, current_user.id, body.name)
    return await _to_group_out(svc, group)


@router.delete("/{group_id}", status_code=204)
async def delete_group(group_id: str, current_user: CurrentUser, db: DbSession) -> None:
    svc = GroupService(db)
    await svc.soft_delete_group(group_id, current_user.id)


@router.delete("/{group_id}/members/{user_id}", status_code=204)
async def remove_group_member(
    group_id: str, user_id: str, current_user: CurrentUser, db: DbSession
) -> None:
    svc = GroupService(db)
    if user_id == current_user.id:
        await svc.leave_group(group_id, current_user.id)
    else:
        await svc.remove_member(group_id, current_user.id, user_id)


@router.patch("/{group_id}/members/{user_id}", status_code=204)
async def update_group_member_role(
    group_id: str,
    user_id: str,
    body: MemberRoleUpdate,
    current_user: CurrentUser,
    db: DbSession,
) -> None:
    svc = GroupService(db)
    await svc.set_member_role(group_id, current_user.id, user_id, body.role)
