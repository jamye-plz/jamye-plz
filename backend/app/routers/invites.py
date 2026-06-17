"""Invites router — invite code creation and redemption."""

from fastapi import APIRouter

from app.core.deps import CurrentUser, DbSession
from app.core.exceptions import AlreadyMemberError
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
    group_svc = GroupService(db)
    # Existing members enter regardless of the invite's expiry/exhaustion state,
    # so check membership BEFORE validate() (which would 410 a used/expired code).
    invite = await invite_svc.get_invite_or_404(code)
    group_id = invite.group_id
    if await group_svc.is_member(group_id, current_user.id):
        return {"group_id": group_id, "joined": False}
    # New member: validate() row-locks the invite + checks expiry/exhaustion,
    # then join + consume run under that lock, and the single commit is atomic.
    locked = await invite_svc.validate(code)
    try:
        membership = await group_svc.join_via_invite(group_id, current_user.id)
        await invite_svc.consume(locked)
        await db.commit()
        return {"group_id": group_id, "membership_id": membership.id, "joined": True}
    except AlreadyMemberError:
        # Concurrent double-redeem race: someone joined between our check and join.
        await db.rollback()
        return {"group_id": group_id, "joined": False}
