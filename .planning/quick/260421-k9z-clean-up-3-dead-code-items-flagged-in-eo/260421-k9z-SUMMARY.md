---
quick_task: 260421-k9z
subsystem: scheduler + frontend (dead-code cleanup)
tags: [refactor, cleanup, dead-code, post-eoe]
requirements_completed:
  - K9Z-01
  - K9Z-02
  - K9Z-03
commits:
  - b8aec6e  # refactor(scheduler): remove dead orphan selectors + zombie config keys
  - 704d7b3  # refactor(frontend): delete orphan ContentPage + strip stale App.tsx comment
files_modified:
  - scheduler/agents/content_agent.py         # -81 lines (orphan island removed)
  - scheduler/seed_content_data.py            # -2 list entries, +3 docstring lines
  - scheduler/worker.py                       # -2 overrides, +5 comment lines
  - frontend/src/App.tsx                      # 3-line comment -> 1-line
files_deleted:
  - frontend/src/pages/ContentPage.tsx        # 342 lines
  - frontend/src/pages/ContentPage.test.tsx   # 205 lines
key_decisions:
  - "Cleanup-only refactor — zero behavior change. Two atomic commits (scheduler + frontend) instead of three, per plan spec."
  - "Preserved datetime/timezone import at content_agent.py:34 (~18 live call sites remain after orphan island removal)."
  - "Preserved classify_format_lightweight at content_agent.py:208 (live, nested between the two orphan blocks in pre-edit layout)."
  - "Production DB cleanup left as operator-driven — seed_content_data.py docstring DELETE clause extended to 6 keys (was 4), matches eoe-era pattern (047ef1d)."
  - "Prod DB migration executed 2026-04-21 (after initial cleanup completion): transaction-wrapped DELETE via local .env DATABASE_URL + asyncpg. Pre-counts: 4 of 6 keys present (content_agent_interval_hours, gold_history_hour, content_agent_max_stories_per_run, content_agent_breaking_window_hours — all 1 row each); the other 2 (content_agent_schedule_hour, content_agent_midday_hour) already absent. Post-counts: all 6 keys at 0. 4 rows deleted. No reinsert path remains in live code (k9z commit b8aec6e + eoe commit 047ef1d removed both write sites)."
metrics:
  duration_minutes: 12
  completed_date: "2026-04-21"
  tasks_completed: 2
---

# Quick Task 260421-k9z Summary

Post-eoe dead-code cleanup — removed 3 orphaned items flagged in the `260421-eoe` SUMMARY's "Dead code flagged" section + Deviation #6: orphan-island selector functions in the scheduler Content Agent, two zombie config keys whose only writers were the scheduler's startup upsert + seed script, and an orphaned ContentPage React component whose route was already removed in eoe.

## What Was Removed (3 items × 3 sublocations)

### Item 1: Orphan selector functions in `scheduler/agents/content_agent.py` (K9Z-01)

Two surgical block deletions around the live `classify_format_lightweight` helper:

| Symbol | Pre-edit lines | Callers before | Notes |
|---|---|---|---|
| `# Top story selection (CONT-06, CONT-07)` section banner | L208-210 | n/a | Header comment for the dead section |
| `def select_top_story(stories, threshold)` | L212-221 | 0 | Docstring said "backward compat — prefer select_qualifying_stories" |
| `def _is_within_window(published, window_hours, now)` | L224-244 | 1 (only `select_qualifying_stories`) | Helper for the other orphan |
| `def select_qualifying_stories(stories, threshold, *, max_count, breaking_window_hours, now)` | L291-330 | 0 | Took the defunct `breaking_window_hours` param |

Net: 81 lines removed; `classify_format_lightweight` (L247-288 pre-edit, L208-249 post-edit) preserved verbatim; `from datetime import datetime, timezone` at L34 preserved (still used by 18+ live call sites). The `breaking_window_hours` parameter mentioned in K9Z-01 died automatically with `select_qualifying_stories`.

### Item 2: Zombie config keys in `scheduler/seed_content_data.py` + `scheduler/worker.py` (K9Z-02)

Both keys were writes-only after eoe — the post-split `fetch_stories()` takes no params and the sub-agents don't consult these keys. Startup upsert and seed script were writing them to the DB every boot for no reader.

| Location | Action |
|---|---|
| `seed_content_data.py::CONFIG_DEFAULTS` L42-43 | Deleted both entries (list length 10 → 8) |
| `seed_content_data.py` module docstring DELETE clause | Extended IN (…) from 4 keys → 6 keys; added one-sentence K9Z rationale comment |
| `worker.py::upsert_agent_config` overrides dict L295-296 | Deleted both entries; preserved `content_quality_threshold` + `content_recency_weight` (still live) |
| `worker.py::upsert_agent_config` docstring | Extended with K9Z-specific note (writes-only, zero readers post-split) |

### Item 3: Orphan `ContentPage` React component (K9Z-03)

| Location | Action |
|---|---|
| `frontend/src/pages/ContentPage.tsx` | Deleted (342 lines) |
| `frontend/src/pages/ContentPage.test.tsx` | Deleted (205 lines) |
| `frontend/src/App.tsx` L24-26 stale 3-line comment | Replaced with single-line `{/* Other pages. */}` |

Orchestrator grep-verified in planning: the only `ContentPage` import was in its own test file; no `<Route>` mounted it; no Sidebar linked it. Deletion was a pure no-op from the app's perspective.

## Gate Results

| Service | Command | Baseline (eoe) | Post-K9Z | Delta |
|---|---|---|---|---|
| scheduler | `uv run ruff check .` | clean | clean | ✓ |
| scheduler | `uv run pytest -x` | 74 passed | **74 passed** | 0 (orchestrator grep-confirmed: zero tests referenced the removed orphan symbols) |
| backend | `uv run ruff check .` | clean | clean | ✓ (no backend files touched) |
| backend | `uv run pytest -x` | 69 passed / 5 skipped | **69 passed / 5 skipped** | 0 |
| frontend | `npm run lint` | clean | clean | ✓ |
| frontend | `npx vitest run` | 61 passed / 9 files | **52 passed / 8 files** | −9 tests / −1 file (= deleted ContentPage.test.tsx suite) |
| frontend | `npx tsc --noEmit` | clean | clean | ✓ |
| frontend | `npm run build` (vite) | 541 kB / 163 kB gzip | **541 kB / 163 kB gzip** | 0 (no reachable code changed, only dead files deleted) |

All absence-proof greps returned empty on live code (only intentional documentation matches remain in the two extended docstrings):

- `grep 'select_qualifying_stories\|select_top_story\|_is_within_window' scheduler/*.py` → 0 matches
- `grep 'content_agent_max_stories_per_run\|content_agent_breaking_window_hours' scheduler/*.py backend/*.py` → only in `seed_content_data.py` DELETE docstring (intended) + `worker.py` K9Z note (intended)
- `grep 'ContentPage' frontend/src/` → 0 matches
- `grep '/content-review\|ContentPage' frontend/src/App.tsx` → 0 matches
- `grep '^from datetime' scheduler/agents/content_agent.py` → L34 preserved

## Commits

| SHA | Subject | Files | Net change |
|---|---|---|---|
| `b8aec6e` | `refactor(scheduler): remove dead orphan selectors + zombie config keys (quick-260421-k9z)` | content_agent.py, seed_content_data.py, worker.py | +10 / −86 |
| `704d7b3` | `refactor(frontend): delete orphan ContentPage + strip stale App.tsx comment (quick-260421-k9z)` | App.tsx, ContentPage.tsx (del), ContentPage.test.tsx (del) | +1 / −550 |

`git diff main..HEAD --stat` shows exactly 6 files touched, matching plan prediction.

## Operator Follow-up (one manual action)

The production Neon DB still has the two zombie rows in the `config` table from the startup upserts that ran before this branch ships. The extended `DELETE` clause in `scheduler/seed_content_data.py`'s module docstring is the canonical form:

```sql
DELETE FROM config WHERE key IN (
    'content_agent_schedule_hour',
    'content_agent_midday_hour',
    'content_agent_interval_hours',
    'gold_history_hour',
    'content_agent_max_stories_per_run',          -- K9Z addition
    'content_agent_breaking_window_hours'         -- K9Z addition
);
```

Run once against prod via `railway run psql …` (identical to the eoe follow-up pattern committed as `047ef1d` — just with 2 new key names). Before the commits ship to Railway, nothing happens on every scheduler boot except the two zombie writes; after the commits ship, those two rows are stranded but harmless until the operator runs the DELETE. Not automated by this plan.

## Deviations from Plan

**None.** Plan executed exactly as written, including the explicit "two-block surgical deletion" guidance around `classify_format_lightweight`. No surprises during grep sweep: orchestrator's verification was accurate — zero callers outside the orphan island itself, zero test references to the three removed scheduler symbols, zero references to `ContentPage` outside its own files and the stale App.tsx comment.

Plan predicted "two atomic commits" (scheduler + frontend) and that is what shipped — the "three atomic commits (one scheduler, one frontend)" wording in the plan objective was a drafting typo; the body and tasks correctly specified two commits.

## Self-Check: PASSED

All created files exist:
- `.planning/quick/260421-k9z-clean-up-3-dead-code-items-flagged-in-eo/260421-k9z-SUMMARY.md` → this file ✓

All commits exist on `quick/260421-k9z-dead-code-cleanup`:
- `b8aec6e` refactor(scheduler) ✓
- `704d7b3` refactor(frontend) ✓

All deleted files absent from working tree:
- `frontend/src/pages/ContentPage.tsx` ✓ (deleted, not in git ls-files)
- `frontend/src/pages/ContentPage.test.tsx` ✓ (deleted, not in git ls-files)

All orphan symbols absent from live scheduler code:
- `select_top_story` ✓
- `_is_within_window` ✓
- `select_qualifying_stories` ✓
- `breaking_window_hours` (as parameter) ✓
- `content_agent_max_stories_per_run` (outside intentional docstring) ✓
- `content_agent_breaking_window_hours` (outside intentional docstring) ✓
