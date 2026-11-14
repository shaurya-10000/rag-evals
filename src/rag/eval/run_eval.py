import json
import sys

from sqlalchemy.orm import sessionmaker

from rag.db import engine
from rag.db_models import Chunk, Document
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

    db.query(Chunk).delete()
    db.query(Document).delete()
    db.commit()

    gold_set = runner.load_gold_set("eval/gold_set/qa_pairs.json")
    for item in gold_set:
        expected_chunk = item.get("expected_answer_chunk", "")
        if expected_chunk and expected_chunk != "NONE":
            repo.ingest_document("Eval Doc", expected_chunk)

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
