"""Video Clip (Gold Media) sub-agent — self-contained drafter.

Part of the 7-agent split (quick-260421-eoe). Does NOT call
``content_agent.fetch_stories()`` — it searches X (Twitter) directly via
tweepy's async client for video posts from the curated VIDEO_ACCOUNTS list,
drafts a quote-tweet style caption per clip, runs ``content_agent.review()``
inline, and writes a ContentBundle with ``content_type="video_clip"``.

Preserves the X API quota pre-check from the pre-split ContentAgent
(``twitter_monthly_tweet_count`` / ``twitter_monthly_quota_limit`` read from
Config). Frontend label: "Gold Media" — DB value stays ``video_clip`` for
schema parity.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import tweepy.asynchronous
from anthropic import AsyncAnthropic
from sqlalchemy import func as sqlfunc
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agents import content_agent
from config import get_settings
from database import AsyncSessionLocal
from models.agent_run import AgentRun
from models.config import Config
from models.content_bundle import ContentBundle
from services.market_snapshot import fetch_market_snapshot, render_snapshot_block

logger = logging.getLogger(__name__)

CONTENT_TYPE: str = "video_clip"
AGENT_NAME: str = "sub_video_clip"

# Curated video-source accounts (CONT-09, CONT-13). Reordered + trimmed in
# quick-260422-vxg to favor analyst/economist media handles over
# corporate/sector accounts — Gold Media's goal is senior-analyst commentary,
# not PR clips.
VIDEO_ACCOUNTS = [
    "Kitco",            # Michael Oliver / Jeff Christian / roundtable analyst interviews
    "CNBC",             # Halftime Report, Fast Money — frequent analyst segments
    "Bloomberg",        # analyst + economist segments
    "BloombergTV",      # real-time analyst interviews
    "ReutersBiz",       # economist panels
    "FT",               # Financial Times video interviews
    "MarketWatch",      # analyst segments
]

VIDEO_CLIP_SCORE = 7.5  # Fixed score for Twitter-sourced content (parity).


async def _get_config(session: AsyncSession, key: str, default: str) -> str:
    """Read a config value from the DB by key. Returns default if not found."""
    result = await session.execute(select(Config).where(Config.key == key))
    row = result.scalar_one_or_none()
    return row.value if row else default


async def _set_config_str(session: AsyncSession, key: str, value: str) -> None:
    """Upsert a config key with a string value."""
    result = await session.execute(select(Config).where(Config.key == key))
    row = result.scalar_one_or_none()
    if row is None:
        session.add(Config(key=key, value=value))
    else:
        row.value = value


async def _search_video_clips(
    session: AsyncSession, tweepy_client: tweepy.asynchronous.AsyncClient
) -> list[dict]:
    """Search X for gold-sector video posts from credible accounts.

    Uses has:videos operator. Filters to tweets with at least one media
    attachment of type="video". Respects the monthly quota — returns empty
    list if within 500 of the configured cap.
    """
    current_count_str = await _get_config(session, "twitter_monthly_tweet_count", "0")
    quota_limit_str = await _get_config(session, "twitter_monthly_quota_limit", "10000")
    current_count = int(current_count_str)
    quota_limit = int(quota_limit_str)
    if quota_limit - current_count < 500:
        logger.info(
            "%s: X API quota near cap (%d/%d) — skipping video clip search",
            AGENT_NAME, current_count, quota_limit,
        )
        return []

    accounts_clause = " OR ".join(f"from:{acct}" for acct in VIDEO_ACCOUNTS[:5])
    query = f"({accounts_clause}) has:videos gold -is:retweet"

    try:
        response = await tweepy_client.search_recent_tweets(
            query=query,
            max_results=10,
            tweet_fields=["created_at", "public_metrics", "author_id", "text", "attachments"],
            expansions=["author_id", "attachments.media_keys"],
            user_fields=["username", "public_metrics"],
            media_fields=["type", "duration_ms", "preview_image_url"],
        )

        if not response.data:
            return []

        users_data = (response.includes or {}).get("users") or []
        media_data = (response.includes or {}).get("media") or []
        user_map = {str(u.id): u for u in users_data}
        media_map = {m.media_key: m for m in media_data} if media_data else {}

        results: list[dict] = []
        for tweet in response.data:
            attachment_keys = (
                (tweet.attachments or {}).get("media_keys", []) if tweet.attachments else []
            )
            has_video = any(
                media_map.get(k) and media_map[k].type == "video"
                for k in attachment_keys
            )
            if not has_video:
                continue

            user = user_map.get(str(tweet.author_id))
            username = user.username if user else "unknown"
            author_name = user.name if user else "unknown"
            tweet_url = f"https://twitter.com/{username}/status/{tweet.id}"

            results.append({
                "tweet_id": str(tweet.id),
                "text": tweet.text,
                "author_username": username,
                "author_name": author_name,
                "tweet_url": tweet_url,
                "public_metrics": tweet.public_metrics or {},
                "created_at": tweet.created_at,
            })

        total_returned = len(response.data)
        new_count = current_count + total_returned
        await _set_config_str(session, "twitter_monthly_tweet_count", str(new_count))

        logger.info(
            "%s: video clip search returned %d tweets (%d passed video filter)",
            AGENT_NAME, total_returned, len(results),
        )
        return results

    except Exception as exc:
        logger.warning("%s: video clip X API search failed: %s", AGENT_NAME, exc)
        return []


async def _draft_video_caption(
    tweet_text: str,
    author_username: str,
    author_name: str,
    tweet_url: str,
    market_snapshot: dict | None,
    *,
    client: AsyncAnthropic,
) -> dict | None:
    """Draft a quote-tweet style caption for a video clip.

    Mirrors the pre-split ContentAgent._draft_video_caption prompt exactly
    for functional parity.
    """
    snapshot_block = render_snapshot_block(market_snapshot) if market_snapshot else ""
    system_prompt = (
        f"{snapshot_block}\n\n"
        "You are a senior gold market analyst. You write quote-tweet style captions "
        "for video clips from gold sector figures. Write 1-3 sentences: who said it, "
        "what the key claim is, why it matters to gold investors. Lead with the data "
        "or the insight — not preamble. Also provide an Instagram-adapted version "
        "(same content, slightly more context for a less technical audience). "
        "You never mention Seva Mining. You never give financial advice."
    )
    user_prompt = f"""Write a caption for this video clip from @{author_username} ({author_name}).

Tweet text: {tweet_text}
Video URL: {tweet_url}

## Quality bar — draft ONLY if the video features an identifiable senior
analyst or economist with clear gold-market commentary:
1. **Speaker identifiable:** Named analyst, economist, strategist, or
   central bank official — NOT anonymous reporters reading headlines, NOT
   retail commentators, NOT pure market-recap voice-overs without named
   speaker.
2. **Substantive commentary:** Contains an analyst view, forecast, data
   interpretation, or contrarian take on gold price / macro. NOT just
   "gold prices rose today" news-recital.
3. **Gold focus:** Speaker discusses gold specifically (not mentioning
   gold in passing during a broader markets segment).

If the video does NOT meet this bar, respond with:
{{"reject": true, "rationale": "1-2 sentence reason"}}

Otherwise, respond in valid JSON:
{{
  "twitter_caption": "1-3 sentences for X quote-tweet (data-forward, senior analyst voice)",
  "instagram_caption": "same content adapted for Instagram (slightly more context)"
}}"""

    try:
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```", 2)[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.rsplit("```", 1)[0].strip()
        parsed = json.loads(raw)
    except Exception as exc:
        logger.warning("%s: _draft_video_caption JSON parse failed: %s", AGENT_NAME, exc)
        return None

    if parsed.get("reject") is True:
        logger.info(
            "%s: _draft_video_caption rejected — %s",
            AGENT_NAME, parsed.get("rationale", "no rationale given"),
        )
        return None

    return {
        "format": "video_clip",
        "source_account": author_username,
        "tweet_url": tweet_url,
        "twitter_caption": parsed.get("twitter_caption", ""),
        "instagram_caption": parsed.get("instagram_caption", ""),
    }


async def run_draft_cycle() -> None:
    """Single-tick pipeline: X search → per-clip draft → review → write.

    Does NOT call content_agent.fetch_stories() — video_clip has its own source.
    Does call content_agent.review() inline before writing each bundle.

    Post quick-260422-vxg: iterates up to MAX_DRAFT_ATTEMPTS=5 most-recent
    candidates, breaks after first successful persist — goal is 1 analyst
    clip/day. If no clip passes the drafter quality bar, none queued.
    """
    settings = get_settings()
    anthropic_client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    tweepy_client = tweepy.asynchronous.AsyncClient(
        bearer_token=settings.x_api_bearer_token,
        wait_on_rate_limit=True,
    )

    async with AsyncSessionLocal() as session:
        agent_run = AgentRun(
            agent_name=AGENT_NAME,
            status="running",
            started_at=datetime.now(timezone.utc),
            items_found=0,
            items_queued=0,
            items_filtered=0,
        )
        session.add(agent_run)
        await session.commit()

        items_queued = 0
        try:
            try:
                market_snapshot = await fetch_market_snapshot(session=session)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "%s: market snapshot fetch failed (%s) — continuing without",
                    AGENT_NAME, type(exc).__name__,
                )
                market_snapshot = None

            clips = await _search_video_clips(session, tweepy_client)
            clips.sort(key=lambda c: c.get("created_at") or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
            MAX_DRAFT_ATTEMPTS = 5
            clips = clips[:MAX_DRAFT_ATTEMPTS]
            agent_run.items_found = len(clips)
            if not clips:
                agent_run.status = "completed"
                return

            today_utc = datetime.now(timezone.utc).date()

            for clip in clips:
                try:
                    tweet_url = clip["tweet_url"]
                    existing = await session.execute(
                        select(ContentBundle).where(
                            sqlfunc.date(ContentBundle.created_at) == today_utc,
                            ContentBundle.story_url == tweet_url,
                            ContentBundle.no_story_flag.is_(False),
                        )
                    )
                    if existing.scalar_one_or_none() is not None:
                        logger.info("%s: already covered today: %s", AGENT_NAME, tweet_url)
                        continue

                    draft_content = await _draft_video_caption(
                        tweet_text=clip["text"],
                        author_username=clip["author_username"],
                        author_name=clip["author_name"],
                        tweet_url=tweet_url,
                        market_snapshot=market_snapshot,
                        client=anthropic_client,
                    )
                    if draft_content is None:
                        logger.warning("%s: caption draft failed for %s", AGENT_NAME, tweet_url)
                        continue

                    review_result = await content_agent.review(draft_content)
                    compliance_ok = bool(review_result.get("compliance_passed", False))

                    bundle = ContentBundle(
                        story_headline=clip["text"][:200],
                        story_url=tweet_url,
                        source_name=clip["author_username"],
                        content_type=CONTENT_TYPE,
                        score=VIDEO_CLIP_SCORE,
                        draft_content=draft_content,
                        compliance_passed=compliance_ok,
                    )
                    session.add(bundle)
                    await session.flush()

                    if compliance_ok:
                        rationale = f"Video clip from @{clip['author_username']} on gold sector"
                        item = content_agent.build_draft_item(bundle, rationale)
                        session.add(item)
                        await session.flush()
                        items_queued += 1
                        logger.info("%s: queued video clip from @%s", AGENT_NAME, clip["author_username"])
                        break  # max 1 analyst clip per day — per quick-260422-vxg
                    else:
                        logger.warning(
                            "%s: compliance blocked video clip %s — reason=%s",
                            AGENT_NAME, tweet_url, review_result.get("rationale"),
                        )
                except Exception as exc:
                    logger.error(
                        "%s: error processing clip %s: %s",
                        AGENT_NAME, clip.get("tweet_url", "?"), exc, exc_info=True,
                    )

            agent_run.items_queued = items_queued
            agent_run.notes = json.dumps({"candidates": len(clips)})
            agent_run.status = "completed"
        except Exception as exc:
            agent_run.status = "failed"
            agent_run.errors = str(exc)
            logger.error("%s run failed: %s", AGENT_NAME, exc, exc_info=True)
        finally:
            agent_run.ended_at = datetime.now(timezone.utc)
            await session.commit()
