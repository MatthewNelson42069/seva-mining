"""Tests for scheduler/agents/ontario_law.py — Phase 2, Plan 01.

Coverage (Tests A through M from plan):
  A: Synthetic positive filter (real Haiku, gated by ANTHROPIC_API_KEY env)
  B: Synthetic REJECT-1 (mocked anthropic) — "Minister speaks at mining association gala"
  C: Synthetic REJECT-2 (mocked) — "Government announces consultation..."
  D: ACCEPT example in prompt — contains "Bill 71" AND "Royal Assent" AND "Mining Act"
  E: Filter body length truncation — 5000-char body truncated to 1500 chars
  F: Dedup by URL — 2 duplicate URLs → 2 unique
  G: Survival rule truth table (5 cases)
  H: SerpAPI fetcher uses qdr:d 24h date filter + keyword constants
  I: NRCan fetcher hits exact URL
  J: SerpAPI raises → survivors from NRCan only (section does NOT raise)
  K: NRCan raises → survivors from SerpAPI only (section does NOT raise)
  L: Both sources empty → empty list (filter NOT called)
  M: Telemetry counts surfaced in tuple (serpapi, nrcan, after_dedup, after_filter)
"""
from __future__ import annotations

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://fake-pooler.neon.tech/db?sslmode=require"
)
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test-fake")
os.environ.setdefault("X_API_BEARER_TOKEN", "x")
os.environ.setdefault("SERPAPI_API_KEY", "x")


from agents.ontario_law import (  # noqa: E402
    FILTER_BODY_MAX_CHARS,
    FILTER_SYSTEM_PROMPT,
    NRCAN_ATOM_URL,
    SERPAPI_DATE_FILTER,
    OntarioLawHit,
    _dedup_by_url,
    _fetch_nrcan_candidates,
    _fetch_serpapi_candidates,
    _filter_one,
    _survives,
    fetch_ontario_law_hits,
)


# ---------------------------------------------------------------------------
# Test A — Synthetic positive filter (real Haiku, gated by API key)
# ---------------------------------------------------------------------------

def _is_fake_api_key() -> bool:
    """Return True if the env has a fake/test/empty API key (not a real key)."""
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    return not key or key.startswith("sk-test-") or key == "sk-test-fake"


@pytest.mark.asyncio
@pytest.mark.skipif(
    _is_fake_api_key(),
    reason="real Haiku key required for synthetic positive test",
)
async def test_filter_positive_building_ontario_act():
    """Real Haiku call: Building Ontario Act amends Mining Act → is_law=True."""
    from anthropic import AsyncAnthropic

    client = AsyncAnthropic(
        api_key=os.environ["ANTHROPIC_API_KEY"], timeout=30.0
    )
    result = await _filter_one(
        client,
        model="claude-haiku-4-5",
        title="Building Ontario Act amends Mining Act",
        body=(
            "Bill 71 received Royal Assent yesterday and amends the Mining Act "
            "sections 21 through 24, effective January 1 2027. The amendments "
            "streamline exploration permit applications and reduce staking fees."
        ),
    )
    assert result["is_law"] is True, f"Expected is_law=True, got: {result}"
    assert result["bill_or_reg_number"] is not None, (
        f"Expected bill_or_reg_number to be set, got: {result}"
    )
    assert "71" in (result["bill_or_reg_number"] or ""), (
        f"Expected Bill 71 in bill_or_reg_number, got: {result['bill_or_reg_number']}"
    )
    assert result["favour_or_neutral"] != "against", (
        f"Expected favour or neutral, got: {result['favour_or_neutral']}"
    )


# ---------------------------------------------------------------------------
# Test B — REJECT-1 (mocked): "Minister speaks at mining association gala"
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_filter_reject_ministerial_speech():
    """Mocked: REJECT example 1 returns is_law=False with correct prompt content."""
    reject_response = {
        "is_law": False,
        "bill_or_reg_number": None,
        "reason": "ministerial speech, no enacted law",
        "favour_or_neutral": "neutral",
    }

    import json

    captured_messages = []

    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=json.dumps(reject_response))]

    mock_client = AsyncMock()

    async def mock_create(**kwargs):
        captured_messages.append(kwargs)
        return mock_response

    mock_client.messages.create = mock_create

    result = await _filter_one(
        mock_client,
        model="claude-haiku-4-5",
        title="Minister speaks at mining association gala",
        body="The Minister of Mines addressed the Ontario Mining Association today.",
    )

    assert result["is_law"] is False
    assert result["bill_or_reg_number"] is None

    # Verify the REJECT example 1 appears VERBATIM in the system prompt sent
    assert len(captured_messages) == 1
    system_prompt = captured_messages[0]["system"]
    assert "Minister speaks at mining association gala" in system_prompt, (
        "REJECT example 1 must appear verbatim in filter prompt (HIGH-1)"
    )


# ---------------------------------------------------------------------------
# Test C — REJECT-2 (mocked): "Government announces consultation..."
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_filter_reject_consultation_announcement():
    """Mocked: REJECT example 2 returns is_law=False with correct prompt content."""
    import json

    reject_response = {
        "is_law": False,
        "bill_or_reg_number": None,
        "reason": "announcement of consultation, not a bill or law",
        "favour_or_neutral": "neutral",
    }

    captured_messages = []

    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=json.dumps(reject_response))]

    mock_client = AsyncMock()

    async def mock_create(**kwargs):
        captured_messages.append(kwargs)
        return mock_response

    mock_client.messages.create = mock_create

    result = await _filter_one(
        mock_client,
        model="claude-haiku-4-5",
        title="Government announces consultation on critical minerals strategy",
        body="The government has launched a new consultation process.",
    )

    assert result["is_law"] is False
    assert result["bill_or_reg_number"] is None

    # Verify REJECT example 2 appears VERBATIM in system prompt
    system_prompt = captured_messages[0]["system"]
    assert "Government announces consultation on critical minerals strategy" in system_prompt, (
        "REJECT example 2 must appear verbatim in filter prompt (HIGH-1)"
    )


# ---------------------------------------------------------------------------
# Test D — ACCEPT example in prompt
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_filter_prompt_contains_accept_example():
    """Filter prompt contains the ACCEPT example with Bill 71, Royal Assent, Mining Act."""
    import json

    captured_messages = []

    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=json.dumps({
        "is_law": True, "bill_or_reg_number": "Bill 71",
        "reason": "test", "favour_or_neutral": "favour",
    }))]

    mock_client = AsyncMock()

    async def mock_create(**kwargs):
        captured_messages.append(kwargs)
        return mock_response

    mock_client.messages.create = mock_create

    await _filter_one(
        mock_client,
        model="claude-haiku-4-5",
        title="Bill 71 (Building Ontario Act) receives Royal Assent",
        body="Amends Mining Act sections 21-24.",
    )

    system_prompt = captured_messages[0]["system"]
    assert "Bill 71" in system_prompt, "ACCEPT example must contain 'Bill 71'"
    assert "Royal Assent" in system_prompt, "ACCEPT example must contain 'Royal Assent'"
    assert "Mining Act" in system_prompt, "ACCEPT example must contain 'Mining Act'"


# ---------------------------------------------------------------------------
# Test E — Filter body length truncation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_filter_body_truncated_to_1500_chars():
    """_filter_one truncates body to FILTER_BODY_MAX_CHARS (1500) before sending."""
    import json

    assert FILTER_BODY_MAX_CHARS == 1500

    captured_messages = []
    long_body = "x" * 5000  # well over 1500

    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=json.dumps({
        "is_law": False, "bill_or_reg_number": None,
        "reason": "test", "favour_or_neutral": "neutral",
    }))]

    mock_client = AsyncMock()

    async def mock_create(**kwargs):
        captured_messages.append(kwargs)
        return mock_response

    mock_client.messages.create = mock_create

    await _filter_one(
        mock_client,
        model="claude-haiku-4-5",
        title="Test title",
        body=long_body,
    )

    user_content = captured_messages[0]["messages"][0]["content"]
    # The body section in the message should not contain more than 1500 x's
    assert user_content.count("x") <= FILTER_BODY_MAX_CHARS, (
        f"Body was not truncated: found {user_content.count('x')} chars, max {FILTER_BODY_MAX_CHARS}"
    )


# ---------------------------------------------------------------------------
# Test F — Dedup by URL
# ---------------------------------------------------------------------------

def test_dedup_by_url_removes_duplicates():
    """_dedup_by_url([u1, u1, u2]) returns 2 unique items."""
    candidates = [
        {"link": "https://example.com/1", "title": "A"},
        {"link": "https://example.com/1", "title": "A duplicate"},
        {"link": "https://example.com/2", "title": "B"},
    ]
    result = _dedup_by_url(candidates)
    assert len(result) == 2
    assert result[0]["title"] == "A"
    assert result[1]["title"] == "B"


def test_dedup_by_url_empty_link_skipped():
    """Candidates with empty link string are skipped."""
    candidates = [
        {"link": "", "title": "No link"},
        {"link": "https://example.com/1", "title": "Has link"},
    ]
    result = _dedup_by_url(candidates)
    assert len(result) == 1
    assert result[0]["title"] == "Has link"


# ---------------------------------------------------------------------------
# Test G — Survival rule truth table (5 cases)
# ---------------------------------------------------------------------------

def test_filter_survival_rule_table():
    """_survives truth table: 2 pass, 3 reject (LAW-02 D-Survival)."""
    cases = [
        # (filter_result, expected_survives)
        ({"is_law": True, "bill_or_reg_number": "Bill 71", "favour_or_neutral": "favour"}, True),
        ({"is_law": True, "bill_or_reg_number": "Reg 23/26", "favour_or_neutral": "neutral"}, True),
        ({"is_law": True, "bill_or_reg_number": "Bill 7", "favour_or_neutral": "against"}, False),
        ({"is_law": True, "bill_or_reg_number": None, "favour_or_neutral": "favour"}, False),
        ({"is_law": False, "bill_or_reg_number": "Bill 71", "favour_or_neutral": "favour"}, False),
    ]
    for fr, expected in cases:
        result = _survives(fr)
        assert result is expected, (
            f"_survives({fr}) expected {expected}, got {result}"
        )


# ---------------------------------------------------------------------------
# Test H — SerpAPI fetcher uses qdr:d + SERPAPI_QUERY keyword constants
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_serpapi_fetcher_uses_24h_date_filter():
    """_fetch_serpapi_candidates calls client.search with tbs=qdr:d and keyword query."""
    assert SERPAPI_DATE_FILTER == "qdr:d"

    captured_calls = []
    mock_client = MagicMock()

    def mock_search(params):
        captured_calls.append(params)
        return {"news_results": []}

    mock_client.search = mock_search

    with patch(
        "agents.ontario_law.asyncio.get_event_loop"
    ) as mock_loop:
        # run_in_executor should call the function synchronously in tests
        async def fake_run_in_executor(executor, func):
            return func()

        mock_loop.return_value.run_in_executor = fake_run_in_executor
        await _fetch_serpapi_candidates(mock_client)

    assert len(captured_calls) == 1
    call_params = captured_calls[0]
    assert call_params.get("tbs") == "qdr:d", (
        f"Expected tbs=qdr:d (24h filter), got: {call_params.get('tbs')}"
    )
    # Verify query contains key terms from SERPAPI_QUERY constant
    assert "Ontario" in call_params.get("q", ""), (
        f"Expected 'Ontario' in SerpAPI query, got: {call_params.get('q')}"
    )
    assert "Mining Act" in call_params.get("q", ""), (
        f"Expected 'Mining Act' in SerpAPI query, got: {call_params.get('q')}"
    )


# ---------------------------------------------------------------------------
# Test I — NRCan fetcher hits exact URL
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_nrcan_fetcher_hits_exact_url():
    """_fetch_nrcan_candidates GETs the exact NRCan Atom URL."""
    assert "naturalresourcescanada" in NRCAN_ATOM_URL
    assert "pick=50" in NRCAN_ATOM_URL
    assert "format=atom" in NRCAN_ATOM_URL

    captured_urls = []

    class FakeResponse:
        text = "<feed><entry></entry></feed>"
        def raise_for_status(self): pass

    class FakeClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def get(self, url, **kwargs):
            captured_urls.append(url)
            return FakeResponse()

    with patch("agents.ontario_law.httpx.AsyncClient", return_value=FakeClient()), \
         patch("agents.ontario_law.feedparser.parse", return_value=MagicMock(entries=[])), \
         patch(
             "agents.ontario_law.asyncio.get_event_loop"
         ) as mock_loop:
        async def fake_run_in_executor(executor, func, *args):
            return func(*args)
        mock_loop.return_value.run_in_executor = fake_run_in_executor
        await _fetch_nrcan_candidates()

    assert len(captured_urls) == 1
    assert captured_urls[0] == NRCAN_ATOM_URL, (
        f"Expected exact NRCan URL, got: {captured_urls[0]}"
    )


# ---------------------------------------------------------------------------
# Test J — SerpAPI raises → survivors from NRCan only (resilience)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_source_failure_resilience_serpapi_raises():
    """When SerpAPI raises, survivors from NRCan still returned — section does NOT raise."""
    import json

    nrcan_hit = {
        "title": "Bill 71 (Building Ontario Act) receives Royal Assent",
        "link": "https://nrcan.gc.ca/news/bill71",
        "source_name": "naturalresourcescanada",
        "summary": "Amends Mining Act sections 21-24 effective Jan 1 2027.",
        "published_at": None,
    }

    filter_response = {
        "is_law": True,
        "bill_or_reg_number": "Bill 71",
        "reason": "named bill amending Mining Act",
        "favour_or_neutral": "favour",
    }

    mock_anthropic = AsyncMock()
    mock_anthropic.messages.create = AsyncMock(
        return_value=MagicMock(
            content=[MagicMock(text=json.dumps(filter_response))]
        )
    )

    mock_serpapi = MagicMock()  # serpapi_client present but will raise

    with patch("agents.ontario_law._fetch_serpapi_candidates", side_effect=RuntimeError("SerpAPI down")), \
         patch("agents.ontario_law._fetch_nrcan_candidates", return_value=[nrcan_hit]):
        survivors, counts = await fetch_ontario_law_hits(
            serpapi_client=mock_serpapi,
            anthropic_client=mock_anthropic,
            model="claude-haiku-4-5",
        )

    # Section must not raise; NRCan survivors must come through
    assert counts["serpapi"] == 0  # SerpAPI failed, count stays 0
    assert counts["nrcan"] == 1
    assert counts["after_filter"] == 1
    assert len(survivors) == 1
    assert survivors[0].bill_or_reg_number == "Bill 71"


# ---------------------------------------------------------------------------
# Test K — NRCan raises → survivors from SerpAPI only (resilience)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_source_failure_resilience_nrcan_raises():
    """When NRCan raises, survivors from SerpAPI still returned — section does NOT raise."""
    import json

    serpapi_hit = {
        "title": "Ontario Regulation 23/26 amends staking rules",
        "link": "https://news.ontario.ca/reg23-26",
        "source_name": "ontario.ca",
        "summary": "Ontario Regulation 23/26 amends staking rules effective March 2026.",
        "published_at": None,
    }

    filter_response = {
        "is_law": True,
        "bill_or_reg_number": "Reg 23/26",
        "reason": "regulation amending staking rules",
        "favour_or_neutral": "neutral",
    }

    mock_anthropic = AsyncMock()
    mock_anthropic.messages.create = AsyncMock(
        return_value=MagicMock(
            content=[MagicMock(text=json.dumps(filter_response))]
        )
    )

    mock_serpapi = MagicMock()

    with patch("agents.ontario_law._fetch_serpapi_candidates", return_value=[serpapi_hit]), \
         patch("agents.ontario_law._fetch_nrcan_candidates", side_effect=RuntimeError("NRCan down")):
        survivors, counts = await fetch_ontario_law_hits(
            serpapi_client=mock_serpapi,
            anthropic_client=mock_anthropic,
            model="claude-haiku-4-5",
        )

    assert counts["serpapi"] == 1
    assert counts["nrcan"] == 0  # NRCan failed, count stays 0
    assert counts["after_filter"] == 1
    assert len(survivors) == 1
    assert survivors[0].bill_or_reg_number == "Reg 23/26"


# ---------------------------------------------------------------------------
# Test L — Both sources empty → empty list (filter NOT called)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_both_sources_empty_returns_empty_list():
    """When both SerpAPI and NRCan return zero candidates, no filter is called."""
    mock_anthropic = AsyncMock()
    mock_serpapi = MagicMock()

    with patch("agents.ontario_law._fetch_serpapi_candidates", return_value=[]), \
         patch("agents.ontario_law._fetch_nrcan_candidates", return_value=[]):
        survivors, counts = await fetch_ontario_law_hits(
            serpapi_client=mock_serpapi,
            anthropic_client=mock_anthropic,
            model="claude-haiku-4-5",
        )

    assert survivors == []
    assert counts["after_filter"] == 0
    assert counts["after_dedup"] == 0
    # filter was NOT called
    mock_anthropic.messages.create.assert_not_called()


# ---------------------------------------------------------------------------
# Test M — Telemetry counts in returned tuple
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_telemetry_counts_in_return_tuple():
    """fetch_ontario_law_hits returns (hits, counts) with serpapi/nrcan/after_dedup/after_filter keys."""
    import json

    serpapi_hits = [
        {"title": "Story A", "link": "https://a.com/1", "source_name": "a.com", "summary": "test A", "published_at": None},
        {"title": "Story B", "link": "https://b.com/2", "source_name": "b.com", "summary": "test B", "published_at": None},
    ]
    nrcan_hits = [
        {"title": "Story C", "link": "https://c.com/3", "source_name": "nrcan", "summary": "test C", "published_at": None},
    ]

    # All filter calls return is_law=False so after_filter=0
    filter_response = {
        "is_law": False,
        "bill_or_reg_number": None,
        "reason": "not a law",
        "favour_or_neutral": "neutral",
    }

    mock_anthropic = AsyncMock()
    mock_anthropic.messages.create = AsyncMock(
        return_value=MagicMock(
            content=[MagicMock(text=json.dumps(filter_response))]
        )
    )

    mock_serpapi = MagicMock()

    with patch("agents.ontario_law._fetch_serpapi_candidates", return_value=serpapi_hits), \
         patch("agents.ontario_law._fetch_nrcan_candidates", return_value=nrcan_hits):
        survivors, counts = await fetch_ontario_law_hits(
            serpapi_client=mock_serpapi,
            anthropic_client=mock_anthropic,
            model="claude-haiku-4-5",
        )

    # Verify all 4 telemetry keys present with correct types
    for key in ("serpapi", "nrcan", "after_dedup", "after_filter"):
        assert key in counts, f"Missing telemetry key: {key}"
        assert isinstance(counts[key], int), f"Telemetry key {key} must be int"

    assert counts["serpapi"] == 2
    assert counts["nrcan"] == 1
    assert counts["after_dedup"] == 3
    assert counts["after_filter"] == 0  # all rejected by filter


# ---------------------------------------------------------------------------
# Additional constant verification tests
# ---------------------------------------------------------------------------

def test_filter_system_prompt_contains_verbatim_reject_examples():
    """FILTER_SYSTEM_PROMPT must contain all 3 verbatim REJECT/ACCEPT examples (HIGH-1)."""
    assert "Minister speaks at mining association gala" in FILTER_SYSTEM_PROMPT
    assert "Government announces consultation on critical minerals strategy" in FILTER_SYSTEM_PROMPT
    assert "Bill 71 (Building Ontario Act) receives Royal Assent" in FILTER_SYSTEM_PROMPT
    assert "amends Mining Act sections 21-24" in FILTER_SYSTEM_PROMPT


def test_nrcan_url_exact():
    """NRCAN_ATOM_URL must be the exact locked URL from CONTEXT.md."""
    expected = (
        "https://api.io.canada.ca/io-server/gc/news/en/v2"
        "?dept=naturalresourcescanada&sort=publishedDate&orderBy=desc&pick=50&format=atom"
    )
    assert NRCAN_ATOM_URL == expected


def test_filter_body_max_chars_is_1500():
    """FILTER_BODY_MAX_CHARS must be 1500 (HIGH-2)."""
    assert FILTER_BODY_MAX_CHARS == 1500


def test_ontario_law_hit_has_reason_field():
    """OntarioLawHit (local mirror) has reason field for Phase 2 bullet rendering."""
    hit = OntarioLawHit(
        title="Test",
        link="https://x.com",
        source_name="test",
        bill_or_reg_number="Bill 71",
        reason="named bill amending Mining Act",
    )
    assert hit.reason == "named bill amending Mining Act"


def test_filter_serpapi_date_filter_constant():
    """SERPAPI_DATE_FILTER must be 'qdr:d' (24h window — CONTEXT.md D-Source-A)."""
    assert SERPAPI_DATE_FILTER == "qdr:d"
