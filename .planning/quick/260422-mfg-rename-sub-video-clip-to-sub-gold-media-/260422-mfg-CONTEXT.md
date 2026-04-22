# Quick Task 260422-mfg: Rename sub_video_clip to sub_gold_media across scheduler+backend+frontend+DB — Context

**Gathered:** 2026-04-22
**Status:** Ready for planning

<domain>
## Task Boundary

Rename `sub_video_clip` → `sub_gold_media` across the repo to eliminate the "gold_media / video_clip" label confusion flagged in the zid debug session (follow-up (b), paired with the queued (a) investigation into 0-items behavior). The scheduler file is `scheduler/agents/content/video_clip.py` with `CONTENT_TYPE="video_clip"` and `AGENT_NAME="sub_video_clip"`; the module docstring at L11 documents the intentional split: *"Frontend label: 'Gold Media' — DB value stays video_clip for schema parity."* That split is what created the confusion — the debugger during zid kept wondering if `gold_media.py` existed when it didn't.

`CLAUDE.md` enumerates the 7 content types as "breaking news, threads, long-form, quotes, infographics, **gold media**, gold history" — so "gold media" IS the canonical project name; the backend just never got renamed from the pre-split era. This task fixes the inconsistency by moving the backend (code + DB values) to match the frontend label that already reads "Gold Media".

**Scope boundary:**
- Scheduler: rename `scheduler/agents/content/video_clip.py` → `scheduler/agents/content/gold_media.py`, rename constants/symbols, rename test file, update all imports and branch conditions.
- Backend: update docstrings in `backend/app/models/content_bundle.py` and `backend/app/routers/queue.py` (no code changes — both only contain comments referencing the content_type values).
- Frontend: rename `VideoClipPreview.tsx` → `GoldMediaPreview.tsx`, update `ContentDetailModal.tsx` imports and branch conditions, update `agentTabs.ts` config values (`contentType: 'video_clip'` → `'gold_media'`; `agentName: 'sub_video_clip'` → `'sub_gold_media'`), update `AgentRunsTab.tsx` dropdown option.
- DB: Alembic migration with `UPDATE content_bundles SET content_type='gold_media' WHERE content_type='video_clip'` + `UPDATE agent_runs SET agent_name='sub_gold_media' WHERE agent_name='sub_video_clip'`.

**Explicitly out of scope:**
- No changes to the 6 other sub-agents (breaking_news / threads / long_form / quotes / infographics / gold_history).
- No investigation into why sub_video_clip produces 0 items — that's follow-up (a), queued as a separate `/gsd:debug` session after this rename ships.
- No source-switching from X API to YouTube/podcast RSS — vxg explicitly deferred that to a future task.

</domain>

<decisions>
## Implementation Decisions

User reviewed the gray areas and responded **"All clear"** → all decisions below are **Claude's Discretion, locked via the user's explicit authorization** to proceed with the Recommended path for every gray area.

### D-01 — Rename depth: Full rename (Option A)

Full rename across Python module, constants, DB values, test files, frontend config, and frontend component. This is the cleanest and most consistent outcome, matching `CLAUDE.md`'s canonical "gold media" naming. One-shot data migration brings existing rows into alignment.

**Rejected alternatives:**
- (B) Code-only rename, no DB touch — creates a dual-value problem (new rows `gold_media`, old rows `video_clip`) that breaks dashboard grouping unless we add IN-clause filters or a later backfill. Strictly worse than doing the UPDATE now.
- (C) File-rename only (keep string constants as `video_clip`) — half-measure that fixes "does gold_media.py exist?" confusion but leaves the UI label mismatch. Not worth the partial churn.
- (D) Docstring/comment cleanup only — cheapest but leaves the structural inconsistency. User's zid-follow-up directive implies actual renaming, not comment polish.

### D-02 — DB migration mechanism: Alembic migration file (Option i)

Add a new Alembic revision file under `backend/alembic/versions/` with explicit `UPDATE` statements for both tables. Auditable in version history, replayable, and consistent with how the project handles schema+data migrations (prior migrations exist up to `0007_add_market_snapshots.py`).

**Rejected alternative:** One-off `railway run` UPDATE transaction outside Alembic (pattern from sn9 / k9z) — cheaper but less auditable. Rename crosses scheduler + backend + frontend contracts, so deserves a recorded migration rather than an ephemeral prod-only transaction.

### D-03 — Frontend component rename: Full file rename (Option i)

Rename `frontend/src/components/content/VideoClipPreview.tsx` → `GoldMediaPreview.tsx` and update all imports (in `ContentDetailModal.tsx` at L30 + L132, and any other consumer). Rename the default export component from `VideoClipPreview` → `GoldMediaPreview`. Consistent with the full-rename depth (D-01) and matches the already-renamed `agentTabs.ts` slug/label.

### D-04 — Test file rename (Claude's Discretion, recommended path)

Rename `scheduler/tests/test_video_clip.py` → `scheduler/tests/test_gold_media.py` alongside the module rename. Update the import statement (`from agents.content import video_clip` → `from agents.content import gold_media`) and all test function references. Test count stays at 109 (no new tests, no retired tests — pure rename churn). This is the consistent path with D-01.

### D-05 — worker.py display name: Keep as "Gold Media" (Claude's Discretion)

`scheduler/worker.py` line 118 already has display name `"Gold Media"` — unchanged. The display string is what shows up in scheduler startup logs and already matches the frontend label. Only the job_id (`"sub_video_clip"` → `"sub_gold_media"`) and the function reference (`video_clip.run_draft_cycle` → `gold_media.run_draft_cycle`) change in that tuple.

### D-06 — Lock ID: Keep 1015 (Claude's Discretion)

`JOB_LOCK_IDS["sub_video_clip"] = 1015` → `JOB_LOCK_IDS["sub_gold_media"] = 1015`. The lock ID is an opaque integer; only the key name changes. Prevents any Postgres advisory-lock churn in prod.

### D-07 — VIDEO_ACCOUNTS constant: Rename to GOLD_MEDIA_ACCOUNTS (Claude's Discretion)

Consistent with the rest of the rename. Any test references (`video_clip.VIDEO_ACCOUNTS`) updated to `gold_media.GOLD_MEDIA_ACCOUNTS`. This is a small internal cleanup that falls naturally out of the module rename.

### D-08 — Backward-compat aliases: NO aliases (Claude's Discretion)

No backward-compat `VIDEO_ACCOUNTS = GOLD_MEDIA_ACCOUNTS` shim, no `video_clip = gold_media` module alias, no dual-read in queries. Single source of truth post-rename. The Alembic migration ensures old DB rows are updated in-place at deploy time, so there's no transitional period where both values coexist. If rollback is needed, the migration has a symmetrical `downgrade()` that reverses the UPDATEs.

### Claude's Discretion

All decisions locked per user's "All clear" response. No open questions remain for the planner.

</decisions>

<specifics>
## Specific Ideas

**File layout (proposed, planner to confirm):**
```
scheduler/agents/content/gold_media.py              # renamed from video_clip.py
scheduler/agents/content/gold_history.py            # unchanged
scheduler/agents/content/__init__.py                # docstring: "video_clip" → "gold_media" (L4, L10, L74)
scheduler/agents/content_agent.py                   # L568, L652: `fmt == "video_clip"` → `fmt == "gold_media"`
scheduler/models/content_bundle.py                  # L15 docstring: allowed values list
scheduler/tests/test_gold_media.py                  # renamed from test_video_clip.py
scheduler/tests/test_content_agent.py               # any "video_clip" content_type references
scheduler/tests/test_worker.py                      # test_video_clip_is_daily_cron → test_gold_media_is_daily_cron, JOB_LOCK_IDS keys
scheduler/worker.py                                 # JOB_LOCK_IDS key + CONTENT_CRON_AGENTS tuple + docstrings/comments
scheduler/seed_content_data.py                      # any references (probably none, but verify)

backend/alembic/versions/0008_rename_video_clip_to_gold_media.py   # NEW Alembic migration
backend/app/models/content_bundle.py                # L17 docstring
backend/app/routers/queue.py                        # L64 docstring

frontend/src/config/agentTabs.ts                    # L32: contentType + agentName values
frontend/src/components/content/GoldMediaPreview.tsx  # renamed from VideoClipPreview.tsx
frontend/src/components/approval/ContentDetailModal.tsx  # L30 + L132 imports + branch conditions
frontend/src/components/settings/AgentRunsTab.tsx   # L27: option value + label
```

**Alembic migration shape (proposed):**
```python
"""Rename video_clip → gold_media in content_bundles.content_type and agent_runs.agent_name.

Revision ID: 0008
Revises: 0007
Create Date: 2026-04-22
"""
from alembic import op

revision = "0008"
down_revision = "0007"

def upgrade():
    op.execute(
        "UPDATE content_bundles SET content_type = 'gold_media' "
        "WHERE content_type = 'video_clip'"
    )
    op.execute(
        "UPDATE agent_runs SET agent_name = 'sub_gold_media' "
        "WHERE agent_name = 'sub_video_clip'"
    )

def downgrade():
    op.execute(
        "UPDATE agent_runs SET agent_name = 'sub_video_clip' "
        "WHERE agent_name = 'sub_gold_media'"
    )
    op.execute(
        "UPDATE content_bundles SET content_type = 'video_clip' "
        "WHERE content_type = 'gold_media'"
    )
```

**Module rename mechanics (proposed):**
Use `git mv scheduler/agents/content/video_clip.py scheduler/agents/content/gold_media.py` to preserve history. Same for `test_video_clip.py` → `test_gold_media.py` and `VideoClipPreview.tsx` → `GoldMediaPreview.tsx`. Inside the renamed files, globally replace `video_clip` → `gold_media`, `VIDEO_ACCOUNTS` → `GOLD_MEDIA_ACCOUNTS`, `VideoClipPreview` → `GoldMediaPreview`.

**Symbol rename map:**
```
video_clip module          → gold_media
CONTENT_TYPE = "video_clip" → CONTENT_TYPE = "gold_media"
AGENT_NAME = "sub_video_clip" → AGENT_NAME = "sub_gold_media"
VIDEO_ACCOUNTS              → GOLD_MEDIA_ACCOUNTS
_search_video_clips         → _search_gold_media_clips (or keep _search_video_clips — internal helper, not a public symbol; planner decides)
_draft_video_caption        → _draft_gold_media_caption (or keep — same internal-helper argument)
VideoClipPreview            → GoldMediaPreview (component + filename)
```

**Planner to decide on internal helper names** (`_search_video_clips`, `_draft_video_caption`): these are module-private functions. Two reasonable options:
1. Rename for consistency (`_search_gold_media_clips`, `_draft_gold_media_caption`)
2. Keep the internal names — they describe the action ("search video clips", "draft a video caption") regardless of the sub-agent name. The sub-agent deals with video-clip content even after the rename to "gold media".
Lean toward option 1 for consistency, but planner can judge.

**Validation gates (to be refined during planning):**
- `cd scheduler && uv run ruff check .` → clean
- `cd scheduler && uv run pytest -x` → 109 passed (baseline from lbb, no test count change expected)
- `cd backend && uv run ruff check .` → clean
- `cd backend && uv run pytest -x` → passes (prior baseline from lbb session; migration file addition shouldn't affect backend test count)
- `pnpm -C frontend lint` → clean
- `pnpm -C frontend exec tsc --noEmit` → clean
- `pnpm -C frontend test --run` → passes (baseline 52; rename churn, no count change)
- `pnpm -C frontend build` → green
- `grep -r "video_clip" scheduler/ backend/app/ frontend/src/` (excluding `.pyc`, `__pycache__`, `node_modules`, `dist`, `.pytest_cache`, `.ruff_cache`) → zero live-code matches. Acceptable matches only in: git-history comments that reference the pre-mfg task id, Alembic migration file (by design — it references the old value in UPDATE WHERE), CLAUDE.md historical notes (unchanged).
- `grep -r "sub_video_clip" scheduler/ backend/app/ frontend/src/` → zero live-code matches (same exclusions).
- `grep -r "VideoClipPreview" frontend/src/` → zero matches.
- `alembic upgrade head` dry-run against a test DB or scripted replay → succeeds; `alembic downgrade -1` also succeeds.

</specifics>

<canonical_refs>
## Canonical References

- Source files:
  - `scheduler/agents/content/video_clip.py` (current module, 347 lines post-vxg)
  - `scheduler/tests/test_video_clip.py` (6 tests after vxg)
  - `scheduler/worker.py` (CONTENT_CRON_AGENTS + JOB_LOCK_IDS)
  - `scheduler/models/content_bundle.py` + `backend/app/models/content_bundle.py` (both carry comment-only references)
  - `backend/app/routers/queue.py::L64` (docstring-only reference)
  - `frontend/src/config/agentTabs.ts` (L32 tab config)
  - `frontend/src/components/content/VideoClipPreview.tsx`
  - `frontend/src/components/approval/ContentDetailModal.tsx` (L30, L132)
  - `frontend/src/components/settings/AgentRunsTab.tsx` (L27)

- zid debug session flagging this as follow-up (b): `.planning/debug/resolved/260422-zid-non-bn-agents-produce-zero-items.md`
- CLAUDE.md enumeration of 7 content types as "breaking news, threads, long-form, quotes, infographics, gold media, gold history" — the canonical naming authority for this rename
- Recent quick tasks the planner should cross-reference:
  - `260421-eoe` (original 7-sub-agent split — where the video_clip/gold_media mismatch was introduced)
  - `260422-vxg` (last touched this module — reordered VIDEO_ACCOUNTS, added analyst quality gate)
  - `260422-lbb` (just-shipped pattern for single-file rewrite + comprehensive test coverage)

</canonical_refs>
