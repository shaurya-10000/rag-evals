import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from rag.config.settings import settings
from rag.db_models import Base, Document
from rag.repository import DocumentRepository
from rag.retrieve.embedder import Embedder


@pytest.fixture(scope="module")
def db_session():
    # Connect to real DB
    engine = create_engine(settings.DATABASE_URL)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_ingest_document_is_idempotent(db_session):
    # Use mock embedder to avoid OpenAI API calls during CI
    embedder = Embedder(mock=True) 
    repo = DocumentRepository(db=db_session, embedder=embedder)

    text = "This is a test document content."
    
    # Insert first time
    doc1 = repo.ingest_document("Test Doc", text)
    assert doc1.id is not None

    # Insert second time with same text
    doc2 = repo.ingest_document("Test Doc (Duplicate)", text)
    
    # Ensure it returned the same document (idempotency)
    assert doc1.id == doc2.id
    assert db_session.query(Document).filter_by(content_hash=doc1.content_hash).count() == 1
