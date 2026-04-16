import pytest

# Wave 0 stub — skip until image_render_agent module exists (Plan 02)
pytest.skip("image_render_agent not implemented yet (Plan 11-02)", allow_module_level=True)

from agents.image_render_agent import render_bundle_job  # noqa: E402


async def test_render_bundle_infographic_produces_four_images():
    """render_bundle_job on an infographic bundle writes 4 entries to rendered_images."""
    pass


async def test_render_bundle_quote_produces_two_images():
    """render_bundle_job on a quote bundle writes 2 entries to rendered_images."""
    pass


async def test_render_bundle_skips_when_compliance_failed():
    """render_bundle_job must not render if bundle.compliance_passed is False (D-11)."""
    pass


async def test_render_bundle_retries_on_transient_failure():
    """render_bundle_job retries up to 3 times with ~2s/8s/30s backoff (D-18)."""
    pass


async def test_render_bundle_silent_fail_after_permanent_error():
    """On 3 retries exhausted, render logs error but raises nothing (D-18)."""
    pass


async def test_upload_to_r2_returns_public_url():
    """_upload_to_r2 returns {R2_PUBLIC_BASE_URL}/{object_key} exactly (no ACL)."""
    pass
