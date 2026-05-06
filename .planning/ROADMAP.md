# Roadmap: Seva Mining v2.0 — Daily Summary Feed

## Overview

Four phases deliver a 2x-daily gold intelligence digest: a combined shippable slice ships
the full stack end-to-end in Phase 1 (DB + API + gold-only agent + web feed + WhatsApp),
Ontario law ingestion completes the hardest new pipeline in Phase 2, Ontario stats completes
the third section in Phase 3, and operations hardening (prune cron + observability) closes
the milestone in Phase 4. Every phase ends with something the operator can open in a browser
or read on WhatsApp.

**Milestone:** v2.0 Daily Summary Feed
**Phase numbering:** Reset — v1.0.1 phases archived to `.planning/milestones/v1.0.1/phases/`

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3, 4): Planned milestone work (reset for v2.0)
- Decimal phases: Urgent insertions via `/gsd:insert-phase` only

- [ ] **Phase 1: Gold News Card + Web Feed** - Full-stack shippable slice: DB migration, dual models, GET /summaries, daily_summary cron with real gold-news section + Ontario stubs, WhatsApp teaser + failure alert, web feed page, midday_digest retirement
- [ ] **Phase 2: Ontario Law Ingestion** - Real ontario_law.py module (3 concurrent sources), Haiku relevance filter with explicit REJECT examples, _build_ontario_law_section() wired, synthetic test, last_known_law empty-state continuity
- [ ] **Phase 3: Ontario Stats Ingestion** - Real ontario_stats.py module (StatCan The Daily RSS trigger + WDS API pull on release days), monthly cadence, snapshot persistence, two distinct empty states (no_new_data vs error)
- [ ] **Phase 4: Prune Cron + Operations Hardening** - daily_summary_prune cron at 03:00 PT (lock 1018), /agent-runs telemetry verification, retire-via-deregistration audit

## Phase Details

### Phase 1: Gold News Card + Web Feed
**Goal**: Operator can read a gold-news summary card in a browser and receive a WhatsApp teaser within minutes of the 08:00 PT cron firing; Ontario sections render as stubs
**Depends on**: Nothing (first phase)
**Requirements**: SUM-01, SUM-02, SUM-03, SUM-04, SUM-05, SUM-06, GOLD-01, GOLD-02, GOLD-03, FEED-01, FEED-02, FEED-03, FEED-04, FEED-05, FEED-06, WHA-01, WHA-02, WHA-03, OPS-02
**Success Criteria** (what must be TRUE):
  1. The 08:00 PT cron fires on a weekday morning and writes a `daily_summaries` row with `status='completed'` and `notes.candidates_gold > 0` visible in the agent_runs log
  2. The WhatsApp teaser arrives within 2 minutes of cron fire, is under 400 chars, and contains a link to the feed — no build_chunks multi-part messages
  3. Navigating to `/` in the browser shows the summary card with a "Gold News" section containing real headlines and bullets; Ontario Law and Ontario Stats sections show stub empty-state text
  4. Navigating to `/queue` redirects to `/` without a 404; startup logs show `midday_digest` absent from `scheduler.get_jobs()` output
  5. Two rapid scheduler restarts within 30 minutes produce exactly one `daily_summaries` row (idempotency guard works); the lock-ID uniqueness assertion passes at startup with no AssertionError
**Plans**: TBD
**UI hint**: yes

### Phase 2: Ontario Law Ingestion
**Goal**: The Ontario Law section on the summary card shows real legislative hits on sitting days and renders a contextual empty state (with last known law) on quiet days
**Depends on**: Phase 1
**Requirements**: LAW-01, LAW-02, LAW-03, LAW-04
**Success Criteria** (what must be TRUE):
  1. The synthetic test case "Building Ontario Act amends Mining Act" passed through the Haiku filter returns `is_law=True` and a non-null `bill_or_reg_number`
  2. On a day the Ontario legislature is sitting, the Ontario Law section contains at least one bullet citing a specific bill or regulation number (not a ministerial speech)
  3. On a quiet day (legislature in recess or no relevant items), the Ontario Law section renders "No new Ontario mining-related laws today. Last update: {date} — {law_name}." using the stored `last_known_law` JSONB field — not a blank section
  4. The Haiku filter model config key is confirmed as `claude-haiku-4-5` in the DB config — not Sonnet — and the filter prompt contains explicit REJECT examples for ministerial speeches
**Plans**: TBD

### Phase 3: Ontario Stats Ingestion
**Goal**: The Ontario Stats section shows the latest StatCan production figure on release days (~19th-21st of M+2) and renders a date-anchored empty state on all other days; an error state is visually distinct from the no-data state
**Depends on**: Phase 2
**Requirements**: STAT-01, STAT-02, STAT-03, STAT-04, STAT-05
**Success Criteria** (what must be TRUE):
  1. On a StatCan release day, the summary card's Ontario Stats section shows the new Ontario gold production figure with comparison to the prior period, sourced from the WDS API pull
  2. On any non-release day (the default — roughly 29/30 days per month), the Ontario Stats section renders "No new production statistics released today. Next Monthly Mineral Production Survey release expected around {date}. Last data: {YYYY-MM} — Ontario gold production: {figure} oz." — not a blank section
  3. When the StatCan WDS API call fails (ingestion error), the section renders a visually distinct error state that links to the agent-runs log — distinguishable from the expected no-data state without opening the DB
  4. The `snapshot_date` (YYYY-MM) and `last_known_figure` are stored in `daily_summaries.raw_sources_jsonb.ontario_stats` so the empty-state copy renders without re-querying StatCan
**Plans**: TBD

### Phase 4: Prune Cron + Operations Hardening
**Goal**: The system enforces 30-day retention automatically, daily_summary telemetry is visible in the existing /agent-runs UI, and v1.0 sub-agent retirement is confirmed as cron-deregistration-only with no source code deletion
**Depends on**: Phase 3
**Requirements**: OPS-01, OPS-03, OPS-04
**Success Criteria** (what must be TRUE):
  1. The `daily_summary_prune` cron fires at 03:00 PT and deletes `daily_summaries` rows where `generated_at < NOW() - INTERVAL '30 days'`; the agent_runs log shows a `daily_summary_prune` entry with lock ID 1018 on the morning after first deploy
  2. The Settings > Agent Runs tab shows `daily_summary` run history with structured notes fields (`candidates_gold`, `sections_completed`, `whatsapp_sent`) parseable by the existing per-agent UI patterns
  3. A code audit confirms the 6 retired sub-agent modules + approval-flow components + Phase B post-to-X route exist as dead code in the repo — no source files were deleted in v2.0
**Plans**: TBD

## Phase Decomposition Rationale

### Why 4 phases instead of the research SUMMARY.md's 4 (same count, one deviation)

The SUMMARY.md recommended structure is adopted as-is with one deliberate mapping change:
**OPS-02** (lock-ID uniqueness assertion at startup) is moved from Phase 4 to Phase 1.

Rationale: OPS-02 is a one-line `assert` that must live in the same commit as the lock ID
additions to `JOB_LOCK_IDS`. Shipping it in Phase 4 — three phases after the lock IDs are
added — leaves a gap where a duplicate could be introduced silently. The assertion is a
zero-cost safety gate for CRIT-2 (advisory lock collision), which is a Phase 1 concern.
Moving it to Phase 1 costs nothing and makes the commit atomic: "add lock IDs, assert they
are unique."

### Why Phase 1 combines DB + API + agent + frontend

The web feed renders `TEXT` columns from `daily_summaries`. Those columns are null for
Ontario sections until Phases 2 and 3 complete — the feed page renders stub empty states for
null columns. No technical reason exists to ship DB+API before the frontend; they deploy
together in one Railway push. Combining them delivers a complete reading surface on day 1
of Phase 1 completion, which is strictly better than shipping a backend with no frontend for
the operator to see.

### Why Phase 2 (Ontario law) before Phase 3 (Ontario stats)

Ontario law appears any weekday the legislature is sitting (higher urgency, unpredictable).
Ontario stats releases monthly on a predictable schedule (~19th-21st of M+2). The law
section benefits from earlier shipping; the stats section is safe to defer one phase.

### Why Phase 4 (prune + operations) is last

The prune cron is fully independent — nothing in the product depends on it shipping early,
and 30-day retention can be enforced manually until Phase 4. OPS-03 (agent-runs telemetry)
requires real summary rows to verify the UI parsing — so it correctly follows Phase 1 in
execution even though it is defined in Phase 4. OPS-04 (retirement audit) is a verification
step, not a build step, and is cheapest to do once the full v2.0 feature set is in place.

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Gold News Card + Web Feed | 1/6 | In Progress|  |
| 2. Ontario Law Ingestion | 0/TBD | Not started | - |
| 3. Ontario Stats Ingestion | 0/TBD | Not started | - |
| 4. Prune Cron + Operations Hardening | 0/TBD | Not started | - |
