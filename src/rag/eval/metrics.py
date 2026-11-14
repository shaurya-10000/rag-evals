class RetrievalMetrics:
    @staticmethod
    def recall_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float:
        """Calculate Recall@K: what fraction of relevant items were retrieved in the top K?"""
        if not relevant_ids:
            return 1.0

        top_k_retrieved = set(retrieved_ids[:k])
        hits = len(top_k_retrieved.intersection(relevant_ids))
        return hits / len(relevant_ids)

    @staticmethod
    def mean_reciprocal_rank(retrieved_ids: list[str], relevant_ids: set[str]) -> float:
        """Calculate MRR: 1 / rank of the first relevant item."""
        if not relevant_ids:
            return 1.0

        for i, doc_id in enumerate(retrieved_ids):
            if doc_id in relevant_ids:
                return 1.0 / (i + 1)
        return 0.0
