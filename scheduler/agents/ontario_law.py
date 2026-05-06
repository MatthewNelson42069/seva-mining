"""v2.0 Phase 2 — Ontario Law ingestion + Haiku relevance filter.

Replaces the Phase 1 _build_ontario_law_section() stub in daily_summary.py.

Sources (LAW-01 — Path A, locked CONTEXT.md):
  PRIMARY:   SerpAPI keyword search (tbs=qdr:d, 24h window).
  SECONDARY: NRCan Atom feed (https://api.io.canada.ca/io-server/...).

Filter (LAW-02 — Haiku, HIGH-1/HIGH-2/HIGH-6):
  Model:        claude-haiku-4-5 (env-tunable via ONTARIO_LAW_FILTER_MODEL).
  Input:        title + first 1500 chars of body.
  Output:       {is_law: bool, bill_or_reg_number: str|null, reason: str,
                 favour_or_neutral: 'favour'|'neutral'|'against'}.
  Survival:     is_law=True AND bill_or_reg_number != null AND
                favour_or_neutral != 'against'.
  Concurrency:  asyncio.gather(*[_filter_one(c) for c in candidates]).

Resilience:
  asyncio.gather(..., return_exceptions=True) so one source failing degrades
  the section gracefully — does NOT crash the whole daily_summary fire.

Schema note:
  OntarioLawHit is mirrored locally here because the scheduler does NOT
  import from the backend package (separate pyproject.toml / venv). The
  field names are byte-identical to backend/app/schemas/daily_summary.py
  OntarioLawHit — any field change must be applied in BOTH places.
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import feedparser
import httpx
import serpapi
from anthropic import AsyncAnthropic

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Local mirror of OntarioLawHit (byte-identical fields to backend schema)
# ---------------------------------------------------------------------------

@dataclass
class OntarioLawHit:
    """Mirror of backend/app/schemas/daily_summary.py OntarioLawHit.

    Field names are byte-identical. Any change must be applied in both places.
    Phase 2 adds `reason` (optional) for markdown bullet rendering.
    """
    title: str
    link: str
    source_name: str
    bill_or_reg_number: str | None = None
    favour_or_neutral: str | None = None  # 'favour' | 'neutral' | 'against'
    reason: str | None = None  # Phase 2 — used in the markdown bullet rendering
    published_at: datetime | None = None

    def model_dump(self, *, mode: str = "python") -> dict:
        """Serialize to dict (parity with Pydantic model_dump)."""
        result = {
            "title": self.title,
            "link": self.link,
            "source_name": self.source_name,
            "bill_or_reg_number": self.bill_or_reg_number,
            "favour_or_neutral": self.favour_or_neutral,
            "reason": self.reason,
            "published_at": (
                self.published_at.isoformat() if self.published_at else None
            ) if mode == "json" else self.published_at,
        }
        return result


# ---------------------------------------------------------------------------
# Locked constants (CONTEXT.md D-Source-A, D-Filter)
# ---------------------------------------------------------------------------

NRCAN_ATOM_URL = (
    "https://api.io.canada.ca/io-server/gc/news/en/v2"
    "?dept=naturalresourcescanada&sort=publishedDate&orderBy=desc&pick=50&format=atom"
)

# CONTEXT.md D-Source-A: SerpAPI keyword query, 24h date filter
SERPAPI_QUERY = (
    '"Ontario" AND ("Mining Act" OR "Mines Act" OR "mining bill" '
    'OR "mining law" OR ("Bill" AND mining))'
)
SERPAPI_DATE_FILTER = "qdr:d"  # last 24 hours
SERPAPI_NUM_RESULTS = 25

FILTER_BODY_MAX_CHARS = 1500  # HIGH-2: pass body, but bound it
FILTER_TIMEOUT_SECONDS = 30.0  # match existing AsyncAnthropic pattern from daily_summary.py

# CONTEXT.md D-Filter-Examples — VERBATIM REJECT + ACCEPT examples (HIGH-1)
FILTER_SYSTEM_PROMPT = """\
You are a relevance filter for an Ontario mining-law news digest.

Given an article (title + body), return a structured JSON object:
{
  "is_law": true | false,
  "bill_or_reg_number": "Bill 71" | "Ontario Regulation 23/26" | null,
  "reason": "1-sentence explanation",
  "favour_or_neutral": "favour" | "neutral" | "against"
}

KEEP an article ONLY when it cites a SPECIFIC bill or regulation number AND
describes an enacted/effective law amending or affecting Ontario mining
(Mining Act, Mineral Tenure Act, Aggregate Resources Act, Crown lands, royalty
schedule, exploration permit, staking regulation, critical-minerals statute).

Required: the article must reference a specific bill number, regulation
number, or enacted/effective date for is_law=true.

REJECT examples (return is_law=false):
  1. "Minister speaks at mining association gala" -> {"is_law": false, "bill_or_reg_number": null, "reason": "ministerial speech, no enacted law", "favour_or_neutral": "neutral"}
  2. "Government announces consultation on critical minerals strategy" -> {"is_law": false, "bill_or_reg_number": null, "reason": "announcement of consultation, not a bill or law", "favour_or_neutral": "neutral"}

ACCEPT example (return is_law=true):
  3. "Bill 71 (Building Ontario Act) receives Royal Assent — amends Mining Act sections 21-24" -> {"is_law": true, "bill_or_reg_number": "Bill 71", "reason": "named bill amending Mining Act, Royal Assent received", "favour_or_neutral": "favour"}

favour_or_neutral guidance:
  "favour"  — law is mining-favourable (reduces friction, expands access, lower royalty)
  "against" — law is mining-restrictive (new fees, stricter permits, moratorium)
  "neutral" — procedural amendment, technical correction, jurisdictional housekeeping

Reply with ONLY the compact JSON object. No prose, no markdown fences.
"""


# ---------------------------------------------------------------------------
# Source fetchers (LAW-01)
# ---------------------------------------------------------------------------

async def _fetch_serpapi_candidates(client: serpapi.Client) -> list[dict]:
    """Fetch up to SERPAPI_NUM_RESULTS hits with 24h date filter (qdr:d)."""
    loop = asyncio.get_event_loop()

    def _call() -> Any:
        return client.search({
            "engine": "google_news",
            "q": SERPAPI_QUERY,
            "tbs": SERPAPI_DATE_FILTER,
            "num": SERPAPI_NUM_RESULTS,
        })

    results = await loop.run_in_executor(None, _call)
    out: list[dict] = []
    for item in (results.get("news_results") or [])[:SERPAPI_NUM_RESULTS]:
        out.append({
            "title": item.get("title", "") or "",
            "link": item.get("link", "") or "",
            "source_name": ((item.get("source") or {}).get("name") or "serpapi"),
            "summary": item.get("snippet", "") or "",
            "published_at": _parse_serpapi_date(item.get("date")),
        })
    return out


def _parse_serpapi_date(raw: str | None) -> datetime | None:
    """Defensively parse SerpAPI date strings — same pattern as content_agent."""
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        try:
            return datetime.strptime(raw, "%m/%d/%Y, %I:%M %p, +0000 UTC").replace(
                tzinfo=timezone.utc
            )
        except (ValueError, TypeError):
            return None


async def _fetch_nrcan_candidates() -> list[dict]:
    """Fetch + parse the NRCan Atom feed. Body comes from atom <summary>/<content>."""
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        resp = await client.get(
            NRCAN_ATOM_URL,
            headers={"User-Agent": "Mozilla/5.0 SevaBot/1.0"},
        )
        resp.raise_for_status()
        atom_text = resp.text

    loop = asyncio.get_event_loop()
    feed = await loop.run_in_executor(None, feedparser.parse, atom_text)
    out: list[dict] = []
    for entry in feed.entries[:50]:
        published_parsed = entry.get("published_parsed") or entry.get("updated_parsed")
        published = (
            datetime(*published_parsed[:6], tzinfo=timezone.utc)
            if published_parsed
            else None
        )
        out.append({
            "title": entry.get("title", "") or "",
            "link": entry.get("link", "") or "",
            "source_name": "naturalresourcescanada",
            "summary": entry.get("summary", "") or entry.get("description", "") or "",
            "published_at": published,
        })
    return out


# ---------------------------------------------------------------------------
# Dedup + filter (LAW-02)
# ---------------------------------------------------------------------------

def _dedup_by_url(candidates: list[dict]) -> list[dict]:
    """Remove duplicate candidates by URL (first occurrence wins)."""
    seen: set[str] = set()
    out: list[dict] = []
    for c in candidates:
        url = c.get("link", "")
        if not url or url in seen:
            continue
        seen.add(url)
        out.append(c)
    return out


async def _filter_one(
    client: AsyncAnthropic,
    *,
    model: str,
    title: str,
    body: str,
) -> dict:
    """Run the Haiku relevance filter on one candidate. Returns the parsed JSON dict.

    Fail-closed on parse errors (returns is_law=false) — better to drop a real
    hit silently than to surface a false positive whose JSON we can't trust.

    Filter input: title + first 1500 chars of body (HIGH-2: include body for
    bills with opaque names like 'Building Ontario Act' that amend Mining Act).
    """
    truncated_body = (body or "")[:FILTER_BODY_MAX_CHARS]
    user_message = (
        f"Title: {title}\n\n"
        f"Body (first {FILTER_BODY_MAX_CHARS} chars):\n{truncated_body}"
    )
    try:
        response = await client.messages.create(
            model=model,
            max_tokens=200,
            system=FILTER_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        raw = response.content[0].text.strip()
        # Strip markdown fences defensively (Haiku usually doesn't, but be safe)
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.rsplit("```", 1)[0].strip()
        parsed = json.loads(raw)
    except Exception as exc:  # noqa: BLE001 — fail-closed
        logger.warning(
            "ontario_law filter parse failure on '%s' (%s) — fail-closed (rejecting)",
            (title or "")[:60],
            type(exc).__name__,
        )
        return {
            "is_law": False,
            "bill_or_reg_number": None,
            "reason": "parse_error",
            "favour_or_neutral": "neutral",
        }

    return {
        "is_law": bool(parsed.get("is_law", False)),
        "bill_or_reg_number": parsed.get("bill_or_reg_number") or None,
        "reason": str(parsed.get("reason", ""))[:300],
        "favour_or_neutral": str(parsed.get("favour_or_neutral", "neutral")).lower(),
    }


def _survives(filter_result: dict) -> bool:
    """LAW-02 survival rule (CONTEXT.md D-Survival).

    is_law=True AND bill_or_reg_number != null AND favour_or_neutral != 'against'.
    Items with 'against' are excluded — we surface mining-favourable laws only.
    """
    return bool(
        filter_result.get("is_law") is True
        and filter_result.get("bill_or_reg_number") is not None
        and filter_result.get("favour_or_neutral") != "against"
    )


# ---------------------------------------------------------------------------
# Orchestrator (called from daily_summary.py)
# ---------------------------------------------------------------------------

async def fetch_ontario_law_hits(
    *,
    serpapi_client: serpapi.Client | None,
    anthropic_client: AsyncAnthropic,
    model: str,
) -> tuple[list[OntarioLawHit], dict[str, int]]:
    """Run the full Phase 2 ingestion pipeline.

    Returns (survivors, counts) where counts has keys:
      serpapi, nrcan, after_dedup, after_filter

    LAW-01: 2 sources via asyncio.gather(return_exceptions=True).
    LAW-02: parallel Haiku filter via asyncio.gather, body included.
    LAW-03/04: caller (daily_summary._build_ontario_law_section) renders the bullets.
    """
    counts: dict[str, int] = {
        "serpapi": 0,
        "nrcan": 0,
        "after_dedup": 0,
        "after_filter": 0,
    }

    if serpapi_client is None:
        # No SerpAPI credentials available; fall through to NRCan only.
        serpapi_task: Any = _empty_list_coro()
    else:
        serpapi_task = _fetch_serpapi_candidates(serpapi_client)

    serpapi_result, nrcan_result = await asyncio.gather(
        serpapi_task,
        _fetch_nrcan_candidates(),
        return_exceptions=True,  # CONTEXT.md D-Resilience
    )

    serpapi_cands: list[dict] = []
    nrcan_cands: list[dict] = []
    if isinstance(serpapi_result, Exception):
        logger.warning(
            "ontario_law: SerpAPI source failed (%s)", type(serpapi_result).__name__
        )
    else:
        serpapi_cands = serpapi_result or []
    if isinstance(nrcan_result, Exception):
        logger.warning(
            "ontario_law: NRCan source failed (%s)", type(nrcan_result).__name__
        )
    else:
        nrcan_cands = nrcan_result or []

    counts["serpapi"] = len(serpapi_cands)
    counts["nrcan"] = len(nrcan_cands)

    deduped = _dedup_by_url(serpapi_cands + nrcan_cands)
    counts["after_dedup"] = len(deduped)

    if not deduped:
        return ([], counts)

    # Parallel filter — bounded by per-call timeout=30s in the AsyncAnthropic client.
    filter_results = await asyncio.gather(
        *[
            _filter_one(
                anthropic_client,
                model=model,
                title=c.get("title", ""),
                body=c.get("summary", ""),
            )
            for c in deduped
        ],
        return_exceptions=True,
    )

    survivors: list[OntarioLawHit] = []
    for cand, fr in zip(deduped, filter_results):
        if isinstance(fr, Exception):
            logger.warning(
                "ontario_law: filter call raised on '%s' (%s)",
                (cand.get("title") or "")[:60],
                type(fr).__name__,
            )
            continue
        if not _survives(fr):
            continue
        survivors.append(
            OntarioLawHit(
                title=cand.get("title", ""),
                link=cand.get("link", ""),
                source_name=cand.get("source_name", ""),
                bill_or_reg_number=fr.get("bill_or_reg_number"),
                favour_or_neutral=fr.get("favour_or_neutral"),
                reason=fr.get("reason"),
                published_at=cand.get("published_at"),
            )
        )

    counts["after_filter"] = len(survivors)
    return (survivors, counts)


async def _empty_list_coro() -> list:
    """Return empty list — used when serpapi_client is None."""
    return []
