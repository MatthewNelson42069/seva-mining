import asyncio
import json
import logging

from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client

from config import get_settings

logger = logging.getLogger(__name__)

# D-17: Pre-registered Meta-approved template SIDs
TEMPLATE_SIDS = {
    "morning_digest": "HX930c2171b211acdea4d5fa0a12d6c0e0",
    "breaking_news":  "HXc5bcef9a42a18e9071acd1d6fb0fac39",
    "expiry_alert":   "HX45fd40f45d91e2ea54abd2298dd8bc41",
}


def _send_sync(template: str, variables: dict) -> str:
    """Synchronous Twilio send. Called via asyncio.to_thread()."""
    settings = get_settings()
    client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
    msg = client.messages.create(
        from_=settings.twilio_whatsapp_from,
        to=settings.digest_whatsapp_to,
        content_sid=TEMPLATE_SIDS[template],
        content_variables=json.dumps(variables),
    )
    return msg.sid


async def send_whatsapp_template(template: str, variables: dict) -> str:
    """
    Send a pre-approved WhatsApp template message via Twilio.

    D-16: Log + retry once on failure.

    Args:
        template: One of 'morning_digest', 'breaking_news', 'expiry_alert'
        variables: Dict of template variable values, e.g. {"1": "Top stories..."}

    Returns:
        Twilio message SID on success.

    Raises:
        KeyError: If template name is not in TEMPLATE_SIDS.
        TwilioRestException: On Twilio API failure after retry.
    """
    # Validate template name early
    if template not in TEMPLATE_SIDS:
        raise KeyError(f"Unknown template: {template}. Valid: {list(TEMPLATE_SIDS.keys())}")

    try:
        return await asyncio.to_thread(_send_sync, template, variables)
    except TwilioRestException as e:
        logger.warning("Twilio send failed (attempt 1), retrying: %s", e)
        try:
            return await asyncio.to_thread(_send_sync, template, variables)
        except TwilioRestException as e2:
            logger.error("Twilio send failed (attempt 2), giving up: %s", e2)
            raise
