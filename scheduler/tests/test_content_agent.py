"""Tests for content_agent — review-service-only module (post quick-260421-eoe).

The pre-split test_content_agent.py covered the monolithic ContentAgent class
(run/_run_pipeline, every _draft_* helper, whatsapp handoff, etc). Those
tests were retired alongside the methods they covered. This file now covers
only the public surface the 7 content sub-agents depend on:

- ``fetch_stories()``: 30-min TTL cache + fetch-failure handling.
- ``review(draft)``: Haiku compliance gate return shape.
- ``classify_format_lightweight(story, *, client)``: fixed string set.

Per-format drafting and pipeline behavior is covered in the per-agent test
files (test_breaking_news.py, test_threads.py, ...). Scoring / dedup / gold
gate helpers are covered inline here because they remain module-level in
content_agent.py and have no sub-agent-specific equivalent.
"""

import asyncio
import os
import sys
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Env vars must be set before importing settings-bound modules.
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

from agents import content_agent  # noqa: E402


# ---------------------------------------------------------------------------
# Module-level constants — retained after split
# ---------------------------------------------------------------------------


def test_rss_feeds_constant_preserved():
    """RSS_FEEDS constant is preserved and reachable (CONT-02)."""
    assert len(content_agent.RSS_FEEDS) == 7
    assert any("kitco" in url for url, _ in content_agent.RSS_FEEDS)


def test_serpapi_keywords_constant_preserved():
    """SERPAPI_KEYWORDS is preserved (CONT-03).

    quick-260424-j5i D8: count drops 18 → 17 after removing the unhyphenated
    rare-earth keyword.
    """
    assert len(content_agent.SERPAPI_KEYWORDS) == 17
    assert "gold price" in content_agent.SERPAPI_KEYWORDS


def test_serpapi_keywords_critical_minerals_coverage():
    """New keywords for critical-minerals + sovereign-gold coverage (htu).

    quick-260424-j5i D8: the unhyphenated rare-earth keyword was removed because
    it pulled too many off-theme policy pieces. Remaining 7 htu additions still
    cover critical-minerals + sovereign-gold without that noise.
    """
    required = [
        "critical minerals",
        "strategic metals",
        "sovereign wealth fund gold",
        "treasury gold sale",
        "gold mining M&A",
        "US China metals",
        "mineral supply chain",
    ]
    for kw in required:
        assert kw in content_agent.SERPAPI_KEYWORDS, f"missing keyword: {kw}"


def test_serpapi_keywords_existing_preserved():
    """Original 10 keywords must remain after expansion (htu)."""
    original = [
        "gold exploration",
        "gold price",
        "central bank gold",
        "gold ETF",
        "junior miners",
        "gold reserves",
        "gold inflation hedge",
        "Fed gold",
        "dollar gold",
        "recession gold",
    ]
    for kw in original:
        assert kw in content_agent.SERPAPI_KEYWORDS, f"pre-existing keyword dropped: {kw}"


def test_serpapi_keywords_total_count_and_unique():
    """Total = 17, no duplicates (quick-260424-j5i D8 dropped one from htu's 18)."""
    assert len(content_agent.SERPAPI_KEYWORDS) == 17
    assert len(set(content_agent.SERPAPI_KEYWORDS)) == 17


def test_rss_feeds_reuters_dropped_bnn_added():
    """Dead Reuters feed removed, BNN Bloomberg added (htu)."""
    urls = [u for u, _ in content_agent.RSS_FEEDS]
    assert not any("feeds.reuters.com" in u for u in urls), "dead Reuters feed still present"
    assert any("bnnbloomberg.ca" in u for u in urls), "BNN Bloomberg feed missing"


# ---------------------------------------------------------------------------
# fetch_stories() — shared SerpAPI + RSS ingestion with 30-min TTL cache
# ---------------------------------------------------------------------------


def _clear_cache():
    content_agent._STORIES_CACHE.clear()


@pytest.mark.asyncio
async def test_fetch_stories_cache_hit_same_bucket():
    """Two calls within the same 30-min bucket issue one underlying fetch."""
    _clear_cache()
    stories = [
        {
            "title": "GOLD NEWS",
            "summary": "...",
            "link": "http://a",
            "source_name": "kitco.com",
            "published": None,
        }
    ]

    bucket = content_agent._cache_bucket()
    # Seed the cache directly — if fetch_stories respects the cache, no fetch
    # is invoked and the function returns our pre-seeded list.
    content_agent._STORIES_CACHE[bucket] = stories

    with (
        patch.object(content_agent, "_fetch_all_rss", new=AsyncMock()) as mock_rss,
        patch.object(content_agent, "_fetch_all_serpapi", new=AsyncMock()) as mock_serp,
    ):
        first = await content_agent.fetch_stories()
        second = await content_agent.fetch_stories()

    assert first is stories
    assert second is stories
    mock_rss.assert_not_called()
    mock_serp.assert_not_called()


@pytest.mark.asyncio
async def test_fetch_stories_cache_miss_new_bucket():
    """Advancing past the 30-min bucket triggers a second underlying fetch."""
    _clear_cache()

    # Put a value in an old bucket; current bucket should miss.
    old_bucket = content_agent._cache_bucket() - 1
    content_agent._STORIES_CACHE[old_bucket] = [{"title": "stale"}]

    fetched = [
        {
            "title": "fresh",
            "summary": "",
            "link": "http://b",
            "source_name": "kitco.com",
            "published": None,
        }
    ]

    with (
        patch.object(content_agent, "_fetch_all_rss", new=AsyncMock(return_value=fetched)),
        patch.object(content_agent, "_fetch_all_serpapi", new=AsyncMock(return_value=[])),
        patch.object(content_agent, "deduplicate_stories", return_value=fetched),
        patch.object(content_agent, "_score_relevance", new=AsyncMock(return_value=0.5)),
        patch.object(content_agent, "recency_score", return_value=0.9),
        patch.object(content_agent, "credibility_score", return_value=0.8),
        patch.object(
            content_agent, "classify_format_lightweight", new=AsyncMock(return_value="thread")
        ),
    ):
        result = await content_agent.fetch_stories()

    assert len(result) == 1
    assert result[0]["title"] == "fresh"
    # Old bucket should have been evicted.
    assert old_bucket not in content_agent._STORIES_CACHE


@pytest.mark.asyncio
async def test_fetch_stories_fetch_failure_returns_empty():
    """Ingestion exceptions produce [] and log a warning, not re-raise."""
    _clear_cache()

    with (
        patch.object(
            content_agent, "_fetch_all_rss", new=AsyncMock(side_effect=RuntimeError("network down"))
        ),
        patch.object(content_agent, "_fetch_all_serpapi", new=AsyncMock(return_value=[])),
    ):
        result = await content_agent.fetch_stories()

    assert result == []
    # Result is cached for the bucket so subsequent calls don't re-try.
    bucket = content_agent._cache_bucket()
    assert content_agent._STORIES_CACHE[bucket] == []


def test_cache_bucket_matches_30_min_formula():
    """_cache_bucket returns int(time.time() // 1800) at call time."""
    expected = int(time.time() // 1800)
    assert content_agent._cache_bucket() == expected


@pytest.mark.asyncio
async def test_fetch_stories_coalesce_concurrent_callers_issue_one_fetch():
    """Concurrent callers within the same bucket coalesce onto one in-flight fetch.

    quick-260427-m51: the coalesce pattern ensures _do_fetch is called exactly
    once even when multiple coroutines arrive simultaneously on a cache miss.
    Previously the sequential _score_relevance loop held _CACHE_LOCK for the
    entire scoring duration, blocking all concurrent callers for up to 59 min.
    This test verifies: (a) _do_fetch is called once, (b) both callers receive
    the same list, (c) _CACHE_LOCK is NOT held during the actual fetch work.
    """
    _clear_cache()
    # Also clear any in-flight futures from a previous test.
    content_agent._FETCH_IN_FLIGHT.clear()

    scored_story = {
        "title": "GOLD UP",
        "summary": "",
        "link": "http://c",
        "source_name": "kitco.com",
        "published": None,
        "score": 7.0,
        "predicted_format": "breaking_news",
    }
    do_fetch_call_count = 0

    async def _fake_do_fetch(bucket):
        nonlocal do_fetch_call_count
        do_fetch_call_count += 1
        # Yield to the event loop so the second coroutine can also enter
        # fetch_stories and see the in-flight Future.
        await asyncio.sleep(0)
        return [scored_story]

    with patch.object(content_agent, "_do_fetch", new=_fake_do_fetch):
        result_a, result_b = await asyncio.gather(
            content_agent.fetch_stories(),
            content_agent.fetch_stories(),
        )

    # _do_fetch must be called exactly once — the second caller coalesced.
    assert do_fetch_call_count == 1
    # Both callers receive the same list.
    assert result_a == [scored_story]
    assert result_b == [scored_story]
    # Cache populated correctly.
    bucket = content_agent._cache_bucket()
    assert content_agent._STORIES_CACHE[bucket] == [scored_story]
    # In-flight entry cleaned up.
    assert bucket not in content_agent._FETCH_IN_FLIGHT


# ---------------------------------------------------------------------------
# review(draft) — Haiku compliance gate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_review_pass_returns_compliance_passed_true():
    """When check_compliance passes, review returns compliance_passed=True."""
    draft = {"format": "breaking_news", "tweet": "Gold at $2400."}
    with patch.object(content_agent, "check_compliance", new=AsyncMock(return_value=True)):
        result = await content_agent.review(draft)
    assert result["compliance_passed"] is True
    assert "rationale" in result


@pytest.mark.asyncio
async def test_review_fail_returns_compliance_passed_false():
    """When check_compliance fails, review returns compliance_passed=False + rationale."""
    draft = {"format": "breaking_news", "tweet": "You should buy gold now."}
    with patch.object(content_agent, "check_compliance", new=AsyncMock(return_value=False)):
        result = await content_agent.review(draft)
    assert result["compliance_passed"] is False
    assert result["rationale"]


@pytest.mark.asyncio
async def test_review_empty_draft_treated_as_pass():
    """Drafts with no extractable text short-circuit to compliance_passed=True."""
    # A draft with no known format and no checkable text → _extract_check_text = ""
    # review() must treat empty text as pass (no compliance issue to flag).
    draft = {"format": "unknown_format"}
    with patch.object(content_agent, "_extract_check_text", return_value=""):
        result = await content_agent.review(draft)
    assert result["compliance_passed"] is True


# ---------------------------------------------------------------------------
# classify_format_lightweight — fixed string return set
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_classify_format_lightweight_returns_valid_format():
    """Classifier returns one of the 5 recognised format strings."""
    client = AsyncMock()
    response = MagicMock()
    response.content = [MagicMock(text="breaking_news")]
    client.messages.create = AsyncMock(return_value=response)

    result = await content_agent.classify_format_lightweight(
        {"title": "Gold hits record high", "summary": "short", "published": ""},
        client=client,
    )
    assert result == "breaking_news"


@pytest.mark.asyncio
async def test_classify_format_lightweight_fails_open_to_thread():
    """Any error in the Haiku call returns the 'thread' fallback."""
    client = AsyncMock()
    client.messages.create = AsyncMock(side_effect=RuntimeError("api down"))

    result = await content_agent.classify_format_lightweight(
        {"title": "x", "summary": "y", "published": ""},
        client=client,
    )
    assert result == "thread"


@pytest.mark.asyncio
async def test_classify_format_lightweight_clamps_invalid_output():
    """Unexpected classifier outputs are clamped to 'thread'."""
    client = AsyncMock()
    response = MagicMock()
    response.content = [MagicMock(text="some_new_format_we_do_not_support")]
    client.messages.create = AsyncMock(return_value=response)

    result = await content_agent.classify_format_lightweight(
        {"title": "x", "summary": "y", "published": ""},
        client=client,
    )
    assert result == "thread"


def test_classify_format_lightweight_returns_sub_agent_filter_strings():
    """The classifier's valid_formats set MUST match the 4 CONTENT_TYPE strings
    that text-story sub-agents filter on (quick-260423-k8n: long_form removed)."""
    import inspect

    source = inspect.getsource(content_agent.classify_format_lightweight)
    for expected in ("breaking_news", "thread", "infographic", "quote"):
        assert f'"{expected}"' in source, f"missing classifier label {expected}"
    assert '"long_form"' not in source, "long_form should have been removed from classifier"


# ---------------------------------------------------------------------------
# Compliance checker — retained module-level helper
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_compliance_screens_seva_mining_mention_locally():
    """check_compliance short-circuits on 'seva mining' substring — no API call."""
    client = AsyncMock()
    client.messages.create = AsyncMock()
    ok = await content_agent.check_compliance(
        "Seva Mining just hit a big drill result", anthropic_client=client
    )
    assert ok is False
    client.messages.create.assert_not_called()


@pytest.mark.asyncio
async def test_compliance_failsafe_on_api_error():
    """API errors during compliance check return False (fail-safe block)."""
    client = AsyncMock()
    client.messages.create = AsyncMock(side_effect=RuntimeError("rate limited"))
    ok = await content_agent.check_compliance(
        "A neutral gold market update", anthropic_client=client
    )
    assert ok is False


# ---------------------------------------------------------------------------
# Draft item / content bundle builder helpers — retained + used by sub-agents
# ---------------------------------------------------------------------------


def test_build_draft_item_stores_bundle_id_in_engagement_snapshot():
    """DraftItem.engagement_snapshot contains the content_bundle_id (pre-split pattern preserved)."""
    from uuid import uuid4

    bundle = MagicMock()
    bundle.id = uuid4()
    bundle.story_headline = "gold at record high"
    bundle.story_url = "http://example.com"
    bundle.source_name = "kitco"
    bundle.score = 8.5
    bundle.quality_score = None
    bundle.draft_content = {"format": "breaking_news", "tweet": "GOLD: $2500"}

    item = content_agent.build_draft_item(bundle, "test rationale")
    assert item.platform == "content"
    assert item.engagement_snapshot == {"content_bundle_id": str(bundle.id)}


# ---------------------------------------------------------------------------
# build_draft_item — gold_history carousel renderer (quick-260427-k5h regression)
# ---------------------------------------------------------------------------


def _make_gold_history_bundle(carousel: list, tweets: list | None = None):
    """Build a MagicMock bundle whose draft_content matches the gold_history schema."""
    from uuid import uuid4

    bundle = MagicMock()
    bundle.id = uuid4()
    bundle.story_headline = "Gold has not peaked"
    bundle.story_url = "http://example.com/article"
    bundle.source_name = "AJ Bell"
    bundle.score = 8.0
    bundle.quality_score = None
    bundle.draft_content = {
        "format": "gold_history",
        "story_title": "Gold has not peaked",
        "story_slug": "gold-has-not-peaked",
        "tweets": tweets if tweets is not None else ["Tweet one", "Tweet two"],
        "instagram_carousel": carousel,
        "instagram_caption": "Caption text.",
        "sources": [],
    }
    return bundle


def test_build_draft_item_gold_history_renders_carousel_slides():
    """Regression for quick-260427-k5h: carousel slides must surface headline + body + visual_note.

    Pre-fix behavior: build_draft_item read ``slide.get('text', '')`` which does
    not exist on the real schema → modal showed empty ``Slide N:`` lines. This
    test feeds the realistic schema (``{slide, headline, body, visual_note}``)
    through build_draft_item and asserts every field is present in the
    assembled draft_text.
    """
    carousel = [
        {
            "slide": 1,
            "headline": "Gold Has Not Peaked",
            "body": "History says the biggest move may still be ahead.",
            "visual_note": "Full-bleed warm cream background with bold serif headline.",
        },
        {
            "slide": 2,
            "headline": "1971 Set the Stage",
            "body": "Nixon shock ended the gold standard, freeing the price to discover its true level.",
            "visual_note": "Vintage newspaper clipping motif, sepia tone.",
        },
        {
            "slide": 3,
            "headline": "1980 Peak Was a Crisis Top",
            "body": "Inflation, hostage crisis, Soviet invasion of Afghanistan — peak fear, peak gold.",
            "visual_note": "Dual chart: CPI vs gold price 1976-1982.",
        },
        {
            "slide": 4,
            "headline": "Today Looks Different",
            "body": "Real rates positive, dollar strong, yet gold rallies — that's structural demand.",
            "visual_note": "Side-by-side chart: gold vs DXY 2020-present.",
        },
        {
            "slide": 5,
            "headline": "The Asymmetric Setup",
            "body": "When central banks accumulate, retail follows; we are still in act one.",
            "visual_note": "Stacked area chart of central bank gold reserves 2010-present.",
        },
    ]
    bundle = _make_gold_history_bundle(carousel)

    item = content_agent.build_draft_item(bundle, "test rationale")
    text = item.alternatives[0]["text"]

    # Section markers must be preserved (frontend rendering depends on them).
    assert "=== Thread ===" in text
    assert "=== Instagram Carousel ===" in text

    # Every slide's headline, body, and visual_note must appear in the output.
    for slide in carousel:
        assert slide["headline"] in text, f"missing headline for slide {slide['slide']}"
        assert slide["body"] in text, f"missing body for slide {slide['slide']}"
        assert slide["visual_note"] in text, f"missing visual_note for slide {slide['slide']}"

    # Visual: prefix is used to separate render-direction from post copy.
    assert "Visual:" in text

    # Regression guard: no empty "Slide N:" line followed immediately by another
    # slide marker (the broken renderer produced "Slide 1:\n\nSlide 2:\n\n...").
    assert "Slide 1:\n\nSlide 2:" not in text
    assert "Slide 1: \n\nSlide 2:" not in text


def test_build_draft_item_gold_history_handles_partial_slide():
    """Slides missing one of headline/body/visual_note still render the present fields."""
    carousel = [
        # Slide with everything
        {"slide": 1, "headline": "Full slide", "body": "All fields present.", "visual_note": "Visual cue."},
        # Slide missing headline (only body + visual)
        {"slide": 2, "body": "Body only.", "visual_note": "Some visual."},
        # Slide missing visual_note
        {"slide": 3, "headline": "No visual", "body": "Has body."},
        # Slide with only headline
        {"slide": 4, "headline": "Just a headline"},
    ]
    bundle = _make_gold_history_bundle(carousel, tweets=[])

    item = content_agent.build_draft_item(bundle, "test rationale")
    text = item.alternatives[0]["text"]

    # Every present field surfaces.
    assert "Full slide" in text
    assert "All fields present." in text
    assert "Visual cue." in text
    assert "Body only." in text
    assert "Some visual." in text
    assert "No visual" in text
    assert "Has body." in text
    assert "Just a headline" in text

    # Slide markers exist for every slide even when fields are sparse.
    assert "Slide 1:" in text
    assert "Slide 2:" in text
    assert "Slide 3:" in text
    assert "Slide 4:" in text


def test_build_draft_item_gold_history_legacy_string_slide_compat():
    """Legacy compat: a slide that's a bare string still renders as ``Slide N: <str>``."""
    carousel = ["legacy slide one", "legacy slide two"]
    bundle = _make_gold_history_bundle(carousel, tweets=[])

    item = content_agent.build_draft_item(bundle, "test rationale")
    text = item.alternatives[0]["text"]

    assert "Slide 1: legacy slide one" in text
    assert "Slide 2: legacy slide two" in text


def test_build_draft_item_gold_history_empty_carousel_falls_back():
    """When both tweets and carousel are empty, fall back to ``Gold History: {story_title}``."""
    bundle = _make_gold_history_bundle(carousel=[], tweets=[])

    item = content_agent.build_draft_item(bundle, "test rationale")
    text = item.alternatives[0]["text"]

    assert text == "Gold History: Gold has not peaked"


# ---------------------------------------------------------------------------
# is_gold_relevant_or_systemic_shock — gold gate bearish filter (quick-260423-j7x)
# ---------------------------------------------------------------------------

GATE_CONFIG = {
    "content_gold_gate_enabled": "true",
    "content_gold_gate_model": "claude-haiku-4-5",
    "content_bearish_filter_enabled": "true",
}


@pytest.mark.asyncio
async def test_gold_gate_rejects_price_bearish_forecast():
    """Gate rejects price-bearish analyst forecasts with reject_reason='bearish_toward_gold'."""
    client = AsyncMock()
    response = MagicMock()
    response.content = [
        MagicMock(
            text='{"is_gold_relevant": true, "primary_subject_is_specific_miner": false, "company": null, "sentiment": "bearish"}'
        )
    ]
    client.messages.create = AsyncMock(return_value=response)

    story = {"title": "Morgan Stanley cuts gold price forecast by almost 10%", "summary": "..."}
    result = await content_agent.is_gold_relevant_or_systemic_shock(
        story, GATE_CONFIG, client=client
    )

    assert result["keep"] is False
    assert result["reject_reason"] == "bearish_toward_gold"
    assert result["sentiment"] == "bearish"


@pytest.mark.asyncio
async def test_gold_gate_rejects_anti_gold_narrative():
    """Gate rejects anti-gold narrative (bitcoin replacing gold) with bearish_toward_gold."""
    client = AsyncMock()
    response = MagicMock()
    response.content = [
        MagicMock(
            text='{"is_gold_relevant": true, "primary_subject_is_specific_miner": false, "company": null, "sentiment": "bearish"}'
        )
    ]
    client.messages.create = AsyncMock(return_value=response)

    story = {"title": "Bitcoin replaces gold as reserve asset of choice", "summary": "..."}
    result = await content_agent.is_gold_relevant_or_systemic_shock(
        story, GATE_CONFIG, client=client
    )

    assert result["keep"] is False
    assert result["reject_reason"] == "bearish_toward_gold"
    assert result["sentiment"] == "bearish"


@pytest.mark.asyncio
async def test_gold_gate_rejects_factual_price_decline():
    """Gate rejects factual-negative price movement stories with bearish_toward_gold."""
    client = AsyncMock()
    response = MagicMock()
    response.content = [
        MagicMock(
            text='{"is_gold_relevant": true, "primary_subject_is_specific_miner": false, "company": null, "sentiment": "bearish"}'
        )
    ]
    client.messages.create = AsyncMock(return_value=response)

    story = {"title": "Gold fell 1.2% today on stronger dollar", "summary": "..."}
    result = await content_agent.is_gold_relevant_or_systemic_shock(
        story, GATE_CONFIG, client=client
    )

    assert result["keep"] is False
    assert result["reject_reason"] == "bearish_toward_gold"
    assert result["sentiment"] == "bearish"


@pytest.mark.asyncio
async def test_gold_gate_keeps_bullish_central_bank_buying():
    """Gate keeps bullish stories (central bank buying) with keep=True."""
    client = AsyncMock()
    response = MagicMock()
    response.content = [
        MagicMock(
            text='{"is_gold_relevant": true, "primary_subject_is_specific_miner": false, "company": null, "sentiment": "bullish"}'
        )
    ]
    client.messages.create = AsyncMock(return_value=response)

    story = {"title": "Central banks added 800t of gold in Q1", "summary": "..."}
    result = await content_agent.is_gold_relevant_or_systemic_shock(
        story, GATE_CONFIG, client=client
    )

    assert result["keep"] is True
    assert result["reject_reason"] is None
    assert result["sentiment"] == "bullish"


@pytest.mark.asyncio
async def test_gold_gate_keeps_bullish_price_forecast():
    """Gate keeps bullish upside forecasts (Goldman $4K) — direction matters, not the word 'forecast'."""
    client = AsyncMock()
    response = MagicMock()
    response.content = [
        MagicMock(
            text='{"is_gold_relevant": true, "primary_subject_is_specific_miner": false, "company": null, "sentiment": "bullish"}'
        )
    ]
    client.messages.create = AsyncMock(return_value=response)

    story = {"title": "Goldman sees gold at $4K by year-end", "summary": "..."}
    result = await content_agent.is_gold_relevant_or_systemic_shock(
        story, GATE_CONFIG, client=client
    )

    assert result["keep"] is True
    assert result["reject_reason"] is None
    assert result["sentiment"] == "bullish"


@pytest.mark.asyncio
async def test_gold_gate_keeps_neutral_record_high():
    """Gate keeps neutral factual stories (record high) with keep=True."""
    client = AsyncMock()
    response = MagicMock()
    response.content = [
        MagicMock(
            text='{"is_gold_relevant": true, "primary_subject_is_specific_miner": false, "company": null, "sentiment": "neutral"}'
        )
    ]
    client.messages.create = AsyncMock(return_value=response)

    story = {"title": "Gold hits new record high", "summary": "..."}
    result = await content_agent.is_gold_relevant_or_systemic_shock(
        story, GATE_CONFIG, client=client
    )

    assert result["keep"] is True
    assert result["reject_reason"] is None
    assert result["sentiment"] == "neutral"


@pytest.mark.asyncio
async def test_gold_gate_fail_open_on_parse_error():
    """Gate fails open (keep=True, sentiment=None) when Haiku returns non-JSON."""
    client = AsyncMock()
    response = MagicMock()
    response.content = [MagicMock(text="not valid json at all")]
    client.messages.create = AsyncMock(return_value=response)

    story = {"title": "Some gold story", "summary": "..."}
    result = await content_agent.is_gold_relevant_or_systemic_shock(
        story, GATE_CONFIG, client=client
    )

    assert result["keep"] is True
    assert result["reject_reason"] is None
    assert result["sentiment"] is None


@pytest.mark.asyncio
async def test_gold_gate_flag_disabled():
    """When content_bearish_filter_enabled='false', bearish stories are NOT rejected."""
    client = AsyncMock()
    response = MagicMock()
    response.content = [
        MagicMock(
            text='{"is_gold_relevant": true, "primary_subject_is_specific_miner": false, "company": null, "sentiment": "bearish"}'
        )
    ]
    client.messages.create = AsyncMock(return_value=response)

    config_flag_off = {
        "content_gold_gate_enabled": "true",
        "content_gold_gate_model": "claude-haiku-4-5",
        "content_bearish_filter_enabled": "false",
    }
    story = {"title": "Morgan Stanley cuts gold price forecast by almost 10%", "summary": "..."}
    result = await content_agent.is_gold_relevant_or_systemic_shock(
        story, config_flag_off, client=client
    )

    assert result["keep"] is True


# ---------------------------------------------------------------------------
# fetch_analytical_historical_stories — quick-260423-lvp T1
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_analytical_historical_stories_returns_story_shape():
    """fetch_analytical_historical_stories returns story dicts with the
    expected keys (title, link, published, summary, source_name)."""
    from datetime import datetime

    fake_results = {
        "news_results": [
            {
                "title": "Gold during wars: a historical analysis",
                "link": "http://example.com/gold-wars",
                "date": "2026-04-23T12:00:00Z",
                "snippet": "Gold historically surges during major conflicts.",
                "source": {"name": "KitcoNews"},
            }
        ]
    }

    mock_client_instance = MagicMock()
    mock_client_instance.search = MagicMock(return_value=fake_results)

    with (
        patch("agents.content_agent.get_settings") as mock_settings,
        patch("agents.content_agent.serpapi.Client", return_value=mock_client_instance),
    ):
        mock_settings.return_value.serpapi_api_key = "fake-key"
        stories = await content_agent.fetch_analytical_historical_stories(
            ["gold during wars", "gold recessions 2008"]
        )

    assert len(stories) >= 1
    story = stories[0]
    assert "title" in story
    assert "link" in story
    assert "published" in story
    assert "summary" in story
    assert "source_name" in story
    assert story["title"] == "Gold during wars: a historical analysis"
    assert story["source_name"] == "KitcoNews"
    assert isinstance(story["published"], datetime)


@pytest.mark.asyncio
async def test_fetch_analytical_historical_stories_handles_no_client():
    """fetch_analytical_historical_stories returns [] when SerpAPI key is missing."""
    with patch("agents.content_agent.get_settings") as mock_settings:
        mock_settings.return_value.serpapi_api_key = None
        stories = await content_agent.fetch_analytical_historical_stories(["gold during wars"])

    assert stories == []


# ---------------------------------------------------------------------------
# recency_score — quick-260424-j5i D3: new <48h=0.3 bucket
# ---------------------------------------------------------------------------


def test_recency_score_48h_bucket():
    """D3 (j5i): recency_score grows a <48h=0.3 bucket between <24h=0.4 and >=48h=0.2.

    - 25h old  → 0.3 (previously 0.2 — new softer bucket)
    - 47h old  → 0.3 (inside new bucket)
    - 49h old  → 0.2 (floor unchanged)
    Bucket-below (22h) and bucket-above (>=48h) assertions lock both edges.
    """
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    assert content_agent.recency_score(now - timedelta(hours=25)) == 0.3
    assert content_agent.recency_score(now - timedelta(hours=47)) == 0.3
    assert content_agent.recency_score(now - timedelta(hours=49)) == 0.2
    # Sanity-preserve <24h edge unaffected by the new bucket.
    assert content_agent.recency_score(now - timedelta(hours=22)) == 0.4
