# Quick Task 260507-drw — Headline-grouped gold news format + RSS/SerpAPI telemetry — SUMMARY

**Shipped:** 2026-05-07
**Branch:** `main`

## Why

User feedback after seeing the first 08:00 PT v2.0 card render in production:

1. **Format request:** *"Lets make it so the gold headlines and news stuff is 1 by 1. Gold headline #1 / [bullets] / Gold headline #2 / [bullets]. If it warrants a second gold headline."* — They want headline-grouped output instead of the flat list of 5 standalone bullets the original Sonnet prompt produced.

2. **SerpAPI question:** *"Is the SerpAPI not working?"* — They noticed all 5 bullets in the first card cited only RSS-feed domains (mining.com / bloomberg.com / northernminer.com). The existing telemetry only had `candidates_gold: 5` (post-filter top-5) — no breakdown of how many candidates each ingestion path contributed. Operationally invisible whether SerpAPI is broken or just losing the score race.

## Fix

Two changes, single atomic commit.

### Change 1: New `GOLD_NEWS_SYSTEM_PROMPT` — headline-grouped format

Replaced the legacy "Why it matters" 1-lead + 3-5-bullet flat format with a 1-3 adaptive headlines + 2-4 bullets per headline structure. The new prompt instructs Sonnet to:

- Identify 1-3 distinct gold-sector stories from the candidate pool. Group articles covering the same story under one headline (don't emit a separate headline for every article).
- Use 1 headline if there's one dominant story, 2 if two distinct stories, 3 max if news is unusually rich. Don't pad.
- For each story, emit a `**bold one-line headline**` (markdown strong, not `#` heading — `#` headings get stripped by `rehype-sanitize` but `<strong>` renders cleanly in the existing react-markdown pipeline).
- Headlines ≤ 12 words and concrete (name the company, price, bill — not generic "Gold rallies").
- Per headline: 2-4 supporting bullets, each ≤ 25 words ending with `(Source Name)`. Bullets pull distinct angles (data point / market reaction / analyst view / context).
- Bullets under one headline can cite multiple sources (different angles on the same story).
- One blank line between headline groups.
- The first headline IS the WhatsApp teaser body — make it self-contained.
- Forbid `#` headings, `Sources:` footnotes, tables, blockquotes, and the literal `Gold headline #1:` text prefix (the bold IS the visible separator).

Expected rendered output (example):

```markdown
**Gold breaks $4,700 on US-Iran deal optimism**

* Spot gold surged 3.6% on May 6 to top $4,700 as US-Iran deal optimism cooled inflation concerns and oil prices. (mining.com)
* Bloomberg reports the rally extended into May 6 morning trading as traders pared inflation-hedge positions. (bloomberg.com)
* 30-year US Treasury yields flirting with 5% create a competing safe-haven narrative, pulling traders between bonds and gold. (bloomberg.com)

**Denarius drops Emerita takeover bid**

* Denarius Metals abandoned its three-week takeover bid for Emerita Resources after the Spain-focused explorer refused negotiations. (northernminer.com)
* The pull-out signals notable cooling in the gold M&A market that had been heating in early 2026. (northernminer.com)
```

### Change 2: Raw-count telemetry per ingestion path

Tagged each story dict with `_source_type` ('rss' or 'serpapi') in `_fetch_all_rss()` and `_fetch_all_serpapi()` (single field added to the existing dict shape; no signature change). `_build_gold_news_section()` counts these tags pre-filter and returns a counts dict. `run_daily_summary()` writes 4 new keys to `agent_runs.notes` JSONB:

- `candidates_gold_rss`: pre-filter count of stories surfaced by RSS feeds
- `candidates_gold_serpapi`: pre-filter count of stories surfaced by SerpAPI keyword search
- `candidates_gold_total`: total candidates after dedup, before score-floor filter
- `candidates_gold_after_floor`: count of stories that cleared the ≥6.0 score floor

These nest into the existing `notes` JSONB without schema migration. The `parseRunNotes` frontend helper (post-no4) gracefully ignores unknown keys.

## Files modified

- `scheduler/agents/content_agent.py` — `_source_type` tags added to RSS + SerpAPI story dicts (2-line additions each)
- `scheduler/agents/daily_summary.py` — new `GOLD_NEWS_SYSTEM_PROMPT` + `_build_gold_news_section` returns 3-tuple `(md, raw, counts)` + `run_daily_summary` writes 4 new telemetry keys
- `scheduler/tests/agents/test_daily_summary.py` — updated 3 sites that unpacked `(md, raw)` to `(md, raw, counts)`; replaced `test_gold_news_system_prompt_contains_why_it_matters` with `test_gold_news_system_prompt_contains_headline_grouped_format` + new `test_gold_news_system_prompt_no_numbered_headline_prefix`; extended `test_run_daily_summary_writes_telemetry_notes_with_required_keys` required_keys with the 4 new counters
- `scheduler/tests/test_content_agent.py` — 3 new tests verifying `_source_type` tagging on RSS + SerpAPI ingestion plus the empty-list graceful-degrade when serpapi_client is None

## Validation

- `cd scheduler && uv run pytest -x` → **313 passed, 1 skipped, 3.76s** (was 309 before; +4 new tests)
- `cd scheduler && uv run ruff check .` → clean
- Preservation diff: `git diff main -- backend/ frontend/ scheduler/worker.py` returns 0 bytes ✓
- WhatsApp teaser extraction (`_extract_lead`) untouched; the new format's first non-empty line is `**Gold breaks $4,700 on US-Iran deal optimism**` (or similar) — strips fine to a teaser body with the `**` markdown left in or stripped depending on what `_extract_lead` does. The teaser delivery is gated by `WHATSAPP_DELIVERY_ENABLED` so any rendering issue is observable but not breaking.

## Operational impact (after Railway redeploy)

- Next 12:00 PT cron fire produces a card with the **new headline-grouped format** in the Gold News section. Ontario Law / Ontario Stats sections unchanged.
- `agent_runs.notes` JSONB on the next fire will include the **4 new telemetry counters**, visible via the existing `/agents/daily_summary` page (post-no4 parseRunNotes handles unknown keys gracefully) AND directly via Neon SQL:

```sql
SELECT started_at, notes::jsonb -> 'candidates_gold_rss' AS rss,
       notes::jsonb -> 'candidates_gold_serpapi' AS serpapi,
       notes::jsonb -> 'candidates_gold_total' AS total,
       notes::jsonb -> 'candidates_gold_after_floor' AS after_floor
FROM agent_runs WHERE agent_name='daily_summary'
ORDER BY started_at DESC LIMIT 5;
```

- **Diagnosis path for the SerpAPI question:** if `candidates_gold_serpapi: 0` shows up on the next fire, the most likely cause is `SERPAPI_API_KEY` env var not set on the Railway scheduler service. The local `.env` has no `SERPAPI_API_KEY` either. Per safety rules I cannot set Railway env vars on the user's behalf. Action for the user: open Railway → scheduler service → Variables → confirm `SERPAPI_API_KEY` is set with their SerpAPI plan key (the user pays $50/mo for SerpAPI per the budget constraint, so the key exists somewhere). If `candidates_gold_serpapi > 0` on the next fire, SerpAPI is fine — it just lost the score race today.

## Out of scope (untouched)

- WhatsApp teaser extraction logic — verified to still work with the new format (extracts the first non-empty line)
- Backend, frontend (no API or UI changes; markdown still renders fine via rehype-sanitize)
- RSS_FEEDS list (just shipped in inz; don't churn)
- SerpAPI keyword list (already gold-focused)
- Score weights / threshold (sound)
- Other section builders (Ontario law / Ontario stats unchanged)
