"""Phase 15 unit tests for run_juno_weekly_sweeper() + its helpers.

Covers:
- JSWEEP-02 (X query + virality compute over 3-sub-array union + dedup
  + distinct-source counting)
- JSWEEP-03 (idempotency-includes-partial + company_id='juno' on persist
  + cross-tenant isolation)
- JSWEEP-04 (anthropic_client hardcoded 'juno' literal + refusal-detector
  retry path wiring + status='partial' on refusal)

Validates D-02 (X query), D-03 (3-sub-array union virality substrate),
D-04 (Sonnet via per-tenant resolver), D-05 (refusal-detector wrap),
D-06 (helper-share via import-from-Seva), D-10 (Seva byte-identical)
contracts.

Test framework follows the existing scheduler test pattern (see
tests/test_weekly_sweeper.py + tests/agents/test_juno_daily_summary.py):
MagicMock + AsyncMock + monkeypatch — scheduler test layer doesn't use a
SQLite fixture (Postgres-only JSONB + UUID column types).
"""
from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

# Match the test_juno_daily_summary.py path setup so module-level config
# loads succeed even when this file runs in isolation.
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


# ---------------------------------------------------------------------------
# Fixture helpers — mirror tests/test_weekly_sweeper.py shape
# ---------------------------------------------------------------------------

def _fake_x_posts(n: int = 5) -> list[dict]:
    """Build n mock X post dicts with the fetch_top_x_posts return shape."""
    return [
        {
            "tweet_id": str(i),
            "text": f"defence-sector signal {i}",
            "author_username": f"defence_handle_{i}",
            "tweet_url": f"https://twitter.com/handle{i}/status/{i}",
            "likes": 100 - i,
            "retweets": 50 - i,
            "replies": 10 - i,
            "created_at": datetime.now(timezone.utc),
        }
        for i in range(n)
    ]


def _fake_viral_stories(n: int = 5) -> list[dict]:
    """Build n mock virality result dicts (post-_compute_juno_virality shape)."""
    return [
        {
            "canonical_url": f"https://defencenews.example.com/story-{i}",
            "title": f"Defence Story {i}",
            "distinct_source_count": max(2, 5 - i),
            "source_names": ["RUSI", "Janes", "DefenseNews"][: max(2, 5 - i)],
            "sample_published_at": None,
        }
        for i in range(n)
    ]


def _mk_juno_summary_row(
    *,
    defence_news: list | None = None,
    canadian_procurement: list | None = None,
    world_events: list | None = None,
    status: str = "completed",
    days_ago: int = 0,
) -> SimpleNamespace:
    """Build a SimpleNamespace mimicking a Juno DailySummary row.

    Mirrors tests/test_weekly_sweeper.py::_mk_summary_row, but with the
    Plan 15-01 D-03a 3-sub-array substrate keys.
    """
    raw: dict = {}
    if defence_news is not None:
        raw["defence_news"] = defence_news
    if canadian_procurement is not None:
        raw["canadian_procurement"] = canadian_procurement
    if world_events is not None:
        raw["world_events"] = world_events
    return SimpleNamespace(
        id=uuid.uuid4(),
        company_id="juno",
        generated_at=datetime.now(timezone.utc) - timedelta(days=days_ago),
        status=status,
        raw_sources_jsonb=raw if raw else None,
    )


def _mk_session_with_rows(rows: list) -> MagicMock:
    """Build a MagicMock AsyncSession whose execute() returns the given rows."""
    session = MagicMock()
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = rows
    result_mock = MagicMock()
    result_mock.scalars.return_value = scalars_mock
    session.execute = AsyncMock(return_value=result_mock)
    return session


def _make_orchestration_session():
    """Build a MagicMock async-context-manager that captures session.add calls.

    Mirrors tests/test_weekly_sweeper.py::_make_orchestration_session — the
    same MagicMock session is yielded by every `async with AsyncSessionLocal()
    as session:` so test assertions can inspect added rows after run completes.
    """
    sess = MagicMock()
    sess.add = MagicMock()
    sess.commit = AsyncMock()
    sess.refresh = AsyncMock(
        side_effect=lambda obj: setattr(obj, "id", uuid.uuid4())
    )
    sess.get = AsyncMock(
        return_value=MagicMock(status="running", errors=None, notes=None)
    )

    # Idempotency check default: no recent row (returns None).
    idempotency_result = MagicMock()
    idempotency_result.scalar_one_or_none.return_value = None
    # Virality default: empty rows (test overrides via session.execute mock).
    virality_scalars = MagicMock()
    virality_scalars.all.return_value = []
    virality_result = MagicMock()
    virality_result.scalars.return_value = virality_scalars

    # session.execute is called by both idempotency + virality flows; default
    # path returns the idempotency 'no recent row' result so the orchestrator
    # proceeds. Tests that want a different virality substrate inject via
    # _seed_juno_substrate(session, ...).
    sess.execute = AsyncMock(return_value=idempotency_result)
    sess._idempotency_result = idempotency_result
    sess._virality_result = virality_result

    def make_ctx():
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=sess)
        ctx.__aexit__ = AsyncMock(return_value=None)
        return ctx

    return sess, make_ctx


def _added_sweep_rows(sess):
    """Return all WeeklySweep rows passed to session.add."""
    return [
        c.args[0]
        for c in sess.add.call_args_list
        if getattr(c.args[0], "__tablename__", None) == "weekly_sweeps"
    ]


# ---------------------------------------------------------------------------
# Group A — _compute_juno_virality unit tests (JSWEEP-02)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_virality_compute_three_sub_array_union():
    """JSWEEP-02 / D-03 — virality compute reads ALL THREE sub-arrays
    (defence_news + canadian_procurement + world_events) from raw_sources_jsonb,
    not just one.

    Seeds one Juno daily_summary with one story per sub-array (3 stories total),
    asserts all 3 surface in the virality result with distinct canonical URLs.
    """
    from agents.juno_weekly_sweeper import _compute_juno_virality

    row = _mk_juno_summary_row(
        defence_news=[
            {
                "link": "https://defence.example/story-A",
                "title": "Defence story A",
                "source_name": "RUSI",
            },
        ],
        canadian_procurement=[
            {
                "link": "https://procurement.example/story-B",
                "title": "Procurement story B",
                "source_name": "Canada.ca",
            },
        ],
        world_events=[
            {
                "link": "https://world.example/story-C",
                "title": "World event C",
                "source_name": "Reuters",
            },
        ],
    )
    session = _mk_session_with_rows([row])
    result = await _compute_juno_virality(session)

    # All three sub-arrays contribute exactly one story each (3 total).
    # Note: canonical_url() lowercases the host but preserves path case.
    assert len(result) == 3, (
        f"Expected 3 viral stories (one from each sub-array), got {len(result)}"
    )
    urls = {s["canonical_url"] for s in result}
    assert "https://defence.example/story-A" in urls, (
        f"defence_news sub-array did NOT surface; urls={urls}"
    )
    assert "https://procurement.example/story-B" in urls, (
        f"canadian_procurement sub-array did NOT surface; urls={urls}"
    )
    assert "https://world.example/story-C" in urls, (
        f"world_events sub-array did NOT surface; urls={urls}"
    )


@pytest.mark.asyncio
async def test_virality_compute_dedupes_by_canonical_url():
    """JSWEEP-02 / D-03 — same canonical URL across different sub-arrays
    + different tracking params groups together. distinct_source_count
    counts the union of source_names across rows."""
    from agents.juno_weekly_sweeper import _compute_juno_virality

    row1 = _mk_juno_summary_row(
        defence_news=[
            {
                "link": "https://shared.example/big-story?utm_source=tw",
                "title": "Shared big story",
                "source_name": "RUSI",
            },
        ],
    )
    row2 = _mk_juno_summary_row(
        world_events=[
            {
                "link": "https://shared.example/big-story?fbclid=abc",
                "title": "Shared big story",
                "source_name": "Reuters",
            },
        ],
    )
    session = _mk_session_with_rows([row1, row2])
    result = await _compute_juno_virality(session)

    # Canonical-URL dedup collapses both rows into a single virality entry
    # with distinct_source_count == 2 (RUSI + Reuters).
    assert len(result) == 1, (
        f"Expected 1 deduped virality entry, got {len(result)}: {result}"
    )
    assert result[0]["distinct_source_count"] == 2, (
        f"distinct_source_count should be 2 (RUSI + Reuters across rows); "
        f"got {result[0]['distinct_source_count']}"
    )
    assert set(result[0]["source_names"]) == {"RUSI", "Reuters"}
    # canonical_url() strips tracking params + lowercases host
    assert result[0]["canonical_url"] == "https://shared.example/big-story"


@pytest.mark.asyncio
async def test_virality_compute_returns_empty_on_no_juno_rows():
    """JSWEEP-02 — empty DB (or scoped-out — only Seva rows exist) returns []
    without error."""
    from agents.juno_weekly_sweeper import _compute_juno_virality

    session = _mk_session_with_rows([])
    result = await _compute_juno_virality(session)
    assert result == [], f"Expected empty result on no rows, got {result}"


@pytest.mark.asyncio
async def test_virality_compute_null_raw_sources_guards():
    """P3 guard — raw_sources_jsonb=None must not crash the virality compute."""
    from agents.juno_weekly_sweeper import _compute_juno_virality

    row_null = SimpleNamespace(
        id=uuid.uuid4(),
        company_id="juno",
        generated_at=datetime.now(timezone.utc),
        status="failed",
        raw_sources_jsonb=None,
    )
    session = _mk_session_with_rows([row_null])
    result = await _compute_juno_virality(session)
    assert result == [], (
        f"NULL raw_sources_jsonb should produce empty virality, got {result}"
    )


# ---------------------------------------------------------------------------
# Group B — _idempotency_skip unit tests (JSWEEP-03 / Phase 9 critical-fix)
# ---------------------------------------------------------------------------


def _idempotency_session(returns_existing: bool) -> MagicMock:
    """Build an AsyncSession mock whose execute() returns an existing-row UUID
    iff returns_existing=True, otherwise None."""
    session = MagicMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = (
        uuid.uuid4() if returns_existing else None
    )
    session.execute = AsyncMock(return_value=result_mock)
    return session


@pytest.mark.asyncio
async def test_idempotency_skip_when_partial_exists():
    """JSWEEP-03 / Phase 9 critical-fix — when a recent Juno row with
    status='partial' exists, second invocation skips without writing duplicate.

    The Juno idempotency filter MUST include 'partial' (Seva's filter is
    ['running', 'completed']). Without it, every cron fire that landed
    status='partial' (refusal-detector trip or D-03b backfill window) would
    write a duplicate row on the next retry."""
    from agents.juno_weekly_sweeper import _idempotency_skip

    session = _idempotency_session(returns_existing=True)
    skipped = await _idempotency_skip(session, datetime.now(timezone.utc))
    assert skipped is True, (
        "Idempotency must skip when an existing recent Juno row exists "
        "(status='partial' included in the filter per Phase 9 critical-fix)"
    )


@pytest.mark.asyncio
async def test_idempotency_skip_returns_false_when_no_recent_row():
    """JSWEEP-03 — when no recent Juno row exists, idempotency must NOT skip."""
    from agents.juno_weekly_sweeper import _idempotency_skip

    session = _idempotency_session(returns_existing=False)
    skipped = await _idempotency_skip(session, datetime.now(timezone.utc))
    assert skipped is False


@pytest.mark.asyncio
async def test_idempotency_filter_includes_partial_status_in_query():
    """JSWEEP-03 / Phase 9 critical-fix — verify the actual SQL filter
    includes the string 'partial'.

    Mirrors the Phase 10 daily-summary idempotency contract — the in_ filter
    must carry all three statuses (running/completed/partial). Without this,
    Juno's high partial-row volume (refusal-detector trips + D-03b backfill)
    would silently produce duplicates."""
    import inspect

    from agents.juno_weekly_sweeper import _idempotency_skip

    src = inspect.getsource(_idempotency_skip)
    # The filter literal MUST appear verbatim. Tightest grep gate.
    assert "'partial'" in src or '"partial"' in src, (
        "_idempotency_skip MUST include 'partial' in the status filter "
        "(Phase 9 critical-fix); source did not contain the literal"
    )
    assert "'running'" in src or '"running"' in src, (
        "_idempotency_skip MUST include 'running' in the status filter"
    )
    assert "'completed'" in src or '"completed"' in src, (
        "_idempotency_skip MUST include 'completed' in the status filter"
    )


# ---------------------------------------------------------------------------
# Group C — run_juno_weekly_sweeper end-to-end (JSWEEP-02, -03, -04)
# ---------------------------------------------------------------------------


def _patch_orchestration(monkeypatch, *, x_posts, viral, refusal_return):
    """Patch all external services on the SUT module + return the session
    mock so tests can introspect added rows.

    refusal_return: tuple (angles_md_or_None, diagnostic_dict) returned by
    call_with_refusal_guard.
    """
    from agents import juno_weekly_sweeper

    async def fake_fetch(query, max_results=100):
        return x_posts

    async def fake_virality(session):
        return viral

    async def fake_refusal_guard(*args, **kwargs):
        return refusal_return

    monkeypatch.setattr(juno_weekly_sweeper, "fetch_top_x_posts", fake_fetch)
    monkeypatch.setattr(
        juno_weekly_sweeper, "_compute_juno_virality", fake_virality
    )
    monkeypatch.setattr(
        juno_weekly_sweeper, "call_with_refusal_guard", fake_refusal_guard
    )
    monkeypatch.setattr(
        juno_weekly_sweeper, "_idempotency_skip", AsyncMock(return_value=False)
    )

    sess, make_ctx = _make_orchestration_session()
    monkeypatch.setattr(juno_weekly_sweeper, "AsyncSessionLocal", make_ctx)

    resolver_calls: list = []

    def _resolver(company_id, *, timeout):
        resolver_calls.append((company_id, timeout))
        # Return a minimal mock client — call_with_refusal_guard is patched
        # above, so this client is never .messages.create()'d.
        return MagicMock()

    monkeypatch.setattr(
        juno_weekly_sweeper, "get_anthropic_client", _resolver
    )

    return sess, resolver_calls


@pytest.mark.asyncio
async def test_run_happy_path_writes_weekly_sweeps_row(monkeypatch):
    """JSWEEP-02 / JSWEEP-03 happy path — 5 X posts + 5 viral stories +
    angles markdown synthesized → status='completed', all 3 markdown columns
    populated, raw_sources_jsonb carries x_search_query == JUNO_SWEEPER_X_QUERY."""
    from agents.juno_weekly_sweeper import run_juno_weekly_sweeper
    from companies.juno.x_queries import JUNO_SWEEPER_X_QUERY

    sess, _resolver_calls = _patch_orchestration(
        monkeypatch,
        x_posts=_fake_x_posts(5),
        viral=_fake_viral_stories(5),
        refusal_return=("### Angle 1: foo\n\n* X signal: bar", {"refusal_detected": False}),
    )

    await run_juno_weekly_sweeper()

    sweep_rows = _added_sweep_rows(sess)
    assert len(sweep_rows) == 1, (
        f"Expected exactly 1 WeeklySweep row added, got {len(sweep_rows)}"
    )
    row = sweep_rows[0]
    assert row.status == "completed", (
        f"Happy path must produce status='completed', got {row.status!r}"
    )
    assert row.reddit_top_md is not None
    assert "Top X Posts" in row.reddit_top_md
    assert row.story_virality_md is not None
    assert "Most Cross-Referenced Stories" in row.story_virality_md
    assert row.content_angles_md is not None
    assert "Angle 1" in row.content_angles_md
    # raw_sources_jsonb carries the executed X query string for diagnostics
    assert row.raw_sources_jsonb is not None
    assert row.raw_sources_jsonb.get("x_search_query") == JUNO_SWEEPER_X_QUERY, (
        f"x_search_query in raw_sources_jsonb must match JUNO_SWEEPER_X_QUERY; "
        f"got {row.raw_sources_jsonb.get('x_search_query')!r}"
    )


@pytest.mark.asyncio
async def test_anthropic_client_called_with_hardcoded_juno_literal(monkeypatch):
    """JSWEEP-04 / Phase 12 D-07 — get_anthropic_client MUST be called with
    the LITERAL string 'juno', NOT a variable.

    Mitigates Phase 15 Hard Part P8 (sweeper Sonnet billing to wrong Anthropic
    key). A typo'd or accidentally-swapped variable would bill Juno's
    synthesis to Seva's Anthropic dashboard."""
    from agents.juno_weekly_sweeper import (
        JUNO_SWEEPER_SONNET_TIMEOUT,
        run_juno_weekly_sweeper,
    )

    _sess, resolver_calls = _patch_orchestration(
        monkeypatch,
        x_posts=_fake_x_posts(5),
        viral=_fake_viral_stories(5),
        refusal_return=("### Angle 1: foo", {"refusal_detected": False}),
    )

    await run_juno_weekly_sweeper()

    assert len(resolver_calls) >= 1, (
        "get_anthropic_client was never invoked — orchestrator did not "
        "reach Sonnet resolution step"
    )
    assert resolver_calls[0][0] == "juno", (
        f"Phase 12 D-07 violated: get_anthropic_client called with "
        f"{resolver_calls[0][0]!r}, expected literal 'juno'"
    )
    assert resolver_calls[0][1] == JUNO_SWEEPER_SONNET_TIMEOUT, (
        f"Resolver timeout must match JUNO_SWEEPER_SONNET_TIMEOUT "
        f"({JUNO_SWEEPER_SONNET_TIMEOUT}s); got {resolver_calls[0][1]}"
    )


@pytest.mark.asyncio
async def test_persisted_row_has_company_id_juno(monkeypatch):
    """JSWEEP-03 — persisted weekly_sweeps row MUST carry company_id='juno'
    (NOT 'seva' — cross-tenant write would corrupt Seva's data set)."""
    from agents.juno_weekly_sweeper import run_juno_weekly_sweeper

    sess, _resolver_calls = _patch_orchestration(
        monkeypatch,
        x_posts=_fake_x_posts(5),
        viral=_fake_viral_stories(5),
        refusal_return=("### Angle 1: foo", {"refusal_detected": False}),
    )

    await run_juno_weekly_sweeper()

    sweep_rows = _added_sweep_rows(sess)
    assert len(sweep_rows) == 1
    assert sweep_rows[0].company_id == "juno", (
        f"Juno sweeper must persist company_id='juno', got "
        f"{sweep_rows[0].company_id!r}"
    )


@pytest.mark.asyncio
async def test_x_search_query_persisted_in_raw_sources(monkeypatch):
    """JSWEEP-02 — the EXECUTED X query is persisted in raw_sources_jsonb
    for diagnostic / audit purposes."""
    from agents.juno_weekly_sweeper import run_juno_weekly_sweeper
    from companies.juno.x_queries import JUNO_SWEEPER_X_QUERY

    sess, _ = _patch_orchestration(
        monkeypatch,
        x_posts=_fake_x_posts(5),
        viral=_fake_viral_stories(5),
        refusal_return=("### Angle 1: foo", {"refusal_detected": False}),
    )

    await run_juno_weekly_sweeper()

    sweep_rows = _added_sweep_rows(sess)
    row = sweep_rows[0]
    assert row.raw_sources_jsonb["x_search_query"] == JUNO_SWEEPER_X_QUERY


@pytest.mark.asyncio
async def test_refusal_first_attempt_retries_via_refusal_guard(monkeypatch):
    """JSWEEP-04 / D-05 — Sonnet call is wrapped by call_with_refusal_guard.

    The Phase 10 wrapper handles retry-with-framing-nudge internally — this
    test asserts that the SUT routes through the wrapper (not that the SUT
    itself implements retry logic). The wrapper's behavior is owned by
    Phase 10's test suite.

    Verified by asserting call_with_refusal_guard is invoked with the right
    section_name marker and system prompt."""
    from agents import juno_weekly_sweeper
    from companies.juno.prompts import JUNO_SWEEPER_SYSTEM_PROMPT

    captured_calls: list[dict] = []

    async def spy_refusal_guard(client, **kwargs):
        captured_calls.append(kwargs)
        return ("### Angle 1: foo", {"refusal_detected": False})

    async def fake_fetch(query, max_results=100):
        return _fake_x_posts(5)

    async def fake_virality(session):
        return _fake_viral_stories(5)

    monkeypatch.setattr(juno_weekly_sweeper, "fetch_top_x_posts", fake_fetch)
    monkeypatch.setattr(
        juno_weekly_sweeper, "_compute_juno_virality", fake_virality
    )
    monkeypatch.setattr(
        juno_weekly_sweeper, "call_with_refusal_guard", spy_refusal_guard
    )
    monkeypatch.setattr(
        juno_weekly_sweeper, "_idempotency_skip", AsyncMock(return_value=False)
    )
    sess, make_ctx = _make_orchestration_session()
    monkeypatch.setattr(juno_weekly_sweeper, "AsyncSessionLocal", make_ctx)
    monkeypatch.setattr(
        juno_weekly_sweeper,
        "get_anthropic_client",
        lambda *a, **kw: MagicMock(),
    )

    await juno_weekly_sweeper.run_juno_weekly_sweeper()

    assert len(captured_calls) == 1, (
        f"Sonnet call must route through call_with_refusal_guard exactly "
        f"once on the happy path; got {len(captured_calls)} call(s)"
    )
    kwargs = captured_calls[0]
    assert kwargs.get("section_name") == "sweeper", (
        f"section_name must be 'sweeper' for diagnostic clarity; got "
        f"{kwargs.get('section_name')!r}"
    )
    assert kwargs.get("system") == JUNO_SWEEPER_SYSTEM_PROMPT, (
        "call_with_refusal_guard must be called with JUNO_SWEEPER_SYSTEM_PROMPT"
    )


@pytest.mark.asyncio
async def test_refusal_second_attempt_sets_partial(monkeypatch):
    """JSWEEP-04 / D-05 — when call_with_refusal_guard returns (None, diag)
    (second-attempt refusal), the persisted weekly_sweeps row MUST have
    status='partial' AND raw_sources_jsonb.refusal_diagnostic populated."""
    from agents.juno_weekly_sweeper import run_juno_weekly_sweeper

    refusal_diag = {
        "refusal_detected": True,
        "retry_attempted": True,
        "first_attempt_excerpt": "I cannot help with that...",
        "second_attempt_excerpt": "I'm unable to provide tactical...",
        "section": "sweeper",
    }
    sess, _ = _patch_orchestration(
        monkeypatch,
        x_posts=_fake_x_posts(5),
        viral=_fake_viral_stories(5),
        refusal_return=(None, refusal_diag),
    )

    await run_juno_weekly_sweeper()

    sweep_rows = _added_sweep_rows(sess)
    assert len(sweep_rows) == 1
    row = sweep_rows[0]
    assert row.status == "partial", (
        f"Refusal second-attempt failure MUST produce status='partial' "
        f"(D-05); got {row.status!r}"
    )
    assert row.raw_sources_jsonb["refusal_diagnostic"]["refusal_detected"] is True, (
        "refusal_diagnostic must be persisted in raw_sources_jsonb for "
        "operator visibility"
    )


@pytest.mark.asyncio
async def test_idempotency_skip_blocks_orchestration(monkeypatch):
    """JSWEEP-03 — when _idempotency_skip returns True, run_juno_weekly_sweeper
    must NOT do any external work (no fetch_top_x_posts call, no DB writes)."""
    from agents import juno_weekly_sweeper

    sess, make_ctx = _make_orchestration_session()
    monkeypatch.setattr(juno_weekly_sweeper, "AsyncSessionLocal", make_ctx)
    monkeypatch.setattr(
        juno_weekly_sweeper, "_idempotency_skip", AsyncMock(return_value=True)
    )

    fetch_mock = AsyncMock()
    monkeypatch.setattr(juno_weekly_sweeper, "fetch_top_x_posts", fetch_mock)

    await juno_weekly_sweeper.run_juno_weekly_sweeper()

    fetch_mock.assert_not_called()
    sess.add.assert_not_called()


@pytest.mark.asyncio
async def test_insufficient_signal_does_not_call_sonnet(monkeypatch):
    """JSWEEP-04 / D-03b — when virality returns 0 cross-references (or X
    returns < 3 posts), Sonnet MUST NOT be called and status is 'partial'
    with INSUFFICIENT_SIGNAL_FALLBACK copy.

    For Juno (per D-03b backfill window) this is more likely to fire than
    for Seva, so the status mapping deliberately uses 'partial' (not
    'completed') with a diagnostic note."""
    from agents.juno_weekly_sweeper import (
        INSUFFICIENT_SIGNAL_FALLBACK,
        run_juno_weekly_sweeper,
    )

    sonnet_call_count = 0

    async def spy_refusal_guard(*args, **kwargs):
        nonlocal sonnet_call_count
        sonnet_call_count += 1
        return ("should not be called", {})

    from agents import juno_weekly_sweeper as jws_module

    async def fake_fetch(query, max_results=100):
        return _fake_x_posts(2)  # < SUFFICIENT_SIGNAL_MIN (3)

    async def fake_virality(session):
        return []  # no cross-references

    monkeypatch.setattr(jws_module, "fetch_top_x_posts", fake_fetch)
    monkeypatch.setattr(jws_module, "_compute_juno_virality", fake_virality)
    monkeypatch.setattr(
        jws_module, "call_with_refusal_guard", spy_refusal_guard
    )
    monkeypatch.setattr(
        jws_module, "_idempotency_skip", AsyncMock(return_value=False)
    )
    sess, make_ctx = _make_orchestration_session()
    monkeypatch.setattr(jws_module, "AsyncSessionLocal", make_ctx)
    monkeypatch.setattr(
        jws_module, "get_anthropic_client", lambda *a, **kw: MagicMock()
    )

    await run_juno_weekly_sweeper()

    assert sonnet_call_count == 0, (
        f"Sonnet MUST NOT be called on insufficient-signal path; "
        f"got {sonnet_call_count} call(s)"
    )
    sweep_rows = _added_sweep_rows(sess)
    assert len(sweep_rows) == 1
    row = sweep_rows[0]
    assert row.status == "partial", (
        f"Insufficient-signal path must produce status='partial' "
        f"(D-03b backfill window pattern); got {row.status!r}"
    )
    assert INSUFFICIENT_SIGNAL_FALLBACK in (row.content_angles_md or ""), (
        f"content_angles_md must contain INSUFFICIENT_SIGNAL_FALLBACK copy; "
        f"got {row.content_angles_md!r}"
    )


@pytest.mark.asyncio
async def test_juno_x_query_passed_to_fetch_top_x_posts(monkeypatch):
    """JSWEEP-02 — fetch_top_x_posts is called with JUNO_SWEEPER_X_QUERY,
    NOT with Seva's X_SEARCH_QUERY (D-10 zero-regression — wrong query
    would leak Seva's gold-cashtag search into Juno's defence sweep)."""
    from agents import juno_weekly_sweeper as jws_module
    from companies.juno.x_queries import JUNO_SWEEPER_X_QUERY

    fetch_calls: list[str] = []

    async def spy_fetch(query, max_results=100):
        fetch_calls.append(query)
        return _fake_x_posts(5)

    async def fake_virality(session):
        return _fake_viral_stories(5)

    monkeypatch.setattr(jws_module, "fetch_top_x_posts", spy_fetch)
    monkeypatch.setattr(jws_module, "_compute_juno_virality", fake_virality)
    monkeypatch.setattr(
        jws_module,
        "call_with_refusal_guard",
        AsyncMock(return_value=("### Angle 1: foo", {})),
    )
    monkeypatch.setattr(
        jws_module, "_idempotency_skip", AsyncMock(return_value=False)
    )
    _sess, make_ctx = _make_orchestration_session()
    monkeypatch.setattr(jws_module, "AsyncSessionLocal", make_ctx)
    monkeypatch.setattr(
        jws_module, "get_anthropic_client", lambda *a, **kw: MagicMock()
    )

    await jws_module.run_juno_weekly_sweeper()

    assert len(fetch_calls) == 1
    assert fetch_calls[0] == JUNO_SWEEPER_X_QUERY, (
        f"fetch_top_x_posts must be called with JUNO_SWEEPER_X_QUERY (NOT "
        f"Seva's X_SEARCH_QUERY); got {fetch_calls[0]!r}"
    )


@pytest.mark.asyncio
async def test_d10_helper_share_imports_from_seva_module(monkeypatch):
    """D-06 / D-10 — canonical_url and _sunday_of_this_week MUST be imported
    from agents.weekly_sweeper (Seva module) — NOT re-defined in
    juno_weekly_sweeper.

    Verifies the D-06 LOCKED helper-share decision (import-from-Seva path
    rather than duplicate) is honored. If a future refactor copy-pastes
    the helpers into juno_weekly_sweeper instead of importing, this test
    fails loudly."""
    from agents import juno_weekly_sweeper, weekly_sweeper

    # The helpers must be the SAME function object as Seva's (identity, not
    # equality) — which is only true if juno_weekly_sweeper does
    # `from agents.weekly_sweeper import canonical_url, _sunday_of_this_week`.
    assert juno_weekly_sweeper.canonical_url is weekly_sweeper.canonical_url, (
        "D-06 LOCKED contract violated: canonical_url must be imported from "
        "agents.weekly_sweeper, not redefined in juno_weekly_sweeper"
    )
    assert (
        juno_weekly_sweeper._sunday_of_this_week
        is weekly_sweeper._sunday_of_this_week
    ), (
        "D-06 LOCKED contract violated: _sunday_of_this_week must be imported "
        "from agents.weekly_sweeper, not redefined in juno_weekly_sweeper"
    )
