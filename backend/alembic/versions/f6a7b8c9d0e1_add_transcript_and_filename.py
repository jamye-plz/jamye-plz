"""add message_media transcript columns and filename

M4a voice messages: audio attachments get an async transcript
(pending -> done | failed; NULL for non-audio media and for deployments
without Redis, where transcription is silently skipped).

filename closes tech debt #8: the original client-side name of ANY
attachment, so downloads can restore "IMG_4821.jpg" instead of the
synthesised jamye-{id}.{ext}.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-08-05

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, Sequence[str], None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("message_media", sa.Column("transcript", sa.Text(), nullable=True))
    op.add_column(
        "message_media", sa.Column("transcript_status", sa.String(length=16), nullable=True)
    )
    op.add_column("message_media", sa.Column("filename", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("message_media", "filename")
    op.drop_column("message_media", "transcript_status")
    op.drop_column("message_media", "transcript")
