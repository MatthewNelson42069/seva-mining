"""
Tests for scheduler/services/whatsapp.py
Covers: WHAT-01, WHAT-05
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Required env vars before any project import
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://fake/db")
os.environ.setdefault("ANTHROPIC_API_KEY", "x")
os.environ.setdefault("X_API_BEARER_TOKEN", "x")
os.environ.setdefault("TWILIO_ACCOUNT_SID", "AC_test_sid")
os.environ.setdefault("TWILIO_AUTH_TOKEN", "test_auth_token")
os.environ.setdefault("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
os.environ.setdefault("DIGEST_WHATSAPP_TO", "whatsapp:+15550001234")

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from twilio.base.exceptions import TwilioRestException


@pytest.mark.asyncio
async def test_send_whatsapp_message_happy_path():
    """Happy path: all credentials present, _send_sync returns SID."""
    from services.whatsapp import send_whatsapp_message

    with patch("services.whatsapp._send_sync", return_value="SM_test_sid") as mock_send:
        result = await send_whatsapp_message("Gold Agent: 3 new items")

    assert result == "SM_test_sid"
    mock_send.assert_called_once_with("Gold Agent: 3 new items")


@pytest.mark.asyncio
async def test_send_whatsapp_message_missing_credentials():
    """Missing credential: returns None, never calls Twilio Client."""
    from services.whatsapp import send_whatsapp_message

    mock_settings = MagicMock()
    mock_settings.twilio_account_sid = None   # <-- missing
    mock_settings.twilio_auth_token = "tok"
    mock_settings.twilio_whatsapp_from = "whatsapp:+14155238886"
    mock_settings.digest_whatsapp_to = "whatsapp:+15550001234"

    with patch("services.whatsapp.get_settings", return_value=mock_settings):
        with patch("services.whatsapp._send_sync") as mock_send:
            result = await send_whatsapp_message("test message")

    assert result is None
    mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_send_whatsapp_message_retries_and_raises():
    """TwilioRestException on both attempts: retries once, then raises."""
    from services.whatsapp import send_whatsapp_message

    exc = TwilioRestException(status=500, uri="/messages", msg="fail")

    with patch("services.whatsapp._send_sync", side_effect=exc) as mock_send:
        with pytest.raises(TwilioRestException):
            await send_whatsapp_message("test")

    assert mock_send.call_count == 2
