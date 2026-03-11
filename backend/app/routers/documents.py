import uuid

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sse_starlette.sse import EventSourceResponse
from fastapi import Depends

from app.core.config import settings
from app.core.database import get_db
from app.core.redis import redis_client
from app.models.chunk import DocumentChunk
from app.models.document import Document, DocumentStatus
from app.models.tag import DocumentTag, Tag
from app.schemas.document import (
    DocumentDetailResponse,
    DocumentListResponse,
    DocumentResponse,
    TagInDocument,
    UploadResponse,
)

router = APIRouter()


@router.get("/status-stream", response_class=EventSourceResponse)
async def document_status_stream(request: Request):
    """SSE stream for real-time document processing status updates."""

    async def event_generator():
        pubsub = redis_client.pubsub()
        channel = "document-status"
        await pubsub.subscribe(channel)
        try:
            while True:
                if await request.is_disconnected():
                    break
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=1.0
                )
                if message and message["type"] == "message":
                    data = message["data"]
                    if isinstance(data, bytes):
                        data = data.decode()
                    yield {"event": "status_update", "data": data}
                else:
                    yield {"event": "ping", "data": ""}
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()

    return EventSourceResponse(event_generator())


@router.post("/upload", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload a PDF file directly to the database and start processing."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are supported",
        )

    pdf_bytes = await file.read()
    max_size = settings.PDF_MAX_SIZE_MB * 1024 * 1024
    if len(pdf_bytes) > max_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Max size is {settings.PDF_MAX_SIZE_MB}MB",
        )

    document_id = uuid.uuid4()
    document = Document(
        id=document_id,
        title=file.filename.rsplit(".", 1)[0],
        original_filename=file.filename,
        pdf_data=pdf_bytes,
        file_size=len(pdf_bytes),
        status=DocumentStatus.PROCESSING,
    )
    db.add(document)
    await db.commit()  # Commit before dispatching task to avoid race condition

    # Dispatch Celery task
    from app.tasks.pdf_processing import process_pdf

    process_pdf.delay(document_id=str(document_id))

    return UploadResponse(document_id=document_id, status="processing")


@router.get("/{document_id}/download")
async def download_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Download the original PDF from the database."""
    result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    document = result.scalar_one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    if document.pdf_data is None:
        raise HTTPException(status_code=404, detail="PDF data not available")

    return Response(
        content=document.pdf_data,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{document.original_filename}"'
        },
    )


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: DocumentStatus | None = Query(None, alias="status"),
    tag_ids: list[uuid.UUID] | None = Query(None),
    search: str | None = Query(None, max_length=200),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    db: AsyncSession = Depends(get_db),
):
    """List all documents with filtering and pagination."""
    query = select(Document)

    if status_filter:
        query = query.where(Document.status == status_filter)
    if search:
        query = query.where(Document.title.ilike(f"%{search}%"))
    if tag_ids:
        query = query.join(DocumentTag).where(DocumentTag.tag_id.in_(tag_ids))

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Sort
    sort_column = getattr(Document, sort_by, Document.created_at)
    if sort_order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    # Paginate
    query = query.offset((page - 1) * page_size).limit(page_size)
    query = query.options(
        selectinload(Document.document_tags).selectinload(DocumentTag.tag)
    )

    result = await db.execute(query)
    documents = result.scalars().unique().all()

    doc_responses = []
    for doc in documents:
        tags = [
            TagInDocument(
                id=dt.tag.id,
                name=dt.tag.name,
                color=dt.tag.color,
                source=dt.source.value,
                confidence=dt.confidence,
            )
            for dt in doc.document_tags
        ]
        doc_responses.append(
            DocumentResponse(
                id=doc.id,
                title=doc.title,
                original_filename=doc.original_filename,
                file_size=doc.file_size,
                page_count=doc.page_count,
                status=doc.status.value,
                global_index_entry=doc.global_index_entry,
                tags=tags,
                created_at=doc.created_at,
                updated_at=doc.updated_at,
            )
        )

    return DocumentListResponse(
        documents=doc_responses,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{document_id}", response_model=DocumentDetailResponse)
async def get_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a single document with full details."""
    result = await db.execute(
        select(Document)
        .where(Document.id == document_id)
        .options(
            selectinload(Document.document_tags).selectinload(DocumentTag.tag)
        )
    )
    document = result.scalar_one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    tags = [
        TagInDocument(
            id=dt.tag.id,
            name=dt.tag.name,
            color=dt.tag.color,
            source=dt.source.value,
            confidence=dt.confidence,
        )
        for dt in document.document_tags
    ]

    return DocumentDetailResponse(
        id=document.id,
        title=document.title,
        original_filename=document.original_filename,
        file_size=document.file_size,
        page_count=document.page_count,
        status=document.status.value,
        global_index_entry=document.global_index_entry,
        condensed_note=document.condensed_note,
        tags=tags,
        has_pdf=document.pdf_data is not None,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


@router.get("/{document_id}/chunks")
async def get_document_chunks(
    document_id: uuid.UUID,
    full: bool = Query(False, description="Include full chunk content"),
    db: AsyncSession = Depends(get_db),
):
    """Get all chunks for a document (useful for debugging and detail view)."""
    doc_result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    if doc_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Document not found")

    result = await db.execute(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.chunk_index)
    )
    chunks = result.scalars().all()
    return [
        {
            "id": str(c.id),
            "chunk_index": c.chunk_index,
            "heading": c.heading,
            "content": c.content[:300] + "..." if len(c.content) > 300 else c.content,
            **({"full_content": c.content} if full else {}),
            "page_start": c.page_start,
            "page_end": c.page_end,
            "token_count": c.token_count,
            "has_embedding": c.embedding is not None,
        }
        for c in chunks
    ]


@router.post("/{document_id}/reprocess")
async def reprocess_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Re-trigger processing for a document (e.g., after an error)."""
    result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    document = result.scalar_one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    if document.pdf_data is None:
        raise HTTPException(status_code=400, detail="No PDF data to reprocess")

    document.status = DocumentStatus.PROCESSING
    document.processing_error = None
    await db.commit()  # Commit before dispatching task to avoid race condition

    from app.tasks.pdf_processing import process_pdf
    process_pdf.delay(document_id=str(document_id))

    return {"status": "processing", "document_id": str(document_id)}


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete a document (CASCADE handles related records)."""
    result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    document = result.scalar_one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    await db.delete(document)
