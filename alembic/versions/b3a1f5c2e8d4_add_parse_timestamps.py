"""add parse timestamps to documents

Revision ID: b3a1f5c2e8d4
Revises: 7f9bd3a72082
Create Date: 2026-06-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3a1f5c2e8d4'
down_revision: Union[str, Sequence[str], None] = '7f9bd3a72082'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('documents', sa.Column('parse_started_at', sa.DateTime(), nullable=True))
    op.add_column('documents', sa.Column('parse_completed_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('documents', 'parse_completed_at')
    op.drop_column('documents', 'parse_started_at')
