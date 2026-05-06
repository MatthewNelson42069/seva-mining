"""Schema validation tests — Phase 1, Plan 01.

Pitfall HIGH-4: raw_sources_jsonb has no DB-level shape enforcement.
RawSources Pydantic model must reject malformed data on write.
"""
import pytest
from pydantic import ValidationError

from app.schemas.daily_summary import (
    GoldNewsSource,
    OntarioLawState,
    OntarioStatsState,
    RawSources,
    SummaryCardResponse,
)


def test_rawsources_default_construction():
    rs = RawSources()
    assert rs.gold_news == []
    assert rs.ontario_law.hits == []
    assert rs.ontario_law.last_known_law is None
    assert rs.ontario_stats.snapshot_date == ""


def test_rawsources_full_construction():
    rs = RawSources(
        gold_news=[
            GoldNewsSource(
                title="t", link="https://x.com",
                source_name="kitco.com", score=8.5,
            )
        ],
        ontario_law=OntarioLawState(),
        ontario_stats=OntarioStatsState(snapshot_date="2026-04"),
    )
    assert len(rs.gold_news) == 1
    assert rs.gold_news[0].score == 8.5
    assert rs.ontario_stats.snapshot_date == "2026-04"


def test_goldnewssource_score_above_10_rejected():
    with pytest.raises(ValidationError):
        GoldNewsSource(title="t", link="x", source_name="s", score=11.0)


def test_goldnewssource_score_below_zero_rejected():
    with pytest.raises(ValidationError):
        GoldNewsSource(title="t", link="x", source_name="s", score=-1.0)


def test_rawsources_wrong_type_rejected():
    with pytest.raises(ValidationError):
        RawSources(gold_news="not-a-list")


def test_rawsources_round_trip():
    """Writer-reader contract: model_dump() must round-trip via model_validate()."""
    original = RawSources(
        gold_news=[
            GoldNewsSource(title="t", link="x", source_name="s", score=7.0)
        ],
    )
    dumped = original.model_dump(mode="json")
    restored = RawSources.model_validate(dumped)
    assert restored.gold_news[0].score == 7.0


def test_summary_card_response_omits_raw_sources():
    """raw_sources_jsonb is intentionally NOT in the API response schema."""
    assert "raw_sources_jsonb" not in SummaryCardResponse.model_fields
