"""Local generation-quality eval: faithfulness, answer relevance and refusal behaviour.

    python -m rag.eval.run_generation_eval --limit 10

Retrieval and generation use real Gemini calls, so pace it with --sleep on the free tier.
Results are saved after every question, so an interrupted run keeps its numbers, and a
question that hangs is abandoned after --question-timeout seconds instead of freezing the run.
"""

import argparse
import json
import threading
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar, cast

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

T = TypeVar("T")

GOLD_SET = "eval/gold_set/qa_pairs.json"
EVAL_EMAIL = "eval@rag-evals.local"
CANDIDATES = 10
TOP_K = 3


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 3) if values else None


def _rate(count: int, total: int) -> float | None:
    return round(count / total, 3) if total else None


def run_with_timeout(fn: Callable[[], T], seconds: float) -> T:
    """Run fn in a daemon thread; give up (but never block the process) after `seconds`."""
    box: dict[str, Any] = {}

    def target() -> None:
        try:
            box["value"] = fn()
        except Exception as e:
            box["error"] = e

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(seconds)
    if thread.is_alive():
        raise TimeoutError(f"no result after {seconds:.0f}s")
    if "error" in box:
        raise cast(Exception, box["error"])
    return cast(T, box["value"])


def build_summary(records: list[dict[str, Any]], min_score: float, planned: int) -> dict[str, Any]:
    answerable = [r for r in records if r["answerable"]]
    unanswerable = [r for r in records if not r["answerable"]]
    return {
        "questions_planned": planned,
        "questions_done": len(records),
        "errors": sum(1 for r in records if r.get("error")),
        "refusal_threshold": min_score,
        "faithfulness_mean": _mean(
            [r["faithfulness"] for r in records if r["faithfulness"] is not None]
        ),
        "answer_relevance_mean": _mean(
            [r["answer_relevance"] for r in records if r["answer_relevance"] is not None]
        ),
        "false_refusal_rate": _rate(sum(1 for r in answerable if r["refused"]), len(answerable)),
        "unanswerable_refusal_rate": _rate(
            sum(1 for r in unanswerable if r["refused"]), len(unanswerable)
        ),
    }


def write_results(
    path: Path, records: list[dict[str, Any]], min_score: float, planned: int
) -> dict[str, Any]:
    summary = build_summary(records, min_score, planned)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"summary": summary, "records": records}, indent=2), encoding="utf-8"
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Generation-quality evaluation")
    parser.add_argument("--limit", type=int, default=0, help="only run the first N questions")
    parser.add_argument("--sleep", type=float, default=6.0, help="seconds between questions")
    parser.add_argument("--output", default="eval/results/generation_latest.json")
    parser.add_argument(
        "--question-timeout",
        type=float,
        default=300.0,
        help="abandon a question that takes longer than this many seconds",
    )
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

    session_factory = sessionmaker(bind=engine)
    embedder = Embedder(mock=args.mock_embeddings)
    reranker = Reranker(mock=False)
    generator = Generator(mock=False)
    judge = LLMJudge()

    with session_factory() as db:
        eval_user = db.query(User).filter(User.email == EVAL_EMAIL).first()
        if not eval_user:
            eval_user = User(
                id=uuid.uuid4(),
                email=EVAL_EMAIL,
                username="eval_bot",
                hashed_password=get_password_hash(uuid.uuid4().hex),
            )
            db.add(eval_user)
            db.commit()
            db.refresh(eval_user)
        eval_user_id = eval_user.id

        db.query(Chunk).filter(
            Chunk.document_id.in_(db.query(Document.id).filter(Document.user_id == eval_user_id))
        ).delete(synchronize_session=False)
        db.query(Document).filter(Document.user_id == eval_user_id).delete(
            synchronize_session=False
        )
        db.commit()

        retriever = Retriever(db=db, embedder=embedder)
        gold = EvalRunner(retriever).load_gold_set(GOLD_SET)
        repo = DocumentRepository(db=db, embedder=embedder)
        for item in gold:
            chunk = item.get("expected_answer_chunk", "")
            if chunk and chunk != "NONE":
                repo.ingest_document(user_id=eval_user_id, title="Eval Doc", text=chunk)

    items = gold[: args.limit] if args.limit else gold
    min_score = refusal_min_score()
    out = Path(args.output)
    print(f"Running {len(items)} questions (refusal threshold {min_score})")

    def evaluate(item: dict[str, Any]) -> dict[str, Any]:
        question = item["question"]
        expected = item.get("expected_answer_chunk", "")
        answerable = bool(expected) and expected != "NONE"
        record: dict[str, Any] = {
            "question": question,
            "answerable": answerable,
            "best_score": None,
            "refused": False,
            "faithfulness": None,
            "answer_relevance": None,
        }
        # Own session per question: a question abandoned on timeout cannot corrupt the next one.
        with session_factory() as session:
            retriever_q = Retriever(db=session, embedder=embedder)
            candidates = retriever_q.search(query=question, user_id=eval_user_id, top_k=CANDIDATES)
            chunks, best_score = reranker.rerank_scored(question, candidates, top_k=TOP_K)
            refused = should_refuse(best_score, min_score)
            record["best_score"] = best_score
            record["refused"] = refused
            if not refused and not args.scores_only:
                answer = generator.generate_answer(question, chunks)
                if answer.startswith("Error:"):
                    record["error"] = answer
                else:
                    record["answer"] = answer
                    record["faithfulness"] = judge.faithfulness(answer, [c.content for c in chunks])
                    if answerable:
                        record["answer_relevance"] = judge.answer_relevance(question, answer)
        return record

    records: list[dict[str, Any]] = []
    for n, item in enumerate(items, start=1):
        try:
            record = run_with_timeout(lambda item=item: evaluate(item), args.question_timeout)  # type: ignore[misc]
        except Exception as e:
            expected = item.get("expected_answer_chunk", "")
            record = {
                "question": item["question"],
                "answerable": bool(expected) and expected != "NONE",
                "best_score": None,
                "refused": False,
                "faithfulness": None,
                "answer_relevance": None,
                "error": f"{type(e).__name__}: {e}"[:300],
            }
        records.append(record)
        write_results(out, records, min_score, len(items))
        print(
            f"[{n}/{len(items)}] answerable={record['answerable']} refused={record['refused']} "
            f"score={record['best_score']} faith={record['faithfulness']} "
            f"rel={record['answer_relevance']}"
            + (f" ERROR={record['error']}" if record.get("error") else "")
        )
        if n < len(items) and not args.scores_only:
            time.sleep(args.sleep)

    summary = write_results(out, records, min_score, len(items))
    print(json.dumps(summary, indent=2))
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
