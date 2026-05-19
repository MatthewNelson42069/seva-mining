"""pytest coverage for scheduler/agents/weekly_sweeper.py (Phase 7, Plan 04).

Covers:
- canonical_url tracking-param strip + sort + lowercase + trailing-slash (P10)
- _compute_virality: empty DB, NULL raw_sources_jsonb (P3 guard),
  distinct-source-count ranking (SWEEP-07), top-5 cap, status filter
- run_weekly_sweeper:
  * happy path -> status='completed', all 3 markdown fields populated
  * insufficient signal (P15) -> Sonnet NOT called, fallback copy, status='completed'
  * Sonnet fails -> status='partial', failure copy in angles_md
  * idempotency skip (SWEEP-10) -> no external work, no row inserted
"""
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ---------------------------------------------------------------------------
# canonical_url tests — pure function, no fixtures needed
# ---------------------------------------------------------------------------

def test_canonical_url_strips_tracking():
    from agents.weekly_sweeper import canonical_url
    result = canonical_url(
        "https://Example.COM/path/?utm_source=tw&utm_medium=cpc&fbclid=abc&gclid=xyz&id=42&ref=home"
    )
    assert result == "https://example.com/path?id=42"


def test_canonical_url_query_sorted():
    from agents.weekly_sweeper import canonical_url
    assert canonical_url("https://a.com/p?z=2&a=1&m=5") == "https://a.com/p?a=1&m=5&z=2"


def test_canonical_url_trailing_slash():
    from agents.weekly_sweeper import canonical_url
    assert canonical_url("https://a.com/path/") == "https://a.com/path"
    # root path is preserved (only strip slash when len(path) > 1)
    assert canonical_url("https://a.com/") == "https://a.com/"


def test_canonical_url_lowercases_host():
    from agents.weekly_sweeper import canonical_url
    assert canonical_url("HTTPS://Example.COM/path") == "https://example.com/path"


def test_canonical_url_strips_full_tracking_set():
    from agents.weekly_sweeper import canonical_url
    # All tracking params should be stripped, leaving only 'id'
    result = canonical_url(
        "https://x.com/p?utm_source=a&utm_medium=b&utm_campaign=c&utm_term=d&utm_content=e&fbclid=f&gclid=g&ref=h&source=i&_ga=j&id=42"
    )
    assert result == "https://x.com/p?id=42"


# ---------------------------------------------------------------------------
# _compute_virality tests — needs a mocked AsyncSession
# ---------------------------------------------------------------------------

def _mk_summary_row(status="completed", gold_news=None, days_ago=0):
    """Build a SimpleNamespace mimicking a DailySummary row."""
    return SimpleNamespace(
        id=uuid.uuid4(),
        generated_at=datetime.now(timezone.utc) - timedelta(days=days_ago),
        status=status,
        raw_sources_jsonb={"gold_news": gold_news} if gold_news is not None else None,
    )


def _mk_session_with_rows(rows):
    """Build a MagicMock AsyncSession whose execute() returns rows."""
    session = MagicMock()
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = rows
    result_mock = MagicMock()
    result_mock.scalars.return_value = scalars_mock
    session.execute = AsyncMock(return_value=result_mock)
    return session


@pytest.mark.asyncio
async def test_compute_virality_empty_db():
    from agents.weekly_sweeper import _compute_virality
    session = _mk_session_with_rows([])
    result = await _compute_virality(session)
    assert result == []


@pytest.mark.asyncio
async def test_compute_virality_null_raw_sources():
    """P3 guard: rows with raw_sources_jsonb=None must not crash _compute_virality."""
    from agents.weekly_sweeper import _compute_virality
    session = _mk_session_with_rows([_mk_summary_row(gold_news=None)])
    result = await _compute_virality(session)
    assert result == []


@pytest.mark.asyncio
async def test_compute_virality_ranks_by_distinct_source_count():
    """SWEEP-07: same canonical URL across 3 distinct source_names ranks #1 with count=3."""
    from agents.weekly_sweeper import _compute_virality
    url = "https://example.com/big-gold-story"
    rows = [
        _mk_summary_row(gold_news=[
            {"link": url, "title": "Gold Story", "source_name": "Reuters", "score": 8.0},
        ]),
        _mk_summary_row(gold_news=[
            {"link": url, "title": "Gold Story", "source_name": "Bloomberg", "score": 7.5},
        ]),
        _mk_summary_row(gold_news=[
            {"link": url, "title": "Gold Story", "source_name": "Kitco", "score": 6.5},
        ]),
    ]
    session = _mk_session_with_rows(rows)
    result = await _compute_virality(session)
    assert len(result) == 1
    assert result[0]["distinct_source_count"] == 3
    assert set(result[0]["source_names"]) == {"Reuters", "Bloomberg", "Kitco"}


@pytest.mark.asyncio
async def test_compute_virality_top_5_only():
    """Cap at VIRALITY_TOP_N (5) even when there are more candidates.

    Use distinctly-worded titles to avoid the title-similarity dedup that
    deduplicate_stories applies per-row (SequenceMatcher >= 0.85). Each story
    is on its own URL with its own source, so it should pass dedup and
    contribute one canonical URL each.
    """
    from agents.weekly_sweeper import _compute_virality
    distinct_titles = [
        "Central banks accelerate gold buying program",
        "Goldman Sachs raises 2026 price target sharply",
        "Mining production drops in Western Australia",
        "Federal Reserve signals dovish pivot next quarter",
        "Inflation data shows persistent CPI pressure",
        "Geopolitical tensions spike across Middle East",
        "ETF flows reverse with massive new inflows",
        "USD weakness drives commodities rally broadly",
        "Real yields compress on bond auction surprise",
        "Major M&A deal reshapes producer landscape",
    ]
    rows = [
        _mk_summary_row(gold_news=[
            {
                "link": f"https://example.com/story-{i}",
                "title": distinct_titles[i],
                "source_name": f"Source{i}",
                "score": 8.0,
            }
            for i in range(10)
        ]),
    ]
    session = _mk_session_with_rows(rows)
    result = await _compute_virality(session)
    assert len(result) == 5


@pytest.mark.asyncio
async def test_compute_virality_canonicalizes_urls():
    """Same canonical URL via tracking-param variants should group together."""
    from agents.weekly_sweeper import _compute_virality
    rows = [
        _mk_summary_row(gold_news=[
            {
                "link": "https://example.com/story?utm_source=tw&id=1",
                "title": "Gold rallies",
                "source_name": "Reuters",
            },
        ]),
        _mk_summary_row(gold_news=[
            {
                "link": "https://example.com/story?fbclid=abc&id=1",
                "title": "Gold rallies",
                "source_name": "Bloomberg",
            },
        ]),
    ]
    session = _mk_session_with_rows(rows)
    result = await _compute_virality(session)
    assert len(result) == 1
    assert result[0]["distinct_source_count"] == 2
    assert result[0]["canonical_url"] == "https://example.com/story?id=1"


# ---------------------------------------------------------------------------
# run_weekly_sweeper happy path + fault branches
# ---------------------------------------------------------------------------

def _make_orchestration_session():
    """Build a MagicMock async-context-manager that captures session.add calls.

    Returns (session, ctx_callable) — pass ctx_callable to monkeypatch as
    AsyncSessionLocal so each `async with AsyncSessionLocal() as session:`
    yields the same MagicMock session.
    """
    sess = MagicMock()
    sess.add = MagicMock()
    sess.commit = AsyncMock()
    sess.refresh = AsyncMock(side_effect=lambda obj: setattr(obj, "id", uuid.uuid4()))
    sess.get = AsyncMock(return_value=MagicMock(status="running", errors=None, notes=None))

    def make_ctx():
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=sess)
        ctx.__aexit__ = AsyncMock(return_value=None)
        return ctx

    return sess, make_ctx


def _added_sweep_rows(sess):
    """Return all WeeklySweep rows passed to session.add (filtered by __tablename__)."""
    return [
        c.args[0] for c in sess.add.call_args_list
        if getattr(c.args[0], "__tablename__", None) == "weekly_sweeps"
    ]


@pytest.mark.asyncio
async def test_run_weekly_sweeper_insufficient_signal(monkeypatch):
    """P15: fetch_top_x_posts returns 2 posts -> Sonnet NOT called, fallback copy, completed."""
    from agents import weekly_sweeper

    fake_x_posts = [
        {
            "tweet_id": "1", "text": "x1", "author_username": "a", "tweet_url": "u1",
            "likes": 0, "retweets": 0, "replies": 0,
            "created_at": datetime.now(timezone.utc),
        },
        {
            "tweet_id": "2", "text": "x2", "author_username": "b", "tweet_url": "u2",
            "likes": 0, "retweets": 0, "replies": 0,
            "created_at": datetime.now(timezone.utc),
        },
    ]
    fake_viral_stories: list[dict] = []

    async def fake_fetch(query, max_results=100):
        return fake_x_posts

    async def fake_virality(session):
        return fake_viral_stories

    monkeypatch.setattr(weekly_sweeper, "fetch_top_x_posts", fake_fetch)
    monkeypatch.setattr(weekly_sweeper, "_compute_virality", fake_virality)
    monkeypatch.setattr(weekly_sweeper, "_idempotency_skip", AsyncMock(return_value=False))

    sess, make_ctx = _make_orchestration_session()
    monkeypatch.setattr(weekly_sweeper, "AsyncSessionLocal", make_ctx)

    anthropic_inst = MagicMock()
    anthropic_inst.messages = MagicMock()
    anthropic_inst.messages.create = AsyncMock()
    monkeypatch.setattr(weekly_sweeper, "AsyncAnthropic", lambda **kw: anthropic_inst)

    await weekly_sweeper.run_weekly_sweeper()

    # P15: Sonnet must NOT have been called
    anthropic_inst.messages.create.assert_not_called()

    sweep_rows = _added_sweep_rows(sess)
    assert len(sweep_rows) == 1
    row = sweep_rows[0]
    assert "Insufficient signal" in (row.content_angles_md or "")
    assert row.status == "completed"  # designed-fallback path


@pytest.mark.asyncio
async def test_run_weekly_sweeper_happy_path(monkeypatch):
    """X returns 10, virality returns 5, Sonnet returns angles -> completed + all 3 md fields."""
    from agents import weekly_sweeper

    fake_x = [
        {
            "tweet_id": str(i), "text": f"x{i}", "author_username": f"a{i}",
            "tweet_url": f"u{i}", "likes": i, "retweets": i, "replies": i,
            "created_at": datetime.now(timezone.utc),
        }
        for i in range(10)
    ]
    fake_viral = [
        {
            "canonical_url": f"https://example.com/s{i}",
            "title": f"Story {i}",
            "distinct_source_count": 3 - (i // 2),
            "source_names": ["A", "B", "C"][: max(1, 3 - (i // 2))],
            "sample_published_at": None,
        }
        for i in range(5)
    ]

    async def fake_fetch(query, max_results=100):
        return fake_x

    async def fake_virality(session):
        return fake_viral

    monkeypatch.setattr(weekly_sweeper, "fetch_top_x_posts", fake_fetch)
    monkeypatch.setattr(weekly_sweeper, "_compute_virality", fake_virality)
    monkeypatch.setattr(weekly_sweeper, "_idempotency_skip", AsyncMock(return_value=False))

    sess, make_ctx = _make_orchestration_session()
    monkeypatch.setattr(weekly_sweeper, "AsyncSessionLocal", make_ctx)

    anthropic_inst = MagicMock()
    anthropic_inst.messages = MagicMock()
    fake_resp = MagicMock()
    fake_resp.content = [MagicMock(text="### Angle 1: foo\n\n* X signal: hello")]
    anthropic_inst.messages.create = AsyncMock(return_value=fake_resp)
    monkeypatch.setattr(weekly_sweeper, "AsyncAnthropic", lambda **kw: anthropic_inst)

    await weekly_sweeper.run_weekly_sweeper()

    anthropic_inst.messages.create.assert_awaited_once()
    sweep_rows = _added_sweep_rows(sess)
    assert len(sweep_rows) == 1
    row = sweep_rows[0]
    assert row.status == "completed"
    assert row.reddit_top_md is not None and "Top X Posts" in row.reddit_top_md
    assert row.story_virality_md is not None and "Most Cross-Referenced Stories" in row.story_virality_md
    assert row.content_angles_md is not None and "Angle 1" in row.content_angles_md


@pytest.mark.asyncio
async def test_run_weekly_sweeper_sonnet_fails(monkeypatch):
    """Sufficient signal + Sonnet raises -> status='partial', failure copy in angles_md."""
    from agents import weekly_sweeper

    fake_x = [
        {
            "tweet_id": str(i), "text": f"x{i}", "author_username": f"a{i}",
            "tweet_url": f"u{i}", "likes": i, "retweets": i, "replies": i,
            "created_at": datetime.now(timezone.utc),
        }
        for i in range(10)
    ]
    fake_viral = [
        {
            "canonical_url": f"https://example.com/s{i}",
            "title": f"Story {i}",
            "distinct_source_count": 2,
            "source_names": ["A", "B"],
            "sample_published_at": None,
        }
        for i in range(5)
    ]

    async def fake_fetch(query, max_results=100):
        return fake_x

    async def fake_virality(session):
        return fake_viral

    monkeypatch.setattr(weekly_sweeper, "fetch_top_x_posts", fake_fetch)
    monkeypatch.setattr(weekly_sweeper, "_compute_virality", fake_virality)
    monkeypatch.setattr(weekly_sweeper, "_idempotency_skip", AsyncMock(return_value=False))

    sess, make_ctx = _make_orchestration_session()
    monkeypatch.setattr(weekly_sweeper, "AsyncSessionLocal", make_ctx)

    anthropic_inst = MagicMock()
    anthropic_inst.messages = MagicMock()
    anthropic_inst.messages.create = AsyncMock(side_effect=TimeoutError("sonnet hung"))
    monkeypatch.setattr(weekly_sweeper, "AsyncAnthropic", lambda **kw: anthropic_inst)

    await weekly_sweeper.run_weekly_sweeper()

    sweep_rows = _added_sweep_rows(sess)
    assert len(sweep_rows) == 1
    row = sweep_rows[0]
    assert row.status == "partial"
    assert row.content_angles_md is not None
    assert "fail" in row.content_angles_md.lower()


@pytest.mark.asyncio
async def test_run_weekly_sweeper_idempotency_skip(monkeypatch):
    """SWEEP-10: existing row in window -> no external work, no insert."""
    from agents import weekly_sweeper

    sess, make_ctx = _make_orchestration_session()
    monkeypatch.setattr(weekly_sweeper, "AsyncSessionLocal", make_ctx)
    monkeypatch.setattr(weekly_sweeper, "_idempotency_skip", AsyncMock(return_value=True))

    fetch_mock = AsyncMock()
    monkeypatch.setattr(weekly_sweeper, "fetch_top_x_posts", fetch_mock)

    await weekly_sweeper.run_weekly_sweeper()

    # No external work or DB writes should have happened
    fetch_mock.assert_not_called()
    sess.add.assert_not_called()
