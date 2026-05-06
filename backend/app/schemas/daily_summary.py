"""Pydantic schemas for daily_summaries — Phase 1, Plan 01 / Phase 3.

Includes:
- RawSources: typed model gating raw_sources_jsonb writes (Pitfall HIGH-4 mitigation)
- SummaryCardResponse: API response shape (raw_sources_jsonb omitted)
- SummaryFeedResponse: list wrapper for GET /summaries
"""
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# RawSources — strict shape for raw_sources_jsonb writes (HIGH-4 mitigation)
# ---------------------------------------------------------------------------

class GoldNewsSource(BaseModel):
    """One scored story that fed the gold-news section."""
    title: str
    link: str
    source_name: str
    score: float = Field(ge=0.0, le=10.0)
    published_at: datetime | None = None


class OntarioLawHit(BaseModel):
    """One Ontario law hit (Phase 2 will populate; Phase 1 stub returns empty)."""
    title: str
    link: str
    source_name: str
    bill_or_reg_number: str | None = None
    favour_or_neutral: str | None = None  # 'favour' | 'neutral' | 'against'
    reason: str | None = None  # Phase 2 — used in the markdown bullet rendering
    published_at: datetime | None = None


class LastKnownLaw(BaseModel):
    """Continuity pointer for Ontario Law empty-state copy.

    Stored at daily_summaries.raw_sources_jsonb.ontario_law.last_known_law
    and propagated forward across fires that produce zero surviving hits.
    """
    date: str  # YYYY-MM-DD — date of the fire that produced this hit
    law_name: str  # e.g. "Bill 71 (Building Ontario Act)"
    url: str  # link to the article that surfaced the hit


class OntarioLawState(BaseModel):
    """Ontario law section state — hits + continuity pointer."""
    hits: list[OntarioLawHit] = Field(default_factory=list)
    last_known_law: LastKnownLaw | None = None  # Phase 2 narrows from OntarioLawHit to LastKnownLaw


class OntarioStatsSnapshot(BaseModel):
    """One StatCan polled state — Phase 3.

    Stored at daily_summaries.raw_sources_jsonb.ontario_stats.snapshot
    and propagated forward across non-release-day fires. period is
    the StatCan reference period (refPer, YYYY-MM). figure_kg is the
    Ontario gold recoverable production figure (vectorId 1146004456).
    release_time is StatCan's release timestamp (lexicographically
    comparable as ISO YYYY-MM-DDThh:mm).
    """
    period: str  # "YYYY-MM"
    figure_kg: float
    release_time: str  # "YYYY-MM-DDThh:mm"
    prior_period: str | None = None
    prior_figure_kg: float | None = None


class OntarioStatsState(BaseModel):
    """Ontario stats section state — Phase 3 (replaces Phase 1 placeholder).

    snapshot: latest StatCan polled figure (None on first-ever fire or after error)
    last_state: which branch the last fire took
    last_error_text: short error string for visibility on last_state='error'
    """
    snapshot: OntarioStatsSnapshot | None = None
    last_state: Literal["fresh", "no_new_data", "error"] | None = None
    last_error_text: str | None = None


class RawSources(BaseModel):
    """Locked Pydantic shape for daily_summaries.raw_sources_jsonb.

    Validated on write via model_dump(). Phase 1 ships with ontario_law and
    ontario_stats as empty stubs; Phase 2/3 populate them.

    DO NOT add fields without bumping a migration AND coordinating with the
    scheduler agent writer (HIGH-4 schema-drift defense).
    """
    gold_news: list[GoldNewsSource] = Field(default_factory=list)
    ontario_law: OntarioLawState = Field(default_factory=OntarioLawState)
    ontario_stats: OntarioStatsState = Field(default_factory=OntarioStatsState)


# ---------------------------------------------------------------------------
# API response shapes
# ---------------------------------------------------------------------------

class SummaryCardResponse(BaseModel):
    """Card payload returned by GET /summaries.

    raw_sources_jsonb intentionally omitted — large forensics blob; if a
    detail endpoint is added later it can return it.
    """
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    generated_at: datetime
    period_label: str
    gold_news_md: str | None
    ontario_law_md: str | None
    ontario_stats_md: str | None
    status: str  # 'completed' | 'failed' | 'partial'
    error_text: str | None


class SummaryFeedResponse(BaseModel):
    """Wrapper for GET /summaries — list of cards + total count."""
    summaries: list[SummaryCardResponse]
    total: int
