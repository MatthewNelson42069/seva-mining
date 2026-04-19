from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.agent_run import AgentRun
from app.schemas.agent_run import AgentRunResponse

router = APIRouter(
    prefix="/agent-runs",
    tags=["agent-runs"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=list[AgentRunResponse])
async def list_agent_runs(
    agent_name: str | None = Query(None),
    days: int = Query(7, ge=1, le=30),
    db: AsyncSession = Depends(get_db),
):
    """List agent runs, optionally filtered by agent_name. Defaults to last 7 days."""
    cutoff = datetime.now(UTC) - timedelta(days=days)
    stmt = select(AgentRun).where(AgentRun.created_at >= cutoff)
    if agent_name:
        stmt = stmt.where(AgentRun.agent_name == agent_name)
    stmt = stmt.order_by(AgentRun.created_at.desc())
    result = await db.execute(stmt)
    return [AgentRunResponse.model_validate(r) for r in result.scalars().all()]
