---
phase: quick-260422-mfg
plan: 01
subsystem: scheduler, backend, frontend, alembic
tags: [rename, refactor, gold-media, alembic-migration]
dependency_graph:
  requires: [260422-lbb, 260422-vxg, 260421-eoe]
  provides: [canonical-gold-media-naming]
  affects: [scheduler-worker, content-agent, frontend-queue, alembic-chain]
tech_stack:
  added: []
  patterns: [git-mv-history-preservation, alembic-data-migration, zero-grep-hygiene]
key_files:
  created:
    - backend/alembic/versions/0008_rename_video_clip_to_gold_media.py
    - scheduler/agents/content/gold_media.py (renamed from video_clip.py)
    - scheduler/tests/test_gold_media.py (renamed from test_video_clip.py)
    - frontend/src/components/content/GoldMediaPreview.tsx (renamed from VideoClipPreview.tsx)
  modified:
    - scheduler/agents/content/__init__.py
    - scheduler/agents/content_agent.py
    - scheduler/models/content_bundle.py
    - scheduler/worker.py
    - scheduler/tests/test_worker.py
    - backend/app/models/content_bundle.py
    - backend/app/routers/queue.py
    - frontend/src/config/agentTabs.ts
    - frontend/src/components/approval/ContentDetailModal.tsx
    - frontend/src/components/approval/__tests__/ContentDetailModal.test.tsx
    - frontend/src/components/settings/AgentRunsTab.tsx
    - frontend/src/pages/PerAgentQueuePage.test.tsx
decisions:
  - "Renamed _search_video_clips → _search_gold_media_clips and _draft_video_caption → _draft_gold_media_caption for zero-grep hygiene consistency (planner decision, per D-01 rationale)"
  - "Renamed VIDEO_CLIP_SCORE → GOLD_MEDIA_SCORE for same reason (D-07 extended)"
  - "Alembic 0008 downgrade order: agent_runs first, then content_bundles (readable symmetry; no FK dependency)"
metrics:
  duration: "~25 minutes"
  completed: "2026-04-22"
  tasks: 2
  files: 19
---

# Quick Task 260422-mfg: rename sub_video_clip → sub_gold_media Summary

Single-line: Full rename of the Gold Media sub-agent from video_clip/sub_video_clip to gold_media/sub_gold_media across all four layers — scheduler module + constants + tests, backend Alembic migration, frontend component + config + tests — eliminating the label/DB split that caused the zid debug session to waste cycles.

## Files Renamed via git mv (history preserved)

| Old Path | New Path | Similarity |
|---|---|---|
| `scheduler/agents/content/video_clip.py` | `scheduler/agents/content/gold_media.py` | 88% |
| `scheduler/tests/test_video_clip.py` | `scheduler/tests/test_gold_media.py` | 61% |
| `frontend/src/components/content/VideoClipPreview.tsx` | `frontend/src/components/content/GoldMediaPreview.tsx` | 90% |

`git log --follow` on `gold_media.py` shows history through vxg (68b21d1) and eoe (762b08b) — history preserved.

## Symbol Rename Map Applied

| Old Symbol | New Symbol | Location |
|---|---|---|
| `CONTENT_TYPE = "video_clip"` | `CONTENT_TYPE = "gold_media"` | gold_media.py |
| `AGENT_NAME = "sub_video_clip"` | `AGENT_NAME = "sub_gold_media"` | gold_media.py |
| `VIDEO_ACCOUNTS` | `GOLD_MEDIA_ACCOUNTS` | gold_media.py (D-07) |
| `VIDEO_CLIP_SCORE` | `GOLD_MEDIA_SCORE` | gold_media.py (planner decision) |
| `_search_video_clips` | `_search_gold_media_clips` | gold_media.py (planner decision) |
| `_draft_video_caption` | `_draft_gold_media_caption` | gold_media.py (planner decision) |
| `VideoClipPreview` | `GoldMediaPreview` | GoldMediaPreview.tsx (D-03) |
| `import video_clip` | `import gold_media` | worker.py |
| `JOB_LOCK_IDS["sub_video_clip"]` | `JOB_LOCK_IDS["sub_gold_media"]` | worker.py (D-06, lock 1015 preserved) |
| `contentType: 'video_clip'` | `contentType: 'gold_media'` | agentTabs.ts |
| `agentName: 'sub_video_clip'` | `agentName: 'sub_gold_media'` | agentTabs.ts |
| `case 'video_clip'` | `case 'gold_media'` | ContentDetailModal.tsx |

Display name "Gold Media" in worker.py CONTENT_CRON_AGENTS tuple was already correct — unchanged (D-05).

## Alembic Migration 0008

File: `backend/alembic/versions/0008_rename_video_clip_to_gold_media.py`

- `revision = "0008"`, `down_revision = "0007"`
- `alembic heads` returns `0008 (head)` — single-headed chain confirmed
- `alembic history` confirms 0008 → 0007 → 0006 → ... chain
- Upgrade: `UPDATE content_bundles SET content_type = 'gold_media' WHERE content_type = 'video_clip'` then `UPDATE agent_runs SET agent_name = 'sub_gold_media' WHERE agent_name = 'sub_video_clip'`
- Downgrade: symmetric reverse (agent_runs first, then content_bundles)
- No live DB applied (no test DB available); `--sql` dry-run not available with asyncpg dialect in offline mode; migration structure verified by inspection and `alembic history` chain validation
- This is the SINGLE allowed location for `video_clip` / `sub_video_clip` strings in the codebase

## Files Dropped from Commit Scope

- `scheduler/seed_content_data.py` — zero `video_clip` / `sub_video_clip` references found; excluded from commit (no changes needed)

## Validation Gate Results

| Gate | Command | Result |
|---|---|---|
| Scheduler ruff | `uv run ruff check .` | All checks passed |
| Scheduler pytest | `uv run pytest -x` | **109 passed**, 17 warnings |
| Backend ruff | `uv run ruff check .` | All checks passed (fixed E501 line-too-long in migration docstring) |
| Backend pytest | `uv run pytest -x` | 69 passed, 5 skipped |
| Alembic heads | `alembic heads` | `0008 (head)` |
| Frontend lint | `pnpm lint` | Clean (no errors) |
| Frontend tsc | `tsc --noEmit` | Clean (no errors) |
| Frontend vitest | `pnpm test --run` | **52 passed** |
| Frontend build | `pnpm build` | Green (541kB bundle, chunk size warning is pre-existing) |

## Zero-Grep Results

| Pattern | Scope | Result |
|---|---|---|
| `video_clip` | scheduler/, backend/app/, frontend/src/ (excluding migration) | **0 matches** |
| `sub_video_clip` | scheduler/, backend/app/, frontend/src/ (excluding migration) | **0 matches** |
| `VideoClipPreview` | frontend/src/ | **0 matches** |
| `VIDEO_ACCOUNTS`, `VIDEO_CLIP_SCORE`, `_search_video_clips`, `_draft_video_caption` | scheduler/ | **0 matches** |

The 0008 migration file is the single permitted location containing `video_clip` / `sub_video_clip` strings (WHERE clauses and downgrade SET clauses by design).

## Planner Decision: Internal Helper Renames

Per the plan objective (D-01 full-rename depth rationale):

- `_search_video_clips` → `_search_gold_media_clips`: private helper, renamed for zero-grep hygiene consistency — same reason as D-07 ruling on `VIDEO_ACCOUNTS`
- `_draft_video_caption` → `_draft_gold_media_caption`: same rationale
- `VIDEO_CLIP_SCORE` → `GOLD_MEDIA_SCORE`: same rationale (the 7.5 value is unchanged; only the symbol name moves)

All call sites within `gold_media.py` and `test_gold_media.py` updated accordingly.

No backward-compat aliases introduced (D-08). No dual-read logic.

## Cross-References

- **zid** (`260422-zid`): debug session that flagged this as follow-up (b) — debugger was confused by `gold_media.py` not existing when the frontend label already said "Gold Media"
- **vxg** (`260422-vxg`): last touched the video_clip module — reordered GOLD_MEDIA_ACCOUNTS, added analyst quality gate
- **lbb** (`260422-lbb`): immediately prior quick task — provided the 109 scheduler test baseline; same pattern for single-file rewrite + comprehensive test coverage
- **eoe** (`260421-eoe`): original 7-agent split — where the `video_clip` / `gold_media` mismatch was introduced (the module was named video_clip.py but the frontend tab already showed "Gold Media")

## Follow-up (a) Still Queued

"Why does sub_gold_media produce 0 items" — separate `/gsd:debug` session, NOT addressed by this rename. The rename was purely cosmetic/structural; the 0-items behavior is a separate investigation.

## Self-Check

- `scheduler/agents/content/gold_media.py` — FOUND
- `scheduler/tests/test_gold_media.py` — FOUND
- `backend/alembic/versions/0008_rename_video_clip_to_gold_media.py` — FOUND
- `frontend/src/components/content/GoldMediaPreview.tsx` — FOUND
- Commit `e835b61` at HEAD — VERIFIED

## Self-Check: PASSED
