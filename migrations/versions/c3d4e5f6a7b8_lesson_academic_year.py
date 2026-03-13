"""lesson academic year

Revision ID: c3d4e5f6a7b8
Revises: ba9009090262
Create Date: 2025-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'ba9009090262'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add academic_year_id column to lesson table
    op.add_column(
        'lesson',
        sa.Column('academic_year_id', postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.create_foreign_key(
        'fk_lesson_academic_year',
        'lesson',
        'academic_year',
        ['academic_year_id'],
        ['id'],
        ondelete='SET NULL',
    )
    # Back-fill existing lessons to the currently active academic year
    op.execute(
        """
        UPDATE lesson
        SET academic_year_id = (
            SELECT id FROM academic_year
            WHERE is_active = TRUE AND is_delete = FALSE
            ORDER BY start_date DESC
            LIMIT 1
        )
        WHERE academic_year_id IS NULL
        """
    )


def downgrade() -> None:
    op.drop_constraint('fk_lesson_academic_year', 'lesson', type_='foreignkey')
    op.drop_column('lesson', 'academic_year_id')
