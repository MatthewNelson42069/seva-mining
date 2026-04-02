"""
Tests for Senior Agent — SENR-01 through SENR-09 and WHAT-01 through WHAT-03/WHAT-05.

Wave 0 state: agents.senior_agent does not exist yet.
All tests are stubs that skip — implementation lands in Waves 1-3 (Plans 02-04).
Each test uses a lazy per-function import so all 19 tests are collectable before
the senior_agent module exists. The pytest.skip() call precedes the import so
Wave 0 stubs always show as 'skipped' rather than 'error'.
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Set required env vars before any imports
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://fake-pooler.neon.tech/db?sslmode=require")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test-fake")
os.environ.setdefault("TWILIO_ACCOUNT_SID", "x")
os.environ.setdefault("TWILIO_AUTH_TOKEN", "x")
os.environ.setdefault("TWILIO_WHATSAPP_FROM", "whatsapp:+1x")
os.environ.setdefault("DIGEST_WHATSAPP_TO", "whatsapp:+1x")
os.environ.setdefault("X_API_BEARER_TOKEN", "test-bearer-token")
os.environ.setdefault("X_API_KEY", "test-key")
os.environ.setdefault("X_API_SECRET", "test-secret")
os.environ.setdefault("APIFY_API_TOKEN", "x")
os.environ.setdefault("SERPAPI_API_KEY", "x")
os.environ.setdefault("FRONTEND_URL", "https://x.com")


# --- SENR-02: Deduplication ---

def test_jaccard_similarity():
    """SENR-02: Jaccard similarity returns correct value for known token sets."""
    from agents.senior_agent import jaccard_similarity

    # Standard overlap: 2 common ("gold", "price") / 4 union ("gold", "price", "surges", "drops")
    result = jaccard_similarity(
        frozenset({"gold", "price", "surges"}),
        frozenset({"gold", "price", "drops"}),
    )
    assert result == 0.5, f"Expected 0.5, got {result}"

    # Empty sets → 0.0 (no divide-by-zero)
    assert jaccard_similarity(frozenset(), frozenset()) == 0.0

    # Identical sets → 1.0
    tokens = frozenset({"gold", "mining", "rally"})
    assert jaccard_similarity(tokens, tokens) == 1.0

    # Completely disjoint sets → 0.0
    assert jaccard_similarity(frozenset({"gold"}), frozenset({"tesla"})) == 0.0


def test_extract_fingerprint_tokens():
    """SENR-02: extract_fingerprint_tokens strips stopwords, keeps cashtags and numbers."""
    from agents.senior_agent import extract_fingerprint_tokens

    # Standard sentence with stopwords "to" and "per"
    tokens = extract_fingerprint_tokens(
        "Gold price surges to $2400 per troy ounce amid central bank buying"
    )
    assert isinstance(tokens, frozenset)
    # Must include meaningful terms
    assert "gold" in tokens
    assert "price" in tokens
    assert "surges" in tokens
    assert "$2400" in tokens
    assert "troy" in tokens
    assert "ounce" in tokens
    assert "amid" in tokens
    assert "central" in tokens
    assert "bank" in tokens
    assert "buying" in tokens
    # Must exclude stopwords
    assert "to" not in tokens
    assert "per" not in tokens

    # Empty string → empty frozenset
    assert extract_fingerprint_tokens("") == frozenset()

    # None → empty frozenset
    assert extract_fingerprint_tokens(None) == frozenset()

    # Cashtag preserved
    cashtag_tokens = extract_fingerprint_tokens("$GLD hits all-time high")
    assert "$gld" in cashtag_tokens


def test_dedup_sets_related_id():
    """SENR-02: Dedup sets related_id when token overlap >= 0.40 threshold."""
    import asyncio
    import uuid
    from datetime import datetime, timezone
    from unittest.mock import AsyncMock, MagicMock, patch
    from agents.senior_agent import SeniorAgent

    older_id = uuid.uuid4()
    newer_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    # Two items with substantially overlapping source_text — should be >= 0.40 Jaccard
    older_item = MagicMock()
    older_item.id = older_id
    older_item.source_text = "Gold price hits $2400 amid central bank buying"
    older_item.rationale = "Strong gold momentum"
    older_item.status = "pending"
    older_item.created_at = now
    older_item.related_id = None

    newer_item = MagicMock()
    newer_item.id = newer_id
    newer_item.source_text = "Gold price reaches $2400 as central banks buy"
    newer_item.rationale = "Strong gold momentum continues"
    newer_item.status = "pending"
    newer_item.created_at = now
    newer_item.related_id = None

    # Mock session
    mock_session = AsyncMock()

    # session.get() returns the newer item when called with (DraftItem, newer_id)
    mock_session.get = AsyncMock(return_value=newer_item)

    # session.execute() returns a result with .scalars().all() = [older_item]
    mock_execute_result = MagicMock()
    mock_execute_result.scalars.return_value.all.return_value = [older_item]
    mock_session.execute = AsyncMock(return_value=mock_execute_result)

    # _get_config returns default threshold
    async def run_test():
        agent = SeniorAgent()

        async def mock_get_config(session, key, default):
            if key == "senior_dedup_threshold":
                return "0.40"
            if key == "senior_dedup_lookback_hours":
                return "24"
            return default

        with patch.object(agent, "_get_config", new=mock_get_config):
            await agent._run_deduplication(mock_session, newer_id)

    asyncio.run(run_test())

    # The newer item's related_id must be set to the older item's id
    assert newer_item.related_id == older_id, (
        f"Expected related_id={older_id}, got {newer_item.related_id}"
    )


def test_dedup_no_match_below_threshold():
    """SENR-02: Dedup does NOT set related_id when overlap < 0.40."""
    import asyncio
    import uuid
    from datetime import datetime, timezone
    from unittest.mock import AsyncMock, MagicMock, patch
    from agents.senior_agent import SeniorAgent

    other_id = uuid.uuid4()
    new_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    # Two items with completely different topics — should be < 0.40 Jaccard
    other_item = MagicMock()
    other_item.id = other_id
    other_item.source_text = "Tesla announces new gigafactory in Berlin Germany"
    other_item.rationale = "EV manufacturing expansion"
    other_item.status = "pending"
    other_item.created_at = now
    other_item.related_id = None

    new_item = MagicMock()
    new_item.id = new_id
    new_item.source_text = "Gold price surges amid Federal Reserve rate decisions"
    new_item.rationale = "Gold rally driven by inflation fears"
    new_item.status = "pending"
    new_item.created_at = now
    new_item.related_id = None

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=new_item)

    mock_execute_result = MagicMock()
    mock_execute_result.scalars.return_value.all.return_value = [other_item]
    mock_session.execute = AsyncMock(return_value=mock_execute_result)

    async def run_test():
        agent = SeniorAgent()

        async def mock_get_config(session, key, default):
            if key == "senior_dedup_threshold":
                return "0.40"
            if key == "senior_dedup_lookback_hours":
                return "24"
            return default

        with patch.object(agent, "_get_config", new=mock_get_config):
            await agent._run_deduplication(mock_session, new_id)

    asyncio.run(run_test())

    # related_id must remain None — no match
    assert new_item.related_id is None, (
        f"Expected related_id=None, got {new_item.related_id}"
    )


# --- SENR-04: Queue Cap ---

def test_queue_cap_accepts_below_cap():
    """SENR-04: Queue cap accepts item when pending count < 15 (no displacement)."""
    import asyncio
    import uuid
    from decimal import Decimal
    from datetime import datetime, timezone, timedelta
    from unittest.mock import AsyncMock, MagicMock, patch
    from agents.senior_agent import SeniorAgent

    new_item_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    # New item with some score
    new_item = MagicMock()
    new_item.id = new_item_id
    new_item.score = Decimal("7.5")
    new_item.expires_at = now + timedelta(hours=5)
    new_item.status = "pending"

    mock_session = AsyncMock()

    # Simulate count query returning 10 (below cap of 15)
    count_result = MagicMock()
    count_result.scalar_one.return_value = 10
    mock_session.execute = AsyncMock(return_value=count_result)

    # session.get returns the new item
    mock_session.get = AsyncMock(return_value=new_item)

    deleted_items = []
    mock_session.delete = AsyncMock(side_effect=lambda item: deleted_items.append(item))

    async def run_test():
        agent = SeniorAgent()

        async def mock_get_config(session, key, default):
            if key == "senior_queue_cap":
                return "15"
            return default

        with patch.object(agent, "_get_config", new=mock_get_config):
            await agent._enforce_queue_cap(mock_session, new_item_id)

    asyncio.run(run_test())

    # Nothing should be deleted — queue is below cap
    assert len(deleted_items) == 0, (
        f"Expected no deletions below cap, but {len(deleted_items)} item(s) were deleted"
    )


def test_queue_cap_displaces_lowest():
    """SENR-04: Queue cap displaces lowest-score item when full and new item scores higher."""
    import asyncio
    import uuid
    from decimal import Decimal
    from datetime import datetime, timezone, timedelta
    from unittest.mock import AsyncMock, MagicMock, patch
    from agents.senior_agent import SeniorAgent

    new_item_id = uuid.uuid4()
    lowest_item_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    # New item with score 9.0 — higher than the lowest existing item (1.0)
    new_item = MagicMock()
    new_item.id = new_item_id
    new_item.score = Decimal("9.0")
    new_item.expires_at = now + timedelta(hours=5)
    new_item.status = "pending"

    # Lowest-scoring existing item (score 1.0)
    lowest_item = MagicMock()
    lowest_item.id = lowest_item_id
    lowest_item.score = Decimal("1.0")
    lowest_item.expires_at = now + timedelta(hours=3)
    lowest_item.status = "pending"

    mock_session = AsyncMock()

    # Count query returns 15 (at cap)
    count_result = MagicMock()
    count_result.scalar_one.return_value = 15

    # Lowest query returns lowest_item
    lowest_result = MagicMock()
    lowest_result.scalar_one_or_none.return_value = lowest_item

    # First execute call = count, second = fetch lowest
    mock_session.execute = AsyncMock(side_effect=[count_result, lowest_result])

    # session.get returns the new item
    mock_session.get = AsyncMock(return_value=new_item)

    deleted_items = []
    mock_session.delete = AsyncMock(side_effect=lambda item: deleted_items.append(item))

    async def run_test():
        agent = SeniorAgent()

        async def mock_get_config(session, key, default):
            if key == "senior_queue_cap":
                return "15"
            return default

        with patch.object(agent, "_get_config", new=mock_get_config):
            await agent._enforce_queue_cap(mock_session, new_item_id)

    asyncio.run(run_test())

    # Lowest-scoring item should be deleted; new item stays
    assert len(deleted_items) == 1, (
        f"Expected 1 deletion, got {len(deleted_items)}"
    )
    assert deleted_items[0].id == lowest_item_id, (
        f"Expected lowest item {lowest_item_id} deleted, got {deleted_items[0].id}"
    )


def test_queue_cap_discards_new_item():
    """SENR-04: Queue cap discards new item when full and new item scores <= lowest."""
    import asyncio
    import uuid
    from decimal import Decimal
    from datetime import datetime, timezone, timedelta
    from unittest.mock import AsyncMock, MagicMock, patch
    from agents.senior_agent import SeniorAgent

    new_item_id = uuid.uuid4()
    lowest_item_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    # New item with score 3.0 — lower than the queue's minimum score (5.0)
    new_item = MagicMock()
    new_item.id = new_item_id
    new_item.score = Decimal("3.0")
    new_item.expires_at = now + timedelta(hours=5)
    new_item.status = "pending"

    # Lowest-scoring existing item (score 5.0 — still higher than new item)
    lowest_item = MagicMock()
    lowest_item.id = lowest_item_id
    lowest_item.score = Decimal("5.0")
    lowest_item.expires_at = now + timedelta(hours=3)
    lowest_item.status = "pending"

    mock_session = AsyncMock()

    count_result = MagicMock()
    count_result.scalar_one.return_value = 15

    lowest_result = MagicMock()
    lowest_result.scalar_one_or_none.return_value = lowest_item

    mock_session.execute = AsyncMock(side_effect=[count_result, lowest_result])
    mock_session.get = AsyncMock(return_value=new_item)

    deleted_items = []
    mock_session.delete = AsyncMock(side_effect=lambda item: deleted_items.append(item))

    async def run_test():
        agent = SeniorAgent()

        async def mock_get_config(session, key, default):
            if key == "senior_queue_cap":
                return "15"
            return default

        with patch.object(agent, "_get_config", new=mock_get_config):
            await agent._enforce_queue_cap(mock_session, new_item_id)

    asyncio.run(run_test())

    # New item should be deleted; lowest existing item stays
    assert len(deleted_items) == 1, (
        f"Expected 1 deletion, got {len(deleted_items)}"
    )
    assert deleted_items[0].id == new_item_id, (
        f"Expected new item {new_item_id} deleted, got {deleted_items[0].id}"
    )


def test_queue_cap_tiebreak_expires_at():
    """SENR-04: Tiebreaking keeps item with later expires_at — soonest-expiring item is displaced."""
    import asyncio
    import uuid
    from decimal import Decimal
    from datetime import datetime, timezone, timedelta
    from unittest.mock import AsyncMock, MagicMock, patch
    from agents.senior_agent import SeniorAgent

    new_item_id = uuid.uuid4()
    soon_item_id = uuid.uuid4()   # expires in 1 hour — should be displaced
    later_item_id = uuid.uuid4()  # expires in 3 hours — should be kept  # noqa: F841
    now = datetime.now(timezone.utc)

    # New item with score 9.0 — higher than existing min score (3.0), so displacement occurs
    new_item = MagicMock()
    new_item.id = new_item_id
    new_item.score = Decimal("9.0")
    new_item.expires_at = now + timedelta(hours=5)
    new_item.status = "pending"

    # Item expiring soonest (1h) — should be the one displaced by ORDER BY score ASC, expires_at ASC
    soon_item = MagicMock()
    soon_item.id = soon_item_id
    soon_item.score = Decimal("3.0")
    soon_item.expires_at = now + timedelta(hours=1)
    soon_item.status = "pending"

    mock_session = AsyncMock()

    count_result = MagicMock()
    count_result.scalar_one.return_value = 15

    # The ORDER BY score ASC, expires_at ASC returns soon_item first (both have score 3.0,
    # soon_item has the earlier/smaller expires_at)
    lowest_result = MagicMock()
    lowest_result.scalar_one_or_none.return_value = soon_item

    mock_session.execute = AsyncMock(side_effect=[count_result, lowest_result])
    mock_session.get = AsyncMock(return_value=new_item)

    deleted_items = []
    mock_session.delete = AsyncMock(side_effect=lambda item: deleted_items.append(item))

    async def run_test():
        agent = SeniorAgent()

        async def mock_get_config(session, key, default):
            if key == "senior_queue_cap":
                return "15"
            return default

        with patch.object(agent, "_get_config", new=mock_get_config):
            await agent._enforce_queue_cap(mock_session, new_item_id)

    asyncio.run(run_test())

    # The item expiring soonest (smallest expires_at) should be displaced
    assert len(deleted_items) == 1, (
        f"Expected 1 deletion, got {len(deleted_items)}"
    )
    assert deleted_items[0].id == soon_item_id, (
        f"Expected soon-expiring item {soon_item_id} deleted, got {deleted_items[0].id}"
    )


# --- SENR-05/SENR-09: Expiry Sweep ---

def test_expiry_sweep_marks_expired():
    """SENR-05/SENR-09: Expiry sweep marks items past expires_at as status='expired'."""
    import asyncio
    from unittest.mock import AsyncMock, MagicMock, patch
    from agents.senior_agent import SeniorAgent

    mock_session = AsyncMock()

    # execute() for the bulk UPDATE returns a result with rowcount=2
    update_result = MagicMock()
    update_result.rowcount = 2

    # Additional execute() calls (expiry alerts, engagement alerts) return safe mocks
    expiry_alert_result = MagicMock()
    expiry_alert_result.scalar_one_or_none.return_value = None
    expiry_alert_result.scalars.return_value.all.return_value = []

    engagement_watchlist_result = MagicMock()
    engagement_watchlist_result.scalars.return_value.all.return_value = []

    engagement_items_result = MagicMock()
    engagement_items_result.scalars.return_value.all.return_value = []

    mock_session.execute = AsyncMock(
        side_effect=[
            update_result,           # bulk UPDATE expired items
            expiry_alert_result,     # expiry alerts config (score threshold)
            expiry_alert_result,     # expiry alerts config (minutes before)
            expiry_alert_result,     # expiry alerts config (dashboard url)
            expiry_alert_result,     # expiry alert candidates query
            engagement_watchlist_result,  # watchlist handles query
            engagement_watchlist_result,  # engagement config (dashboard url)
            engagement_items_result, # engagement alert candidates query
        ]
    )
    mock_session.commit = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()

    # AgentRun mock
    mock_run = MagicMock()
    mock_run.status = "running"

    async def run_test():
        agent = SeniorAgent()

        async def mock_get_config(session, key, default):
            return default

        with patch.object(agent, "_get_config", new=mock_get_config), \
             patch("agents.senior_agent.AsyncSessionLocal") as mock_session_local, \
             patch("agents.senior_agent.AgentRun", return_value=mock_run), \
             patch("agents.senior_agent.send_whatsapp_template", new_callable=AsyncMock):
            mock_session_local.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_local.return_value.__aexit__ = AsyncMock(return_value=False)
            await agent.run_expiry_sweep()

    asyncio.run(run_test())

    # The UPDATE was called — verify execute was invoked
    assert mock_session.execute.called, "Expected session.execute() to be called for bulk UPDATE"
    # run.status should be 'completed' on success
    assert mock_run.status == "completed", f"Expected 'completed', got '{mock_run.status}'"


# --- WHAT-02: Breaking News Alert ---

def test_breaking_news_alert_fires():
    """WHAT-02: Breaking news alert fires when item score >= 8.5."""
    import asyncio
    import uuid
    from decimal import Decimal
    from unittest.mock import AsyncMock, MagicMock, patch
    from agents.senior_agent import SeniorAgent

    item_id = uuid.uuid4()

    item = MagicMock()
    item.id = item_id
    item.score = Decimal("9.0")
    item.rationale = "Gold hits all-time high amid central bank buying. Markets rally."
    item.source_account = "@KitcoNews"
    item.platform = "twitter"

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=item)

    async def run_test():
        agent = SeniorAgent()

        async def mock_get_config(session, key, default):
            if key == "senior_breaking_news_threshold":
                return "8.5"
            if key == "dashboard_url":
                return "https://app.sevamining.com"
            return default

        with patch.object(agent, "_get_config", new=mock_get_config), \
             patch("agents.senior_agent.send_whatsapp_template", new_callable=AsyncMock) as mock_send:
            await agent._check_breaking_news_alert(mock_session, item_id)
            mock_send.assert_called_once_with(
                "breaking_news",
                {
                    "1": "Gold hits all-time high amid central bank buying.",
                    "2": "@KitcoNews",
                    "3": "9.0",
                    "4": "https://app.sevamining.com",
                },
            )

    asyncio.run(run_test())


def test_breaking_news_alert_no_fire():
    """WHAT-02: Breaking news alert does NOT fire when item score < 8.5."""
    import asyncio
    import uuid
    from decimal import Decimal
    from unittest.mock import AsyncMock, MagicMock, patch
    from agents.senior_agent import SeniorAgent

    item_id = uuid.uuid4()

    item = MagicMock()
    item.id = item_id
    item.score = Decimal("7.5")
    item.rationale = "Gold price consolidates after recent gains. Analysts cautious."
    item.source_account = "@GoldInsider"
    item.platform = "twitter"

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=item)

    async def run_test():
        agent = SeniorAgent()

        async def mock_get_config(session, key, default):
            if key == "senior_breaking_news_threshold":
                return "8.5"
            if key == "dashboard_url":
                return "https://app.sevamining.com"
            return default

        with patch.object(agent, "_get_config", new=mock_get_config), \
             patch("agents.senior_agent.send_whatsapp_template", new_callable=AsyncMock) as mock_send:
            await agent._check_breaking_news_alert(mock_session, item_id)
            mock_send.assert_not_called()

    asyncio.run(run_test())


# --- WHAT-03: Expiry Alert ---

def test_expiry_alert_fires():
    """WHAT-03: Expiry alert fires for score >= 7.0 item within 1 hour of expiry."""
    import asyncio
    import uuid
    from decimal import Decimal
    from datetime import datetime, timezone, timedelta
    from unittest.mock import AsyncMock, MagicMock, patch
    from agents.senior_agent import SeniorAgent

    item_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    item = MagicMock()
    item.id = item_id
    item.score = Decimal("8.0")
    item.expires_at = now + timedelta(minutes=30)
    item.alerted_expiry_at = None
    item.platform = "twitter"
    item.rationale = "Gold price breakout above key resistance level. Strong momentum."
    item.source_account = "@KitcoNews"

    mock_session = AsyncMock()

    # Return the candidate item from the expiry alert query
    expiry_result = MagicMock()
    expiry_result.scalars.return_value.all.return_value = [item]
    mock_session.execute = AsyncMock(return_value=expiry_result)

    async def run_test():
        agent = SeniorAgent()

        async def mock_get_config(session, key, default):
            if key == "senior_expiry_alert_score_threshold":
                return "7.0"
            if key == "senior_expiry_alert_minutes_before":
                return "60"
            if key == "dashboard_url":
                return "https://app.sevamining.com"
            return default

        with patch.object(agent, "_get_config", new=mock_get_config), \
             patch("agents.senior_agent.send_whatsapp_template", new_callable=AsyncMock) as mock_send:
            await agent._check_expiry_alerts(mock_session)
            mock_send.assert_called_once()
            call_args = mock_send.call_args
            assert call_args[0][0] == "expiry_alert", f"Expected 'expiry_alert', got {call_args[0][0]}"
            variables = call_args[0][1]
            assert variables["1"] == "twitter"
            assert "4" in variables and variables["4"] == "https://app.sevamining.com"

        # alerted_expiry_at must be set
        assert item.alerted_expiry_at is not None, "Expected alerted_expiry_at to be set"

    asyncio.run(run_test())


def test_expiry_alert_no_double_send():
    """WHAT-03: Expiry alert does NOT fire twice for same item (alerted_expiry_at dedup)."""
    import asyncio
    import uuid
    from decimal import Decimal
    from datetime import datetime, timezone, timedelta
    from unittest.mock import AsyncMock, MagicMock, patch
    from agents.senior_agent import SeniorAgent

    item_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    item = MagicMock()
    item.id = item_id
    item.score = Decimal("8.0")
    item.expires_at = now + timedelta(minutes=30)
    # Already alerted — dedup should prevent re-send
    item.alerted_expiry_at = now - timedelta(minutes=10)
    item.platform = "twitter"
    item.rationale = "Gold price breakout above key resistance level."
    item.source_account = "@KitcoNews"

    mock_session = AsyncMock()

    # The query should NOT return this item (alerted_expiry_at IS NULL filter in query)
    expiry_result = MagicMock()
    expiry_result.scalars.return_value.all.return_value = []
    mock_session.execute = AsyncMock(return_value=expiry_result)

    async def run_test():
        agent = SeniorAgent()

        async def mock_get_config(session, key, default):
            if key == "senior_expiry_alert_score_threshold":
                return "7.0"
            if key == "senior_expiry_alert_minutes_before":
                return "60"
            if key == "dashboard_url":
                return "https://app.sevamining.com"
            return default

        with patch.object(agent, "_get_config", new=mock_get_config), \
             patch("agents.senior_agent.send_whatsapp_template", new_callable=AsyncMock) as mock_send:
            await agent._check_expiry_alerts(mock_session)
            mock_send.assert_not_called()

    asyncio.run(run_test())


# --- Engagement Alerts ---

def test_engagement_alert_watchlist_early():
    """WHAT-02: Watchlist item gets early signal alert at 50+ likes / 5000+ views."""
    import asyncio
    import uuid
    from decimal import Decimal
    from datetime import datetime, timezone
    from unittest.mock import AsyncMock, MagicMock, patch
    from agents.senior_agent import SeniorAgent

    item_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    item = MagicMock()
    item.id = item_id
    item.score = Decimal("7.0")
    item.source_account = "@KitcoNews"
    item.platform = "twitter"
    item.engagement_snapshot = {"likes": 60, "views": 6000, "retweets": 5, "replies": 3,
                                 "captured_at": now.isoformat()}
    item.engagement_alert_level = None
    item.source_text = "Gold price surges to new highs as central banks continue buying"
    item.rationale = "Strong bullish signal"
    item.status = "pending"

    mock_session = AsyncMock()

    # First execute: watchlist handles query → returns {kitconews}
    watchlist_row = MagicMock()
    watchlist_row.__iter__ = MagicMock(return_value=iter(["@KitcoNews"]))
    watchlist_result = MagicMock()
    watchlist_result.all.return_value = [("@KitcoNews",)]
    mock_session.execute = AsyncMock(return_value=watchlist_result)

    async def run_test():
        agent = SeniorAgent()

        async def mock_get_config(session, key, default):
            if key == "dashboard_url":
                return "https://app.sevamining.com"
            return default

        with patch.object(agent, "_get_config", new=mock_get_config), \
             patch("agents.senior_agent.send_whatsapp_template", new_callable=AsyncMock) as mock_send:
            # Patch the items query to return our watchlist item
            call_count = 0
            original_execute = mock_session.execute.side_effect

            async def execute_side_effect(stmt):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    # watchlist handles query
                    result = MagicMock()
                    result.all.return_value = [("@KitcoNews",)]
                    return result
                else:
                    # items query
                    result = MagicMock()
                    result.scalars.return_value.all.return_value = [item]
                    return result

            mock_session.execute = AsyncMock(side_effect=execute_side_effect)
            await agent._check_engagement_alerts(mock_session)
            mock_send.assert_called_once()
            call_args = mock_send.call_args
            assert call_args[0][0] == "breaking_news", f"Expected 'breaking_news', got {call_args[0][0]}"

        assert item.engagement_alert_level == "watchlist", \
            f"Expected 'watchlist', got '{item.engagement_alert_level}'"

    asyncio.run(run_test())


def test_engagement_alert_watchlist_viral():
    """WHAT-02: Watchlist item gets viral confirmation at 500+ likes / 40000+ views."""
    import asyncio
    import uuid
    from decimal import Decimal
    from datetime import datetime, timezone
    from unittest.mock import AsyncMock, MagicMock, patch
    from agents.senior_agent import SeniorAgent

    item_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    item = MagicMock()
    item.id = item_id
    item.score = Decimal("8.5")
    item.source_account = "@KitcoNews"
    item.platform = "twitter"
    item.engagement_snapshot = {"likes": 600, "views": 50000, "retweets": 80, "replies": 25,
                                 "captured_at": now.isoformat()}
    # Already at watchlist level — should escalate to viral
    item.engagement_alert_level = "watchlist"
    item.source_text = "Gold price hits historic record as global demand surges to extraordinary levels"
    item.rationale = "Viral gold story"
    item.status = "pending"

    mock_session = AsyncMock()

    async def run_test():
        agent = SeniorAgent()

        async def mock_get_config(session, key, default):
            if key == "dashboard_url":
                return "https://app.sevamining.com"
            return default

        with patch.object(agent, "_get_config", new=mock_get_config), \
             patch("agents.senior_agent.send_whatsapp_template", new_callable=AsyncMock) as mock_send:
            call_count = 0

            async def execute_side_effect(stmt):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    result = MagicMock()
                    result.all.return_value = [("@KitcoNews",)]
                    return result
                else:
                    result = MagicMock()
                    result.scalars.return_value.all.return_value = [item]
                    return result

            mock_session.execute = AsyncMock(side_effect=execute_side_effect)
            await agent._check_engagement_alerts(mock_session)
            mock_send.assert_called_once()

        assert item.engagement_alert_level == "viral", \
            f"Expected 'viral', got '{item.engagement_alert_level}'"

    asyncio.run(run_test())


def test_engagement_alert_nonwatchlist_viral():
    """WHAT-02: Non-watchlist item gets single alert at 500+ likes / 40000+ views."""
    import asyncio
    import uuid
    from decimal import Decimal
    from datetime import datetime, timezone
    from unittest.mock import AsyncMock, MagicMock, patch
    from agents.senior_agent import SeniorAgent

    item_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    item = MagicMock()
    item.id = item_id
    item.score = Decimal("7.5")
    item.source_account = "@RandomUser"
    item.platform = "twitter"
    item.engagement_snapshot = {"likes": 600, "views": 50000, "retweets": 70, "replies": 20,
                                 "captured_at": now.isoformat()}
    item.engagement_alert_level = None
    item.source_text = "Massive gold discovery reported in remote Canadian mining region"
    item.rationale = "Viral gold discovery story"
    item.status = "pending"

    mock_session = AsyncMock()

    async def run_test():
        agent = SeniorAgent()

        async def mock_get_config(session, key, default):
            if key == "dashboard_url":
                return "https://app.sevamining.com"
            return default

        with patch.object(agent, "_get_config", new=mock_get_config), \
             patch("agents.senior_agent.send_whatsapp_template", new_callable=AsyncMock) as mock_send:
            call_count = 0

            async def execute_side_effect(stmt):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    # watchlist — @RandomUser is NOT in watchlist
                    result = MagicMock()
                    result.all.return_value = [("@KitcoNews",)]
                    return result
                else:
                    result = MagicMock()
                    result.scalars.return_value.all.return_value = [item]
                    return result

            mock_session.execute = AsyncMock(side_effect=execute_side_effect)
            await agent._check_engagement_alerts(mock_session)
            mock_send.assert_called_once()

        assert item.engagement_alert_level == "viral", \
            f"Expected 'viral', got '{item.engagement_alert_level}'"

    asyncio.run(run_test())


def test_engagement_alert_no_repeat_viral():
    """WHAT-02: Item at engagement_alert_level='viral' does NOT get another alert."""
    import asyncio
    import uuid
    from decimal import Decimal
    from datetime import datetime, timezone
    from unittest.mock import AsyncMock, MagicMock, patch
    from agents.senior_agent import SeniorAgent

    item_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    item = MagicMock()
    item.id = item_id
    item.score = Decimal("9.0")
    item.source_account = "@KitcoNews"
    item.platform = "twitter"
    item.engagement_snapshot = {"likes": 1000, "views": 100000, "retweets": 200, "replies": 50,
                                 "captured_at": now.isoformat()}
    # Already at viral — should NOT get another alert
    item.engagement_alert_level = "viral"
    item.source_text = "Gold prices have broken all records"
    item.rationale = "Already viral"
    item.status = "pending"

    mock_session = AsyncMock()

    async def run_test():
        agent = SeniorAgent()

        async def mock_get_config(session, key, default):
            if key == "dashboard_url":
                return "https://app.sevamining.com"
            return default

        with patch.object(agent, "_get_config", new=mock_get_config), \
             patch("agents.senior_agent.send_whatsapp_template", new_callable=AsyncMock) as mock_send:
            call_count = 0

            async def execute_side_effect(stmt):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    result = MagicMock()
                    result.all.return_value = [("@KitcoNews",)]
                    return result
                else:
                    # Query filters out viral items, returns empty
                    result = MagicMock()
                    result.scalars.return_value.all.return_value = []
                    return result

            mock_session.execute = AsyncMock(side_effect=execute_side_effect)
            await agent._check_engagement_alerts(mock_session)
            mock_send.assert_not_called()

    asyncio.run(run_test())


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

    approved_1 = make_item(uuid.uuid4(), "approved", 9.0, "twitter", "@Kitco", "Gold hits high. Details here.", "https://ex.com/1")
    approved_2 = make_item(uuid.uuid4(), "edited_approved", 8.5, "instagram", "@GoldInvestor", "Fed signals rate cut. Market reacts.", "https://ex.com/2")
    approved_3 = make_item(uuid.uuid4(), "approved", 7.8, "content", "@NewsDesk", "Mining output rises quarterly. Analysts bullish.", "https://ex.com/3")
    rejected_1 = make_item(uuid.uuid4(), "rejected", 5.0, "twitter", "@Spam", "Not relevant. Discard.", "https://ex.com/4")
    expired_1 = make_item(uuid.uuid4(), "expired", 4.0, "twitter", "@Old", "Old story expired. Not shown.", "https://ex.com/5")
    expired_2 = make_item(uuid.uuid4(), "expired", 3.5, "twitter", "@Old2", "Another expired. Done.", "https://ex.com/6")

    # Top 5 stories query: 3 items by score DESC
    top_story_1 = make_item(uuid.uuid4(), "approved", 9.0, "twitter", "@Kitco", "Gold hits all-time high. Markets rally strongly.", "https://ex.com/t1")
    top_story_2 = make_item(uuid.uuid4(), "approved", 8.5, "instagram", "@GoldInvestor", "Central banks buying gold. Record purchases.", "https://ex.com/t2")
    top_story_3 = make_item(uuid.uuid4(), "pending", 7.0, "twitter", "@AuAnalyst", "Gold ETF inflows surge. Demand robust.", "https://ex.com/t3")

    # Priority alert: highest-scoring pending item
    priority_item = make_item(uuid.uuid4(), "pending", 9.0, "twitter", "@Breaking", "Breaking gold news right now. Act fast.", "https://ex.com/p1")

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
    top_stories_result.scalars.return_value.all.return_value = [top_story_1, top_story_2, top_story_3]

    queue_snapshot_result = MagicMock()
    queue_snapshot_result.all.return_value = [("twitter", 3), ("instagram", 1), ("content", 1)]

    priority_result = MagicMock()
    priority_result.scalar_one_or_none.return_value = priority_item

    mock_session.execute = AsyncMock(side_effect=[
        approved_result,
        rejected_result,
        expired_result,
        top_stories_result,
        queue_snapshot_result,
        priority_result,
    ])

    async def run_test():
        agent = SeniorAgent()
        return await agent._assemble_digest(mock_session)

    digest = asyncio.run(run_test())

    # top_stories: list of 3, each with correct keys
    assert isinstance(digest["top_stories"], list), "top_stories must be a list"
    assert len(digest["top_stories"]) == 3, f"Expected 3 top stories, got {len(digest['top_stories'])}"
    for story in digest["top_stories"]:
        assert "headline" in story, f"Missing 'headline' key in story: {story}"
        assert "source_account" in story, f"Missing 'source_account' key"
        assert "platform" in story, f"Missing 'platform' key"
        assert "score" in story, f"Missing 'score' key"
        assert "source_url" in story, f"Missing 'source_url' key"

    # queue_snapshot: correct platform counts and total
    qs = digest["queue_snapshot"]
    assert qs == {"twitter": 3, "instagram": 1, "content": 1, "total": 5}, \
        f"queue_snapshot mismatch: {qs}"

    # yesterday counts
    assert digest["yesterday_approved"]["count"] == 3, \
        f"Expected approved count 3, got {digest['yesterday_approved']['count']}"
    assert digest["yesterday_rejected"]["count"] == 1, \
        f"Expected rejected count 1, got {digest['yesterday_rejected']['count']}"
    assert digest["yesterday_expired"]["count"] == 2, \
        f"Expected expired count 2, got {digest['yesterday_expired']['count']}"

    # priority_alert: has required keys, correct score
    pa = digest["priority_alert"]
    assert pa is not None, "priority_alert must not be None"
    for key in ("id", "platform", "score", "headline", "expires_at", "source_url"):
        assert key in pa, f"Missing key '{key}' in priority_alert: {pa}"
    assert pa["score"] == 9.0, f"Expected priority_alert score 9.0, got {pa['score']}"


def test_morning_digest_whatsapp_send():
    """WHAT-01/WHAT-05: Morning digest sends WhatsApp with 7 template variables including dashboard URL."""
    import asyncio
    from datetime import date
    from unittest.mock import AsyncMock, MagicMock, patch
    from agents.senior_agent import SeniorAgent

    # Known digest dict returned by _assemble_digest
    known_digest = {
        "top_stories": [
            {"headline": "Gold hits all-time high.", "source_account": "@Kitco", "platform": "twitter", "score": 9.0, "source_url": "https://ex.com/1"},
            {"headline": "Central banks buying gold.", "source_account": "@GoldInvestor", "platform": "instagram", "score": 8.5, "source_url": "https://ex.com/2"},
            {"headline": "Gold ETF inflows surge.", "source_account": "@AuAnalyst", "platform": "twitter", "score": 7.0, "source_url": "https://ex.com/3"},
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

        with patch.object(agent, "_assemble_digest", new=mock_assemble_digest), \
             patch.object(agent, "_get_config", new=mock_get_config), \
             patch("agents.senior_agent.AsyncSessionLocal") as mock_session_local, \
             patch("agents.senior_agent.AgentRun", return_value=mock_run), \
             patch("agents.senior_agent.send_whatsapp_template", new_callable=AsyncMock) as mock_send:

            mock_session_local.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_local.return_value.__aexit__ = AsyncMock(return_value=False)

            await agent.run_morning_digest()

            # Assert send_whatsapp_template called once with "morning_digest" and 7 variables
            mock_send.assert_called_once()
            call_args = mock_send.call_args
            assert call_args[0][0] == "morning_digest", \
                f"Expected template 'morning_digest', got '{call_args[0][0]}'"
            variables = call_args[0][1]

            # Variable 1: today's date as YYYY-MM-DD
            today_str = date.today().isoformat()
            assert variables["1"] == today_str, \
                f"Variable 1 (date) expected '{today_str}', got '{variables['1']}'"

            # Variable 2: headlines joined, <= 200 chars
            assert "2" in variables, "Variable 2 (headlines) missing"
            assert len(variables["2"]) <= 200, \
                f"Variable 2 length {len(variables['2'])} > 200 chars: {variables['2']}"
            assert "Gold hits all-time high" in variables["2"], \
                f"Expected first headline in variable 2: {variables['2']}"

            # Variable 3: total queue count
            assert variables["3"] == "5", f"Variable 3 (queue total) expected '5', got '{variables['3']}'"

            # Variable 4: approved count
            assert variables["4"] == "3", f"Variable 4 (approved) expected '3', got '{variables['4']}'"

            # Variable 5: rejected count
            assert variables["5"] == "1", f"Variable 5 (rejected) expected '1', got '{variables['5']}'"

            # Variable 6: expired count
            assert variables["6"] == "2", f"Variable 6 (expired) expected '2', got '{variables['6']}'"

            # Variable 7: dashboard URL
            assert variables["7"] == "https://app.sevamining.com", \
                f"Variable 7 (dashboard_url) expected 'https://app.sevamining.com', got '{variables['7']}'"

        # Assert DailyDigest was added to the session
        daily_digest_objects = [obj for obj in added_objects if type(obj).__name__ == "DailyDigest"]
        assert len(daily_digest_objects) >= 1, \
            f"Expected DailyDigest to be added to session, added_objects: {[type(o).__name__ for o in added_objects]}"

        # Assert whatsapp_sent_at is set (not None)
        digest_record = daily_digest_objects[0]
        assert digest_record.whatsapp_sent_at is not None, \
            "Expected DailyDigest.whatsapp_sent_at to be set after send"

    asyncio.run(run_test())
