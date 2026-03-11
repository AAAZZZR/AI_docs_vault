import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.document import Document
from app.models.tag import DocumentTag, EvolutionLog, Tag, TagEvent, TagSource
from app.schemas.tag import TagCreate, TagResponse, TagUpdate

router = APIRouter()


@router.get("", response_model=list[TagResponse])
async def list_tags(db: AsyncSession = Depends(get_db)):
    """List all tags with document counts."""
    result = await db.execute(
        select(Tag, func.count(DocumentTag.id).label("doc_count"))
        .outerjoin(DocumentTag, DocumentTag.tag_id == Tag.id)
        .group_by(Tag.id)
        .order_by(Tag.name)
    )
    rows = result.all()

    return [
        TagResponse(
            id=tag.id,
            name=tag.name,
            color=tag.color,
            source=tag.source.value,
            description=tag.description,
            parent_id=tag.parent_id,
            document_count=doc_count,
            created_at=tag.created_at,
        )
        for tag, doc_count in rows
    ]


@router.post("", response_model=TagResponse, status_code=status.HTTP_201_CREATED)
async def create_tag(
    body: TagCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new user-defined tag."""
    existing = await db.execute(
        select(Tag).where(Tag.name == body.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Tag '{body.name}' already exists")

    tag = Tag(
        name=body.name,
        color=body.color,
        source=TagSource.USER,
        description=body.description,
        parent_id=body.parent_id,
    )
    db.add(tag)
    await db.flush()

    # Generate embedding for the tag
    try:
        import asyncio
        from app.services.embedding import embedding_service
        embed_text = f"{body.name}: {body.description}" if body.description else body.name
        tag.embedding = await asyncio.to_thread(embedding_service.embed_single, embed_text)
        await db.flush()
    except Exception:
        pass  # Non-critical

    return TagResponse(
        id=tag.id,
        name=tag.name,
        color=tag.color,
        source=tag.source.value,
        description=tag.description,
        parent_id=tag.parent_id,
        document_count=0,
        created_at=tag.created_at,
    )


@router.patch("/{tag_id}", response_model=TagResponse)
async def update_tag(
    tag_id: uuid.UUID,
    body: TagUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update tag name, color, description, or parent."""
    result = await db.execute(select(Tag).where(Tag.id == tag_id))
    tag = result.scalar_one_or_none()
    if tag is None:
        raise HTTPException(status_code=404, detail="Tag not found")

    if body.name is not None:
        existing = await db.execute(
            select(Tag).where(Tag.name == body.name, Tag.id != tag_id)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail=f"Tag '{body.name}' already exists")
        tag.name = body.name

    if body.color is not None:
        tag.color = body.color
    if body.description is not None:
        tag.description = body.description
    if body.parent_id is not None:
        tag.parent_id = body.parent_id if str(body.parent_id) != "00000000-0000-0000-0000-000000000000" else None

    await db.flush()

    # Get document count
    count_result = await db.execute(
        select(func.count(DocumentTag.id)).where(DocumentTag.tag_id == tag_id)
    )
    doc_count = count_result.scalar() or 0

    return TagResponse(
        id=tag.id,
        name=tag.name,
        color=tag.color,
        source=tag.source.value,
        description=tag.description,
        parent_id=tag.parent_id,
        document_count=doc_count,
        created_at=tag.created_at,
    )


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tag(
    tag_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete a tag (cascades to document_tags)."""
    result = await db.execute(select(Tag).where(Tag.id == tag_id))
    tag = result.scalar_one_or_none()
    if tag is None:
        raise HTTPException(status_code=404, detail="Tag not found")

    await db.delete(tag)


@router.post(
    "/documents/{document_id}/tags/{tag_id}",
    status_code=status.HTTP_201_CREATED,
)
async def add_tag_to_document(
    document_id: uuid.UUID,
    tag_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Add a tag to a document (records as user feedback)."""
    doc_result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    if doc_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Document not found")

    tag_result = await db.execute(select(Tag).where(Tag.id == tag_id))
    if tag_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Tag not found")

    existing = await db.execute(
        select(DocumentTag).where(
            DocumentTag.document_id == document_id,
            DocumentTag.tag_id == tag_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Tag already applied to document")

    doc_tag = DocumentTag(
        document_id=document_id,
        tag_id=tag_id,
        source=TagSource.USER,
        confidence=1.0,
    )
    db.add(doc_tag)

    # Record feedback event
    event = TagEvent(event_type="add", tag_id=tag_id, document_id=document_id)
    db.add(event)

    await db.flush()
    return {"document_id": str(document_id), "tag_id": str(tag_id)}


@router.delete(
    "/documents/{document_id}/tags/{tag_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_tag_from_document(
    document_id: uuid.UUID,
    tag_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Remove a tag from a document (records as user feedback)."""
    result = await db.execute(
        delete(DocumentTag).where(
            DocumentTag.document_id == document_id,
            DocumentTag.tag_id == tag_id,
        )
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Tag not associated with document")

    # Record feedback event
    event = TagEvent(
        event_type="remove",
        tag_id=tag_id,
        document_id=document_id,
    )
    db.add(event)


@router.post("/{tag_id}/merge", status_code=status.HTTP_200_OK)
async def merge_tag(
    tag_id: uuid.UUID,
    target_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Merge tag_id INTO target_id. All documents with tag_id get target_id instead."""
    source_tag = (await db.execute(select(Tag).where(Tag.id == tag_id))).scalar_one_or_none()
    target_tag = (await db.execute(select(Tag).where(Tag.id == target_id))).scalar_one_or_none()

    if not source_tag or not target_tag:
        raise HTTPException(status_code=404, detail="Tag not found")

    # Move document_tags from source to target (skip duplicates)
    source_doc_tags = (await db.execute(
        select(DocumentTag).where(DocumentTag.tag_id == tag_id)
    )).scalars().all()

    for dt in source_doc_tags:
        existing = (await db.execute(
            select(DocumentTag).where(
                DocumentTag.document_id == dt.document_id,
                DocumentTag.tag_id == target_id,
            )
        )).scalar_one_or_none()
        if existing is None:
            dt.tag_id = target_id
        else:
            await db.delete(dt)

    # Record event
    event = TagEvent(
        event_type="merge",
        tag_id=target_id,
        metadata_={"merged_from": str(tag_id), "merged_name": source_tag.name},
    )
    db.add(event)

    # Delete source tag
    await db.delete(source_tag)
    await db.flush()

    return {"merged_into": str(target_id), "deleted": str(tag_id)}
