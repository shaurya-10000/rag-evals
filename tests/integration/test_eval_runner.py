import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from rag.auth.utils import get_password_hash
from rag.config.settings import settings
from rag.db_models import Base, User
from rag.eval.runner import EvalRunner
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


def test_eval_runner_returns_metrics(db_session):
    embedder = Embedder(mock=True)
    repo = DocumentRepository(db=db_session, embedder=embedder)
    retriever = Retriever(db=db_session, embedder=embedder)
    runner = EvalRunner(retriever)

    uniq = uuid.uuid4().hex[:8]
    user = User(
        email=f"eval_{uniq}@example.com",
        username=f"evaluser_{uniq}",
        hashed_password=get_password_hash("testpassword123"),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    repo.ingest_document(
        user.id, "Eval Doc", "This is the exact text we want to retrieve."
    )

    gold_set = [
        {
            "type": "direct",
            "question": "What exact text?",
            "expected_answer_chunk": "This is the exact text we want to retrieve.",
        }
    ]

    results = runner.run(gold_set, k=1)
    assert "recall_at_k" in results
    assert "mrr" in results
    assert results["num_questions"] == 1
