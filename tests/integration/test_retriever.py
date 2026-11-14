import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from rag.auth.utils import get_password_hash
from rag.config.settings import settings
from rag.db_models import Base, User
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

    uniq = uuid.uuid4().hex[:8]
    user = User(
        email=f"ret_{uniq}@example.com",
        username=f"retuser_{uniq}",
        hashed_password=get_password_hash("testpassword123"),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    repo.ingest_document(user.id, "Test Retrieval Doc", "Unique text for retrieval.")

    results = retriever.search("Random query", user_id=user.id, top_k=2)

    assert len(results) > 0
    assert isinstance(results[0].content, str)
