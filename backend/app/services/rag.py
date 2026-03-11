"""
RAG Service — chunk-level retrieval with document context.

Pipeline:
1. Embed query
2. Vector search on document_chunks (cosine similarity)
3. Group chunks by document
4. Return chunks + parent document condensed notes for context
"""

import logging
import uuid
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chunk import DocumentChunk
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
        top_k: int = 8,
    ) -> dict:
        """
        Chunk-level RAG query.

        Returns:
            {
                "chunks": [{"content", "heading", "page_start", "page_end", "document_id", "document_title", "distance"}],
                "condensed_notes": [{"document_id", "title", "note"}],
                "document_ids": [str],
            }
        """
        import asyncio

        # Step 1: Embed query
        query_embedding = await asyncio.to_thread(
            embedding_service.embed_single, query_text
        )

        # Step 2: Vector search on chunks
        chunk_query = (
            select(
                DocumentChunk,
                DocumentChunk.embedding.cosine_distance(query_embedding).label("distance"),
            )
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(
                Document.status == DocumentStatus.READY,
                DocumentChunk.embedding.isnot(None),
            )
            .order_by("distance")
            .limit(top_k)
        )

        # Optional tag filter
        if tag_filter:
            chunk_query = chunk_query.join(
                DocumentTag, DocumentTag.document_id == Document.id
            ).where(DocumentTag.tag_id.in_(tag_filter))

        result = await db.execute(chunk_query)
        rows = result.all()

        if not rows:
            # Fallback: try document-level search if no chunks exist yet
            return await self._fallback_document_search(
                db, query_embedding, tag_filter, top_k=5
            )

        # Step 3: Build response
        chunks = []
        doc_ids_seen = set()
        doc_id_list = []

        for row in rows:
            chunk = row.DocumentChunk
            distance = float(row.distance)
            doc_id = str(chunk.document_id)

            chunks.append({
                "content": chunk.content,
                "heading": chunk.heading,
                "page_start": chunk.page_start,
                "page_end": chunk.page_end,
                "document_id": doc_id,
                "distance": distance,
            })

            if doc_id not in doc_ids_seen:
                doc_ids_seen.add(doc_id)
                doc_id_list.append(doc_id)

        # Step 4: Fetch parent documents for condensed notes
        doc_uuids = [uuid.UUID(d) for d in doc_id_list]
        doc_result = await db.execute(
            select(Document).where(Document.id.in_(doc_uuids))
        )
        documents = {str(d.id): d for d in doc_result.scalars().all()}

        # Attach document titles to chunks
        for chunk in chunks:
            doc = documents.get(chunk["document_id"])
            chunk["document_title"] = doc.title if doc else "Unknown"

        condensed_notes = []
        for doc_id in doc_id_list:
            doc = documents.get(doc_id)
            if doc:
                condensed_notes.append({
                    "document_id": doc_id,
                    "title": doc.title,
                    "note": doc.condensed_note or {},
                })

        logger.info(
            "RAG query returned %d chunks from %d documents",
            len(chunks), len(doc_id_list),
        )

        return {
            "chunks": chunks,
            "condensed_notes": condensed_notes,
            "document_ids": doc_id_list,
        }

    async def _fallback_document_search(
        self,
        db: AsyncSession,
        query_embedding: list[float],
        tag_filter: list[uuid.UUID] | None,
        top_k: int = 5,
    ) -> dict:
        """Fallback to document-level search when no chunks exist."""
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
            return {"chunks": [], "condensed_notes": [], "document_ids": []}

        condensed_notes = []
        document_ids = []
        chunks = []

        for row in rows:
            doc = row.Document
            doc_id = str(doc.id)
            document_ids.append(doc_id)
            note = doc.condensed_note or {}
            condensed_notes.append({
                "document_id": doc_id,
                "title": doc.title,
                "note": note,
                "distance": float(row.distance),
            })
            # Synthesize a pseudo-chunk from the condensed note
            summary = note.get("summary", "")
            if summary:
                chunks.append({
                    "content": summary,
                    "heading": "Document Summary",
                    "page_start": None,
                    "page_end": None,
                    "document_id": doc_id,
                    "document_title": doc.title,
                    "distance": float(row.distance),
                })

        logger.info(
            "RAG fallback: returned %d documents (no chunks found)", len(document_ids)
        )

        return {
            "chunks": chunks,
            "condensed_notes": condensed_notes,
            "document_ids": document_ids,
        }


rag_service = RAGService()
