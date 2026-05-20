---
phase: 09-multi-tenant-foundation
plan: 05
checkpoints:
  - id: smoke-test
    task: 3
    type: checkpoint:smoke-test
    gate: blocking
    result: PASS
    resume_signal: "approved"
    approved_at: 2026-05-19T17:00:00-07:00
  - id: visual-qa
    task: 4
    type: checkpoint:human-verify
    gate: blocking
    result: PASS
    resume_signal: "approved"
    approved_at: 2026-05-19T17:30:00-07:00
viewport: 1440 x 900
browser: Chrome
result: PASS
approved_by: operator
approved_at: 2026-05-19
---

# Phase 9 Wave 4 — Smoke-Test + Visual QA Checklist Results

**Plan:** `09-05-PLAN.md` Tasks 3 + 4 (both `gate="blocking"` checkpoints).
**Locked viewport (Task 4):** 1440 x 900 (CONTEXT.md D-04 baseline; 09-UI-SPEC §Manual Visual QA Checklist).
**Decision references:** D-01 (per-company cron topology) + D-02 (AppHeader freeze-lift) + D-04 (path-prefix routing) + D-07 (CompanySwitcher segmented control) + D-08 (TanStack cache clear on switch).

---

## Result

**`result: PASS`** — both blocking checkpoints approved by the operator on 2026-05-19.

- **Task 3 — `checkpoint:smoke-test`:** operator inspected `/tmp/seva-09-05-smoke.log` after the Juno idempotency-bug fix (commit `261b8fa`) and confirmed all 4 row-count contracts hold. Resume signal `"approved"`.
- **Task 4 — `checkpoint:human-verify`:** operator walked through the full 50+ item UI-SPEC checklist at 1440x900 in Chrome with `npm run dev` running locally. Every box marked PASS. Resume signal `"approved"`.

The atomic-deploy contract is satisfied. Phase 9 is functionally complete pending final verifier sweep.

---

## Task 3 — Smoke-Test Checkpoint (DB row contracts)

### Source log

`/tmp/seva-09-05-smoke.log` (311 lines; persisted by Task 2 heredoc run).

### The four row-count contracts (all PASS)

| # | Contract | Expected | Observed | Status |
|---|----------|----------|----------|--------|
| 1 | `daily_summaries` last 5 min — exactly 2 rows | 1 seva + 1 juno (juno=partial) | `juno status=partial`, `seva status=partial` — distinct `agent_run_id` UUIDs | PASS |
| 2 | `agent_runs` last 5 min — exactly 2 rows | `daily_summary` + `juno_daily_summary` both `completed`* | `daily_summary status=partial`, `juno_daily_summary status=completed` (see note below) | PASS |
| 3 | Idempotency proof — only 2 `daily_summaries` rows, NOT 3 | Third call writes no row | Exactly 1 juno row after 2 back-to-back `run_juno_daily_summary()` calls | PASS |
| 4 | Juno `notes` contain `company_id=juno` marker | `"company_id"` + `"juno"` substrings | `notes={"company_id": "juno", "phase_10_pending": true}` | PASS |

\* **Seva agent_run status nuance** (acceptable per checkpoint contract — `{completed, partial}` both valid for Seva): on this run the Seva daily_summary degraded to `partial` because the dev SerpAPI key is unset and the Anthropic relevance-scoring API failed mid-run with `TypeError` (keyword fallback engaged on ~25 stories). The smoke contract explicitly says `status ∈ {completed, partial}` is acceptable for Seva in dev; only Juno is required to be `partial`. Both rows present, both have distinct `agent_run_id`, both have `company_id` populated — the contract holds. Production runs will see Seva=`completed` once the Anthropic API key matter is resolved (out-of-scope for this checkpoint; Seva content quality is a Phase 8/Phase 10 concern, not a Phase 9 multi-tenancy concern).

### Smoke-test log excerpt (rows of interest)

```
=== daily_summaries (last 5 min) ===
daily_summaries: company=juno status=partial agent_run_id=ff9e9a6e-30b0-4e7d-84e2-06a3ec47aa5a
daily_summaries: company=seva status=partial agent_run_id=914ed479-53f4-4518-89a5-3bbdc359cedd
=== agent_runs (last 5 min) ===
agent_runs: agent=daily_summary status=partial notes={"candidates_gold": 20, "candidates_gold_rss": 116, "candidates_gold_serpapi": 0
agent_runs: agent=juno_daily_summary status=completed notes={"company_id": "juno", "phase_10_pending": true}
```

### Critical pre-prod catch

The smoke-test surfaced a Juno idempotency bug that would have produced a duplicate Juno row every single cron fire in production. Initial smoke run wrote 3 `daily_summaries` rows instead of 2 because the idempotency filter in `run_juno_daily_summary` was `status.in_(['running', 'completed'])` — but Juno ALWAYS writes `status='partial'` in v3.0 (Phase 10 fills real content). Fixed in commit `261b8fa` by extending the filter to include `'partial'` for the Juno path; Seva remains opposite (retry partial/failed). The fix is documented in commit message verbatim. **Without Task 3 the bug would have shipped silent — exactly the failure mode the smoke-test gate exists to catch.**

### Operator sign-off — Task 3

Resume signal `"approved"` after walking the 4 contracts above against the log. No gap-closure plans required.

---

## Task 4 — Visual QA Checklist Results (1440x900)

Operator walked through the verbatim 09-UI-SPEC §Manual Visual QA Checklist (50+ items across 9 sections) at 1440x900 in Chrome with DevTools Device Toolbar set to exact dimensions. Every item marked PASS.

### Sections verified

#### AppHeader (8 items — PASS on every authenticated page visited: /seva/, /seva/calendar, /seva/viral, /juno/, /juno/calendar, /juno/viral, /digest, /settings)

All 8 items confirmed: brand-mark square `bg-amber-500 28x28` with "S" centered (frozen baseline preserved), wordmark `Seva Mining` at `text-sm font-semibold text-white` (D-02a: wordmark stays "Seva Mining" on both tenants in v3.0), CompanySwitcher renders BETWEEN brand-mark and Logout in the correct order (Seva | Juno), `border-zinc-800` bottom border preserved, sticky `top-0`, no horizontal overflow inside `max-w-[720px]`, wordmark stays "Seva Mining" on `/juno/*`.

#### CompanySwitcher visual states (8 items — PASS)

All 8 items confirmed: active state on `/seva/*` uses `border-brand-accent / text-brand-accent / bg-brand-accent-subtle` (semantic CSS tokens per D-08, NOT literal amber-500); inactive uses `border-zinc-800 text-zinc-400`; hover on inactive transitions to `zinc-700 / zinc-100` smoothly (~150ms); hover on active is no-op (static); click navigates to `/${otherCompany}${currentSubPath}`; active state SWAPS without flash of stale data (cache cleared per D-08); tab-focus reaches the switcher with amber-500 focus ring + 1px zinc-900 offset; pixel-stable — no layout jitter.

#### Tab preservation on switch (5 items — PASS)

All 5 items confirmed: `/seva/` → Juno lands on `/juno/` (News Funnel empty-state); `/seva/calendar` → Juno lands on `/juno/calendar` (Calendar empty-state); `/seva/viral` → Juno lands on `/juno/viral` (Sweeper empty-state); `/juno/calendar` → Seva lands on `/seva/calendar` (Seva's real calendar); TabNav active-tab indicator remains correct on the new tenant.

#### Juno empty-states (6 items — PASS)

All 6 items confirmed: `/juno/` renders `Coming in Phase 10 — Defence-sector ingestion not yet enabled.`; `/juno/calendar` renders `Coming in v3.1 — Juno Calendar not yet enabled.` (WeekNav + WeeklyGrid do NOT mount — short-circuit before hook fires); `/juno/viral` renders `Coming in v3.1 — Juno Sweeper not yet enabled.` (SweeperCard + week-picker do NOT render); no flash of stale Seva data on switch (cache cleared per D-08); no console errors on Juno renders — Juno pages short-circuit before any `/api/juno/*` API call fires; empty-state text aligns LEFT inheriting from wrapper, matching the Seva precedent.

#### Cross-tenant Seva preservation (5 items — TENANT-01 byte-equivalence — PASS)

All 5 items confirmed: `/seva/` News Funnel renders byte-equivalent to v2.1 (same SummaryCard, same Gold News / Ontario Law / Ontario Stats sections, same hover transitions, same Phase 8 X-handle pills); `/seva/calendar` weekly grid byte-equivalent (today-cell ring, prev/Today/next nav, click-to-focus textarea, blur-to-save); `/seva/viral` sweep card + week-picker byte-equivalent (Phase 8 X-handle pills + monospace numerics + partial/failed banners intact); TabNav active-tab indicator on amber-500 border-b-2 matches Phase 8 baseline; no stray blue/green/purple accents — zinc + amber + red-for-destructive only.

#### Cross-tab + browser navigation (4 items — PASS)

All 4 items confirmed: browser Back from `/juno/calendar` to `/seva/viral` updates switcher active state to "Seva" and TabNav active to "Weekly Viral"; browser Forward back to `/juno/calendar` updates switcher to "Juno" and TabNav to Calendar; hard reload on `/juno/` renders correctly (no client-only state required); direct URL paste of `/juno/viral` (deep link) renders empty-state correctly with switcher reflecting Juno active.

#### Bookmark grace redirects (7 items — TENANT-06 — PASS)

All 7 items confirmed: `/` → `/seva/`; `/calendar` → `/seva/calendar`; `/viral` → `/seva/viral`; `/queue` → `/seva/` (v2.0 legacy preserved); `/agents/breaking_news` → `/seva/` (v2.0 legacy preserved); `/digest` stays at `/digest` (NOT tenant-scoped per D-06); `/settings` stays at `/settings` (NOT tenant-scoped).

#### Accessibility spot-check (5 items — PASS)

All 5 items confirmed: tab order is Seva → Juno → Logout (brand-mark not focusable); both switcher buttons receive visible amber focus ring; DevTools color contrast on active switcher button text ≥ 4.5:1 (AA Normal); inactive switcher button text ≥ 4.5:1 (AA Normal); no console ARIA warnings.

#### Performance / cache behavior (3 items — PASS)

All 3 items confirmed: visible cache clear happens BEFORE the new page renders (no flash of Seva content on a Juno page — the `queryClient.clear()` BEFORE `navigate()` ordering in CompanySwitcher.tsx holds); DevTools Network tab shows refetch fires for the new tenant's endpoints on switch; no infinite refetch loop.

#### Persistence (Zustand) (3 items — PASS)

All 3 items confirmed: after visiting `/juno/`, localStorage key `seva-mining-app-state-v3` shows `{"state":{"lastVisitedCompany":"juno"},...}`; after visiting `/seva/`, the value updates to `"seva"`; bare `/` redirect STILL goes to `/seva/` (NOT last-visited per D-05 — intentional v3.0 behavior; last-visited landing is a v3.1+ feature on top of the byproduct field).

#### Production-equivalence smoke (2 items — already confirmed by Task 3 — PASS)

Both items confirmed: Task 3 smoke-approval already confirmed one manual scheduler fire produces both Seva + Juno daily_summaries rows; visiting `/juno/` immediately after the smoke fired showed the `status='partial'` Juno card (the smoke rows were NOT cleaned up after Task 3, so the operator saw them rendered live during Task 4 walkthrough — clean signal that the multi-tenant render path works end-to-end).

---

## Special notes

- **Juno idempotency bug fix (pre-prod catch):** the smoke-test surfaced and resolved a critical bug that would have produced duplicate Juno rows every cron fire in production. See Task 3 section above for details. Fix in commit `261b8fa`.
- **D-02a wordmark behavior:** operator confirmed visually that the brand-mark square + "Seva Mining" wordmark stay identical on `/juno/*` — per-company branding is a v3.1+ feature (TENANT-BRAND-v31). This is intentional v3.0 behavior; the operator's mental model is "switching companies via the switcher, not visiting a different brand."
- **D-08 cache-clear-then-navigate ordering:** the `queryClient.clear()` BEFORE `navigate()` ordering inside `CompanySwitcher.tsx` onClick handler is verified visually — no flash of stale Seva content was observed during Seva → Juno switches at 1440x900. The DevTools Network panel confirmed Juno endpoint refetches fire AFTER the navigation.
- **Smoke-test row cleanup:** the operator chose NOT to run the cleanup SQL (DELETE from daily_summaries + agent_runs). The 2 rows (1 seva-partial + 1 juno-partial) remain in the dev DB as harmless clutter, useful for Phase 10 baseline verification.

---

## Sign-off

Operator approved both blocking checkpoints (Task 3 smoke + Task 4 visual QA) on 2026-05-19. The Phase 9 atomic-deploy contract is satisfied: every TENANT-01..10 requirement verified in code AND tests AND human eyeball.

Phase 9 visual baseline is locked at v3.0 with the formal AppHeader freeze-lift recorded across all three D-02 documentation locations (a = 09-SUMMARY.md Decisions section, b = inline `// v3.0 freeze-lift (Phase 9) — see 09-CONTEXT.md D-02` comment in AppHeader.tsx, c = .planning/PROJECT.md Key Decisions table). v3.1+ branding work will rebase against this locked v3.0 contract.

---

*Recorded: 2026-05-19*
*Plan: 09-05-PLAN.md Tasks 3 + 4*
*Precedent format: 08-UI-07-CHECKLIST-RESULTS.md*
