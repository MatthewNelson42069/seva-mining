"""Backend X-poster service. Phase B (quick-260424-l0d) Task 2.

Thin wrapper around `tweepy.asynchronous.AsyncClient` for OAuth 1.0a User Context
posting. All exceptions from tweepy are mapped to a uniform `PostError(code, message)`
internal exception so the route layer can write a single `post_error="{code}:{message}"`
column value (per CONTEXT.md D11).

Catch order is critical: specific exception classes (TooManyRequests, Unauthorized,
Forbidden, BadRequest) BEFORE the generic HTTPException, BEFORE the catch-all
TweepyException — Python `except` is first-match (RESEARCH.md Pitfall 7).

Public surface:
- post_single_tweet(text) -> str             # tweet_id on success; raises PostError on failure
- post_thread(tweets) -> tuple[list[str], PostError | None]  # caller branches on err
- PostError (exposed for the route's `except` clause)
"""
from __future__ import annotations

import logging

import tweepy
import tweepy.asynchronous

from app.config import get_settings

logger = logging.getLogger(__name__)


class PostError(Exception):
    """Internal error wrapper. .code is HTTP-status-like, .message is humanized."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"{code}:{message}")


def _build_client() -> tweepy.asynchronous.AsyncClient:
    """Construct an OAuth 1.0a User Context async client per D8.

    All four credentials are required for posting on a user's behalf. Bearer token is
    deliberately NOT passed — bearer is app-auth and cannot post (gold_media uses bearer
    for read-only X API search; this service is the user-auth posting path).
    """
    s = get_settings()
    return tweepy.asynchronous.AsyncClient(
        consumer_key=s.x_api_key,
        consumer_secret=s.x_api_secret,
        access_token=s.x_access_token,
        access_token_secret=s.x_access_token_secret,
    )


def _msg(e: tweepy.HTTPException) -> str:
    """Best-effort humanization. tweepy populates .api_messages on HTTP errors."""
    api_messages = getattr(e, "api_messages", None)
    if api_messages:
        return api_messages[0]
    return str(e)


async def post_single_tweet(text: str) -> str:
    """Post a single tweet via OAuth1 user-auth. Returns the new tweet's id.

    Raises PostError(code, message) on any tweepy exception. Specific subclasses
    are caught BEFORE HTTPException to ensure correct status-code mapping.
    """
    client = _build_client()
    try:
        resp = await client.create_tweet(text=text, user_auth=True)
        return resp.data["id"]
    except tweepy.TooManyRequests as e:
        raise PostError("429", _msg(e)) from e
    except tweepy.Unauthorized as e:
        raise PostError("401", _msg(e)) from e
    except tweepy.Forbidden as e:
        raise PostError("403", _msg(e)) from e
    except tweepy.BadRequest as e:
        raise PostError("400", _msg(e)) from e
    except tweepy.HTTPException as e:
        code = str(getattr(e.response, "status_code", "500"))
        raise PostError(code, _msg(e)) from e
    except tweepy.TweepyException as e:
        raise PostError("500", str(e)) from e


async def post_thread(tweets: list[str]) -> tuple[list[str], PostError | None]:
    """Post a thread, chaining each tweet as `in_reply_to_tweet_id` of the previous.

    Returns (posted_ids_so_far, optional_error). On full success: (ids, None).
    On mid-thread failure at index N: (ids[0..N-1], PostError). On first-tweet failure:
    ([], PostError). Caller writes posted_partial state on partial-failure (D7).
    """
    client = _build_client()
    posted: list[str] = []
    prev_id: str | None = None
    for text in tweets:
        kwargs: dict = {"text": text, "user_auth": True}
        if prev_id is not None:
            kwargs["in_reply_to_tweet_id"] = prev_id
        try:
            resp = await client.create_tweet(**kwargs)
        except tweepy.TooManyRequests as e:
            return posted, PostError("429", _msg(e))
        except tweepy.Unauthorized as e:
            return posted, PostError("401", _msg(e))
        except tweepy.Forbidden as e:
            return posted, PostError("403", _msg(e))
        except tweepy.BadRequest as e:
            return posted, PostError("400", _msg(e))
        except tweepy.HTTPException as e:
            code = str(getattr(e.response, "status_code", "500"))
            return posted, PostError(code, _msg(e))
        except tweepy.TweepyException as e:
            return posted, PostError("500", str(e))
        new_id = resp.data["id"]
        posted.append(new_id)
        prev_id = new_id
    return posted, None
