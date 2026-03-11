import logging
import uuid
from datetime import datetime, timezone

from celery import Task
from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.redis import publish_document_status_sync
from app.models.document import Document, DocumentStatus
from app.models.tag import DocumentTag, Tag, TagSource
from app.services.embedding import embedding_service
from app.services.llm import llm_service
from app.services.pdf_parser import pdf_parser
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

sync_engine = create_engine(
    settings.DATABASE_URL_SYNC,
    pool_size=2,
    max_overflow=3,
    pool_pre_ping=True,
)


def _publish(document_id, status, detail=""):
    try:
        publish_document_status_sync(
            uuid.UUID(str(document_id)),
            status,
            detail,
        )
    except Exception as e:
        logger.warning("Failed to publish status: %s", e)


def _set_error(document_id: str, error_message: str):
    with Session(sync_engine) as db:
        doc = db.execute(
            select(Document).where(Document.id == uuid.UUID(document_id))
        ).scalar_one_or_none()
        if doc:
            doc.status = DocumentStatus.ERROR
            doc.processing_error = error_message
            _publish(document_id, "error", error_message)
            db.commit()


@celery_app.task(
    bind=True,
    name="app.tasks.pdf_processing.process_pdf",
    max_retries=3,
    default_retry_delay=60,
    soft_time_limit=600,
    time_limit=900,
)
def process_pdf(self: Task, document_id: str):
    """
    Full PDF processing pipeline:
    1. Read PDF from DB
    2. Convert pages to images
    3. Send each page to LLM for extraction
    4. Synthesize into condensed note
    5. Generate document-level embedding
    6. Generate context-aware tags with embeddings
    7. Save to DB
    8. Publish ready status
    """
    logger.info("Starting PDF processing for document %s", document_id)

    with Session(sync_engine) as db:
        document = db.execute(
            select(Document).where(Document.id == uuid.UUID(document_id))
        ).scalar_one_or_none()

        if document is None:
            logger.error("Document %s not found", document_id)
            return

        document.processing_started_at = datetime.now(timezone.utc)
        db.commit()

    try:
        # Step 1: Read PDF from database
        _publish(document_id, "processing", "Reading PDF...")
        with Session(sync_engine) as db:
            document = db.execute(
                select(Document).where(Document.id == uuid.UUID(document_id))
            ).scalar_one()
            pdf_bytes = document.pdf_data
            filename = document.original_filename

        if not pdf_bytes:
            raise ValueError("No PDF data found in database")

        # Step 2: Convert to images
        _publish(document_id, "processing", "Converting pages to images...")
        page_images = pdf_parser.extract_pages_as_images(pdf_bytes)
        total_pages = len(page_images)
        logger.info("Converted %d pages to images", total_pages)

        # Step 3: Parse each page with LLM
        page_extractions = []
        for page_num, base64_img in page_images:
            _publish(
                document_id, "processing",
                f"Analyzing page {page_num}/{total_pages}...",
            )
            context = ""
            if page_extractions:
                prev = page_extractions[-1]
                context = prev.get("summary", "")[:200]

            extraction = llm_service.parse_pdf_page(
                base64_img, page_num, total_pages, context
            )
            page_extractions.append(extraction)
            logger.info("Parsed page %d/%d", page_num, total_pages)

        # Step 4: Synthesize condensed note
        _publish(document_id, "processing", "Generating condensed note...")
        condensed_note = llm_service.generate_condensed_note(
            page_extractions, filename
        )
        logger.info("Generated condensed note: %s", condensed_note.get("title", ""))

        # Step 5: Generate document-level embedding
        _publish(document_id, "processing", "Generating embedding...")
        embed_parts = [condensed_note.get("summary", "")]
        for sec in condensed_note.get("sections", []):
            heading = sec.get("heading", "")
            content = sec.get("content", "")
            embed_parts.append(f"{heading}\n{content}" if heading else content)
        for finding in condensed_note.get("key_findings", []):
            embed_parts.append(finding)
        embed_text = "\n\n".join(p for p in embed_parts if p)
        doc_embedding = embedding_service.embed_single(embed_text) if embed_text else None

        # Step 6: Generate context-aware tags
        _publish(document_id, "processing", "Generating tags...")
        with Session(sync_engine) as db:
            existing_tags_result = db.execute(select(Tag.name, Tag.description))
            existing_tags = [
                {"name": r[0], "description": r[1] or ""}
                for r in existing_tags_result.all()
            ]

        tag_suggestions = llm_service.generate_tags(
            condensed_note, existing_tags
        )

        # Step 7: Save everything to DB
        _publish(document_id, "processing", "Saving results...")
        with Session(sync_engine) as db:
            document = db.execute(
                select(Document).where(Document.id == uuid.UUID(document_id))
            ).scalar_one()

            document.condensed_note = condensed_note
            document.page_count = total_pages
            document.title = condensed_note.get("title", document.original_filename)
            document.global_index_entry = condensed_note.get("summary", "")[:500]
            document.embedding = doc_embedding
            document.status = DocumentStatus.READY
            document.processing_completed_at = datetime.now(timezone.utc)
            document.processing_error = None

            # Save tags with embeddings
            for tag_data in tag_suggestions:
                tag_name = tag_data.get("name", "").strip()
                if not tag_name:
                    continue

                existing_tag = db.execute(
                    select(Tag).where(Tag.name == tag_name)
                ).scalar_one_or_none()

                if existing_tag is None:
                    # Create new tag with embedding
                    tag_desc = tag_data.get("description", "")
                    embed_text = f"{tag_name}: {tag_desc}" if tag_desc else tag_name
                    try:
                        tag_embedding = embedding_service.embed_single(embed_text)
                    except Exception:
                        tag_embedding = None

                    existing_tag = Tag(
                        name=tag_name,
                        source=TagSource.AUTO,
                        description=tag_desc or None,
                        embedding=tag_embedding,
                    )
                    db.add(existing_tag)
                    db.flush()

                existing_assoc = db.execute(
                    select(DocumentTag).where(
                        DocumentTag.document_id == document.id,
                        DocumentTag.tag_id == existing_tag.id,
                    )
                ).scalar_one_or_none()

                if existing_assoc is None:
                    doc_tag = DocumentTag(
                        document_id=document.id,
                        tag_id=existing_tag.id,
                        confidence=tag_data.get("confidence", 0.8),
                        source=TagSource.AUTO,
                    )
                    db.add(doc_tag)

            # Update document_count on tags
            for tag_data in tag_suggestions:
                tag_name = tag_data.get("name", "").strip()
                if not tag_name:
                    continue
                tag = db.execute(
                    select(Tag).where(Tag.name == tag_name)
                ).scalar_one_or_none()
                if tag:
                    from sqlalchemy import func
                    count = db.execute(
                        select(func.count(DocumentTag.id)).where(
                            DocumentTag.tag_id == tag.id
                        )
                    ).scalar() or 0
                    tag.document_count = count

            db.commit()

        # Step 8: Done
        _publish(document_id, "ready", "Document ready!")
        logger.info("PDF processing complete for document %s", document_id)

    except SoftTimeLimitExceeded:
        logger.error("PDF processing timed out for %s", document_id)
        _set_error(document_id, "Processing timed out. The PDF may be too complex.")
        raise

    except Exception as exc:
        logger.exception("PDF processing failed for %s", document_id)
        _set_error(document_id, str(exc)[:500])
        raise self.retry(exc=exc)
