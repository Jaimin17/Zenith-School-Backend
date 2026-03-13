"""academic_year and student_class_history tables, student status column

Revision ID: a1b2c3d4e5f6
Revises: dc86806d688f
Create Date: 2026-03-10 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '0dcb51477945'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()
    existing_student_cols = [c['name'] for c in inspector.get_columns('student')]

    # ── 1. academic_year table ──────────────────────────────────────────────
    if 'academic_year' not in existing_tables:
        op.create_table(
            'academic_year',
            sa.Column('id', sa.Uuid(), nullable=False),
            sa.Column('year_label', sa.String(), nullable=False),
            sa.Column('start_date', sa.Date(), nullable=False),
            sa.Column('end_date', sa.Date(), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('is_delete', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('year_label'),
        )

    # ── 2. student_class_history table ──────────────────────────────────────
    if 'student_class_history' not in existing_tables:
        op.create_table(
            'student_class_history',
            sa.Column('id', sa.Uuid(), nullable=False),
            sa.Column('student_id', sa.Uuid(), nullable=False),
            sa.Column('academic_year_id', sa.Uuid(), nullable=False),
            sa.Column('class_id', sa.Uuid(), nullable=True),
            sa.Column('grade_id', sa.Uuid(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['academic_year_id'], ['academic_year.id']),
            sa.ForeignKeyConstraint(['class_id'], ['class.id']),
            sa.ForeignKeyConstraint(['grade_id'], ['grade.id']),
            sa.ForeignKeyConstraint(['student_id'], ['student.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('student_id', 'academic_year_id', name='uq_student_year'),
        )

    # ── 3. Add status column to student ─────────────────────────────────────
    if 'status' not in existing_student_cols:
        op.add_column(
            'student',
            sa.Column('status', sa.String(), nullable=True),
        )
        op.execute("UPDATE student SET status = 'active' WHERE status IS NULL")
        op.alter_column('student', 'status', nullable=False)


def downgrade() -> None:
    op.drop_column('student', 'status')
    op.drop_table('student_class_history')
    op.drop_table('academic_year')
