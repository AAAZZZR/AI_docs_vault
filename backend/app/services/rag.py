import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentStatus
from app.models.tag import DocumentTag
from app.services.embedding import embedding_service

logger = logging.getLogger(__name__)


class RAGService:
    async def query(
        self,
        db: AsyncSession,
        query_text: str,
        tag_filter: list[uuid.UUID] | None = None,
        top_k: int = 5,
    ) -> dict:
        """
        Document-level RAG pipeline:
        1. Embed query
        2. Vector search on documents table (optional tag filter)
        3. Return matched documents with full condensed_notes
        """
        import asyncio

        # Step 1: Embed query
        query_embedding = await asyncio.to_thread(
            embedding_service.embed_single, query_text
        )

        # Step 2: Vector similarity search on documents
        doc_query = (
            select(
                Document,
                Document.embedding.cosine_distance(query_embedding).label("distance"),
            )
            .where(
                Document.status == DocumentStatus.READY,
                Document.embedding.isnot(None),
            )
            .order_by("distance")
            .limit(top_k)
        )

        if tag_filter:
            doc_query = doc_query.join(
                DocumentTag, DocumentTag.document_id == Document.id
            ).where(DocumentTag.tag_id.in_(tag_filter))

        result = await db.execute(doc_query)
        rows = result.all()

        if not rows:
            return {
                "chunks": [],
                "condensed_notes": [],
                "document_ids": [],
            }

        # Step 3: Build context bundle
        condensed_notes = []
        document_ids = []
        for row in rows:
            doc = row.Document
            document_ids.append(str(doc.id))
            condensed_notes.append({
                "document_id": str(doc.id),
                "title": doc.title,
                "note": doc.condensed_note or {},
                "distance": float(row.distance),
            })

        logger.info(
            "RAG query returned %d documents", len(document_ids),
        )

        return {
            "chunks": [],
            "condensed_notes": condensed_notes,
            "document_ids": document_ids,
        }


rag_service = RAGService()
