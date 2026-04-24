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
