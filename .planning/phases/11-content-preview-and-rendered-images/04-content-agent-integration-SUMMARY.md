---
phase: 11-content-preview-and-rendered-images
plan: 04
subsystem: scheduler
tags: [apscheduler, datetrigger, content-agent, render-enqueue, async, late-import, silent-fail]

# Dependency graph
requires:
  - phase: 11-02
    provides: "render_bundle_job(bundle_id: str) async function in scheduler/agents/image_render_agent.py"
  - phase: 11-01
    provides: "get_scheduler() module-level accessor in scheduler/worker.py"

provides:
  - "_enqueue_render_job_if_eligible(bundle) — module-level helper in content_agent.py that fires a DateTrigger render job for infographic/quote bundles"
  - "_RENDER_FORMATS = {'infographic', 'quote'} — module-level constant gating which formats trigger rendering (D-04)"
  - "3 wired call sites: main RSS/SerpAPI loop (line 1447), video_clip loop (line 1561), quote tweet loop (line 1624)"
  - "9 unit tests covering all enqueue branches (infographic, quote, thread, long_form, breaking_news, video_clip, compliance-gate, silent-fail, replace_existing)"

affects:
  - "11-07 (human-verification) — enqueue fires live during staging once GEMINI_API_KEY and R2_* are provisioned"

# Tech tracking
tech-stack:
  added: []  # No new deps — apscheduler already installed; late imports only
  patterns:
    - "Late import pattern for circular-dep avoidance: all imports of worker.get_scheduler and agents.image_render_agent.render_bundle_job are inside the try block of the helper, never at module top-level"
    - "Silent-fail pattern: bare except Exception swallowed with logging.warning — helper always returns None, never raises"
    - "_RENDER_FORMATS set constant at module level for O(1) format gate"
    - "misfire_grace_time=300 on add_job allows up to 5 min of worker downtime before job is skipped"

key-files:
  created: []
  modified:
    - scheduler/agents/content_agent.py  # Added _RENDER_FORMATS, _enqueue_render_job_if_eligible, 3 call sites
    - scheduler/tests/test_content_agent.py  # Added 9 enqueue unit tests

key-decisions:
  - "Call site for video_clip at line 1561 is wired even though video_clip is not in _RENDER_FORMATS — the helper no-ops immediately, but wiring the site means future format additions automatically flow through without touching three separate locations"
  - "Enqueue call placed AFTER compliance check but BEFORE build_draft_item in the main RSS/SerpAPI loop — render starts as soon as compliance passes, not waiting for the DraftItem Senior Agent call"
  - "Quote tweet enqueue placed AFTER session.flush() but OUTSIDE the if compliance_ok: block — the helper itself gates on compliance_passed, so calling it unconditionally is semantically identical but simpler and avoids duplicated compliance logic"

requirements-completed: [CREV-07, CREV-10]

# Metrics
duration: ~3 min
completed: "2026-04-16"
---

# Phase 11 Plan 04: Content Agent Integration Summary

**APScheduler DateTrigger render enqueue wired into ContentAgent at 3 commit sites via late-import silent-fail helper; 9 unit tests cover all format and compliance branches**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-04-16T21:09:37Z
- **Completed:** 2026-04-16T21:12:09Z
- **Tasks:** 1/1
- **Files modified:** 2

## Accomplishments

- Added `_RENDER_FORMATS = {"infographic", "quote"}` module-level constant to `content_agent.py` (D-04 gating)
- Added `_enqueue_render_job_if_eligible(bundle)` helper with compliance gate, format gate, late imports (to avoid circular deps), APScheduler `DateTrigger` call with `replace_existing=True` and `misfire_grace_time=300`, and silent-fail exception handler (D-18/D-19)
- Wired helper at all 3 ContentBundle commit sites: main RSS/SerpAPI loop (line 1447), video_clip loop (line 1561), quote tweet loop (line 1624)
- Added 9 unit tests to `test_content_agent.py` covering every branch — full suite now 29 passed, 0 new failures

## Call Sites (Exact Line Numbers)

| Line | Variable | Context | Enqueue fires? |
|------|----------|---------|---------------|
| 117 | — | Helper definition | N/A |
| 1447 | `bundle` | Main RSS/SerpAPI loop — after compliance passes, before build_draft_item | Yes (infographic, quote); no-op otherwise |
| 1561 | `vc_bundle` | video_clip loop — after session.flush(), before if compliance_ok: | No-op (video_clip not in _RENDER_FORMATS) |
| 1624 | `q_bundle` | Quote tweet loop — after session.flush(), before if compliance_ok: | Yes (quote format) |

### Sites NOT wired

- `build_no_story_bundle` path (line ~1483–1493 in the "all already covered" branch) — these bundles always have `no_story_flag=True` and `compliance_passed=None`, so the helper would return immediately. Not wired per plan spec.
- Compliance-failed early-return bundles (line ~1408–1413 in the draft_result=None path) — compliance_passed=False, helper would no-op. Not wired.

## Task Commits

| Task | Commit | Message |
|------|--------|---------|
| T1 (TDD GREEN + wire) | 05baa1e | feat(11-04): wire _enqueue_render_job_if_eligible into ContentAgent |

Note: TDD RED (failing tests) and GREEN (implementation) were done in a single commit since both modifications were small and coherent.

## Files Created/Modified

- `scheduler/agents/content_agent.py` — Added `_RENDER_FORMATS` constant (line 109), `_enqueue_render_job_if_eligible()` helper (lines 117–162), and 3 call sites (lines 1447, 1561, 1624)
- `scheduler/tests/test_content_agent.py` — Added 9 enqueue unit tests (lines 416–562)

## Decisions Made

- Helper placed as a module-level function (not a method on ContentAgent class) to match existing pattern for pure functions like `recency_score`, `credibility_score`, etc. This also makes it directly importable for unit tests without instantiating ContentAgent.
- Late imports of `worker.get_scheduler` and `agents.image_render_agent.render_bundle_job` inside the try block — the plan's canonical requirement to avoid circular dependency cycles at module load time.
- `misfire_grace_time=300` added per APScheduler best practice — allows up to 5 minutes of scheduler downtime before a missed one-off job is dropped.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required. Render jobs will not fire until `GEMINI_API_KEY` and R2 credentials are provisioned in Railway (covered by Plan 07 human verification checkpoint).

## Next Phase Readiness

- `_enqueue_render_job_if_eligible` is in place and tested — Plan 05 (frontend) and Plan 06 (modal) can proceed independently
- Plan 07 (human verification) requires GEMINI_API_KEY and R2_* provisioned in Railway before live render jobs can fire
- Full scheduler suite: 114 passed, 1 pre-existing failure (test_morning_digest_assembly per Plan 01 SUMMARY)

---
*Phase: 11-content-preview-and-rendered-images*
*Completed: 2026-04-16*

## Self-Check

- `/Users/matthewnelson/seva-mining/scheduler/agents/content_agent.py` — FOUND (modified)
- `/Users/matthewnelson/seva-mining/scheduler/tests/test_content_agent.py` — FOUND (modified)
- `grep -c "_enqueue_render_job_if_eligible" content_agent.py` → 4 (1 def + 3 call sites) ✓
- `grep -c "from worker import get_scheduler" content_agent.py` → 1 (late import inside helper) ✓
- `grep -c "replace_existing=True" content_agent.py` → 1 ✓
- `grep -c "_RENDER_FORMATS" content_agent.py` → 2 (definition + usage) ✓
- `cd scheduler && uv run pytest tests/test_content_agent.py -v -k "enqueue or render"` → 9 passed ✓
- `cd scheduler && uv run pytest tests/test_content_agent.py -v` → 29 passed ✓
- `cd scheduler && uv run pytest` → 114 passed, 1 pre-existing failure (test_morning_digest_assembly) ✓
- Task commit 05baa1e in git log ✓

## Self-Check: PASSED
