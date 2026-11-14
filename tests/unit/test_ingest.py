from rag.ingest.pipeline import DocumentChunker, IngestionPipeline


def test_compute_hash_is_deterministic():
    text = "This is a test document."
    hash1 = IngestionPipeline.compute_hash(text)
    hash2 = IngestionPipeline.compute_hash(text)
    assert hash1 == hash2
    assert len(hash1) == 64  # SHA-256 length

def test_chunker_splits_correctly():
    chunker = DocumentChunker(chunk_size=100, overlap=10)
    text = "Short sentence one. Short sentence two."
    chunks = chunker.split(text)
    assert len(chunks) == 1
    assert chunks[0] == text
    
    # Test a long text that forces a split
    long_text = "A" * 60 + ". " + "B" * 60 + "."
    chunker_small = DocumentChunker(chunk_size=50, overlap=10)
    chunks = chunker_small.split(long_text)
    assert len(chunks) > 1
