"""Schema validation tests — Phase 1, Plan 01 + Phase 2, Plan 01 extensions + Phase 3.

Pitfall HIGH-4: raw_sources_jsonb has no DB-level shape enforcement.
RawSources Pydantic model must reject malformed data on write.
"""
import pytest
from pydantic import ValidationError

from app.schemas.daily_summary import (
    GoldNewsSource,
    LastKnownLaw,
    OntarioLawState,
    OntarioStatsSnapshot,
    OntarioStatsState,
    RawSources,
    SummaryCardResponse,
)


def test_rawsources_default_construction():
    rs = RawSources()
    assert rs.gold_news == []
    assert rs.ontario_law.hits == []
    assert rs.ontario_law.last_known_law is None
    # Phase 3: new OntarioStatsState shape — snapshot/last_state/last_error_text all None by default
    assert rs.ontario_stats.snapshot is None
    assert rs.ontario_stats.last_state is None
    assert rs.ontario_stats.last_error_text is None


def test_rawsources_full_construction():
    rs = RawSources(
        gold_news=[
            GoldNewsSource(
                title="t", link="https://x.com",
                source_name="kitco.com", score=8.5,
            )
        ],
        ontario_law=OntarioLawState(),
        ontario_stats=OntarioStatsState(last_state="no_new_data"),
    )
    assert len(rs.gold_news) == 1
    assert rs.gold_news[0].score == 8.5
    assert rs.ontario_stats.last_state == "no_new_data"


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


# ---------------------------------------------------------------------------
# Phase 3, Plan 01 — OntarioStatsSnapshot + new OntarioStatsState tests
# ---------------------------------------------------------------------------


def test_ontario_stats_snapshot_construction_required_fields():
    """Test 1: OntarioStatsSnapshot constructs with required fields only."""
    snap = OntarioStatsSnapshot(
        period="2026-02",
        figure_kg=7359.0,
        release_time="2026-04-20T08:30",
    )
    assert snap.period == "2026-02"
    assert snap.figure_kg == 7359.0
    assert snap.release_time == "2026-04-20T08:30"
    assert snap.prior_period is None
    assert snap.prior_figure_kg is None


def test_ontario_stats_snapshot_round_trip():
    """Test 2: OntarioStatsSnapshot round-trips via model_dump() — JSON-safe primitives."""
    snap = OntarioStatsSnapshot(
        period="2026-02",
        figure_kg=7359.0,
        release_time="2026-04-20T08:30",
        prior_period="2026-01",
        prior_figure_kg=7559.0,
    )
    dumped = snap.model_dump(mode="json")
    assert isinstance(dumped["period"], str)
    assert isinstance(dumped["figure_kg"], float)
    assert isinstance(dumped["release_time"], str)
    assert isinstance(dumped["prior_period"], str)
    assert isinstance(dumped["prior_figure_kg"], float)
    # No datetime objects — all JSON-safe primitives
    restored = OntarioStatsSnapshot.model_validate(dumped)
    assert restored.figure_kg == 7359.0
    assert restored.prior_period == "2026-01"


def test_ontario_stats_state_default_all_none():
    """Test 3: OntarioStatsState() constructs with all defaults None."""
    state = OntarioStatsState()
    assert state.snapshot is None
    assert state.last_state is None
    assert state.last_error_text is None


def test_ontario_stats_state_accepts_fresh_literal():
    """Test 4: OntarioStatsState(last_state='fresh', snapshot=...) accepted."""
    snap = OntarioStatsSnapshot(
        period="2026-02",
        figure_kg=7359.0,
        release_time="2026-04-20T08:30",
    )
    state = OntarioStatsState(last_state="fresh", snapshot=snap)
    assert state.last_state == "fresh"
    assert state.snapshot is not None
    assert state.snapshot.period == "2026-02"


def test_ontario_stats_state_rejects_invalid_last_state():
    """Test 5: OntarioStatsState(last_state='invalid') raises ValidationError."""
    with pytest.raises(ValidationError):
        OntarioStatsState(last_state="invalid")


def test_ontario_stats_state_round_trip_via_raw_sources():
    """Test 6: RawSources(ontario_stats=OntarioStatsState(...)) round-trips via JSON."""
    snap = OntarioStatsSnapshot(
        period="2026-02",
        figure_kg=7359.0,
        release_time="2026-04-20T08:30",
        prior_period="2026-01",
        prior_figure_kg=7559.0,
    )
    rs = RawSources(
        ontario_stats=OntarioStatsState(
            snapshot=snap,
            last_state="fresh",
            last_error_text=None,
        )
    )
    restored = RawSources.model_validate_json(rs.model_dump_json())
    assert restored.ontario_stats.last_state == "fresh"
    assert restored.ontario_stats.snapshot is not None
    assert restored.ontario_stats.snapshot.figure_kg == 7359.0


def test_ontario_stats_old_fields_removed():
    """Test 7: Phase 1 fields (snapshot_date, last_known_figure, fresh_data) are GONE."""
    state = OntarioStatsState()
    assert not hasattr(state, "snapshot_date"), "snapshot_date should be removed in Phase 3"
    assert not hasattr(state, "last_known_figure"), "last_known_figure should be removed in Phase 3"
    assert not hasattr(state, "fresh_data"), "fresh_data should be removed in Phase 3"
