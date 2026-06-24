"""add topic_id to messages

Revision ID: 0885dfeb8656
Revises: 0a5d7bbeb961
Create Date: 2026-06-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0885dfeb8656'
down_revision: Union[str, Sequence[str], None] = '0a5d7bbeb961'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('messages', sa.Column('topic_id', sa.String(length=36), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('messages', 'topic_id')
