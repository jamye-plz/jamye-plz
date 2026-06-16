"""Centralized custom exception hierarchy for jamye-plz backend.

All domain errors derive from AppError. FastAPI exception handlers
registered in main.py translate these into appropriate HTTP responses.
Never raise raw HTTPException from service or repository layers.
"""

from typing import Any


class AppError(Exception):
    """Base application error."""

    status_code: int = 500
    code: str = "internal_error"

    def __init__(self, detail: str = "Internal server error", **extra: Any) -> None:
        self.detail = detail
        self.extra = extra
        super().__init__(detail)


# ── Auth ──────────────────────────────────────────────────────────────────────


class AuthenticationError(AppError):
    status_code = 401
    code = "unauthenticated"

    def __init__(self, detail: str = "Authentication required") -> None:
        super().__init__(detail)


class ForbiddenError(AppError):
    status_code = 403
    code = "forbidden"

    def __init__(self, detail: str = "Access denied") -> None:
        super().__init__(detail)


# ── Resource ──────────────────────────────────────────────────────────────────


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"

    def __init__(self, resource: str = "Resource", resource_id: Any = None) -> None:
        detail = f"{resource} not found"
        if resource_id is not None:
            detail = f"{resource} '{resource_id}' not found"
        super().__init__(detail)


class ConflictError(AppError):
    status_code = 409
    code = "conflict"

    def __init__(self, detail: str = "Resource conflict") -> None:
        super().__init__(detail)


# ── Validation ────────────────────────────────────────────────────────────────


class ValidationError(AppError):
    status_code = 422
    code = "validation_error"

    def __init__(self, detail: str = "Validation failed") -> None:
        super().__init__(detail)


# ── Business Logic ────────────────────────────────────────────────────────────


class InviteExpiredError(AppError):
    status_code = 410
    code = "invite_expired"

    def __init__(self) -> None:
        super().__init__("Invite code has expired")


class InviteExhaustedError(AppError):
    status_code = 410
    code = "invite_exhausted"

    def __init__(self) -> None:
        super().__init__("Invite code has reached its usage limit")


class GroupFullError(AppError):
    status_code = 409
    code = "group_full"

    def __init__(self) -> None:
        super().__init__("Group has reached its member limit")


class AlreadyMemberError(AppError):
    status_code = 409
    code = "already_member"

    def __init__(self) -> None:
        super().__init__("User is already a member of this group")


class MessageIdempotencyError(AppError):
    """Raised when a duplicate client_msg_id is detected (used internally)."""

    status_code = 200  # Not a real HTTP error; handled in WS layer
    code = "message_duplicate"

    def __init__(self) -> None:
        super().__init__("Duplicate client_msg_id: returning existing message")
