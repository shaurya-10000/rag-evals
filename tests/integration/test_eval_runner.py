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

DOCS = {
    "Why do cats purr?": "Cats purr softly when they feel content.",
    "Where do rockets launch?": "Rockets launch from coastal pads at dawn.",
    "Why does bread need yeast?": "Bread dough rises because yeast produces gas.",
}


@pytest.fixture(scope="module")
def db_session():
    engine = create_engine(settings.DATABASE_URL)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _make_user(db_session) -> User:
    uniq = uuid.uuid4().hex[:8]
    user = User(
        email=f"eval_{uniq}@example.com",
        username=f"evaluser_{uniq}",
        hashed_password=get_password_hash("testpassword123"),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_eval_runner_scores_scoped_retrieval(db_session):
    embedder = Embedder(mock=True)
    repo = DocumentRepository(db=db_session, embedder=embedder)
    runner = EvalRunner(Retriever(db=db_session, embedder=embedder))
    user = _make_user(db_session)

    for text in DOCS.values():
        repo.ingest_document(user.id, "Eval Doc", text)

    gold_set = [
        {"type": "direct", "question": q, "expected_answer_chunk": text} for q, text in DOCS.items()
    ]
    gold_set.append(
        {"type": "unanswerable", "question": "Who won in 1998?", "expected_answer_chunk": "NONE"}
    )

    results = runner.run(gold_set, k=1, user_id=user.id)
    assert results["num_questions"] == 3  # unanswerable item is skipped
    assert results["recall_at_k"] == 1.0
    assert results["mrr"] == 1.0

    # Scoping: a user with no documents must retrieve nothing.
    empty = runner.run(gold_set, k=1, user_id=uuid.uuid4())
    assert empty["recall_at_k"] == 0.0
