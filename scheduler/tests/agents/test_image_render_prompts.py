"""
Unit tests for _build_prompt in agents.image_render_agent.

Scope (post quick-260419-t78):
- _build_prompt is called ONLY for the `quote` format (ROLES_BY_FORMAT key).
- Infographic bundles are routed to _render_infographic_charts() which calls the
  Node chart renderer; the infographic branches of _build_prompt were removed.
- The instagram_slide_2/3 roles and infographic branches that previously lived
  here are also removed (see quick-260419-lvy for Instagram purge rationale).

Tests confirm:
  1. All three brand hex codes appear in every prompt (D-05 enforcement)
  2. Role-specific content is embedded (attribution, quote text)
  3. Graceful fallback when draft_content keys are missing / malformed

These tests import _build_prompt directly and do NOT call Imagen — they are
pure string-assertion unit tests with no external dependencies.
"""
import os
import sys

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

QUOTE_DRAFT = {
    "format": "quote",
    "twitter_post": "Gold is the only true global currency without a counterparty.",
    "instagram_post": "Gold is the only true global currency without a counterparty risk.",
    "attributed_to": "Ray Dalio",
    "source_url": "https://example.com/dalio",
}


# ---------------------------------------------------------------------------
# Brand palette enforcement (D-05)
# ---------------------------------------------------------------------------

BRAND_HEX_CODES = ["#F0ECE4", "#0C1B32", "#D4AF37"]


def _assert_brand_palette(prompt: str):
    """Assert all three brand hex codes appear in the prompt."""
    for hex_code in BRAND_HEX_CODES:
        assert hex_code in prompt, f"Expected brand hex code {hex_code!r} in prompt: {prompt[:200]}..."


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


def test_prompt_never_raises_on_malformed_draft_content():
    """_build_prompt must return a valid non-empty string even when draft_content is empty dict."""
    # Should never raise regardless of input — hits the fallback branch.
    prompt = _build_prompt("twitter_visual", {}, "Story headline")
    _assert_brand_palette(prompt)
    assert isinstance(prompt, str)
    assert len(prompt) > 0
