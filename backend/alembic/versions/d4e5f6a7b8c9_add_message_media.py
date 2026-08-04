"""add message_media

Chat message attachments (photos + mp4 video, M3). Mirrors topic_media but is
scoped to a message instead of a topic.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-08-04

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "message_media",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("message_id", sa.String(length=36), nullable=False),
        # content_type, e.g. "image/jpeg" / "video/mp4". Named `type` to mirror
        # topic_media, but widened to 64 so a longer MIME can never truncate.
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("object_key", sa.String(length=512), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("byte_size", sa.Integer(), nullable=True),
        # Seconds. Video only; null for images.
        sa.Column("duration", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    # History loads a page of messages then batch-fetches their media by
    # message_id — without this index that fan-in is a sequential scan.
    op.create_index("ix_message_media_message_id", "message_media", ["message_id"])


def downgrade() -> None:
    op.drop_index("ix_message_media_message_id", table_name="message_media")
    op.drop_table("message_media")
