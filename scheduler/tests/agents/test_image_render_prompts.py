"""
Unit tests for _build_prompt in agents.image_render_agent — Plan 11-02 Task 2.

Tests confirm:
  1. All three brand hex codes appear in every prompt (D-05 enforcement)
  2. Role-specific content is embedded (slide headlines, attribution, quote text)
  3. Graceful fallback when draft_content keys are missing

These tests import _build_prompt directly and do NOT call Imagen — they are
pure string-assertion unit tests with no external dependencies.
"""
import os
import sys
import pytest

# Ensure scheduler root is on sys.path for absolute imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

# Required env vars — must match what other test files expect via lru_cache(get_settings)
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://fake.neon.tech/db?ssl=require")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test-fake")
os.environ.setdefault("X_API_BEARER_TOKEN", "test-bearer")
os.environ.setdefault("TWILIO_ACCOUNT_SID", "AC_test_sid")
os.environ.setdefault("TWILIO_AUTH_TOKEN", "test_auth_token")
os.environ.setdefault("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
os.environ.setdefault("DIGEST_WHATSAPP_TO", "whatsapp:+15550001234")

from agents.image_render_agent import _build_prompt  # noqa: E402

# ---------------------------------------------------------------------------
# Fixtures / test data
# ---------------------------------------------------------------------------

INFOGRAPHIC_DRAFT = {
    "format": "infographic",
    "headline": "African Central Banks Gold Accumulation Hits 7-Year High",
    "key_stats": [
        {"stat": "7 tonnes net purchase Q1 2026", "source": "WGC"},
        {"stat": "3 consecutive quarters of buying", "source": "IMF"},
    ],
    "visual_structure": "bar chart with country breakdown",
    "caption_text": "Central banks are net gold buyers again.",
    "instagram_brief": {
        "headline": "Central Banks Are Buying Gold Again",
        "carousel_slides": [
            {
                "slide_number": 1,
                "headline": "7 Tonnes Purchased Q1 2026",
                "key_stat": "7T net purchase",
            },
            {
                "slide_number": 2,
                "headline": "Three Consecutive Quarters of Buying",
                "key_stat": "3 quarters",
            },
            {
                "slide_number": 3,
                "headline": "Africa Leads Global Central Bank Gold Buying",
                "key_stat": "55% share",
            },
        ],
        "caption": "Follow for daily gold market insights.",
    },
}

QUOTE_DRAFT = {
    "format": "quote",
    "twitter_post": "Gold is the only true global currency without a counterparty.",
    "instagram_post": "Gold is the only true global currency without a counterparty risk.",
    "attributed_to": "Ray Dalio",
    "source_url": "https://example.com/dalio",
}

HEADLINE = "African Central Banks Gold Accumulation"


# ---------------------------------------------------------------------------
# Brand palette enforcement (D-05)
# ---------------------------------------------------------------------------

BRAND_HEX_CODES = ["#F0ECE4", "#0C1B32", "#D4AF37"]


def _assert_brand_palette(prompt: str):
    """Assert all three brand hex codes appear in the prompt."""
    for hex_code in BRAND_HEX_CODES:
        assert hex_code in prompt, f"Expected brand hex code {hex_code!r} in prompt: {prompt[:200]}..."


# ---------------------------------------------------------------------------
# Tests: infographic prompts
# ---------------------------------------------------------------------------


def test_prompt_infographic_twitter_visual_contains_brand_hex():
    """_build_prompt for twitter_visual/infographic must contain all three brand hex codes (D-05)."""
    prompt = _build_prompt("twitter_visual", INFOGRAPHIC_DRAFT, HEADLINE)
    _assert_brand_palette(prompt)
    assert len(prompt) > 0


def test_prompt_infographic_slide_1_references_slide_headline():
    """_build_prompt for instagram_slide_1/infographic must contain slide 1 headline text."""
    prompt = _build_prompt("instagram_slide_1", INFOGRAPHIC_DRAFT, HEADLINE)
    _assert_brand_palette(prompt)
    slide_1_headline = INFOGRAPHIC_DRAFT["instagram_brief"]["carousel_slides"][0]["headline"]
    assert slide_1_headline in prompt, (
        f"Expected slide 1 headline {slide_1_headline!r} in prompt: {prompt[:200]}..."
    )


def test_prompt_infographic_slide_2_references_slide_headline():
    """_build_prompt for instagram_slide_2/infographic must contain slide 2 headline text."""
    prompt = _build_prompt("instagram_slide_2", INFOGRAPHIC_DRAFT, HEADLINE)
    _assert_brand_palette(prompt)
    slide_2_headline = INFOGRAPHIC_DRAFT["instagram_brief"]["carousel_slides"][1]["headline"]
    assert slide_2_headline in prompt, (
        f"Expected slide 2 headline {slide_2_headline!r} in prompt: {prompt[:200]}..."
    )


def test_prompt_infographic_slide_3_references_slide_headline():
    """_build_prompt for instagram_slide_3/infographic must contain slide 3 headline text."""
    prompt = _build_prompt("instagram_slide_3", INFOGRAPHIC_DRAFT, HEADLINE)
    _assert_brand_palette(prompt)
    slide_3_headline = INFOGRAPHIC_DRAFT["instagram_brief"]["carousel_slides"][2]["headline"]
    assert slide_3_headline in prompt, (
        f"Expected slide 3 headline {slide_3_headline!r} in prompt: {prompt[:200]}..."
    )


# ---------------------------------------------------------------------------
# Tests: quote prompts
# ---------------------------------------------------------------------------


def test_prompt_quote_twitter_visual_contains_attributed_to():
    """_build_prompt for twitter_visual/quote must contain the attributed_to value."""
    prompt = _build_prompt("twitter_visual", QUOTE_DRAFT, "Gold quote")
    _assert_brand_palette(prompt)
    attributed_to = QUOTE_DRAFT["attributed_to"]
    assert attributed_to in prompt, (
        f"Expected attribution {attributed_to!r} in prompt: {prompt[:200]}..."
    )


def test_prompt_quote_instagram_slide_1_contains_quote_text():
    """_build_prompt for instagram_slide_1/quote must contain instagram_post or twitter_post text."""
    prompt = _build_prompt("instagram_slide_1", QUOTE_DRAFT, "Gold quote")
    _assert_brand_palette(prompt)
    # Either the instagram_post or twitter_post text should appear
    instagram_post = QUOTE_DRAFT["instagram_post"]
    twitter_post = QUOTE_DRAFT["twitter_post"]
    assert instagram_post in prompt or twitter_post in prompt, (
        f"Expected quote text in prompt: {prompt[:200]}..."
    )


# ---------------------------------------------------------------------------
# Tests: fallback / robustness
# ---------------------------------------------------------------------------


def test_prompt_missing_slide_falls_back_to_headline():
    """_build_prompt for instagram_slide_3 with draft missing carousel slides falls back to story_headline."""
    draft_without_carousel = {
        "format": "infographic",
        "headline": "Gold hits $3500",
        # No instagram_brief
    }
    # Must not raise
    prompt = _build_prompt("instagram_slide_3", draft_without_carousel, HEADLINE)
    _assert_brand_palette(prompt)
    # Should contain the story headline as fallback
    assert HEADLINE in prompt, (
        f"Expected story_headline {HEADLINE!r} as fallback in prompt: {prompt[:200]}..."
    )
    assert len(prompt) > 0


def test_prompt_never_raises_on_malformed_draft_content():
    """_build_prompt must return a valid non-empty string even when draft_content is empty dict."""
    # Should never raise regardless of input
    prompt = _build_prompt("twitter_visual", {}, "Story headline")
    _assert_brand_palette(prompt)
    assert isinstance(prompt, str)
    assert len(prompt) > 0
