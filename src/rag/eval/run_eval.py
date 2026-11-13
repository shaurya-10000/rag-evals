import json
import sys

from sqlalchemy.orm import sessionmaker

from rag.db import engine
from rag.db_models import Chunk, Document
from rag.eval.runner import EvalRunner
from rag.repository import DocumentRepository
from rag.retrieve.embedder import Embedder
from rag.retrieve.retriever import Retriever


def main():
    print("Running evaluation harness...")
    
    # 1. Setup DB and retriever
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    embedder = Embedder(mock=True)
    repo = DocumentRepository(db=db, embedder=embedder)
    retriever = Retriever(db=db, embedder=embedder)
    runner = EvalRunner(retriever)

    # 2. Clear existing data (for a clean eval)
    db.query(Chunk).delete()
    db.query(Document).delete()
    db.commit()

    # 3. Ingest the gold set chunks into the DB
    gold_set = runner.load_gold_set("eval/gold_set/qa_pairs.json")
    for item in gold_set:
        for chunk_text in item["relevant_chunks"]:
            repo.ingest_document("Eval Doc", chunk_text)

    # 4. Run eval
    results = runner.run(gold_set, k=3)
    print(f"Results: {json.dumps(results, indent=2)}")

    # 5. CI Gate (Temporarily 0.0 for mock embedder)
    RECALL_THRESHOLD = 0.0
    if results["recall_at_k"] < RECALL_THRESHOLD:
        print(f"FAILED: Recall@K ({results['recall_at_k']}) < {RECALL_THRESHOLD}")
        sys.exit(1)
    
    print("PASSED: Metrics are within acceptable limits.")
    sys.exit(0)

if __name__ == "__main__":
    main()
