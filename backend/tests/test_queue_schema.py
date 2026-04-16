import pytest

# Wave 0 stub — DraftItemResponse.engagement_snapshot added in this same plan (Task 3)
# but leaving tests skipped until real assertion fixtures exist in Plan 03.
pytest.skip("queue schema test deferred to Plan 11-03", allow_module_level=True)


async def test_queue_response_includes_engagement_snapshot(authed_client):
    """Queue list response items include engagement_snapshot with content_bundle_id for content-agent drafts."""
    pass
