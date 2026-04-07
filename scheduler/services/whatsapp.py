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

    # Graceful skip if any required credential is absent
    if not all([
        settings.twilio_account_sid,
        settings.twilio_auth_token,
        settings.twilio_whatsapp_from,
        settings.digest_whatsapp_to,
    ]):
        logger.warning(
            "WhatsApp notification skipped — Twilio credentials not configured. "
            "Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM, "
            "and DIGEST_WHATSAPP_TO in environment."
        )
        return None

    try:
        return await asyncio.to_thread(_send_sync, message)
    except TwilioRestException as e:
        logger.warning("Twilio send failed (attempt 1), retrying: %s", e)
        try:
            return await asyncio.to_thread(_send_sync, message)
        except TwilioRestException as e2:
            logger.error("Twilio send failed (attempt 2), giving up: %s", e2)
            raise
