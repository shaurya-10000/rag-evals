"""add full text search column to chunks

Revision ID: hybrid_search_01
Revises: 2b68242ecdae
Create Date: 2026-11-14

"""

from alembic import op

revision = "hybrid_search_01"
down_revision = "2b68242ecdae"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE chunks ADD COLUMN search_vector tsvector")
    op.execute("CREATE INDEX chunks_search_vector_idx ON chunks USING GIN(search_vector)")
    op.execute("""
        CREATE FUNCTION chunks_search_vector_update() RETURNS trigger AS $$ 
        BEGIN
            NEW.search_vector := to_tsvector('english', COALESCE(NEW.content, ''));
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER chunks_search_vector_trigger
        BEFORE INSERT OR UPDATE ON chunks
        FOR EACH ROW EXECUTE FUNCTION chunks_search_vector_update();
    """)
    op.execute("UPDATE chunks SET search_vector = to_tsvector('english', COALESCE(content, ''))")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS chunks_search_vector_trigger ON chunks")
    op.execute("DROP FUNCTION IF EXISTS chunks_search_vector_update()")
    op.execute("DROP INDEX IF EXISTS chunks_search_vector_idx")
    op.execute("ALTER TABLE chunks DROP COLUMN search_vector")
