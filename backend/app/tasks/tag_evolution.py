"""Celery task for periodic tag evolution analysis."""

import logging

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.document import Document, DocumentStatus
from app.models.tag import Tag
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

sync_engine = create_engine(
    settings.DATABASE_URL_SYNC,
    pool_size=2,
    max_overflow=3,
    pool_pre_ping=True,
)


@celery_app.task(name="app.tasks.tag_evolution.run_tag_evolution")
def run_tag_evolution():
    """
    Periodic tag evolution analysis.
    Checks if enough documents exist, then runs the evolution pipeline.
    """
    import asyncio
    from app.core.database import AsyncSessionLocal
    from app.services.tag_evolution import TagEvolutionService

    # Quick check: enough documents?
    with Session(sync_engine) as db:
        doc_count = db.execute(
            select(func.count(Document.id)).where(
                Document.status == DocumentStatus.READY
            )
        ).scalar() or 0

        tag_count = db.execute(
            select(func.count(Tag.id))
        ).scalar() or 0

    if doc_count < settings.TAG_EVOLUTION_MIN_DOCS:
        logger.info(
            "Skipping tag evolution: only %d docs (need %d)",
            doc_count, settings.TAG_EVOLUTION_MIN_DOCS,
        )
        return

    if tag_count < 2:
        logger.info("Skipping tag evolution: only %d tags", tag_count)
        return

    logger.info(
        "Running tag evolution analysis (%d docs, %d tags)",
        doc_count, tag_count,
    )

    async def _run():
        async with AsyncSessionLocal() as db:
            svc = TagEvolutionService(db)
            proposals = await svc.analyze()
            if proposals:
                logger.info("Found %d evolution proposals", len(proposals))
                await svc.save_proposals(proposals)
                await db.commit()
            else:
                logger.info("No evolution proposals found")

    asyncio.run(_run())
