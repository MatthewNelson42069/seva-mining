"""Pydantic schemas for weekly_sweeps — Phase 7, Plan 01.

Mirrors the daily_summary schema pattern:
- WeeklySweepCard: API response shape (raw_sources_jsonb omitted, mirrors SummaryCardResponse)
- WeeklySweepFeedResponse: list wrapper for GET /weekly-sweeps (mirrors SummaryFeedResponse)

Column name reddit_top_md is preserved from the Phase 5 migration even though
Phase 7 stores X posts in it (per 07-CONTEXT.md X-API pivot — column rename
would require a migration that adds zero value).
"""
import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class WeeklySweepCard(BaseModel):
    """One weekly sweep card returned by GET /api/{company}/weekly-sweeps.

    Mirrors columns from backend/app/models/weekly_sweep.py with
    raw_sources_jsonb omitted (matches SummaryCardResponse pattern —
    internal telemetry, not for the UI).

    v3.0 Phase 9 (TENANT-04): `company_id` surfaced as optional for debug
    visibility — the URL prefix carries authoritative tenant scope.
    """
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: str | None = None  # v3.0 P9 — debug visibility (TENANT-04)
    generated_at: datetime
    week_start: date
    week_end: date
    # NOTE: column is named reddit_top_md in the Phase 5 migration; Phase 7
    # stores X posts in it under the X-API pivot. Renaming column would
    # require a migration with zero functional benefit.
    reddit_top_md: str | None = None
    story_virality_md: str | None = None
    content_angles_md: str | None = None
    status: Literal["completed", "failed", "partial"]
    error_text: str | None = None
    agent_run_id: uuid.UUID | None = None


class WeeklySweepFeedResponse(BaseModel):
    """List wrapper for GET /weekly-sweeps."""
    sweeps: list[WeeklySweepCard]
    total: int
