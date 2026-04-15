"""add chat session and message tables

Revision ID: c9a71ab2d001
Revises: 9d7e3f12ab45
Create Date: 2026-04-15 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9a71ab2d001'
down_revision: Union[str, Sequence[str], None] = '9d7e3f12ab45'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if 'chat_session' not in existing_tables:
        op.create_table(
            'chat_session',
            sa.Column('id', sa.Uuid(), nullable=False),
            sa.Column('owner_id', sa.Uuid(), nullable=False),
            sa.Column('owner_role', sa.String(), nullable=False),
            sa.Column('title', sa.String(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.Column('is_delete', sa.Boolean(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
        )

    session_indexes = {idx['name'] for idx in inspector.get_indexes('chat_session')}
    if 'ix_chat_session_owner_id' not in session_indexes:
        op.create_index('ix_chat_session_owner_id', 'chat_session', ['owner_id'], unique=False)
    if 'ix_chat_session_owner_role' not in session_indexes:
        op.create_index('ix_chat_session_owner_role', 'chat_session', ['owner_role'], unique=False)
    if 'ix_chat_session_created_at' not in session_indexes:
        op.create_index('ix_chat_session_created_at', 'chat_session', ['created_at'], unique=False)
    if 'ix_chat_session_updated_at' not in session_indexes:
        op.create_index('ix_chat_session_updated_at', 'chat_session', ['updated_at'], unique=False)

    if 'chat_message' not in existing_tables:
        op.create_table(
            'chat_message',
            sa.Column('id', sa.Uuid(), nullable=False),
            sa.Column('session_id', sa.Uuid(), nullable=False),
            sa.Column('role', sa.String(), nullable=False),
            sa.Column('content', sa.String(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['session_id'], ['chat_session.id']),
            sa.PrimaryKeyConstraint('id'),
        )

    message_indexes = {idx['name'] for idx in inspector.get_indexes('chat_message')}
    if 'ix_chat_message_session_id' not in message_indexes:
        op.create_index('ix_chat_message_session_id', 'chat_message', ['session_id'], unique=False)
    if 'ix_chat_message_created_at' not in message_indexes:
        op.create_index('ix_chat_message_created_at', 'chat_message', ['created_at'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if 'chat_message' in existing_tables:
        message_indexes = {idx['name'] for idx in inspector.get_indexes('chat_message')}
        if 'ix_chat_message_created_at' in message_indexes:
            op.drop_index('ix_chat_message_created_at', table_name='chat_message')
        if 'ix_chat_message_session_id' in message_indexes:
            op.drop_index('ix_chat_message_session_id', table_name='chat_message')
        op.drop_table('chat_message')

    if 'chat_session' in existing_tables:
        session_indexes = {idx['name'] for idx in inspector.get_indexes('chat_session')}
        if 'ix_chat_session_updated_at' in session_indexes:
            op.drop_index('ix_chat_session_updated_at', table_name='chat_session')
        if 'ix_chat_session_created_at' in session_indexes:
            op.drop_index('ix_chat_session_created_at', table_name='chat_session')
        if 'ix_chat_session_owner_role' in session_indexes:
            op.drop_index('ix_chat_session_owner_role', table_name='chat_session')
        if 'ix_chat_session_owner_id' in session_indexes:
            op.drop_index('ix_chat_session_owner_id', table_name='chat_session')
        op.drop_table('chat_session')
