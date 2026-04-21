"""
Tests for the queue router: state machine, pagination, approve/reject endpoints.

Uses mocked approach: patch get_db dependency to return a mock AsyncSession.
DraftItem uses PostgreSQL ENUM so SQLite in-memory can't run schema-level tests.
"""
import json
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth import create_access_token
from app.database import get_db
from app.main import app

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_draft_item(
    *,
    id: UUID | None = None,
    status: str = "pending",
    platform: str = "content",
    alternatives: list | None = None,
) -> MagicMock:
    """Create a MagicMock that mimics a DraftItem ORM object."""
    item = MagicMock()
    item.id = id or uuid.uuid4()
    item.status = status
    item.platform = platform
    item.alternatives = alternatives if alternatives is not None else ["draft alt 1", "draft alt 2"]
    item.source_url = "https://x.com/example/1234"
    item.source_text = "Gold hits record highs"
    item.source_account = "@goldnews"
    item.follower_count = None
    item.score = 7.5
    item.quality_score = None
    item.rationale = "High relevance"
    item.urgency = "high"
    item.related_id = None
    item.rejection_reason = None
    item.edit_delta = None
    item.expires_at = None
    item.decided_at = None
    item.created_at = datetime(2026, 3, 31, 12, 0, 0, tzinfo=UTC)
    item.updated_at = None
    item.event_mode = None
    item.engagement_snapshot = None
    return item


def make_mock_db(item: MagicMock | None = None) -> AsyncMock:
    """Create a mock AsyncSession that returns a given item on execute."""
    mock_db = AsyncMock()

    scalars_result = MagicMock()
    scalars_result.all.return_value = [item] if item else []

    scalar_one_or_none_result = item

    execute_result = MagicMock()
    execute_result.scalars.return_value = scalars_result
    execute_result.scalar_one_or_none.return_value = scalar_one_or_none_result

    mock_db.execute = AsyncMock(return_value=execute_result)
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    return mock_db


def make_authed_headers() -> dict:
    """Return Authorization header with a valid test JWT."""
    token = create_access_token()
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Unit tests: state machine logic (_enforce_transition)
# ---------------------------------------------------------------------------

class TestStateMachine:
    """Direct unit tests for the transition enforcement logic."""

    async def test_pending_to_approved_is_valid(self):
        """pending -> approved should succeed."""
        from app.models.draft_item import DraftStatus
        from app.routers.queue import _enforce_transition

        item = make_draft_item(status="pending")
        # Should not raise
        await _enforce_transition(item, DraftStatus.approved)

    async def test_pending_to_edited_approved_is_valid(self):
        """pending -> edited_approved should succeed."""
        from app.models.draft_item import DraftStatus
        from app.routers.queue import _enforce_transition

        item = make_draft_item(status="pending")
        await _enforce_transition(item, DraftStatus.edited_approved)

    async def test_pending_to_rejected_is_valid(self):
        """pending -> rejected should succeed."""
        from app.models.draft_item import DraftStatus
        from app.routers.queue import _enforce_transition

        item = make_draft_item(status="pending")
        await _enforce_transition(item, DraftStatus.rejected)

    async def test_invalid_transition_raises_409(self):
        """approved -> approved should raise 409."""
        from fastapi import HTTPException

        from app.models.draft_item import DraftStatus
        from app.routers.queue import _enforce_transition

        item = make_draft_item(status="approved")
        with pytest.raises(HTTPException) as exc_info:
            await _enforce_transition(item, DraftStatus.approved)
        assert exc_info.value.status_code == 409

    async def test_rejected_to_approved_raises_409(self):
        """rejected -> approved should raise 409 (no re-approve)."""
        from fastapi import HTTPException

        from app.models.draft_item import DraftStatus
        from app.routers.queue import _enforce_transition

        item = make_draft_item(status="rejected")
        with pytest.raises(HTTPException) as exc_info:
            await _enforce_transition(item, DraftStatus.approved)
        assert exc_info.value.status_code == 409

    async def test_expired_cannot_be_approved(self):
        """expired -> approved should raise 409."""
        from fastapi import HTTPException

        from app.models.draft_item import DraftStatus
        from app.routers.queue import _enforce_transition

        item = make_draft_item(status="expired")
        with pytest.raises(HTTPException) as exc_info:
            await _enforce_transition(item, DraftStatus.approved)
        assert exc_info.value.status_code == 409

    def test_valid_transitions_structure(self):
        """VALID_TRANSITIONS must have DraftStatus.pending as key."""
        from app.models.draft_item import DraftStatus
        from app.routers.queue import VALID_TRANSITIONS

        assert DraftStatus.pending in VALID_TRANSITIONS
        allowed = VALID_TRANSITIONS[DraftStatus.pending]
        assert DraftStatus.approved in allowed
        assert DraftStatus.edited_approved in allowed
        assert DraftStatus.rejected in allowed


# ---------------------------------------------------------------------------
# HTTP endpoint tests
# ---------------------------------------------------------------------------

@pytest.fixture
def auth_headers():
    return make_authed_headers()


class TestApproveTransition:
    """Tests for PATCH /items/{id}/approve."""

    async def test_approve_pending_returns_200(self, auth_headers):
        """Approving a pending item returns 200 with updated status."""
        item = make_draft_item(status="pending")
        item_id = item.id

        mock_db = make_mock_db(item)

        async def refresh_side_effect(i):
            i.status = "approved"

        mock_db.refresh.side_effect = refresh_side_effect

        async def override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.patch(f"/items/{item_id}/approve", headers=auth_headers)
            assert resp.status_code == 200
        finally:
            app.dependency_overrides.pop(get_db, None)

    async def test_approve_sets_status_approved(self, auth_headers):
        """Plain approve (no edited_text) sets status=approved."""
        item = make_draft_item(status="pending")
        item_id = item.id

        mock_db = make_mock_db(item)

        async def override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.patch(f"/items/{item_id}/approve", headers=auth_headers)
            assert resp.status_code == 200
            # Confirm the ORM item status was set to approved
            assert item.status == "approved"
        finally:
            app.dependency_overrides.pop(get_db, None)

    async def test_edit_delta_preserved(self, auth_headers):
        """Approving with edited_text stores edit_delta=original alternatives[0] (D-14)."""
        original_alt = "Original draft alternative text"
        item = make_draft_item(status="pending", alternatives=[original_alt, "alt 2"])
        item_id = item.id

        mock_db = make_mock_db(item)

        async def override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.patch(
                    f"/items/{item_id}/approve",
                    json={"edited_text": "My polished version of the draft"},
                    headers=auth_headers,
                )
            assert resp.status_code == 200
            # edit_delta should be set to original first alternative
            assert item.edit_delta == original_alt
            assert item.status == "edited_approved"
        finally:
            app.dependency_overrides.pop(get_db, None)

    async def test_approve_already_approved_returns_409(self, auth_headers):
        """Approving an already-approved item returns 409 Conflict (D-11)."""
        item = make_draft_item(status="approved")
        item_id = item.id

        mock_db = make_mock_db(item)

        async def override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.patch(f"/items/{item_id}/approve", headers=auth_headers)
            assert resp.status_code == 409
        finally:
            app.dependency_overrides.pop(get_db, None)

    async def test_approve_nonexistent_returns_404(self, auth_headers):
        """Approving a nonexistent item returns 404."""
        random_id = uuid.uuid4()
        mock_db = make_mock_db(None)

        async def override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.patch(f"/items/{random_id}/approve", headers=auth_headers)
            assert resp.status_code == 404
        finally:
            app.dependency_overrides.pop(get_db, None)

    async def test_approve_without_token_returns_401(self):
        """Approve endpoint requires auth — no token returns 401 or 403."""
        item = make_draft_item(status="pending")
        item_id = item.id
        mock_db = make_mock_db(item)

        async def override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.patch(f"/items/{item_id}/approve")
            assert resp.status_code in (401, 403)
        finally:
            app.dependency_overrides.pop(get_db, None)


class TestRejectRequiresReason:
    """Tests for PATCH /items/{id}/reject."""

    async def test_reject_with_category_returns_200(self, auth_headers):
        """Rejecting with category returns 200."""
        item = make_draft_item(status="pending")
        item_id = item.id
        mock_db = make_mock_db(item)

        async def override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.patch(
                    f"/items/{item_id}/reject",
                    json={"category": "off-topic", "notes": "Not related to gold"},
                    headers=auth_headers,
                )
            assert resp.status_code == 200
        finally:
            app.dependency_overrides.pop(get_db, None)

    async def test_reject_stores_json_rejection_reason(self, auth_headers):
        """Reject stores rejection_reason as JSON with category + notes (D-12)."""
        item = make_draft_item(status="pending")
        item_id = item.id
        mock_db = make_mock_db(item)

        async def override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                await ac.patch(
                    f"/items/{item_id}/reject",
                    json={"category": "low-quality", "notes": "Too vague"},
                    headers=auth_headers,
                )
            parsed = json.loads(item.rejection_reason)
            assert parsed["category"] == "low-quality"
            assert parsed["notes"] == "Too vague"
        finally:
            app.dependency_overrides.pop(get_db, None)

    async def test_reject_without_category_returns_422(self, auth_headers):
        """Reject without category body returns 422 Unprocessable Entity."""
        item = make_draft_item(status="pending")
        item_id = item.id
        mock_db = make_mock_db(item)

        async def override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                # Send empty body — category is required
                resp = await ac.patch(
                    f"/items/{item_id}/reject",
                    json={},
                    headers=auth_headers,
                )
            assert resp.status_code == 422
        finally:
            app.dependency_overrides.pop(get_db, None)

    async def test_reject_without_token_returns_401(self):
        """Reject endpoint requires auth — no token returns 401 or 403."""
        item = make_draft_item(status="pending")
        item_id = item.id
        mock_db = make_mock_db(item)

        async def override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.patch(
                    f"/items/{item_id}/reject",
                    json={"category": "off-topic"},
                )
            assert resp.status_code in (401, 403)
        finally:
            app.dependency_overrides.pop(get_db, None)


class TestQueueList:
    """Tests for GET /queue."""

    async def test_list_queue_returns_200(self, auth_headers):
        """GET /queue returns 200 with items list."""
        item = make_draft_item(status="pending")
        mock_db = make_mock_db(item)

        async def override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/queue", headers=auth_headers)
            assert resp.status_code == 200
            data = resp.json()
            assert "items" in data
            assert "next_cursor" in data
        finally:
            app.dependency_overrides.pop(get_db, None)

    async def test_list_queue_without_token_returns_401(self):
        """GET /queue without auth returns 401/403."""
        mock_db = make_mock_db(None)

        async def override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/queue")
            assert resp.status_code in (401, 403)
        finally:
            app.dependency_overrides.pop(get_db, None)

    async def test_list_empty_queue_returns_empty_list(self, auth_headers):
        """GET /queue with no items returns empty items list."""
        mock_db = make_mock_db(None)

        async def override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/queue", headers=auth_headers)
            assert resp.status_code == 200
            data = resp.json()
            assert data["items"] == []
            assert data["next_cursor"] is None
        finally:
            app.dependency_overrides.pop(get_db, None)


class TestQueueContentTypeFilter:
    """quick-260421-eoe: /queue?content_type=X filters via the JSONB bundle link.

    draft_items has no direct FK to content_bundles; the link lives in
    draft_items.engagement_snapshot->>'content_bundle_id'. The router must
    issue a correlated subquery against content_bundles.id::text.
    """

    async def test_content_type_filter_present_in_sql(self, auth_headers):
        """When content_type is given, the compiled SQL references content_bundles."""
        item = make_draft_item(status="pending")
        mock_db = make_mock_db(item)

        async def override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get(
                    "/queue?platform=content&content_type=thread",
                    headers=auth_headers,
                )
            assert resp.status_code == 200
            # Inspect the SQLAlchemy statement that was executed — must include
            # the content_bundles subquery AND the JSONB ->> extraction.
            executed_stmt = mock_db.execute.call_args.args[0]
            compiled_sql = str(
                executed_stmt.compile(compile_kwargs={"literal_binds": True})
            )
            assert "content_bundles" in compiled_sql
            assert "content_bundle_id" in compiled_sql
            assert "thread" in compiled_sql
        finally:
            app.dependency_overrides.pop(get_db, None)

    async def test_content_type_filter_omitted_does_not_reference_bundles(self, auth_headers):
        """Without content_type, the query stays untouched — no JOIN / subquery added."""
        item = make_draft_item(status="pending")
        mock_db = make_mock_db(item)

        async def override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/queue?platform=content", headers=auth_headers)
            assert resp.status_code == 200
            executed_stmt = mock_db.execute.call_args.args[0]
            compiled_sql = str(
                executed_stmt.compile(compile_kwargs={"literal_binds": True})
            )
            assert "content_bundles" not in compiled_sql
        finally:
            app.dependency_overrides.pop(get_db, None)

    async def test_content_type_filter_unknown_type_returns_empty_list(self, auth_headers):
        """Bogus content_type must return 200 with empty items, not 500."""
        mock_db = make_mock_db(None)  # empty result set

        async def override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get(
                    "/queue?platform=content&content_type=bogus_unknown_type",
                    headers=auth_headers,
                )
            assert resp.status_code == 200
            data = resp.json()
            assert data["items"] == []
            assert data["next_cursor"] is None
        finally:
            app.dependency_overrides.pop(get_db, None)
