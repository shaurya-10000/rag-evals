"""Local generation-quality eval: faithfulness, answer relevance and refusal behaviour.

    python -m rag.eval.run_generation_eval --limit 10

Retrieval uses the recorded embedding fixtures; generation and judging use real Gemini
calls, so pace it with --sleep on the free tier. Results go to eval/results/.
"""

import argparse
import json
import time
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy.orm import sessionmaker

from rag.auth.utils import get_password_hash
from rag.db import engine
from rag.db_models import Chunk, Document, User
from rag.eval.generation_metrics import LLMJudge
from rag.eval.runner import EvalRunner
from rag.generate.generator import Generator
from rag.generate.relevance import refusal_min_score, should_refuse
from rag.generate.reranker import Reranker
from rag.repository import DocumentRepository
from rag.retrieve.embedder import Embedder
from rag.retrieve.retriever import Retriever

GOLD_SET = "eval/gold_set/qa_pairs.json"
EVAL_EMAIL = "eval@rag-evals.local"
CANDIDATES = 10
TOP_K = 3


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 3) if values else None


def _rate(count: int, total: int) -> float | None:
    return round(count / total, 3) if total else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Generation-quality evaluation")
    parser.add_argument("--limit", type=int, default=0, help="only run the first N questions")
    parser.add_argument("--sleep", type=float, default=6.0, help="seconds between questions")
    parser.add_argument("--output", default="eval/results/generation_latest.json")
    parser.add_argument(
        "--scores-only",
        action="store_true",
        help="only retrieve and rerank (no generation or judging); use it to tune the threshold",
    )
    parser.add_argument(
        "--mock-embeddings",
        action="store_true",
        help="use recorded fixture embeddings instead of real Gemini embeddings",
    )
    args = parser.parse_args()

    db = sessionmaker(bind=engine)()
    embedder = Embedder(mock=args.mock_embeddings)
    repo = DocumentRepository(db=db, embedder=embedder)
    retriever = Retriever(db=db, embedder=embedder)
    reranker = Reranker(mock=False)
    generator = Generator(mock=False)
    judge = LLMJudge()

    eval_user = db.query(User).filter(User.email == EVAL_EMAIL).first()
    if not eval_user:
        eval_user = User(
            id=uuid.uuid4(),
            email=EVAL_EMAIL,
            username="eval_bot",
            hashed_password=get_password_hash("unused_password_123"),
        )
        db.add(eval_user)
        db.commit()
        db.refresh(eval_user)

    db.query(Chunk).filter(
        Chunk.document_id.in_(db.query(Document.id).filter(Document.user_id == eval_user.id))
    ).delete(synchronize_session=False)
    db.query(Document).filter(Document.user_id == eval_user.id).delete(synchronize_session=False)
    db.commit()

    gold = EvalRunner(retriever).load_gold_set(GOLD_SET)
    for item in gold:
        chunk = item.get("expected_answer_chunk", "")
        if chunk and chunk != "NONE":
            repo.ingest_document(user_id=eval_user.id, title="Eval Doc", text=chunk)

    items = gold[: args.limit] if args.limit else gold
    min_score = refusal_min_score()
    print(f"Running {len(items)} questions (refusal threshold {min_score})")

    records: list[dict[str, Any]] = []
    for n, item in enumerate(items, start=1):
        question = item["question"]
        expected = item.get("expected_answer_chunk", "")
        answerable = bool(expected) and expected != "NONE"

        candidates = retriever.search(query=question, user_id=eval_user.id, top_k=CANDIDATES)
        chunks, best_score = reranker.rerank_scored(question, candidates, top_k=TOP_K)
        refused = should_refuse(best_score, min_score)

        record: dict[str, Any] = {
            "question": question,
            "answerable": answerable,
            "best_score": best_score,
            "refused": refused,
            "faithfulness": None,
            "answer_relevance": None,
        }
        if not refused and not args.scores_only:
            answer = generator.generate_answer(question, chunks)
            if answer.startswith("Error:"):
                record["error"] = answer
            else:
                record["answer"] = answer
                record["faithfulness"] = judge.faithfulness(answer, [c.content for c in chunks])
                if answerable:
                    record["answer_relevance"] = judge.answer_relevance(question, answer)

        records.append(record)
        print(
            f"[{n}/{len(items)}] answerable={answerable} refused={refused} "
            f"score={best_score} faith={record['faithfulness']} "
            f"rel={record['answer_relevance']}"
        )
        if n < len(items):
            time.sleep(0 if args.scores_only else args.sleep)

    answerable_recs = [r for r in records if r["answerable"]]
    unanswerable_recs = [r for r in records if not r["answerable"]]
    summary = {
        "questions": len(records),
        "refusal_threshold": min_score,
        "faithfulness_mean": _mean(
            [r["faithfulness"] for r in records if r["faithfulness"] is not None]
        ),
        "answer_relevance_mean": _mean(
            [r["answer_relevance"] for r in records if r["answer_relevance"] is not None]
        ),
        "false_refusal_rate": _rate(
            sum(1 for r in answerable_recs if r["refused"]), len(answerable_recs)
        ),
        "unanswerable_refusal_rate": _rate(
            sum(1 for r in unanswerable_recs if r["refused"]), len(unanswerable_recs)
        ),
    }
    print(json.dumps(summary, indent=2))

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"summary": summary, "records": records}, indent=2), encoding="utf-8")
    print(f"Wrote {out}")
    db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
