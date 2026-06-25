"""add chatroom_reads table and notification dedup_key

Revision ID: a1b2c3d4e5f6
Revises: 0a5d7bbeb961
Create Date: 2026-06-25 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "0a5d7bbeb961"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. New table: chatroom_reads
    op.create_table(
        "chatroom_reads",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("chatroom_id", sa.String(length=36), nullable=False),
        sa.Column(
            "last_read_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["chatroom_id"], ["chatrooms.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "chatroom_id", name="uq_chatroom_reads_user_chatroom"),
    )

    # 2. Add dedup_key column to notifications
    op.add_column(
        "notifications",
        sa.Column("dedup_key", sa.String(length=128), nullable=True),
    )

    # 3. Partial unique index on (user_id, dedup_key) WHERE dedup_key IS NOT NULL
    op.create_index(
        "ix_notifications_user_dedup",
        "notifications",
        ["user_id", "dedup_key"],
        unique=True,
        postgresql_where=sa.text("dedup_key IS NOT NULL"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_notifications_user_dedup",
        table_name="notifications",
        postgresql_where=sa.text("dedup_key IS NOT NULL"),
    )
    op.drop_column("notifications", "dedup_key")
    op.drop_table("chatroom_reads")
