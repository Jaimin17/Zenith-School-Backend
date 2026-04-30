"""teacher class history added

Revision ID: e7f8a9b0c1d2
Revises: 5b06c4da4526
Create Date: 2026-04-28 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = 'e7f8a9b0c1d2'
down_revision: Union[str, Sequence[str], None] = '5b06c4da4526'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    if 'teacher_class_history' not in existing_tables:
        op.create_table(
            'teacher_class_history',
            sa.Column('id', sa.Uuid(), nullable=False),
            sa.Column('teacher_id', sa.Uuid(), nullable=False),
            sa.Column('academic_year_id', sa.Uuid(), nullable=False),
            sa.Column('class_id', sa.Uuid(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['teacher_id'], ['teacher.id']),
            sa.ForeignKeyConstraint(['academic_year_id'], ['academic_year.id']),
            sa.ForeignKeyConstraint(['class_id'], ['class.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('teacher_id', 'academic_year_id', 'class_id', name='uq_teacher_class_year'),
        )


def downgrade() -> None:
    op.drop_table('teacher_class_history')
