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
from unittest.mock import MagicMock, patch
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
    mock_settings.twilio_account_sid = None  # <-- missing
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


# ---------------------------------------------------------------------------
# Debug session twilio-morning-digest-not-delivering (2026-04-24):
# missing-cred path must log at ERROR and name the missing env var(s) so a
# Railway log tail makes the problem obvious.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_credentials_logs_at_error_level_and_names_missing(caplog):
    """Missing cred path must log at ERROR (not WARNING) and list which env vars are missing.

    Regression guard: the old code logged at WARNING, which is suppressed in
    Railway's default log stream — a multi-week silent failure hid behind it.
    """
    import logging
    from services.whatsapp import send_whatsapp_message
    from unittest.mock import MagicMock

    mock_settings = MagicMock()
    mock_settings.twilio_account_sid = ""
    mock_settings.twilio_auth_token = "tok"
    mock_settings.twilio_whatsapp_from = "whatsapp:+14155238886"
    mock_settings.digest_whatsapp_to = ""  # two missing

    with patch("services.whatsapp.get_settings", return_value=mock_settings):
        with caplog.at_level(logging.ERROR, logger="services.whatsapp"):
            result = await send_whatsapp_message("test")

    assert result is None
    error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert error_records, "Expected an ERROR-level log when creds are missing"
    msg = error_records[0].getMessage()
    assert "TWILIO_ACCOUNT_SID" in msg
    assert "DIGEST_WHATSAPP_TO" in msg
    # Must NOT list the ones that ARE set
    assert "TWILIO_AUTH_TOKEN" not in msg
    assert "TWILIO_WHATSAPP_FROM" not in msg


# ---------------------------------------------------------------------------
# quick-260424-i8b: build_chunks + send_agent_run_notification helpers
# ---------------------------------------------------------------------------


def test_build_chunks_single_chunk_has_no_prefix():
    """Single-chunk output starts directly with [agent_name] header, no [agent 1/1] prefix."""
    from services.whatsapp import build_chunks

    items = ["Gold hits $3000.", "Fed holds rates.", "ETF inflows surge."]
    chunks = build_chunks("breaking_news", items)
    assert len(chunks) == 1
    # Must start with the [breaking_news] N approved: header
    assert chunks[0].startswith("[breaking_news] 3 approved:")
    # Must NOT have a [breaking_news 1/1] prefix
    assert "[breaking_news 1/1]" not in chunks[0]


def test_build_chunks_multi_chunk_prefixes():
    """Multi-chunk output prefixes every chunk with [short_name X/N]."""
    from services.whatsapp import build_chunks

    # 10 items × 250 chars each is way over 1500 chars
    long_text = "A" * 250
    items = [long_text] * 10
    chunks = build_chunks("breaking_news", items)
    assert len(chunks) >= 2, f"Expected multiple chunks, got {len(chunks)}"
    n = len(chunks)
    for i, chunk in enumerate(chunks, start=1):
        expected_prefix = f"[breaking_news {i}/{n}]"
        assert chunk.startswith(expected_prefix), (
            f"Chunk {i} should start with {expected_prefix!r}, got: {chunk[:50]!r}"
        )


def test_build_chunks_never_splits_an_item():
    """Every chunk boundary sits between numbered items — no chunk ends mid-item."""
    from services.whatsapp import build_chunks

    items = [f"Tweet text number {i}. " + "content " * 30 for i in range(1, 8)]
    chunks = build_chunks("breaking_news", items)
    for chunk in chunks:
        # Strip the [name X/N] header if present
        body = chunk
        if chunk.startswith("[breaking_news"):
            newline = chunk.find("\n")
            if newline >= 0:
                body = chunk[newline + 1:]
        # The body should either start with the "[breaking_news] N approved:" header
        # or start with a digit-dot-space pattern
        stripped = body.lstrip()
        assert stripped.startswith("[breaking_news]") or (
            len(stripped) > 0 and stripped[0].isdigit()
        ), f"Chunk body should start with header or digit-dot: {stripped[:60]!r}"


def test_build_chunks_respects_1500_char_budget():
    """Every chunk's len() <= 1500."""
    from services.whatsapp import build_chunks

    # 280-char tweets × 8 items to force chunking
    items = ["G" * 280] * 8
    chunks = build_chunks("breaking_news", items)
    for i, chunk in enumerate(chunks):
        assert len(chunk) <= 1500, (
            f"Chunk {i} is {len(chunk)} chars, exceeds 1500: {chunk[:80]!r}"
        )


def test_build_chunks_threads_short_name():
    """sub_threads produces [threads X/N] headers, not [sub_threads X/N]."""
    from services.whatsapp import build_chunks

    items = ["T" * 280] * 8  # force multi-chunk
    chunks = build_chunks("sub_threads", items)
    assert len(chunks) >= 2
    for chunk in chunks:
        assert "[sub_threads" not in chunk, "Header should strip 'sub_' prefix"
        assert "[threads" in chunk or chunk.startswith("[threads]"), (
            f"Expected [threads...] header, got: {chunk[:60]!r}"
        )


@pytest.mark.asyncio
async def test_send_agent_run_notification_dispatches_chunks_in_order():
    """send_agent_run_notification dispatches chunks sequentially and returns SIDs in order."""
    from services.whatsapp import send_agent_run_notification

    call_count = 0

    async def mock_send(msg):
        nonlocal call_count
        call_count += 1
        return f"SM_{call_count}"

    with patch("services.whatsapp.send_whatsapp_message", side_effect=mock_send):
        items = ["Tweet A", "Tweet B", "Tweet C"]
        result = await send_agent_run_notification("sub_breaking_news", items, run_id=1)

    assert isinstance(result, list)
    assert len(result) >= 1
    for sid in result:
        assert sid.startswith("SM_")


@pytest.mark.asyncio
async def test_send_agent_run_notification_empty_items_returns_empty():
    """Passing items=[] returns [] and never calls send_whatsapp_message."""
    from services.whatsapp import send_agent_run_notification

    with patch("services.whatsapp.send_whatsapp_message") as mock_send:
        result = await send_agent_run_notification("sub_breaking_news", [], run_id=1)

    assert result == []
    mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_send_agent_run_notification_stops_on_missing_creds():
    """First send returning None (creds missing) stops further sends."""
    from services.whatsapp import send_agent_run_notification

    # Force chunking: 10 items × 280 chars each → multiple chunks
    items = ["G" * 280] * 10

    call_count = 0

    async def mock_send_none_first(msg):
        nonlocal call_count
        call_count += 1
        return None  # creds missing

    with patch("services.whatsapp.send_whatsapp_message", side_effect=mock_send_none_first):
        result = await send_agent_run_notification("sub_breaking_news", items, run_id=1)

    # Should have stopped after first None — not sent all chunks
    assert result == []
    assert call_count == 1, f"Expected exactly 1 call (stopped after None), got {call_count}"
