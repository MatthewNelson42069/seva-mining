"""
Tests for scheduler/agents/image_render_agent.py — infographic branch replacement.

Tests verify:
- Infographic bundles route through ChartRendererClient (not genai.Client)
- Quote bundles still use Gemini (unchanged path)
- Role generation for 1 and 2 charts
- Missing chart_spec gracefully produces empty rendered_images
- ROLES_BY_FORMAT contains no instagram_slide entries for infographic
"""
import os
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

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
os.environ.setdefault("SERPAPI_API_KEY", "x")
os.environ.setdefault("FRONTEND_URL", "https://x.com")
os.environ.setdefault("R2_ACCOUNT_ID", "fake_account_id")
os.environ.setdefault("R2_ACCESS_KEY_ID", "fake_key")
os.environ.setdefault("R2_SECRET_ACCESS_KEY", "fake_secret")
os.environ.setdefault("R2_BUCKET", "fake_bucket")
os.environ.setdefault("R2_PUBLIC_BASE_URL", "https://fake.r2.cloudflarestorage.com")
os.environ.setdefault("GEMINI_API_KEY", "fake-gemini-key")


def make_bundle(content_type='infographic', draft_content=None, compliance_passed=True):
    """Create a minimal fake ContentBundle-like object."""
    bundle = MagicMock()
    bundle.id = uuid4()
    bundle.content_type = content_type
    bundle.compliance_passed = compliance_passed
    bundle.story_headline = 'Gold Price Hits Record High'
    bundle.draft_content = draft_content or {}
    bundle.rendered_images = None
    return bundle


def make_infographic_draft(charts=None, twitter_caption='Test caption'):
    """Create a valid infographic draft_content with chart_spec."""
    return {
        'format': 'infographic',
        'charts': charts or [
            {
                'type': 'bar',
                'title': 'Gold Price YTD',
                'data': [{'label': 'Jan', 'value': 2050.0}],
            }
        ],
        'twitter_caption': twitter_caption,
    }


# ---------------------------------------------------------------------------
# test_infographic_calls_chart_renderer_not_gemini
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_infographic_calls_chart_renderer_not_gemini():
    """Mock ChartRendererClient.render_charts; verify genai.Client is NOT instantiated for infographic bundles."""
    import agents.image_render_agent as ira

    bundle = make_bundle(content_type='infographic', draft_content=make_infographic_draft())
    bundle_id = bundle.id

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=bundle))
    )
    mock_session.commit = AsyncMock()

    mock_client = AsyncMock()
    mock_client.render_charts = AsyncMock(return_value=[b'PNG1'])

    with patch('agents.image_render_agent._upload_to_r2', new=AsyncMock(return_value='https://fake.r2.dev/test.png')):
        with patch('agents.chart_renderer_client.get_chart_renderer_client', return_value=mock_client):
            with patch('google.genai.Client') as mock_genai_cls:
                await ira._render_and_persist(mock_session, bundle_id)
                # genai.Client should NOT be instantiated for infographic
                mock_genai_cls.assert_not_called()

    mock_client.render_charts.assert_called_once()


# ---------------------------------------------------------------------------
# test_infographic_one_chart_produces_twitter_visual
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_infographic_one_chart_produces_twitter_visual():
    """render_charts returns [b'PNGBYTES']; rendered_images has role 'twitter_visual'."""
    import agents.image_render_agent as ira

    bundle = make_bundle(content_type='infographic', draft_content=make_infographic_draft())
    bundle_id = bundle.id

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=bundle))
    )
    mock_session.commit = AsyncMock()

    mock_client = AsyncMock()
    mock_client.render_charts = AsyncMock(return_value=[b'PNGBYTES'])

    with patch('agents.image_render_agent._upload_to_r2', new=AsyncMock(return_value='https://fake.r2.dev/test.png')):
        with patch('agents.chart_renderer_client.get_chart_renderer_client', return_value=mock_client):
            await ira._render_and_persist(mock_session, bundle_id)

    assert bundle.rendered_images is not None
    assert len(bundle.rendered_images) == 1
    assert bundle.rendered_images[0]['role'] == 'twitter_visual'
    assert bundle.rendered_images[0]['url'] == 'https://fake.r2.dev/test.png'


# ---------------------------------------------------------------------------
# test_infographic_two_charts_produces_two_roles
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_infographic_two_charts_produces_two_roles():
    """render_charts returns [b'PNG1', b'PNG2']; rendered_images has roles ['twitter_visual','twitter_visual_2']."""
    import agents.image_render_agent as ira

    draft = make_infographic_draft(charts=[
        {'type': 'bar', 'title': 'Chart 1', 'data': [{'label': 'A', 'value': 100.0}]},
        {'type': 'line', 'title': 'Chart 2', 'data': [{'label': 'B', 'value': 200.0}]},
    ])
    bundle = make_bundle(content_type='infographic', draft_content=draft)
    bundle_id = bundle.id

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=bundle))
    )
    mock_session.commit = AsyncMock()

    mock_client = AsyncMock()
    mock_client.render_charts = AsyncMock(return_value=[b'PNG1', b'PNG2'])

    call_count = [0]
    async def fake_upload(image_bytes, object_key):
        call_count[0] += 1
        return f'https://fake.r2.dev/image{call_count[0]}.png'

    with patch('agents.image_render_agent._upload_to_r2', side_effect=fake_upload):
        with patch('agents.chart_renderer_client.get_chart_renderer_client', return_value=mock_client):
            await ira._render_and_persist(mock_session, bundle_id)

    assert len(bundle.rendered_images) == 2
    roles = [img['role'] for img in bundle.rendered_images]
    assert 'twitter_visual' in roles
    assert 'twitter_visual_2' in roles


# ---------------------------------------------------------------------------
# test_infographic_chart_renderer_returns_none_produces_empty
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_infographic_chart_renderer_returns_none_produces_empty():
    """render_charts returns [None]; rendered_images=[] (partial-success path)."""
    import agents.image_render_agent as ira

    bundle = make_bundle(content_type='infographic', draft_content=make_infographic_draft())
    bundle_id = bundle.id

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=bundle))
    )
    mock_session.commit = AsyncMock()

    mock_client = AsyncMock()
    mock_client.render_charts = AsyncMock(return_value=[None])

    with patch('agents.chart_renderer_client.get_chart_renderer_client', return_value=mock_client):
        await ira._render_and_persist(mock_session, bundle_id)

    assert bundle.rendered_images == []


# ---------------------------------------------------------------------------
# test_quote_format_unchanged_uses_gemini
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_quote_format_unchanged_uses_gemini():
    """Mock genai.Client; quote bundle still calls generate_images (Gemini path untouched)."""
    import agents.image_render_agent as ira

    draft = {
        'format': 'quote',
        'twitter_post': '"Gold is money" — Jim Rogers',
        'speaker': 'Jim Rogers',
    }
    bundle = make_bundle(content_type='quote', draft_content=draft)
    bundle_id = bundle.id

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=bundle))
    )
    mock_session.commit = AsyncMock()

    # Fake Gemini response
    fake_image = MagicMock()
    fake_image.image.image_bytes = b'GEMINI_PNG'
    fake_genai_response = MagicMock()
    fake_genai_response.generated_images = [fake_image]

    mock_genai_client = AsyncMock()
    mock_genai_client.aio.models.generate_images = AsyncMock(return_value=fake_genai_response)

    with patch('google.genai.Client', return_value=mock_genai_client):
        with patch('agents.image_render_agent._upload_to_r2', new=AsyncMock(return_value='https://fake.r2.dev/quote.png')):
            await ira._render_and_persist(mock_session, bundle_id)

    # Gemini should have been called
    mock_genai_client.aio.models.generate_images.assert_called()
    assert bundle.rendered_images is not None


# ---------------------------------------------------------------------------
# test_instagram_slide_roles_absent
# ---------------------------------------------------------------------------

def test_instagram_slide_roles_absent():
    """ROLES_BY_FORMAT['infographic'] does NOT contain any 'instagram_slide_*' entry."""
    import agents.image_render_agent as ira
    # infographic key should not be in ROLES_BY_FORMAT at all
    infographic_roles = ira.ROLES_BY_FORMAT.get('infographic', [])
    role_names = [r[0] for r in infographic_roles]
    assert not any('instagram_slide' in r for r in role_names), \
        f"instagram_slide roles found in infographic: {role_names}"


# ---------------------------------------------------------------------------
# test_no_chart_spec_in_draft_content_skips_render
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_chart_spec_in_draft_content_skips_render():
    """Infographic bundle where draft_content has no 'charts' key → rendered_images=[] without calling chart renderer."""
    import agents.image_render_agent as ira

    # Old-style infographic draft without 'charts' key
    bundle = make_bundle(content_type='infographic', draft_content={
        'format': 'infographic',
        'headline': 'Gold at $2500',
        'key_stats': [{'stat': '$2500/oz'}],
        'visual_structure': 'bar chart',
    })
    bundle_id = bundle.id

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=bundle))
    )
    mock_session.commit = AsyncMock()

    mock_client = AsyncMock()
    mock_client.render_charts = AsyncMock(return_value=[])

    with patch('agents.chart_renderer_client.get_chart_renderer_client', return_value=mock_client):
        await ira._render_and_persist(mock_session, bundle_id)

    # render_charts should NOT be called — no charts key
    mock_client.render_charts.assert_not_called()
    assert bundle.rendered_images == []
