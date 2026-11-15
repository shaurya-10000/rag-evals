"""add collections and document content/updated_at

Revision ID: collections_01
Revises: 5c4fe66afce5
Create Date: 2026-11-15

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "collections_01"
down_revision = "5c4fe66afce5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "collections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("user_id", "name", name="uq_collections_user_name"),
    )
    op.create_index("ix_collections_user_id", "collections", ["user_id"])

    op.add_column(
        "documents",
        sa.Column(
            "collection_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("collections.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_documents_collection_id", "documents", ["collection_id"])
    op.add_column("documents", sa.Column("content", sa.Text(), nullable=True))
    op.add_column(
        "documents",
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.execute("UPDATE documents SET updated_at = created_at")


def downgrade() -> None:
    op.drop_column("documents", "updated_at")
    op.drop_column("documents", "content")
    op.drop_index("ix_documents_collection_id", table_name="documents")
    op.drop_column("documents", "collection_id")
    op.drop_index("ix_collections_user_id", table_name="collections")
    op.drop_table("collections")
