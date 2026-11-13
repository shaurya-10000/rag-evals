import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from rag.config.settings import settings
from rag.db_models import Base
from rag.repository import DocumentRepository
from rag.retrieve.embedder import Embedder
from rag.retrieve.retriever import Retriever


@pytest.fixture(scope="module")
def db_session():
    engine = create_engine(settings.DATABASE_URL)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_retriever_returns_similar_chunks(db_session):
    embedder = Embedder(mock=True)
    repo = DocumentRepository(db=db_session, embedder=embedder)
    retriever = Retriever(db=db_session, embedder=embedder)

    # Insert a document with known text
    repo.ingest_document("Test Retrieval Doc", "Unique text for retrieval.")

    # Since we use a mock embedder, all embeddings are identical.
    # The retriever should still successfully fetch them without SQL errors.
    results = retriever.search("Random query", top_k=2)
    
    assert len(results) > 0
    assert isinstance(results[0].content, str)
