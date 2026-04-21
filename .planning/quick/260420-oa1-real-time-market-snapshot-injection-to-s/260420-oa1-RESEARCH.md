# Quick 260420-oa1 — Real-time Market Snapshot Injection

**Researched:** 2026-04-20
**Domain:** Financial data APIs + LLM prompt-grounding
**Confidence:** HIGH on FRED + metals choice; MEDIUM on DXY; HIGH on prompt pattern

---

## User Constraints (from preceding operator turn)

### Locked Decisions
- Scope: content agent only (Twitter agent is separate task)
- Cadence: refresh per content_agent cron cycle (every 3h) — no per-draft fetches
- Storage: new `market_snapshots` table (DB-cached, survives restarts)
- Injection: drafter system prompt gets `CURRENT MARKET SNAPSHOT (as of <UTC>)` block + hard instruction "only cite figures that appear here; otherwise use qualitative language; do not invent numbers"
- Fallback: on fetch failure, inject `[UNAVAILABLE]` placeholders (do not skip draft) — drafter forced into qualitative mode
- Budget: free preferred, ≤$10/mo acceptable

### Claude's Discretion
- Which specific APIs to pick
- Whether DXY is worth including
- Aggregator shape (single fn vs. parallel gather)

### Deferred Ideas (OUT OF SCOPE)
- Post-hoc structured-output hallucination validators
- Twitter-agent snapshot injection
- Per-draft fetches
- Skip-draft-on-failure

---

## Summary

Use **two free APIs in parallel** every 3h:

1. **FRED API** (Federal Reserve St. Louis) — macro stack: 10Y nominal, 10Y real, Fed funds, CPI. Free, instant key, 120 req/min, rock-solid schema, official government data source.
2. **metalpriceapi.com** on the $8.99/mo **Basic** plan (10k req/mo, 10-min updates) — spot gold (XAU) + silver (XAG). Free tier is 100 req/mo which is borderline tight at 8 runs/day × 30 = 240 fetches; paid is within the ≤$10/mo budget and buys reliability + 60s freshness.

**Skip DXY.** FRED's `DTWEXBGS` is trade-weighted, not ICE DXY — different number, would confuse a senior-analyst tone. yfinance for `DX-Y.NYB` is a scraping dependency that's repeatedly broken in 2024-2025. Better to use qualitative language ("dollar strength," "dollar softening") derived from real 10Y real yields and Fed funds positioning — the drafter has those numbers to reason from.

**Architecture:** single `async def fetch_market_snapshot() -> dict` using `asyncio.gather` with per-source `try/except`, each source has its own 10s httpx timeout. On any one source failing, that slice of the dict is `None` and the injection helper renders `[UNAVAILABLE]` for those keys. Persist to new `market_snapshots` table immediately after fetch; content agent reads latest row (not in-memory state) at draft time.

**Primary recommendation:** Wire `MarketSnapshotFetcher` as a module in `scheduler/services/market_snapshot.py`, call it at the very top of `ContentAgent._run_pipeline`, persist the row, then read it just before building each Sonnet prompt in `_research_and_draft`. Inject as a block at the top of the system prompt, just after the senior-analyst preamble and before the "you never mention Seva Mining" line.

**Estimated monthly cost delta:** +$8.99/mo (metalpriceapi Basic). FRED is free. Total content-agent API surface becomes: Anthropic + SerpAPI + X API + FRED + metalpriceapi.

---

## API Evaluation Matrix

| API | Coverage | Free tier | Paid | Reliability | Python fit | Verdict |
|---|---|---|---|---|---|---|
| **FRED (fred.stlouisfed.org)** | 10Y nominal (DGS10), 10Y real (DFII10), Fed funds daily (DFF) + monthly (FEDFUNDS), CPI (CPIAUCSL), trade-wtd dollar (DTWEXBGS) | Free, 120 req/min, instant key | N/A | HIGH — official Fed, gov-grade uptime | `fredapi` (sync, OK via `run_in_executor`) or httpx-direct | **RECOMMENDED** — macro stack |
| **metalpriceapi.com** | Gold, silver, platinum, palladium spot (USD) | 100 req/mo (daily updates only) — too tight | $8.99/mo Basic: 10k req/mo, 10-min updates | HIGH — multi-source aggregator w/ correction | `metalpriceapi-python` SDK, or httpx-direct | **RECOMMENDED** — metals |
| gold-api.com | XAU, XAG — confirmed live ~$4820/oz, no auth, no rate limits claimed | Free, unlimited | N/A | MEDIUM — unclear data provenance, thin docs, single-dev project; "fallback to next source" language suggests scraping layer | httpx-direct (single GET) | **Viable free fallback** if metalpriceapi budget is denied — but schema and uptime are untested at our cadence |
| omkarcloud gold-price-api | Gold futures (CME GC) — not spot | 5k req/mo free | N/A | LOW — single-repo, no SLA | httpx-direct | **SKIP** — futures ≠ spot, and 5k/mo is the same ceiling as a $9 plan with worse reliability |
| GoldAPI.io / GoldAPI.net | Gold, silver, platinum | 100 req/mo | $25+/mo | MEDIUM | httpx-direct | SKIP — over budget |
| Metals-API.com | Gold, silver, 15+ sources | 100 req/mo (commercial use excluded) | Higher tiers pricey | MEDIUM | httpx-direct | SKIP — free tier is non-commercial |
| metals.dev | Gold, silver, plat, palladium | 100 req/mo, 60s updates | Cheaper tiers but verify | HIGH | httpx-direct | Honourable mention — similar to metalpriceapi, slightly worse docs |
| Alpha Vantage | Commodities incl. gold (monthly WTI etc.) | 25 req/**day** (hard cap, confirmed 2025) | $50+/mo | MEDIUM | `alpha_vantage` pkg | SKIP — 25/day is below our 8/day cadence × multiple endpoints |
| yfinance | Gold futures (GC=F), silver (SI=F), DX-Y.NYB, ^TNX | Free | N/A | **LOW** — Yahoo scraping. Repeatedly 429-blacklisted in 2024-2025. HTML changes break the lib silently. Multiple dev-blog warnings. | `yfinance` pkg (sync) | **SKIP** — operator-locked "reliable" requirement rules this out |
| Finnhub | Metals via symbols (OANDA:XAUUSD) | 60 req/min free but metals are **premium-only** | $50+/mo for metals | HIGH | `finnhub-python` | SKIP — metals gated behind paid |
| stooq.com CSV | Gold, silver, DXY, yields — wide coverage | Free CSV | N/A | LOW for programmatic — pandas-datareader commodities integration broken since late 2021, ~15min delayed | `pd.read_csv(url)` direct | **SKIP** — fragile, commodities endpoint has a track record of breaking |

**Bottom line on metals source:** metalpriceapi $8.99/mo is the cleanest answer. If operator wants truly-zero additional spend, the **gold-api.com** free endpoint (no auth, no rate limits) is viable but untested — add it as the current-cycle fallback and plan for a swap if it flakes.

---

## Python Integration Notes

### FRED (RECOMMENDED: httpx-direct, skip `fredapi` package)

`fredapi` is sync-only and wraps a handful of endpoints we don't need. For 5 series, httpx-direct is ~15 lines and plays natively with the existing async architecture:

```python
# scheduler/services/market_snapshot.py (pseudocode)
FRED_SERIES = {
    "ust_10y_nominal":   "DGS10",     # daily, %
    "ust_10y_real":      "DFII10",    # daily, % (10Y TIPS)
    "fed_funds":         "DFF",       # daily, %
    "cpi_yoy":           "CPIAUCSL",  # monthly, index — compute YoY in code
}

async def _fetch_fred_series(client: httpx.AsyncClient, series_id: str, api_key: str) -> dict | None:
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "sort_order": "desc",
        "limit": 2,  # for YoY diff on CPI we need 2 points, 1 for rates
    }
    try:
        r = await client.get(url, params=params, timeout=10.0)
        r.raise_for_status()
        obs = r.json().get("observations", [])
        return {"observations": obs}  # caller parses series-specific shape
    except Exception:
        return None
```

- **Package:** none beyond `httpx` (already a dep).
- **Env var:** `FRED_API_KEY` — add to `scheduler/config.py` as `Optional[str] = None`. Fail-soft if missing (snapshot renders `[UNAVAILABLE]` for all FRED series).
- **Response schema:** `{"observations": [{"date": "2026-04-18", "value": "4.21"}, ...]}`. Stable since 2012. `value` can be `"."` for missing data — guard against that.

### metalpriceapi.com (RECOMMENDED: httpx-direct, skip SDK)

The `metalpriceapi-python` SDK is a thin wrapper. httpx-direct keeps the dep tree clean:

```python
async def _fetch_metals(client: httpx.AsyncClient, api_key: str) -> dict | None:
    url = "https://api.metalpriceapi.com/v1/latest"
    params = {"api_key": api_key, "base": "USD", "currencies": "XAU,XAG"}
    try:
        r = await client.get(url, params=params, timeout=10.0)
        r.raise_for_status()
        data = r.json()
        # Response: {"rates": {"USDXAU": 0.000207, ...}} — rate is USD per 1 metal unit.
        # Price per oz = 1 / rate.
        rates = data.get("rates", {})
        gold = 1 / rates["USDXAU"] if rates.get("USDXAU") else None
        silver = 1 / rates["USDXAG"] if rates.get("USDXAG") else None
        return {"gold_usd_per_oz": gold, "silver_usd_per_oz": silver, "timestamp": data.get("timestamp")}
    except Exception:
        return None
```

- **Package:** none beyond `httpx`.
- **Env var:** `METALPRICEAPI_API_KEY` — add to `scheduler/config.py` as `Optional[str] = None`.
- **Important gotcha:** the `rates` object returns **USD per 1 XAU** as a reciprocal (i.e., 0.000207) — you must invert to get `USD per oz`. Test this at integration time; easy off-by-reciprocal bug.

### gold-api.com fallback shape (if operator rejects paid)

No API key. URL pattern per docs: `https://api.gold-api.com/price/XAU` returns `{"name": "Gold", "price": 4820.80, "symbol": "XAU", "updatedAt": "..."}`. Single GET. Same httpx-direct shape. Add as a secondary fetcher that runs only when `METALPRICEAPI_API_KEY` is unset.

### Aggregator shape

```python
async def fetch_market_snapshot() -> dict:
    settings = get_settings()
    async with httpx.AsyncClient() as client:
        fred_tasks = [
            _fetch_fred_series(client, sid, settings.fred_api_key)
            for sid in FRED_SERIES.values()
        ] if settings.fred_api_key else []
        metals_task = _fetch_metals(client, settings.metalpriceapi_api_key) \
            if settings.metalpriceapi_api_key else None

        results = await asyncio.gather(
            *fred_tasks,
            metals_task if metals_task else asyncio.sleep(0, result=None),
            return_exceptions=False,  # inner try/except already handles
        )
    # Parse results into flat snapshot dict, None per missing slice → "[UNAVAILABLE]" at render time.
    return snapshot
```

No rate-limit concerns: FRED 120 req/min vs. our 5 calls every 3h is 4 orders of magnitude below ceiling. metalpriceapi Basic 10k/mo vs. our 8 × 30 = 240 calls/mo is ~40x headroom. (If operator adds the Twitter agent later at 2h cadence, total is still well under.)

---

## FRED API Specifics

| Item | Value |
|---|---|
| Key provisioning | Free, self-serve at `https://fred.stlouisfed.org/docs/api/api_key.html`. Requires a fredaccount login (instant email signup). Key issued immediately, no human approval. **HIGH confidence** — multiple sources confirm, no hold queue. |
| Rate limit | 120 req/min per key. **HIGH confidence** — documented by FRED and confirmed across `fredapi`, `fedfred`, and `fredr` R package docs. |
| Auth | `api_key=<key>` query-string param. No OAuth. |
| Response format | JSON when `file_type=json`. Stable schema since 2012. |
| Confirmed series IDs (MEDIUM-HIGH — verified against FRED series search) | `DGS10` ✓ — 10Y Treasury Constant Maturity (daily, %). `DFII10` ✓ — 10Y Treasury Inflation-Indexed (daily, real %). `DFF` ✓ — Federal Funds Effective Rate (daily). `FEDFUNDS` ✓ — Federal Funds Effective Rate (monthly). `CPIAUCSL` ✓ — CPI All Urban Consumers (monthly, index — must compute YoY from 2 observations). `DTWEXBGS` ✓ — Trade-Weighted USD Index, Broad Goods+Services (daily, **NOT the ICE DXY**). |
| **Refresh cadence awareness** | DGS10, DFII10, DFF are daily but only update on US business days. Weekend cron runs will get Friday's value — acceptable. CPIAUCSL is **monthly** and released mid-month — expect 2-6 week lag; the value doesn't change per-cycle, so injecting a stale CPI is fine (CPI is always a backward-looking print anyway). |
| Python SDK recommendation | `fredapi` is sync and adds no value for 5 series — **use httpx-direct**. `fedfred` is async but the wrapper adds indirection for a 1-endpoint API. |

**Action:** Operator creates a free FRED account at `fredaccount.stlouisfed.org`, copies the key from the API Keys page, sets `FRED_API_KEY` in Railway. No approval delay.

---

## Pitfalls (top 5)

1. **metalpriceapi reciprocal rate trap.** Response gives `USDXAU=0.000207` not `4830.00`. Invert in code; write a unit test with a canned response. If the bundle system prompt ever ships with `gold_usd_per_oz: 0.000207`, the drafter will produce nonsense grounded in nonsense — worse than hallucination.

2. **CPI non-update silent staleness.** CPI is monthly. Your 3h cron will re-fetch the same value 240 times/month. Make sure the `market_snapshots` row stores the FRED observation date alongside the value, and render it as `CPI YoY: 3.2% (as of March 2026 print)` in the prompt — the drafter needs to know how old the number is so it won't cite it as "today's CPI."

3. **FRED returns `"."` for missing observations.** The `value` field is a string, and missing data is literally `"."`. Guard on parse — `float(v) if v != "." else None`. If a series just had a holiday and returns `.`, fall back to the 2nd-most-recent observation (`limit=2` already covers this).

4. **DB row bloat / migration ordering.** Adding `market_snapshots` is migration `0007_add_market_snapshots.py`. Schema: `(id PK uuid, fetched_at TIMESTAMPTZ, fred_data JSONB, metals_data JSONB, errors JSONB)`. Add before deploy, not after — otherwise scheduler will crash at startup on `Table 'market_snapshots' doesn't exist` when the new code queries it. Keep the last 30 days only (add a TTL cleanup to a future quick task — out of scope here).

5. **Drafter still hallucinates historical context despite real current numbers.** Operator's screenshotted bug was "$3500/oz in 2025" — that's a *historical claim*, not a current one. Injecting today's snapshot fixes the "what is gold right now" axis but doesn't fix "when did gold first hit $3000." The system prompt instruction must explicitly forbid historical numeric claims too: *"Only cite figures that appear in the CURRENT MARKET SNAPSHOT block. For any other quantitative claim — historical, forward, or comparative — use qualitative language ('record highs,' 'multi-decade lows,' 'roughly triple its 2020 level'). Do not invent numbers. Do not cite 'as of 2024' or similar dated historical values."*

---

## Prompt-Injection Pattern

Anthropic's official hallucination-reduction playbook (from their prompt engineering course and Claude 4 best-practices docs) maps cleanly to this problem:

1. **Ground in explicit context** (the snapshot block is the ground truth)
2. **Give Claude an "out"** — permit "I don't have that figure" rather than inventing
3. **Quote-first workflow** — cite from the block, don't paraphrase

### Recommended block structure

Insert at the top of the Sonnet system prompt in `_research_and_draft` (and later: `_draft_video_caption`, `_draft_quote_post` — out of scope this task but plan for reuse):

```
CURRENT MARKET SNAPSHOT (as of 2026-04-20 14:00 UTC)

Spot gold:         $4,820.80 / oz
Spot silver:       $42.15 / oz
US 10Y nominal:    4.21%
US 10Y real:       1.87%
Fed funds (eff):   4.33%
CPI YoY:           3.2% (March 2026 print)

RULES FOR USING THESE NUMBERS
- You may cite any figure above verbatim, with its "as of" date.
- For ANY other quantitative claim — historical prices, prior-year levels, forward
  forecasts, multi-year comparisons — use qualitative language only. Examples:
  "record highs," "multi-year peaks," "roughly triple its 2020 level,"
  "cooling from recent highs." Do NOT invent specific numbers.
- If a figure above is marked [UNAVAILABLE], treat the entire market axis as
  unknown and use purely qualitative language ("dollar strength," "real-rate
  pressure," "inflation still above Fed target") without citing any numbers.
- It is better to say "I don't have the 2022 average gold price to hand" than
  to guess. Never fabricate a specific dollar amount, percentage, or date.
```

Three design notes:

- **Put the block BEFORE the senior-analyst voice/tone instructions**, not after. Claude weights earlier-in-prompt instructions more heavily for factual constraints, and you want the "don't invent numbers" rule to dominate tone preferences.
- **Keep the snapshot compact** — one line per metric. Long blocks dilute the "only cite these" constraint. The entire block should be <20 lines.
- **Always render the timestamp on the block header**, and always tag each datum with its own "as of" where it differs (CPI is monthly, rates are daily). The drafter can then write "Fed funds sit at 4.33% (as of today) against 3.2% March CPI" — a sentence that would be wrong 40 days from now because CPI would have updated. The date-tags let the drafter self-correct tone for temporal relevance.

### Expected behavioral shift (from Anthropic's hallucination docs, MEDIUM confidence based on published guidance)

When the snapshot contains all 6 numbers, drafts will cite them directly and use qualitative language elsewhere. When one or more are `[UNAVAILABLE]`, drafts will flip to fully qualitative — still coherent analyst-voice prose, but without the specific-number anchors that were causing hallucinations. This is the desired behavior per operator-locked decisions.

### Do-not pattern

Do **not** do this:

```
Here are today's market numbers: (fetch them yourself if needed)
```

This invites the drafter to "fetch" by reaching into training-data prices — which is exactly the bug being fixed. The block must be declarative, not instructional.

---

## Sources

### Primary (HIGH confidence)
- FRED API docs: https://fred.stlouisfed.org/docs/api/fred/ — rate limit, auth, series semantics
- FRED API key registration: https://fred.stlouisfed.org/docs/api/api_key.html — free, instant
- Anthropic prompt engineering tutorial, hallucination chapter: https://github.com/anthropics/courses/blob/master/prompt_engineering_interactive_tutorial/Anthropic%201P/08_Avoiding_Hallucinations.ipynb
- Claude 4 best practices (prompting docs): https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/claude-4-best-practices
- metalpriceapi pricing (fetched 2026-04-20): https://metalpriceapi.com/pricing — free 100 req/mo, Basic $8.99/mo for 10k req/mo
- Existing codebase: `scheduler/agents/content_agent.py`, `scheduler/agents/brand_preamble.py`, `scheduler/config.py`, `scheduler/models/content_bundle.py`, `scheduler/worker.py`

### Secondary (MEDIUM confidence)
- yfinance reliability issues 2025: Medium post "Why yfinance Keeps Getting Blocked" + multiple corroborating dev blogs
- Alpha Vantage 25/day free tier: https://www.macroption.com/alpha-vantage-api-limits/ + RapidAPI + multiple GitHub issue reports
- gold-api.com behavior: docs page confirms no-auth, no-rate-limit for price endpoint; landing page showed live $4820.80 gold price at fetch time (2026-04-20)
- metals.dev pricing: https://metals.dev/pricing — 100 req/mo free, 60s updates
- "How to Reduce Claude AI Hallucinations" guide (corroborates official Anthropic techniques): https://superclaude.app/en/blog/claude-ai-reduce-hallucinations-proven-techniques

### Tertiary (LOW confidence — not relied upon for decisions)
- stooq reliability: pandas-datareader GitHub issue #925 confirms broken commodities endpoint since late 2021
- omkarcloud gold-price-api: single-repo project, 5k req/mo — not chosen

---

## Metadata

**Confidence breakdown:**
- FRED stack (free, 120 req/min, instant key, series IDs): HIGH — government API with extensive docs and multiple independent Python clients confirming behavior
- metalpriceapi choice: HIGH — pricing fetched live, fits budget, SDK exists
- gold-api.com as fallback: MEDIUM — confirmed no-auth endpoint + live price observed, but provenance and uptime unverified at 8/day cadence
- DXY drop recommendation: MEDIUM-HIGH — grounded in "DTWEXBGS ≠ DXY" fact + yfinance reliability record; operator could reasonably override if they want the specific ICE DXY number
- Prompt injection pattern: HIGH — directly aligned with Anthropic's published hallucination-reduction techniques
- Pitfall list: HIGH on items 1-4 (grounded in API schema reality), MEDIUM on item 5 (historical-hallucination residue — based on how LLMs behave, not measured in this project)

**Research date:** 2026-04-20
**Valid until:** 2026-05-20 (30 days — metalpriceapi pricing and FRED behavior are stable; re-verify if delaying implementation >30 days)
