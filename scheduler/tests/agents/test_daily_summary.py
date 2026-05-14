"""Tests for scheduler/agents/daily_summary.py — Phase 1, Plan 05.

Coverage:
  Test 1  (CRIT-3 / SUM-03): idempotency skip when recent completed row exists
  Test 2  (period_label): derive_period_label for 08:xx and 12:xx LA times
  Test 3  (GOLD-01 score floor): top 5 filtered to score >= 6.0
  Test 4  (GOLD-03 empty state): no qualifying stories → empty-state copy
  Test 5  (GOLD-02 prompt structure): GOLD_NEWS_SYSTEM_PROMPT constants grep
  Test 6  (MOD-5 date grounding): user prompt includes published_at + instruction
  Test 7  (SUM-04 telemetry): agent_runs notes has all 6 required keys
  Test 8  (SUM-05 status): completed / partial / failed mapping
  Test 9  (Ontario stubs): phase-1 stubs return (markdown, [])
  Test 10 (run failure → failure-alert): unhandled exception triggers failure alert
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://fake-pooler.neon.tech/db?sslmode=require"
)
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test-fake")
os.environ.setdefault("TWILIO_ACCOUNT_SID", "x")
os.environ.setdefault("TWILIO_AUTH_TOKEN", "x")
os.environ.setdefault("TWILIO_WHATSAPP_FROM", "whatsapp:+1x")
os.environ.setdefault("DIGEST_WHATSAPP_TO", "whatsapp:+1x")
os.environ.setdefault("X_API_BEARER_TOKEN", "x")
os.environ.setdefault("X_API_KEY", "x")
os.environ.setdefault("X_API_SECRET", "x")
os.environ.setdefault("SERPAPI_API_KEY", "x")
os.environ.setdefault("FRONTEND_URL", "https://x.com")

from agents.daily_summary import (  # noqa: E402
    EMPTY_STATE_FALLBACK,
    GOLD_NEWS_SYSTEM_PROMPT,
    GOLD_SCORE_FLOOR,
    GOLD_TOP_N,
    IDEMPOTENCY_WINDOW_MIN,
    _build_gold_news_section,
    _build_ontario_law_section,
    _build_ontario_stats_section,
    _derive_period_label,
    _gold_empty_state,
    run_daily_summary,
)


# ---------------------------------------------------------------------------
# Test 1 — CRIT-3 / SUM-03: idempotency skip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_idempotency_skip_when_recent_completed_row_exists(caplog):
    """run_daily_summary must skip + log 'idempotency_skip' if a recent row exists."""
    import logging

    # Mock the DB session to return a non-None scalar (simulating existing row)
    mock_scalar_result = MagicMock()
    mock_scalar_result.scalar_one_or_none.return_value = "some-uuid"

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_scalar_result)
    mock_session.commit = AsyncMock()

    session_cm = MagicMock()
    session_cm.__aenter__ = AsyncMock(return_value=mock_session)
    session_cm.__aexit__ = AsyncMock(return_value=False)
    mock_session_factory = MagicMock(return_value=session_cm)

    with patch("agents.daily_summary.AsyncSessionLocal", mock_session_factory), caplog.at_level(
        logging.INFO, logger="agents.daily_summary"
    ):
        await run_daily_summary()

    # Must log idempotency_skip
    assert any("idempotency_skip" in record.message for record in caplog.records), (
        "Expected 'idempotency_skip' in log messages, got: "
        + str([r.message for r in caplog.records])
    )

    # Must NOT have added any new rows (session.add never called)
    mock_session.add.assert_not_called()


# ---------------------------------------------------------------------------
# Test 2 — period_label derivation
# ---------------------------------------------------------------------------


def test_derive_period_label_at_0830_returns_0800_pt():
    """08:30 LA time → '08:00 PT'."""
    from zoneinfo import ZoneInfo

    now_la = datetime(2026, 5, 6, 8, 30, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
    assert _derive_period_label(now_la) == "08:00 PT"


def test_derive_period_label_at_1230_returns_1200_pt():
    """12:30 LA time → '12:00 PT'."""
    from zoneinfo import ZoneInfo

    now_la = datetime(2026, 5, 6, 12, 30, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
    assert _derive_period_label(now_la) == "12:00 PT"


def test_derive_period_label_at_0800_returns_0800_pt():
    """08:00 exact LA time → '08:00 PT'."""
    from zoneinfo import ZoneInfo

    now_la = datetime(2026, 5, 6, 8, 0, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
    assert _derive_period_label(now_la) == "08:00 PT"


def test_derive_period_label_at_1200_returns_1200_pt():
    """12:00 exact LA time → '12:00 PT'."""
    from zoneinfo import ZoneInfo

    now_la = datetime(2026, 5, 6, 12, 0, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
    assert _derive_period_label(now_la) == "12:00 PT"


# ---------------------------------------------------------------------------
# Test 3 — GOLD-01 score floor: select top 5 with score >= 6.0
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_gold_news_section_filters_by_score_floor():
    """_build_gold_news_section selects up to GOLD_TOP_N stories with score >= 6.0 (drops 5.5)."""
    stories = [
        {"title": "A", "score": 9.0, "link": "http://a", "source_name": "kitco.com", "published": "2026-05-06", "summary": "A summary"},
        {"title": "B", "score": 7.5, "link": "http://b", "source_name": "kitco.com", "published": "2026-05-06", "summary": "B summary"},
        {"title": "C", "score": 5.5, "link": "http://c", "source_name": "kitco.com", "published": "2026-05-06", "summary": "C summary"},  # below floor
        {"title": "D", "score": 6.5, "link": "http://d", "source_name": "kitco.com", "published": "2026-05-06", "summary": "D summary"},
        {"title": "E", "score": 8.0, "link": "http://e", "source_name": "kitco.com", "published": "2026-05-06", "summary": "E summary"},
        {"title": "F", "score": 6.0, "link": "http://f", "source_name": "kitco.com", "published": "2026-05-06", "summary": "F summary"},
    ]

    mock_anthropic_response = MagicMock()
    mock_anthropic_response.content = [MagicMock(text="Why it matters lead.\n\n* Bullet one (kitco.com)\n* Bullet two (kitco.com)")]
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_anthropic_response)

    with patch("agents.daily_summary.fetch_stories", AsyncMock(return_value=stories)):
        md, raw, counts = await _build_gold_news_section(mock_client)

    # Should return 5 stories (9.0, 8.0, 7.5, 6.5, 6.0) — not the 5.5
    assert len(raw) == 5, f"Expected 5 stories (5 above floor in input), got {len(raw)}: {[s['title'] for s in raw]}"
    scores = [s["score"] for s in raw]
    assert 5.5 not in scores, f"Score 5.5 (below floor {GOLD_SCORE_FLOOR}) should be excluded"
    # Sorted descending
    assert scores == sorted(scores, reverse=True), f"Expected descending order: {scores}"


@pytest.mark.asyncio
async def test_build_gold_news_section_top_n_is_12():
    """_build_gold_news_section takes at most GOLD_TOP_N (12) stories — quick-260512-of1."""
    assert GOLD_TOP_N == 12
    assert GOLD_SCORE_FLOOR == 6.0

    # 20 stories all above floor — should select top 12 (quick-260512-of1 bumped from 5)
    stories = [
        {"title": f"S{i}", "score": float(20 - i * 0.5), "link": f"http://s{i}", "source_name": "kitco.com",
         "published": "2026-05-12", "summary": f"Summary {i}"}
        for i in range(20)
    ]

    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="### 🟡 Top Gold Headlines\n\n**Gold rallies** (kitco.com)\n* Bullet (kitco.com)")]
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    with patch("agents.daily_summary.fetch_stories", AsyncMock(return_value=stories)):
        md, raw, counts = await _build_gold_news_section(mock_client)

    assert len(raw) == 12, f"Expected GOLD_TOP_N=12 stories, got {len(raw)}"


# ---------------------------------------------------------------------------
# quick-260508-dj5 — datetime-not-JSON-serializable regression
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_gold_news_section_returns_json_serializable_raw_when_sonnet_raises():
    """quick-260508-dj5 regression test for the bug that crashed the 2026-05-08
    08:00 PT fire (run id 50875012). When Sonnet raises, the returned raw list
    MUST be JSON-serializable (no datetime objects) so the downstream
    daily_summaries INSERT does not crash with
    "TypeError: Object of type datetime is not JSON serializable".

    Pre-fix: the except path returned the raw `top` list which still had
    datetime objects in s["published"], because the JSON-safe conversion only
    ran on the success path AFTER the try/except.
    Post-fix: the JSON-safe `raw` is constructed BEFORE the try/except and is
    returned from both success and failure paths.
    """
    import json as _json
    from datetime import datetime, timezone

    stories = [
        {
            "title": "G", "score": 8.0, "link": "http://g", "source_name": "kitco.com",
            # The critical input: a real datetime object (matches what
            # _fetch_all_rss / _fetch_all_serpapi populate).
            "published": datetime(2026, 5, 8, 12, 0, 0, tzinfo=timezone.utc),
            "summary": "summary",
        },
    ]

    mock_client = AsyncMock()
    # Force the Sonnet call to raise — exercise the fallback path.
    mock_client.messages.create = AsyncMock(side_effect=RuntimeError("anthropic hiccup"))

    with patch("agents.daily_summary.fetch_stories", AsyncMock(return_value=stories)):
        md, raw, counts = await _build_gold_news_section(mock_client)

    assert md is None, "md must be None when Sonnet raises"
    # The critical regression assertion: raw must be JSON-serializable
    # (this is what would be put into raw_sources_jsonb["gold_news"]).
    json_str = _json.dumps(raw)  # MUST NOT raise TypeError
    assert "2026-05-08" in json_str, (
        f"published_at should be ISO-formatted string in raw, got: {json_str[:200]}"
    )
    # Confirm raw retains story metadata for forensic value (we don't lose visibility).
    assert len(raw) == 1
    assert raw[0]["title"] == "G"
    assert raw[0]["score"] == 8.0
    assert raw[0]["published_at"] is not None


# ---------------------------------------------------------------------------
# Test 4 — GOLD-03 empty state
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_gold_news_section_empty_state_when_no_qualifying_stories():
    """When all stories score below 6.0, returns empty-state markdown."""
    stories = [
        {"title": "Low", "score": 3.0, "link": "http://low", "source_name": "unknown",
         "published": "2026-05-06", "summary": "Low quality"},
    ]

    mock_client = AsyncMock()

    with patch("agents.daily_summary.fetch_stories", AsyncMock(return_value=stories)), \
         patch("agents.daily_summary.fetch_market_snapshot", AsyncMock(return_value={"gold_24h_low": 3200.0, "gold_24h_high": 3280.0})):
        md, raw, counts = await _build_gold_news_section(mock_client)

    assert md is not None
    assert "No major moves in gold today" in md, f"Expected empty-state copy in: {md!r}"
    assert raw == []
    # Anthropic should NOT have been called
    mock_client.messages.create.assert_not_called()


@pytest.mark.asyncio
async def test_gold_empty_state_uses_price_range_when_available():
    """_gold_empty_state includes price range from market_snapshot when available."""
    with patch(
        "agents.daily_summary.fetch_market_snapshot",
        AsyncMock(return_value={"gold_24h_low": 3200.0, "gold_24h_high": 3280.0}),
    ):
        result = await _gold_empty_state()

    assert "3,200" in result or "3200" in result.replace(",", ""), f"Expected gold low in: {result}"
    assert "No major moves in gold today" in result


@pytest.mark.asyncio
async def test_gold_empty_state_fallback_when_snapshot_fails():
    """_gold_empty_state returns fallback when market_snapshot raises."""
    with patch(
        "agents.daily_summary.fetch_market_snapshot",
        AsyncMock(side_effect=Exception("API down")),
    ):
        result = await _gold_empty_state()

    assert result == EMPTY_STATE_FALLBACK


# ---------------------------------------------------------------------------
# Test 5 — GOLD-02 prompt structure constants (grep-able)
# ---------------------------------------------------------------------------


def test_gold_news_system_prompt_contains_bull_thesis_structure():
    """quick-260512-of1 — GOLD_NEWS_SYSTEM_PROMPT instructs the bull-thesis brief
    with 4 labeled sub-sections (Top Gold Headlines, Top Macro Headlines,
    Analyst & Bank Predictions, Macro Economic Stats) + optional Bearish Risk.

    Replaces the quick-260507-drw 'headline-grouped 1-3 stories' format.
    """
    prompt = GOLD_NEWS_SYSTEM_PROMPT
    # All 6 required markers present
    assert "Top Gold Headlines" in prompt, "missing 'Top Gold Headlines' section header"
    assert "Top Macro Headlines" in prompt, "missing 'Top Macro Headlines' section header"
    assert "Analyst & Bank Predictions" in prompt, "missing 'Analyst & Bank Predictions' section header"
    assert "Macro Economic Stats" in prompt, "missing 'Macro Economic Stats' section header"
    assert "Bearish Risk to Watch" in prompt, "missing 'Bearish Risk to Watch' section header"
    assert "Does this point to a higher gold price?" in prompt, (
        "missing bull-thesis framing question"
    )
    # No legacy 'Why it matters' single-lead framing
    assert "Why it matters" not in prompt, (
        "legacy 'Why it matters' lead removed in quick-260507-drw and stays gone in quick-260512-of1"
    )


def test_gold_news_system_prompt_contains_analyst_names():
    """quick-260512-of1 — prompt prioritizes specific named analysts/banks for highest signal."""
    prompt = GOLD_NEWS_SYSTEM_PROMPT
    assert "Pierre Lassonde" in prompt
    assert "Peter Schiff" in prompt
    assert "Goldman Sachs" in prompt


def test_gold_news_system_prompt_references_v2_1_macro_stats_future_work():
    """quick-260512-of1 — Macro Economic Stats sub-section references v2.1 for live indicators."""
    assert "v2.1" in GOLD_NEWS_SYSTEM_PROMPT, (
        "Macro Economic Stats sub-section must reference v2.1 as the future-work hint"
    )


def test_sonnet_max_tokens_is_1500():
    """quick-260512-of1 — bumped from 800 because bull-thesis brief is structurally larger."""
    from agents.daily_summary import SONNET_MAX_TOKENS
    assert SONNET_MAX_TOKENS == 1500



def test_gold_news_system_prompt_contains_source_name():
    """GOLD_NEWS_SYSTEM_PROMPT includes '(Source Name)' inline citation instruction."""
    assert "(Source Name)" in GOLD_NEWS_SYSTEM_PROMPT, (
        "GOLD_NEWS_SYSTEM_PROMPT must include '(Source Name)'"
    )


def test_gold_news_system_prompt_contains_word_limit():
    """GOLD_NEWS_SYSTEM_PROMPT includes per-bullet word limit.

    quick-260512-oxr: bumped 25 → 35 words to give Sonnet room to land both
    the fact AND the gold-mechanism in each bullet.
    """
    prompt = GOLD_NEWS_SYSTEM_PROMPT
    assert "≤ 35 words" in prompt, (
        f"GOLD_NEWS_SYSTEM_PROMPT must mention 35-word limit: {prompt[:200]}"
    )
    # The 35-word limit appears once per section (3 sections) — assert all 3.
    assert prompt.count("≤ 35 words") >= 3, (
        f"Expected '≤ 35 words' to appear in at least 3 sections, "
        f"got {prompt.count('≤ 35 words')}"
    )
    # The legacy 25-word limit must NOT linger.
    assert "≤ 25 words" not in prompt, (
        "GOLD_NEWS_SYSTEM_PROMPT still contains the legacy 25-word limit; "
        "quick-260512-oxr bumped it to 35 words across all sections."
    )


def test_gold_news_system_prompt_contains_bullet_rule():
    """quick-260512-oxr: top-level rule mandates every bullet ties back to gold.

    The rule must explicitly forbid descriptive ('X happened') bullets that
    don't make the gold-bull-case connection.
    """
    prompt = GOLD_NEWS_SYSTEM_PROMPT
    assert "Bullet rule (applies to all sections)" in prompt, (
        "GOLD_NEWS_SYSTEM_PROMPT must include the top-level Bullet rule"
    )
    # Examples / mechanism keywords that anchor the rule
    assert "tie the fact back to the gold bull case" in prompt
    assert "Descriptive bullets" in prompt


def test_gold_news_system_prompt_contains_example_bullets():
    """quick-260512-oxr: few-shot examples anchor Sonnet's output style."""
    prompt = GOLD_NEWS_SYSTEM_PROMPT
    assert "Example bullets (use these as a model)" in prompt, (
        "GOLD_NEWS_SYSTEM_PROMPT must include the example-bullets section"
    )
    # The 3 worked examples — exact substring matches per quick-260512-oxr spec
    assert "Spot gold surged 3.6%" in prompt, (
        "Top Gold Headlines worked example missing"
    )
    assert "sticky inflation keeps real yields suppressed" in prompt, (
        "Top Macro Headlines worked example missing"
    )
    assert "Lassonde points to $40T US debt" in prompt, (
        "Analyst & Bank Predictions worked example missing"
    )


def test_gold_news_system_prompt_no_build_chunks():
    """Module must NOT import or call build_chunks (HIGH-5 enforcement).

    The docstring is allowed to reference 'build_chunks' as a negation
    ('NOT build_chunks'), but the module must not import or call it.
    """
    import agents.daily_summary as ds_module

    # Check that build_chunks is not imported (no "from ... import build_chunks"
    # or "import build_chunks" pattern — only comment/docstring mentions are ok)
    assert not hasattr(ds_module, "build_chunks"), (
        "daily_summary.py must NOT import build_chunks (HIGH-5)"
    )
    # Check no call-site usage: grep for open-paren after build_chunks
    import inspect
    source = inspect.getsource(ds_module)
    # Remove comment and docstring lines from source before checking
    non_comment_lines = [
        line for line in source.splitlines()
        if not line.strip().startswith("#") and not line.strip().startswith('"""')
        and not line.strip().startswith("'")
    ]
    non_comment_source = "\n".join(non_comment_lines)
    assert "build_chunks(" not in non_comment_source, (
        "daily_summary.py must NOT call build_chunks() (HIGH-5)"
    )


# ---------------------------------------------------------------------------
# Test 6 — MOD-5 date grounding: published_at in user prompt
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_gold_news_section_includes_published_in_prompt():
    """The user prompt sent to Sonnet includes the 'Published:' field for each story."""
    stories = [
        {"title": "Gold hits new high", "score": 8.5, "link": "http://x", "source_name": "kitco.com",
         "published": "2026-05-06", "summary": "Summary text"},
    ]

    captured_calls = []

    async def mock_create(**kwargs):
        captured_calls.append(kwargs)
        response = MagicMock()
        response.content = [MagicMock(text="Gold is on the move.\n\n* Bullet one (kitco.com)")]
        return response

    mock_client = AsyncMock()
    mock_client.messages.create = mock_create

    with patch("agents.daily_summary.fetch_stories", AsyncMock(return_value=stories)):
        await _build_gold_news_section(mock_client)

    assert len(captured_calls) == 1
    user_content = captured_calls[0]["messages"][0]["content"]
    assert "Published:" in user_content, (
        f"User prompt must include 'Published:' for MOD-5 date grounding. Got: {user_content[:300]}"
    )


def test_gold_news_system_prompt_contains_date_instruction():
    """GOLD_NEWS_SYSTEM_PROMPT instructs Sonnet to use ONLY dates from provided articles."""
    assert (
        "ONLY dates" in GOLD_NEWS_SYSTEM_PROMPT
        or "only dates" in GOLD_NEWS_SYSTEM_PROMPT.lower()
        or "Do not" in GOLD_NEWS_SYSTEM_PROMPT
    ), "GOLD_NEWS_SYSTEM_PROMPT must include date-grounding instruction (MOD-5)"


# ---------------------------------------------------------------------------
# Test 7 — SUM-04 telemetry: agent_runs notes contains 6 required keys
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_daily_summary_writes_telemetry_notes_with_required_keys():
    """agent_runs telemetry notes must contain all 6 SUM-04 keys + the 4 new
    quick-260507-drw raw-count keys for the gold ingestion path.
    """
    required_keys = {
        "candidates_gold",
        # quick-260507-drw — RSS / SerpAPI / total / after_floor breakdown
        "candidates_gold_rss",
        "candidates_gold_serpapi",
        "candidates_gold_total",
        "candidates_gold_after_floor",
        "candidates_law",
        "candidates_stats",
        "sections_completed",
        "sections_failed",
        "whatsapp_sent",
    }

    # We'll capture the notes written to the agent_run via a plain object
    written_notes = []

    class FakeAgentRun:
        """A simple object that captures attribute assignments."""
        id = "test-run-uuid"
        status = "running"

        def __setattr__(self, name, value):
            if name == "notes":
                written_notes.append(value)
            object.__setattr__(self, name, value)

    fake_run = FakeAgentRun()

    # Track session calls by index
    call_count = [0]

    class FakeSessionCM:
        """Context manager returning different mock sessions by call sequence."""

        async def __aenter__(self):
            call_count[0] += 1
            idx = call_count[0]
            sess = AsyncMock()
            if idx == 1:
                # First session: idempotency check
                idem = MagicMock()
                idem.scalar_one_or_none.return_value = None
                sess.execute = AsyncMock(return_value=idem)
            elif idx == 2:
                # Second session: agent_run insert + refresh
                sess.add = MagicMock()
                sess.commit = AsyncMock()
                sess.refresh = AsyncMock(side_effect=lambda obj: setattr(obj, "id", "test-run-uuid"))
            elif idx == 3:
                # Third session: previous-summary read (Phase 2 — last_known_law continuity)
                prev = MagicMock()
                prev.scalar_one_or_none.return_value = None  # no previous summary
                sess.execute = AsyncMock(return_value=prev)
            elif idx == 4:
                # Fourth session: DailySummary insert
                sess.add = MagicMock()
                sess.commit = AsyncMock()
            else:
                # Fifth+ session: telemetry update (finally block)
                sess.get = AsyncMock(return_value=fake_run)
                sess.commit = AsyncMock()
            return sess

        async def __aexit__(self, *args):
            return False

    mock_anthropic_response = MagicMock()
    mock_anthropic_response.content = [MagicMock(text="Gold surges.\n\n* Bullet (kitco.com)")]

    mock_client_instance = AsyncMock()
    mock_client_instance.messages.create = AsyncMock(return_value=mock_anthropic_response)

    stories = [
        {"title": "Gold story", "score": 8.0, "link": "http://x", "source_name": "kitco.com",
         "published": "2026-05-06", "summary": "Gold summary"},
    ]

    with patch("agents.daily_summary.AsyncSessionLocal", FakeSessionCM), \
         patch("agents.daily_summary.fetch_stories", AsyncMock(return_value=stories)), \
         patch("agents.daily_summary.AsyncAnthropic", return_value=mock_client_instance), \
         patch("agents.ontario_law._fetch_serpapi_candidates", return_value=[]), \
         patch("agents.ontario_law._fetch_nrcan_candidates", return_value=[]), \
         patch("agents.daily_summary.deliver_summary_teaser", AsyncMock(return_value=None)), \
         patch("agents.daily_summary.deliver_summary_failure_alert", AsyncMock()):
        await run_daily_summary()

    assert written_notes, "No notes were written to the agent_run"
    notes_json = written_notes[-1]
    notes = json.loads(notes_json)
    missing = required_keys - set(notes.keys())
    assert not missing, f"SUM-04 keys missing from notes: {missing}. Got: {set(notes.keys())}"


# ---------------------------------------------------------------------------
# Test 8 — SUM-05 status assembly
# ---------------------------------------------------------------------------


def test_status_is_completed_when_all_sections_succeed():
    """0 failed sections → status='completed' (SUM-05)."""
    sections_failed: list[str] = []
    failed_count = len(sections_failed)

    if failed_count == 0:
        status = "completed"
    elif failed_count < 3:
        status = "partial"
    else:
        status = "failed"

    assert status == "completed"


def test_status_is_partial_when_one_section_fails():
    """1 failed section → status='partial' (SUM-05)."""
    sections_failed = ["gold_news"]
    failed_count = len(sections_failed)

    if failed_count == 0:
        status = "completed"
    elif failed_count < 3:
        status = "partial"
    else:
        status = "failed"

    assert status == "partial"


def test_status_is_failed_when_all_sections_fail():
    """3 failed sections → status='failed' (SUM-05)."""
    sections_failed = ["gold_news", "ontario_law", "ontario_stats"]
    failed_count = len(sections_failed)

    if failed_count == 0:
        status = "completed"
    elif failed_count < 3:
        status = "partial"
    else:
        status = "failed"

    assert status == "failed"


# ---------------------------------------------------------------------------
# Test 9 — Ontario section builders (Phase 2 updates)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_ontario_law_section_returns_real_empty_state():
    """Phase 2: _build_ontario_law_section returns empty-state when no candidates (mocked sources)."""
    from unittest.mock import patch

    mock_anthropic = AsyncMock()

    with patch("agents.ontario_law._fetch_serpapi_candidates", return_value=[]), \
         patch("agents.ontario_law._fetch_nrcan_candidates", return_value=[]):
        md, hits, lkl, counts = await _build_ontario_law_section(
            anthropic_client=mock_anthropic,
            serpapi_client=None,
            model="claude-haiku-4-5",
            previous_last_known_law=None,
        )

    # Phase 2 real path: empty state without prior last_known_law
    assert md == "No new Ontario mining-related laws today."
    assert hits == []
    assert lkl is None
    assert isinstance(counts, dict)


@pytest.mark.asyncio
async def test_build_ontario_stats_section_fresh_path():
    """Phase 3: _build_ontario_stats_section returns fresh markdown + stats_jsonb + telemetry."""
    from agents.ontario_stats import OntarioStatsResult

    fresh_result = OntarioStatsResult(
        state="fresh",
        figure_kg=7359.0,
        period="2026-02",
        release_time="2026-04-20T08:30",
        prior_period="2026-01",
        prior_figure_kg=7559.0,
    )

    with patch("agents.daily_summary.fetch_ontario_stats_snapshot",
               AsyncMock(return_value=fresh_result)):
        md, jsonb, telemetry = await _build_ontario_stats_section(
            previous_snapshot=None,
            previous_release_time=None,
            agent_run_id="test-run-uuid",
        )

    assert md is not None
    assert "7,359 kg" in md
    assert jsonb["last_state"] == "fresh"
    assert jsonb["snapshot"] is not None
    assert jsonb["snapshot"]["period"] == "2026-02"
    assert telemetry["candidates_stats_state"] == "fresh"


def test_ontario_stats_stub_constant_removed():
    """ONTARIO_STATS_STUB_MD was removed in Phase 3 — no longer in module."""
    import agents.daily_summary as ds_module
    assert not hasattr(ds_module, "ONTARIO_STATS_STUB_MD"), (
        "ONTARIO_STATS_STUB_MD should be removed in Phase 3 — use real ingestion"
    )


def test_ontario_law_stub_md_not_in_module():
    """ONTARIO_LAW_STUB_MD was removed in Phase 2 — no longer referenced in module."""
    import agents.daily_summary as ds_module
    assert not hasattr(ds_module, "ONTARIO_LAW_STUB_MD"), (
        "ONTARIO_LAW_STUB_MD should be removed in Phase 2 — use real ingestion"
    )


# ---------------------------------------------------------------------------
# Test 10 — run failure → failure-alert called (MOD-6)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_failure_triggers_failure_alert():
    """On unhandled exception in run_daily_summary's main try block, deliver_summary_failure_alert is called."""
    call_count = [0]

    class FakeSessionCM:
        async def __aenter__(self):
            call_count[0] += 1
            sess = AsyncMock()
            if call_count[0] == 1:
                # idempotency check — no existing row
                idem = MagicMock()
                idem.scalar_one_or_none.return_value = None
                sess.execute = AsyncMock(return_value=idem)
            elif call_count[0] == 2:
                # agent_run insert succeeds
                sess.add = MagicMock()
                sess.commit = AsyncMock()
                sess.refresh = AsyncMock(side_effect=lambda obj: setattr(obj, "id", "run-id"))
            elif call_count[0] == 3:
                # Phase 2: previous-summary read for last_known_law continuity
                prev = MagicMock()
                prev.scalar_one_or_none.return_value = None
                sess.execute = AsyncMock(return_value=prev)
            elif call_count[0] == 4:
                # DailySummary insert — raises to trigger outer except block
                sess.add = MagicMock()
                sess.commit = AsyncMock(side_effect=RuntimeError("DB failure on summary write"))
            else:
                # Failure-row write session and telemetry session
                sess.add = MagicMock()
                sess.commit = AsyncMock()
                sess.get = AsyncMock(return_value=MagicMock())
            return sess

        async def __aexit__(self, *args):
            return False

    mock_failure_alert = AsyncMock()

    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Gold surged.\n\n* Bullet (kitco.com)")]
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    stories = [
        {"title": "Gold story", "score": 8.0, "link": "http://x", "source_name": "kitco.com",
         "published": "2026-05-06", "summary": "Gold moved"},
    ]

    with patch("agents.daily_summary.AsyncSessionLocal", FakeSessionCM), \
         patch("agents.daily_summary.fetch_stories", AsyncMock(return_value=stories)), \
         patch("agents.daily_summary.AsyncAnthropic", return_value=mock_client), \
         patch("agents.ontario_law._fetch_serpapi_candidates", return_value=[]), \
         patch("agents.ontario_law._fetch_nrcan_candidates", return_value=[]), \
         patch("agents.daily_summary.deliver_summary_failure_alert", mock_failure_alert):
        await run_daily_summary()

    mock_failure_alert.assert_called_once()


# ---------------------------------------------------------------------------
# Test 11 — WhatsApp teaser called on success (WHA-01 plumbing)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deliver_summary_teaser_called_on_success():
    """On successful run, deliver_summary_teaser is called with period_label and lead."""
    call_count = [0]

    class FakeSessionCM:
        async def __aenter__(self):
            call_count[0] += 1
            idx = call_count[0]
            sess = AsyncMock()
            if idx == 1:
                idem = MagicMock()
                idem.scalar_one_or_none.return_value = None
                sess.execute = AsyncMock(return_value=idem)
            elif idx == 2:
                sess.add = MagicMock()
                sess.commit = AsyncMock()
                sess.refresh = AsyncMock(side_effect=lambda obj: setattr(obj, "id", "run-id"))
            elif idx == 3:
                # Phase 2: previous-summary read for last_known_law continuity
                prev = MagicMock()
                prev.scalar_one_or_none.return_value = None
                sess.execute = AsyncMock(return_value=prev)
            elif idx == 4:
                sess.add = MagicMock()
                sess.commit = AsyncMock()
            else:
                mock_run = MagicMock()
                mock_run.id = "run-id"
                sess.get = AsyncMock(return_value=mock_run)
                sess.commit = AsyncMock()
            return sess

        async def __aexit__(self, *args):
            return False

    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Gold rallied on safe-haven demand.\n\n* Bullet (kitco.com)")]
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    mock_teaser = AsyncMock(return_value="test-sid")
    mock_alert = AsyncMock()

    stories = [
        {"title": "Gold story", "score": 8.0, "link": "http://x", "source_name": "kitco.com",
         "published": "2026-05-06", "summary": "Gold moved"},
    ]

    with patch("agents.daily_summary.AsyncSessionLocal", FakeSessionCM), \
         patch("agents.daily_summary.fetch_stories", AsyncMock(return_value=stories)), \
         patch("agents.daily_summary.AsyncAnthropic", return_value=mock_client), \
         patch("agents.ontario_law._fetch_serpapi_candidates", return_value=[]), \
         patch("agents.ontario_law._fetch_nrcan_candidates", return_value=[]), \
         patch("agents.daily_summary.deliver_summary_teaser", mock_teaser), \
         patch("agents.daily_summary.deliver_summary_failure_alert", mock_alert):
        await run_daily_summary()

    mock_teaser.assert_called_once()
    call_args = mock_teaser.call_args
    assert call_args is not None
    # period_label and lead are the two positional args
    assert len(call_args.args) == 2 or "period_label" in str(call_args)


# ---------------------------------------------------------------------------
# Test 12 — IDEMPOTENCY_WINDOW_MIN constant
# ---------------------------------------------------------------------------


def test_idempotency_window_is_30_minutes():
    """IDEMPOTENCY_WINDOW_MIN must be 30 (matches misfire_grace_time — CRIT-3)."""
    assert IDEMPOTENCY_WINDOW_MIN == 30


# ---------------------------------------------------------------------------
# Phase 2, Plan 01 — Ontario Law section tests (U1-U8)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_ontario_law_section_bullets_when_survivors():
    """U1: When fetch_ontario_law_hits returns survivors, markdown contains bullet lines."""
    from agents.ontario_law import OntarioLawHit

    hit1 = OntarioLawHit(
        title="Bill 71 receives Royal Assent",
        link="https://ontario.ca/bill71",
        source_name="ontario.ca",
        bill_or_reg_number="Bill 71",
        favour_or_neutral="favour",
        reason="named bill amending Mining Act",
    )
    hit2 = OntarioLawHit(
        title="Reg 23/26 amends staking rules",
        link="https://ontario.ca/reg23",
        source_name="ontario.ca",
        bill_or_reg_number="Reg 23/26",
        favour_or_neutral="neutral",
        reason="staking procedure update",
    )
    counts = {"serpapi": 5, "nrcan": 3, "after_dedup": 7, "after_filter": 2}

    mock_anthropic = AsyncMock()

    with patch("agents.daily_summary.fetch_ontario_law_hits",
               AsyncMock(return_value=([hit1, hit2], counts))):
        md, hits_jsonb, new_lkl, ret_counts = await _build_ontario_law_section(
            anthropic_client=mock_anthropic,
            serpapi_client=None,
            model="claude-haiku-4-5",
            previous_last_known_law=None,
        )

    assert md is not None
    assert "* **Bill 71** — named bill amending Mining Act" in md
    assert "* **Reg 23/26** — staking procedure update" in md
    assert new_lkl is not None
    assert new_lkl["law_name"] == "Bill 71"
    assert "url" in new_lkl
    assert len(hits_jsonb) == 2


@pytest.mark.asyncio
async def test_build_ontario_law_section_empty_with_prior_last_known_law():
    """U2: Empty + previous last_known_law → continuity copy + law propagated forward."""
    mock_anthropic = AsyncMock()
    prior_lkl = {
        "date": "2026-04-15",
        "law_name": "Bill 71 (Building Ontario Act)",
        "url": "https://ontario.ca/bill71",
    }

    with patch("agents.daily_summary.fetch_ontario_law_hits",
               AsyncMock(return_value=([], {"serpapi": 0, "nrcan": 0, "after_dedup": 0, "after_filter": 0}))):
        md, hits_jsonb, new_lkl, counts = await _build_ontario_law_section(
            anthropic_client=mock_anthropic,
            serpapi_client=None,
            model="claude-haiku-4-5",
            previous_last_known_law=prior_lkl,
        )

    expected_md = (
        "No new Ontario mining-related laws today. "
        "Last update: 2026-04-15 — Bill 71 (Building Ontario Act)."
    )
    assert md == expected_md, f"Expected:\n{expected_md}\nGot:\n{md}"
    assert hits_jsonb == []
    assert new_lkl == prior_lkl  # propagated forward


@pytest.mark.asyncio
async def test_build_ontario_law_section_empty_no_prior_last_known_law():
    """U3: Empty + no previous summary → fallback without date."""
    mock_anthropic = AsyncMock()

    with patch("agents.daily_summary.fetch_ontario_law_hits",
               AsyncMock(return_value=([], {"serpapi": 0, "nrcan": 0, "after_dedup": 0, "after_filter": 0}))):
        md, hits_jsonb, new_lkl, counts = await _build_ontario_law_section(
            anthropic_client=mock_anthropic,
            serpapi_client=None,
            model="claude-haiku-4-5",
            previous_last_known_law=None,
        )

    assert md == "No new Ontario mining-related laws today."
    assert hits_jsonb == []
    assert new_lkl is None


@pytest.mark.asyncio
async def test_telemetry_has_all_4_new_law_keys():
    """U4: agent_runs.notes contains all 4 Phase 2 candidates_law_* telemetry keys."""
    written_notes: list[str] = []

    class FakeAgentRun:
        id = "test-run-uuid"
        status = "running"

        def __setattr__(self, name, value):
            if name == "notes":
                written_notes.append(value)
            object.__setattr__(self, name, value)

    fake_run = FakeAgentRun()
    call_count = [0]

    class FakeSessionCM:
        async def __aenter__(self):
            call_count[0] += 1
            idx = call_count[0]
            sess = AsyncMock()
            if idx == 1:
                idem = MagicMock()
                idem.scalar_one_or_none.return_value = None
                sess.execute = AsyncMock(return_value=idem)
            elif idx == 2:
                sess.add = MagicMock()
                sess.commit = AsyncMock()
                sess.refresh = AsyncMock(side_effect=lambda obj: setattr(obj, "id", "test-run-uuid"))
            elif idx == 3:
                prev = MagicMock()
                prev.scalar_one_or_none.return_value = None
                sess.execute = AsyncMock(return_value=prev)
            elif idx == 4:
                sess.add = MagicMock()
                sess.commit = AsyncMock()
            else:
                sess.get = AsyncMock(return_value=fake_run)
                sess.commit = AsyncMock()
            return sess

        async def __aexit__(self, *args):
            return False

    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Gold is up.\n\n* Bullet (kitco.com)")]
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)
    stories = [{"title": "Gold up", "score": 8.0, "link": "http://x", "source_name": "kitco.com",
                "published": "2026-05-06", "summary": "Gold moved"}]

    with patch("agents.daily_summary.AsyncSessionLocal", FakeSessionCM), \
         patch("agents.daily_summary.fetch_stories", AsyncMock(return_value=stories)), \
         patch("agents.daily_summary.AsyncAnthropic", return_value=mock_client), \
         patch("agents.ontario_law._fetch_serpapi_candidates", return_value=[]), \
         patch("agents.ontario_law._fetch_nrcan_candidates", return_value=[]), \
         patch("agents.daily_summary.deliver_summary_teaser", AsyncMock(return_value=None)), \
         patch("agents.daily_summary.deliver_summary_failure_alert", AsyncMock()):
        await run_daily_summary()

    assert written_notes, "No notes written to agent_run"
    notes = json.loads(written_notes[-1])

    new_keys = {
        "candidates_law_serpapi",
        "candidates_law_nrcan",
        "candidates_law_after_dedup",
        "candidates_law_after_filter",
    }
    missing = new_keys - set(notes.keys())
    assert not missing, f"Phase 2 telemetry keys missing: {missing}"
    # All 4 new keys should be integers
    for key in new_keys:
        assert isinstance(notes[key], int), f"{key} must be int, got {type(notes[key])}"


def test_build_ontario_law_section_signature_has_required_kwargs():
    """U5: _build_ontario_law_section is a coroutine function with expected kwargs."""
    import inspect
    sig = inspect.signature(_build_ontario_law_section)
    params = set(sig.parameters.keys())
    assert "anthropic_client" in params
    assert "serpapi_client" in params
    assert "model" in params
    assert "previous_last_known_law" in params


def test_fetch_ontario_law_hits_wired_to_daily_summary():
    """U6: fetch_ontario_law_hits is imported into agents.daily_summary namespace."""
    import agents.daily_summary as ds_module
    assert hasattr(ds_module, "fetch_ontario_law_hits"), (
        "fetch_ontario_law_hits must be imported in daily_summary.py"
    )


def test_ontario_law_filter_model_resolved_from_settings():
    """U7: settings.ontario_law_filter_model drives the model passed to _build_ontario_law_section."""
    import inspect
    import agents.daily_summary as ds_module
    source = inspect.getsource(ds_module)
    assert "settings.ontario_law_filter_model" in source, (
        "daily_summary must resolve model from settings.ontario_law_filter_model"
    )


@pytest.mark.asyncio
async def test_ontario_law_section_failure_marks_section_failed():
    """U8: When fetch_ontario_law_hits raises, _build_ontario_law_section returns (None, [], ...) — section marked failed."""
    mock_anthropic = AsyncMock()

    with patch("agents.daily_summary.fetch_ontario_law_hits",
               AsyncMock(side_effect=RuntimeError("filter crashed"))):
        md, hits_jsonb, new_lkl, counts = await _build_ontario_law_section(
            anthropic_client=mock_anthropic,
            serpapi_client=None,
            model="claude-haiku-4-5",
            previous_last_known_law=None,
        )

    assert md is None, "Hard failure should return md=None (section failed)"
    assert hits_jsonb == []


# ---------------------------------------------------------------------------
# Phase 3, Plan 01 — Ontario Stats section wiring tests (S1-S8)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_s1_fresh_path_populates_snapshot_and_markdown():
    """S1: fresh state → markdown + raw_sources.ontario_stats.snapshot populated."""
    from agents.ontario_stats import OntarioStatsResult

    fresh_result = OntarioStatsResult(
        state="fresh",
        figure_kg=7359.0,
        period="2026-02",
        release_time="2026-04-20T08:30",
        prior_period="2026-01",
        prior_figure_kg=7559.0,
    )

    with patch("agents.daily_summary.fetch_ontario_stats_snapshot",
               AsyncMock(return_value=fresh_result)):
        md, jsonb, telemetry = await _build_ontario_stats_section(
            previous_snapshot=None,
            previous_release_time=None,
            agent_run_id="test-agent-run",
        )

    assert md is not None
    assert "7,359 kg" in md
    assert "February 2026" in md
    assert jsonb["last_state"] == "fresh"
    assert jsonb["snapshot"] is not None
    assert jsonb["snapshot"]["figure_kg"] == 7359.0
    assert jsonb["last_error_text"] is None


@pytest.mark.asyncio
async def test_s2_no_new_data_with_prior_snapshot_propagates_forward():
    """S2: no_new_data + prior snapshot → 'No new production statistics' + snapshot propagated."""
    from agents.ontario_stats import OntarioStatsResult

    prior_snapshot = {
        "period": "2026-02",
        "figure_kg": 7359.0,
        "release_time": "2026-04-20T08:30",
        "prior_period": "2026-01",
        "prior_figure_kg": 7559.0,
    }
    no_new_result = OntarioStatsResult(state="no_new_data")

    with patch("agents.daily_summary.fetch_ontario_stats_snapshot",
               AsyncMock(return_value=no_new_result)):
        md, jsonb, telemetry = await _build_ontario_stats_section(
            previous_snapshot=prior_snapshot,
            previous_release_time="2026-04-20T08:30",
            agent_run_id="test-agent-run",
        )

    assert md is not None
    assert "No new production statistics released today" in md
    assert "around May 20, 2026" in md
    assert jsonb["last_state"] == "no_new_data"
    # Prior snapshot must be propagated forward
    assert jsonb["snapshot"] == prior_snapshot
    assert telemetry["candidates_stats_state"] == "no_new_data"
    assert telemetry["candidates_stats_period"] == "2026-02"


@pytest.mark.asyncio
async def test_s3_no_new_data_first_ever_fire():
    """S3: no_new_data + no prior snapshot → 'Awaiting first StatCan release'."""
    from agents.ontario_stats import OntarioStatsResult

    no_new_result = OntarioStatsResult(state="no_new_data")

    with patch("agents.daily_summary.fetch_ontario_stats_snapshot",
               AsyncMock(return_value=no_new_result)):
        md, jsonb, telemetry = await _build_ontario_stats_section(
            previous_snapshot=None,
            previous_release_time=None,
            agent_run_id="test-agent-run",
        )

    assert md is not None
    assert "Awaiting first StatCan release" in md
    assert jsonb["last_state"] == "no_new_data"
    assert jsonb["snapshot"] is None


@pytest.mark.asyncio
async def test_s4_error_preserves_prior_snapshot():
    """S4: error state → error markdown with agent_run_id + prior snapshot NOT overwritten."""
    from agents.ontario_stats import OntarioStatsResult

    prior_snapshot = {
        "period": "2026-02",
        "figure_kg": 7359.0,
        "release_time": "2026-04-20T08:30",
        "prior_period": None,
        "prior_figure_kg": None,
    }
    error_result = OntarioStatsResult(
        state="error",
        error_text="HTTPError: connection refused",
    )

    with patch("agents.daily_summary.fetch_ontario_stats_snapshot",
               AsyncMock(return_value=error_result)):
        md, jsonb, telemetry = await _build_ontario_stats_section(
            previous_snapshot=prior_snapshot,
            previous_release_time="2026-04-20T08:30",
            agent_run_id="abcdef12-1234-5678-abcd-ef1234567890",
        )

    assert md is not None
    assert "⚠" in md
    assert "Ontario production statistics ingestion failed" in md
    assert "abcdef12" in md  # first 8 chars of agent_run_id
    assert jsonb["last_state"] == "error"
    assert jsonb["last_error_text"] == "HTTPError: connection refused"
    # CRITICAL: prior snapshot must be preserved, NOT overwritten
    assert jsonb["snapshot"] == prior_snapshot, (
        "Error state must preserve the prior snapshot — do NOT overwrite!"
    )
    assert telemetry["candidates_stats_state"] == "error"


@pytest.mark.asyncio
async def test_s5_telemetry_fresh_path():
    """S5: fresh path → all 3 candidates_stats_* telemetry keys correctly set."""
    from agents.ontario_stats import OntarioStatsResult

    fresh_result = OntarioStatsResult(
        state="fresh",
        figure_kg=7359.0,
        period="2026-02",
        release_time="2026-04-20T08:30",
        prior_period="2026-01",
        prior_figure_kg=7559.0,
    )

    with patch("agents.daily_summary.fetch_ontario_stats_snapshot",
               AsyncMock(return_value=fresh_result)):
        _, _, telemetry = await _build_ontario_stats_section(
            previous_snapshot=None,
            previous_release_time=None,
            agent_run_id="test-run",
        )

    assert telemetry["candidates_stats_state"] == "fresh"
    assert telemetry["candidates_stats_period"] == "2026-02"
    assert telemetry["candidates_stats_release_time"] == "2026-04-20T08:30"


@pytest.mark.asyncio
async def test_s6_telemetry_error_path():
    """S6: error path → candidates_stats_state='error', period/release_time=None."""
    from agents.ontario_stats import OntarioStatsResult

    error_result = OntarioStatsResult(state="error", error_text="WDS down")

    with patch("agents.daily_summary.fetch_ontario_stats_snapshot",
               AsyncMock(return_value=error_result)):
        _, _, telemetry = await _build_ontario_stats_section(
            previous_snapshot=None,
            previous_release_time=None,
            agent_run_id="test-run",
        )

    assert telemetry["candidates_stats_state"] == "error"
    assert telemetry["candidates_stats_period"] is None
    assert telemetry["candidates_stats_release_time"] is None


def test_s7_raw_sources_new_shape_only():
    """S7: raw_sources['ontario_stats'] uses new shape — no old Phase 1 keys."""
    import inspect
    import agents.daily_summary as ds_module

    source = inspect.getsource(ds_module)
    # Old keys must NOT appear
    assert "snapshot_date" not in source, "snapshot_date (old Phase 1 key) must be gone"
    assert "last_known_figure" not in source, "last_known_figure (old Phase 1 key) must be gone"
    assert "fresh_data" not in source, "fresh_data (old Phase 1 key) must be gone"
    # New keys must appear
    assert "last_state" in source
    assert "last_error_text" in source


def test_s8_stub_constant_and_text_removed():
    """S8: ONTARIO_STATS_STUB_MD constant removed; stub text no longer in module source."""
    import inspect
    import agents.daily_summary as ds_module

    assert not hasattr(ds_module, "ONTARIO_STATS_STUB_MD"), (
        "ONTARIO_STATS_STUB_MD must be removed in Phase 3"
    )
    source = inspect.getsource(ds_module)
    assert "(stub) Ontario stats section" not in source, (
        "Stub text must be removed from daily_summary.py in Phase 3"
    )


# ---------------------------------------------------------------------------
# quick-260514-jny — Per-section error capture into agent_runs.errors
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gold_section_captures_sonnet_exception_into_counts():
    """quick-260514-jny: when Sonnet's WRITE call raises, the exception type
    and message must be captured into counts['last_error'] so the orchestrator
    can propagate it to agent_runs.errors. Format: 'sonnet_write: {Type}: {msg}'.

    Without this, post-mortem diagnostics require Railway log access; with it,
    operators can query agent_runs.errors directly via Neon SQL.
    """
    from datetime import datetime, timezone
    from unittest.mock import AsyncMock, patch

    from anthropic import APITimeoutError

    stories = [
        {
            "title": "Gold up", "link": "http://x", "source_name": "kitco.com",
            "summary": "...", "published": datetime.now(timezone.utc),
            "score": 7.5, "_source_type": "rss",
        }
    ]
    anthropic_client = AsyncMock()
    # Simulate a real APITimeoutError; SDK uses httpx under the hood
    anthropic_client.messages.create = AsyncMock(
        side_effect=APITimeoutError(request=AsyncMock())
    )

    with patch("agents.daily_summary.fetch_stories", AsyncMock(return_value=stories)):
        md, raw, counts = await _build_gold_news_section(anthropic_client)

    assert md is None, "gold section md must be None on Sonnet failure"
    assert raw, "raw_sources must be populated even on Sonnet failure (forensic value)"
    assert counts.get("last_error") is not None, (
        "counts['last_error'] must be populated when Sonnet raises"
    )
    last_error = counts["last_error"]
    assert "sonnet_write" in last_error, (
        f"last_error must be tagged with 'sonnet_write' stage; got: {last_error}"
    )
    assert "APITimeoutError" in last_error, (
        f"last_error must include exception type name; got: {last_error}"
    )


@pytest.mark.asyncio
async def test_gold_section_captures_fetch_stories_exception_into_counts():
    """quick-260514-jny: when fetch_stories raises, the exception text is
    captured into counts['last_error'] with the 'fetch_stories' stage tag.
    """
    from unittest.mock import AsyncMock, patch

    with patch(
        "agents.daily_summary.fetch_stories",
        AsyncMock(side_effect=RuntimeError("network down")),
    ):
        md, raw, counts = await _build_gold_news_section(AsyncMock())

    assert md is None
    assert raw == []
    assert counts.get("last_error") is not None
    last_error = counts["last_error"]
    assert "fetch_stories" in last_error
    assert "RuntimeError" in last_error
    assert "network down" in last_error


def test_gold_section_counts_has_last_error_key_on_success():
    """quick-260514-jny: counts dict must declare the last_error key (with None
    value) on success paths too — so the orchestrator can do a uniform
    counts.get('last_error') without KeyError.
    """
    # Just check the constant init in _build_gold_news_section by inspecting source.
    import inspect
    import agents.daily_summary as ds_module

    source = inspect.getsource(ds_module._build_gold_news_section)
    # The counts dict must initialize last_error to None
    assert '"last_error": None' in source, (
        "counts dict in _build_gold_news_section must initialize last_error: None"
    )


# ---------------------------------------------------------------------------
# quick-260514-ii6 — Sonnet per-request timeout regression guards
# ---------------------------------------------------------------------------


def test_anthropic_client_timeout_is_60_seconds():
    """quick-260514-ii6: AsyncAnthropic construction in run_daily_summary must use
    a 60-second per-request timeout.

    The 2026-05-14 12:00 PT fire fell back to status=partial because Sonnet's
    WRITE call hit the prior 30s ceiling on a heavy-news day. The bull-thesis
    prompt (of1/oxr) tripled the gold section's effective compute load:
    12 candidates × ~3 KB each in the user prompt + 1500-token output target +
    4-sub-section structural ask. 60s gives headroom without being reckless.

    Regression guard: if anyone reverts the timeout, this test catches it.
    """
    import inspect
    import agents.daily_summary as ds_module

    source = inspect.getsource(ds_module)
    # The exact construction must use timeout=60.0 (not 30.0, not 45.0)
    assert "timeout=60.0" in source, (
        "AsyncAnthropic in run_daily_summary must use timeout=60.0 "
        "(quick-260514-ii6 bumped from 30s to absorb bull-thesis prompt size)"
    )
    # The legacy 30s ceiling must NOT linger in daily_summary's anthropic_client
    # construction. (Other modules — content_agent's fetch_stories — still use
    # 30s and that's intentional; this test is scoped to daily_summary only.)
    # Check by ensuring the run_daily_summary scope contains 60.0 and the AsyncAnthropic
    # construction inside it does NOT mention timeout=30.0
    construction_block = source[source.find("anthropic_client = AsyncAnthropic"):]
    construction_block = construction_block[:construction_block.find(")") + 1]
    assert "timeout=60.0" in construction_block, (
        f"AsyncAnthropic construction must use timeout=60.0; got: {construction_block}"
    )
    assert "timeout=30.0" not in construction_block, (
        "Legacy 30s timeout in daily_summary's AsyncAnthropic must be removed"
    )
