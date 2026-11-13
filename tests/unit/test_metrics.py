from rag.eval.metrics import RetrievalMetrics


def test_recall_at_k():
    retrieved = ["doc1", "doc2", "doc3", "doc4"]
    relevant = {"doc1", "doc3", "doc5"}
    
    # Top 2: retrieved doc1, doc2. Only doc1 is relevant. Hits = 1. Total relevant = 3.
    assert RetrievalMetrics.recall_at_k(retrieved, relevant, k=2) == 1/3
    
    # Top 4: hits=2, total=3
    assert RetrievalMetrics.recall_at_k(retrieved, relevant, k=4) == 2/3

def test_mrr():
    retrieved = ["doc2", "doc3", "doc1"]
    relevant = {"doc1", "doc3"}
    
    # First relevant is doc3 at index 1 (rank 2). MRR = 1/2.
    assert RetrievalMetrics.mean_reciprocal_rank(retrieved, relevant) == 0.5

def test_mrr_no_relevant_found():
    retrieved = ["doc2", "doc4"]
    relevant = {"doc1"}
    assert RetrievalMetrics.mean_reciprocal_rank(retrieved, relevant) == 0.0

