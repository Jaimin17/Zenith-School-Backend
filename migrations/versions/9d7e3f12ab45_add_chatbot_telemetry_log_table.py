"""add chatbot telemetry log table

Revision ID: 9d7e3f12ab45
Revises: 5b06c4da4526
Create Date: 2026-04-10 11:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9d7e3f12ab45'
down_revision: Union[str, Sequence[str], None] = '5b06c4da4526'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'chatbot_telemetry_log',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('request_id', sa.String(), nullable=False),
        sa.Column('event', sa.String(), nullable=False),
        sa.Column('level', sa.String(), nullable=False),
        sa.Column('source', sa.String(), nullable=False),
        sa.Column('payload_json', sa.JSON(), nullable=False),
        sa.Column('hash_key', sa.String(), nullable=False),
        sa.Column('is_delete', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_index('ix_chatbot_telemetry_log_created_at', 'chatbot_telemetry_log', ['created_at'], unique=False)
    op.create_index('ix_chatbot_telemetry_log_request_id', 'chatbot_telemetry_log', ['request_id'], unique=False)
    op.create_index('ix_chatbot_telemetry_log_event', 'chatbot_telemetry_log', ['event'], unique=False)
    op.create_index('ix_chatbot_telemetry_log_hash_key', 'chatbot_telemetry_log', ['hash_key'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_chatbot_telemetry_log_hash_key', table_name='chatbot_telemetry_log')
    op.drop_index('ix_chatbot_telemetry_log_event', table_name='chatbot_telemetry_log')
    op.drop_index('ix_chatbot_telemetry_log_request_id', table_name='chatbot_telemetry_log')
    op.drop_index('ix_chatbot_telemetry_log_created_at', table_name='chatbot_telemetry_log')
    op.drop_table('chatbot_telemetry_log')
