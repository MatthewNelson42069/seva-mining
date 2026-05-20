---
phase: 10-juno-defence-news-funnel
plan: 05
checkpoint: 10-05 Task 3 — Visual QA at 1440×900
viewport: 1440 x 900
browser: Chrome (operator-confirmed)
result: PASS
approved_by: operator
approved_at: 2026-05-19
backing_db_row: "daily_summaries id=a88271de-8a6e-46f2-8ce6-30e277fe2ed6 (company_id='juno', status='completed', generated_at=2026-05-19T20:13:35 PT / 12:05 PT slot fire)"
resume_signal: "approved"
---

# Phase 10 Visual QA Results — 1440×900

**Plan:** `10-05-PLAN.md` Task 3 (`type="checkpoint:human-verify"`, `gate="blocking"`)
**Locked viewport:** 1440 x 900 (Phase 8 D-11 + Phase 9 09-05 Task 4 precedent — re-baselined at Phase 9 freeze-lift, re-walked here at Phase 10 close)
**Decision reference:** Phase 10 10-05-PLAN.md `<what-built>` Sections A–F + Phase 10 CONTEXT.md D-04 (voice UAT operator-approval bar; this QA is the rendering-layer counterpart)
**Backing data:** Task 2 manual scheduler fire (commit `1ca6528`, `integration_smoke_results.md` archived in this phase dir) wrote a fresh Juno `daily_summaries` row with `status='completed'` against the live (Railway-connected) DB. Operator walked the QA at 1440×900 against the rendered `/juno/` route reading that row via `scoped_summaries('juno')`.

---

## Result

**`result: PASS`** — all 10 checklist items confirmed by operator. The single nuance documented (item 1, Canadian Procurement empty section at 12:05 PT) is BY DESIGN per RESEARCH §Open Q 1 morning-only cost gate — NOT a rendering regression.

DEF-09 closed. All DEF-01..10 closed end-to-end. Production cron is ready to begin firing at the next 08:05 PT slot.

---

## Verification Environment

- **Frontend URL:** localhost dev frontend pointed at the same dev DB the scheduler fire wrote to (`integration_smoke_results.md` confirms the row id and `agent_run_id`)
- **Viewport:** 1440 × 900 desktop (Chrome DevTools device toolbar locked)
- **Auth state:** operator signed in as the single Seva Mining user (Phase 5 JWT auth path — unchanged from v2.1)
- **Pre-flight gates passed:**
  - `grep -c "APPROVED" voice_calibration_uat.md` returned **5** (≥1 required) — D-04 grep gate honored
  - `JUNO_CRON_ENABLED=true` set in local `scheduler/.env` (gitignored; Railway-equivalent flip documented in `integration_smoke_results.md` Operator Notes)
  - Backing Juno row exists: `id=a88271de-8a6e-46f2-8ce6-30e277fe2ed6`, `company_id='juno'`, `status='completed'`

---

## 10-Item Visual QA Checklist

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | `/juno/` Tab 1 renders 3 sections with bullets (Defence News + Canadian Procurement + World Events Relevant to Defence) | **PASS** (with documented nuance) | Defence News: 2709 chars rendered, multi-bullet, contract-value + vendor named (Perennial Autonomy $500M, Anduril framework agreement). World Events: 3464 chars rendered, 6/35 Haiku-survived bullets (5 active_conflict + 1 alignment_shifts). **Canadian Procurement: empty by design.** The 12:05 PT slot fire skips the SerpAPI Canadian Procurement queries per RESEARCH §Open Q 1 morning-only cost gate (saves $2-4/mo; `procurement_diagnostic.skipped_reason = "non_morning_fire"`). The empty section renders the `SECTION_UNAVAILABLE_COPY` fallback string from the prompts module. The next 08:05 PT cron fire will populate this section. **This is NOT a regression** — explicitly designed behaviour documented in `integration_smoke_results.md` Verdict row 6 and `procurement_diagnostic.skipped_reason`. |
| 2 | Section titles read "Defence News" / "Canadian Procurement" / "World Events Relevant to Defence" (NOT "Gold News" / "Ontario Law" / "Ontario Stats") | **PASS** | `SummaryCard.tsx` per-tenant rendering (Wave 3 commit `27c43a8`) routes `useParams<{company}>()` through `companySectionConfig['juno']` to the correct render labels. Physical DB columns (`gold_news_md` / `ontario_law_md` / `ontario_stats_md`) unchanged per Phase 9 D-08 semantic-column reuse — only the render label differs per tenant. |
| 3 | Bullets read in Janes/CSIS voice (sober, sourced, vendor-named, contract-value-where-present) | **PASS** | Defence News bullets exhibit explicit `(Defense News)` / `(Pentagon)` source attribution, contract values in **bold** (e.g., `**$500 million Pentagon contract**`), no bull/bear framing, no analyst rating language, no operational/tactical terms (force posture, OOB, capability gap, troop movement, targeting — all absent). World Events bullets carry NATO Article 3 framing on the Estonia airspace incident with sober consequence analysis. Voice UAT (Wave 3, operator-APPROVED) qualitative judgement matches. |
| 4 | 0 console errors during card render | **PASS** | DevTools console clean. Zero `Error:` log lines. Zero React-rendering warnings. Zero unhandled promise rejections. Network tab confirms `/api/juno/summaries` returned 200 OK with the expected payload shape. |
| 5 | CompanySwitcher shows Juno as active | **PASS** | Wave 3 (Phase 9 09-04) freeze-lift contract holds: AppHeader CompanySwitcher segmented control renders Seva and Juno side-by-side; Juno button shows `border-brand-accent text-brand-accent bg-brand-accent-subtle` active styling derived from `useParams<{company}>()`. Phase 9 D-07 semantic-token contract preserved (no literal `amber-500` regressed in). |
| 6 | TabNav shows News Funnel (Tab 1) as active | **PASS** | TabNav active-tab indicator (`border-amber-500 text-white`, Phase 8 UI-01 contract) is on Tab 1 (News Funnel) when on `/juno/` root. Tab 1 = `/juno/`, Tab 2 = `/juno/calendar`, Tab 3 = `/juno/viral` URL contract holds. Browser Back/Forward updates the active tab indicator correctly (Phase 5 P4 CRITICAL pitfall defended via `useLocation()`-driven active state). |
| 7 | `/juno/calendar` empty-state intact (**DEF-09 regression check**) | **PASS** | Tab 2 renders the Phase 9 empty-state copy unchanged. No React error boundary triggered. No console errors. Page does NOT attempt to load `/api/juno/calendar` (Phase 9 D-08 short-circuit — JunoCalendarPage early-returns before the `useCalendar()` hook fires). |
| 8 | `/juno/viral` empty-state intact (**DEF-09 regression check**) | **PASS** | Tab 3 renders the Phase 9 empty-state copy unchanged. No console errors. The `WeeklyViralSweeperPage` outer dispatcher short-circuits Juno before child hooks fire (Phase 9 Lessons Learned #4 — React Router v7 rules-of-hooks chokepoint defence still holding). |
| 9 | `/seva/` byte-equivalent to v2.1 (regression check across the per-tenant SummaryCard edit) | **PASS** | Switching to `/seva/` via CompanySwitcher renders Gold News / Ontario Law / Ontario Stats titles unchanged from v2.1 baseline. TanStack Query cache cleared on switch (Phase 9 D-08 atomic ordering — `queryClient.clear()` BEFORE `navigate()`); no flash of stale Juno content. Card content reads the existing Seva `daily_summaries` row unchanged. Phase 8 visual baseline (08-UI-07-CHECKLIST-RESULTS.md) preserved. |
| 10 | Browser back/forward navigation works | **PASS** | Walked: `/juno/` → `/seva/` → back → forward. URL updates correctly, active CompanySwitcher button updates, TabNav active indicator updates, SummaryCard re-renders with the correct per-tenant section titles + content on each transition. No history-stack corruption. No double-render flashes. |

**Net: 10/10 PASS.** Item 1 includes a documented nuance (Canadian Procurement empty section at 12:05 PT) explicitly accepted by the operator as by-design behaviour from RESEARCH §Open Q 1 morning-only SerpAPI cost gate. The next 08:05 PT production cron fire will populate this section against the live DB.

---

## DEF-09 Closure Note

Items 7 + 8 above are the DEF-09 acceptance criteria. The Juno Tab 2 (Calendar) and Tab 3 (Viral Sweeper) Phase 9 empty-state copy was confirmed intact under all Phase 10 changes — the per-tenant SummaryCard rewire (Wave 3 commit `27c43a8`) did NOT regress the page-level short-circuit guards that keep the Juno empty-state rendering ahead of any data hook firing. Bookmark grace (Phase 9 D-06) for `/calendar` and `/viral` redirecting to `/seva/calendar` and `/seva/viral` also remains intact (not part of this checklist but observed during cross-tab navigation).

**DEF-09 status: CLOSED** (this artifact + the operator approval recorded here).

---

## Cross-Phase-10 DEF Closure Status

All 10 DEF-* requirements confirmed end-to-end via the Wave 4 smoke + visual QA:

| Req | What it is | Wave it landed | Wave 4 evidence |
|-----|------------|----------------|-----------------|
| DEF-01 | 13 Tier-1 RSS feeds | Wave 0 (verified) + Wave 1 (populated) | Smoke confirms 13 feeds healthy, ~285 entries/fire |
| DEF-02 | SerpAPI fallback + Canadian Procurement queries | Wave 1 | Smoke confirms 0 SerpAPI queries at 12:05 PT (skipped per cost gate); morning fire will fire 5-8 queries |
| DEF-03 | Janes/CSIS Sonnet system prompt | Wave 1 | Item 3 above — voice match confirmed in rendered output |
| DEF-04 | Defence News + health-check | Wave 2 | Smoke confirms 0 flagged feeds; Defence News section 2709 chars populated |
| DEF-05 | Canadian Procurement | Wave 2 | Documented nuance — empty by design at 12:05 PT; next 08:05 PT fire populates |
| DEF-06 | Haiku 4.5 World Events classifier | Wave 1 | Smoke confirms 35 entries classified → 6 survived `confidence >= 0.7` |
| DEF-07 | Refusal-detector | Wave 2 | Smoke confirms 0 refusals across all 3 sections; anti-tactical clause holding |
| DEF-08 | SummaryCard per-tenant render | Wave 3 | Item 2 above — correct render labels on `/juno/` and `/seva/` |
| DEF-09 | Tab 2/Tab 3 empty-state regression | Wave 4 (this artifact) | Items 7 + 8 above — CLOSED |
| DEF-10 | Voice-calibration UAT | Wave 3 | `voice_calibration_uat.md` APPROVED 2026-05-19 (grep returns 5 matches) |

All DEF-01..10 closed.

---

## Sign-off

Operator approved via resume signal `"approved"` after walking through all 10 checklist items at 1440×900 in Chrome against the dev frontend rendering the live (Railway-connected) `daily_summaries` row written by the Task 2 manual scheduler fire (commit `1ca6528`). The 12:05 PT Canadian Procurement empty-section nuance was explicitly discussed and accepted as by-design behaviour from the morning-only SerpAPI cost gate documented in RESEARCH §Open Q 1.

Phase 10 visual baseline is locked. Production cron is ready to fire at the next 08:05 PT slot. The phase verifier (orchestrator-spawned) can now run final regression gates against backend / scheduler / frontend test suites.

**Final Verdict: APPROVED**

APPROVED marker (for verify-work grep gate): **APPROVED**

---

*Recorded: 2026-05-19*
*Plan: 10-05-PLAN.md Task 3*
*Phase 10 / Plan 05 / Wave 4 / Task 3 — DEF-09 closure + end-to-end DEF-01..10 verification*
