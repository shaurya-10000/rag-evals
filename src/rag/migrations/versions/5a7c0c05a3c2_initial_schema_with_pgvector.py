"""initial schema with pgvector

Revision ID: 5a7c0c05a3c2
Revises: 
Create Date: 2026-11-13

"""
from collections.abc import Sequence

import pgvector
import sqlalchemy as sa
from alembic import op

revision: str = '5a7c0c05a3c2'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade() -> None:
    # Enable the pgvector extension
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    
    op.create_table('documents',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('source_url', sa.String(length=1024), nullable=True),
        sa.Column('content_hash', sa.String(length=64), nullable=False),
        sa.Column('metadata_col', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_documents_content_hash'), 'documents', ['content_hash'], unique=True)
    
    op.create_table('chunks',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('document_id', sa.UUID(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('embedding', pgvector.sqlalchemy.Vector(dim=1536), nullable=True),
        sa.Column('metadata_col', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_chunks_document_id'), 'chunks', ['document_id'], unique=False)

def downgrade() -> None:
    op.drop_index(op.f('ix_chunks_document_id'), table_name='chunks')
    op.drop_table('chunks')
    op.drop_index(op.f('ix_documents_content_hash'), table_name='documents')
    op.drop_table('documents')
