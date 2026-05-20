# Technology Stack — v2.0 Daily Summary Feed (Delta)

**Project:** Seva Mining — AI Social Media Agency
**Milestone:** v2.0 Daily Summary Feed
**Researched:** 2026-05-05
**Scope:** Additions and changes for v2.0 only. The existing validated stack
(FastAPI, React 19, Vite 6, Tailwind v4, TanStack Query 5, Zustand 5, shadcn/ui,
SQLAlchemy 2.0, Alembic 1.14, APScheduler 3.11.2, anthropic 0.86.0, feedparser 6.x,
serpapi, Twilio 9.x, date-fns 3.x, httpx, passlib, python-jose) is **not re-documented
here** — it is proven to work.

---

## Verdict Summary

| Candidate | Verdict | One-line reason |
|-----------|---------|-----------------|
| `react-markdown` | ADD | Claude returns structured markdown; split-on-newline loses heading hierarchy |
| `rehype-sanitize` | ADD | Pair with react-markdown to sanitise any HTML Claude might emit |
| Ontario Newsroom RSS | SKIP new lib | Existing feedparser handles it; add the URL to the ingestion feed list |
| Ontario Regulatory Registry RSS | SKIP new lib | Same; add ontariocanada.com registry URL to feed list |
| StatCan WDS REST API | SKIP new HTTP lib | Public JSON REST API; existing `httpx` is sufficient |
| New job queue (Celery, ARQ) | SKIP | Forbidden in CLAUDE.md; APScheduler handles 2 new crons trivially |
| `zoneinfo` (Python stdlib) | SKIP install | Already available in Python 3.12; use `from zoneinfo import ZoneInfo` in new cron registrations |
| WhatsApp chunking lib | SKIP | `build_chunks()` in `whatsapp.py` is generic and reusable as-is |
| `remark-gfm` | SKIP for now | Claude won't emit GFM tables in summaries; add later if needed |

**Net new installs: `npm install react-markdown rehype-sanitize` — that is all.**

---

## New Frontend Packages

### `react-markdown` ^10.1.0 + `rehype-sanitize` ^6.0.0

**Verdict: ADD both.**

**Why react-markdown is needed:**
Claude's summary output will be structured markdown — `### Gold News`, bullet lists
with `*`, bold via `**`. Plain `text.split('\n').map(line => <p>)` loses heading
hierarchy: a `###` header becomes visually identical to a paragraph. The feed card
requires three visually-distinct sections with headers and nested bullets; that
requires real markdown rendering.

**Why not `dangerouslySetInnerHTML` after string replace:**
Never render LLM output as raw HTML. Even with a constrained system prompt,
an adversarially-crafted source article could cause Claude to emit `<script>` or
`javascript:` hrefs. The risk is low but the cost of prevention is zero.

**Why react-markdown over alternatives:**
- Uses an AST pipeline (remark → rehype → `React.createElement`), never
  `dangerouslySetInnerHTML`. This is architecturally safer than `marked` or
  `markdown-to-jsx` (the latter had CVE-2024-21535 XSS in Dec 2024).
- Maps cleanly to Tailwind v4 utility classes via the `components` prop:
  `h3` → `<h3 className="text-sm font-semibold ...">`, `ul` →
  `<ul className="list-disc ml-4 ...">`. No CSS-in-JS fight.
- Latest stable: **10.1.0** (no new release in ~12 months — stable; last published
  ~mid-2024). React 19 compatible.
- ESM-only since v9 — fine with the project's `"type": "module"` and Vite 6.

**Why rehype-sanitize alongside it:**
react-markdown passes rehype plugins. `rehype-sanitize` strips any HTML nodes
that survived remark parsing before they reach the DOM. Claude should not emit
raw HTML, but defence-in-depth for a tool with no CSP headers is cheap.

**Integration point:** `frontend/src/components/SummaryCard.tsx` — a single
component, no page-level changes:

```tsx
import ReactMarkdown from 'react-markdown'
import rehypeSanitize from 'rehype-sanitize'

<ReactMarkdown rehypePlugins={[rehypeSanitize]}
  components={{
    h3: ({ children }) => <h3 className="text-sm font-semibold mt-3 mb-1">{children}</h3>,
    ul: ({ children }) => <ul className="list-disc ml-4 space-y-0.5">{children}</ul>,
    li: ({ children }) => <li className="text-sm">{children}</li>,
  }}>
  {summary.body}
</ReactMarkdown>
```

**Do NOT add `remark-gfm`** unless Claude actually emits GFM tables — it adds
unnecessary parsing overhead and the summary format (headlines + bullets) does
not use tables or strikethrough.

```bash
npm install react-markdown rehype-sanitize
```

**Confidence: HIGH** — npm versions confirmed; AST/non-innerHTML approach
documented at remarkjs/react-markdown; rehype-sanitize v6 confirmed ESM/Node 16+.

---

## Existing Libraries Confirmed Sufficient

### feedparser — Ontario Sources

**Verdict: SKIP new lib. Two new feed URLs only.**

Both new Ontario ingestion sources are served as RSS — no new library needed.

**Source 1 — Ontario Newsroom (`news.ontario.ca`):**
The site has an RSS endpoint; the exact URL is not prominently documented (JS-heavy
site). Attempt these at build-time in order:
1. `https://news.ontario.ca/newsroom/en?format=rss`
2. `https://news.ontario.ca/en/releases.rss`

If neither resolves, fall back to SerpAPI with `site:ontario.ca "mining" legislation`.
The Sonnet relevance filter ("is this actually a mining-favourable law?") applies
regardless of source — noise from a broad feed is handled there.

**Source 2 — Ontario Regulatory Registry (`ontariocanada.com/registry`):**
Confirmed RSS feeds exist at `https://www.ontariocanada.com/registry/rssInfo.do`.
The "news" feed covers new regulatory proposals including Mining Act amendments
(e.g. Bill 5 — "Protect Ontario by Unleashing our Economy Act, 2025"). The
direct feed URL is `https://www.ontariocanada.com/registry/rss.do?feedName=news`
(standard Drupal registry pattern; verify at build time).

**Reliability note (MEDIUM confidence):** Ontario government RSS URLs change
without notice. If the feed goes dark, the Ontario law section shows the "no new
data" empty state — same design as the StatCan slow-week case. No reliability
library is needed; feedparser's existing error handling is sufficient.

**feedparser maintenance:** Last release 6.0.11, Sep 2025. Actively maintained.
Python 3.12 compatible. Source: https://pypi.org/project/feedparser/

---

### httpx — StatCan WDS REST API

**Verdict: SKIP new HTTP lib. Use existing httpx.**

Statistics Canada's Web Data Service (WDS) is a public, unauthenticated JSON REST
API. The relevant table for gold and mineral production statistics is
**Table 16-10-0022** (gold included; annual data; covers reference years 2019+).

Latest data release: **February 25, 2026** (reference years 2024 and 2025).

The endpoint follows a consistent pattern:
```
GET https://www150.statcan.gc.ca/t1/tbl1/en/dtbl!16-10-0022-01/json
```

This is a standard unauthenticated GET returning JSON — `httpx.AsyncClient` handles
it identically to `fetch_article()` today. No specialised client library exists
or is needed.

**Critical design implication for the roadmap:**
StatCan mineral statistics are released **annually**, not daily. Between the Feb
2026 release and the next (expected late 2026/early 2027), every daily_summary
cycle will return the same static snapshot. The Ontario stats section must treat
"no new data since {date}" as the **default state**, not an edge case. Design
approach: the daily_summary agent fetches StatCan once on first run and stores the
snapshot as JSONB in the `daily_summaries` table. Subsequent runs display "Latest
available: {date}" without re-fetching.

**Confidence: MEDIUM** — StatCan WDS documented at statcan.gc.ca/en/developers/wds.
Table ID 16-10-0022 confirmed via search (Feb 2026 release referenced). Exact endpoint
URL should be verified against the WDS User Guide before the ingestion module is built.

---

### APScheduler 3.11.2 — DST Handling for New Crons

**Verdict: SKIP upgrade. Same version; same pattern. One implementation note.**

The two new `daily_summary` CronTriggers at 08:00 PT and 12:00 PT follow the same
`cron_kwargs` dict pattern already established for `sub_quotes` etc. in worker.py:

```python
("daily_summary_am", run_daily_summary_am, "Daily Summary AM", 1020,
 {"hour": 8, "minute": 0, "timezone": "America/Los_Angeles"}),

("daily_summary_pm", run_daily_summary_pm, "Daily Summary PM", 1021,
 {"hour": 12, "minute": 0, "timezone": "America/Los_Angeles"}),
```

**DST correctness:** APScheduler 3.11 documents that CronTrigger uses "wall clock"
time. Known DST bugs (issues #606, #529, #980) involve jobs scheduled AT or near
the 02:00 transition boundary. 08:00 and 12:00 are far from the DST boundary;
no pathological behaviour applies.

APScheduler 3.11 internally resolves timezone strings via `zoneinfo` (not pytz).
The string `"America/Los_Angeles"` is the correct form. Do NOT pass a `pytz` zone
object — that triggers a `PytzUsageWarning` and may re-introduce DST bugs that
were fixed in the zoneinfo path (Discussion #570).

**Behavioural expectation:**
- Winter (PST, UTC−8): 08:00 fires at 16:00 UTC, 12:00 fires at 20:00 UTC
- Summer (PDT, UTC−7): 08:00 fires at 15:00 UTC, 12:00 fires at 19:00 UTC

This is correct "wall clock" behaviour — the user sees 8am and noon year-round.

**Lock IDs:** Assign 1020 (`daily_summary_am`) and 1021 (`daily_summary_pm`) from
`JOB_LOCK_IDS` to avoid collisions with existing jobs (highest current is 1016).

**Confidence: HIGH** — APScheduler 3.11.2 docs confirm string timezone resolution
via zoneinfo; 08:00/12:00 are not DST-boundary times; existing worker.py pattern
is proven.

---

### Twilio WhatsApp — Message Length and Chunking

**Verdict: SKIP new lib. Reuse `build_chunks()` from `whatsapp.py` directly.**

**Character limits (MEDIUM confidence):**
- Twilio platform hard cap: **1600 chars** per message (confirmed via Twilio help
  article 360033806753 and GitHub issue #329)
- WhatsApp non-template free-form messages: potentially as low as **1024 chars**
  in some configurations, but Twilio sandbox has historically been more permissive
- Current `build_chunks()` enforces **1500 chars** (`max_chunk_chars=1500`) — a
  100-char safety margin below the Twilio cap. This is the correct ceiling.

**Summary length estimate (3 sections, realistic):**
- Header: ~30 chars
- Gold news (3–5 headlines + 1–2 bullets each): ~500–700 chars
- Ontario law section: ~200–300 chars
- Ontario stats section: ~150–250 chars (or "no new data" one-liner: ~50 chars)
- **Typical total: ~900–1300 chars; heavy-news day: ~1700–1800 chars**

A busy-day summary will exceed 1500 chars. Design approach:
1. Claude's system prompt for summary generation targets ~1200 chars to fit in one
   WhatsApp message on most days
2. The delivery hook calls `build_chunks(agent_name="daily_summary", items=[text])`
   which handles multi-message split automatically with `[daily_summary 1/2]` headers
3. The WhatsApp failure-alert hook is a fixed short message (<100 chars) — no
   chunking logic needed

`build_chunks()` is already a generic function with no morning-digest-specific
coupling. It can be imported and called directly from the new delivery module.

**Confidence: MEDIUM** — 1600-char Twilio platform cap is confirmed. The 1024-char
WhatsApp non-template limit appears in some docs but sandbox behaviour differs;
test in sandbox before treating 1024 as a hard ceiling.

---

### `fetch_stories()` — Reusability for Gold News Section

**Verdict: Reuse as-is. No changes to content_agent.py.**

The post-m51 `fetch_stories()` returns scored, deduplicated stories from 7 RSS feeds
+ 17 SerpAPI keywords, with a 30-min TTL cache and the parallel-scoring coalesce
pattern. The `daily_summary` agent:

1. Calls `fetch_stories()` — gets the cached result (no redundant fetch)
2. Filters by `story["published"] >= window_start` where `window_start` is 04:00 PT
   for the 08:00 run and 08:00 PT for the 12:00 run
3. Takes the top N stories by `story["score"]`
4. Passes them to Claude Sonnet for synthesis into headlines + bullet format

The `daily_summary` agent does NOT need its own relevance scoring pass — stories are
already scored. It does NOT need the `predicted_format` field. It does NOT need the
compliance gate (`review()`) — summaries are read, not posted.

---

## What NOT to Add

| Package | Why Rejected |
|---------|-------------|
| Celery + Redis | Explicitly forbidden in CLAUDE.md "What NOT to Use" table |
| APScheduler 4.0 alpha | Explicitly forbidden in CLAUDE.md |
| `marked` / `markdown-to-jsx` | `marked` uses `innerHTML`; `markdown-to-jsx` had CVE-2024-21535 XSS; react-markdown's AST approach is safer for LLM output |
| `DOMPurify` (separate) | `rehype-sanitize` sanitises at AST level before HTML is rendered; DOMPurify would be a redundant second pass |
| `remark-gfm` | Claude summary output (headlines + bullets) does not use GFM tables or strikethrough; add only if observed in practice |
| Playwright / Puppeteer / Apify | Ontario Newsroom and StatCan both have RSS/JSON APIs; scraping is not needed; Apify was explicitly purged in quick-260419-lvy |
| `fastfeedparser` | Only 4–6 feeds total; feedparser is sufficient; listed as alternative in v1 STACK.md |
| Any new auth library | Single-user password auth is validated and shipped |
| `pytz` | APScheduler 3.11 uses `zoneinfo` internally; passing pytz zones triggers warnings and may reintroduce DST bugs |

---

## Installation

```bash
# Frontend only — from /frontend
npm install react-markdown rehype-sanitize

# Backend — zero new pip packages
# zoneinfo is Python 3.9+ stdlib; no install needed
# httpx is already installed; use for StatCan WDS GET
# feedparser is already installed; add new feed URLs to the ingestion module
```

---

## Version Compatibility

| Package | Version | Compat | Notes |
|---------|---------|--------|-------|
| react-markdown | ^10.1.0 | React 19, Node 20+, Vite 6 | ESM-only — fine with `"type":"module"` |
| rehype-sanitize | ^6.0.0 | Node 16+, React 19 | ESM-only — same |
| zoneinfo | stdlib (3.12) | Python 3.12 | `from zoneinfo import ZoneInfo` — no install |

---

## Sources

- react-markdown npm (10.1.0 latest): https://www.npmjs.com/package/react-markdown
- react-markdown GitHub (AST/security approach): https://github.com/remarkjs/react-markdown
- react-markdown security guide: https://strapi.io/blog/react-markdown-complete-guide-security-styling
- markdown-to-jsx CVE-2024-21535 XSS: https://security.snyk.io/vuln/SNYK-JS-MARKDOWNTOJSX-6258886
- rehype-sanitize npm: https://www.npmjs.com/package/rehype-sanitize
- APScheduler 3.11.2 CronTrigger + DST docs: https://apscheduler.readthedocs.io/en/3.x/modules/triggers/cron.html
- APScheduler issue #606 (DST skip at midnight): https://github.com/agronholm/apscheduler/issues/606
- APScheduler issue #980 (DST infinite loop): https://github.com/agronholm/apscheduler/issues/980
- APScheduler pytz → zoneinfo migration (Discussion #570): https://github.com/agronholm/apscheduler/discussions/570
- Twilio 1600-char platform cap: https://help.twilio.com/articles/360033806753
- Twilio WhatsApp rules and limits: https://help.twilio.com/articles/360017773294
- StatCan WDS API developer docs: https://www.statcan.gc.ca/en/developers/wds
- StatCan WDS User Guide: https://www.statcan.gc.ca/en/developers/wds/user-guide
- StatCan mineral production Table 16-10-0022 + Feb 2026 release: https://natural-resources.canada.ca/minerals-mining/mining-data-statistics-analysis
- StatCan RSS feeds: https://www.statcan.gc.ca/en/sc/rss
- Ontario Regulatory Registry RSS: https://www.ontariocanada.com/registry/rssInfo.do?action=list
- Ontario mining Bill 5 (2025): https://www.canadianminingjournal.com/featured-article/modernizing-mining-in-ontario-recent-regulatory-shifts-with-bill-5/
- feedparser PyPI (6.0.11, Sep 2025): https://pypi.org/project/feedparser/
