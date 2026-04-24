---
quick_task: 260424-htu
slug: expand-serpapi-rss-ingestion-coverage-cr
subsystem: scheduler/agents/content_agent (SERPAPI_KEYWORDS + RSS_FEEDS)
date: 2026-04-24
status: complete
commits: [7530663]
---

# Quick Task 260424-htu Summary

## One-liner

Expanded SERPAPI_KEYWORDS 10→18 with targeted critical-minerals + sovereign-gold entries and swapped the dead Reuters RSS feed for BNN Bloomberg, directly addressing the EU/US critical minerals deal miss and the Azerbaijan $3B gold drawdown miss identified in the DB diagnostic.

## What shipped

**`scheduler/agents/content_agent.py`**

- `RSS_FEEDS`: Dropped dead feed `https://feeds.reuters.com/reuters/businessNews` ("reuters.com"); replaced with `https://www.bnnbloomberg.ca/feed/` ("bnnbloomberg.ca"). List length stays at 7 (net neutral).
- `SERPAPI_KEYWORDS`: Appended 8 new entries after the original 10 (list now 18 total):
  - `"critical minerals"` — direct fix for EU/US deal coverage gap
  - `"rare earth restrictions"` — REE + export controls theme
  - `"strategic metals"` — adjacent coverage (lithium, cobalt)
  - `"sovereign wealth fund gold"` — direct fix for Azerbaijan-type sovereign sales
  - `"treasury gold sale"` — alternative phrasing for sovereign sales
  - `"gold mining M&A"` — acquisition theme not covered by "junior miners"
  - `"US China metals"` — geopolitical minerals theme
  - `"mineral supply chain"` — broader supply-chain risk

**`scheduler/tests/test_content_agent.py`**

- Updated existing length assertion: `len(SERPAPI_KEYWORDS) == 10` → `== 18`
- Added 4 new tests:
  - `test_serpapi_keywords_critical_minerals_coverage` — all 8 new keywords present
  - `test_serpapi_keywords_existing_preserved` — original 10 keywords still present
  - `test_serpapi_keywords_total_count_and_unique` — total==18, no duplicates
  - `test_rss_feeds_reuters_dropped_bnn_added` — Reuters absent, BNN Bloomberg present

## Why (link to CONTEXT decisions)

- **CONTEXT Q1** — 8 surgical additions (not 15) to avoid blowing SerpAPI budget. Pipeline already fetches 65-82 unique articles per run; expansion is targeted not broad.
- **CONTEXT Q2** — Reuters RSS is a dead endpoint. SerpAPI's google_news engine catches Reuters coverage under keyword queries; no feed replacement needed.
- **CONTEXT Q3** — BNN Bloomberg covered the EU/US critical minerals deal per user screenshot. Low maintenance risk, confirmed viable.
- **CONTEXT Q9** — T1+T2 collapsed into single atomic commit (allowed deviation for data-list changes of this size). TDD RED/GREEN ceremony adds no durable signal here.

## Commit history

| Commit | Message |
|--------|---------|
| `7530663` | feat(content): expand SerpAPI keywords + swap Reuters→BNN Bloomberg RSS, with coverage tests (htu) |

## Validation evidence

### pytest

```
tests/test_content_agent.py  30 passed  (26 pre-existing + 4 new)
Full scheduler suite          147 passed  0 failed
```

### ruff

```
uv run ruff check agents/content_agent.py tests/test_content_agent.py  → clean
uv run ruff format --check agents/content_agent.py tests/test_content_agent.py → clean
```

### grep proofs (positive)

```
scheduler/agents/content_agent.py:78:    "critical minerals",
scheduler/agents/content_agent.py:79:    "rare earth restrictions",
scheduler/agents/content_agent.py:80:    "strategic metals",
scheduler/agents/content_agent.py:81:    "sovereign wealth fund gold",
scheduler/agents/content_agent.py:82:    "treasury gold sale",
scheduler/agents/content_agent.py:83:    "gold mining M&A",
scheduler/agents/content_agent.py:84:    "US China metals",
scheduler/agents/content_agent.py:85:    "mineral supply chain",
scheduler/agents/content_agent.py:57:    ("https://www.bnnbloomberg.ca/feed/", "bnnbloomberg.ca"),
```

### grep proof (negative)

```
grep -n "feeds.reuters.com" scheduler/agents/content_agent.py  → 0 matches
```

### Preservation diffs (all empty)

```
git diff main -- scheduler/agents/content/          → empty
git diff main -- scheduler/worker.py                → empty
git diff main -- scheduler/agents/senior_agent.py   → empty
git diff main -- backend/ frontend/ alembic/ scheduler/models/  → empty
```

## Deviations

**T1+T2 combined into single commit** (CONTEXT Q9 allowed deviation). No RED/GREEN TDD ceremony — this is a data-list configuration change. Commit message documents the deviation. Both test additions and production changes land in `7530663`. T3 docs commit is separate per plan requirement.

## Known follow-ups (out of scope, from CONTEXT)

1. **SerpAPI plan tier verification** — post-expansion math: ~1,170 calls/day = ~35,100/month. User to verify current plan at console.serpapi.com. If on $50 tier (15k searches), likely already over limit before this task — not a regression introduced here. Upgrade to $130+ tier or implement keyword rotation if 429s appear.
2. **Recency curve tuning** — Azerbaijan story's ~24h age means `recency_score=0.2` (weakest bucket). Consider adding a 24-48h bucket at 0.5. Risks queue flood from older content. Re-evaluate after BNN Bloomberg proves value in prod for ~1 week.
3. **Dedup horizon review** — cross-agent dedup may be collapsing sovereign-sales stories (France/Russia/Azerbaijan all similar theme) too aggressively. Separate investigation.
4. **RSS feed expansion phase 2** — BNN Bloomberg added this task. Candidates for next round: AP business, Dow Jones newswire, Nikkei English gold section.
