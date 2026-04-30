"""merge heads

Revision ID: 86e66359aa76
Revises: c9a71ab2d001, e7f8a9b0c1d2
Create Date: 2026-04-29 15:40:46.064434

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '86e66359aa76'
down_revision: Union[str, Sequence[str], None] = ('c9a71ab2d001', 'e7f8a9b0c1d2')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
