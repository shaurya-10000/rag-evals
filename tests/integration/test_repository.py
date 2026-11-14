import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from rag.auth.utils import get_password_hash
from rag.config.settings import settings
from rag.db_models import Base, Document, User
from rag.repository import DocumentRepository
from rag.retrieve.embedder import Embedder


@pytest.fixture(scope="module")
def db_session():
    engine = create_engine(settings.DATABASE_URL)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_ingest_document_is_idempotent(db_session):
    embedder = Embedder(mock=True)
    repo = DocumentRepository(db=db_session, embedder=embedder)

    # Create a real user first
    uniq = uuid.uuid4().hex[:8]
    user = User(
        email=f"repo_{uniq}@example.com",
        username=f"repouser_{uniq}",
        hashed_password=get_password_hash("testpassword123"),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    text = "This is a test document content."

    doc1 = repo.ingest_document(user.id, "Test Doc", text)
    assert doc1.id is not None

    doc2 = repo.ingest_document(user.id, "Test Doc (Duplicate)", text)
    assert doc1.id == doc2.id
    assert (
        db_session.query(Document)
        .filter_by(content_hash=doc1.content_hash)
        .count()
        == 1
    )
