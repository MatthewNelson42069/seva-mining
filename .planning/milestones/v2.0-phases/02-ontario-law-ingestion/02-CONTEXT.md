# Phase 2: Ontario Law Ingestion - Context

**Gathered:** 2026-04-27
**Status:** Ready for planning
**Mode:** Smart-discuss (autonomous), build-time source verification complete, Path A locked

<domain>
## Phase Boundary

Replace the Phase 1 Ontario Law section stub with a real ingestion pipeline. Each daily_summary fire (08:00 PT + 12:00 PT) ingests candidate Ontario/Canadian mining law items, filters them through a Haiku relevance filter, and produces a markdown section listing surviving hits OR an empty-state with `last_known_law` continuity.

**In scope:**
- New module: `scheduler/agents/ontario_law.py` exposing `fetch_ontario_law_hits()` → `list[OntarioLawHit]`
- 2 ingestion sources, fetched concurrently:
  - **Primary:** SerpAPI keyword search (`"Ontario" AND ("Mining Act" OR "Mines Act" OR "mining bill" OR "mining law" OR "Bill" mining)` with 24h date window)
  - **Secondary:** NRCan Atom feed via `https://api.io.canada.ca/io-server/gc/news/en/v2?dept=naturalresourcescanada&sort=publishedDate&orderBy=desc&pick=50&format=atom`
- Haiku relevance filter (`claude-haiku-4-5`) returning structured JSON `{is_law: bool, bill_or_reg_number: str|null, reason: str, favour_or_neutral: 'favour'|'neutral'|'against'}`. Filter prompt MUST include explicit REJECT examples (ministerial speeches, CTA announcements without a named bill).
- Wire `_build_ontario_law_section()` in `scheduler/agents/daily_summary.py` (replacing the stub from Phase 1)
- Persist most recent passing hit in `daily_summaries.raw_sources_jsonb.ontario_law.last_known_law` for empty-state continuity
- New env config: `ONTARIO_LAW_FILTER_MODEL` (default `"claude-haiku-4-5"`) in BOTH `scheduler/config.py` AND `backend/app/config.py` for parity (single-line tunable)
- Tests: synthetic positive case ("Building Ontario Act amends Mining Act"), synthetic REJECT case (ministerial speech), end-to-end with mocked sources, empty-state continuity test

**Out of scope:**
- Ontario Newsroom RSS (DOES NOT EXIST — verified at build time, JS SPA with no public feed)
- OMA RSS (returns 404)
- Mining Association of Canada feed (site doesn't respond)
- OLA bill tracker (403 on direct GET)
- Ontario Stats section (Phase 3)
- Cross-summary continuity for the law section (deferred to v2.1+ if useful)

**Requirements covered (4):** LAW-01, LAW-02, LAW-03, LAW-04

</domain>

<decisions>
## Implementation Decisions

### Source Strategy (Path A — User Locked 2026-04-27)

**Build-time verification proved Ontario Newsroom RSS does NOT exist** — the entire `news.ontario.ca` site is a JavaScript SPA with no `<link rel="alternate" type="application/rss+xml">` element and no documented feed endpoint. All candidate URLs return the same 1505-byte HTML shell.

LAW-01 implementation deviates from the requirement text. The original text said "Ontario Newsroom RSS (primary), NRCan RSS (secondary), and a SerpAPI keyword search (tertiary)" — this is impossible. The new source list is:

- **PRIMARY: SerpAPI keyword search.** Query: `"Ontario" AND ("Mining Act" OR "Mines Act" OR "mining bill" OR "mining law" OR ("Bill" AND mining))` with `tbs=qdr:d` (last 24h). Fetch up to 25 results per fire. ~10 calls/day (2 fires × ~5 keyword variants), well within SerpAPI quota.
- **SECONDARY: NRCan Atom feed** at `https://api.io.canada.ca/io-server/gc/news/en/v2?dept=naturalresourcescanada&sort=publishedDate&orderBy=desc&pick=50&format=atom`. Fetched once per fire. Verified: HTTP 200, valid Atom XML, ~8.3 KB, 50 entries. Stable, documented, zero auth.

The two sources fetch CONCURRENTLY via `asyncio.gather`. Combined results dedup by URL before passing to the Haiku filter.

### Haiku Relevance Filter

- **Model:** `claude-haiku-4-5` (locked in research SUMMARY.md). Configurable via `ONTARIO_LAW_FILTER_MODEL` env var for safe model rolls.
- **Output schema (verbatim):** `{"is_law": bool, "bill_or_reg_number": str|null, "reason": str, "favour_or_neutral": "favour"|"neutral"|"against"}`. Must round-trip via Pydantic.
- **REJECT examples in prompt** (mandatory — addresses HIGH-1):
  1. *"Minister speaks at mining association gala"* → `{"is_law": false, "bill_or_reg_number": null, "reason": "ministerial speech, no enacted law", "favour_or_neutral": "neutral"}`
  2. *"Government announces consultation on critical minerals strategy"* → `{"is_law": false, "bill_or_reg_number": null, "reason": "announcement of consultation, not a bill or law", "favour_or_neutral": "neutral"}`
  3. *"Bill 71 (Building Ontario Act) receives Royal Assent — amends Mining Act sections 21-24"* → `{"is_law": true, "bill_or_reg_number": "Bill 71", "reason": "named bill amending Mining Act, Royal Assent received", "favour_or_neutral": "favour"}`
- **Input to filter:** title + first 1500 chars of body (article text or atom summary). Body is essential — bills with non-obvious names (e.g. "Building Ontario Act" amending the Mining Act) are easy false-negatives without it.
- **Concurrency:** filter ALL candidates in parallel via `asyncio.gather`. Each call has the per-request timeout=30s pattern from kro. With ~25 candidates, total ≤ 30s wall-clock.
- **Survival rule:** `is_law=True AND bill_or_reg_number != null AND favour_or_neutral != "against"`. Items with `favour_or_neutral="against"` are excluded (we surface mining-favourable laws only per REQUIREMENTS.md text).

### Markdown Output

- Each surviving hit renders as one bullet:
  - `**{bill_or_reg_number}** — {reason}` (markdown bold for the bill number, em-dash separator, 1-sentence summary)
- Section heading "Ontario Law" is added by the SectionBlock component on the frontend (don't repeat in the markdown body).
- If no hits survive, the markdown body is the empty-state copy (from REQUIREMENTS.md LAW-04 verbatim): `No new Ontario mining-related laws today. Last update: {date} — {law_name}.` where `{date}` and `{law_name}` come from `last_known_law` JSONB. If `last_known_law` is null (first-ever fire with no hits), fallback: `No new Ontario mining-related laws today.`

### Empty-State Continuity (`last_known_law`)

- Stored at `daily_summaries.raw_sources_jsonb.ontario_law.last_known_law` per the existing `RawSources` Pydantic model.
- Shape: `{"date": "YYYY-MM-DD", "law_name": "Bill 71 (Building Ontario Act)", "url": "https://..."}` — define a `LastKnownLaw` Pydantic model in `backend/app/schemas/daily_summary.py` and add it to `OntarioLawState`.
- Updated whenever a fire produces ≥1 surviving hit (use the highest-priority hit — first one in the list).
- Preserved across fires with no hits: each fire reads the previous summary's `last_known_law` and propagates it forward.

### Cross-Module Wiring

- `scheduler/agents/daily_summary.py` — replace the `_build_ontario_law_section()` stub from Phase 1 with a real implementation that:
  1. Calls `fetch_ontario_law_hits()` to get filtered survivors
  2. If survivors → render bullets, update `raw_sources.ontario_law.last_known_law`, return markdown
  3. If no survivors → read previous summary's `last_known_law` from the most recent `daily_summaries` row, render empty-state, propagate `last_known_law` to current row's JSONB
- The previous-summary read is a single SELECT on `daily_summaries` ordered by `generated_at DESC LIMIT 1` (no transaction — eventually-consistent read is fine).

### Telemetry

`agent_runs.notes` already has `candidates_law` and `sections_completed` keys from Phase 1's SUM-04. Phase 2 adds:
- `candidates_law_serpapi`: int (raw SerpAPI count)
- `candidates_law_nrcan`: int (raw NRCan count)
- `candidates_law_after_dedup`: int
- `candidates_law_after_filter`: int (i.e. survivors)

These nest under the existing `notes` JSONB without schema migration.

### Test Strategy

- **Synthetic positive:** Pass `{"title": "Building Ontario Act amends Mining Act", "body": "Bill 71 received Royal Assent yesterday..."}` through the filter. Assert `is_law=True`, `bill_or_reg_number="Bill 71"`. (Uses real Haiku call gated by `ANTHROPIC_API_KEY` env — skip if env is missing in CI.)
- **Synthetic REJECT:** Pass `{"title": "Minister gives speech at OMA", "body": "Today the Minister of Mines spoke at..."}`. Assert `is_law=False`.
- **End-to-end with mocks:** Mock SerpAPI + httpx clients to return canned data; assert the daily_summary section ends up with the expected bullets.
- **Empty-state continuity:** Mock both ingestion sources to return zero candidates. Run on a fresh DB → assert empty-state without `last_known_law`. Run again with a previous summary that has `last_known_law` → assert empty-state with continuity copy.
- **No regression:** All 237 scheduler tests from Phase 1 still pass.

### Cross-cutting (locked from research, not re-decided here)

- Sources fetched CONCURRENTLY via `asyncio.gather` (not sequential)
- Per-Anthropic-call timeout=30s (kro pattern)
- Anthropic SDK from existing scheduler client
- httpx for the NRCan Atom fetch (existing dep)
- `feedparser` for parsing the Atom XML (existing dep)
- SerpAPI client from existing scheduler module
- Module style: pure functions where possible, classes only when state is needed
- Tests in `scheduler/tests/agents/test_ontario_law.py` (mirrors existing `tests/agents/test_daily_summary.py` from Phase 1)
- Ruff clean; pytest -x green

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets

- `scheduler/agents/daily_summary.py` — has the stub `_build_ontario_law_section()` placeholder from Phase 1. Replace its body in this phase.
- `scheduler/agents/content_agent.py` — uses SerpAPI client (`serpapi.Client`) and shows the search pattern; also shows the `feedparser.parse()` + httpx fetch pattern for RSS.
- `scheduler/services/anthropic_client.py` (or wherever the AsyncAnthropic singleton lives) — already has `timeout=30.0`. Reuse for the Haiku filter.
- `backend/app/schemas/daily_summary.py` — has `OntarioLawState` and `OntarioLawHit` Pydantic models. Extend with `LastKnownLaw`.
- `scheduler/models/daily_summary.py` — DailySummary ORM model. The `raw_sources_jsonb` column accepts arbitrary JSON; Pydantic validates the shape on write.

### Established Patterns

- **Concurrent fetching:** `asyncio.gather(fetch_serpapi(), fetch_nrcan())` returns both results; if either raises, use `return_exceptions=True` and degrade gracefully (one source failure ≠ section failure).
- **Filter parallelism:** `asyncio.gather(*[filter_one(c) for c in candidates])` — each call uses the kro 30s per-request Anthropic timeout.
- **Pydantic JSON validation:** `RawSources(...).model_dump_json()` on write, `RawSources.model_validate_json(row.raw_sources_jsonb)` on read.
- **Section orchestration:** `daily_summary.py`'s `run_daily_summary()` already calls 3 section builders. Just upgrade builder #2 from stub to real.
- **Empty-state continuity:** Phase 1 already established the JSONB shape. Phase 2 wires the `last_known_law` propagation logic.

### Integration Points

- `scheduler/config.py`: add `ontario_law_filter_model: str = "claude-haiku-4-5"`. Mirror in `backend/app/config.py`.
- `scheduler/agents/daily_summary.py:_build_ontario_law_section()`: replace body. Signature stays the same so call site in `run_daily_summary()` doesn't change.
- `scheduler/agents/ontario_law.py`: NEW file. Exports `fetch_ontario_law_hits(serpapi_client, anthropic_client) -> list[OntarioLawHit]` and supporting helpers (`_fetch_serpapi_candidates`, `_fetch_nrcan_candidates`, `_dedup_by_url`, `_filter_one`).
- `scheduler/tests/agents/test_ontario_law.py`: NEW file. Mirrors `test_daily_summary.py` structure.
- `backend/app/schemas/daily_summary.py`: extend `OntarioLawState` with `last_known_law: LastKnownLaw | None`.
- No DB migration needed — JSONB schema is open-ended; Pydantic enforces shape on write.

</code_context>

<specifics>
## Specific Ideas

- **SerpAPI quota math:** ~10 searches/day × 30 days = 300/month, plus some breathing room for retries. Existing SerpAPI plan is $50/month for 5,000 searches. Phase 2 uses ~6% of quota.
- **NRCan feed update cadence:** The feed shows new releases daily on weekdays. ~5 fresh entries per week is realistic. Most Ontario provincial mining laws will NOT appear here (federal department) — but cross-jurisdictional bills (e.g., federal Critical Minerals Strategy) will.
- **Haiku cost math:** ~25 candidates × 2 fires/day × 30 days = 1500 Haiku calls/month. At ~$0.001/call (input+output), that's $1.50/month. Negligible.
- **NRCan API note:** the `<link href="http://localhost:8181/...">` self-link in the Atom output is an upstream serialization artifact — ignore it. The feed itself is correctly hosted at the public URL.

</specifics>

<deferred>
## Deferred Ideas

- **OLA bill tracker scraping** — 403 on direct GET. Could add a Selenium/Playwright-based scraper later if SerpAPI coverage proves insufficient. Defer until evidence justifies the complexity.
- **Ontario Mining Association RSS** — `oma.on.ca/feed` returned 404. Defer; revisit if/when they expose a feed.
- **Mining Association of Canada** — site offline. Defer indefinitely.
- **CSC-01 for the law section** — passing the morning's law hits into the noon Sonnet context — not in Phase 2 scope. The law section is a list (not narrative prose), so cross-summary continuity adds little value.
- **Custom keyword tuning UI** — locked in v2.0 Out of Scope; the SerpAPI keyword set is a constant in `ontario_law.py`, not a settings-page knob.

</deferred>
