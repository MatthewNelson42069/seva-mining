"""
WhatsApp notification service using Twilio WhatsApp Sandbox.

Sends free-form text messages (no Meta template approval required).
Sandbox number: whatsapp:+14155238886
Recipient must have opted in via: "join government-accident" to +14155238886

Decision (Phase 10): Switched from content_sid (template SIDs) to body (free-form)
for Twilio sandbox support. TEMPLATE_SIDS removed entirely.
"""

import asyncio
import logging

from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client

from config import get_settings

logger = logging.getLogger(__name__)


def _send_sync(message: str) -> str:
    """Synchronous Twilio send. Called via asyncio.to_thread() to avoid blocking."""
    settings = get_settings()
    client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
    msg = client.messages.create(
        from_=settings.twilio_whatsapp_from,
        to=settings.digest_whatsapp_to,
        body=message,
    )
    return msg.sid


async def send_whatsapp_message(message: str) -> str | None:
    """
    Send a free-form WhatsApp message via the Twilio sandbox.

    Gracefully skips (returns None) if Twilio credentials are not configured
    in the environment — agents must not crash if Twilio is absent.

    Retries once on TwilioRestException. If the second attempt also fails,
    logs the error and raises.

    Args:
        message: Plain text message body to send.

    Returns:
        Twilio message SID on success, or None if credentials are missing.

    Raises:
        TwilioRestException: On Twilio API failure after one retry.
    """
    settings = get_settings()

    # Graceful skip if any required credential is absent. The caller contract
    # is: returns None on cred miss, raises on Twilio API error. Do NOT change
    # the return-None path without updating callers — senior_agent and the
    # send tests rely on this behavior.
    # However: log at ERROR (not WARNING) and name the missing keys so this
    # is visible in Railway production logs. The old WARNING-level log was
    # invisible in Railway's default log stream and hid a multi-week silent
    # failure — see debug session twilio-morning-digest-not-delivering
    # (2026-04-24).
    missing = [
        name
        for name, present in (
            ("TWILIO_ACCOUNT_SID", bool(settings.twilio_account_sid)),
            ("TWILIO_AUTH_TOKEN", bool(settings.twilio_auth_token)),
            ("TWILIO_WHATSAPP_FROM", bool(settings.twilio_whatsapp_from)),
            ("DIGEST_WHATSAPP_TO", bool(settings.digest_whatsapp_to)),
        )
        if not present
    ]
    if missing:
        logger.error(
            "WhatsApp notification SKIPPED — missing env vars on this service: %s. "
            "Set these in the Railway scheduler service (NOT the API service — "
            "they are separate Railway services with independent env sets) and redeploy.",
            ", ".join(missing),
        )
        return None

    try:
        sid = await asyncio.to_thread(_send_sync, message)
        logger.info("WhatsApp send OK — Twilio SID=%s", sid)
        return sid
    except TwilioRestException as e:
        logger.warning("Twilio send failed (attempt 1), retrying: %s", e)
        try:
            sid = await asyncio.to_thread(_send_sync, message)
            logger.info("WhatsApp send OK on retry — Twilio SID=%s", sid)
            return sid
        except TwilioRestException as e2:
            logger.error(
                "Twilio send failed (attempt 2), giving up. status=%s code=%s msg=%s",
                getattr(e2, "status", None),
                getattr(e2, "code", None),
                getattr(e2, "msg", str(e2)),
            )
            raise


# ---------------------------------------------------------------------------
# quick-260424-i8b: per-run firehose helpers
# ---------------------------------------------------------------------------


def build_chunks(
    agent_name: str,
    items: list[str],
    max_chunk_chars: int = 1500,
) -> list[str]:
    """Build WhatsApp message chunks from a list of approved tweet texts.

    Packs items greedily into chunks up to max_chunk_chars. Never splits an
    individual item across chunks. Single-chunk output has NO continuation prefix.
    Multi-chunk output prefixes every chunk with ``[<short_name> X/N]``.

    Args:
        agent_name: Agent name, e.g. "sub_breaking_news" or "sub_threads".
            The "sub_" prefix is stripped to produce the short name used in headers.
        items: List of approved tweet/thread text strings. Empty list → [].
        max_chunk_chars: Per-chunk character budget (default 1500 — 100-char safety
            margin below Twilio's 1600-char hard cap).

    Returns:
        List of message strings ready to send. May be empty if items is empty.
    """
    short_name = agent_name.removeprefix("sub_")
    n = len(items)
    if n == 0:
        return []

    header = f"[{short_name}] {n} approved:"
    blocks = [f"{i}. {text}" for i, text in enumerate(items, start=1)]

    chunks: list[str] = []
    current = header
    for block in blocks:
        tentative = current + "\n\n" + block
        if len(tentative) <= max_chunk_chars:
            current = tentative
        else:
            chunks.append(current)
            current = block  # new chunk starts with the block (no repeated header)
    chunks.append(current)

    if len(chunks) == 1:
        return chunks

    # Multi-chunk: prefix every chunk with [short_name X/N]
    total = len(chunks)
    return [f"[{short_name} {i}/{total}]\n{c}" for i, c in enumerate(chunks, start=1)]


async def send_agent_run_notification(
    agent_name: str,
    items: list[str],
    run_id: int,
) -> list[str]:
    """Per-run firehose dispatcher for sub_breaking_news and sub_threads.

    Sends one or more WhatsApp messages listing all approved items from this run.
    Returns a list of Twilio SIDs (one per chunk sent). Empty list if items is
    empty OR if the first chunk returns None (credentials missing).

    Twilio exceptions propagate to the caller's try/except (content/__init__.py
    hook) which records failure into agent_run.notes.

    Args:
        agent_name: Agent name, e.g. "sub_breaking_news".
        items: List of approved tweet/thread text strings from this run.
        run_id: The agent_run.id for this run (for logging/tracing).

    Returns:
        List of Twilio message SIDs, one per chunk dispatched.
    """
    if not items:
        return []

    chunks = build_chunks(agent_name, items)
    sids: list[str] = []
    for chunk in chunks:
        sid = await send_whatsapp_message(chunk)
        if sid is None:
            # Credentials missing — don't attempt remaining chunks; return what we have.
            logger.warning(
                "send_agent_run_notification: credentials missing for run_id=%s "
                "(agent=%s), stopping after chunk %d/%d",
                run_id,
                agent_name,
                len(sids) + 1,
                len(chunks),
            )
            return sids
        sids.append(sid)
    return sids
