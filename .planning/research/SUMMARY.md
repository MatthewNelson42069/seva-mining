# Research Summary — v2.0 Daily Summary Feed

**Project:** Seva Mining — AI Social Media Agency
**Milestone:** v2.0 Daily Summary Feed
**Researched:** 2026-05-05
**Confidence:** HIGH (stack + architecture), MEDIUM (Ontario law sources), HIGH (StatCan stats cadence)

---

## Executive Summary

The v2.0 pivot replaces the 6-sub-agent approval dashboard with a 2x-daily structured summary feed delivered via WhatsApp and a minimal web feed. The product is a personal intelligence digest — not a broadcast tool — and that framing drives every architectural decision: single DB table, read-only API, teaser-style WhatsApp notification pointing to the web feed as the primary reading surface. The existing stack (fetch_stories, APScheduler CronTrigger, Twilio, FastAPI, React 19) handles 90% of the work; net-new installs are exactly two npm packages (react-markdown, rehype-sanitize) and zero pip packages.

The critical implementation risk is not the technology — it is the Ontario law section. No clean machine-readable feed delivers "Ontario just passed a mining-favourable law." The recommended approach is Ontario Newsroom RSS + NRCan RSS + a SerpAPI fallback, all routed through a Haiku relevance filter with explicit REJECT examples for political speech. Without the negative examples the filter will accept ministerial speeches as laws. The Ontario stats section is a solved problem operationally: StatCan Table 16-10-0019-01 releases monthly (~19th-21st of M+2), so the correct design treats the empty state as the default, not an edge case. The stat snapshot (last_known_figure, snapshot_date) must be stored in daily_summaries.raw_sources_jsonb.ontario_stats.snapshot_date so the empty-state copy can always render "data through {YYYY-MM}" without re-querying StatCan.

The recommended build order — gold-only summary card + WhatsApp + minimal web feed first, then Ontario law, then Ontario stats, then prune — delivers user-visible value at the end of every phase. The alternative (ARCHITECTURE.md's original 6-phase split that deferred the web feed to Phase 3 after Ontario law) would make the operator wait 3 phases before seeing anything in a browser. Shipping the web feed alongside the gold-only card in Phase 1 costs only a few additional frontend files and unlocks the reading surface immediately.

---

## Recommended Stack Additions

The existing validated stack is unchanged. These are the only additions:

| Addition | Type | Verdict | Rationale |
|----------|------|---------|-----------|
| react-markdown ^10.1.0 | npm | ADD | Claude returns markdown; split-on-newline loses heading hierarchy; AST pipeline, never dangerouslySetInnerHTML |
| rehype-sanitize ^6.0.0 | npm | ADD | Pairs with react-markdown; sanitises HTML nodes at AST level before DOM; defence-in-depth for LLM output |
| zoneinfo (stdlib) | Python 3.12 | ALREADY PRESENT | Use ZoneInfo("America/Los_Angeles") for CronTrigger; do NOT pass pytz zones (triggers APScheduler DST bug) |
| feedparser (existing) | pip | NO NEW INSTALL | Add two new feed URLs; no new library needed |
| httpx (existing) | pip | NO NEW INSTALL | StatCan WDS is a public JSON REST API; existing httpx handles it identically to fetch_article() |

Install command (frontend only):
  npm install react-markdown rehype-sanitize

What NOT to add: Celery, ARQ, APScheduler 4.0 alpha, marked, markdown-to-jsx (CVE-2024-21535 XSS), DOMPurify (redundant given rehype-sanitize), remark-gfm (Claude will not emit GFM tables in summaries), pytz.

---

## Key Findings

### From STACK.md

The existing stack covers all v2.0 requirements without new backend dependencies. The Ontario Newsroom RSS URL is unconfirmed — attempt https://news.ontario.ca/newsroom/en?format=rss or https://news.ontario.ca/en/releases.rss at build time. The Ontario Regulatory Registry RSS is confirmed at https://www.ontariocanada.com/registry/rss.do?feedName=news. StatCan WDS endpoint pattern is GET https://www150.statcan.gc.ca/t1/wds/rest/getDataFromVectorsAndLatestNPeriods/{vectorId}/1 — unauthenticated, existing httpx handles it. APScheduler CronTrigger(hour="8,12", minute=0, timezone="America/Los_Angeles") is correct; 08:00 and 12:00 are well outside the DST-ambiguous 01:00-02:00 window. WhatsApp teaser design (< 400 chars, link to web feed) sidesteps the 1600-char Twilio hard cap entirely.

### From FEATURES.md

Must ship in v2.0:
- daily_summary cron at 08:00 PT + 12:00 PT with daily_summaries table
- Three-section card: Gold News / Ontario Laws / Ontario Stats
- Gold News from fetch_stories() (score >= 6.0, top 5 stories) — reuse as-is
- Ontario Laws: Ontario Newsroom RSS + NRCan RSS + SerpAPI tertiary; Haiku relevance filter
- Ontario Stats: StatCan "The Daily" RSS trigger + WDS API call on release day; monthly cadence
- Empty-state copy for all three sections (the default for Ontario Stats and Laws on most days — not an edge case)
- "No major moves since 08:00" template for 12:00 gold section on slow days
- GET /summaries endpoint — 30 days x 2 per day = 60 rows max
- Web feed at / — vertical scroll, replaces /queue
- WhatsApp teaser delivery on each fire + failure alert on cron error
- 30-day auto-prune cron

Ship after core is validated (v2.0 differentiators):
- Cross-summary continuity: pass 08:00 gold bullets into 12:00 Sonnet context (eliminates same-story repetition and enables narrative arc)
- Section anchor links (#gold-news, #ontario-laws, #ontario-stats)
- "Last updated" pointer in empty-state sections
- Click-through source URLs per bullet

Never ship:
- User comments, sharing, public access, multi-user, custom keywords, additional notification channels, archival beyond 30 days, auto-posting summaries

StatCan cadence resolution (FEATURES.md supersedes STACK.md): Table 16-10-0019-01 (Monthly Mineral Production, metallic minerals) releases monthly, approximately the 19th-21st of M+2. Confirmed release dates: April 2025 data released June 20 2025; September 2025 data released November 20 2025; February 2026 data released April 20 2026. STACK.md referenced Table 16-10-0022 (annual data). Use Table 16-10-0019-01 (monthly). Empty-state copy must show "data through {YYYY-MM}" with snapshot_date stored in daily_summaries.raw_sources_jsonb.ontario_stats.snapshot_date.

### From ARCHITECTURE.md

New files are well-bounded: one migration (0010), dual SQLAlchemy models (scheduler + backend parity — a confirmed pattern), one FastAPI router (GET-only, auth-gated, modelled after digests.py), one agent module (daily_summary.py) calling three section builders, two ingestion modules (ontario_law.py, ontario_stats.py), and four frontend files (feed page, API hook, SummaryCard, SectionBlock). Modified files: worker.py (add lock IDs + job registrations), main.py (one include_router call), App.tsx (replace / redirect, add /queue redirect). Single CronTrigger with hour="8,12" fires the same lock ID (1017) twice daily — intentional; the 4-hour gap makes lock collision impossible.

DB schema locked decisions:
- daily_summaries has separate TEXT columns per section (gold_news_md, ontario_law_md, ontario_stats_md) plus raw_sources_jsonb JSONB for forensics
- status as VARCHAR(20) with CHECK constraint (completed | failed | partial) — not a PG enum
- agent_run_id UUID FK -> agent_runs(id) ON DELETE SET NULL
- Single index on (generated_at DESC) — table max 60 rows

### From PITFALLS.md

1. CRIT-1 — Duplicate WhatsApp from midday_digest + daily_summary both registered. In the SAME commit that registers daily_summary, remove the scheduler.add_job(...) call for midday_digest from build_scheduler(). Factory and lock ID entry can remain as dead code. Verify: midday_digest absent from scheduler.get_jobs() in startup logs.

2. CRIT-2 — Lock ID collision. ARCHITECTURE.md verified via direct grep that 1017 and 1018 are the next free IDs. PITFALLS.md proposed 1020 + 1021 with a buffer. Locked pick: 1017 (daily_summary) + 1018 (daily_summary_prune). Add startup assertion: assert len(set(JOB_LOCK_IDS.values())) == len(JOB_LOCK_IDS).

3. CRIT-3 — Multiple fires during Railway restart churn. APScheduler misfire_grace_time=1800 causes a fresh scheduler instance to fire a coalesced missed run. Three flappy restarts in the 08:00 window = three summaries + three WhatsApp messages. Fix: DB-level idempotency guard in run_daily_summary() — query for any row where generated_at >= now - 30min AND status IN ('running', 'completed'); if found, skip and log.

4. HIGH-1/HIGH-2 — Ontario law filter false positives AND false negatives. False positives: political speech accepted as enacted law. False negatives: cross-domain bills with non-obvious names (e.g., "Building Ontario Act" amends the Mining Act). Fix: use Haiku (not Sonnet), pass article body (first 1500 chars), include explicit REJECT examples, require bill_or_reg_number in structured JSON response, add synthetic test case before merge.

5. HIGH-5 — WhatsApp > 1600 chars. Do NOT use build_chunks() for daily_summary delivery. Send a teaser (< 400 chars) with link to web feed. Log len(teaser_message) and assert < 400.

---

## Phase Build Order

Recommended: 4 phases. This merges ARCHITECTURE.md's original 6 phases into a delivery cadence where every phase produces something the operator can use immediately.

The core disagreement between ARCHITECTURE.md (6 phases: DB+API -> agent + gold news -> frontend -> Ontario law -> Ontario stats -> prune) and FEATURES.md (4 phases: gold news + WhatsApp -> Ontario both -> web feed -> polish) is about when to ship the web feed. ARCHITECTURE.md defers frontend to Phase 3. FEATURES.md defers Ontario sections so web feed ships earlier.

The correct order: Ship the gold-only summary card to WhatsApp + a minimal web feed in Phase 1. Ontario sections are independent of the web feed rendering — they are TEXT columns in the same table and SectionBlock components on the same card. The feed renders whatever columns are non-null and shows empty states for null ones. Combining DB + API skeleton + agent (gold-only) + frontend into one phase adds only a few frontend files beyond ARCHITECTURE.md's Phase 1+2 combined.

---

### Phase 1: Gold News Card + Web Feed (Shippable Slice)

Rationale: Ship the highest-value piece end-to-end in one phase. Ontario sections appear as empty states. The operator can use the product on day 1 of this phase completing.

Delivers:
- Migration 0010: daily_summaries table (hand-written, no --autogenerate)
- Dual SQLAlchemy models (scheduler + backend)
- GET /summaries FastAPI router (auth-gated, returns real rows)
- Pydantic schemas with RawSource Pydantic model for JSONB write validation
- scheduler/agents/daily_summary.py — run_daily_summary() + _build_gold_news_section() (real fetch_stories(), score >= 6.0, top 5); Ontario section builders are stubs
- scheduler/worker.py — lock IDs 1017 + 1018, _make_daily_summary_job factory, daily_summary CronTrigger registered, midday_digest registration REMOVED in same commit
- WhatsApp teaser delivery (< 400 chars, link to feed) + failure alert hook wrapped in its own try/except
- frontend/src/api/summaries.ts + useSummaries() hook with refetchInterval: 5 * 60 * 1000
- SectionBlock.tsx + SummaryCard.tsx (react-markdown + rehype-sanitize)
- SummaryFeedPage.tsx
- App.tsx — / wired to feed page, /queue -> / redirect

Pitfalls addressed: CRIT-1, CRIT-2, CRIT-3, CRIT-4, HIGH-4, HIGH-5, MOD-2, MOD-3, MOD-4, MOD-5, MOD-6, MIN-1, MIN-3

Research flag: SKIP research-phase — architecture researcher verified source files directly.

---

### Phase 2: Ontario Law Ingestion

Rationale: Ontario law is the hardest new pipeline and the most time-sensitive (legislation appears any weekday the legislature is sitting). Ships before Ontario stats which is monthly and predictable.

Delivers:
- scheduler/agents/ontario_law.py — fetch_ontario_law_hits(): Ontario Newsroom RSS (primary) + NRCan RSS (secondary) + SerpAPI tertiary
- Haiku relevance filter: {"is_law": bool, "bill_or_reg_number": str|null, "reason": str, "favour_or_neutral": str}
- ontario_law_filter_model config key defaulting to "claude-haiku-4-5"
- Wire _build_ontario_law_section() in daily_summary.py (replace stub)
- Synthetic test: "Building Ontario Act amends Mining Act" -> is_law=True
- Empty-state copy: "No new Ontario mining-related laws today. Last update: {date} — {law_name}"

Pitfalls addressed: HIGH-1, HIGH-2, HIGH-6

Research flag: NEEDS source verification at build time. Verify Ontario Newsroom RSS URL before writing ingestion module. OLA bill tracker has no confirmed RSS — SerpAPI fallback already specified.

Open source research required (verify at build time, not pre-planning):
- Ontario Newsroom RSS: try https://news.ontario.ca/newsroom/en?format=rss then https://news.ontario.ca/en/releases.rss
- OMA RSS: check https://www.oma.on.ca/modules/news/en — if absent, use SerpAPI "Ontario Mining Association" site:oma.on.ca
- OLA bill tracker: no RSS confirmed; SerpAPI "Ontario bill" "Mining Act" site:ola.org is the fallback

---

### Phase 3: Ontario Stats Ingestion

Rationale: Ontario stats releases are monthly and predictable (~19th-21st of M+2). Empty state is the correct default on most days. This phase designs two distinct states (no_new_data vs error) so the operator can distinguish expected silence from broken ingestion.

Delivers:
- scheduler/agents/ontario_stats.py — fetch_ontario_stats_hits(): StatCan "The Daily" RSS monitor (trigger) + WDS API call on release day for Table 16-10-0019-01
- Two distinct empty states: no_new_data (with snapshot_date) and error (distinct visual treatment, links to agent-runs log)
- snapshot_date stored in raw_sources_jsonb.ontario_stats.snapshot_date (YYYY-MM)
- Empty-state copy: "No new production statistics released today. Next Monthly Mineral Production Survey release expected around {next_release_estimate}. Last data: {YYYY-MM} — Ontario gold production: {last_known_figure} oz."
- last_known_figure updated in JSONB each time a real StatCan release is processed
- Wire _build_ontario_stats_section() in daily_summary.py (replace stub)

Pitfalls addressed: MIN-2, HIGH-3 (frontend 404 handling)

Research flag: NEEDS one-time source setup at build time. StatCan WDS vector IDs for Ontario + Gold must be resolved by querying Table 16-10-0019-01 metadata. Documented in WDS User Guide. This is a setup step, not ongoing research.

---

### Phase 4: Prune Cron + Differentiators

Rationale: Prune is fully independent — nothing blocks on it and retention can be managed manually. Polish features require validated content in the DB from prior phases.

Delivers:
- _make_daily_summary_prune_job(engine) in scheduler/worker.py
- daily_summary_prune CronTrigger at 03:00 PT with lock ID 1018
- Cross-summary continuity: 12:00 Sonnet call receives 08:00 gold bullets in context (also resolves cross-session dedup)
- Section anchor links (id="gold-news" etc. on section headers in SectionBlock.tsx)
- "Last updated" pointer in empty-state sections
- Click-through source URLs per bullet (requires story.link stored in summary JSONB)

Pitfalls addressed: HIGH-3 (prune-vs-read race; soft-delete option if hard-delete causes UX issues)

Research flag: SKIP research-phase — prune is a trivial DELETE; cross-summary continuity is a prompt engineering addition.

---

### Phase Ordering Rationale

- Phase 1 is a combined shippable slice (DB + API + agent + frontend) because the web feed renders whatever columns are non-null and shows empty states for null ones. No technical reason to ship DB+API before frontend — they deploy together.
- Phase 2 before Phase 3 because Ontario law appears any weekday the legislature is sitting (higher urgency) while Ontario stats releases are monthly and predictable.
- Phase 4 last because prune and differentiators have zero dependencies on being early.
- Every phase ends with something the operator can read and trust.

---

## Locked Defaults

These values are locked by research and must not be re-litigated during planning:

| Decision | Locked Value | Basis |
|----------|-------------|-------|
| Lock ID: daily_summary | 1017 | ARCHITECTURE.md direct grep of JOB_LOCK_IDS — 1016 is highest current; 1017 is next free |
| Lock ID: daily_summary_prune | 1018 | ARCHITECTURE.md same grep; 1018 is next free |
| PITFALLS.md proposal (1020+1021) | REJECTED — 1017+1018 are confirmed free | Architecture researcher read the actual source file |
| WhatsApp delivery pattern | Teaser < 400 chars, link to feed — NOT full content, NOT build_chunks() | HIGH-5; web feed is the primary surface |
| Ontario law filter model | claude-haiku-4-5 via ontario_law_filter_model DB config key | HIGH-6; Sonnet at filter volume exceeds AI budget |
| Ontario stats table | Table 16-10-0019-01 (monthly, M+2 lag) — NOT Table 16-10-0022 (annual) | FEATURES.md actual release dates cited; STACK.md referenced annual table |
| StatCan empty-state copy | Must show "data through {YYYY-MM}"; snapshot_date in raw_sources_jsonb.ontario_stats.snapshot_date | Synthesis decision resolving STACK.md vs FEATURES.md |
| Ontario stats cadence | Monthly, ~19th-21st of M+2. Empty state is the DEFAULT, not an edge case. | FEATURES.md HIGH confidence — actual release dates cited |
| Sonnet char budget target | ~1200 chars for summary body; teaser bounded at < 400 chars separately | STACK.md heavy-day estimate 1700-1800 chars without constraint |
| Score threshold for gold news | >= 6.0 (broader than 7.0 sub-agent drafting threshold — summaries need coverage, not selectivity) | ARCHITECTURE.md |
| SerpAPI keywords for summary | SUMMARY_SERPAPI_KEYWORDS constant <= 10 keywords (separate from existing 17-keyword sub-agent list) | MOD-3; SerpAPI quota right at limit with 17 keywords x 2 fires/day |
| Migration 0010 | Hand-written (no --autogenerate) — ONLY op.create_table + op.create_index | MOD-2; autogenerate risks touching ApprovalState enum |
| Status column type | VARCHAR(20) with CHECK constraint — NOT a PG enum | MOD-2; PG enums are hard to modify post-creation |

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All findings verified against installed library versions and existing source files |
| Features | HIGH (gold + stats cadence), MEDIUM (Ontario law sources) | StatCan monthly cadence confirmed from actual release dates; Ontario law feed URLs require build-time verification |
| Architecture | HIGH | Architecture researcher read worker.py, content_agent.py, whatsapp.py, digests.py, and migration 0009 directly |
| Pitfalls | HIGH | Based on direct code inspection of production files; critical pitfalls grounded in specific observed behaviors |

Overall confidence: HIGH — this is a well-scoped addition to a proven system. The only genuine uncertainty is Ontario law source URLs, verified at Phase 2 build time.

### Gaps to Address

- Ontario Newsroom RSS URL: attempt two candidate URLs at Phase 2 build time. Fall back to SerpAPI if neither resolves.
- OMA RSS availability: check at Phase 2 build time. If absent, use SerpAPI. OMA is supplementary; not a blocker.
- OLA bill tracker RSS: no RSS confirmed. SerpAPI fallback specified. Not a blocker.
- StatCan WDS vector IDs for Ontario gold production: resolve once by querying Table 16-10-0019-01 metadata at Phase 3 build time.
- Twilio sandbox vs production: move to production Twilio sender before v2.0 go-live. Sandbox session expires after 24h inactivity; send_whatsapp_message returns None on lapsed session, indistinguishable from success. Flag for Phase 1 deploy checklist.

---

## Sources

### Primary (HIGH confidence — direct code inspection or official docs)

- /Users/matthewnelson/seva-mining/scheduler/worker.py — JOB_LOCK_IDS (1005, 1010-1016 confirmed), midday_digest registration, misfire_grace_time=1800
- /Users/matthewnelson/seva-mining/scheduler/agents/content_agent.py — fetch_stories() return shape, score field, cache bucket, model constants
- /Users/matthewnelson/seva-mining/scheduler/services/whatsapp.py — send_whatsapp_message signature, build_chunks() 1500-char safety margin
- /Users/matthewnelson/seva-mining/backend/app/routers/digests.py — auth pattern confirmed
- StatCan Table 16-10-0019-01 confirmed release dates: June 20 2025, Nov 20 2025, April 20 2026
- react-markdown npm 10.1.0: https://www.npmjs.com/package/react-markdown
- rehype-sanitize npm 6.0.0: https://www.npmjs.com/package/rehype-sanitize
- APScheduler 3.11.2 CronTrigger + DST: https://apscheduler.readthedocs.io/en/3.x/modules/triggers/cron.html
- StatCan WDS API: https://www.statcan.gc.ca/en/developers/wds/user-guide
- Twilio 1600-char cap: https://help.twilio.com/articles/360033806753

### Secondary (MEDIUM confidence — inferred from standard patterns or partially confirmed)

- Ontario Newsroom RSS URL: unconfirmed; verify at Phase 2 build time
- Ontario Regulatory Registry RSS: standard Drupal pattern; verify at Phase 2 build time
- StatCan WDS endpoint pattern: confirmed from developer docs; vector IDs require one-time resolution
- SerpAPI 5,000-6,000 searches/month on $50 plan: community sources
- Twilio non-template 1024-char limit: sandbox behaviour differs; test before treating as hard ceiling

### Tertiary (LOW confidence — requires build-time verification)

- OMA RSS at oma.on.ca/modules/news/en: not confirmed; check at Phase 2 build time
- OLA bill tracker RSS: no RSS confirmed; SerpAPI fallback specified

---
*Research completed: 2026-05-05*
*Ready for roadmap: yes*
