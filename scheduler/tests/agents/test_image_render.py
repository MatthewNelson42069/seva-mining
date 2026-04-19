"""
Integration tests for agents.image_render_agent — Plan 11-02 Task 1.

Covers:
  - 4-image output for infographic bundles (T1)
  - 2-image output for quote bundles (T2)
  - Compliance gate (T3)
  - Unsupported format gate (T4)
  - Per-role retry on transient failure (T5)
  - Silent-fail on permanent failure (T6)
  - R2 upload URL shape + no ACL kwarg (T7)

All external dependencies (Imagen API, aioboto3, SQLAlchemy engine) are mocked.
Tests use pytest-asyncio (asyncio_mode=auto set in pyproject.toml).
"""
import os
import sys
import uuid
from unittest.mock import AsyncMock, MagicMock

# Ensure scheduler root is on sys.path for absolute imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

# Inject required env vars before any scheduler module imports.
# Must include ALL vars that other test files rely on via lru_cache(get_settings).
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://fake.neon.tech/db?ssl=require")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test-fake")
os.environ.setdefault("X_API_BEARER_TOKEN", "test-bearer")
os.environ.setdefault("X_API_KEY", "test-key")
os.environ.setdefault("X_API_SECRET", "test-secret")
os.environ.setdefault("SERPAPI_API_KEY", "x")
os.environ.setdefault("TWILIO_ACCOUNT_SID", "AC_test_sid")
os.environ.setdefault("TWILIO_AUTH_TOKEN", "test_auth_token")
os.environ.setdefault("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
os.environ.setdefault("DIGEST_WHATSAPP_TO", "whatsapp:+15550001234")
os.environ.setdefault("FRONTEND_URL", "https://x.com")
os.environ.setdefault("R2_ACCOUNT_ID", "test-account-id")
os.environ.setdefault("R2_ACCESS_KEY_ID", "test-access-key")
os.environ.setdefault("R2_SECRET_ACCESS_KEY", "test-secret-key")
os.environ.setdefault("R2_BUCKET", "seva-test-bucket")
os.environ.setdefault("R2_PUBLIC_BASE_URL", "https://pub.r2.dev/seva-test")
os.environ.setdefault("GEMINI_API_KEY", "test-gemini-key")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FAKE_PNG = b"\x89PNG\r\n\x1a\nFAKE"
R2_BASE_URL = "https://pub.r2.dev/seva-test"


def _make_bundle(
    bundle_id=None,
    content_type="infographic",
    compliance_passed=True,
    rendered_images=None,
    story_headline="African Central Banks Gold Accumulation",
    draft_content=None,
):
    """Return a MagicMock resembling a ContentBundle ORM row."""
    bundle = MagicMock()
    bundle.id = bundle_id or uuid.uuid4()
    bundle.content_type = content_type
    bundle.compliance_passed = compliance_passed
    bundle.rendered_images = rendered_images
    bundle.story_headline = story_headline
    bundle.draft_content = draft_content or {
        "format": content_type,
        "headline": "African central banks accumulate gold",
        "key_stats": [{"stat": "7 tonnes", "source": "WGC"}],
        "visual_structure": "bar chart comparison",
        "instagram_brief": {
            "headline": "IG headline",
            "carousel_slides": [
                {"slide_number": 1, "headline": "Slide 1 headline", "key_stat": "7T"},
                {"slide_number": 2, "headline": "Slide 2 headline", "key_stat": "5T"},
                {"slide_number": 3, "headline": "Slide 3 headline", "key_stat": "3T"},
            ],
        },
    }
    return bundle


def _make_session_factory(bundle):
    """Return a mock async_sessionmaker whose context manager yields a session containing bundle."""
    session = AsyncMock()

    # scalar_one_or_none returns the bundle
    scalar_result = MagicMock()
    scalar_result.scalar_one_or_none.return_value = bundle
    session.execute = AsyncMock(return_value=scalar_result)
    session.commit = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)

    factory = MagicMock()
    factory.return_value = session
    return factory, session


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_render_bundle_infographic_produces_four_images(fake_imagen_client, fake_r2_client, monkeypatch):
    """render_bundle_job on an infographic bundle writes exactly 4 entries to rendered_images."""
    from agents.image_render_agent import render_bundle_job

    fake_r2_session, fake_s3 = fake_r2_client
    bundle = _make_bundle(content_type="infographic")
    session_factory, session = _make_session_factory(bundle)

    monkeypatch.setattr("agents.image_render_agent.async_sessionmaker", lambda *a, **kw: session_factory)
    monkeypatch.setattr("agents.image_render_agent.genai.Client", lambda: fake_imagen_client)
    monkeypatch.setattr("agents.image_render_agent.aioboto3.Session", lambda: fake_r2_session)

    await render_bundle_job(str(bundle.id))

    assert bundle.rendered_images is not None
    assert len(bundle.rendered_images) == 4
    roles = [img["role"] for img in bundle.rendered_images]
    assert roles == ["twitter_visual", "instagram_slide_1", "instagram_slide_2", "instagram_slide_3"]
    for img in bundle.rendered_images:
        assert img["url"].startswith(R2_BASE_URL)
        assert "role" in img
        assert "generated_at" in img
    session.commit.assert_called_once()


async def test_render_bundle_quote_produces_two_images(fake_imagen_client, fake_r2_client, monkeypatch):
    """render_bundle_job on a quote bundle writes exactly 2 entries to rendered_images."""
    from agents.image_render_agent import render_bundle_job

    fake_r2_session, fake_s3 = fake_r2_client
    bundle = _make_bundle(
        content_type="quote",
        draft_content={
            "format": "quote",
            "twitter_post": "Gold is the ultimate safe haven",
            "instagram_post": "Gold is the ultimate safe haven",
            "attributed_to": "Ray Dalio",
            "source_url": "https://example.com",
        },
    )
    session_factory, session = _make_session_factory(bundle)

    monkeypatch.setattr("agents.image_render_agent.async_sessionmaker", lambda *a, **kw: session_factory)
    monkeypatch.setattr("agents.image_render_agent.genai.Client", lambda: fake_imagen_client)
    monkeypatch.setattr("agents.image_render_agent.aioboto3.Session", lambda: fake_r2_session)

    await render_bundle_job(str(bundle.id))

    assert bundle.rendered_images is not None
    assert len(bundle.rendered_images) == 2
    roles = [img["role"] for img in bundle.rendered_images]
    assert roles == ["twitter_visual", "instagram_slide_1"]
    session.commit.assert_called_once()


async def test_render_bundle_skips_when_compliance_failed(fake_imagen_client, fake_r2_client, monkeypatch):
    """render_bundle_job must not render if bundle.compliance_passed is False (D-11)."""
    from agents.image_render_agent import render_bundle_job

    fake_r2_session, fake_s3 = fake_r2_client
    bundle = _make_bundle(compliance_passed=False)
    session_factory, session = _make_session_factory(bundle)

    monkeypatch.setattr("agents.image_render_agent.async_sessionmaker", lambda *a, **kw: session_factory)
    monkeypatch.setattr("agents.image_render_agent.genai.Client", lambda: fake_imagen_client)
    monkeypatch.setattr("agents.image_render_agent.aioboto3.Session", lambda: fake_r2_session)

    await render_bundle_job(str(bundle.id))

    # Imagen must not be called at all
    fake_imagen_client.aio.models.generate_images.assert_not_called()
    # rendered_images must remain unchanged (None by default)
    assert bundle.rendered_images is None
    # Session should not be committed
    session.commit.assert_not_called()


async def test_render_bundle_skips_unsupported_format(fake_imagen_client, fake_r2_client, monkeypatch):
    """render_bundle_job returns without calling Imagen for formats with no render roles (thread, etc.)."""
    from agents.image_render_agent import render_bundle_job

    fake_r2_session, _ = fake_r2_client
    bundle = _make_bundle(content_type="thread", compliance_passed=True)
    session_factory, session = _make_session_factory(bundle)

    monkeypatch.setattr("agents.image_render_agent.async_sessionmaker", lambda *a, **kw: session_factory)
    monkeypatch.setattr("agents.image_render_agent.genai.Client", lambda: fake_imagen_client)
    monkeypatch.setattr("agents.image_render_agent.aioboto3.Session", lambda: fake_r2_session)

    await render_bundle_job(str(bundle.id))

    fake_imagen_client.aio.models.generate_images.assert_not_called()
    assert bundle.rendered_images is None
    session.commit.assert_not_called()


async def test_render_bundle_retries_on_transient_failure(fake_r2_client, monkeypatch):
    """When generate_images raises on attempt 1+2 and succeeds on attempt 3, rendered_images has correct entries."""
    from agents.image_render_agent import render_bundle_job

    fake_r2_session, fake_s3 = fake_r2_client
    bundle = _make_bundle(content_type="infographic")
    session_factory, session = _make_session_factory(bundle)

    # Build a fresh fake client where the FIRST two calls to generate_images fail,
    # then subsequent calls succeed. This simulates the first role retrying twice.
    fail_count = {"n": 0}

    async def flaky_generate_images(*args, **kwargs):
        fail_count["n"] += 1
        if fail_count["n"] <= 2:
            raise RuntimeError("Transient API error")
        fake_image = MagicMock()
        fake_image.image.image_bytes = FAKE_PNG
        response = MagicMock()
        response.generated_images = [fake_image]
        return response

    flaky_client = MagicMock()
    flaky_client.aio.models.generate_images = AsyncMock(side_effect=flaky_generate_images)

    # Patch asyncio.sleep to avoid real delays in tests
    sleep_mock = AsyncMock()
    monkeypatch.setattr("agents.image_render_agent.asyncio.sleep", sleep_mock)
    monkeypatch.setattr("agents.image_render_agent.async_sessionmaker", lambda *a, **kw: session_factory)
    monkeypatch.setattr("agents.image_render_agent.genai.Client", lambda: flaky_client)
    monkeypatch.setattr("agents.image_render_agent.aioboto3.Session", lambda: fake_r2_session)

    await render_bundle_job(str(bundle.id))

    # After 2 failures then success, the first role should have produced 1 image.
    # Remaining roles should succeed on first try (total calls > 2).
    assert bundle.rendered_images is not None
    # At minimum the first role succeeded on attempt 3
    assert len(bundle.rendered_images) >= 1
    # logger.warning should have been called twice (for the two failures)
    assert sleep_mock.call_count == 2
    session.commit.assert_called_once()


async def test_render_bundle_silent_fail_after_permanent_error(monkeypatch):
    """When generate_images raises on ALL attempts for all roles, render_bundle_job returns None (no raise) — D-18."""
    from agents.image_render_agent import render_bundle_job

    bundle = _make_bundle(content_type="infographic")
    session_factory, session = _make_session_factory(bundle)

    # All calls to generate_images always raise
    always_fail_client = MagicMock()
    always_fail_client.aio.models.generate_images = AsyncMock(side_effect=RuntimeError("Permanent API error"))

    # Fake R2 session (should never be reached, but needed for monkeypatching)
    fake_r2_session = MagicMock()

    sleep_mock = AsyncMock()
    monkeypatch.setattr("agents.image_render_agent.asyncio.sleep", sleep_mock)
    monkeypatch.setattr("agents.image_render_agent.async_sessionmaker", lambda *a, **kw: session_factory)
    monkeypatch.setattr("agents.image_render_agent.genai.Client", lambda: always_fail_client)
    monkeypatch.setattr("agents.image_render_agent.aioboto3.Session", lambda: fake_r2_session)

    # Must NOT raise — silent-fail contract
    result = await render_bundle_job(str(bundle.id))
    assert result is None

    # rendered_images should be set to an empty list (not left None)
    # This allows frontend polling age-ceiling to work (D-14)
    assert bundle.rendered_images == []
    session.commit.assert_called_once()


async def test_upload_to_r2_returns_public_url(fake_r2_client, monkeypatch):
    """_upload_to_r2 returns {R2_PUBLIC_BASE_URL}/{object_key} exactly, and put_object has no ACL kwarg."""
    from agents.image_render_agent import _upload_to_r2

    fake_r2_session, fake_s3 = fake_r2_client

    monkeypatch.setattr("agents.image_render_agent.aioboto3.Session", lambda: fake_r2_session)

    url = await _upload_to_r2(b"bytes", "test/key.png")

    assert url == f"{R2_BASE_URL}/test/key.png"

    # put_object must be called with correct args and NO 'ACL' kwarg (R2 rejects ACLs — Pitfall 4)
    fake_s3.put_object.assert_called_once()
    call_kwargs = fake_s3.put_object.call_args.kwargs
    assert call_kwargs["Bucket"] == "seva-test-bucket"
    assert call_kwargs["Key"] == "test/key.png"
    assert call_kwargs["Body"] == b"bytes"
    assert call_kwargs["ContentType"] == "image/png"
    assert "ACL" not in call_kwargs
