"""
Tests for Senior Agent — digest-only surface (post-sn9 scope).

Trimmed in quick 260420-sn9: dedup, queue-cap, breaking-news/expiry/engagement
alert, expiry sweep, and process_new_item tests deleted (17 tests removed)
alongside the implementation in agents/senior_agent.py. Remaining tests cover
SENR-06, SENR-07, SENR-08 (morning digest assembly + WhatsApp dispatch) and
WHAT-01 (free-form digest message).
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Set required env vars before any imports
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://fake-pooler.neon.tech/db?sslmode=require"
)
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test-fake")
os.environ.setdefault("TWILIO_ACCOUNT_SID", "x")
os.environ.setdefault("TWILIO_AUTH_TOKEN", "x")
os.environ.setdefault("TWILIO_WHATSAPP_FROM", "whatsapp:+1x")
os.environ.setdefault("DIGEST_WHATSAPP_TO", "whatsapp:+1x")
os.environ.setdefault("X_API_BEARER_TOKEN", "test-bearer-token")
os.environ.setdefault("X_API_KEY", "test-key")
os.environ.setdefault("X_API_SECRET", "test-secret")
os.environ.setdefault("SERPAPI_API_KEY", "x")
os.environ.setdefault("FRONTEND_URL", "https://x.com")


# --- SENR-06/SENR-07: Morning Digest ---


def test_morning_digest_assembly():
    """SENR-06/SENR-07: Morning digest assembles correct JSONB with top stories, counts, snapshot."""
    import asyncio
    import uuid
    from decimal import Decimal
    from datetime import datetime, timezone
    from unittest.mock import AsyncMock, MagicMock
    from agents.senior_agent import SeniorAgent

    now = datetime.now(timezone.utc)

    # --- Build mock DraftItems for approved (3), rejected (1), expired (2) ---

    def make_item(item_id, status, score, platform, source_account, rationale, source_url):
        item = MagicMock()
        item.id = item_id
        item.status = status
        item.score = Decimal(str(score))
        item.platform = platform
        item.source_account = source_account
        item.rationale = rationale
        item.source_url = source_url
        item.expires_at = now
        return item

    # These items document the expected counts; the digest aggregates only via count queries,
    # so the individual objects are not referenced — keep them as documentation via `_` names.
    _approved_1 = make_item(
        uuid.uuid4(),
        "approved",
        9.0,
        "twitter",
        "@Kitco",
        "Gold hits high. Details here.",
        "https://ex.com/1",
    )  # noqa: E501
    _approved_2 = make_item(
        uuid.uuid4(),
        "edited_approved",
        8.5,
        "instagram",
        "@GoldInvestor",
        "Fed signals rate cut. Market reacts.",
        "https://ex.com/2",
    )  # noqa: E501
    _approved_3 = make_item(
        uuid.uuid4(),
        "approved",
        7.8,
        "content",
        "@NewsDesk",
        "Mining output rises quarterly. Analysts bullish.",
        "https://ex.com/3",
    )  # noqa: E501
    _rejected_1 = make_item(
        uuid.uuid4(),
        "rejected",
        5.0,
        "twitter",
        "@Spam",
        "Not relevant. Discard.",
        "https://ex.com/4",
    )  # noqa: E501
    _expired_1 = make_item(
        uuid.uuid4(),
        "expired",
        4.0,
        "twitter",
        "@Old",
        "Old story expired. Not shown.",
        "https://ex.com/5",
    )  # noqa: E501
    _expired_2 = make_item(
        uuid.uuid4(),
        "expired",
        3.5,
        "twitter",
        "@Old2",
        "Another expired. Done.",
        "https://ex.com/6",
    )  # noqa: E501

    # Top 5 stories query: 3 items by score DESC
    top_story_1 = make_item(
        uuid.uuid4(),
        "approved",
        9.0,
        "twitter",
        "@Kitco",
        "Gold hits all-time high. Markets rally strongly.",
        "https://ex.com/t1",
    )
    top_story_2 = make_item(
        uuid.uuid4(),
        "approved",
        8.5,
        "instagram",
        "@GoldInvestor",
        "Central banks buying gold. Record purchases.",
        "https://ex.com/t2",
    )
    top_story_3 = make_item(
        uuid.uuid4(),
        "pending",
        7.0,
        "twitter",
        "@AuAnalyst",
        "Gold ETF inflows surge. Demand robust.",
        "https://ex.com/t3",
    )

    # Priority alert: highest-scoring pending item
    priority_item = make_item(
        uuid.uuid4(),
        "pending",
        9.0,
        "twitter",
        "@Breaking",
        "Breaking gold news right now. Act fast.",
        "https://ex.com/p1",
    )

    mock_session = AsyncMock()

    # execute() call sequence:
    # 1. yesterday approved count → scalar_one() = 3
    # 2. yesterday rejected count → scalar_one() = 1
    # 3. yesterday expired count → scalar_one() = 2
    # 4. top 5 stories → scalars().all() = [top_story_1, top_story_2, top_story_3]
    # 5. queue snapshot → all() = [("twitter", 3), ("instagram", 1), ("content", 1)]
    # 6. priority alert → scalar_one_or_none() = priority_item

    approved_result = MagicMock()
    approved_result.scalar_one.return_value = 3

    rejected_result = MagicMock()
    rejected_result.scalar_one.return_value = 1

    expired_result = MagicMock()
    expired_result.scalar_one.return_value = 2

    top_stories_result = MagicMock()
    top_stories_result.scalars.return_value.all.return_value = [
        top_story_1,
        top_story_2,
        top_story_3,
    ]

    queue_snapshot_result = MagicMock()
    queue_snapshot_result.all.return_value = [("twitter", 3), ("instagram", 1), ("content", 1)]

    priority_result = MagicMock()
    priority_result.scalar_one_or_none.return_value = priority_item

    mock_session.execute = AsyncMock(
        side_effect=[
            approved_result,
            rejected_result,
            expired_result,
            top_stories_result,
            queue_snapshot_result,
            priority_result,
        ]
    )

    async def run_test():
        agent = SeniorAgent()
        return await agent._assemble_digest(mock_session)

    digest = asyncio.run(run_test())

    # top_stories: list of 3, each with correct keys
    assert isinstance(digest["top_stories"], list), "top_stories must be a list"
    assert len(digest["top_stories"]) == 3, (
        f"Expected 3 top stories, got {len(digest['top_stories'])}"
    )
    for story in digest["top_stories"]:
        assert "headline" in story, f"Missing 'headline' key in story: {story}"
        assert "source_account" in story, "Missing 'source_account' key"
        assert "platform" in story, "Missing 'platform' key"
        assert "score" in story, "Missing 'score' key"
        assert "source_url" in story, "Missing 'source_url' key"

    # queue_snapshot: correct platform counts and total
    qs = digest["queue_snapshot"]
    assert qs == {"twitter": 3, "instagram": 1, "content": 1, "total": 5}, (
        f"queue_snapshot mismatch: {qs}"
    )

    # yesterday counts
    assert digest["yesterday_approved"]["count"] == 3, (
        f"Expected approved count 3, got {digest['yesterday_approved']['count']}"
    )
    assert digest["yesterday_rejected"]["count"] == 1, (
        f"Expected rejected count 1, got {digest['yesterday_rejected']['count']}"
    )
    assert digest["yesterday_expired"]["count"] == 2, (
        f"Expected expired count 2, got {digest['yesterday_expired']['count']}"
    )

    # priority_alert: has required keys, correct score
    pa = digest["priority_alert"]
    assert pa is not None, "priority_alert must not be None"
    for key in ("id", "platform", "score", "headline", "expires_at", "source_url"):
        assert key in pa, f"Missing key '{key}' in priority_alert: {pa}"
    assert pa["score"] == 9.0, f"Expected priority_alert score 9.0, got {pa['score']}"


def test_morning_digest_whatsapp_send():
    """WHAT-01/WHAT-05: Morning digest sends WhatsApp free-form message including date, queue total, and dashboard URL.
    Updated in Phase 10-03: uses send_whatsapp_message() (not send_whatsapp_template)."""
    import asyncio
    from datetime import date
    from unittest.mock import AsyncMock, MagicMock, patch
    from agents.senior_agent import SeniorAgent

    # Known digest dict returned by _assemble_digest
    known_digest = {
        "top_stories": [
            {
                "headline": "Gold hits all-time high.",
                "source_account": "@Kitco",
                "platform": "twitter",
                "score": 9.0,
                "source_url": "https://ex.com/1",
            },
            {
                "headline": "Central banks buying gold.",
                "source_account": "@GoldInvestor",
                "platform": "instagram",
                "score": 8.5,
                "source_url": "https://ex.com/2",
            },
            {
                "headline": "Gold ETF inflows surge.",
                "source_account": "@AuAnalyst",
                "platform": "twitter",
                "score": 7.0,
                "source_url": "https://ex.com/3",
            },
        ],
        "queue_snapshot": {"twitter": 3, "instagram": 1, "content": 1, "total": 5},
        "yesterday_approved": {"count": 3, "items": []},
        "yesterday_rejected": {"count": 1},
        "yesterday_expired": {"count": 2},
        "priority_alert": {
            "id": "some-uuid",
            "platform": "twitter",
            "score": 9.0,
            "source_account": "@Breaking",
            "headline": "Breaking gold news right now.",
            "expires_at": None,
            "source_url": "https://ex.com/p1",
        },
    }

    mock_run = MagicMock()
    mock_run.status = "running"

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    added_objects = []
    mock_session.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))

    async def run_test():
        agent = SeniorAgent()

        async def mock_assemble_digest(session):
            return known_digest

        async def mock_get_config(session, key, default):
            if key == "dashboard_url":
                return "https://app.sevamining.com"
            return default

        with (
            patch.object(agent, "_assemble_digest", new=mock_assemble_digest),
            patch.object(agent, "_get_config", new=mock_get_config),
            patch("agents.senior_agent.AsyncSessionLocal") as mock_session_local,
            patch("agents.senior_agent.AgentRun", return_value=mock_run),
            patch("agents.senior_agent.send_whatsapp_message", new_callable=AsyncMock) as mock_send,
        ):
            mock_session_local.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_local.return_value.__aexit__ = AsyncMock(return_value=False)

            await agent.run_morning_digest()

            # Assert send_whatsapp_message called once with a free-form string
            mock_send.assert_called_once()
            call_args = mock_send.call_args
            message = call_args[0][0]

            # Must contain date, queue total, approved count, and dashboard URL
            today_str = date.today().isoformat()
            assert today_str in message, (
                f"Expected today's date '{today_str}' in message, got: {message!r}"
            )
            assert "5" in message, f"Expected queue total '5' in message, got: {message!r}"
            assert "3" in message, f"Expected approved count '3' in message, got: {message!r}"
            assert "https://app.sevamining.com" in message, (
                f"Expected dashboard URL in message, got: {message!r}"
            )
            assert "Morning Digest" in message, (
                f"Expected 'Morning Digest' header in message, got: {message!r}"
            )

        # Assert DailyDigest was added to the session
        daily_digest_objects = [obj for obj in added_objects if type(obj).__name__ == "DailyDigest"]
        assert len(daily_digest_objects) >= 1, (
            f"Expected DailyDigest to be added to session, added_objects: {[type(o).__name__ for o in added_objects]}"
        )

        # Assert whatsapp_sent_at is set (not None)
        digest_record = daily_digest_objects[0]
        assert digest_record.whatsapp_sent_at is not None, (
            "Expected DailyDigest.whatsapp_sent_at to be set after send"
        )

    asyncio.run(run_test())


# ---------------------------------------------------------------------------
# Phase 10-03 — Morning digest WhatsApp tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_morning_digest_calls_send_whatsapp_message():
    """run_morning_digest uses send_whatsapp_message (not send_whatsapp_template)."""
    from agents.senior_agent import SeniorAgent
    from unittest.mock import patch, AsyncMock, MagicMock

    agent = SeniorAgent()

    mock_digest = {
        "top_stories": [{"headline": "Gold hits $3000", "score": 9.5}],
        "queue_snapshot": {"total": 5},
        "yesterday_approved": {"count": 3},
        "yesterday_rejected": {"count": 1},
        "yesterday_expired": {"count": 2},
        "priority_alert": None,
    }

    with (
        patch.object(agent, "_assemble_digest", new_callable=AsyncMock, return_value=mock_digest),
        patch.object(
            agent, "_get_config", new_callable=AsyncMock, return_value="https://app.sevamining.com"
        ),
        patch("agents.senior_agent.AsyncSessionLocal") as mock_session_cls,
        patch("agents.senior_agent.DailyDigest") as mock_digest_cls,
        patch("agents.senior_agent.AgentRun") as mock_run_cls,
        patch("agents.senior_agent.send_whatsapp_message", new_callable=AsyncMock) as mock_wa,
    ):
        mock_session = AsyncMock()
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_session.commit = AsyncMock()
        mock_session.flush = AsyncMock()
        mock_session.add = MagicMock()

        mock_run = MagicMock()
        mock_run_cls.return_value = mock_run

        mock_digest_record = MagicMock()
        mock_digest_cls.return_value = mock_digest_record

        await agent.run_morning_digest()

    mock_wa.assert_called_once()
    msg = mock_wa.call_args[0][0]
    assert "Morning Digest" in msg
    assert "5" in msg  # queue total
    assert "3" in msg  # approved


@pytest.mark.asyncio
async def test_morning_digest_whatsapp_failure_still_commits():
    """WhatsApp failure in run_morning_digest does not prevent DailyDigest commit."""
    from agents.senior_agent import SeniorAgent
    from unittest.mock import patch, AsyncMock, MagicMock

    agent = SeniorAgent()

    mock_digest = {
        "top_stories": [],
        "queue_snapshot": {"total": 0},
        "yesterday_approved": {"count": 0},
        "yesterday_rejected": {"count": 0},
        "yesterday_expired": {"count": 0},
        "priority_alert": None,
    }

    with (
        patch.object(agent, "_assemble_digest", new_callable=AsyncMock, return_value=mock_digest),
        patch.object(
            agent, "_get_config", new_callable=AsyncMock, return_value="https://app.sevamining.com"
        ),
        patch("agents.senior_agent.AsyncSessionLocal") as mock_session_cls,
        patch("agents.senior_agent.DailyDigest"),
        patch("agents.senior_agent.AgentRun") as mock_run_cls,
        patch("agents.senior_agent.send_whatsapp_message", side_effect=Exception("Twilio down")),
    ):
        mock_session = AsyncMock()
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_session.commit = AsyncMock()
        mock_session.flush = AsyncMock()
        mock_session.add = MagicMock()

        mock_run = MagicMock()
        mock_run_cls.return_value = mock_run

        await agent.run_morning_digest()

    # commit must have been called (digest record persisted)
    assert mock_session.commit.called
    # run status should be "completed" (WhatsApp failure is non-fatal)
    assert mock_run.status == "completed"


# ---------------------------------------------------------------------------
# Debug session twilio-morning-digest-not-delivering (2026-04-24):
# run.notes must capture delivery status so a multi-week silent failure
# can be diagnosed by querying agent_runs.notes alone.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_notes_captures_twilio_sid_on_success():
    """On successful send, run.notes must include the Twilio SID."""
    from agents.senior_agent import SeniorAgent
    from unittest.mock import patch, AsyncMock, MagicMock

    agent = SeniorAgent()

    mock_digest = {
        "top_stories": [],
        "queue_snapshot": {"total": 0},
        "yesterday_approved": {"count": 0},
        "yesterday_rejected": {"count": 0},
        "yesterday_expired": {"count": 0},
        "priority_alert": None,
    }

    with (
        patch.object(agent, "_assemble_digest", new_callable=AsyncMock, return_value=mock_digest),
        patch.object(
            agent, "_get_config", new_callable=AsyncMock, return_value="https://app.sevamining.com"
        ),
        patch("agents.senior_agent.AsyncSessionLocal") as mock_session_cls,
        patch("agents.senior_agent.DailyDigest"),
        patch("agents.senior_agent.AgentRun") as mock_run_cls,
        patch(
            "agents.senior_agent.send_whatsapp_message",
            new_callable=AsyncMock,
            return_value="SMabc123",
        ),
    ):
        mock_session = AsyncMock()
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_session.commit = AsyncMock()
        mock_session.flush = AsyncMock()
        mock_session.add = MagicMock()

        mock_run = MagicMock()
        mock_run_cls.return_value = mock_run

        await agent.run_morning_digest()

    assert isinstance(mock_run.notes, str)
    assert "whatsapp_sent" in mock_run.notes
    assert "SMabc123" in mock_run.notes


@pytest.mark.asyncio
async def test_run_notes_captures_skip_reason_when_creds_missing():
    """When send_whatsapp_message returns None (missing creds), run.notes
    must record 'whatsapp_skipped' with an actionable reason.
    """
    from agents.senior_agent import SeniorAgent
    from unittest.mock import patch, AsyncMock, MagicMock

    agent = SeniorAgent()

    mock_digest = {
        "top_stories": [],
        "queue_snapshot": {"total": 0},
        "yesterday_approved": {"count": 0},
        "yesterday_rejected": {"count": 0},
        "yesterday_expired": {"count": 0},
        "priority_alert": None,
    }

    with (
        patch.object(agent, "_assemble_digest", new_callable=AsyncMock, return_value=mock_digest),
        patch.object(
            agent, "_get_config", new_callable=AsyncMock, return_value="https://app.sevamining.com"
        ),
        patch("agents.senior_agent.AsyncSessionLocal") as mock_session_cls,
        patch("agents.senior_agent.DailyDigest"),
        patch("agents.senior_agent.AgentRun") as mock_run_cls,
        patch(
            "agents.senior_agent.send_whatsapp_message",
            new_callable=AsyncMock,
            return_value=None,
        ),
    ):
        mock_session = AsyncMock()
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_session.commit = AsyncMock()
        mock_session.flush = AsyncMock()
        mock_session.add = MagicMock()

        mock_run = MagicMock()
        mock_run_cls.return_value = mock_run

        await agent.run_morning_digest()

    assert isinstance(mock_run.notes, str)
    assert "whatsapp_skipped" in mock_run.notes
    assert "credentials" in mock_run.notes.lower()


# ---------------------------------------------------------------------------
# quick-260424-i8b: _assemble_digest must exclude firehose content types
# ---------------------------------------------------------------------------


def test_assemble_digest_excludes_firehose_content_types():
    """_assemble_digest with excluded_content_types filters out breaking_news and thread items.

    Seeds mock DB with:
    - 3 DraftItem rows paired with ContentBundle content_type IN
      ('breaking_news', 'thread', 'breaking_news') — should be EXCLUDED
    - 2 DraftItem rows paired with ContentBundle content_type IN
      ('infographic', 'quote') — should be INCLUDED

    Asserts that yesterday_approved["count"] == 2 (not 5) and top_stories
    contains only the 2 non-firehose items.
    """
    import asyncio
    import uuid
    from decimal import Decimal
    from datetime import datetime, timezone
    from unittest.mock import AsyncMock, MagicMock
    from agents.senior_agent import SeniorAgent

    now = datetime.now(timezone.utc)

    # The _assemble_digest method uses mock session.execute() calls in order:
    # 1. approved count
    # 2. rejected count
    # 3. expired count
    # 4. top_stories
    # 5. queue snapshot
    # 6. priority alert
    #
    # The filter test: when SeniorAgent is instantiated with
    # excluded_content_types=frozenset({"breaking_news", "thread"}), the queries
    # must NOT include breaking_news/thread items. We verify this by checking the
    # SQL generated includes a subquery/join filtering on content_type.
    #
    # Strategy: use a real session mock but capture the SQL statements to assert
    # the exclusion filter is present in the approved/rejected/expired/top_stories
    # queries.

    def make_item(item_id, status, score, platform, source_account, rationale, source_url):
        item = MagicMock()
        item.id = item_id
        item.status = status
        item.score = Decimal(str(score))
        item.platform = platform
        item.source_account = source_account
        item.rationale = rationale
        item.source_url = source_url
        item.created_at = now
        item.expires_at = now
        item.source_text = None
        return item

    infographic_item = make_item(
        uuid.uuid4(), "approved", 8.0, "content", "@InfographicDesk",
        "Gold mining output up 12% QoQ. Strong performance.", "https://ex.com/infographic1"
    )
    quote_item = make_item(
        uuid.uuid4(), "approved", 7.5, "content", "@QuoteDesk",
        "Central banks added 100t gold in Q1. Record pace.", "https://ex.com/quote1"
    )

    mock_session = AsyncMock()

    # Capture which SQL statements are executed so we can verify the filter
    executed_stmts: list = []

    async def capturing_execute(stmt, *args, **kwargs):
        executed_stmts.append(stmt)
        # Return appropriate mock results based on call order
        call_n = len(executed_stmts)
        if call_n == 1:  # approved count — should return 2 (only non-firehose)
            r = MagicMock()
            r.scalar_one.return_value = 2
            return r
        elif call_n == 2:  # rejected count
            r = MagicMock()
            r.scalar_one.return_value = 0
            return r
        elif call_n == 3:  # expired count
            r = MagicMock()
            r.scalar_one.return_value = 0
            return r
        elif call_n == 4:  # top_stories
            r = MagicMock()
            r.scalars.return_value.all.return_value = [infographic_item, quote_item]
            return r
        elif call_n == 5:  # queue snapshot
            r = MagicMock()
            r.all.return_value = [("content", 2)]
            return r
        else:  # priority alert
            r = MagicMock()
            r.scalar_one_or_none.return_value = None
            return r

    mock_session.execute = capturing_execute

    async def run_test():
        agent = SeniorAgent(excluded_content_types=frozenset({"breaking_news", "thread"}))
        return await agent._assemble_digest(mock_session)

    digest = asyncio.run(run_test())

    # The mock returns what the FILTERED DB would return (2 approved, not 5).
    # The real test is that the SeniorAgent.__init__ accepts the kwarg and
    # that the SQL statements include the content_type exclusion filter.
    assert digest["yesterday_approved"]["count"] == 2, (
        f"Expected approved count 2 (firehose excluded), got {digest['yesterday_approved']['count']}"
    )
    assert len(digest["top_stories"]) == 2, (
        f"Expected 2 top stories (only non-firehose), got {len(digest['top_stories'])}"
    )

    # Verify filter was applied to SQL — all executed statements should reference
    # content_type or contain a subquery that excludes firehose content types.
    # Compile all statements and check for content_type references in the approved/
    # rejected/expired/top_stories queries (indices 0, 1, 2, 3).
    assert len(executed_stmts) >= 4, (
        f"Expected at least 4 execute() calls, got {len(executed_stmts)}"
    )
    for i, stmt in enumerate(executed_stmts[:4]):
        compiled = str(stmt.compile(compile_kwargs={"literal_binds": False}))
        assert "content_type" in compiled.lower() or "content_bundles" in compiled.lower(), (
            f"Query {i+1} (approved/rejected/expired/top_stories) must reference "
            f"content_type or content_bundles for the exclusion filter. "
            f"Compiled SQL: {compiled[:300]}"
        )
