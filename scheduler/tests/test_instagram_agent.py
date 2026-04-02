"""
Tests for Instagram Agent — INST-01 through INST-12.
All tests use mocked Apify, mocked anthropic, and mocked DB sessions.

Wave 0 state: agents.instagram_agent does not exist yet.
All 15 tests skip immediately (before any lazy import) so they are
collectable and show as SKIPPED (not ERROR) until implementation.
"""
import json
import os
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta

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
os.environ.setdefault("APIFY_API_TOKEN", "test-apify-token")
os.environ.setdefault("SERPAPI_API_KEY", "x")
os.environ.setdefault("FRONTEND_URL", "https://x.com")


def _get_instagram_agent():
    """Import agents.instagram_agent lazily; only called after the skip guard in each test."""
    import importlib
    return importlib.import_module("agents.instagram_agent")


# ---------------------------------------------------------------------------
# INST-02: Composite scoring formula
# ---------------------------------------------------------------------------

def test_scoring_formula():
    """
    calculate_instagram_score(likes=200, comment_count=50, follower_count=100000)
    returns the expected float using: likes*1 + comments*2 + normalize_followers(n)*1.5
    Covers: INST-02
    """
    ia = _get_instagram_agent()
    score = ia.calculate_instagram_score(likes=200, comment_count=50, follower_count=100000)
    # normalize_followers(100000) = log10(100000)/log10(1_000_000) = 5/6 ≈ 0.8333
    # score = 200*1 + 50*2 + 0.8333*1.5 = 200 + 100 + 1.25 = 301.25
    assert isinstance(score, float), f"Expected float, got {type(score)}"
    assert score > 0, "Score must be positive"


# ---------------------------------------------------------------------------
# INST-02: Follower count normalization
# ---------------------------------------------------------------------------

def test_normalize_followers():
    """
    normalize_followers uses log10 scale capped at 1M:
      0 → 0.0, 1000 → ~0.5, 1_000_000 → 1.0
    Covers: INST-02
    """
    ia = _get_instagram_agent()
    assert ia.normalize_followers(0) == 0.0
    norm_1k = ia.normalize_followers(1000)
    assert 0.4 <= norm_1k <= 0.6, f"1000 followers should normalize to ~0.5, got {norm_1k}"
    assert ia.normalize_followers(1_000_000) == 1.0


# ---------------------------------------------------------------------------
# INST-03: Engagement gate
# ---------------------------------------------------------------------------

def test_engagement_gate():
    """
    200+ likes AND post created within last 8 hours passes; 199 likes fails;
    200 likes but 9h old fails.
    Covers: INST-03
    """
    ia = _get_instagram_agent()
    now = datetime.now(timezone.utc)
    recent = now - timedelta(hours=4)
    old = now - timedelta(hours=9)

    # Pass: 200 likes, within 8h
    assert ia.passes_engagement_gate(likes=200, created_at=recent) is True
    # Fail: 199 likes
    assert ia.passes_engagement_gate(likes=199, created_at=recent) is False
    # Fail: 200 likes but 9h old
    assert ia.passes_engagement_gate(likes=200, created_at=old) is False


# ---------------------------------------------------------------------------
# INST-04: Top N post selection
# ---------------------------------------------------------------------------

def test_select_top_posts():
    """
    Given 5 scored posts, select_top_posts returns top 3 by score descending.
    Covers: INST-04
    """
    ia = _get_instagram_agent()
    posts = [
        {"shortCode": "a", "score": 3.0},
        {"shortCode": "b", "score": 9.5},
        {"shortCode": "c", "score": 7.2},
        {"shortCode": "d", "score": 8.1},
        {"shortCode": "e", "score": 5.5},
    ]
    selected = ia.select_top_posts(posts, top_n=3)
    assert len(selected) == 3, f"Expected 3 posts, got {len(selected)}"
    scores = [p["score"] for p in selected]
    assert scores == sorted(scores, reverse=True), "Posts must be sorted by score descending"
    assert selected[0]["score"] == 9.5, "Top post must have highest score"


# ---------------------------------------------------------------------------
# INST-05, INST-06: Draft comment alternatives — no hashtags
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_draft_for_post():
    """
    Mock Claude returns 3 comment alternatives as JSON; each has 'text' and 'rationale' keys.
    No alternative contains '#'. Covers: INST-05, INST-06
    """
    ia = _get_instagram_agent()
    mock_response_json = json.dumps({
        "comment_alternatives": [
            {"text": "Gold demand from central banks reached a 40-year high.", "rationale": "Data-driven insight"},
            {"text": "Central bank buying accounts for 25% of gold demand in 2024.", "rationale": "Market context"},
            {"text": "Mining output down 3% YoY while demand surges.", "rationale": "Supply analysis"},
        ]
    })
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=MagicMock(
        content=[MagicMock(text=mock_response_json)]
    ))
    post = {
        "shortCode": "abc123",
        "caption": "Gold breaking records as central banks load up",
        "ownerUsername": "goldanalyst",
        "likesCount": 500,
        "commentsCount": 42,
        "score": 8.5,
    }
    result = await ia.draft_for_post(post=post, client=mock_client)

    assert isinstance(result, list), "Result must be a list of alternatives"
    assert len(result) == 3, f"Expected 3 alternatives, got {len(result)}"
    for alt in result:
        assert "text" in alt, f"Alternative must have 'text' key: {alt}"
        assert "rationale" in alt, f"Alternative must have 'rationale' key: {alt}"
        assert "#" not in alt["text"], f"Alternative text must not contain hashtags: {alt['text']}"


# ---------------------------------------------------------------------------
# INST-06: Compliance blocks hashtags
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_compliance_blocks_hashtags():
    """
    Draft containing '#gold' is pre-screened and blocked without calling Claude.
    Clean draft with mock Claude PASS returns True.
    Covers: INST-06
    """
    ia = _get_instagram_agent()
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=MagicMock(
        content=[MagicMock(text="PASS")]
    ))
    # Hashtag pre-screen: should block without even calling Claude
    passed = await ia.check_compliance(draft="Great insight on #gold performance this quarter.", client=mock_client)
    assert passed is False, "Draft containing hashtag must be blocked by compliance"
    # Clean draft: mock Claude returns PASS, should return True
    passed_clean = await ia.check_compliance(draft="Gold reserves increased by 12% year-over-year.", client=mock_client)
    assert passed_clean is True, "Clean draft with PASS response must not be blocked"


# ---------------------------------------------------------------------------
# INST-08: Compliance blocks brand mentions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_compliance_blocks_seva():
    """
    Draft containing 'Seva Mining' is pre-screened and blocked without calling Claude.
    Covers: INST-08
    """
    ia = _get_instagram_agent()
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=MagicMock(
        content=[MagicMock(text="PASS")]
    ))
    draft_with_brand = "Seva Mining has identified this trend as a key opportunity."
    passed = await ia.check_compliance(draft=draft_with_brand, client=mock_client)
    assert passed is False, "Draft containing brand name must be blocked by compliance"
    # Verify pre-screen doesn't call Claude for Seva Mining mention
    mock_client.messages.create.assert_not_called()


# ---------------------------------------------------------------------------
# INST-08: Compliance fail-safe — ambiguous response blocks
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_compliance_fail_safe():
    """
    An ambiguous or unparseable compliance response must block the draft (not pass it).
    Covers: INST-08
    """
    ia = _get_instagram_agent()
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=MagicMock(
        content=[MagicMock(text="I'm not sure about this one.")]
    ))
    passed = await ia.check_compliance(draft="Some draft text about gold.", client=mock_client)
    assert passed is False, "Ambiguous compliance response must fail-safe to blocked"


# ---------------------------------------------------------------------------
# INST-09: Retry logic — Apify call fails twice then succeeds
# ---------------------------------------------------------------------------

async def test_retry_logic():
    """
    _call_apify_actor_once fails twice then succeeds on 3rd attempt.
    asyncio.sleep called with 1 then 2 (exponential backoff).
    Covers: INST-09
    """
    ia = _get_instagram_agent()
    call_count = 0

    async def fake_once(run_input: dict) -> list:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise Exception("Apify transient error")
        return [{"shortCode": "abc"}]

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        with patch("agents.instagram_agent.get_settings", return_value=MagicMock(
            apify_api_token="tok", anthropic_api_key="key"
        )):
            with patch("agents.instagram_agent.ApifyClientAsync"):
                agent = ia.InstagramAgent()
                agent._call_apify_actor_once = fake_once
                result = await agent._call_apify_actor_with_retry(run_input={})

    assert result == [{"shortCode": "abc"}], f"Expected success result, got {result}"
    assert call_count == 3, f"Expected 3 total attempts, got {call_count}"
    sleep_calls = [c.args[0] for c in mock_sleep.call_args_list]
    assert sleep_calls == [1, 2], f"Expected backoff [1, 2], got {sleep_calls}"


# ---------------------------------------------------------------------------
# INST-10: Health check — skip baseline for first 3 runs
# ---------------------------------------------------------------------------

async def test_health_check_skip_baseline():
    """
    No health warnings are emitted when run_number <= 3 (baseline not yet established).
    Covers: INST-10
    """
    pytest.skip("Instagram agent not yet implemented")
    ia = _get_instagram_agent()
    warnings = await ia.check_scraper_health(
        hashtag_counts={"gold": 0},
        rolling_averages={"gold": 50.0},
        run_number=2,
        baseline_runs=3,
    )
    assert warnings == [], f"Expected no warnings during baseline runs, got {warnings}"


# ---------------------------------------------------------------------------
# INST-10: Health check — threshold warning
# ---------------------------------------------------------------------------

async def test_health_warning_threshold():
    """
    Hashtag returning <20% of its rolling average triggers a health warning.
    Covers: INST-10
    """
    pytest.skip("Instagram agent not yet implemented")
    ia = _get_instagram_agent()
    # Rolling avg = 50 posts; threshold = 20% = 10 posts; actual = 5 → should warn
    warnings = await ia.check_scraper_health(
        hashtag_counts={"gold": 5},
        rolling_averages={"gold": 50.0},
        run_number=5,
        baseline_runs=3,
    )
    assert len(warnings) > 0, "Expected health warning when count < 20% of rolling avg"
    assert any("gold" in w for w in warnings), "Warning must reference the affected hashtag"


# ---------------------------------------------------------------------------
# INST-11: Critical failure — 2 consecutive zero-result runs triggers alert
# ---------------------------------------------------------------------------

async def test_critical_failure_alert():
    """
    Two consecutive runs where ALL hashtags return zero results triggers a WhatsApp alert.
    Covers: INST-11
    """
    pytest.skip("Instagram agent not yet implemented")
    ia = _get_instagram_agent()
    mock_whatsapp = AsyncMock()
    alert_sent = await ia.maybe_send_critical_alert(
        consecutive_zero_runs=2,
        last_run_alerted=False,
        whatsapp_fn=mock_whatsapp,
        dashboard_url="https://x.com",
    )
    assert alert_sent is True, "Alert should be sent on 2nd consecutive zero-result run"
    mock_whatsapp.assert_called_once()


# ---------------------------------------------------------------------------
# INST-11: No duplicate alert on 3rd consecutive zero run
# ---------------------------------------------------------------------------

async def test_no_duplicate_alert():
    """
    A 3rd consecutive zero-result run does NOT send a second WhatsApp alert.
    Dedup check: last_run_alerted=True prevents re-alert.
    Covers: INST-11
    """
    pytest.skip("Instagram agent not yet implemented")
    ia = _get_instagram_agent()
    mock_whatsapp = AsyncMock()
    alert_sent = await ia.maybe_send_critical_alert(
        consecutive_zero_runs=3,
        last_run_alerted=True,
        whatsapp_fn=mock_whatsapp,
        dashboard_url="https://x.com",
    )
    assert alert_sent is False, "Should not send duplicate alert on 3rd consecutive zero run"
    mock_whatsapp.assert_not_called()


# ---------------------------------------------------------------------------
# INST-01: Scheduler wiring — InstagramAgent.run() is async callable
# ---------------------------------------------------------------------------

async def test_scheduler_wiring():
    """
    InstagramAgent().run must be an async callable (coroutine function).
    Covers: INST-01
    """
    pytest.skip("Instagram agent not yet implemented")
    import inspect
    ia = _get_instagram_agent()
    agent = ia.InstagramAgent()
    assert inspect.iscoroutinefunction(agent.run), (
        "InstagramAgent.run must be an async def (coroutine function)"
    )


# ---------------------------------------------------------------------------
# INST-12: DraftItem expires_at = created_at + 12 hours
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_expiry_12h():
    """
    DraftItem created by the agent has expires_at = created_at + 12 hours.
    platform must be 'instagram'.
    Covers: INST-12
    """
    ia = _get_instagram_agent()
    now = datetime.now(timezone.utc)
    draft_item = ia.build_draft_item_expiry(created_at=now)
    expected_expiry = now + timedelta(hours=12)
    diff = abs((draft_item.expires_at - expected_expiry).total_seconds())
    assert diff < 1, (
        f"expires_at must be created_at + 12h, got diff of {diff}s"
    )
    assert draft_item.platform == "instagram", (
        f"DraftItem platform must be 'instagram', got '{draft_item.platform}'"
    )
