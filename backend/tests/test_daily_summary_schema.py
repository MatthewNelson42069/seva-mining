"""Schema validation tests — Phase 1, Plan 01 + Phase 2, Plan 01 extensions.

Pitfall HIGH-4: raw_sources_jsonb has no DB-level shape enforcement.
RawSources Pydantic model must reject malformed data on write.
"""
import pytest
from pydantic import ValidationError

from app.schemas.daily_summary import (
    GoldNewsSource,
    LastKnownLaw,
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


# ---------------------------------------------------------------------------
# Phase 2, Plan 01 — LastKnownLaw schema tests
# ---------------------------------------------------------------------------


def test_last_known_law_construction():
    """LastKnownLaw constructs cleanly with all 3 required string fields."""
    lkl = LastKnownLaw(
        date="2026-04-15",
        law_name="Bill 71 (Building Ontario Act)",
        url="https://www.ontario.ca/laws/bill/b71",
    )
    assert lkl.date == "2026-04-15"
    assert lkl.law_name == "Bill 71 (Building Ontario Act)"
    assert lkl.url == "https://www.ontario.ca/laws/bill/b71"


def test_last_known_law_round_trip():
    """LastKnownLaw round-trips via model_dump_json() → model_validate_json()."""
    original = LastKnownLaw(
        date="2026-04-15",
        law_name="Bill 71 (Building Ontario Act)",
        url="https://www.ontario.ca/laws/bill/b71",
    )
    restored = LastKnownLaw.model_validate_json(original.model_dump_json())
    assert restored == original


def test_ontario_law_state_accepts_last_known_law_or_none():
    """OntarioLawState.last_known_law accepts both None and a populated LastKnownLaw."""
    state_none = OntarioLawState(hits=[], last_known_law=None)
    assert state_none.last_known_law is None

    lkl = LastKnownLaw(
        date="2026-04-15",
        law_name="Bill 71 (Building Ontario Act)",
        url="https://www.ontario.ca/laws/bill/b71",
    )
    state_with = OntarioLawState(hits=[], last_known_law=lkl)
    assert state_with.last_known_law is not None
    assert state_with.last_known_law.law_name == "Bill 71 (Building Ontario Act)"


def test_ontario_law_state_last_known_law_is_last_known_law_type():
    """OntarioLawState.last_known_law annotation is LastKnownLaw | None (not OntarioLawHit)."""
    # Verify that a LastKnownLaw instance is accepted and stored correctly
    lkl = LastKnownLaw(date="2026-04-15", law_name="Bill X", url="https://x.com")
    state = OntarioLawState(last_known_law=lkl)
    assert isinstance(state.last_known_law, LastKnownLaw)
    # Verify the field name matches the Phase 2 annotation
    assert "last_known_law" in OntarioLawState.model_fields
