"""Juno daily_summary stub entry point (TENANT-08).

v3.0 Phase 9 Wave 2 — production code lives at
``scheduler/agents/daily_summary.py::run_juno_daily_summary``.

The stub writes a `daily_summaries` row with:
    company_id='juno'
    status='partial'
    gold_news_md=None
    error_text containing 'Juno content pipeline pending' or 'Phase 10'
and a corresponding `agent_runs` row:
    agent_name='juno_daily_summary'
    status='completed' (not 'running'/'failed' — writing the partial row IS success)
    notes JSONB containing {"company_id": "juno"}

Idempotency: a second call within the same 30-minute window must NOT create
a second row (per-company check via scoped_summaries('juno')).

Test approach (matches scheduler/tests/agents/test_daily_summary.py): mock
AsyncSessionLocal so the test runs against captured ORM constructor args
without needing a real Neon Postgres. The scheduler test layer doesn't have
a SQLite fixture (Postgres-only types JSONB + UUID); mocking matches the
existing daily_summary test pattern.
"""
from __future__ import annotations

import json
import os
import sys
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


def _mock_session_factory(idempotency_returns_existing: bool = False):
    """Build a mock AsyncSessionLocal that:

    - Returns ``some-uuid`` from idempotency_skip's SELECT when
      ``idempotency_returns_existing=True`` (forces a skip path).
    - Otherwise returns None from idempotency check + captures every
      session.add() call so the test can inspect the ORM rows constructed.

    Both pathways use a single shared MagicMock as the AgentRun row
    (`session.get(AgentRun, ...)` returns it) so the test can assert
    `.status` was updated to 'completed' or 'failed'.
    """
    added_rows: list = []

    # Mock the AgentRun row returned by session.get(AgentRun, ...) after
    # session.refresh(). Track its mutations.
    agent_run_mock = MagicMock()
    agent_run_mock.id = "fake-agent-run-uuid"
    agent_run_mock.status = "running"
    agent_run_mock.errors = None
    agent_run_mock.notes = None
    agent_run_mock.ended_at = None

    # Idempotency SELECT result
    idempotency_result = MagicMock()
    idempotency_result.scalar_one_or_none.return_value = (
        "some-existing-uuid" if idempotency_returns_existing else None
    )

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=idempotency_result)
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()
    mock_session.get = AsyncMock(return_value=agent_run_mock)

    def add(row):
        added_rows.append(row)

    mock_session.add = MagicMock(side_effect=add)

    session_cm = MagicMock()
    session_cm.__aenter__ = AsyncMock(return_value=mock_session)
    session_cm.__aexit__ = AsyncMock(return_value=False)
    factory = MagicMock(return_value=session_cm)
    return factory, mock_session, added_rows, agent_run_mock


@pytest.mark.asyncio
async def test_run_juno_daily_summary_writes_row(monkeypatch):
    """v3.0 Phase 10 — after run_juno_daily_summary() returns, exactly 1 Juno
    daily_summaries row and 1 agent_runs row were constructed with the
    expected structural fields.

    Replaces the Phase 9 stub-only assertions (phase_10_pending,
    gold_news_md is None) — those described the empty-stub behavior that
    Phase 10 deliberately replaces with real synthesis. The structural
    invariants (1 row each, company_id='juno', agent_name correct,
    notes.company_id='juno', status in valid set) are preserved.
    """
    from agents.daily_summary import run_juno_daily_summary
    from models.agent_run import AgentRun
    from models.daily_summary import DailySummary

    factory, _session, added_rows, agent_run_mock = _mock_session_factory(
        idempotency_returns_existing=False
    )

    # Empty feed for every feedparser.parse call → defence ingestion produces
    # zero entries → status='failed' for this synthetic test fire (no Sonnet
    # call needed). This keeps the test offline + deterministic.
    empty_feed = MagicMock(bozo=0, entries=[])

    with patch("agents.daily_summary.AsyncSessionLocal", factory), patch(
        "feedparser.parse", return_value=empty_feed
    ), patch("agents.daily_summary.get_anthropic_client") as MockClient, patch(
        "agents.daily_summary.serpapi.Client"
    ) as MockSerp:
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock()  # never called in this test
        mock_client.messages.parse = AsyncMock()
        MockClient.return_value = mock_client
        MockSerp.return_value.search = MagicMock(return_value={"news_results": []})
        await run_juno_daily_summary()

    # Find the AgentRun + DailySummary rows that were session.add()-ed.
    agent_run_rows = [r for r in added_rows if isinstance(r, AgentRun)]
    summary_rows = [r for r in added_rows if isinstance(r, DailySummary)]

    assert len(agent_run_rows) == 1, (
        f"Expected 1 AgentRun row added; got {len(agent_run_rows)}"
    )
    assert len(summary_rows) == 1, (
        f"Expected 1 DailySummary row added; got {len(summary_rows)}"
    )

    summary = summary_rows[0]
    assert summary.company_id == "juno", (
        f"Juno run must set company_id='juno', got {summary.company_id!r}"
    )
    # Phase 10 valid statuses: 'completed' | 'partial' | 'failed'. With empty
    # defence feeds in this test, the orchestrator maps to 'failed'.
    assert summary.status in {"completed", "partial", "failed"}, (
        f"Juno status must be one of completed/partial/failed; "
        f"got {summary.status!r}"
    )
    assert summary.status == "failed", (
        f"Empty defence feeds → status='failed' (per D-12); "
        f"got {summary.status!r}"
    )

    # AgentRun row carries the correct agent_name + notes JSON.
    agent_run = agent_run_rows[0]
    assert agent_run.agent_name == "juno_daily_summary", (
        f"agent_name must be 'juno_daily_summary', got {agent_run.agent_name!r}"
    )
    notes_payload = json.loads(agent_run.notes)
    assert notes_payload.get("company_id") == "juno", (
        f"agent_runs.notes must carry company_id='juno' (D-08 per-tenant "
        f"telemetry); got {notes_payload}"
    )

    # On status='failed', the mocked AgentRun (session.get) must have been
    # transitioned to 'failed' (matches overall row status mapping).
    assert agent_run_mock.status == "failed", (
        f"juno_daily_summary agent_run.status must be 'failed' when defence "
        f"feeds produce zero entries; got {agent_run_mock.status!r}"
    )


@pytest.mark.asyncio
async def test_run_juno_daily_summary_idempotency(caplog):
    """When idempotency check returns an existing row, run_juno_daily_summary
    must log 'idempotency_skip' and return WITHOUT inserting any row.

    Mirrors the Phase 7 D-15 idempotency guard for the Seva daily_summary —
    the per-period uniqueness check applies per-company because the SELECT
    is filtered by company_id via scoped_summaries('juno').
    """
    import logging

    from agents.daily_summary import run_juno_daily_summary
    from models.agent_run import AgentRun
    from models.daily_summary import DailySummary

    factory, _session, added_rows, _agent_run_mock = _mock_session_factory(
        idempotency_returns_existing=True
    )

    with patch("agents.daily_summary.AsyncSessionLocal", factory), caplog.at_level(
        logging.INFO, logger="agents.daily_summary"
    ):
        await run_juno_daily_summary()

    # Must log idempotency_skip
    assert any(
        "juno_daily_summary idempotency_skip" in record.message
        for record in caplog.records
    ), (
        "Expected 'juno_daily_summary idempotency_skip' in log messages, got: "
        + str([r.message for r in caplog.records])
    )

    # Must NOT have added any new rows
    agent_run_rows = [r for r in added_rows if isinstance(r, AgentRun)]
    summary_rows = [r for r in added_rows if isinstance(r, DailySummary)]
    assert len(agent_run_rows) == 0, (
        f"Idempotency violation: AgentRow added despite recent row; "
        f"got {len(agent_run_rows)}"
    )
    assert len(summary_rows) == 0, (
        f"Idempotency violation: DailySummary row added despite recent row; "
        f"got {len(summary_rows)}"
    )


# ---------------------------------------------------------------------------
# Phase 10 Wave 2 GREEN tests — landed in 10-03-PLAN.md alongside the real
# synthesis path in scheduler/agents/daily_summary.py::run_juno_daily_summary.
# Originally Wave 0 RED scaffolds (per-function skips); skips removed in
# Wave 2 task. CLEANUP-01 (Phase 11, 2026-05-19): dropped the
# `_is_juno_morning_fire=True` force-mocks from `test_serpapi_canadian_procurement`
# and `test_canadian_procurement_section` — the SerpAPI dispatch now runs on
# both daily fires per operator preference.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_defence_news_section():
    """Wave 2 (10-03-PLAN.md): JUNO_DEFENCE_FEEDS → Sonnet → 3 bullets in gold_news_md."""
    from agents.daily_summary import run_juno_daily_summary
    from models.daily_summary import DailySummary

    # Mock 5 fake feed entries
    fake_entries = [
        MagicMock(
            title=f"Defence story {i}",
            link=f"https://example.com/{i}",
            summary=f"snippet {i}",
        )
        for i in range(5)
    ]
    fake_feed = MagicMock(bozo=0, entries=fake_entries)

    expected_md = (
        "### 🛡️ Defence News\n"
        "- Item 1 (Defense News)\n"
        "- Item 2 (Breaking Defense)\n"
        "- Item 3 (DefenseScoop)\n"
    )
    sonnet_resp = MagicMock()
    sonnet_resp.content = [MagicMock(text=expected_md)]

    factory, _session, added_rows, _agent_run = _mock_session_factory(
        idempotency_returns_existing=False
    )

    with patch("agents.daily_summary.AsyncSessionLocal", factory), patch(
        "feedparser.parse", return_value=fake_feed
    ), patch(
        "agents.daily_summary.get_anthropic_client"
    ) as MockClient, patch(
        "companies.juno.feeds.JUNO_DEFENCE_FEEDS",
        [(f"src{i}", f"https://example.com/feed{i}") for i in range(5)],
    ):
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=sonnet_resp)
        MockClient.return_value = mock_client
        await run_juno_daily_summary()

    summary_rows = [r for r in added_rows if isinstance(r, DailySummary)]
    assert len(summary_rows) == 1
    assert summary_rows[0].gold_news_md is not None
    assert "Defence News" in summary_rows[0].gold_news_md
    assert summary_rows[0].gold_news_md.count("\n- ") >= 3


@pytest.mark.asyncio
async def test_serpapi_canadian_procurement():
    """Wave 2 (10-03-PLAN.md): SerpAPI hits flow into ontario_law_md."""
    from agents.daily_summary import run_juno_daily_summary
    from models.daily_summary import DailySummary

    fake_hits = [
        {"title": f"Canadian DND contract {i}", "link": f"https://canada.ca/{i}"}
        for i in range(3)
    ]
    serpapi_resp = MagicMock()
    serpapi_resp.get_dict = MagicMock(return_value={"news_results": fake_hits})

    expected_md = (
        "### 🇨🇦 Canadian Procurement\n"
        "- DND awards $200M contract (SerpAPI)\n"
        "- PSPC announces vendor list (SerpAPI)\n"
        "- RCAF procurement notice (SerpAPI)\n"
    )
    sonnet_resp = MagicMock()
    sonnet_resp.content = [MagicMock(text=expected_md)]

    factory, _session, added_rows, _agent_run = _mock_session_factory(
        idempotency_returns_existing=False
    )

    with patch("agents.daily_summary.AsyncSessionLocal", factory), patch(
        "agents.daily_summary.get_anthropic_client"
    ) as MockClient, patch(
        "companies.juno.serpapi.JUNO_SERPAPI_QUERIES",
        ["site:canada.ca defence", "site:war.gov defence"],
    ), patch(
        "serpapi.Client"
    ) as MockSerp:
        # CLEANUP-01 (Phase 11): SerpAPI now runs on BOTH fires (08:05 + 12:05
        # PT) per operator preference. No need to force the morning-fire path —
        # the procurement section dispatches SerpAPI regardless of wall clock.
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=sonnet_resp)
        MockClient.return_value = mock_client
        MockSerp.return_value.search = MagicMock(return_value=serpapi_resp)
        await run_juno_daily_summary()

    summary_rows = [r for r in added_rows if isinstance(r, DailySummary)]
    assert len(summary_rows) == 1
    assert summary_rows[0].ontario_law_md is not None
    assert "Canadian Procurement" in summary_rows[0].ontario_law_md
    assert summary_rows[0].ontario_law_md.count("\n- ") >= 3


@pytest.mark.asyncio
async def test_canadian_procurement_section():
    """Wave 2 (10-03-PLAN.md): end-to-end Canadian Procurement section write."""
    from agents.daily_summary import run_juno_daily_summary
    from models.daily_summary import DailySummary

    sonnet_resp = MagicMock()
    sonnet_resp.content = [
        MagicMock(
            text=(
                "### 🇨🇦 Canadian Procurement\n"
                "- DND signs $1B Boeing contract (Canada.ca)\n"
                "- PSPC vendor list update (canadiandefencereview.com)\n"
                "- Lagassé commentary on NORAD modernization (Substack)\n"
            )
        )
    ]

    factory, _session, added_rows, _agent_run = _mock_session_factory(
        idempotency_returns_existing=False
    )

    with patch("agents.daily_summary.AsyncSessionLocal", factory), patch(
        "agents.daily_summary.get_anthropic_client"
    ) as MockClient:
        # CLEANUP-01 (Phase 11): morning-fire mock no longer required —
        # _build_juno_canadian_procurement_section runs on both fires.
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=sonnet_resp)
        MockClient.return_value = mock_client
        await run_juno_daily_summary()

    summary_rows = [r for r in added_rows if isinstance(r, DailySummary)]
    assert len(summary_rows) == 1
    assert summary_rows[0].ontario_law_md is not None
    assert "Canadian Procurement" in summary_rows[0].ontario_law_md
    # Verify structured-bullets format
    assert "- " in summary_rows[0].ontario_law_md


@pytest.mark.asyncio
async def test_world_events_section_with_haiku_filter():
    """Wave 2 (10-03-PLAN.md): Haiku classifier filter → Sonnet → ontario_stats_md."""
    from agents.daily_summary import run_juno_daily_summary
    from agents.juno_relevance import DefenceRelevance
    from models.daily_summary import DailySummary

    # 10 fake world-news entries
    fake_entries = [
        MagicMock(
            title=f"World event {i}",
            link=f"https://reuters.com/{i}",
            summary=f"world snippet {i}",
        )
        for i in range(10)
    ]
    fake_feed = MagicMock(bozo=0, entries=fake_entries)

    # 4 above threshold, 6 below
    classifier_results = [
        DefenceRelevance(
            is_relevant=True if i < 4 else False,
            category="active_conflict" if i < 4 else "not_relevant",
            confidence=0.85 if i < 4 else 0.5,
            reasoning=f"reason {i}",
        )
        for i in range(10)
    ]

    expected_md = (
        "### 🌐 World Events Relevant to Defence\n"
        "- Event 1 (Reuters)\n"
        "- Event 2 (Reuters)\n"
        "- Event 3 (Reuters)\n"
        "- Event 4 (Reuters)\n"
    )
    sonnet_resp = MagicMock()
    sonnet_resp.content = [MagicMock(text=expected_md)]

    factory, _session, added_rows, _agent_run = _mock_session_factory(
        idempotency_returns_existing=False
    )

    classifier_responses = [
        MagicMock(parsed_output=r) for r in classifier_results
    ]

    with patch("agents.daily_summary.AsyncSessionLocal", factory), patch(
        "feedparser.parse", return_value=fake_feed
    ), patch(
        "agents.daily_summary.get_anthropic_client"
    ) as MockClient:
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=sonnet_resp)
        mock_client.messages.parse = AsyncMock(side_effect=classifier_responses)
        MockClient.return_value = mock_client
        await run_juno_daily_summary()

    summary_rows = [r for r in added_rows if isinstance(r, DailySummary)]
    assert len(summary_rows) == 1
    assert summary_rows[0].ontario_stats_md is not None
    assert "World Events" in summary_rows[0].ontario_stats_md
    # Only 4 above-threshold entries should appear
    assert summary_rows[0].ontario_stats_md.count("\n- ") == 4


@pytest.mark.asyncio
async def test_idempotency_window_with_partial():
    """Wave 2 (10-03-PLAN.md): second call within 30 min returns without writing duplicate."""
    from agents.daily_summary import run_juno_daily_summary
    from models.agent_run import AgentRun
    from models.daily_summary import DailySummary

    # Idempotency returns existing partial row → no new write
    factory, _session, added_rows, _agent_run = _mock_session_factory(
        idempotency_returns_existing=True
    )

    with patch("agents.daily_summary.AsyncSessionLocal", factory):
        await run_juno_daily_summary()

    agent_run_rows = [r for r in added_rows if isinstance(r, AgentRun)]
    summary_rows = [r for r in added_rows if isinstance(r, DailySummary)]
    assert len(agent_run_rows) == 0
    assert len(summary_rows) == 0
