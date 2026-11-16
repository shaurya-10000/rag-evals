"""Decide whether retrieval found anything relevant enough to answer from."""

import os

# Cross-encoder (ms-marco MiniLM) scores are logits: clearly irrelevant passages
# land well below zero. Tune with REFUSAL_MIN_SCORE after checking the logged scores.
DEFAULT_REFUSAL_MIN_SCORE = -5.0


def refusal_min_score() -> float:
    raw = os.getenv("REFUSAL_MIN_SCORE")
    if raw is None:
        return DEFAULT_REFUSAL_MIN_SCORE
    try:
        return float(raw)
    except ValueError:
        return DEFAULT_REFUSAL_MIN_SCORE


def should_refuse(best_score: float | None, min_score: float | None = None) -> bool:
    """True when the best reranker score is below the threshold.

    A missing score (reranker disabled or nothing retrieved) never triggers a refusal here;
    an empty retrieval is already handled by the generator.
    """
    if best_score is None:
        return False
    threshold = refusal_min_score() if min_score is None else min_score
    return best_score < threshold
