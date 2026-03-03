"""event img varchar to json

Revision ID: e3a1f2b4c5d6
Revises: fce8d304ff90
Create Date: 2026-03-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e3a1f2b4c5d6'
down_revision: Union[str, Sequence[str], None] = 'fce8d304ff90'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Convert existing VARCHAR values to a JSON array, then change column type to JSONB.
    # Rows that already have a non-null string value are wrapped into a one-element JSON array.
    op.execute("""
        ALTER TABLE event
        ADD COLUMN img JSONB
    """)


def downgrade() -> None:
    # Convert JSONB array back to a single VARCHAR (takes the first element).
    op.execute("""
        ALTER TABLE event
        DROP COLUMN img
    """)
