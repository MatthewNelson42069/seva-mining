# Quick Task 260506-inz — Add Bloomberg markets RSS to gold-news pipeline — SUMMARY

**Shipped:** 2026-05-06
**Branch:** `main` (single mechanical addition, ~5 min total)

## Why

User asked: *"lets do the direct RSS from bloomberg as well, add that in"* — direct response to the i65 audit which had marked the Bloomberg commodity feed as 404. Per i65's HTTP probe, `feeds.bloomberg.com/commodities/news.rss` IS dead. But re-probing more aggressively across all known Bloomberg feed paths revealed that the broader `feeds.bloomberg.com/markets/news.rss` IS alive — 200, valid `application/rss+xml`, ~33 KB, ~20 article items.

Sample article titles from the live feed (verified 2026-05-06 13:25 UTC):
- "Canada's Carbon Tax Hinders Pipeline Plans, Cenovus CEO Says"
- "Vitol Is Turning to Mexico for Oil as War Disrupts Crude Market"
- "Stocks Hit All-Time Highs on Hopes War Is Near End: Markets Wrap"
- "Yen Spikes to 10-Week High and Sparks Intervention Chatter"
- "Oil and Gas Plunge as Iran Weighs New US Proposal to End War"
- "Gundlach Warns Investors Will Lose Money on Private Credit"
- 14 more general financial-markets items

So the feed is **broad financial markets**, not gold-specific. ~5-15% of items are gold-relevant on a typical day (central bank gold buying, hedge fund positions, macro drivers like Fed/yields/USD/inflation that move gold). That's fine — Bloomberg's tier-1 credibility (1.0 in `CREDIBILITY_TIERS`) means even a few authoritative gold stories per fire carry strong signal. The Sonnet relevance scoring drops the rest before the score floor.

## Other URLs probed during this task

| URL | Status | Result |
|---|---|---|
| `feeds.bloomberg.com/news.rss` | ✅ 200 | Works (general Bloomberg news) |
| `feeds.bloomberg.com/markets/news.rss` | ✅ 200 | **Selected** — markets-specific, slightly more financial-news-heavy |
| `www.bloomberg.com/feeds/news.rss` | ✅ 200 | Same content as above (alias) |
| `feeds.bloomberg.com/markets.rss` (no `/news`) | 404 | |
| `feeds.bloomberg.com/economics.rss` | 404 | |
| `feeds.bloomberg.com/businessweek.rss` | 404 | |
| `feeds.bloomberg.com/wealth.rss` | 404 | |
| `feeds.bloomberg.com/commodities/news.rss` | 404 | (the original i65-marked-dead URL, still dead) |

Selected `markets/news.rss` over the broader `news.rss` because the markets feed has a slightly higher density of finance/market content vs. the general news feed which mixes in tech / pursuits / lifestyle.

**Reuters last attempt:** `feeds.feedburner.com/reuters/businessNews` returned 200 but the content is hijacked — Flipso Global Feed serving off-topic articles ("Why Poland Is Building Castles Again", "Knitting Bullshit"). Confirmed NOT real Reuters. Skipped.

## Fix

Single change to `scheduler/agents/content_agent.py`:

### `RSS_FEEDS` (4 → 5)

```python
RSS_FEEDS = [
    ("https://www.mining.com/feed/", "mining.com"),
    ("https://www.northernminer.com/feed/", "northernminer.com"),
    ("https://goldswitzerland.com/feed/", "goldswitzerland.com"),
    ("https://www.fxstreet.com/rss/news", "fxstreet.com"),
    ("https://feeds.bloomberg.com/markets/news.rss", "bloomberg.com"),  # NEW
]
```

### `CREDIBILITY_TIERS`

**No change needed.** `bloomberg.com` is already in the dict at `1.0` (tier-1 institutional wire, kept across i65 because it may surface via SerpAPI). The new RSS-feed entry maps to the same `bloomberg.com` source name, so `credibility_score("bloomberg.com")` returns `1.0` — no double-entry, no key conflict.

### Module docstring

Updated comment block above `RSS_FEEDS` to note the i65 → inz progression: i65 dropped the dead `commodities/news.rss`, inz added back the broader `markets/news.rss` once the re-probe found it alive.

## Tests

`scheduler/tests/test_content_agent.py`:
- **UPDATED** `test_rss_feeds_constant_preserved` — assert `len == 5` (was 4); add `feeds.bloomberg.com/markets/news.rss` to the expected URL list.
- **NEW** `test_rss_feeds_bloomberg_uses_markets_feed` — guard against accidentally re-introducing the dead `commodities/news.rss` URL. Asserts exactly one `bloomberg.com` entry and that its URL is the working `markets/news.rss`.
- **UPDATED** `test_rss_feeds_dead_urls_removed` — narrowed the Bloomberg assertion from "no `feeds.bloomberg.com`" to "no `feeds.bloomberg.com/commodities`" (the commodity-specific URL is dead, but the markets URL is live).

Other tests untouched. `test_credibility_tiers_legacy_sources_preserved` still asserts `bloomberg.com == 1.0` — no change.

## Validation

- `cd scheduler && uv run pytest -x` → **309 passed, 1 skipped** (was 308 before; +1 new test)
- `cd scheduler && uv run ruff check .` → clean
- Preservation diff: `git diff main^ -- backend/ frontend/ scheduler/worker.py scheduler/agents/daily_summary.py` returns 0 bytes ✓

## Operational impact

- Next 12:00 PT cron fire ingests from **5 RSS sources + SerpAPI** (vs. the 4 + SerpAPI from i65)
- Expected candidate count per fire: ~100-170 (up from ~80-150 after i65)
- Bloomberg's tier-1 credibility (1.0) means even partial-relevance gold stories from Bloomberg can clear the 6.0 score floor — these are the high-signal central-bank-buying / hedge-fund-positioning / macro-driver stories that the institutional wire excels at
- Anthropic relevance scoring runs over ~20 more candidates per fire — minor cost increase (~$0.10/fire × 60 fires/month = ~$6/month), well within $30-50/mo AI budget

## Limitations

- The Bloomberg feed is broad financial markets, not gold-specific. ~85% of items per fire will fail the relevance scoring and not reach the 6.0 floor. That's expected — Bloomberg's value here is the few high-signal gold stories that DO get through, not breadth.
- If Bloomberg ever resurrects a commodity-specific RSS, switching to that URL would reduce wasted Sonnet scoring calls. Worth a quarterly re-probe as part of the same RSS-rot watch flagged in i65.

## Out of scope (still untouched)

- SerpAPI keyword list — clean
- Score weights / threshold — sound
- Sonnet prompt for gold news section — solid
- Recency curve — reasonable
- Backend, frontend, scheduler/worker.py, scheduler/agents/daily_summary.py — zero diff
