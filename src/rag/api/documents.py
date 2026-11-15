import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from rag.api.deps import get_embedder, limiter, verify_api_key
from rag.api.schemas import (
    CollectionCreate,
    CollectionOut,
    CollectionUpdate,
    DocumentDetail,
    DocumentSummary,
    DocumentUpdate,
    MoveRequest,
)
from rag.auth.utils import get_current_user
from rag.db import get_db
from rag.db_models import Collection, Document, User
from rag.repository import DocumentRepository, DuplicateCollectionError, DuplicateDocumentError
from rag.retrieve.embedder import Embedder

logger = logging.getLogger("rag.api.documents")
router = APIRouter()

PREVIEW_CHARS = 160
MIN_CONTENT_CHARS = 10


def _summary(doc: Document, chunk_count: int) -> DocumentSummary:
    return DocumentSummary(
        id=doc.id,
        title=doc.title,
        collection_id=doc.collection_id,
        source_url=doc.source_url,
        preview=(doc.content or "")[:PREVIEW_CHARS],
        chunk_count=chunk_count,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


def _detail(repo: DocumentRepository, doc: Document) -> DocumentDetail:
    content = repo.get_content(doc)
    count = repo.chunk_counts([doc.id]).get(doc.id, 0)
    return DocumentDetail(**_summary(doc, count).model_dump(), content=content)


def _collection_out(col: Collection, count: int) -> CollectionOut:
    return CollectionOut(id=col.id, name=col.name, document_count=count, created_at=col.created_at)


def _doc_not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="Document not found")


def _collection_not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="Collection not found")


# ------------------------------------------------------------------ documents
@router.get("/documents", response_model=list[DocumentSummary])
def list_documents(
    collection_id: uuid.UUID | None = None,
    unfiled: bool = False,
    q: str | None = None,
    db: Session = Depends(get_db),
    embedder: Embedder = Depends(get_embedder),
    _: str = Depends(verify_api_key),
    current_user: User = Depends(get_current_user),
) -> list[DocumentSummary]:
    repo = DocumentRepository(db=db, embedder=embedder)
    docs = repo.list_documents(
        current_user.id, collection_id=collection_id, unfiled=unfiled, search=q
    )
    counts = repo.chunk_counts([d.id for d in docs])
    return [_summary(d, counts.get(d.id, 0)) for d in docs]


@router.get("/documents/{doc_id}", response_model=DocumentDetail)
def get_document(
    doc_id: uuid.UUID,
    db: Session = Depends(get_db),
    embedder: Embedder = Depends(get_embedder),
    _: str = Depends(verify_api_key),
    current_user: User = Depends(get_current_user),
) -> DocumentDetail:
    repo = DocumentRepository(db=db, embedder=embedder)
    doc = repo.get_document(current_user.id, doc_id)
    if doc is None:
        raise _doc_not_found()
    return _detail(repo, doc)


@router.patch("/documents/{doc_id}", response_model=DocumentDetail)
@limiter.limit("10/minute")
def update_document(
    request: Request,
    doc_id: uuid.UUID,
    payload: DocumentUpdate,
    db: Session = Depends(get_db),
    embedder: Embedder = Depends(get_embedder),
    _: str = Depends(verify_api_key),
    current_user: User = Depends(get_current_user),
) -> DocumentDetail:
    if payload.title is None and payload.content is None:
        raise HTTPException(status_code=422, detail="Nothing to update")

    title = payload.title.strip() if payload.title is not None else None
    if title is not None and not title:
        raise HTTPException(status_code=422, detail="Title cannot be empty")
    if payload.content is not None and len(payload.content.strip()) < MIN_CONTENT_CHARS:
        raise HTTPException(status_code=422, detail="Text must be at least 10 characters long.")

    repo = DocumentRepository(db=db, embedder=embedder)
    if repo.get_document(current_user.id, doc_id) is None:
        raise _doc_not_found()

    # Content first: it is the risky step (re-embedding). If it fails, nothing was renamed.
    if payload.content is not None:
        try:
            repo.update_content(current_user.id, doc_id, payload.content)
        except DuplicateDocumentError:
            raise HTTPException(
                status_code=409, detail="Another document already has this exact content."
            ) from None
    if title is not None:
        repo.rename_document(current_user.id, doc_id, title)

    doc = repo.get_document(current_user.id, doc_id)
    if doc is None:
        raise _doc_not_found()
    return _detail(repo, doc)


@router.put("/documents/{doc_id}/collection", response_model=DocumentDetail)
def move_document(
    doc_id: uuid.UUID,
    payload: MoveRequest,
    db: Session = Depends(get_db),
    embedder: Embedder = Depends(get_embedder),
    _: str = Depends(verify_api_key),
    current_user: User = Depends(get_current_user),
) -> DocumentDetail:
    repo = DocumentRepository(db=db, embedder=embedder)
    if (
        payload.collection_id
        and repo.get_collection(current_user.id, payload.collection_id) is None
    ):
        raise _collection_not_found()
    doc = repo.move_document(current_user.id, doc_id, payload.collection_id)
    if doc is None:
        raise _doc_not_found()
    return _detail(repo, doc)


@router.delete("/documents/{doc_id}")
def delete_document(
    doc_id: uuid.UUID,
    db: Session = Depends(get_db),
    embedder: Embedder = Depends(get_embedder),
    _: str = Depends(verify_api_key),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    repo = DocumentRepository(db=db, embedder=embedder)
    if not repo.delete_document(current_user.id, doc_id):
        raise _doc_not_found()
    return {"status": "deleted"}


# ---------------------------------------------------------------- collections
@router.get("/collections", response_model=list[CollectionOut])
def list_collections(
    db: Session = Depends(get_db),
    embedder: Embedder = Depends(get_embedder),
    _: str = Depends(verify_api_key),
    current_user: User = Depends(get_current_user),
) -> list[CollectionOut]:
    repo = DocumentRepository(db=db, embedder=embedder)
    return [_collection_out(col, n) for col, n in repo.list_collections(current_user.id)]


@router.post("/collections", response_model=CollectionOut)
def create_collection(
    payload: CollectionCreate,
    db: Session = Depends(get_db),
    embedder: Embedder = Depends(get_embedder),
    _: str = Depends(verify_api_key),
    current_user: User = Depends(get_current_user),
) -> CollectionOut:
    if not payload.name.strip():
        raise HTTPException(status_code=422, detail="Name cannot be empty")
    repo = DocumentRepository(db=db, embedder=embedder)
    try:
        col = repo.create_collection(current_user.id, payload.name)
    except DuplicateCollectionError:
        raise HTTPException(status_code=409, detail="A collection with that name exists") from None
    return _collection_out(col, 0)


@router.patch("/collections/{collection_id}", response_model=CollectionOut)
def rename_collection(
    collection_id: uuid.UUID,
    payload: CollectionUpdate,
    db: Session = Depends(get_db),
    embedder: Embedder = Depends(get_embedder),
    _: str = Depends(verify_api_key),
    current_user: User = Depends(get_current_user),
) -> CollectionOut:
    if not payload.name.strip():
        raise HTTPException(status_code=422, detail="Name cannot be empty")
    repo = DocumentRepository(db=db, embedder=embedder)
    try:
        col = repo.rename_collection(current_user.id, collection_id, payload.name)
    except DuplicateCollectionError:
        raise HTTPException(status_code=409, detail="A collection with that name exists") from None
    if col is None:
        raise _collection_not_found()
    return _collection_out(col, repo.collection_document_count(col.id))


@router.delete("/collections/{collection_id}")
def delete_collection(
    collection_id: uuid.UUID,
    delete_documents: bool = False,
    db: Session = Depends(get_db),
    embedder: Embedder = Depends(get_embedder),
    _: str = Depends(verify_api_key),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    repo = DocumentRepository(db=db, embedder=embedder)
    if not repo.delete_collection(current_user.id, collection_id, delete_documents):
        raise _collection_not_found()
    return {"status": "deleted"}
