---
quick_task: 260424-htu
slug: expand-serpapi-rss-ingestion-coverage-cr
subsystem: scheduler/agents/content_agent (SERPAPI_KEYWORDS + RSS_FEEDS)
mode: discuss
date: 2026-04-24
related_work: [260423-lvp, 260424-e37, 260422-lbb]
---

# Quick Task 260424-htu: Expand SerpAPI + RSS ingestion coverage + diagnose Azerbaijan miss

## User's verbatim ask

> "Also we didnt pick up this news today. Especially, the EU US critical minerals, that one is very important"
> "Task A, ingestion expansion / Task B, tackle it / Then do everything else how you best see fit"

Two screenshots shown:
- Azerbaijan Sold Gold Worth $3 Billion in First Ever Drawdown (Bloomberg, 1 day ago) — sovereign wealth fund theme
- EU/US Critical Minerals deal (Reuters / BNN Bloomberg / WSJ / Mining.com / The Deep Dive, 2-4 hours ago)

## Task B diagnostic — DB evidence

Queried prod Neon `content_bundles` + `agent_runs` for last 7 days:

**What the pipeline IS catching (last 7d, related matches):**
- Apr 22: "U.S. Gold Mining Surges Amid Demand For Critical Minerals" (streamlinefeed.co.ke)
- Apr 22: "Bank of France sells its 129-tonne US gold reserve" (Kitco) — sovereign theme ✓
- Apr 24 today: "Russia sold 700,000 oz. of gold in 2026" (Kitco) — sovereign theme ✓
- Apr 24 today: "What made Putin sell 22,000 kg gold from Russia this year?" — sovereign theme ✓
- Apr 24 today: "France Pulls All Gold Out of US Federal Reserve" (Newsweek) ✓
- Apr 18: "Fast-tracking US critical minerals could backfire…" (mining.com)
- Apr 18-19: "Environmental group sues US Interior for approving rare earth mining" (mining.com)
- Apr 17: "Oxford spinout raises $2.3M for deep-underground critical minerals tech"

**What the pipeline is MISSING:**
- Azerbaijan $3B gold drawdown — zero rows matching "azerbaijan" in last 7d
- US-EU critical minerals deal (specifically today's 2-4h-old deal) — zero rows matching that specific deal

**Pipeline volume (last 2d):**
```
2026-04-24 | sub_breaking_news    | runs=13 avg_found=73 max=81 total_queued=35
2026-04-24 | sub_threads          | runs=6  avg_found=66 max=81 total_queued=2
2026-04-24 | sub_quotes           | runs=1  avg_found=80 max=80 total_queued=1
2026-04-24 | sub_infographics     | runs=1  avg_found=80 max=80 total_queued=2
2026-04-23 | sub_breaking_news    | runs=15 avg_found=69 max=82 total_queued=56
```

System fetches 65-82 unique articles per run (after dedup across keywords), so the pipeline is NOT starved. ~5% queue rate — quite selective.

**Task B conclusion (deterministic):**

### Azerbaijan $3B story → most likely age + dedup
- Keyword coverage EXISTS: "central bank gold" + "gold reserves" should catch Bloomberg sovereign-fund story
- Possible cause 1: Article age = ~24h → `recency_score = 0.2` (weakest bucket) → composite score ~4-5 → below queue threshold
- Possible cause 2: Dedup blocked by earlier "France sold gold" / "Russia sold gold" stories covering the sovereign-sales theme
- Possible cause 3: SerpAPI's `google_news` result set for "central bank gold" didn't surface this specific Bloomberg URL (query tuning issue)
- **Fix: adding "sovereign wealth fund gold" + "treasury gold sale" keywords gives direct query match targeting this exact article phrasing. Can't guarantee it without live test, but broadens coverage decisively.**

### US-EU critical minerals deal → confirmed keyword gap
- "critical minerals" is NOT in SERPAPI_KEYWORDS → SerpAPI never fetches under that keyword
- Reuters RSS is broken → Reuters coverage of the deal never ingested
- BNN Bloomberg not in RSS → missed
- Mining.com IS in RSS — but the specific Mining.com article on this deal may not have appeared in the RSS feed at the right window OR wasn't tagged with keywords our scorer recognizes as gold-adjacent
- **Fix: adding "critical minerals" + 2-3 adjacent keywords + BNN Bloomberg RSS directly addresses this story**

## Locked decisions (discuss phase)

### Q1 — New SERPAPI_KEYWORDS: 8 additions (NOT 15 as initially sketched)

**LOCKED: 8 high-signal additions (total 18 keywords).**

Rationale: DB shows the pipeline is catching lots of gold coverage already (73-80 articles/run). Aggressive expansion to 25 keywords risks blowing the SerpAPI budget (math below). A surgical 8-keyword addition that directly targets the two specific gaps is the right call.

**Keep all 10 existing:** gold exploration, gold price, central bank gold, gold ETF, junior miners, gold reserves, gold inflation hedge, Fed gold, dollar gold, recession gold.

**Add 8:**
1. `critical minerals` — direct fix for EU-US deal coverage
2. `rare earth restrictions` — REE + export controls theme
3. `strategic metals` — adjacent coverage (lithium, cobalt, etc.)
4. `sovereign wealth fund gold` — direct fix for Azerbaijan-type sovereign sales
5. `treasury gold sale` — alternative phrasing for sovereign sales
6. `gold mining M&A` — miner-acquisition theme not covered by "junior miners"
7. `US China metals` — geopolitical-minerals theme
8. `mineral supply chain` — broader supply-chain risk theme

**Deferred (for future task if needed):** resource nationalism, BRICS gold, de-dollarization, gold-backed currency, REE export controls, critical minerals policy.

### Q2 — Reuters RSS feed
**LOCKED: (A) — DROP entirely.** `https://feeds.reuters.com/reuters/businessNews` is a dead endpoint. SerpAPI's google_news engine catches Reuters coverage under the existing + expanded keyword list. No replacement feed.

### Q3 — Additional RSS feeds
**LOCKED: Add BNN Bloomberg only.** `https://www.bnnbloomberg.ca/feed/` — covered the EU-US deal per user screenshot, low maintenance risk. Planner may add 1-2 more if a live curl confirms they're viable, but BNN Bloomberg is the committed add.

Declined: WSJ (no stable free RSS), FT (paywall RSS), Seeking Alpha (noisy; gold section RSS unclear).

### Q4 — Task B diagnostic depth
**LOCKED: Evidence-based conclusion already in hand (above). No DB query task needed in the execution phase — this CONTEXT serves as the diagnostic report.** The fix (Task A) directly addresses the identified gaps; a RED test case naming "critical minerals" and "sovereign wealth fund gold" proves intent.

### Q5 — Tests
**LOCKED: Explicit assert tests for each of the 8 new keywords + the RSS changes.**

```python
def test_serpapi_keywords_critical_minerals_coverage():
    from agents.content_agent import SERPAPI_KEYWORDS
    required = ["critical minerals", "rare earth restrictions", "strategic metals",
                "sovereign wealth fund gold", "treasury gold sale", "gold mining M&A",
                "US China metals", "mineral supply chain"]
    for kw in required:
        assert kw in SERPAPI_KEYWORDS, f"missing keyword: {kw}"

def test_reuters_rss_feed_dropped():
    from agents.content_agent import RSS_FEEDS
    urls = [u for u, _ in RSS_FEEDS]
    assert not any("feeds.reuters.com" in u for u in urls), "dead Reuters feed still present"

def test_bnn_bloomberg_rss_added():
    from agents.content_agent import RSS_FEEDS
    urls = [u for u, _ in RSS_FEEDS]
    assert any("bnnbloomberg.ca" in u for u in urls), "BNN Bloomberg feed missing"
```

### Q6 — SerpAPI budget math

Current (estimated from DB): ~13 cache-miss fetches/day × 10 keywords × 5 results = 650 SerpAPI calls/day = ~19,500/month.

After (8 keywords added): ~13 × 18 × 5 = 1,170 calls/day = ~35,100/month.

If user is on $50/mo plan (15k searches): already over, and 2.3x worse after. If on $130/mo plan (50k searches): currently safe, 70% after.

**DECISION: SHIP at 8 new keywords (18 total). DOCUMENT as known follow-up: user to verify SerpAPI plan tier at console.serpapi.com and upgrade if necessary. Pipeline was ALREADY at or over $50 plan before this task — not a regression.**

If SerpAPI starts 429'ing, the existing fetch code logs warnings and continues with partial results. No production crash risk.

### Q7 — Recency boost for high-value stories
**LOCKED: OUT OF SCOPE.** The Azerbaijan story's 1-day-old recency bucket may be a contributing factor, but tuning the recency curve is a separate decision with broader implications (would it flood the queue with older articles?). Document as follow-up.

### Q8 — Keyword rotation
**LOCKED: Keep fire-all, no rotation.** Rotation only needed if hitting SerpAPI cap hard. Address if/when the budget decision in Q6 lands on "upgrade plan."

### Q9 — Commit strategy
**LOCKED: Single atomic commit.** This is a 2-file change (content_agent.py + test_content_agent.py). TDD split (RED then GREEN) preferred if the planner sees value, but single-commit is acceptable for a config-only change of this size.

## Scope constraints

**Modified:**
- `scheduler/agents/content_agent.py` — expand SERPAPI_KEYWORDS (+8 entries); drop Reuters RSS; add BNN Bloomberg RSS.
- `scheduler/tests/test_content_agent.py` — 3 new tests (keyword coverage + RSS changes).
- `.planning/STATE.md` — new row at top of Quick Tasks Completed.

**Unchanged (preservation verification required):**
- `scheduler/agents/content/*.py` (all 6 sub-agents) — zero diff
- `scheduler/worker.py` — zero diff
- `backend/`, `frontend/`, `alembic/`, `models/` — zero diff

## Validation gates

```bash
# Scheduler
cd scheduler && uv run pytest scheduler/tests/test_content_agent.py -x -v → green
cd scheduler && uv run pytest scheduler/ -x → green
cd scheduler && uv run ruff check scheduler/agents/content_agent.py scheduler/tests/test_content_agent.py → clean
cd scheduler && uv run ruff format --check scheduler/agents/content_agent.py scheduler/tests/test_content_agent.py → clean

# Positive grep
grep -n "critical minerals\|rare earth restrictions\|sovereign wealth fund gold\|treasury gold sale\|strategic metals\|gold mining M&A\|US China metals\|mineral supply chain" scheduler/agents/content_agent.py → 8 matches
grep -n "bnnbloomberg.ca" scheduler/agents/content_agent.py → 1 match

# Negative grep (dead feed removed)
grep -n "feeds.reuters.com" scheduler/agents/content_agent.py → 0 matches

# Preservation
git diff main -- scheduler/agents/content/ → empty
git diff main -- scheduler/worker.py → empty
git diff main -- frontend/ → empty
git diff main -- backend/ → empty
git diff main -- alembic/ → empty
git diff main -- models/ → empty
```

## Related work

- **260422-lbb** — historical context: user flagged a missed article pattern before (gold sovereign sales), led to curated whitelist → then online fetch (e37).
- **260423-lvp** — added `fetch_analytical_historical_stories(queries)` helper (infographics fallback). Uses a separate query list, unaffected by this task.
- **260424-e37** — sub_gold_history uses HISTORICAL_GOLD_QUERIES (separate list). Unchanged.
- **Gate prompt** (content_agent.py:440-487) — ALREADY supports "rare-earth restrictions" and "geopolitics/systemic shock" KEEP triggers. No gate changes.
- **260423-j7x** — bullish-only filter. Not implicated in either miss based on DB evidence.

## Execution approach

Single /gsd:quick task, single atomic commit (or 2 commits if planner prefers TDD RED/GREEN split):

1. Write the 3 new tests (or a single combined test) → verify they FAIL against current code.
2. Add the 8 keywords + drop Reuters + add BNN Bloomberg → verify tests PASS.
3. Run full scheduler pytest + ruff → verify green.
4. Preservation grep — verify zero diff on sub-agents, worker, frontend, alembic, models.
5. Commit + STATE.md row + SUMMARY.md.

## Known follow-ups (out of scope, documented for future)

1. **SerpAPI plan tier verification** — user to check current plan at console.serpapi.com. If at $50 tier, likely already 429'ing. Decision: upgrade to $130+ tier OR implement keyword rotation (Q8).
2. **Recency curve tuning** — consider adding a 24-48h bucket valued 0.5 between the current 0.4 (12-24h) and 0.2 (>24h) tiers. Would have helped the Azerbaijan story but risks queue flood from older content.
3. **Dedup horizon review** — cross-agent dedup may be too aggressive across sovereign-sales stories (France / Russia / Azerbaijan all similar). Possible tuning.
4. **RSS feed expansion phase 2** — BNN Bloomberg added this task; candidates for future: AP business, Dow Jones newswire (if feed exists), Nikkei English gold section.

## Success criteria

- All 3 new tests pass.
- `grep -n "critical minerals" scheduler/agents/content_agent.py` returns a match.
- `grep -n "feeds.reuters.com"` returns nothing.
- `grep -n "bnnbloomberg.ca"` returns a match.
- All scheduler + backend tests green; ruff clean.
- Zero diff on 6 sub-agents, worker.py, frontend, alembic, models.
- STATE.md row added.
