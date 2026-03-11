import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.tag import EvolutionLog

router = APIRouter()


@router.get("/pending")
async def list_pending(db: AsyncSession = Depends(get_db)):
    """List pending evolution suggestions."""
    result = await db.execute(
        select(EvolutionLog)
        .where(EvolutionLog.status == "pending")
        .order_by(EvolutionLog.created_at.desc())
    )
    logs = result.scalars().all()
    return [
        {
            "id": str(log.id),
            "action": log.action,
            "details": log.details,
            "status": log.status,
            "created_at": log.created_at.isoformat(),
        }
        for log in logs
    ]


@router.post("/{log_id}/approve")
async def approve_evolution(
    log_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Approve a pending evolution suggestion and execute it."""
    result = await db.execute(
        select(EvolutionLog).where(EvolutionLog.id == log_id)
    )
    log = result.scalar_one_or_none()
    if log is None:
        raise HTTPException(status_code=404, detail="Evolution log not found")
    if log.status != "pending":
        raise HTTPException(status_code=400, detail="Already processed")

    # Execute the evolution action
    from app.services.tag_evolution import TagEvolutionService
    svc = TagEvolutionService(db)
    await svc.execute_evolution(log)

    log.status = "approved"
    await db.flush()

    return {"status": "approved", "action": log.action}


@router.post("/{log_id}/reject")
async def reject_evolution(
    log_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Reject a pending evolution suggestion."""
    result = await db.execute(
        select(EvolutionLog).where(EvolutionLog.id == log_id)
    )
    log = result.scalar_one_or_none()
    if log is None:
        raise HTTPException(status_code=404, detail="Evolution log not found")
    if log.status != "pending":
        raise HTTPException(status_code=400, detail="Already processed")

    log.status = "rejected"
    await db.flush()

    return {"status": "rejected"}


@router.post("/run")
async def trigger_evolution(db: AsyncSession = Depends(get_db)):
    """Manually trigger tag evolution analysis."""
    from app.tasks.tag_evolution import run_tag_evolution
    run_tag_evolution.delay()
    return {"status": "triggered"}
