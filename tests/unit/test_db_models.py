from rag.db_models import Chunk, Document


def test_document_model_instantiation():
    doc = Document(title="Test Doc", content_hash="abc123")
    assert doc.title == "Test Doc"
    assert doc.chunks == []

def test_chunk_model_instantiation():
    chunk = Chunk(content="This is a chunk.", document_id="123")
    assert chunk.content == "This is a chunk."
    assert chunk.embedding is None
