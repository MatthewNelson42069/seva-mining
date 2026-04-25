"""POST /items/{item_id}/post-to-x route. Phase B (quick-260424-l0d) Task 3.

User-initiated approve-then-post-to-X flow. The user clicks "Post to X" on a draft
card's detail modal (T4), confirms, and this route atomically transitions the
`draft_items.approval_state` column from `pending` to `posted` (or `posted_partial`
or `failed`) while invoking tweepy via `app.services.x_poster`.

Atomic flow per CONTEXT D3, D4:

    BEGIN
    SELECT * FROM draft_items WHERE id=$1 FOR UPDATE   -- row lock
    -- short-circuit on already-posted (idempotency)
    -- resolve content_bundle via engagement_snapshot.content_bundle_id
    -- branch on bundle.content_type (Phase B: breaking_news + thread only)
    -- simulate-mode: write `sim-{uuid4()}` ID without calling tweepy
    -- real-mode: call x_poster.post_single_tweet / post_thread
    -- write approval_state + posted_* columns (success or failure)
    COMMIT

The lock is held through the tweepy round-trip — acceptable for a single-user
internal tool with low write QPS. statement_timeout=15s is the worst-case bound.

The route is registered with `prefix="/items"` and route path `/{item_id}/post-to-x`
to match queue.py's convention. Auth-gated via the same router-level
`Depends(get_current_user)` dependency every other mutating router uses.

Per CONTEXT.md D1, D2, D3, D4, D5, D6, D7, D9, D11, D13, D14.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.content_bundle import ContentBundle
from app.models.draft_item import DraftItem
from app.schemas.draft_item import ApprovalState, PostToXResponse
from app.services import x_poster

router = APIRouter(
    prefix="/items",
    tags=["post-to-x"],
    dependencies=[Depends(get_current_user)],
)

# Phase B scope: text-only content types only. Quotes + gold_history (B.5) and
# media-bearing types (B+ — gold_media, infographic) are explicit non-goals here.
_PHASE_B_CONTENT_TYPES = {"breaking_news", "thread"}


def _build_locked_select(item_id: UUID):
    """Construct the FOR-UPDATE select used by the route.

    Exposed as a helper so tests can compile the same statement and assert that
    the generated SQL contains "FOR UPDATE" (Pitfall 2: SQLite no-ops the lock at
    runtime, so we test the syntactic intent against the postgresql dialect).
    """
    return select(DraftItem).where(DraftItem.id == item_id).with_for_update()


def _to_response(item: DraftItem, *, already_posted: bool = False) -> PostToXResponse:
    """Convert the mutated ORM item into the response model."""
    return PostToXResponse(
        approval_state=ApprovalState(item.approval_state),
        posted_tweet_id=item.posted_tweet_id,
        posted_tweet_ids=item.posted_tweet_ids,
        posted_at=item.posted_at,
        post_error=item.post_error,
        already_posted=already_posted,
    )


@router.post("/{item_id}/post-to-x", response_model=PostToXResponse)
async def post_to_x(
    item_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> PostToXResponse:
    """Atomically approve-and-post a draft to X.

    Lock semantics: a single transaction with `SELECT ... FOR UPDATE` holds the
    row lock through the tweepy round-trip, serializing concurrent re-clicks on
    the same draft (D3). On failure, the same transaction writes the failed
    state — the lock guarantees the failure record is consistent with the lock
    holder's view.
    """
    settings = get_settings()
    now = datetime.now(UTC)

    async with db.begin():
        # 1. Lock the row (or 404)
        result = await db.execute(_build_locked_select(item_id))
        item = result.scalar_one_or_none()
        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Item not found",
            )

        # 2. Idempotency: if we already posted, short-circuit without calling
        # tweepy. Returns the existing posted_tweet_id so the frontend can
        # surface the "Already posted" toast + re-link without a second POST.
        if item.approval_state == ApprovalState.posted.value:
            return _to_response(item, already_posted=True)

        # 3. Resolve the content_bundle via the JSONB pointer. The bundle holds
        # the actual post text under draft_content (RESEARCH Pitfall 2): there
        # is no direct FK from draft_items to content_bundles.
        snapshot = item.engagement_snapshot or {}
        bundle_id_str = snapshot.get("content_bundle_id") if isinstance(snapshot, dict) else None
        if not bundle_id_str:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="missing content_bundle_id",
            )

        try:
            bundle_uuid = UUID(bundle_id_str)
        except (ValueError, TypeError) as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="invalid content_bundle_id",
            ) from e

        bundle = await db.get(ContentBundle, bundle_uuid)
        if bundle is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="content bundle not found",
            )

        content_type = bundle.content_type

        # 4. Phase B scope check — only breaking_news + thread for now.
        # Per D1: quotes + gold_history deferred to B.5; media-bearing types to B+.
        if content_type not in _PHASE_B_CONTENT_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"content_type '{content_type}' out of scope for Phase B; "
                    f"supported: breaking_news, thread"
                ),
            )

        draft_content = bundle.draft_content or {}

        # 5. Branch on content_type. Each branch sets approval_state +
        # posted_tweet_id(_ids) + posted_at + post_error. All writes inside the
        # single tx; commit happens on `async with db.begin():` exit.
        if content_type == "breaking_news":
            text = draft_content.get("tweet")
            if text is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="bundle.draft_content missing 'tweet' field for breaking_news",
                )

            if not settings.x_posting_enabled:
                # Simulate mode (D2): generate a sim-{uuid4} ID, no tweepy call.
                tweet_id = f"{settings.x_posting_sim_prefix}{uuid.uuid4()}"
                item.approval_state = ApprovalState.posted.value
                item.posted_tweet_id = tweet_id
                item.posted_tweet_ids = None
                item.posted_at = now
                item.post_error = None
            else:
                # Real mode: call tweepy. Catch PostError inside the tx and
                # write failed state — same lock holds, single commit.
                try:
                    tweet_id = await x_poster.post_single_tweet(text)
                except x_poster.PostError as e:
                    item.approval_state = ApprovalState.failed.value
                    item.posted_tweet_id = None
                    item.posted_tweet_ids = None
                    item.post_error = f"{e.code}:{e.message}"
                    item.posted_at = now
                else:
                    item.approval_state = ApprovalState.posted.value
                    item.posted_tweet_id = tweet_id
                    item.posted_tweet_ids = None
                    item.post_error = None
                    item.posted_at = now

        else:  # content_type == "thread"
            tweets = draft_content.get("tweets")
            if not isinstance(tweets, list) or not tweets:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="bundle.draft_content missing 'tweets' list for thread",
                )

            if not settings.x_posting_enabled:
                # Simulate mode: generate N sim-IDs, one per tweet in the thread.
                sim_ids = [
                    f"{settings.x_posting_sim_prefix}{uuid.uuid4()}" for _ in tweets
                ]
                item.approval_state = ApprovalState.posted.value
                item.posted_tweet_id = sim_ids[0]
                item.posted_tweet_ids = sim_ids
                item.posted_at = now
                item.post_error = None
            else:
                ids, err = await x_poster.post_thread(tweets)
                if err and not ids:
                    # First-tweet failure: nothing posted, treat as plain failure.
                    item.approval_state = ApprovalState.failed.value
                    item.posted_tweet_id = None
                    item.posted_tweet_ids = None
                    item.post_error = f"{err.code}:{err.message}"
                    item.posted_at = now
                elif err:
                    # Mid-thread failure: posted some, then aborted. Per D7 we do
                    # NOT auto-rollback; user sees posted_partial state and
                    # decides whether to delete on X manually or re-trigger.
                    item.approval_state = ApprovalState.posted_partial.value
                    item.posted_tweet_id = ids[0]
                    item.posted_tweet_ids = ids
                    item.post_error = (
                        f"thread posted {len(ids)}/{len(tweets)}: "
                        f"{err.code}:{err.message}"
                    )
                    item.posted_at = now
                else:
                    item.approval_state = ApprovalState.posted.value
                    item.posted_tweet_id = ids[0]
                    item.posted_tweet_ids = ids
                    item.post_error = None
                    item.posted_at = now

        return _to_response(item)
