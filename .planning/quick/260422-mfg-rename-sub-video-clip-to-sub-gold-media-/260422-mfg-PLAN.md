---
phase: quick-260422-mfg
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - scheduler/agents/content/video_clip.py                           # git mv → gold_media.py
  - scheduler/agents/content/gold_media.py                           # renamed target (symbol rewrites inside)
  - scheduler/agents/content/__init__.py                             # docstring references (L4, L10, L74 per CONTEXT)
  - scheduler/agents/content_agent.py                                # L568, L652: fmt == "video_clip" branch
  - scheduler/models/content_bundle.py                               # L15 docstring allowed-values list
  - scheduler/worker.py                                              # import, JOB_LOCK_IDS key, CONTENT_CRON_AGENTS tuple, vxg-era docstrings
  - scheduler/tests/test_video_clip.py                               # git mv → test_gold_media.py
  - scheduler/tests/test_gold_media.py                               # renamed target (imports + symbols + test names)
  - scheduler/tests/test_content_agent.py                            # any "video_clip" content_type fixtures
  - scheduler/tests/test_worker.py                                   # test_video_clip_is_daily_cron → test_gold_media_is_daily_cron, JOB_LOCK_IDS key
  - scheduler/seed_content_data.py                                   # verify & update if references exist
  - backend/alembic/versions/0008_rename_video_clip_to_gold_media.py # NEW migration (revision 0008, down_revision 0007)
  - backend/app/models/content_bundle.py                             # L17 docstring
  - backend/app/routers/queue.py                                     # L64 docstring
  - frontend/src/components/content/VideoClipPreview.tsx             # git mv → GoldMediaPreview.tsx
  - frontend/src/components/content/GoldMediaPreview.tsx             # renamed target (component symbol + default export)
  - frontend/src/components/approval/ContentDetailModal.tsx          # L25-31 CONTENT_BUNDLE_TYPES map, L30 import, L132 branch
  - frontend/src/components/approval/__tests__/ContentDetailModal.test.tsx  # fixture references
  - frontend/src/config/agentTabs.ts                                 # L32 contentType + agentName values
  - frontend/src/components/settings/AgentRunsTab.tsx                # L27 option value + label
  - frontend/src/pages/PerAgentQueuePage.test.tsx                    # fixture references
autonomous: true
requirements:
  - D-01  # Full rename depth across module/constants/DB/test/frontend
  - D-02  # Alembic migration file (revision 0008)
  - D-03  # Frontend component full file rename
  - D-04  # Test file rename (alongside module rename)
  - D-05  # worker.py display name "Gold Media" unchanged
  - D-06  # Lock ID 1015 preserved under new key name
  - D-07  # VIDEO_ACCOUNTS → GOLD_MEDIA_ACCOUNTS
  - D-08  # No backward-compat aliases or dual-read

must_haves:
  truths:
    - "Running the scheduler worker registers a job with id 'sub_gold_media' that invokes scheduler/agents/content/gold_media.py::run_draft_cycle at 12:00 America/Los_Angeles daily (lock_id 1015 preserved)."
    - "The Alembic head is 0008; running `alembic upgrade head` against a DB containing rows with content_type='video_clip' or agent_name='sub_video_clip' updates them to the new values in one transaction, and `alembic downgrade -1` reverses both UPDATEs symmetrically."
    - "The frontend Gold Media tab at /agents/gold-media fetches /queue?content_type=gold_media and renders approved drafts via GoldMediaPreview without import or type errors."
    - "Repo-wide grep for live-code `video_clip`, `sub_video_clip`, `VideoClipPreview`, and `VIDEO_ACCOUNTS` under scheduler/, backend/app/, frontend/src/ returns zero matches (excluding the 0008 Alembic migration WHERE clause, which is the single allowed reference)."
    - "All validation gates pass: scheduler ruff clean + pytest 109 passed, backend ruff clean + pytest passes, frontend lint clean + tsc --noEmit clean + vitest 52 passed + build green."
  artifacts:
    - path: "scheduler/agents/content/gold_media.py"
      provides: "Gold Media sub-agent module with CONTENT_TYPE='gold_media', AGENT_NAME='sub_gold_media', GOLD_MEDIA_ACCOUNTS list"
      contains: "CONTENT_TYPE: str = \"gold_media\""
      min_lines: 340
    - path: "scheduler/tests/test_gold_media.py"
      provides: "Test coverage for gold_media sub-agent (6 tests preserved from video_clip baseline)"
      contains: "from agents.content import gold_media"
    - path: "backend/alembic/versions/0008_rename_video_clip_to_gold_media.py"
      provides: "One-shot data migration renaming content_type and agent_name values"
      contains: "revision = \"0008\""
    - path: "frontend/src/components/content/GoldMediaPreview.tsx"
      provides: "Renamed preview component (default export: GoldMediaPreview)"
      contains: "export function GoldMediaPreview"
    - path: "frontend/src/config/agentTabs.ts"
      provides: "Tab config row for gold-media slug"
      contains: "contentType: 'gold_media'"
  key_links:
    - from: "scheduler/worker.py"
      to: "scheduler/agents/content/gold_media.py"
      via: "CONTENT_CRON_AGENTS tuple entry (sub_gold_media, gold_media.run_draft_cycle, 'Gold Media', 1015, ...)"
      pattern: "gold_media\\.run_draft_cycle"
    - from: "frontend/src/components/approval/ContentDetailModal.tsx"
      to: "frontend/src/components/content/GoldMediaPreview.tsx"
      via: "named import + switch branch on content_type==='gold_media'"
      pattern: "GoldMediaPreview"
    - from: "frontend/src/config/agentTabs.ts"
      to: "backend /queue endpoint"
      via: "contentType: 'gold_media' passed as ?content_type= filter"
      pattern: "contentType: 'gold_media'"
    - from: "backend/alembic/versions/0008_rename_video_clip_to_gold_media.py"
      to: "content_bundles + agent_runs prod rows"
      via: "op.execute UPDATE ... WHERE content_type/agent_name = old-value"
      pattern: "UPDATE (content_bundles|agent_runs) SET"
---

<objective>
Rename the "Video Clip" sub-agent to "Gold Media" across the four layers of the stack (scheduler module + constants + tests, backend docstrings + Alembic data migration, frontend component + config + tests) so the canonical project name from CLAUDE.md ("breaking news, threads, long-form, quotes, infographics, gold media, gold history") is used consistently. Eliminates the "frontend label: 'Gold Media' — DB value stays video_clip for schema parity" split that caused the zid debug session to waste cycles looking for a file named `gold_media.py` that did not exist.

**Purpose:** Close follow-up (b) from zid (`260422-zid`). Single source of truth for the 6th sub-agent. Removes the entire class of "which name do I use here?" confusion for future debug sessions. No behavior change — pure rename churn + one-shot DB row update.

**Output:** Single atomic commit containing: renamed scheduler module + test file + frontend preview component (via `git mv` for history), rewritten internal symbols (`CONTENT_TYPE`, `AGENT_NAME`, `VIDEO_ACCOUNTS` → `GOLD_MEDIA_ACCOUNTS`, `_search_video_clips` → `_search_gold_media_clips`, `_draft_video_caption` → `_draft_gold_media_caption`, `VideoClipPreview` → `GoldMediaPreview`), new Alembic migration `0008_rename_video_clip_to_gold_media.py` (revision "0008", down_revision "0007") with symmetrical `upgrade()`/`downgrade()` that UPDATE `content_bundles.content_type` and `agent_runs.agent_name`, and validation gates all green.

**Planner decision on internal helpers (not locked by CONTEXT.md):** Rename `_search_video_clips` → `_search_gold_media_clips` and `_draft_video_caption` → `_draft_gold_media_caption` (Option 1 from the constraints). Rationale: (a) D-01 mandates "full rename," and leaving two snake_case `video_clip` references inside the renamed module is a partial rename by another name; (b) D-07 already rules the same way on `VIDEO_ACCOUNTS` (another internal-only symbol — only touched by tests via `video_clip.VIDEO_ACCOUNTS`), and consistency with D-07 matters; (c) the zero-live-matches grep gate becomes trivially verifiable — "zero matches" is a simpler invariant than "zero matches except these two helpers, which are intentional"; (d) Option 2's argument ("the sub-agent still ingests video clips") is valid but collapses once you generalize: the content-type label "gold media" is about what surfaces to the user, not the internal source — and helpers that other sub-agents might grep to find "how does the video-source one search" will find them under the new name just as easily. Update all call sites in `gold_media.py` and `test_gold_media.py` accordingly.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/quick/260422-mfg-rename-sub-video-clip-to-sub-gold-media-/260422-mfg-CONTEXT.md
@CLAUDE.md

# Source files — executor should Read() these directly; do not explore the codebase for structure
@scheduler/agents/content/video_clip.py
@scheduler/agents/content/__init__.py
@scheduler/agents/content_agent.py
@scheduler/worker.py
@scheduler/models/content_bundle.py
@scheduler/tests/test_video_clip.py
@scheduler/tests/test_worker.py
@scheduler/tests/test_content_agent.py
@backend/alembic/versions/0007_add_market_snapshots.py
@backend/app/models/content_bundle.py
@backend/app/routers/queue.py
@frontend/src/config/agentTabs.ts
@frontend/src/components/content/VideoClipPreview.tsx
@frontend/src/components/approval/ContentDetailModal.tsx
@frontend/src/components/approval/__tests__/ContentDetailModal.test.tsx
@frontend/src/components/settings/AgentRunsTab.tsx
@frontend/src/pages/PerAgentQueuePage.test.tsx

<interfaces>
<!-- Pinned interfaces the executor will be rewriting. Extracted so no codebase exploration is needed. -->

From scheduler/agents/content/video_clip.py (current → target after rename):
```python
# CURRENT
CONTENT_TYPE: str = "video_clip"
AGENT_NAME: str = "sub_video_clip"
VIDEO_ACCOUNTS = [...]          # list of 7 curated Twitter handles
VIDEO_CLIP_SCORE = 7.5
async def _search_video_clips(session, tweepy_client) -> list[dict]: ...
async def _draft_video_caption(...) -> str: ...   # or similar signature — verify exact name/signature in file
async def run_draft_cycle() -> None: ...

# TARGET (after rename)
CONTENT_TYPE: str = "gold_media"
AGENT_NAME: str = "sub_gold_media"
GOLD_MEDIA_ACCOUNTS = [...]     # same 7 handles, identical order (no content change)
VIDEO_CLIP_SCORE = 7.5           # KEEP — this is a fixed-score constant, not a "name" string. Tied to X-sourced content semantics. Leaving it named VIDEO_CLIP_SCORE keeps the grep for "video_clip" at zero only if we rename it too — DECISION: rename to GOLD_MEDIA_SCORE for the same reason as _search_video_clips (consistency with D-01, zero-grep hygiene).
GOLD_MEDIA_SCORE = 7.5
async def _search_gold_media_clips(session, tweepy_client) -> list[dict]: ...
async def _draft_gold_media_caption(...) -> str: ...
async def run_draft_cycle() -> None: ...   # name unchanged — worker.py references .run_draft_cycle
```

From scheduler/worker.py (current CONTENT_CRON_AGENTS tuple for this agent at L118):
```python
# CURRENT
from agents.content import (breaking_news, threads, long_form, quotes, infographics, video_clip, gold_history)
JOB_LOCK_IDS["sub_video_clip"] = 1015
("sub_video_clip", video_clip.run_draft_cycle, "Gold Media", 1015, {"hour": 12, "minute": 0, "timezone": "America/Los_Angeles"}),

# TARGET
from agents.content import (breaking_news, threads, long_form, quotes, infographics, gold_media, gold_history)
JOB_LOCK_IDS["sub_gold_media"] = 1015   # D-06: lock_id 1015 preserved, key name changes
("sub_gold_media", gold_media.run_draft_cycle, "Gold Media", 1015, {"hour": 12, "minute": 0, "timezone": "America/Los_Angeles"}),
# Display name "Gold Media" unchanged (D-05).
# vxg-era docstring at L11 ("sub_quotes / sub_infographics / sub_video_clip all daily at 12:00...") must be rewritten to use "sub_gold_media".
```

From frontend/src/config/agentTabs.ts (L32 row, current → target):
```typescript
// CURRENT
{ slug: 'gold-media', contentType: 'video_clip', label: 'Gold Media', priority: 6, agentName: 'sub_video_clip' },
// TARGET
{ slug: 'gold-media', contentType: 'gold_media', label: 'Gold Media', priority: 6, agentName: 'sub_gold_media' },
```

From frontend/src/components/approval/ContentDetailModal.tsx (L25-31, L132):
```typescript
// CURRENT — the CONTENT_BUNDLE_TYPES map (or whatever the const is named; verify at L25-31)
const CONTENT_BUNDLE_TYPES: Record<string, boolean> = {
  infographic: true,
  thread: true,
  long_form: true,
  breaking_news: true,
  quote: true,
  video_clip: true,      // ← rename to gold_media: true
}

// Import at L30
import { VideoClipPreview } from '../content/VideoClipPreview'   // ← rename to GoldMediaPreview

// Switch branch at L132
case 'video_clip': return <VideoClipPreview draft={draft} />    // ← rename to case 'gold_media': return <GoldMediaPreview draft={draft} />
```

From frontend/src/components/settings/AgentRunsTab.tsx (L27):
```typescript
// CURRENT
{ value: 'sub_video_clip', label: 'video_clip (Gold Media)' },
// TARGET (conform to the pattern of other rows — bare snake_case agent-name as label)
{ value: 'sub_gold_media', label: 'gold_media' },
```

From backend/alembic/versions/0007_add_market_snapshots.py (the pattern executor must follow):
```python
"""<docstring>

Revision ID: 0007
Revises: 0006
Create Date: 2026-04-21
"""
revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

def upgrade() -> None: ...
def downgrade() -> None: ...
```

NEW backend/alembic/versions/0008_rename_video_clip_to_gold_media.py (target shape, per CONTEXT.md <specifics>):
```python
"""Rename video_clip → gold_media in content_bundles.content_type and agent_runs.agent_name (quick-260422-mfg).

Revision ID: 0008
Revises: 0007
Create Date: 2026-04-22
"""
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute(
        "UPDATE content_bundles SET content_type = 'gold_media' "
        "WHERE content_type = 'video_clip'"
    )
    op.execute(
        "UPDATE agent_runs SET agent_name = 'sub_gold_media' "
        "WHERE agent_name = 'sub_video_clip'"
    )

def downgrade() -> None:
    op.execute(
        "UPDATE agent_runs SET agent_name = 'sub_video_clip' "
        "WHERE agent_name = 'sub_gold_media'"
    )
    op.execute(
        "UPDATE content_bundles SET content_type = 'video_clip' "
        "WHERE content_type = 'gold_media'"
    )
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Coordinated rename across scheduler, backend, frontend, and Alembic migration (single atomic change set)</name>
  <files>
    scheduler/agents/content/video_clip.py,
    scheduler/agents/content/gold_media.py,
    scheduler/agents/content/__init__.py,
    scheduler/agents/content_agent.py,
    scheduler/models/content_bundle.py,
    scheduler/worker.py,
    scheduler/tests/test_video_clip.py,
    scheduler/tests/test_gold_media.py,
    scheduler/tests/test_worker.py,
    scheduler/tests/test_content_agent.py,
    scheduler/seed_content_data.py,
    backend/alembic/versions/0008_rename_video_clip_to_gold_media.py,
    backend/app/models/content_bundle.py,
    backend/app/routers/queue.py,
    frontend/src/components/content/VideoClipPreview.tsx,
    frontend/src/components/content/GoldMediaPreview.tsx,
    frontend/src/components/approval/ContentDetailModal.tsx,
    frontend/src/components/approval/__tests__/ContentDetailModal.test.tsx,
    frontend/src/config/agentTabs.ts,
    frontend/src/components/settings/AgentRunsTab.tsx,
    frontend/src/pages/PerAgentQueuePage.test.tsx
  </files>
  <action>
  Execute the full rename as one coordinated change set. Do NOT commit mid-task — the whole rename ships as one commit in Task 2.

  **Step 1 — Three `git mv` file renames (preserves history per constraint):**
  ```bash
  git mv scheduler/agents/content/video_clip.py scheduler/agents/content/gold_media.py
  git mv scheduler/tests/test_video_clip.py scheduler/tests/test_gold_media.py
  git mv frontend/src/components/content/VideoClipPreview.tsx frontend/src/components/content/GoldMediaPreview.tsx
  ```

  **Step 2 — Rewrite internal symbols inside the renamed scheduler module (`scheduler/agents/content/gold_media.py`):**
  - `CONTENT_TYPE: str = "video_clip"` → `CONTENT_TYPE: str = "gold_media"`
  - `AGENT_NAME: str = "sub_video_clip"` → `AGENT_NAME: str = "sub_gold_media"`
  - `VIDEO_ACCOUNTS` → `GOLD_MEDIA_ACCOUNTS` (per D-07; list contents identical — same 7 handles, same order from vxg)
  - `VIDEO_CLIP_SCORE` → `GOLD_MEDIA_SCORE` (fixed 7.5 value unchanged — only the symbol name moves for zero-grep hygiene; see planner note in <objective>)
  - `_search_video_clips` → `_search_gold_media_clips` (per planner decision in <objective>)
  - `_draft_video_caption` → `_draft_gold_media_caption` (per planner decision)
  - All internal call sites inside this file updated to match the new symbol names
  - Module docstring at L1-13: rewrite. The current docstring ends with *"Frontend label: 'Gold Media' — DB value stays ``video_clip`` for schema parity."* — replace that sentence entirely with a statement that matches the new reality, e.g.: *"Canonical name 'Gold Media' across module / constants / DB / frontend (quick-260422-mfg)."* Also update the opening line — currently reads "Video Clip (Gold Media) sub-agent — self-contained drafter." Change to "Gold Media sub-agent — self-contained drafter."
  - Any inline comments referencing "video clip" as a descriptor of *content* (e.g. "# Search X for gold-sector video posts from credible accounts") may remain — they describe the action, which still involves video posts. But comments that reference the agent *name* (e.g. "# sub_video_clip quota check") must be updated to "sub_gold_media".

  **Step 3 — Update scheduler-module consumers:**
  - `scheduler/agents/content/__init__.py`: CONTEXT.md flags docstring references at L4, L10, L74 — verify line numbers and replace "video_clip" → "gold_media" / "sub_video_clip" → "sub_gold_media" in each. If this file has an `__all__` or imports a `video_clip` name, update those too.
  - `scheduler/agents/content_agent.py`: CONTEXT.md flags L568 and L652 as `fmt == "video_clip"` branches. Change both to `fmt == "gold_media"`.
  - `scheduler/models/content_bundle.py`: L15 docstring allowed-values list — replace `video_clip` entry with `gold_media`.
  - `scheduler/worker.py`:
    - Import statement (L45-53): `video_clip` → `gold_media` in the `from agents.content import (...)` block.
    - `JOB_LOCK_IDS` (L82-91): `"sub_video_clip": 1015` → `"sub_gold_media": 1015` (D-06 — lock_id 1015 preserved exactly; only the key changes).
    - `CONTENT_CRON_AGENTS` (L115-120): the `sub_video_clip` tuple becomes `("sub_gold_media", gold_media.run_draft_cycle, "Gold Media", 1015, {"hour": 12, ...})`. Display name `"Gold Media"` is unchanged per D-05.
    - Module docstring (L1-31): the vxg-era description at ~L11 reads "sub_quotes / sub_infographics / sub_video_clip all daily at 12:00 America/Los_Angeles". Rewrite to "sub_gold_media". Same for any other `sub_video_clip` / `video_clip` mentions in the worker docstring/comments.
  - `scheduler/seed_content_data.py`: `grep` the file for any `video_clip` / `sub_video_clip` / `VIDEO_ACCOUNTS` references and update. CONTEXT.md notes "probably none, but verify" — if file has zero matches, leave untouched and drop from the commit.

  **Step 4 — Update scheduler tests:**
  - `scheduler/tests/test_gold_media.py` (the renamed file):
    - Import line: `from agents.content import video_clip` → `from agents.content import gold_media`
    - Any `video_clip.CONTENT_TYPE` / `video_clip.AGENT_NAME` / `video_clip.VIDEO_ACCOUNTS` / `video_clip.VIDEO_CLIP_SCORE` / `video_clip._search_video_clips` / `video_clip._draft_video_caption` / `video_clip.run_draft_cycle` references → `gold_media.<new-symbol-name>` per the symbol-map in Step 2.
    - Test function names that contain `video_clip` (e.g. `test_video_clip_quota_check`) → rename to `test_gold_media_*` (so the grep for `video_clip` stays clean).
    - Assertions on literal strings: `assert ... == "video_clip"` / `"sub_video_clip"` → `"gold_media"` / `"sub_gold_media"`.
    - Test count: 6 tests preserved (same fixtures, same assertions — only names and symbol refs change).
  - `scheduler/tests/test_content_agent.py`: grep for `video_clip` and update any content_type fixture strings or branch assertions.
  - `scheduler/tests/test_worker.py`:
    - Test name `test_video_clip_is_daily_cron` → `test_gold_media_is_daily_cron`.
    - `JOB_LOCK_IDS["sub_video_clip"]` assertion → `JOB_LOCK_IDS["sub_gold_media"]`.
    - Any `video_clip.run_draft_cycle` reference → `gold_media.run_draft_cycle`.
    - Any tuple membership assertion (e.g. `"sub_video_clip" in CONTENT_CRON_AGENTS` destructured) → `"sub_gold_media"`.

  **Step 5 — Backend docstring updates (comment-only — no code change):**
  - `backend/app/models/content_bundle.py` L17: docstring enumerating content_type values. Replace `video_clip` with `gold_media`.
  - `backend/app/routers/queue.py` L64: docstring referencing `video_clip` filter. Replace with `gold_media`.

  **Step 6 — Create the Alembic migration (NEW FILE — `backend/alembic/versions/0008_rename_video_clip_to_gold_media.py`):**
  Follow the `0007_add_market_snapshots.py` shape exactly (see <interfaces> block for target). Required elements:
  - Module docstring first line: `"""Rename video_clip → gold_media in content_bundles.content_type and agent_runs.agent_name (quick-260422-mfg).`
  - `revision = "0008"` (string literal, matches 0007's `revision = "0007"` style).
  - `down_revision = "0007"`.
  - `branch_labels = None`, `depends_on = None`.
  - `upgrade()`: two `op.execute(...)` calls — first updates `content_bundles`, second updates `agent_runs`. Use the exact SQL strings from the <interfaces> target block.
  - `downgrade()`: reverse order + reverse WHERE clauses (symmetric per D-08). NOTE: execute the `agent_runs` UPDATE first in downgrade, then `content_bundles` — i.e. reverse of upgrade order. This doesn't matter for correctness (no FK between those columns) but keeps the migration readable.

  This is the SINGLE allowed file where `video_clip` / `sub_video_clip` may appear post-rename (it lives in the WHERE clauses and the downgrade SET clauses by design — it's the migration's job to reference the old value).

  **Step 7 — Update frontend files:**
  - `frontend/src/components/content/GoldMediaPreview.tsx` (the renamed file): inside the file, rename the component — `export function VideoClipPreview` (or `export default function VideoClipPreview`) → `export function GoldMediaPreview` (match the existing export style; do not change from named to default or vice versa). Update any internal references to the component name (e.g. displayName, JSX tag if self-referential — unlikely but check).
  - `frontend/src/config/agentTabs.ts` L32: `contentType: 'video_clip'` → `contentType: 'gold_media'`; `agentName: 'sub_video_clip'` → `agentName: 'sub_gold_media'`. Slug (`'gold-media'`), label (`'Gold Media'`), priority (6) all unchanged.
  - `frontend/src/components/approval/ContentDetailModal.tsx`:
    - L25-31 `CONTENT_BUNDLE_TYPES` map (or whatever the const is named at L25 — read the file to confirm): `video_clip: true` → `gold_media: true`.
    - L30 import (or wherever the VideoClipPreview import lives — the line number shifts once you touch L25-31; search for the import by name): `import { VideoClipPreview } from '../content/VideoClipPreview'` → `import { GoldMediaPreview } from '../content/GoldMediaPreview'`. Adjust to match named-vs-default whichever style is actually in use.
    - L132 switch branch: `case 'video_clip': return <VideoClipPreview draft={draft} />` → `case 'gold_media': return <GoldMediaPreview draft={draft} />`.
  - `frontend/src/components/approval/__tests__/ContentDetailModal.test.tsx`: grep for `video_clip` / `VideoClipPreview` in fixtures and assertions, update each.
  - `frontend/src/components/settings/AgentRunsTab.tsx` L27: `{ value: 'sub_video_clip', label: 'video_clip (Gold Media)' }` → `{ value: 'sub_gold_media', label: 'gold_media' }` (the label pattern matches the other 5 rows, which use the bare snake_case agent-name; the parenthetical "(Gold Media)" was a transitional hint that's no longer needed).
  - `frontend/src/pages/PerAgentQueuePage.test.tsx`: grep for `video_clip` in fixtures and update.

  **Step 8 — Zero-grep sweep (BEFORE handing to Task 2):**
  Run these greps yourself and ensure zero live-code matches (the only permitted match is the Alembic migration file):
  ```bash
  grep -rn "video_clip" scheduler/ backend/app/ frontend/src/ --exclude-dir=__pycache__ --exclude-dir=node_modules --exclude-dir=dist --exclude-dir=.pytest_cache --exclude-dir=.ruff_cache --exclude="*.pyc"
  grep -rn "sub_video_clip" scheduler/ backend/app/ frontend/src/ --exclude-dir=__pycache__ --exclude-dir=node_modules --exclude-dir=dist --exclude-dir=.pytest_cache --exclude-dir=.ruff_cache --exclude="*.pyc"
  grep -rn "VideoClipPreview" frontend/src/ --exclude-dir=node_modules --exclude-dir=dist
  grep -rn "VIDEO_ACCOUNTS\|VIDEO_CLIP_SCORE" scheduler/ --exclude-dir=__pycache__ --exclude-dir=.pytest_cache --exclude-dir=.ruff_cache --exclude="*.pyc"
  ```
  Expected: first two greps return one match each (the new `0008_rename_video_clip_to_gold_media.py` — WHERE clauses + downgrade SET clauses + docstring + filename itself). Third and fourth greps return zero matches. If any other file still carries a `video_clip` / `sub_video_clip` / `VideoClipPreview` / `VIDEO_ACCOUNTS` / `VIDEO_CLIP_SCORE` reference, you missed a file — go back and fix, don't proceed to Task 2.

  **Per D-08: no backward-compat aliases.** Do not introduce `VIDEO_ACCOUNTS = GOLD_MEDIA_ACCOUNTS` shims, `video_clip` module aliases, or dual-read logic that checks for both old and new values. Single source of truth.

  **What to avoid:**
  - Do NOT use `sed -i` blindly across the repo — run targeted per-file edits so the reviewer can scan each diff. A misfired sed over `CLAUDE.md` or git-log comments could rewrite historical task-id references (e.g. CLAUDE.md's purge notes mention `video_clip` as historical context — those stay).
  - Do NOT modify the 6 other sub-agents (`breaking_news`, `threads`, `long_form`, `quotes`, `infographics`, `gold_history`) — boundary from CONTEXT.md.
  - Do NOT touch `twitter_*` config keys, `x_api_*` env wiring, or tweepy imports — the module still uses tweepy after rename; only the label changes.
  - Do NOT delete `VIDEO_CLIP_SCORE` — just rename to `GOLD_MEDIA_SCORE`. The 7.5 value is a semantic constant tied to X-sourced content scoring, still in use.
  - Do NOT commit yet. Task 2 runs validation gates and then creates the single atomic commit.

  Traceability:
  - Per D-01 (full rename depth): all layers touched.
  - Per D-02 (Alembic migration file): `0008_rename_video_clip_to_gold_media.py` created.
  - Per D-03 (frontend component full rename): `VideoClipPreview.tsx` git-mv'd.
  - Per D-04 (test file rename): `test_video_clip.py` git-mv'd, imports + symbols updated.
  - Per D-05 (worker.py display name): "Gold Media" string literal unchanged.
  - Per D-06 (lock ID 1015): preserved under new key.
  - Per D-07 (VIDEO_ACCOUNTS → GOLD_MEDIA_ACCOUNTS): applied, extended to `VIDEO_CLIP_SCORE` and the two internal helpers per planner decision.
  - Per D-08 (no backward-compat aliases): no shims introduced.
  </action>
  <verify>
    <automated>cd /Users/matthewnelson/seva-mining && grep -rn "video_clip\|sub_video_clip\|VideoClipPreview\|VIDEO_ACCOUNTS\|VIDEO_CLIP_SCORE" scheduler/ backend/app/ frontend/src/ --exclude-dir=__pycache__ --exclude-dir=node_modules --exclude-dir=dist --exclude-dir=.pytest_cache --exclude-dir=.ruff_cache --exclude="*.pyc" | grep -v "0008_rename_video_clip_to_gold_media"</automated>
  </verify>
  <done>
  - Three files renamed via `git mv` (history preserved): `scheduler/agents/content/gold_media.py`, `scheduler/tests/test_gold_media.py`, `frontend/src/components/content/GoldMediaPreview.tsx`.
  - All symbols renamed per the map in <interfaces> and <action> Step 2.
  - `scheduler/worker.py` imports `gold_media` (not `video_clip`), `JOB_LOCK_IDS["sub_gold_media"] = 1015`, and the `CONTENT_CRON_AGENTS` tuple entry uses `("sub_gold_media", gold_media.run_draft_cycle, "Gold Media", 1015, ...)`.
  - `backend/alembic/versions/0008_rename_video_clip_to_gold_media.py` exists with `revision = "0008"`, `down_revision = "0007"`, symmetric upgrade/downgrade.
  - Frontend: `agentTabs.ts` row 6 uses `contentType: 'gold_media'` and `agentName: 'sub_gold_media'`; `ContentDetailModal.tsx` imports `GoldMediaPreview` and its switch has a `case 'gold_media':` branch; `AgentRunsTab.tsx` L27 uses `'sub_gold_media'` / `'gold_media'`.
  - The verify grep above returns zero lines (the `grep -v` excludes the one allowed file). If any line remains, a file was missed.
  - No backward-compat aliases introduced.
  - The 6 other sub-agent modules are untouched (`git diff --stat scheduler/agents/content/` shows zero changes to `breaking_news.py`, `threads.py`, `long_form.py`, `quotes.py`, `infographics.py`, `gold_history.py`).
  - NOT committed yet (Task 2 commits).
  </done>
</task>

<task type="auto">
  <name>Task 2: Run all validation gates + Alembic dry-run + atomic commit</name>
  <files>
    <!-- This task only runs commands and creates the commit. It does not modify source files.
         If a validation gate fails, the executor loops back to Task 1 to fix — do NOT
         paper over failures with test-skip markers or ruff-ignore comments. -->
  </files>
  <action>
  Run the full validation gate battery from CONTEXT.md <specifics>. If any gate fails, fix the root cause in the Task 1 files (loop back — do not commit a broken rename), then re-run from the top of this task. Only create the commit once every gate is green.

  **Step 1 — Scheduler gates:**
  ```bash
  cd scheduler && uv run ruff check .
  # Expected: All checks passed.
  cd scheduler && uv run pytest -x
  # Expected: 109 passed (baseline from quick-260422-lbb — CONTEXT.md <specifics>). Rename churn should produce exactly 109 (same 6 tests in the renamed test_gold_media.py as were in test_video_clip.py pre-rename; test_worker.py still has the same number of tests, just with a renamed test function). If the count is different, investigate — a missing test or a duplicate registration bug likely exists.
  ```
  If `test_worker.py` fails on an assertion like `assert "sub_video_clip" in JOB_LOCK_IDS` or `assert job_ids == [..., "sub_video_clip", ...]`, the test was not updated in Task 1 Step 4 — go fix, don't skip.

  **Step 2 — Backend gates:**
  ```bash
  cd backend && uv run ruff check .
  # Expected: All checks passed.
  cd backend && uv run pytest -x
  # Expected: passes. Adding the new 0008 migration file should NOT affect the backend test count (Alembic test, if any, typically validates `alembic heads` returns a single head — that still holds: 0008 is the new single head). If backend pytest has an Alembic integration test that actually applies migrations, it will run 0008's upgrade() — ensure the test DB has no rows with content_type='video_clip' (fresh schema), so the UPDATE is a no-op and passes trivially.
  ```

  **Step 3 — Alembic dry-run (per CONTEXT.md specifics):**
  ```bash
  cd backend && uv run alembic heads
  # Expected: single line — "0008 (head)". If it shows "0007" or "0007 (head)", the 0008 file has wrong revision metadata or a broken down_revision chain.

  cd backend && uv run alembic history --verbose | head -40
  # Expected: 0008 → 0007 → 0006 → ... chain visible. Confirm 0008 lists 0007 as its parent.

  # Inspect the SQL that would be emitted (no DB needed):
  cd backend && uv run alembic upgrade head --sql 2>&1 | tail -50
  # Expected: output contains the two UPDATE statements from 0008's upgrade(). If the output is empty or excludes 0008, revision metadata is wrong.
  ```

  Alembic dry-run method — **choose based on DB availability**:
  - **If a local/disposable test DB is available (.env has a DATABASE_URL pointing to something non-prod):** run `cd backend && uv run alembic upgrade head` then `cd backend && uv run alembic downgrade -1` then `cd backend && uv run alembic upgrade head` again. Both must succeed.
  - **If no test DB is available:** the `--sql` inspection above is sufficient. Do NOT connect to a prod DB for validation.
  - Never run the migration against the live Railway/Neon prod DB during planning verification. The orchestrator handles prod deploy after review.

  **Step 4 — Frontend gates:**
  ```bash
  pnpm -C frontend lint
  # Expected: no errors.
  pnpm -C frontend exec tsc --noEmit
  # Expected: no errors. The `contentType: 'gold_media'` literal change + the switch case rename should both type-check cleanly. If tsc complains about the `CONTENT_BUNDLE_TYPES` const's key, it means Task 1 Step 7 missed the L25-31 map.
  pnpm -C frontend test --run
  # Expected: 52 passed (baseline from CONTEXT.md <specifics>). Rename churn only.
  pnpm -C frontend build
  # Expected: green (vite builds without warnings). A stale import to `VideoClipPreview` would fail here if tsc didn't catch it.
  ```

  **Step 5 — Final zero-live-code grep (the hard invariant):**
  ```bash
  cd /Users/matthewnelson/seva-mining && grep -rn "video_clip" scheduler/ backend/app/ frontend/src/ --exclude-dir=__pycache__ --exclude-dir=node_modules --exclude-dir=dist --exclude-dir=.pytest_cache --exclude-dir=.ruff_cache --exclude="*.pyc"
  # Expected: every matching line belongs to backend/alembic/versions/0008_rename_video_clip_to_gold_media.py (WHERE clauses in UPDATE, downgrade SET, module docstring). Zero matches anywhere else.

  grep -rn "sub_video_clip" scheduler/ backend/app/ frontend/src/ --exclude-dir=__pycache__ --exclude-dir=node_modules --exclude-dir=dist --exclude-dir=.pytest_cache --exclude-dir=.ruff_cache --exclude="*.pyc"
  # Expected: only 0008_rename_video_clip_to_gold_media.py references.

  grep -rn "VideoClipPreview" frontend/src/ --exclude-dir=node_modules --exclude-dir=dist
  # Expected: zero matches.

  grep -rn "VIDEO_ACCOUNTS\|VIDEO_CLIP_SCORE\|_search_video_clips\|_draft_video_caption" scheduler/ --exclude-dir=__pycache__ --exclude-dir=.pytest_cache --exclude-dir=.ruff_cache --exclude="*.pyc"
  # Expected: zero matches.
  ```
  Acceptable external matches (outside scheduler/, backend/app/, frontend/src/) that should NOT be scrubbed: git-log comments / historical quick-task markdown in `.planning/`, CLAUDE.md historical notes about the purge, prior DISCOVERY/SUMMARY files. Do not touch these.

  **Step 6 — Review the staged diff, then atomic commit:**
  ```bash
  cd /Users/matthewnelson/seva-mining && git status
  # Expected list (exact file set from the plan frontmatter files_modified; git mv shows as rename):
  #   renamed:    scheduler/agents/content/video_clip.py -> scheduler/agents/content/gold_media.py
  #   renamed:    scheduler/tests/test_video_clip.py -> scheduler/tests/test_gold_media.py
  #   renamed:    frontend/src/components/content/VideoClipPreview.tsx -> frontend/src/components/content/GoldMediaPreview.tsx
  #   modified:   scheduler/agents/content/__init__.py
  #   modified:   scheduler/agents/content_agent.py
  #   modified:   scheduler/models/content_bundle.py
  #   modified:   scheduler/worker.py
  #   modified:   scheduler/tests/test_worker.py
  #   modified:   scheduler/tests/test_content_agent.py
  #   (scheduler/seed_content_data.py — only if it contained matches)
  #   new file:   backend/alembic/versions/0008_rename_video_clip_to_gold_media.py
  #   modified:   backend/app/models/content_bundle.py
  #   modified:   backend/app/routers/queue.py
  #   modified:   frontend/src/config/agentTabs.ts
  #   modified:   frontend/src/components/approval/ContentDetailModal.tsx
  #   modified:   frontend/src/components/approval/__tests__/ContentDetailModal.test.tsx
  #   modified:   frontend/src/components/settings/AgentRunsTab.tsx
  #   modified:   frontend/src/pages/PerAgentQueuePage.test.tsx

  cd /Users/matthewnelson/seva-mining && git diff --stat
  # Sanity check: confirm no unexpected file appears (e.g. CLAUDE.md — it should NOT be in the diff).
  ```

  Spot-check one rename preserves history:
  ```bash
  cd /Users/matthewnelson/seva-mining && git log --follow --oneline scheduler/agents/content/gold_media.py | head -5
  # Expected: shows history back through the pre-rename video_clip.py commits (vxg, lbb, eoe). If it only shows the rename commit, `git mv` wasn't used — history lost.
  ```

  Then commit via gsd-tools (per constraint: do NOT push — orchestrator handles the merge):
  ```bash
  cd /Users/matthewnelson/seva-mining && node "$HOME/.claude/get-shit-done/bin/gsd-tools.cjs" commit "refactor(quick-260422-mfg): rename sub_video_clip → sub_gold_media across scheduler, backend, frontend, DB (follow-up (b) from zid)

- scheduler/agents/content/video_clip.py → gold_media.py (git mv, history preserved)
- CONTENT_TYPE 'video_clip' → 'gold_media'; AGENT_NAME 'sub_video_clip' → 'sub_gold_media'
- VIDEO_ACCOUNTS → GOLD_MEDIA_ACCOUNTS (D-07); VIDEO_CLIP_SCORE → GOLD_MEDIA_SCORE
- _search_video_clips → _search_gold_media_clips; _draft_video_caption → _draft_gold_media_caption (planner decision: consistency with D-01)
- worker.py: import + JOB_LOCK_IDS key + CONTENT_CRON_AGENTS tuple (lock_id 1015 preserved per D-06, display name 'Gold Media' unchanged per D-05)
- scheduler/tests/test_video_clip.py → test_gold_media.py (git mv); test_worker.py updated; 109 tests preserved
- backend/alembic/versions/0008_rename_video_clip_to_gold_media.py: NEW — UPDATE content_bundles.content_type + agent_runs.agent_name with symmetric downgrade (D-02)
- backend docstrings in app/models/content_bundle.py + app/routers/queue.py
- frontend: VideoClipPreview.tsx → GoldMediaPreview.tsx (git mv); agentTabs.ts row 6 contentType/agentName; ContentDetailModal import + branch; AgentRunsTab.tsx option
- No backward-compat aliases per D-08; eliminates gold_media/video_clip label confusion from zid debug session" --files scheduler/agents/content/gold_media.py scheduler/agents/content/__init__.py scheduler/agents/content_agent.py scheduler/models/content_bundle.py scheduler/worker.py scheduler/tests/test_gold_media.py scheduler/tests/test_worker.py scheduler/tests/test_content_agent.py scheduler/seed_content_data.py backend/alembic/versions/0008_rename_video_clip_to_gold_media.py backend/app/models/content_bundle.py backend/app/routers/queue.py frontend/src/components/content/GoldMediaPreview.tsx frontend/src/components/approval/ContentDetailModal.tsx frontend/src/components/approval/__tests__/ContentDetailModal.test.tsx frontend/src/config/agentTabs.ts frontend/src/components/settings/AgentRunsTab.tsx frontend/src/pages/PerAgentQueuePage.test.tsx
  ```

  Note on the `--files` list: if `scheduler/seed_content_data.py` had zero matches in Task 1 Step 3 and was not modified, drop it from the `--files` argument. Same logic for any other file that turned out to have no matches — don't stage an unmodified file.

  Verify post-commit:
  ```bash
  cd /Users/matthewnelson/seva-mining && git log --oneline -1
  # Expected: the refactor(quick-260422-mfg) commit at HEAD.
  cd /Users/matthewnelson/seva-mining && git status
  # Expected: working tree clean (or only unrelated untracked files).
  ```

  **Do NOT `git push` — orchestrator handles merge after review** (per constraint).
  </action>
  <verify>
    <automated>cd /Users/matthewnelson/seva-mining/scheduler && uv run ruff check . && uv run pytest -x && cd /Users/matthewnelson/seva-mining/backend && uv run ruff check . && uv run pytest -x && uv run alembic heads && cd /Users/matthewnelson/seva-mining && pnpm -C frontend lint && pnpm -C frontend exec tsc --noEmit && pnpm -C frontend test --run && pnpm -C frontend build && git log --oneline -1 | grep -q "quick-260422-mfg"</automated>
  </verify>
  <done>
  - `cd scheduler && uv run ruff check .` clean (exit 0).
  - `cd scheduler && uv run pytest -x` → 109 passed.
  - `cd backend && uv run ruff check .` clean.
  - `cd backend && uv run pytest -x` passes.
  - `cd backend && uv run alembic heads` returns `0008 (head)`.
  - `cd backend && uv run alembic upgrade head --sql` output contains both UPDATE statements (for content_bundles and agent_runs).
  - `pnpm -C frontend lint` clean.
  - `pnpm -C frontend exec tsc --noEmit` clean.
  - `pnpm -C frontend test --run` → 52 passed.
  - `pnpm -C frontend build` green.
  - All four grep sweeps in Step 5 return zero unexpected matches (only the Alembic migration file allowed to contain `video_clip` / `sub_video_clip` strings; all `VideoClipPreview` / `VIDEO_ACCOUNTS` / `VIDEO_CLIP_SCORE` / `_search_video_clips` / `_draft_video_caption` references are zero repo-wide).
  - `git log --follow` on the renamed scheduler module shows history predating the rename commit (history preserved via `git mv`).
  - Exactly ONE new commit exists on the worktree branch, titled `refactor(quick-260422-mfg): rename sub_video_clip → sub_gold_media ...`, and `git status` is clean.
  - No `git push` was executed.
  </done>
</task>

</tasks>

<verification>
Phase-level checks that should hold after both tasks complete:

1. **Canonical naming invariant:** `CLAUDE.md`'s 7 content types ("breaking news, threads, long-form, quotes, infographics, gold media, gold history") now match the code exactly — `grep -rn "gold_media\|sub_gold_media" scheduler/agents/content/ scheduler/worker.py frontend/src/config/agentTabs.ts` shows live references under the canonical name.

2. **No label/DB split remains:** The docstring phrase that triggered the zid confusion — *"Frontend label: 'Gold Media' — DB value stays video_clip for schema parity."* — no longer exists anywhere in the repo.

3. **Alembic chain is single-headed and reversible:** `alembic heads` returns exactly `0008 (head)`. `alembic upgrade head --sql` emits both UPDATE statements. If a test DB is available, `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` completes without error.

4. **Scheduler still registers 8 jobs, not 7 or 9:** Eyeball check on `worker.py` — `CONTENT_INTERVAL_AGENTS` has 3 entries, `CONTENT_CRON_AGENTS` has 4 entries (including `sub_gold_media`), plus `morning_digest`. Total 8 jobs. Lock ID 1015 appears exactly once, under `"sub_gold_media"`.

5. **Six other sub-agents untouched:** `git diff` shows zero changes to `breaking_news.py`, `threads.py`, `long_form.py`, `quotes.py`, `infographics.py`, `gold_history.py`.

6. **Single atomic commit:** `git log --oneline -1` is the mfg commit; `git log --oneline -2` shows it sits directly on top of the pre-task HEAD (no fixup commits, no intermediate "WIP" commits).

7. **Test counts unchanged from baseline:** scheduler 109, frontend 52 — CONTEXT.md <specifics> baselines held.
</verification>

<success_criteria>
Complete when:
- [ ] `scheduler/agents/content/gold_media.py` exists (renamed from `video_clip.py` via `git mv`); `CONTENT_TYPE="gold_media"`, `AGENT_NAME="sub_gold_media"`, `GOLD_MEDIA_ACCOUNTS` list of 7 handles, `GOLD_MEDIA_SCORE=7.5`, `_search_gold_media_clips` + `_draft_gold_media_caption` helpers, `run_draft_cycle` entrypoint unchanged.
- [ ] `scheduler/tests/test_gold_media.py` exists (renamed from `test_video_clip.py`); 6 tests, all referencing `gold_media.*` symbols.
- [ ] `scheduler/worker.py` imports `gold_media` in the `from agents.content import (...)` block; `JOB_LOCK_IDS["sub_gold_media"] = 1015`; `CONTENT_CRON_AGENTS` contains `("sub_gold_media", gold_media.run_draft_cycle, "Gold Media", 1015, {...})`.
- [ ] `backend/alembic/versions/0008_rename_video_clip_to_gold_media.py` exists with `revision="0008"`, `down_revision="0007"`, symmetric upgrade/downgrade.
- [ ] `alembic heads` returns `0008 (head)`.
- [ ] `frontend/src/components/content/GoldMediaPreview.tsx` exists (renamed); component export is `GoldMediaPreview`.
- [ ] `frontend/src/config/agentTabs.ts` row 6: `contentType: 'gold_media'`, `agentName: 'sub_gold_media'`.
- [ ] `frontend/src/components/approval/ContentDetailModal.tsx` imports `GoldMediaPreview`, CONTENT_BUNDLE_TYPES key is `gold_media`, switch has `case 'gold_media'`.
- [ ] `frontend/src/components/settings/AgentRunsTab.tsx` option 7 is `{ value: 'sub_gold_media', label: 'gold_media' }`.
- [ ] Repo-wide grep: zero `video_clip` / `sub_video_clip` / `VideoClipPreview` / `VIDEO_ACCOUNTS` / `VIDEO_CLIP_SCORE` live-code matches outside `backend/alembic/versions/0008_rename_video_clip_to_gold_media.py` (which is the single allowed location).
- [ ] All validation gates green: scheduler ruff clean + pytest 109; backend ruff clean + pytest pass + alembic heads=0008; frontend lint clean + tsc --noEmit clean + vitest 52 + build green.
- [ ] `git log --follow` on the renamed scheduler module shows history predating the rename (history preserved).
- [ ] Exactly one new commit on the worktree branch, titled `refactor(quick-260422-mfg): rename sub_video_clip → sub_gold_media ...`.
- [ ] Not pushed (orchestrator handles merge).
</success_criteria>

<output>
After completion, create `.planning/quick/260422-mfg-rename-sub-video-clip-to-sub-gold-media-/260422-mfg-SUMMARY.md` documenting:
- Files renamed via `git mv` (3 files)
- Symbol-rename map applied (CONTENT_TYPE, AGENT_NAME, GOLD_MEDIA_ACCOUNTS, GOLD_MEDIA_SCORE, _search_gold_media_clips, _draft_gold_media_caption, GoldMediaPreview)
- Alembic migration 0008 details (UPDATE counts if run against a DB, or `--sql` inspection if dry-run only)
- Validation gate results (scheduler 109 / backend pass / frontend 52 / build green / zero-grep)
- Planner decision on internal helpers (renamed for consistency, per rationale in <objective>)
- Any files originally in the scope list that were dropped from the commit because they had zero matches (e.g. `seed_content_data.py` if empty)
- Cross-references: zid (debug session that flagged this), vxg (last touched the module), lbb (previous rename-shaped task for pattern), eoe (original 7-agent split that introduced the mismatch)
- Follow-up (a) still queued: "why does sub_video_clip/sub_gold_media produce 0 items" — separate `/gsd:debug` session, NOT addressed by this rename
</output>
