---
phase: 06-instagram-agent
plan: 03
subsystem: scheduler/agents
tags: [tdd, drafting, compliance, two-claude, instagram, wave-2, draft-pipeline]
dependency_graph:
  requires: [06-02]
  provides: [instagram_agent_draft_pipeline, instagram_agent_compliance]
  affects: [06-04-PLAN, 06-05-PLAN]
tech_stack:
  added: []
  patterns: [two-claude-sonnet-haiku, fail-safe-compliance, pre-screen-local, module-level-testable-functions, lazy-import-senior-agent]
key_files:
  created: []
  modified:
    - scheduler/agents/instagram_agent.py
    - scheduler/tests/test_instagram_agent.py
decisions:
  - "Module-level functions (draft_for_post, check_compliance, build_draft_item_expiry) enable direct test injection without class instantiation — mirrors twitter_agent.py pattern"
  - "Pre-screen '#' and 'seva mining' locally before calling Claude Haiku — avoids LLM cost for obvious blocks (INST-06)"
  - "Fail-safe compliance: only explicit 'pass' substring in response returns True; everything else blocks"
  - "DraftItem.alternatives stored as JSONB list (not JSON string) — matches actual model definition"
  - "DraftItem.source_account used (not source_author) — actual model field name"
metrics:
  duration: "~2 minutes"
  completed: "2026-04-02T22:30:20Z"
  tasks_completed: 1
  tasks_total: 1
  files_created: 0
  files_modified: 2
---

# Phase 6 Plan 03: Draft-Compliance Pipeline Summary

TDD implementation of Claude Sonnet drafting + Haiku compliance checking + DraftItem persistence with 12h expiry for InstagramAgent. 5 test stubs converted from SKIPPED to PASSED; 6 remaining stubs stay SKIPPED.

## What Was Done

### Task 1: TDD — Draft, compliance, expiry pipeline

**RED phase:** Removed `pytest.skip()` from 5 target test stubs. Added `@pytest.mark.asyncio` decorators and real assertions for each test. Added `import json` to test file header. All 5 tests failed with `AttributeError: module 'agents.instagram_agent' has no attribute 'draft_for_post'`.

**Commit:** `c0b573d` — `test(06-03): add failing tests for draft-compliance pipeline`

**GREEN phase:** Added 193 lines to `scheduler/agents/instagram_agent.py`:

**Module-level functions (for direct testability):**
- `draft_for_post(post, client)` — Claude Sonnet (`claude-sonnet-4-20250514`) drafts 2-3 comment alternatives as `{"comment_alternatives": [...]}` JSON. Returns list of dicts with `text` and `rationale` keys. Falls back gracefully on JSON parse failure.
- `check_compliance(draft, client)` — Pre-screens `#` and `seva mining` locally (no LLM cost), then calls Claude Haiku (`claude-haiku-3-20240307`). Fail-safe: only explicit `"pass"` in response returns `True`.
- `build_draft_item_expiry(created_at)` — Creates minimal DraftItem with `platform="instagram"` and `expires_at = created_at + timedelta(hours=12)`.

**InstagramAgent class methods (thin wrappers):**
- `_draft_comments(post)` — delegates to `draft_for_post()`
- `_check_instagram_compliance(draft_text)` — delegates to `check_compliance()`
- `_filter_compliant_drafts(drafts)` — loops drafts, calls `_check_instagram_compliance` per item
- `_build_draft_item(post, compliant_drafts)` — builds full DraftItem with `engagement_snapshot` JSONB and all metadata

**_run_pipeline() Steps 7-9 wired:**
- Step 7: `_draft_comments()` per top post
- Step 8: `_filter_compliant_drafts()` compliance gate
- Step 9: `_build_draft_item()` + `session.flush()` + append ID
- Step 9b: Lazy import `from agents.senior_agent import process_new_items` after commit

**Commit:** `fffc488` — `feat(06-03): implement draft-compliance pipeline with 12h expiry`

## Test Results

```
9 passed, 6 skipped, 0 errors
Full suite: 52 passed, 6 skipped in 0.38s
```

Target tests passing:
- `test_draft_for_post` — 3 alternatives returned, each with `text`/`rationale`, no `#` in any text
- `test_compliance_blocks_hashtags` — `#gold` blocked; clean text with mock PASS returns `True`
- `test_compliance_blocks_seva` — "Seva Mining" blocked without calling Claude (mock not called)
- `test_compliance_fail_safe` — "I'm not sure about this one." → `False` (fail-safe)
- `test_expiry_12h` — `expires_at == created_at + 12h`, `platform == "instagram"`

## Deviations from Plan

**1. [Rule 1 - Bug] DraftItem field names differ from plan spec**

- **Found during:** GREEN phase — reading `models/draft_item.py` before writing implementation
- **Issue:** Plan spec uses `source_author` and `alternatives` as JSON string. Actual `DraftItem` model has `source_account` (not `source_author`) and `alternatives` as JSONB (not a string). Also no `rationale` parameter by that name in plan's `_build_draft_item` spec matched real model.
- **Fix:** Used `source_account` and passed `alternatives` as a Python list (SQLAlchemy serializes JSONB natively). The `rationale` field exists in the model as `Text`.
- **Files modified:** scheduler/agents/instagram_agent.py
- **Impact:** Zero — tests pass, model compatibility maintained.

**2. [Rule 1 - Bug] Test stubs called module-level functions, not class methods**

- **Found during:** RED phase — reading test stubs before writing implementation
- **Issue:** Tests call `ia.draft_for_post()`, `ia.check_compliance()`, `ia.build_draft_item_expiry()` on the module object — same pattern established in twitter_agent.py. The plan described adding class methods only.
- **Fix:** Implemented as module-level functions (matching test stubs) with InstagramAgent class methods as thin wrappers that delegate to them.
- **Files modified:** scheduler/agents/instagram_agent.py
- **Impact:** Zero — aligns with existing twitter_agent.py pattern, tests pass.

## Known Stubs

None — all implemented methods are fully functional. The `_run_pipeline()` Step 10 placeholder comment for health monitoring remains, explicitly deferred to Plan 04.

## Self-Check: PASSED

- [x] `scheduler/agents/instagram_agent.py` exists (467 lines)
- [x] `grep "_draft_comments"` matches
- [x] `grep "_check_instagram_compliance"` matches
- [x] `grep "_filter_compliant_drafts"` matches
- [x] `grep "_build_draft_item"` matches
- [x] `grep "process_new_items"` matches
- [x] `grep 'timedelta(hours=12)'` matches (2 occurrences)
- [x] `grep 'platform="instagram"'` matches (2 occurrences)
- [x] `grep 'claude-haiku-3-20240307'` matches
- [x] `grep 'claude-sonnet-4-20250514'` matches
- [x] 9 tests pass: 4 from Plan 02 + 5 new
- [x] 6 stubs still SKIPPED (not ERROR)
- [x] Full suite: 52 passed, 6 skipped, 0 errors
- [x] Commits c0b573d (RED) and fffc488 (GREEN) exist
