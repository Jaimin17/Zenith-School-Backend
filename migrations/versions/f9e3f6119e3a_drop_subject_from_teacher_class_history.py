"""drop subject from teacher class history

Revision ID: f9e3f6119e3a
Revises: 86e66359aa76
Create Date: 2026-04-29 15:41:17.241495

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = 'f9e3f6119e3a'
down_revision: Union[str, Sequence[str], None] = '86e66359aa76'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    if 'teacher_class_history' not in existing_tables:
        return

    existing_columns = {col['name'] for col in inspector.get_columns('teacher_class_history')}
    if 'subject_id' not in existing_columns:
        return

    existing_uniques = {u['name'] for u in inspector.get_unique_constraints('teacher_class_history')}
    if 'uq_teacher_class_subject_year' in existing_uniques:
        op.drop_constraint(
            'uq_teacher_class_subject_year',
            'teacher_class_history',
            type_='unique'
        )

    existing_fks = {fk['name'] for fk in inspector.get_foreign_keys('teacher_class_history') if fk.get('name')}
    if 'fk_teacher_class_history_subject_id' in existing_fks:
        op.drop_constraint(
            'fk_teacher_class_history_subject_id',
            'teacher_class_history',
            type_='foreignkey'
        )

    op.drop_column('teacher_class_history', 'subject_id')

    existing_uniques = {u['name'] for u in inspector.get_unique_constraints('teacher_class_history')}
    if 'uq_teacher_class_year' not in existing_uniques:
        op.create_unique_constraint(
            'uq_teacher_class_year',
            'teacher_class_history',
            ['teacher_id', 'class_id', 'academic_year_id']
        )


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    if 'teacher_class_history' not in existing_tables:
        return

    existing_columns = {col['name'] for col in inspector.get_columns('teacher_class_history')}
    if 'subject_id' in existing_columns:
        return

    op.add_column(
        'teacher_class_history',
        sa.Column('subject_id', sa.Uuid(), nullable=True)
    )

    op.create_foreign_key(
        'fk_teacher_class_history_subject_id',
        'teacher_class_history',
        'subject',
        ['subject_id'],
        ['id']
    )

    existing_uniques = {u['name'] for u in inspector.get_unique_constraints('teacher_class_history')}
    if 'uq_teacher_class_year' in existing_uniques:
        op.drop_constraint(
            'uq_teacher_class_year',
            'teacher_class_history',
            type_='unique'
        )

    existing_uniques = {u['name'] for u in inspector.get_unique_constraints('teacher_class_history')}
    if 'uq_teacher_class_subject_year' not in existing_uniques:
        op.create_unique_constraint(
            'uq_teacher_class_subject_year',
            'teacher_class_history',
            ['teacher_id', 'class_id', 'subject_id', 'academic_year_id']
        )
