"""One-off: rebuild Document.content for documents ingested before content was stored."""

from rag.db import get_db
from rag.db_models import Document


def main() -> None:
    db = next(get_db())
    try:
        docs = db.query(Document).filter(Document.content.is_(None)).all()
        for doc in docs:
            ordered = sorted(doc.chunks, key=lambda c: int(c.metadata_col.get("index", 0)))
            text = " ".join(c.content for c in ordered)
            db.query(Document).filter(Document.id == doc.id).update(
                {"content": text, "updated_at": doc.updated_at}, synchronize_session=False
            )
        db.commit()
        print(f"Backfilled content for {len(docs)} document(s).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
