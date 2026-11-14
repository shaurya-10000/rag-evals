import json
from typing import Any

from rag.eval.metrics import RetrievalMetrics
from rag.retrieve.retriever import Retriever


class EvalRunner:
    def __init__(self, retriever: Retriever):
        self.retriever = retriever

    def load_gold_set(self, filepath: str) -> list[dict[str, Any]]:
        with open(filepath, encoding="utf-8") as f:
            return json.load(f)  # type: ignore[no-any-return]

    def run(self, gold_set: list[dict[str, Any]], k: int = 3) -> dict[str, Any]:
        total_recall = 0.0
        total_mrr = 0.0
        num_questions = 0

        for item in gold_set:
            question = item["question"]
            expected_chunk = item.get("expected_answer_chunk", "")

            if expected_chunk == "NONE" or not expected_chunk:
                continue

            num_questions += 1
            relevant_texts = {expected_chunk}

            retrieved_chunks = self.retriever.search(query=question, user_id=None, top_k=k)
            retrieved_texts = [c.content for c in retrieved_chunks]

            total_recall += RetrievalMetrics.recall_at_k(retrieved_texts, relevant_texts, k)
            total_mrr += RetrievalMetrics.mean_reciprocal_rank(retrieved_texts, relevant_texts)

        return {
            "recall_at_k": total_recall / num_questions if num_questions else 0.0,
            "mrr": total_mrr / num_questions if num_questions else 0.0,
            "num_questions": num_questions,
        }
