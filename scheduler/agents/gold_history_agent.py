"""
Gold History Agent — drama-first gold industry storytelling.

Runs bi-weekly on Sunday at 9am UTC. Picks a fresh historical gold story
(not in the used-slugs list), verifies key facts via SerpAPI, drafts a
5-7 tweet thread + 4-7 slide Instagram carousel using Claude Sonnet with
a drama-first storytelling voice.

Requirements: CONT-07, CONT-14, CONT-15, CONT-16, CONT-17
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

import serpapi
from anthropic import AsyncAnthropic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from database import AsyncSessionLocal
from models.agent_run import AgentRun
from models.config import Config

# Lazy imports from content_agent to avoid circular dependencies.
# check_compliance and build_draft_item are module-level functions in content_agent.py.

logger = logging.getLogger(__name__)


class GoldHistoryAgent:
    """Gold History Agent — historical story selection, fact verification, drama-first drafting.

    Produces ContentBundle records with content_type="gold_history" on a bi-weekly
    Sunday schedule. Story slugs are tracked in the Config table under the key
    "gold_history_used_topics" (JSON-encoded list) so each story is picked at most
    once in the lifetime of the system.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.anthropic = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.serpapi_client = serpapi.Client(api_key=settings.serpapi_api_key)

    async def _get_config(self, session: AsyncSession, key: str, default: str) -> str:
        """Read a config value from the DB by key. Returns default if not found."""
        result = await session.execute(select(Config).where(Config.key == key))
        row = result.scalar_one_or_none()
        return row.value if row else default

    async def _get_used_topics(self, session: AsyncSession) -> list[str]:
        """Read used Gold History story slugs from config.

        Returns a list of slug strings. Returns empty list if key is missing
        or the value cannot be parsed as JSON. (EXP-6)
        """
        result = await session.execute(
            select(Config).where(Config.key == "gold_history_used_topics")
        )
        row = result.scalar_one_or_none()
        if row is None:
            return []
        try:
            return json.loads(row.value)  # Config.value stores JSON-encoded list
        except (json.JSONDecodeError, TypeError):
            return []

    async def _add_used_topic(self, session: AsyncSession, slug: str) -> None:
        """Append a story slug to the used topics list in config.

        No-ops if slug is already present. Upserts the Config row with the
        updated JSON-encoded list. Caller is responsible for committing. (EXP-6)
        """
        topics = await self._get_used_topics(session)
        if slug not in topics:
            topics.append(slug)
        result = await session.execute(
            select(Config).where(Config.key == "gold_history_used_topics")
        )
        row = result.scalar_one_or_none()
        if row is None:
            session.add(Config(
                key="gold_history_used_topics",
                value=json.dumps(topics),
            ))
        else:
            row.value = json.dumps(topics)
        # caller commits

    async def _pick_story(self, used_topics: list[str]) -> dict | None:
        """Pick a fresh gold history story via Claude Sonnet.

        Uses the list of already-used slugs to ensure a fresh story is selected
        on each run. Asks Claude to return JSON with story_title, story_slug,
        and key_claims (3-5 claims to verify via SerpAPI).

        Returns:
            Dict with keys: story_title, story_slug, key_claims.
            None if the Claude response cannot be parsed as valid JSON.
        """
        used_list = json.dumps(used_topics) if used_topics else "[]"

        try:
            response = await self.anthropic.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=512,
                system=(
                    "You are a gold mining historian with a gift for dramatic storytelling. "
                    "Pick a compelling, untold gold industry story. Lead with the most "
                    "dramatic moment. Return only valid JSON — no markdown, no prose."
                ),
                messages=[{
                    "role": "user",
                    "content": (
                        f"Already-used story slugs (do NOT pick these): {used_list}\n\n"
                        "Story type suggestions: company builds, M&A, exploration discoveries, "
                        "notable characters, crashes/frauds, gold rushes. Examples: "
                        "Frank Giustra/GoldCorp, Barrick founding by Peter Munk, Bre-X fraud, "
                        "Newmont history, Nevada gold rush, Klondike.\n\n"
                        "Pick a story NOT in the used list. Return JSON:\n"
                        '{"story_title": "...", "story_slug": "giustra-goldcorp-1994", '
                        '"key_claims": ["claim1", "claim2", "claim3"]}'
                    ),
                }],
            )
            raw = response.content[0].text.strip()
            # Strip markdown code fences if present
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()
            data = json.loads(raw)
            if not all(k in data for k in ("story_title", "story_slug", "key_claims")):
                logger.warning("GoldHistoryAgent._pick_story: missing required keys in response")
                return None
            return data
        except (json.JSONDecodeError, KeyError, IndexError) as exc:
            logger.warning("GoldHistoryAgent._pick_story: parse failure — %s", exc)
            return None
        except Exception as exc:
            logger.error("GoldHistoryAgent._pick_story: Claude call failed — %s", exc, exc_info=True)
            return None

    async def _verify_facts(self, key_claims: list[str]) -> list[dict]:
        """Verify up to 3 key claims via SerpAPI Google search.

        Runs each claim as a synchronous SerpAPI call in the executor to avoid
        blocking the event loop. Claims with no search results are noted as
        "unverified" but NOT discarded — the story proceeds regardless.

        Returns:
            List of dicts: {claim, verified: bool, source: str, snippet: str}
        """
        loop = asyncio.get_event_loop()
        verified = []

        for claim in key_claims[:3]:
            def _call(q=claim):
                return self.serpapi_client.search({
                    "engine": "google",
                    "q": q,
                    "num": 3,
                })

            try:
                results = await loop.run_in_executor(None, _call)
                organic = results.get("organic_results", [])
                if organic:
                    top = organic[0]
                    verified.append({
                        "claim": claim,
                        "verified": True,
                        "source": top.get("link", ""),
                        "snippet": top.get("snippet", "")[:200],
                    })
                else:
                    verified.append({
                        "claim": claim,
                        "verified": False,
                        "source": "",
                        "snippet": "No corroborating results found",
                    })
            except Exception as exc:
                logger.warning("GoldHistoryAgent._verify_facts: SerpAPI error for claim '%s': %s", claim[:60], exc)
                verified.append({
                    "claim": claim,
                    "verified": False,
                    "source": "",
                    "snippet": f"Verification error: {exc}",
                })

        return verified

    async def _draft_gold_history(
        self, story_title: str, story_slug: str, verified_facts: list[dict]
    ) -> dict | None:
        """Draft a gold_history ContentBundle via Claude Sonnet.

        Uses a drama-first storytelling prompt. Produces a 5-7 tweet thread and
        a 4-7 slide Instagram carousel following the brand design system:
        background #F0ECE4 (warm cream), text #0C1B32 (deep navy),
        gold accent #D4AF37 (metallic gold).

        Returns:
            Dict with the locked gold_history structure, or None on parse failure.
        """
        facts_summary = "\n".join(
            f"- {f['claim']} ({'VERIFIED via ' + f['source'][:80] if f['verified'] else 'unverified'})"
            for f in verified_facts
        )

        try:
            response = await self.anthropic.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=2048,
                system=(
                    "You are a senior gold analyst and dramatic historian. "
                    "Your storytelling is drama-first: lead with the most dramatic moment — "
                    "the audacity, the risk, the payoff. Every sentence earns its place. "
                    "No financial advice. No mention of Seva Mining. Return only valid JSON — "
                    "no markdown, no prose outside the JSON structure."
                ),
                messages=[{
                    "role": "user",
                    "content": (
                        f"Story: {story_title}\n\n"
                        f"Verified facts:\n{facts_summary}\n\n"
                        "Story arc: hook → rising action → climax → what it means today.\n\n"
                        "Instagram design system: background #F0ECE4 (warm cream), "
                        "text #0C1B32 (deep navy), gold accent #D4AF37 (metallic gold). "
                        "a16z minimalist aesthetic. One key moment per slide. Max 15 words per slide body. "
                        "Gold accent on 1-2 elements per slide.\n\n"
                        "Return JSON with this exact structure:\n"
                        "{\n"
                        '  "format": "gold_history",\n'
                        '  "story_title": "...",\n'
                        f'  "story_slug": "{story_slug}",\n'
                        '  "tweets": ["hook tweet", "tweet 2", "tweet 3", "tweet 4", "tweet 5"],\n'
                        '  "instagram_carousel": [\n'
                        '    {"slide": 1, "headline": "...", "body": "...(max 15 words)...", "visual_note": "..."},\n'
                        '    {"slide": 2, "headline": "...", "body": "...", "visual_note": "..."}\n'
                        '  ],\n'
                        '  "instagram_caption": "full caption text"\n'
                        "}\n\n"
                        "Tweets: 5-7, hook tweet first (most dramatic moment). "
                        "Carousel: 4-7 slides, one moment per slide."
                    ),
                }],
            )
            raw = response.content[0].text.strip()
            # Strip markdown code fences if present
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()
            data = json.loads(raw)
            required = ("format", "story_title", "story_slug", "tweets", "instagram_carousel", "instagram_caption")
            if not all(k in data for k in required):
                logger.warning("GoldHistoryAgent._draft_gold_history: missing required keys in response")
                return None
            return data
        except (json.JSONDecodeError, KeyError, IndexError) as exc:
            logger.warning("GoldHistoryAgent._draft_gold_history: parse failure — %s", exc)
            return None
        except Exception as exc:
            logger.error(
                "GoldHistoryAgent._draft_gold_history: Claude call failed — %s", exc, exc_info=True
            )
            return None

    async def _run_pipeline(self, session: AsyncSession, agent_run: AgentRun) -> None:
        """Orchestrate the full Gold History pipeline.

        1. Read used topics from Config.
        2. Pick a fresh story via Claude Sonnet.
        3. Verify key claims via SerpAPI.
        4. Draft the gold_history content via Claude Sonnet.
        5. Run compliance check.
        6. Persist ContentBundle.
        7. Track used slug in Config.
        8. If compliance passed: build DraftItem (Senior intake removed in quick-260420-sn9;
           items land in DB directly, aggregated into the morning digest at 8am UTC).
        """
        from models.content_bundle import ContentBundle  # noqa: PLC0415
        from agents.content_agent import check_compliance, build_draft_item  # noqa: PLC0415

        # 1. Read used topics
        used_topics = await self._get_used_topics(session)
        logger.info(
            "GoldHistoryAgent: %d stories already used, picking a fresh one.", len(used_topics)
        )

        # 2. Pick a fresh story
        story = await self._pick_story(used_topics)
        if story is None:
            logger.warning("GoldHistoryAgent: _pick_story returned None — no bundle created.")
            bundle = ContentBundle(
                story_headline="Gold History: no story selected",
                no_story_flag=True,
                score=0.0,
            )
            session.add(bundle)
            agent_run.notes = json.dumps({"reason": "story_pick_failed"})
            return

        story_title = story["story_title"]
        story_slug = story["story_slug"]
        key_claims = story.get("key_claims", [])

        logger.info("GoldHistoryAgent: picked story '%s' (slug=%s)", story_title[:60], story_slug)

        # 3. Verify key claims via SerpAPI
        verified_facts = await self._verify_facts(key_claims)
        verified_count = sum(1 for f in verified_facts if f["verified"])
        logger.info(
            "GoldHistoryAgent: %d/%d claims verified for '%s'",
            verified_count, len(verified_facts), story_slug,
        )

        # 4. Draft content
        draft_content = await self._draft_gold_history(story_title, story_slug, verified_facts)
        if draft_content is None:
            logger.error("GoldHistoryAgent: drafting failed for '%s'", story_title[:60])
            bundle = ContentBundle(
                story_headline=story_title,
                content_type="gold_history",
                no_story_flag=False,
                score=0.0,
                deep_research={"verified_claims": verified_facts, "story_slug": story_slug},
                compliance_passed=False,
            )
            session.add(bundle)
            await self._add_used_topic(session, story_slug)
            agent_run.notes = json.dumps({"reason": "draft_failed", "story_slug": story_slug})
            return

        # 5. Run compliance check on the full draft text
        all_tweet_text = " ".join(draft_content.get("tweets", []))
        carousel_text = " ".join(
            f"{s.get('headline', '')} {s.get('body', '')}"
            for s in draft_content.get("instagram_carousel", [])
        )
        caption_text = draft_content.get("instagram_caption", "")
        check_text = f"{all_tweet_text} {carousel_text} {caption_text}"
        compliance_ok = await check_compliance(check_text, self.anthropic)

        # 6. Persist ContentBundle
        bundle = ContentBundle(
            story_headline=story_title,
            content_type="gold_history",
            no_story_flag=False,
            score=8.0,  # Gold History is curated content — fixed baseline score
            deep_research={"verified_claims": verified_facts, "story_slug": story_slug},
            draft_content=draft_content,
            compliance_passed=compliance_ok,
        )
        session.add(bundle)
        await session.flush()  # Get bundle.id

        # 7. Track used slug
        await self._add_used_topic(session, story_slug)

        if not compliance_ok:
            logger.warning(
                "GoldHistoryAgent: compliance check failed for '%s'", story_title[:60]
            )
            agent_run.notes = json.dumps({
                "reason": "compliance_failed",
                "story_slug": story_slug,
                "story_title": story_title,
            })
            return

        # 8. Build DraftItem (Senior intake pipeline removed in quick-260420-sn9 —
        #    item lands in DB directly; morning_digest aggregates it at 8am UTC).
        rationale = (
            f"Gold History: {story_title}. "
            f"{verified_count}/{len(verified_facts)} claims verified via SerpAPI."
        )
        item = build_draft_item(bundle, rationale)
        session.add(item)
        await session.flush()  # Get item.id

        agent_run.items_found = 1
        agent_run.items_queued = 1
        agent_run.notes = json.dumps({
            "story_title": story_title,
            "story_slug": story_slug,
            "verified_count": verified_count,
            "total_claims": len(verified_facts),
            "content_bundle_id": str(bundle.id),
        })
        logger.info(
            "GoldHistoryAgent: queued gold_history story '%s' (bundle_id=%s)",
            story_title[:60], bundle.id,
        )

    async def run(self) -> None:
        """Entry point called by APScheduler. Runs the full Gold History pipeline."""
        async with AsyncSessionLocal() as session:
            agent_run = AgentRun(
                agent_name="gold_history_agent",
                status="running",
                started_at=datetime.now(timezone.utc),
                items_found=0,
                items_queued=0,
                items_filtered=0,
            )
            session.add(agent_run)
            await session.commit()
            try:
                await self._run_pipeline(session, agent_run)
                agent_run.status = "completed"
            except Exception as exc:
                agent_run.status = "failed"
                agent_run.errors = str(exc)
                logger.error("GoldHistoryAgent run failed: %s", exc, exc_info=True)
            finally:
                agent_run.ended_at = datetime.now(timezone.utc)
                await session.commit()
