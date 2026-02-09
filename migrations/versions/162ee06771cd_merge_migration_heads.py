"""merge migration heads

Revision ID: 162ee06771cd
Revises: 7433104653ef, 8fc514c2166f, b9d3560ed768
Create Date: 2026-02-08 15:53:27.823087

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '162ee06771cd'
down_revision: Union[str, Sequence[str], None] = ('7433104653ef', '8fc514c2166f', 'b9d3560ed768')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
