from rag.repository import EMBED_BATCH_SIZE, DocumentRepository


class CountingEmbedder:
    def __init__(self) -> None:
        self.batch_sizes: list[int] = []

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        self.batch_sizes.append(len(texts))
        return [[0.0] for _ in texts]


def test_embeds_in_batches_and_reports_progress() -> None:
    embedder = CountingEmbedder()
    repo = DocumentRepository(db=None, embedder=embedder)  # type: ignore[arg-type]
    progress: list[tuple[int, int]] = []

    texts = [f"chunk {i}" for i in range(EMBED_BATCH_SIZE * 2 + 20)]
    vectors = repo._embed_in_batches(texts, lambda done, total: progress.append((done, total)))

    total = len(texts)
    assert len(vectors) == total
    assert embedder.batch_sizes == [EMBED_BATCH_SIZE, EMBED_BATCH_SIZE, 20]
    assert progress == [
        (0, total),
        (EMBED_BATCH_SIZE, total),
        (EMBED_BATCH_SIZE * 2, total),
        (total, total),
    ]
