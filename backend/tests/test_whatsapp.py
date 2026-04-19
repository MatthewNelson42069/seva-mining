"""
Tests for WhatsApp notification service (app.services.whatsapp).

Uses unittest.mock to avoid real Twilio API calls.
"""
import json
from unittest.mock import MagicMock, patch

import pytest

from app.config import Settings

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_settings() -> Settings:
    """Return a Settings-like object with test Twilio credentials."""
    return Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        anthropic_api_key="test-key",
        twilio_account_sid="ACtest1234",
        twilio_auth_token="auth_token_test",
        twilio_whatsapp_from="whatsapp:+14155238886",
        digest_whatsapp_to="whatsapp:+15551234567",
        x_api_bearer_token="test-bearer",
        x_api_key="test-key",
        x_api_secret="test-secret",
        serpapi_api_key="test-key",
        jwt_secret="a" * 32,  # >=32 bytes to pass _jwt_secret_min_length validator
        dashboard_password="$2b$12$test",
        frontend_url="http://localhost:3000",
    )


# ---------------------------------------------------------------------------
# Template SID tests
# ---------------------------------------------------------------------------

async def test_template_sid_morning_digest():
    """send_whatsapp_template('morning_digest', ...) uses the correct content_sid."""
    from app.services.whatsapp import send_whatsapp_template

    mock_message = MagicMock()
    mock_message.sid = "SM123"

    with patch("app.services.whatsapp.get_settings", return_value=_make_settings()), \
         patch("app.services.whatsapp.Client") as MockClient:

        mock_client_instance = MockClient.return_value
        mock_client_instance.messages.create.return_value = mock_message

        result = await send_whatsapp_template("morning_digest", {"1": "Top stories today"})

    assert result == "SM123"
    mock_client_instance.messages.create.assert_called_once()
    call_kwargs = mock_client_instance.messages.create.call_args.kwargs
    assert call_kwargs["content_sid"] == "HX930c2171b211acdea4d5fa0a12d6c0e0"
    assert call_kwargs["from_"] == "whatsapp:+14155238886"
    assert call_kwargs["to"] == "whatsapp:+15551234567"
    assert call_kwargs["content_variables"] == json.dumps({"1": "Top stories today"})


async def test_template_sid_breaking_news():
    """send_whatsapp_template('breaking_news', ...) uses the correct content_sid."""
    from app.services.whatsapp import send_whatsapp_template

    mock_message = MagicMock()
    mock_message.sid = "SM456"

    with patch("app.services.whatsapp.get_settings", return_value=_make_settings()), \
         patch("app.services.whatsapp.Client") as MockClient:

        mock_client_instance = MockClient.return_value
        mock_client_instance.messages.create.return_value = mock_message

        result = await send_whatsapp_template("breaking_news", {"1": "Gold hits $3000"})

    assert result == "SM456"
    call_kwargs = mock_client_instance.messages.create.call_args.kwargs
    assert call_kwargs["content_sid"] == "HXc5bcef9a42a18e9071acd1d6fb0fac39"


async def test_template_sid_expiry_alert():
    """send_whatsapp_template('expiry_alert', ...) uses the correct content_sid."""
    from app.services.whatsapp import send_whatsapp_template

    mock_message = MagicMock()
    mock_message.sid = "SM789"

    with patch("app.services.whatsapp.get_settings", return_value=_make_settings()), \
         patch("app.services.whatsapp.Client") as MockClient:

        mock_client_instance = MockClient.return_value
        mock_client_instance.messages.create.return_value = mock_message

        result = await send_whatsapp_template("expiry_alert", {"1": "2 items expiring soon"})

    assert result == "SM789"
    call_kwargs = mock_client_instance.messages.create.call_args.kwargs
    assert call_kwargs["content_sid"] == "HX45fd40f45d91e2ea54abd2298dd8bc41"


# ---------------------------------------------------------------------------
# Error handling tests
# ---------------------------------------------------------------------------

async def test_invalid_template_name():
    """send_whatsapp_template with unknown name raises KeyError immediately."""
    from app.services.whatsapp import send_whatsapp_template

    with pytest.raises(KeyError, match="nonexistent"):
        await send_whatsapp_template("nonexistent", {})


async def test_twilio_failure_logged_and_reraised():
    """On TwilioRestException, function logs error and re-raises after retry."""
    from twilio.base.exceptions import TwilioRestException

    from app.services.whatsapp import send_whatsapp_template

    # Simulate Twilio SDK raising an exception — create one that matches the real signature
    twilio_error = TwilioRestException(
        status=500,
        uri="/Messages",
        msg="Service unavailable",
        code=20001,
        method="POST",
    )

    with patch("app.services.whatsapp.get_settings", return_value=_make_settings()), \
         patch("app.services.whatsapp.Client") as MockClient, \
         patch("app.services.whatsapp.logger") as mock_logger:

        mock_client_instance = MockClient.return_value
        mock_client_instance.messages.create.side_effect = twilio_error

        with pytest.raises(TwilioRestException):
            await send_whatsapp_template("morning_digest", {"1": "Test"})

        # Should have logged a warning on attempt 1 and error on attempt 2
        assert mock_logger.warning.called
        assert mock_logger.error.called
        # Two attempts (initial + retry)
        assert mock_client_instance.messages.create.call_count == 2
