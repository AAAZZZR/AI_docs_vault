"""
Tag Evolution Service — detects and proposes tag merges, splits, and hierarchy changes.

Uses tag embeddings for similarity detection and LLM for final judgment.
"""

import logging
import uuid
from typing import Optional

import numpy as np
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tag import DocumentTag, EvolutionLog, Tag, TagEvent, TagSource

logger = logging.getLogger(__name__)


class TagEvolutionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def analyze(self) -> list[dict]:
        """Run full evolution analysis. Returns list of proposed actions."""
        proposals = []

        tags = await self._load_tags_with_embeddings()
        if len(tags) < 2:
            return proposals

        # 1. Detect merge candidates (high similarity)
        merge_candidates = self._find_merge_candidates(tags)
        for a, b, similarity in merge_candidates:
            proposals.append({
                "action": "merge",
                "details": {
                    "tag_a_id": str(a["id"]),
                    "tag_a_name": a["name"],
                    "tag_b_id": str(b["id"]),
                    "tag_b_name": b["name"],
                    "similarity": round(similarity, 3),
                    "keep": a["name"] if a["doc_count"] >= b["doc_count"] else b["name"],
                    "remove": b["name"] if a["doc_count"] >= b["doc_count"] else a["name"],
                },
                "confidence": similarity,
            })

        # 2. Detect split candidates (tag with many docs + high variance)
        split_candidates = await self._find_split_candidates(tags)
        for tag_info in split_candidates:
            proposals.append({
                "action": "split",
                "details": tag_info,
                "confidence": 0.7,
            })

        # 3. Detect hierarchy candidates (subset relationships)
        hierarchy_candidates = await self._find_hierarchy_candidates(tags)
        for parent, child in hierarchy_candidates:
            proposals.append({
                "action": "reparent",
                "details": {
                    "child_id": str(child["id"]),
                    "child_name": child["name"],
                    "parent_id": str(parent["id"]),
                    "parent_name": parent["name"],
                },
                "confidence": 0.75,
            })

        return proposals

    async def save_proposals(self, proposals: list[dict]) -> list[EvolutionLog]:
        """Save evolution proposals to the database."""
        from app.core.config import settings

        logs = []
        for p in proposals:
            confidence = p.get("confidence", 0.0)
            auto = confidence >= settings.TAG_AUTO_APPROVE_CONFIDENCE
            log = EvolutionLog(
                action=p["action"],
                details=p["details"],
                status="auto_applied" if auto else "pending",
            )
            self.db.add(log)
            logs.append(log)

            if auto:
                await self.db.flush()
                await self.execute_evolution(log)

        await self.db.flush()
        return logs

    async def execute_evolution(self, log: EvolutionLog):
        """Execute a single evolution action."""
        if log.action == "merge":
            await self._execute_merge(log.details)
        elif log.action == "reparent":
            await self._execute_reparent(log.details)
        # split requires LLM suggestion — handled separately

    async def _execute_merge(self, details: dict):
        """Merge one tag into another."""
        keep_name = details["keep"]
        remove_name = details["remove"]

        keep_tag = (await self.db.execute(
            select(Tag).where(Tag.name == keep_name)
        )).scalar_one_or_none()
        remove_tag = (await self.db.execute(
            select(Tag).where(Tag.name == remove_name)
        )).scalar_one_or_none()

        if not keep_tag or not remove_tag:
            return

        # Move document associations
        remove_doc_tags = (await self.db.execute(
            select(DocumentTag).where(DocumentTag.tag_id == remove_tag.id)
        )).scalars().all()

        for dt in remove_doc_tags:
            existing = (await self.db.execute(
                select(DocumentTag).where(
                    DocumentTag.document_id == dt.document_id,
                    DocumentTag.tag_id == keep_tag.id,
                )
            )).scalar_one_or_none()
            if existing is None:
                dt.tag_id = keep_tag.id
            else:
                await self.db.delete(dt)

        # Record event
        event = TagEvent(
            event_type="merge",
            tag_id=keep_tag.id,
            metadata_={"merged_from": str(remove_tag.id), "merged_name": remove_name},
        )
        self.db.add(event)

        await self.db.delete(remove_tag)
        await self.db.flush()

        # Update count
        count = (await self.db.execute(
            select(func.count(DocumentTag.id)).where(DocumentTag.tag_id == keep_tag.id)
        )).scalar() or 0
        keep_tag.document_count = count

    async def _execute_reparent(self, details: dict):
        """Set parent-child relationship."""
        child_id = uuid.UUID(details["child_id"])
        parent_id = uuid.UUID(details["parent_id"])

        child = (await self.db.execute(
            select(Tag).where(Tag.id == child_id)
        )).scalar_one_or_none()
        if child:
            child.parent_id = parent_id

    async def _load_tags_with_embeddings(self) -> list[dict]:
        """Load all tags that have embeddings."""
        result = await self.db.execute(
            select(Tag).where(Tag.embedding.isnot(None))
        )
        tags = result.scalars().all()
        return [
            {
                "id": t.id,
                "name": t.name,
                "embedding": np.array(t.embedding),
                "doc_count": t.document_count,
                "parent_id": t.parent_id,
            }
            for t in tags
        ]

    def _find_merge_candidates(
        self, tags: list[dict], threshold: float | None = None
    ) -> list[tuple[dict, dict, float]]:
        """Find tag pairs with high embedding similarity."""
        from app.core.config import settings
        if threshold is None:
            threshold = settings.TAG_MERGE_SIMILARITY_THRESHOLD

        candidates = []
        for i, a in enumerate(tags):
            for j, b in enumerate(tags):
                if j <= i:
                    continue
                sim = self._cosine_similarity(a["embedding"], b["embedding"])
                if sim >= threshold:
                    candidates.append((a, b, sim))

        candidates.sort(key=lambda x: x[2], reverse=True)
        return candidates

    async def _find_split_candidates(self, tags: list[dict]) -> list[dict]:
        """Find tags with too many documents that might need splitting."""
        from app.core.config import settings

        candidates = []
        for tag in tags:
            if tag["doc_count"] < settings.TAG_SPLIT_DOC_THRESHOLD:
                continue
            candidates.append({
                "tag_id": str(tag["id"]),
                "tag_name": tag["name"],
                "document_count": tag["doc_count"],
                "suggestion": f"Tag '{tag['name']}' has {tag['doc_count']} documents. Consider splitting into subtags.",
            })
        return candidates

    async def _find_hierarchy_candidates(
        self, tags: list[dict]
    ) -> list[tuple[dict, dict]]:
        """Find tags where one is likely a subtopic of another.

        Uses document set overlap: if >80% of child's docs also have parent tag,
        and child has fewer docs, suggest hierarchy.
        """
        candidates = []
        for a in tags:
            for b in tags:
                if a["id"] == b["id"] or a["parent_id"] or b["parent_id"]:
                    continue
                if a["doc_count"] <= b["doc_count"]:
                    continue  # a is potential parent

                # Check document overlap
                a_docs = set(
                    r[0] for r in (await self.db.execute(
                        select(DocumentTag.document_id).where(
                            DocumentTag.tag_id == a["id"]
                        )
                    )).all()
                )
                b_docs = set(
                    r[0] for r in (await self.db.execute(
                        select(DocumentTag.document_id).where(
                            DocumentTag.tag_id == b["id"]
                        )
                    )).all()
                )

                if not b_docs:
                    continue

                overlap = len(a_docs & b_docs) / len(b_docs)
                if overlap >= 0.8 and b["doc_count"] < a["doc_count"]:
                    candidates.append((a, b))

        return candidates

    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))
