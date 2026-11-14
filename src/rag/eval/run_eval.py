import json
import sys
import uuid

from sqlalchemy.orm import sessionmaker

from rag.auth.utils import get_password_hash
from rag.db import engine
from rag.db_models import Chunk, Document, User
from rag.eval.runner import EvalRunner
from rag.repository import DocumentRepository
from rag.retrieve.embedder import Embedder
from rag.retrieve.retriever import Retriever


def main() -> None:
    print("Running evaluation harness...")

    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    embedder = Embedder(mock=False)
    repo = DocumentRepository(db=db, embedder=embedder)
    retriever = Retriever(db=db, embedder=embedder)
    runner = EvalRunner(retriever)

    # Create a dedicated eval user so the FK constraint is satisfied
    eval_user = (
        db.query(User).filter(User.email == "eval@rag-evals.local").first()
    )
    if not eval_user:
        eval_user = User(
            id=uuid.uuid4(),
            email="eval@rag-evals.local",
            username="eval_bot",
            hashed_password=get_password_hash("unused_password_123"),
        )
        db.add(eval_user)
        db.commit()
        db.refresh(eval_user)

    # Clean only this eval user's documents
    db.query(Chunk).filter(
        Chunk.document_id.in_(
            db.query(Document.id).filter(Document.user_id == eval_user.id)
        )
    ).delete(synchronize_session=False)
    db.query(Document).filter(Document.user_id == eval_user.id).delete(
        synchronize_session=False
    )
    db.commit()

    gold_set = runner.load_gold_set("eval/gold_set/qa_pairs.json")
    for item in gold_set:
        expected_chunk = item.get("expected_answer_chunk", "")
        if expected_chunk and expected_chunk != "NONE":
            repo.ingest_document(
                user_id=eval_user.id, title="Eval Doc", text=expected_chunk
            )

    results = runner.run(gold_set, k=3)
    print(f"Results: {json.dumps(results, indent=2)}")

    RECALL_THRESHOLD = 0.7
    if results["recall_at_k"] < RECALL_THRESHOLD:
        print(f"FAILED: Recall@K ({results['recall_at_k']}) < {RECALL_THRESHOLD}")
        sys.exit(1)

    print("PASSED: Metrics are within acceptable limits.")
    sys.exit(0)


if __name__ == "__main__":
    main()
