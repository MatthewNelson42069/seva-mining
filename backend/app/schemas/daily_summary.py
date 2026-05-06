"""Pydantic schemas for daily_summaries — Phase 1, Plan 01.

Includes:
- RawSources: typed model gating raw_sources_jsonb writes (Pitfall HIGH-4 mitigation)
- SummaryCardResponse: API response shape (raw_sources_jsonb omitted)
- SummaryFeedResponse: list wrapper for GET /summaries
"""
import uuid
from datetime import datetime

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
    published_at: datetime | None = None


class OntarioLawState(BaseModel):
    """Ontario law section state — hits + continuity pointer."""
    hits: list[OntarioLawHit] = Field(default_factory=list)
    last_known_law: OntarioLawHit | None = None


class OntarioStatsState(BaseModel):
    """Ontario stats section state — snapshot + last known figure."""
    snapshot_date: str = ""  # YYYY-MM
    last_known_figure: float | None = None
    fresh_data: dict | None = None


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
