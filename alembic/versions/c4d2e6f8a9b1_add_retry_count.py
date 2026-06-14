"""add retry_count to documents

Revision ID: c4d2e6f8a9b1
Revises: b3a1f5c2e8d4
Create Date: 2026-06-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4d2e6f8a9b1'
down_revision: Union[str, Sequence[str], None] = 'b3a1f5c2e8d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('documents', sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('documents', 'retry_count')
