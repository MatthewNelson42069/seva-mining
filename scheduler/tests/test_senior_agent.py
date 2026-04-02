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
    """SENR-04: Queue cap accepts item when pending count < 15."""
    pytest.skip("Wave 0 stub — implementation in Wave 1")
    from agents.senior_agent import SeniorAgent  # noqa: F401


def test_queue_cap_displaces_lowest():
    """SENR-04: Queue cap displaces lowest-score item when full and new item scores higher."""
    pytest.skip("Wave 0 stub — implementation in Wave 1")
    from agents.senior_agent import SeniorAgent  # noqa: F401


def test_queue_cap_discards_new_item():
    """SENR-04: Queue cap discards new item when full and new item scores <= lowest."""
    pytest.skip("Wave 0 stub — implementation in Wave 1")
    from agents.senior_agent import SeniorAgent  # noqa: F401


def test_queue_cap_tiebreak_expires_at():
    """SENR-04: Tiebreaking keeps item with later expires_at when scores are equal."""
    pytest.skip("Wave 0 stub — implementation in Wave 1")
    from agents.senior_agent import SeniorAgent  # noqa: F401


# --- SENR-05/SENR-09: Expiry Sweep ---

def test_expiry_sweep_marks_expired():
    """SENR-05/SENR-09: Expiry sweep marks items past expires_at as status='expired'."""
    pytest.skip("Wave 0 stub — implementation in Wave 2")
    from agents.senior_agent import SeniorAgent  # noqa: F401


# --- WHAT-02: Breaking News Alert ---

def test_breaking_news_alert_fires():
    """WHAT-02: Breaking news alert fires when item score >= 8.5."""
    pytest.skip("Wave 0 stub — implementation in Wave 2")
    from agents.senior_agent import SeniorAgent  # noqa: F401


def test_breaking_news_alert_no_fire():
    """WHAT-02: Breaking news alert does NOT fire when item score < 8.5."""
    pytest.skip("Wave 0 stub — implementation in Wave 2")
    from agents.senior_agent import SeniorAgent  # noqa: F401


# --- WHAT-03: Expiry Alert ---

def test_expiry_alert_fires():
    """WHAT-03: Expiry alert fires for score >= 7.0 item within 1 hour of expiry."""
    pytest.skip("Wave 0 stub — implementation in Wave 2")
    from agents.senior_agent import SeniorAgent  # noqa: F401


def test_expiry_alert_no_double_send():
    """WHAT-03: Expiry alert does NOT fire twice for same item (alerted_expiry_at dedup)."""
    pytest.skip("Wave 0 stub — implementation in Wave 2")
    from agents.senior_agent import SeniorAgent  # noqa: F401


# --- Engagement Alerts ---

def test_engagement_alert_watchlist_early():
    """WHAT-02: Watchlist item gets early signal alert at 50+ likes / 5000+ views."""
    pytest.skip("Wave 0 stub — implementation in Wave 2")
    from agents.senior_agent import SeniorAgent  # noqa: F401


def test_engagement_alert_watchlist_viral():
    """WHAT-02: Watchlist item gets viral confirmation at 500+ likes / 40000+ views."""
    pytest.skip("Wave 0 stub — implementation in Wave 2")
    from agents.senior_agent import SeniorAgent  # noqa: F401


def test_engagement_alert_nonwatchlist_viral():
    """WHAT-02: Non-watchlist item gets single alert at 500+ likes / 40000+ views."""
    pytest.skip("Wave 0 stub — implementation in Wave 2")
    from agents.senior_agent import SeniorAgent  # noqa: F401


def test_engagement_alert_no_repeat_viral():
    """WHAT-02: Item at engagement_alert_level='viral' does NOT get another alert."""
    pytest.skip("Wave 0 stub — implementation in Wave 2")
    from agents.senior_agent import SeniorAgent  # noqa: F401


# --- SENR-06/SENR-07: Morning Digest ---

def test_morning_digest_assembly():
    """SENR-06/SENR-07: Morning digest assembles correct JSONB with top stories, counts, snapshot."""
    pytest.skip("Wave 0 stub — implementation in Wave 3")
    from agents.senior_agent import SeniorAgent  # noqa: F401


def test_morning_digest_whatsapp_send():
    """WHAT-01/WHAT-05: Morning digest sends WhatsApp with 7 template variables including dashboard URL."""
    pytest.skip("Wave 0 stub — implementation in Wave 3")
    from agents.senior_agent import SeniorAgent  # noqa: F401
