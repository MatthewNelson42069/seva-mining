import pytest

# Wave 0 stub — skip until content_bundles router exists (Plan 03)
pytest.skip("content_bundles router not implemented yet (Plan 11-03)", allow_module_level=True)


async def test_get_content_bundle_returns_full_bundle(authed_client, seeded_bundle):
    """GET /content-bundles/{id} returns 200 with full payload for authenticated operator."""
    pass


async def test_get_content_bundle_requires_auth(client, seeded_bundle):
    """GET /content-bundles/{id} returns 401 without token."""
    pass


async def test_get_content_bundle_returns_404_for_missing(authed_client):
    """GET /content-bundles/{random_uuid} returns 404."""
    pass


async def test_rerender_returns_202(authed_client, seeded_bundle):
    """POST /content-bundles/{id}/rerender returns 202 with {bundle_id, render_job_id, enqueued_at}."""
    pass


async def test_rerender_clears_existing_images(authed_client, seeded_bundle_with_images):
    """POST /content-bundles/{id}/rerender sets bundle.rendered_images to [] in DB."""
    pass


async def test_rerender_404_on_missing_bundle(authed_client):
    """POST /content-bundles/{random_uuid}/rerender returns 404."""
    pass
