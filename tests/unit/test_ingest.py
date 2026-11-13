from rag.ingest.pipeline import DocumentChunker, IngestionPipeline


def test_compute_hash_is_deterministic():
    text = "This is a test document."
    hash1 = IngestionPipeline.compute_hash(text)
    hash2 = IngestionPipeline.compute_hash(text)
    assert hash1 == hash2
    assert len(hash1) == 64  # SHA-256 length

def test_chunker_splits_correctly():
    chunker = DocumentChunker(chunk_size=10, overlap=2)
    text = "123456789012345"
    chunks = chunker.split(text)
    # 10 chars, then 10 chars starting from index 8
    assert len(chunks) == 2
    assert chunks[0] == "1234567890"
    assert chunks[1] == "9012345"
