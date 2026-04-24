"""
Senior Agent — daily morning digest dispatch (post-sn9 scope).

Trimmed to digest-only in quick 260420-sn9: dedup, queue-cap enforcement,
breaking-news alerts, expiry alerts, engagement alerts, expiry sweep, and
process_new_item(s) intake were all removed. Sub-agents (content_agent,
gold_history_agent) now land items in the DB directly; the morning digest
aggregates them at 8am UTC.

Requirements: SENR-06, SENR-07, SENR-08, WHAT-01
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from database import AsyncSessionLocal
from models.agent_run import AgentRun
from models.config import Config
from models.daily_digest import DailyDigest
from models.draft_item import DraftItem
from services.whatsapp import send_whatsapp_message

logger = logging.getLogger(__name__)


class SeniorAgent:
    """Runs the daily morning WhatsApp digest."""

    def __init__(self) -> None:
        self.settings = get_settings()

    # ------------------------------------------------------------------
    # Config helper
    # ------------------------------------------------------------------

    async def _get_config(self, session: AsyncSession, key: str, default: str) -> str:
        """Fetch a single config value by *key* or return *default*."""
        result = await session.execute(select(Config.value).where(Config.key == key))
        return result.scalar_one_or_none() or default

    # ------------------------------------------------------------------
    # SENR-06 / SENR-07 / SENR-08: Morning digest helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _headline_from_rationale(rationale: str | None) -> str:
        """Extract a headline from the first sentence of *rationale*.

        Returns the first sentence (split on ``". "``), truncated to 100 chars
        at a word boundary, and guaranteed to end with a period.

        Args:
            rationale: Full rationale text or ``None``.

        Returns:
            Headline string, never ``None``.
        """
        if not rationale:
            return "(no rationale)"

        parts = rationale.split(". ")
        sentence = parts[0]
        # Ensure it ends with a period
        if not sentence.endswith("."):
            sentence = sentence + "."

        # Truncate to 100 chars at a word boundary
        if len(sentence) > 100:
            truncated = sentence[:100]
            last_space = truncated.rfind(" ")
            sentence = (truncated[:last_space] if last_space > 0 else truncated).rstrip(".") + "."

        return sentence

    async def _assemble_digest(self, session: AsyncSession) -> dict:
        """Assemble the morning digest JSONB payload.

        Queries yesterday's approval/rejection/expiry counts, builds the current
        queue snapshot, selects the top 5 stories, and identifies the highest-scoring
        pending item as the priority alert.

        Args:
            session: Active async SQLAlchemy session.

        Returns:
            Dict with keys: ``top_stories``, ``queue_snapshot``, ``yesterday_approved``,
            ``yesterday_rejected``, ``yesterday_expired``, ``priority_alert``.
        """
        today = date.today()
        yesterday_start = datetime.combine(today - timedelta(days=1), datetime.min.time()).replace(
            tzinfo=timezone.utc
        )
        yesterday_end = datetime.combine(today, datetime.min.time()).replace(tzinfo=timezone.utc)

        # --- Yesterday approved count (SENR-08) ---
        approved_result = await session.execute(
            select(func.count())
            .select_from(DraftItem)
            .where(
                DraftItem.status.in_(["approved", "edited_approved"]),
                DraftItem.decided_at >= yesterday_start,
                DraftItem.decided_at < yesterday_end,
            )
        )
        approved_count = approved_result.scalar_one()

        # --- Yesterday rejected count (SENR-08) ---
        rejected_result = await session.execute(
            select(func.count())
            .select_from(DraftItem)
            .where(
                DraftItem.status == "rejected",
                DraftItem.decided_at >= yesterday_start,
                DraftItem.decided_at < yesterday_end,
            )
        )
        rejected_count = rejected_result.scalar_one()

        # --- Yesterday expired count ---
        expired_result = await session.execute(
            select(func.count())
            .select_from(DraftItem)
            .where(
                DraftItem.status == "expired",
                DraftItem.updated_at >= yesterday_start,
                DraftItem.updated_at < yesterday_end,
            )
        )
        expired_count = expired_result.scalar_one()

        # --- Top 15 gold news stories from last 24 hours (content platform only) ---
        lookback_24h = datetime.now(timezone.utc) - timedelta(hours=24)
        top_stories_result = await session.execute(
            select(DraftItem)
            .where(
                DraftItem.platform == "content",
                DraftItem.created_at >= lookback_24h,
            )
            .order_by(DraftItem.score.desc().nullslast())
            .limit(15)
        )
        top_items = top_stories_result.scalars().all()
        top_stories = [
            {
                # source_text first line is the news headline (e.g. "Reuters: Gold hits...")
                "headline": (item.source_text or "").split("\n")[0].strip()
                or self._headline_from_rationale(item.rationale),
                "source_account": item.source_account or "",
                "platform": item.platform or "",
                "time": item.created_at.isoformat() if item.created_at else None,
                "source_url": item.source_url,
                "score": float(item.score or 0),
            }
            for item in top_items
        ]

        # --- Queue snapshot (current pending items by platform) ---
        snapshot_result = await session.execute(
            select(DraftItem.platform, func.count())
            .where(DraftItem.status == "pending")
            .group_by(DraftItem.platform)
        )
        snapshot_rows = snapshot_result.all()
        queue_snapshot: dict[str, int] = {}
        for platform, count in snapshot_rows:
            queue_snapshot[platform] = count
        queue_snapshot["total"] = sum(v for k, v in queue_snapshot.items() if k != "total")

        # --- Priority alert: highest-scoring currently-pending item ---
        priority_result = await session.execute(
            select(DraftItem)
            .where(DraftItem.status == "pending")
            .order_by(DraftItem.score.desc().nullslast())
            .limit(1)
        )
        priority_item = priority_result.scalar_one_or_none()
        if priority_item is not None:
            priority_alert: dict | None = {
                "id": str(priority_item.id),
                "platform": priority_item.platform,
                "score": float(priority_item.score or 0),
                "source_account": priority_item.source_account,
                "headline": self._headline_from_rationale(priority_item.rationale),
                "expires_at": (
                    priority_item.expires_at.isoformat() if priority_item.expires_at else None
                ),
                "source_url": priority_item.source_url,
            }
        else:
            priority_alert = None

        return {
            "top_stories": top_stories,
            "queue_snapshot": queue_snapshot,
            "yesterday_approved": {"count": approved_count, "items": []},
            "yesterday_rejected": {"count": rejected_count},
            "yesterday_expired": {"count": expired_count},
            "priority_alert": priority_alert,
        }

    async def run_morning_digest(self) -> None:
        """Run the daily 8am morning digest job.

        Assembles yesterday's stats and current queue state, writes a
        ``DailyDigest`` record, and sends the ``morning_digest`` WhatsApp
        template with 7 variables.

        Logs to ``AgentRun`` with ``agent_name='morning_digest'``.
        Errors are captured and do not propagate (EXEC-04).
        """
        async with AsyncSessionLocal() as session:
            run = AgentRun(
                agent_name="morning_digest",
                started_at=datetime.now(timezone.utc),
                status="running",
            )
            session.add(run)
            await session.flush()

            try:
                digest = await self._assemble_digest(session)

                # Write DailyDigest record
                record = DailyDigest(
                    digest_date=date.today(),
                    top_stories=digest["top_stories"],
                    queue_snapshot=digest["queue_snapshot"],
                    yesterday_approved=digest["yesterday_approved"],
                    yesterday_rejected=digest["yesterday_rejected"],
                    yesterday_expired=digest["yesterday_expired"],
                    priority_alert=digest["priority_alert"],
                )
                session.add(record)

                # Build WhatsApp template variables
                var_1 = date.today().isoformat()

                raw_headlines = "; ".join(s["headline"] for s in digest["top_stories"][:5])
                if len(raw_headlines) > 200:
                    # Truncate at last "; " boundary within 200 chars
                    truncated = raw_headlines[:200]
                    last_sep = truncated.rfind("; ")
                    var_2 = (
                        truncated[:last_sep] + "..." if last_sep > 0 else truncated[:197] + "..."
                    )
                else:
                    var_2 = raw_headlines

                var_3 = str(digest["queue_snapshot"].get("total", 0))
                var_4 = str(digest["yesterday_approved"]["count"])
                var_5 = str(digest["yesterday_rejected"]["count"])
                var_6 = str(digest["yesterday_expired"]["count"])
                var_7 = await self._get_config(
                    session, "dashboard_url", "https://app.sevamining.com"
                )

                # Delivery status is recorded into run.notes so a simple
                # SELECT notes FROM agent_runs WHERE agent_name='morning_digest'
                # ORDER BY started_at DESC LIMIT 10
                # tells us, without Railway log access, whether each digest
                # actually hit Twilio. See debug session
                # twilio-morning-digest-not-delivering (2026-04-24) — a
                # multi-week silent failure passed undetected because
                # status='completed' was true regardless of delivery.
                whatsapp_status: str
                try:
                    # Build free-form digest message (Twilio sandbox — no template approval needed)
                    digest_message = (
                        f"📊 Morning Digest — {var_1}\n"
                        f"Queue: {var_3} pending items\n"
                        f"Yesterday: {var_4} approved, {var_5} rejected, {var_6} expired\n"
                        f"Top stories: {var_2}\n"
                        f"Review: {var_7}"
                    )
                    sid = await send_whatsapp_message(digest_message)
                    if sid is None:
                        # send_whatsapp_message returned None => credentials
                        # missing (it already logged which keys at ERROR).
                        whatsapp_status = (
                            "whatsapp_skipped: credentials missing (see scheduler log)"
                        )
                    else:
                        record.whatsapp_sent_at = datetime.now(timezone.utc)
                        whatsapp_status = f"whatsapp_sent: sid={sid}"
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Morning digest WhatsApp send failed (non-fatal): %s", exc)
                    whatsapp_status = f"whatsapp_failed: {type(exc).__name__}: {exc}"
                run.notes = whatsapp_status

                run.status = "completed"
                run.ended_at = datetime.now(timezone.utc)
                await session.commit()

            except Exception as exc:  # noqa: BLE001
                logger.exception("run_morning_digest failed: %s", exc)
                run.status = "failed"
                run.errors = [str(exc)]
                run.ended_at = datetime.now(timezone.utc)
                try:
                    await session.commit()
                except Exception:
                    await session.rollback()


# ---------------------------------------------------------------------------
# Module-level config seeder
# ---------------------------------------------------------------------------


async def seed_senior_config() -> None:
    """Insert Senior Agent default config values if not already present.

    Idempotent — safe to call on every worker startup. Only inserts rows
    for keys that do not yet exist in the config table.

    Config keys seeded (post-sn9 scope — digest-only):
    - dashboard_url: "https://app.sevamining.com"

    Removed in quick-260420-sn9: senior_queue_cap, senior_breaking_news_threshold,
    senior_dedup_threshold, senior_dedup_lookback_hours, senior_expiry_alert_*.
    """
    defaults = {
        "dashboard_url": "https://app.sevamining.com",
    }
    async with AsyncSessionLocal() as session:
        for key, value in defaults.items():
            existing = await session.execute(select(Config.value).where(Config.key == key))
            if existing.scalar_one_or_none() is None:
                session.add(Config(key=key, value=value))
        await session.commit()
    logger.info("seed_senior_config: Senior Agent config defaults verified.")
