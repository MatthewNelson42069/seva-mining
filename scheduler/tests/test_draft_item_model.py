"""Parity guard: scheduler-side DraftItem must expose the Phase B X post-state columns
identical to the backend.

If a future change drops one of these or renames it, this test fails — keeping the
backend `app/models/draft_item.py` and `scheduler/models/draft_item.py` in lockstep.

quick-260424-l0d (Phase B).
"""
from models.draft_item import DraftItem


def test_draft_item_has_approval_state_column():
    assert hasattr(DraftItem, "approval_state"), \
        "scheduler DraftItem must expose 'approval_state' column (Phase B parity)"


def test_draft_item_has_posted_tweet_id_column():
    assert hasattr(DraftItem, "posted_tweet_id"), \
        "scheduler DraftItem must expose 'posted_tweet_id' column (Phase B parity)"


def test_draft_item_has_posted_tweet_ids_column():
    assert hasattr(DraftItem, "posted_tweet_ids"), \
        "scheduler DraftItem must expose 'posted_tweet_ids' column (Phase B parity)"


def test_draft_item_has_posted_at_column():
    assert hasattr(DraftItem, "posted_at"), \
        "scheduler DraftItem must expose 'posted_at' column (Phase B parity)"


def test_draft_item_has_post_error_column():
    assert hasattr(DraftItem, "post_error"), \
        "scheduler DraftItem must expose 'post_error' column (Phase B parity)"
