---
phase: 07-content-agent
plan: "10"
subsystem: content-agent
tags: [gold-history-agent, apscheduler, bi-weekly, drama-first, story-tracking, fact-verification, instagram-carousel]
dependency_graph:
  requires: [07-09]
  provides: [gold-history-agent, midday-content-job, bi-weekly-sunday-job, story-slug-tracking]
  affects:
    - scheduler/agents/gold_history_agent.py
    - scheduler/worker.py
    - scheduler/seed_content_data.py
tech_stack:
  added: []
  patterns: [drama-first-storytelling, json-in-text-config, bi-weekly-cron, advisory-lock-1008-1009]
key_files:
  created:
    - scheduler/agents/gold_history_agent.py
  modified:
    - scheduler/worker.py
    - scheduler/seed_content_data.py
decisions:
  - "GoldHistoryAgent imports check_compliance and build_draft_item lazily from content_agent to avoid circular deps"
  - "Fixed baseline score of 8.0 for gold_history ContentBundles (curated content, not scored like RSS stories)"
  - "Story slug tracked in Config before DraftItem creation so re-runs never repeat even if drafting/compliance fails"
  - "week=*/2 ISO week edge case documented inline in worker.py comment"
metrics:
  duration: "~3 minutes"
  completed: "2026-04-07"
  tasks_completed: 2
  files_modified: 2
  files_created: 1
---

# Phase 07 Plan 10: Gold History Agent + Midday Job + Seed Config Summary

Created `GoldHistoryAgent` class with story selection (Claude Sonnet), SerpAPI fact verification, and drama-first carousel/thread drafting. Registered midday content agent job (daily 12pm, lock 1008) and bi-weekly Gold History Sunday job (lock 1009) in APScheduler worker. Seeded three new config keys.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create GoldHistoryAgent class | 6538dce | scheduler/agents/gold_history_agent.py |
| 2 | Register midday + Gold History APScheduler jobs + seed config | 5f44e4f | scheduler/worker.py, scheduler/seed_content_data.py |

## Decisions Made

- **Lazy circular import**: `check_compliance`, `build_draft_item`, and `process_new_items` are imported inside `_run_pipeline()` using inline imports with `# noqa: PLC0415`, matching the pattern used throughout `content_agent.py`.
- **Baseline score 8.0**: Gold History is curated storytelling content, not scored by the RSS/SerpAPI pipeline. A fixed baseline of 8.0 ensures it always clears the 7.0 threshold in `build_draft_item()` without polluting the scoring machinery.
- **Slug tracked before DraftItem**: `_add_used_topic()` is called after persisting the ContentBundle (and before building the DraftItem), so the slug is always recorded even if compliance fails. This prevents re-selecting the same story on the next run after a partial failure.
- **ISO week edge case documented**: `week="*/2"` may fire twice in early January when ISO week 52/53 rolls to week 1. Low-stakes (one extra history post). Documented inline in `worker.py`.

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — all methods fully implemented. GoldHistoryAgent is complete end-to-end: story selection, SerpAPI verification, Claude Sonnet drafting, compliance, ContentBundle persistence, used-topic tracking, DraftItem creation, and Senior Agent integration.

## Self-Check: PASSED

- [x] `scheduler/agents/gold_history_agent.py` exists — VERIFIED
- [x] `class GoldHistoryAgent` with all required methods — VERIFIED (AST check: _get_config, _get_used_topics, _add_used_topic, _pick_story, _verify_facts, _draft_gold_history, _run_pipeline, run)
- [x] `JOB_LOCK_IDS` has 7 entries including content_agent_midday: 1008 and gold_history_agent: 1009 — VERIFIED
- [x] `_read_schedule_config` defaults include content_agent_midday_hour and gold_history_hour — VERIFIED
- [x] `_make_job` elif branches for content_agent_midday and gold_history_agent — VERIFIED
- [x] `build_scheduler` registers midday (daily cron) and gold_history (bi-weekly Sunday) — VERIFIED
- [x] `seed_content_data.py` CONFIG_DEFAULTS includes content_agent_midday_hour, gold_history_hour, gold_history_used_topics — VERIFIED
- [x] Commit 6538dce — FOUND
- [x] Commit 5f44e4f — FOUND
