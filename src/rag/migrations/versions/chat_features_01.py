"""add message metadata, feedback and shared chats

Revision ID: chat_features_01
Revises: ingest_jobs_01
Create Date: 2026-11-17

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "chat_features_01"
down_revision = "ingest_jobs_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("messages", sa.Column("rewritten_query", sa.Text(), nullable=True))
    op.add_column(
        "messages",
        sa.Column("refused", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("messages", sa.Column("feedback", sa.SmallInteger(), nullable=True))
    op.add_column("messages", sa.Column("feedback_comment", sa.Text(), nullable=True))
    op.create_check_constraint("ck_messages_feedback", "messages", "feedback IN (-1, 1)")

    op.create_table(
        "shared_chats",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token", sa.String(64), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("conversation_id", name="uq_shared_chats_conversation"),
    )
    op.create_index("ix_shared_chats_token", "shared_chats", ["token"], unique=True)
    op.create_index("ix_shared_chats_user_id", "shared_chats", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_shared_chats_user_id", table_name="shared_chats")
    op.drop_index("ix_shared_chats_token", table_name="shared_chats")
    op.drop_table("shared_chats")
    op.drop_constraint("ck_messages_feedback", "messages", type_="check")
    op.drop_column("messages", "feedback_comment")
    op.drop_column("messages", "feedback")
    op.drop_column("messages", "refused")
    op.drop_column("messages", "rewritten_query")
