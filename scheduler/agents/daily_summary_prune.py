"""v2.0 daily_summary_prune cron — Phase 4, Plan 01.

Fires at 03:00 PT daily under advisory lock 1018. Deletes daily_summaries
rows where generated_at < now - 30 days. Writes one agent_runs row per
fire with structured notes telemetry.

Pattern mirrors run_daily_summary (Phase 1):
  - Insert agent_runs row (status='running') first
  - Try: DELETE + commit, mark agent_run completed in finally
  - Except: log + mark agent_run failed (do NOT re-raise — EXEC-04 contract)

EXEC-04 contract: never propagate exceptions out of run_daily_summary_prune.
reconcile_stale_runs in worker.py will sweep any orphan 'running' agent_runs
row left by a hard-killed worker (the existing INFRA contract — no new code
needed here).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete

from database import AsyncSessionLocal
from models.agent_run import AgentRun
from models.daily_summary import DailySummary

logger = logging.getLogger(__name__)

RETENTION_DAYS = 30  # locked CONTEXT decision; single-line change to revisit in v2.1+


async def run_daily_summary_prune() -> None:
    """Entry point — called from worker.py via _make_daily_summary_prune_job + with_advisory_lock.

    Deletes daily_summaries rows older than RETENTION_DAYS (30d). Writes one
    agent_runs row per execution with telemetry notes:
      {"deleted_count": N, "cutoff_at": "<ISO8601>"}

    items_found = deleted_count (count of rows removed)
    items_queued = 0           (prune produces no new items)
    """
    now_utc = datetime.now(timezone.utc)
    cutoff = now_utc - timedelta(days=RETENTION_DAYS)
    cutoff_iso = cutoff.isoformat()

    # Insert agent_runs row (status='running').
    # reconcile_stale_runs will sweep this row back to 'failed' if the worker
    # is hard-killed before the finally block runs. (existing INFRA contract)
    agent_run = AgentRun(
        agent_name="daily_summary_prune",
        started_at=now_utc,
        items_found=0,
        items_queued=0,
        items_filtered=0,
        status="running",
    )
    async with AsyncSessionLocal() as session:
        session.add(agent_run)
        await session.commit()
        await session.refresh(agent_run)

    deleted_count = 0
    run_status = "failed"
    error_text: str | None = None

    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                delete(DailySummary).where(
                    DailySummary.generated_at < datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)
                )
            )
            deleted_count = result.rowcount or 0
            await session.commit()

        run_status = "completed"
        logger.info(
            "daily_summary_prune: deleted %d rows older than %s (cutoff: %s)",
            deleted_count,
            f"{RETENTION_DAYS}d",
            cutoff_iso,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("daily_summary_prune failed: %s", exc)
        error_text = f"{type(exc).__name__}: {str(exc)[:500]}"
        run_status = "failed"
    finally:
        # Telemetry write — never raise out of this block (EXEC-04).
        try:
            async with AsyncSessionLocal() as session:
                fresh = await session.get(AgentRun, agent_run.id)
                if fresh is not None:
                    fresh.status = run_status
                    fresh.ended_at = datetime.now(timezone.utc)
                    fresh.items_found = deleted_count
                    fresh.items_queued = 0
                    fresh.notes = json.dumps(
                        {"deleted_count": deleted_count, "cutoff_at": cutoff_iso}
                    )
                    if error_text:
                        fresh.errors = [error_text]
                    await session.commit()
        except Exception:
            logger.exception("daily_summary_prune: agent_runs telemetry update failed")
