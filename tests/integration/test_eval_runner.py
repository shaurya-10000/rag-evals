import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from rag.config.settings import settings
from rag.db_models import Base
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

    # Insert a known document
    repo.ingest_document("Eval Doc", "This is the exact text we want to retrieve.")
    
    # Dummy gold set matching the inserted data
    gold_set = [
        {
            "question": "What exact text?",
            "relevant_chunks": ["Chunk 1 text"] # Mock embedder returns this
        }
    ]

    results = runner.run(gold_set, k=1)
    assert "recall_at_k" in results
    assert "mrr" in results
    assert results["num_questions"] == 1
