"""Invites router — invite code creation and redemption."""

from fastapi import APIRouter

from app.core.deps import CurrentUser, DbSession
from app.schemas.invite import InviteCreate, InviteOut
from app.services.group_service import GroupService
from app.services.invite_service import InviteService

router = APIRouter(prefix="/groups/{group_id}/invites", tags=["invites"])


@router.post("", response_model=InviteOut, status_code=201)
async def create_invite(
    group_id: str,
    body: InviteCreate,
    current_user: CurrentUser,
    db: DbSession,
):
    group_svc = GroupService(db)
    await group_svc.require_owner(group_id, current_user.id)
    invite_svc = InviteService(db)
    return await invite_svc.create_invite(
        group_id=group_id,
        created_by=current_user.id,
        expires_at=body.expires_at,
        max_uses=body.max_uses,
    )


# Standalone invite redemption endpoint (not under a group prefix)
redeem_router = APIRouter(prefix="/invites", tags=["invites"])


@redeem_router.post("/{code}/join", response_model=dict)
async def redeem_invite(code: str, current_user: CurrentUser, db: DbSession):
    invite_svc = InviteService(db)
    invite = await invite_svc.validate(code)
    group_svc = GroupService(db)
    membership = await group_svc.join_via_invite(invite.group_id, current_user.id)
    await invite_svc.consume(invite)
    return {"group_id": invite.group_id, "membership_id": membership.id}
