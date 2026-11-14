"""add username and user_id isolation

Revision ID: 5c4fe66afce5
Revises: 4c9bd44c5edd
Create Date: 2026-11-14

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '5c4fe66afce5'
down_revision: str | Sequence[str] | None = '4c9bd44c5edd'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('users', sa.Column('username', sa.String(length=50), nullable=False))
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)
    op.add_column('documents', sa.Column('user_id', sa.UUID(), nullable=False))
    op.create_index(op.f('ix_documents_user_id'), 'documents', ['user_id'], unique=False)
    op.create_foreign_key(
        'fk_documents_user_id',
        'documents',
        'users',
        ['user_id'],
        ['id'],
        ondelete='CASCADE',
    )
    # Drop the old global unique constraint on content_hash
    op.drop_index('ix_documents_content_hash', table_name='documents')
    op.create_index(
        op.f('ix_documents_content_hash'), 'documents', ['content_hash'], unique=False
    )
    # Add composite unique constraint per-user
    op.create_unique_constraint(
        'uq_documents_user_content', 'documents', ['user_id', 'content_hash']
    )


def downgrade() -> None:
    op.drop_constraint('uq_documents_user_content', 'documents', type_='unique')
    op.drop_index(op.f('ix_documents_content_hash'), table_name='documents')
    op.create_index(
        'ix_documents_content_hash', 'documents', ['content_hash'], unique=True
    )
    op.drop_constraint('fk_documents_user_id', 'documents', type_='foreignkey')
    op.drop_index(op.f('ix_documents_user_id'), table_name='documents')
    op.drop_column('documents', 'user_id')
    op.drop_index(op.f('ix_users_username'), table_name='users')
    op.drop_column('users', 'username')
