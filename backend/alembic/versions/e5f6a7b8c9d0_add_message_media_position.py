"""add message_media.position

Attachments in one message are inserted in the same transaction, so PostgreSQL's
now() gives them identical created_at values. Ordering then fell through to the
random uuid primary key, which made the order in reloaded history differ from
the order the sender picked (and from the live WS payload). Persist the ordinal.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-08-04

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # server_default so the column can be NOT NULL without a separate backfill;
    # existing rows (none in production yet) collapse to a stable 0.
    op.add_column(
        "message_media",
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("message_media", "position")
