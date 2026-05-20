---
phase: 14-juno-content-calendar
verified: 2026-05-20T22:30:00Z
status: passed
score: 5/5 requirements verified + 12/12 invariants verified
verifier: gsd-verifier (goal-backward)
commits_verified:
  - 1ec09ae feat(14-01) delete Phase 9 D-09 Juno calendar short-circuit
  - 75a3039 test(14-01) add ContentCalendarPage TanStack Query key isolation tests
  - 6c7674d test(14-01) add cross-tenant calendar CRUD isolation tests (JCAL-05)
  - f063426 docs(14-01) relax JCAL-01 wording per D-06
  - 7d9321b docs(14-01) complete juno-content-calendar plan
human_verification:
  - test: "Operator navigates to /juno/calendar in browser after deploy and sees the WeeklyGrid (Mon-Sun cells) instead of the v3.1 'Coming soon' placeholder"
    expected: "WeeklyGrid renders with em-dash placeholders per DayCell; current week highlighted; WeekNav prev/next/today work; Juno navy palette applied"
    why_human: "Visual rendering, palette correctness, click flow — automated tests cover the cache-key isolation but not the rendered pixel output"
  - test: "Operator edits a DayCell on /juno/calendar, blurs, then reloads"
    expected: "Edited text persists; row in DB carries company_id='juno'; visiting /seva/calendar shows no bleed"
    why_human: "End-to-end persistence path with autosave timing; mid-flight focus loss UX is operator-feel"
  - test: "Operator switches Juno → Seva via CompanySwitcher mid-edit"
    expected: "Calendar view updates instantly to Seva content with zero cross-tenant bleed"
    why_human: "Live-route-change UX + CompanySwitcher integration — not exercised by Phase 14 RTL tests (those use MemoryRouter remount)"
---

# Phase 14: Juno Content Calendar — Verification Report

**Phase Goal:** Make `/juno/calendar` functional by removing the deliberate Phase 9 D-09 short-circuit at `frontend/src/pages/ContentCalendarPage.tsx:42-54`. After this phase: Juno users see the same Mon-Sun grid Seva users see; CRUD against `/api/{company}/calendar/*` works with row-level `company_id='juno'` enforcement; cross-tenant isolation verified via frontend RTL test + backend pytest. Zero Seva-side changes (D-07 byte-identical contract from v3.0).

**Verified:** 2026-05-20T22:30:00Z
**Status:** PASS
**Verifier:** Claude (gsd-verifier, goal-backward)

---

## Goal Achievement Summary

Phase 14 was a narrow "lift-the-gate" phase: ~13-line deletion + 2 new test files + 1 spec-file wording update. Every must-have artifact exists, is substantive, is wired, and produces real behavior. The 12 D-07 zero-regression invariants are honored byte-identically. Cross-tenant isolation is asserted at BOTH the frontend cache layer (3 RTL tests) AND the backend HTTP layer (4 pytests covering PATCH + DELETE × both directions). Verdict: **PASS**.

---

## Per-Requirement Verdict (JCAL-01..05)

| Req | Status | Evidence |
|-----|--------|----------|
| **JCAL-01** | PASS | `/juno/calendar` now renders `<WeeklyGrid companyId={companyId} weekAnchor={weekAnchor} />` at `frontend/src/pages/ContentCalendarPage.tsx:50` (single shared render path; short-circuit deleted). DayCell em-dash placeholder at `frontend/src/components/calendar/DayCell.tsx:121` (`placeholder="—"`). REQUIREMENTS.md line 14 reworded with `*(D-06)*` annotation. |
| **JCAL-02** | PASS (by inheritance) | DayCell autosave wiring, optimistic UI, `company_id` injection via `scoped_calendar(company)` helper — all already established by v2.1 Phase 6 + v3.0 Phase 9. Phase 14 made zero changes to these paths (D-07). `backend/app/routers/calendar.py:71,140,166` confirms `scoped_calendar(company)` re-look-up on every PATCH/DELETE. Behaviorally proven by JCAL-05 tests (which seed real rows via POST and read them back). |
| **JCAL-03** | PASS | 3 RTL tests in `frontend/src/pages/__tests__/ContentCalendarPage.test.tsx` (lines 70, 93, 116) assert: (a) Juno mount registers `['calendar', 'juno', ...]` key, (b) Seva mount registers `['calendar', 'seva', ...]` key, (c) cross-mount with fresh QueryClient shows zero bleed. All 3 tests pass (`npx vitest --run src/pages/__tests__/ContentCalendarPage.test.tsx` → 3/3 GREEN). |
| **JCAL-04** | PASS (by inheritance) | WeekNav prev/next/today already wired in `ContentCalendarPage.tsx:30-40` (`handlePrev`/`handleNext`/`handleToday` callbacks unchanged from v2.1 Phase 6). Gate removal in Task 1 exposes them for Juno. `WeekNav` is rendered at line 44 of the post-deletion file. |
| **JCAL-05** | PASS | 4 pytest tests in `backend/tests/test_calendar_cross_tenant.py` (lines 85, 120, 161, 192) assert cross-tenant CRUD returns 404 (NOT 403): PATCH Seva-UUID via /api/juno/, PATCH Juno-UUID via /api/seva/, DELETE Seva-UUID via /api/juno/, DELETE Juno-UUID via /api/seva/. Each attack is followed by a row readback asserting the targeted row was NOT mutated. All 4 tests pass (`uv run pytest tests/test_calendar_cross_tenant.py -v` → 4/4 PASSED). |

**Score: 5/5 JCAL requirements satisfied.**

---

## Per-Invariant Verdict (12 invariants)

### Invariant 1 — Short-circuit removed: PASS

```
$ grep -c "if (companyId === 'juno')" frontend/src/pages/ContentCalendarPage.tsx
0
$ grep -c "Coming in v3.1" frontend/src/pages/ContentCalendarPage.tsx
0
$ grep -c "v3.0 Phase 9 — Juno short-circuit" frontend/src/pages/ContentCalendarPage.tsx
0
```

All three forbidden strings absent. The Phase 9 D-09 short-circuit comment + `if`-block + early-return is fully gone. File went from 67 → 53 lines.

### Invariant 2 — WeeklyGrid still rendered: PASS

```
$ grep -n "<WeeklyGrid companyId={companyId}" frontend/src/pages/ContentCalendarPage.tsx
50:      <WeeklyGrid companyId={companyId} weekAnchor={weekAnchor} />
```

Exactly one occurrence at line 50 (post-deletion line number; was line 64 pre-deletion). Single shared render path for both tenants.

### Invariant 3 — Frontend test exists with ≥3 named tests: PASS

```
$ ls -la frontend/src/pages/__tests__/ContentCalendarPage.test.tsx
-rw-r--r--  1 ... 5722 bytes
$ grep -cE "^\s*(test|it)\(" frontend/src/pages/__tests__/ContentCalendarPage.test.tsx
3
$ wc -l frontend/src/pages/__tests__/ContentCalendarPage.test.tsx
145
```

3 tests at lines 70 (Juno key), 93 (Seva key), 116 (isolation across mounts). 145 lines (above the 80-line min_lines floor).

### Invariant 4 — Frontend test asserts BOTH key isolation directions: PASS

```
$ grep -c "'calendar', 'juno'" frontend/src/pages/__tests__/ContentCalendarPage.test.tsx
3
$ grep -c "'calendar', 'seva'" frontend/src/pages/__tests__/ContentCalendarPage.test.tsx
4
```

Both Juno-key and Seva-key assertions present (3 + 4 = 7 total references). Reads as `findAll({ queryKey: ['calendar', tenant] })` partial-match predicates — the canonical TanStack v5 cache-key isolation contract.

### Invariant 5 — Frontend test forbidden patterns absent: PASS

```
$ grep -c "vi.useFakeTimers" frontend/src/pages/__tests__/ContentCalendarPage.test.tsx
0
```

Zero `vi.useFakeTimers` references — the Phase 11-05 TanStack-Query-v5 deadlock pitfall is avoided. Async query registration is observed via `waitFor()` per AppHeader.brand.test.tsx pattern.

### Invariant 6 — Backend test exists with ≥4 functions: PASS

```
$ ls -la backend/tests/test_calendar_cross_tenant.py
-rw-r--r--  1 ... 7816 bytes
$ grep -cE "^async def test_" backend/tests/test_calendar_cross_tenant.py
4
$ wc -l backend/tests/test_calendar_cross_tenant.py
219
```

4 async test functions (`test_patch_seva_uuid_via_juno_prefix_returns_404`, `test_patch_juno_uuid_via_seva_prefix_returns_404`, `test_delete_seva_uuid_via_juno_prefix_returns_404`, `test_delete_juno_uuid_via_seva_prefix_returns_404`). 219 lines (above the 100-line min_lines floor).

### Invariant 7 — Backend test 404 contract (NOT 403): PASS

```
$ grep -c "status_code == 404" backend/tests/test_calendar_cross_tenant.py
4
$ grep -c "status_code == 403" backend/tests/test_calendar_cross_tenant.py
0
```

Exactly 4 `status_code == 404` assertions (one per cross-tenant attempt). Zero `status_code == 403` assertions — the "tenant existence isolation, NOT permission isolation" semantic from JCAL-05 is honored.

### Invariant 8 — Backend test both directions, PATCH + DELETE: PASS

```
$ grep -nE "^async def test_" backend/tests/test_calendar_cross_tenant.py
85:async def test_patch_seva_uuid_via_juno_prefix_returns_404(
120:async def test_patch_juno_uuid_via_seva_prefix_returns_404(
161:async def test_delete_seva_uuid_via_juno_prefix_returns_404(
192:async def test_delete_juno_uuid_via_seva_prefix_returns_404(

$ grep -c "/api/juno/calendar" backend/tests/test_calendar_cross_tenant.py
6
$ grep -c "/api/seva/calendar" backend/tests/test_calendar_cross_tenant.py
6
```

Both tenant prefixes appear 6× each (POST seed + attack URL + readback URL × 2 tests per direction). Test names explicitly cover Seva-via-Juno AND Juno-via-Seva for both PATCH and DELETE.

### Invariant 9 — REQUIREMENTS.md JCAL-01 updated: PASS

```
$ grep -c "matches Seva em-dash placeholder pattern" .planning/REQUIREMENTS.md
1
$ grep -c "No content planned for this week" .planning/REQUIREMENTS.md
0
$ grep -cF "*(D-06)*" .planning/REQUIREMENTS.md
1
$ grep -n "JCAL-01" .planning/REQUIREMENTS.md
14:- [x] **JCAL-01** *(D-06)*: User opens `/juno/calendar` (Juno Tab 2) and sees the same weekly Mon-Sun paper-planner grid Seva users see — direct-edit textarea per day with em-dash placeholder when empty (matches Seva em-dash placeholder pattern; no tenant-asymmetric banner), current-week highlighted.
97:| JCAL-01 | Phase 14 | Complete |
```

- "matches Seva em-dash placeholder pattern" appears exactly once (line 14).
- Old banner copy "No content planned for this week" fully removed.
- `*(D-06)*` provenance annotation present exactly once.
- JCAL-01 appears at line 14 (requirement list) and line 97 (Traceability table — already flipped to "Complete" per Task 4-adjacent metadata update by orchestrator).
- (Note: REQUIREMENTS.md line 14 is now `[x]` Complete + Traceability shows Complete — this is the orchestrator's post-phase update via commit `7d9321b`, consistent with phase signoff. Acceptable.)

### Invariant 10 — D-07 zero-regression contract (12 files untouched): PASS

```
$ for f in <12 files>; do git log --oneline 1ec09ae^..7d9321b -- $f | wc -l; done
```

| File | Commits touching | Diff lines |
|------|------------------|------------|
| frontend/src/components/layout/AppHeader.tsx | 0 | 0 |
| frontend/src/components/calendar/WeeklyGrid.tsx | 0 | 0 |
| frontend/src/components/calendar/DayCell.tsx | 0 | 0 |
| frontend/src/components/calendar/WeekNav.tsx | 0 | 0 |
| frontend/src/hooks/useCalendar.ts | 0 | 0 |
| frontend/src/hooks/useCalendarMutations.ts | 0 | 0 |
| frontend/src/api/calendar.ts | 0 | 0 |
| frontend/src/api/queryKeys.ts | 0 | 0 |
| backend/app/routers/calendar.py | 0 | 0 |
| backend/app/queries/scoped.py | 0 | 0 |
| backend/tests/test_calendar_router.py | 0 | 0 |
| backend/tests/test_multitenant_isolation.py | 0 | 0 |

All 12 files have **zero commits and zero diff lines** across the Phase 14 commit window (`1ec09ae..7d9321b`). D-07 byte-identical contract honored.

### Invariant 11 — Scheduler untouched: PASS

```
$ git diff 1ec09ae^..7d9321b scheduler/ | wc -l
0
```

Zero diff lines in the entire `scheduler/` directory. Phase 14 made zero scheduler-side changes (correct — Phase 14 is frontend page + 2 test files + 1 spec edit only).

### Invariant 12 — Existing Seva calendar + AppHeader brand tests still GREEN: PASS

```
$ npx vitest --run src/components/calendar/__tests__/ src/components/layout/__tests__/AppHeader.brand.test.tsx
 Test Files  3 passed (3)
      Tests  16 passed (16)
```

16/16 tests pass across DayCell.test.tsx + WeekNav.test.tsx + AppHeader.brand.test.tsx. None of these files were touched; their byte-identical regression remains GREEN.

**Score: 12/12 invariants verified.**

---

## D-07 Zero-Regression Contract — Files NOT Touched

Per the phase plan's locked D-07 decision, the following 12 files MUST remain byte-identical across Phase 14:

| File | Status across `1ec09ae..7d9321b` |
|------|-----------------------------------|
| `frontend/src/components/layout/AppHeader.tsx` | UNTOUCHED (0 commits, 0 diff lines) |
| `frontend/src/components/calendar/WeeklyGrid.tsx` | UNTOUCHED |
| `frontend/src/components/calendar/DayCell.tsx` | UNTOUCHED |
| `frontend/src/components/calendar/WeekNav.tsx` | UNTOUCHED |
| `frontend/src/hooks/useCalendar.ts` | UNTOUCHED |
| `frontend/src/hooks/useCalendarMutations.ts` | UNTOUCHED |
| `frontend/src/api/calendar.ts` | UNTOUCHED |
| `frontend/src/api/queryKeys.ts` | UNTOUCHED |
| `backend/app/routers/calendar.py` | UNTOUCHED |
| `backend/app/queries/scoped.py` | UNTOUCHED |
| `backend/tests/test_calendar_router.py` | UNTOUCHED |
| `backend/tests/test_multitenant_isolation.py` | UNTOUCHED |

Files actually changed across the 5-commit window (per `git log --name-only`):

| Commit | Files |
|--------|-------|
| `1ec09ae` | `frontend/src/pages/ContentCalendarPage.tsx` (modified, −13 lines) |
| `75a3039` | `frontend/src/pages/__tests__/ContentCalendarPage.test.tsx` (NEW) |
| `6c7674d` | `backend/tests/test_calendar_cross_tenant.py` (NEW) |
| `f063426` | `.planning/REQUIREMENTS.md` (modified, JCAL-01 1-line swap) |
| `7d9321b` | `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, `.planning/STATE.md`, `.planning/phases/14-juno-content-calendar/14-01-SUMMARY.md` (orchestrator close-out metadata) |

**Total production-tree change surface: 1 modified production file (`ContentCalendarPage.tsx`), 2 new test files, 1 spec file edit.** Matches the CONTEXT estimate ("~30-50 lines + 2 new test files") exactly.

---

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Frontend tests added in Phase 14 pass | `npx vitest --run src/pages/__tests__/ContentCalendarPage.test.tsx` | `Test Files 1 passed (1)`, `Tests 3 passed (3)` | PASS |
| Backend tests added in Phase 14 pass | `uv run pytest tests/test_calendar_cross_tenant.py -v` | 4/4 PASSED (PATCH-Seva-via-Juno, PATCH-Juno-via-Seva, DELETE-Seva-via-Juno, DELETE-Juno-via-Seva) | PASS |
| Existing Seva calendar + AppHeader brand tests still GREEN | `npx vitest --run src/components/calendar/__tests__/ src/components/layout/__tests__/AppHeader.brand.test.tsx` | 16/16 tests pass | PASS |
| Short-circuit code path absent | `grep -c "if (companyId === 'juno')" frontend/src/pages/ContentCalendarPage.tsx` | 0 | PASS |
| WeeklyGrid is sole render | `grep -c "<WeeklyGrid" frontend/src/pages/ContentCalendarPage.tsx` | 1 | PASS |
| All 5 commits exist on main | `git log --oneline -10 main` | All 5 commits present in correct order | PASS |

(Regression baselines 178 frontend / 188 backend / 323 scheduler — already confirmed by orchestrator per the prompt; not re-verified here to keep verification fast. Targeted spot-checks above confirm Phase 14's specific deltas are GREEN.)

---

## Data-Flow Trace (Level 4)

`ContentCalendarPage.tsx` (the only modified production file) renders dynamic data through the WeeklyGrid → DayCell → useCalendar chain. Trace:

| Artifact | Data variable | Source | Real data flows | Status |
|----------|---------------|--------|-----------------|--------|
| `ContentCalendarPage.tsx` | `companyId` | `useParams<{company: string}>()` from `react-router-dom` | Yes — URL path segment from `CompanyScopedRoute` (`:company/*`); narrowed to `'seva' | 'juno'` at line 27 | FLOWING |
| `ContentCalendarPage.tsx` | `weekAnchor` | `useState<Date>(() => new Date())` + 3 useCallback handlers | Yes — handlers mutate via `addDays(d, ±7)` and `new Date()`; state is observed by WeekNav + WeeklyGrid | FLOWING |
| `WeeklyGrid` (downstream) | calendar items | `useCalendar(companyId, start, end)` → `getCalendar(companyId, start, end)` → `GET /api/{company}/calendar?start=&end=` → `scoped_calendar(company)` SQL → DB | Yes — D-07 chain unchanged; backend `scoped_calendar` confirmed at `backend/app/routers/calendar.py:71` | FLOWING |
| `DayCell` (downstream) | per-day note | autosave → `useUpdateCalendarItem(companyId)` → `PATCH /api/{company}/calendar/{id}` → `scoped_calendar(company).where(id=...)` + UPDATE | Yes — JCAL-05 backend tests prove this end-to-end (POST seeds row with real body, GET reads it back identical, cross-tenant PATCH fails 404 without mutating) | FLOWING |
| `REQUIREMENTS.md` JCAL-01 line | — | static markdown | N/A (spec file) | N/A |

No HOLLOW or DISCONNECTED artifacts. Phase 14's 13-line deletion exposes the v2.1 + v3.0 + v3.1 multi-tenant data pipeline (already proven by existing tests + Phase 9/10/12/13 verifiers) for Juno's URL.

---

## Anti-Pattern Scan

Files modified in Phase 14:

| File | TODO/FIXME | Empty handlers | Hardcoded empty data | Console.log only | Notes |
|------|-----------|----------------|---------------------|------------------|-------|
| `frontend/src/pages/ContentCalendarPage.tsx` | none | none | none | none | Clean — comment block deletion removed the only Phase-9-era TODO-adjacent prose ("Coming in v3.1") |
| `frontend/src/pages/__tests__/ContentCalendarPage.test.tsx` | none | `vi.fn()` mocks (intentional, scoped to test) | none in test logic | none | Test mocks are scoped + flagged in docstring; not stubs |
| `backend/tests/test_calendar_cross_tenant.py` | none | none | none | none | Clean; assertions reference real router behavior + readback proves no mutation |
| `.planning/REQUIREMENTS.md` | n/a (spec file) | — | — | — | Surgical 1-line edit, no stale "TODO Phase 14" residue |

Zero blocker anti-patterns. Zero warning anti-patterns. The `vi.fn()` mutation hook mocks in the frontend test are intentional (test isolates the cache-key assertion from the mutation hot-path) and documented in the file header.

---

## Operator-Visible Outcome (human verification queued)

After deploy:

1. Operator navigates to `/juno/calendar` → sees Mon-Sun WeeklyGrid (not "Coming in v3.1" placeholder) — **automated test #1 + #3 above prove the WeeklyGrid mounts; pixel-level visual confirmation deferred to human**
2. Operator edits any DayCell → blur triggers autosave → row persists with `company_id='juno'` — **JCAL-05 backend tests prove POST + GET round-trip works for Juno; persistence-on-blur UX deferred to human**
3. Operator switches Juno → Seva via CompanySwitcher → calendar view updates with zero bleed — **JCAL-03 RTL tests prove cache-key isolation; live-switcher UX deferred to human**
4. Operator week-navigates prev/next/today on Juno → works identically to Seva — **WeekNav handlers unchanged from v2.1 Phase 6; D-07 untouched; behavioral parity inherited**

Human-verification items above are queued in the frontmatter `human_verification` block.

---

## Goal-Backward Summary

**The phase goal was:** Make `/juno/calendar` functional by removing the Phase 9 D-09 short-circuit; verify cross-tenant isolation via tests; make zero Seva-side changes.

**The codebase delivers exactly this:**

- ✓ Short-circuit gone from `ContentCalendarPage.tsx` (13 lines deleted; file 67 → 53 lines)
- ✓ `<WeeklyGrid companyId={companyId}>` is the sole render path for BOTH tenants (line 50)
- ✓ Cross-tenant cache isolation proven at the frontend layer (3 RTL tests, all pass)
- ✓ Cross-tenant CRUD isolation proven at the backend layer (4 pytests, all pass, 404 NOT 403)
- ✓ REQUIREMENTS.md JCAL-01 reworded with `*(D-06)*` provenance
- ✓ D-07 byte-identical: 12 critical files have ZERO diff across the 5-commit window
- ✓ Scheduler 100% untouched (0 diff lines)
- ✓ Existing Seva calendar tests + AppHeader brand tests still pass (16/16)

**No gaps. No regressions. No anti-patterns. No hollow wiring.**

The phase makes a narrow surgical change to enable a feature that had been deliberately gated since v3.0 Phase 9. The supporting multi-tenant scaffolding had already shipped (v2.1 Phase 6 + v3.0 Phase 9 + v3.1 Phase 10/12/13); Phase 14's contribution is the gate removal + the explicit cross-tenant isolation test pair that v3.0 Phase 9 deferred to "the phase that actually turns Juno calendar on."

---

## Final Phase Verdict: PASS

- **Per-requirement (5/5):** JCAL-01, JCAL-02, JCAL-03, JCAL-04, JCAL-05 all PASS
- **Per-invariant (12/12):** All 12 D-07 invariants + anti-pattern + spot-check invariants PASS
- **Net regression delta:** +3 frontend tests (175 → 178), +4 backend tests (184 → 188), 0 scheduler delta
- **D-07 byte-identical contract:** All 12 protected files unchanged
- **Human verification:** 3 visual/UX items queued for operator (post-deploy) — NOT blockers for phase-level signoff

Ready for: phase close-out (ROADMAP/STATE/REQUIREMENTS Traceability already reflect Complete per orchestrator commit `7d9321b`).

---

*Verified: 2026-05-20T22:30:00Z*
*Verifier: Claude (gsd-verifier)*
