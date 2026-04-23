---
quick_task: 260423-k8n
slug: remove-sub-long-form-sub-agent-entirely
subsystem: scheduler/agents + backend + frontend + docs
tags: [sub-agent-removal, topology, 7-to-6, long_form-purge]
created: 2026-04-23
mode: quick --discuss
---

# Quick Task 260423-k8n: Remove `sub_long_form` Sub-Agent Entirely

## User's verbatim ask

> "I want to fully get rid of long-form. If there is more longer-form content, it should just fall under threads. Makes things simpler. Continue on with the other edits we are implementing right now."

## One-liner

Fully purge the `sub_long_form` sub-agent from the 7-sub-agent topology, reducing the system to a 6-sub-agent topology (`sub_breaking_news`, `sub_threads`, `sub_quotes`, `sub_infographics`, `sub_gold_media`, `sub_gold_history`). Historical `content_type='long_form'` rows remain in the DB untouched. Pattern matches the `260419-lvy` (Instagram purge) and `260420-sn9` (Twitter Agent + Senior Agent purge) precedents.

## Why now

The recent pipeline shape work (`260423-hq7` max_count fix, `260423-d30` quotes independence, `260423-of3` infographics independence, `260423-j7x` bearish filter) explicitly gated "5 caller modules unchanged" — and `long_form.py` was one of those 5 callers. This task intentionally inverts that gate: `long_form.py` is deleted, not preserved. All prior work is fully compatible with this removal; nothing in hq7/d30/of3/j7x depends on long_form existing.

## Decision lock (from --discuss phase)

| # | Question | Decision | Rationale |
|---|----------|----------|-----------|
| Q1 | Does threads change shape to absorb longer content? | **No change — threads stays short-thread shape** | User's "makes things simpler" intent. Threads keeps its current 3-5 tweet fact-rich voice. No prompt change. Un-does no part of `260422-r0r`'s long_form-specific sharpening but preserves threads' tight identity. |
| Q2 | What happens to long_form's 4h cron slot (offset 34 min)? | **Delete entirely — 7→6 jobs** | Cleanest. Scheduler runs 6 sub-agents + morning_digest = 7 jobs total. Cron slot is reclaimed, not reassigned. If threads volume needs increasing later, that's a separate decision driven by observed output. |
| Q3 | Migrate historical `content_type='long_form'` DB rows? | **Leave as-is — NO Alembic migration** | Matches lvy/sn9 precedent. Zero schema change, zero migration, zero data loss. Historical rows persist as archival data. Frontend filters out the deprecated agent from active views; URLs that hit the deprecated content_type return empty result sets. |
| Q4 | How should frontend handle `/agent/sub_long_form`? | **Remove route + nav entry entirely** | User said "fully get rid of." Bookmark-breakage acceptable for single-user internal tool. Cleanest UX — no ghost entries in sidebar/dropdown. |
| Q5 | Should threads keep `dedup_scope="cross_agent"` (BN pairing)? | **Keep default `cross_agent`** | Preserves BN-priority-then-threads unity from the original topology spec. Removing long_form doesn't change the pairing intent for threads. |
| Q6 | Keep long_form.py as dead code or delete? | **Delete `long_form.py` + `test_long_form.py` entirely** | Matches lvy Instagram purge pattern. Dead code rots. Git history preserves the old implementation if anyone ever needs it. |
| Q7 | How to update CLAUDE.md + STATE.md references to "7 sub-agents"? | **Update active counts to "6" + add historical note (2026-04-23)** | Follows the existing lvy/sn9 historical-note pattern. Current prose reflects current reality; history preserves removal trajectory. |

## Scope — code surfaces to touch

### DELETE (whole files)

| File | Lines | Reason |
|------|-------|--------|
| `scheduler/agents/content/long_form.py` | 145 | Full drafter module — Q6-A |
| `scheduler/tests/test_long_form.py` | 89 (4 tests) | Test file — Q6-A |
| `frontend/src/components/content/LongFormPreview.tsx` | 44 | Unused after ContentDetailModal loses its long_form branch |

### MODIFY (scheduler/)

| File | Changes |
|------|---------|
| `scheduler/worker.py` | Remove: L9 (comment), L48 (`long_form` import), L86 (`"sub_long_form": 1012` JOB_LOCK_ID), L97 (stagger offsets comment), L104 (`("sub_long_form", ...)` CONTENT_INTERVAL_AGENTS entry), L261 (docstring), L275 (log format string). Stagger offsets reduce from `[0, 17, 34]` → `[0, 17]`. |
| `scheduler/agents/content_agent.py` | Remove `long_form` branches: L16 (`classify_format_lightweight` docstring), L214 (same), L218 (valid_formats set — drop `"long_form"`), L231 (prompt text), L586-587 (`build_draft_item` `elif fmt == "long_form"` branch), L679 (`_extract_check_text` `parts.append(draft_content.get("long_form_post", ""))` inside thread branch — **KEEP**: this is a thread-format compat field, not a long_form-format reference; removing it changes thread behavior), L680-681 (`_extract_check_text` `elif fmt == "long_form"` branch), L878 (docstring). |
| `scheduler/agents/content/__init__.py` | Check for any `long_form` prose references and remove. `run_text_story_cycle` signature itself is untouched. |
| `scheduler/models/content_bundle.py` | L15 — remove `long_form` from the content_type comment list. |
| `scheduler/tests/test_worker.py` | Remove: L98 (expected JOB_LOCK_ID), L128 (expected agent list), L146 (expected agent list), L174 (expected interval map). Test count drops by 0 (tests update in place). |
| `scheduler/tests/test_content_agent.py` | L230 — remove `"long_form"` from expected-formats tuple in `test_classify_format_returns_one_of_valid_formats`. |
| `scheduler/tests/test_content_init.py` | L29 — update comment (`breaking_news, threads, long_form, infographics`) → `breaking_news, threads, infographics`. No logic change. |

### MODIFY (backend/)

| File | Changes |
|------|---------|
| `backend/app/models/content_bundle.py` | L17 — remove `long_form` from content_type comment list. |
| `backend/app/routers/queue.py` | L63 — remove `long_form` from docstring content_type enumeration. |

### MODIFY (frontend/)

| File | Changes |
|------|---------|
| `frontend/src/config/agentTabs.ts` | L29 — delete the `long-form` entry from `CONTENT_AGENT_TABS`. Priority numbers on remaining entries stay as-is (gaps are fine — priority is sort-only). Alternatively renumber 3→3 for quotes etc. (cosmetic). |
| `frontend/src/components/approval/ContentDetailModal.tsx` | L12 — remove `import { LongFormPreview }`. L27 — remove `long_form: true` from `CONTENT_TYPE_HAS_PREVIEW` (or equivalent). L126-127 — remove `case 'long_form': return <LongFormPreview draft={draft} />`. Falls through to default text renderer. |
| `frontend/src/components/approval/__tests__/ContentDetailModal.test.tsx` | L136 (long_form_post test fixture), L153-172 (Test 3 — "renders LongFormPreview when bundle.content_type === 'long_form'") — delete the test block. |
| `frontend/src/components/content/ThreadPreview.tsx` | L8, L14 — **KEEP** the `long_form_post` field. This is a thread-format compat field (the `thread` draft shape carries a `long_form_post` sibling from the pre-split monolithic content agent). Removing it would require modifying the threads drafter's output shape — out of scope for this task (Q1-A: threads unchanged). |
| `frontend/src/components/settings/AgentRunsTab.tsx` | L15 — update comment ("7 sub-agents" → "6 sub-agents"; list shows 6 names). L25 — delete the `{ value: 'sub_long_form', label: 'long_form' }` dropdown entry. |
| `frontend/src/pages/PerAgentQueuePage.test.tsx` | L90-98 — delete the `'renders the Long-form tab'` test block. |

### MODIFY (docs)

| File | Changes |
|------|---------|
| `CLAUDE.md` | Change "7-sub-agent" → "6-sub-agent" in active prose (opening paragraph). Remove `sub_long_form` from the agent name list in the existing `260420-sn9` historical note (OR leave that note as-is since it's historical — Q7 clarification: leave historical notes untouched, update only current-state prose). Add new historical note dated 2026-04-23 under the existing note pattern explaining the long_form removal and rationale. Update the 7→6 job count in the scheduler description. |
| `.planning/STATE.md` | Topology section — change "7 sub-agents" → "6 sub-agents". Add quick task row for k8n in the Quick Tasks Completed table. Update "Last activity:" prose. Roll frontmatter `stopped_at` and `last_updated` forward. |
| `.planning/REQUIREMENTS.md` | If it references 7 sub-agents or long_form, update counts and add note. (Verify during planner phase.) |
| `.planning/ROADMAP.md` | If it references long_form as a deliverable, add strikethrough-with-note or remove. (Verify during planner phase.) |

### NO CHANGE (confirm unchanged)

- DB schema — no Alembic migration (Q3-A)
- `content_bundles.content_type` column — stays `String(50)` with historical `'long_form'` values preserved
- `draft_items` table — no changes
- `agent_runs` table — historical `agent_name='sub_long_form'` rows preserved
- `scheduler/seed_content_data.py` — no config keys to remove (long_form had no dedicated config flag)
- `scheduler/agents/content/threads.py` — Q1-A: threads stays short-thread shape, zero prompt change
- `scheduler/agents/content/breaking_news.py`, `quotes.py`, `infographics.py`, `gold_media.py`, `gold_history.py` — unchanged (no long_form references to remove)
- `morning_digest` job in `scheduler/worker.py` — unchanged

## Validation gates (expected outcomes)

```bash
# Scheduler
grep -rn "long_form\|sub_long_form\|LongForm" scheduler/ --include="*.py"
  → Zero matches (except possibly 1 comment in CHANGELOG-style docstring if we keep a tombstone — aim for zero)

grep -n "sub_long_form" scheduler/worker.py
  → Zero matches

uv run pytest scheduler/ -x
  → All green. Expected count: 131 → 127 (test_long_form.py drops 4 tests)

uv run ruff check scheduler/
  → Clean

# Backend
grep -rn "long_form\|LongForm" backend/ --include="*.py"
  → Zero matches (except possibly content_bundle.py L17 comment — remove)

uv run pytest backend/ -x
  → All green

# Frontend
grep -rn "long_form\|LongForm\|long-form\|sub_long_form" frontend/src/
  → Zero matches (ThreadPreview.tsx L8,14 `long_form_post` is a thread-compat field — intentional keep; aim for zero OUTSIDE that file)

pnpm -C frontend lint
  → Clean

pnpm -C frontend exec tsc --noEmit
  → Clean (no unused imports after LongFormPreview is deleted)

pnpm -C frontend build
  → Success

pnpm -C frontend test
  → All green (PerAgentQueuePage.test.tsx + ContentDetailModal.test.tsx both drop their long_form test blocks)

# Docs
grep -rn "7-sub-agent\|7 sub-agents" CLAUDE.md .planning/
  → Only in historical notes (lvy, sn9). Active prose says "6-sub-agent" / "6 sub-agents".

grep -rn "sub_long_form" CLAUDE.md .planning/
  → Only in historical notes (sn9 pre-existing; new k8n historical note).
```

## Test count movement

| Suite | Before | After | Delta |
|-------|--------|-------|-------|
| `scheduler/` pytest | 131 | 127 | −4 (test_long_form.py removed) |
| `backend/` pytest | unchanged | unchanged | 0 |
| `frontend/` vitest | N | N−2 | −2 (PerAgentQueuePage long-form test + ContentDetailModal long_form test) |

## Related recent work

- **`260419-lvy`** — full purge of Instagram agent. Reference pattern for "remove an agent cleanly." Dormant references left in content-agent output fields (instagram_post etc.) as inert.
- **`260420-sn9`** — Twitter Agent + Senior Agent purge, 3→1 agent reduction, CLAUDE.md historical-note pattern established.
- **`260421-eoe`** — the 7-sub-agent split that *created* `sub_long_form` in the first place. The original rationale was to give long-form content a dedicated drafter with a 400-char minimum floor. That rationale is now superseded by "makes things simpler."
- **`260422-r0r`** — long_form 400-char floor + thread-vs-long_form prompt sharpening. This work gets partially unwound: the 400-char floor and long_form-specific drafter are deleted; the threads prompt sharpening (tight 3-5 tweet fact-rich voice) is preserved.
- **`260423-hq7` / `260423-d30` / `260423-of3` / `260423-j7x`** — the "5 callers unchanged" gate in those tasks included long_form. That gate no longer applies to k8n — long_form is intentionally deleted. All 4 prior tasks remain fully compatible.

## Scope constraints

- **Single atomic commit** if possible, OR a 2-commit sequence (backend + frontend) if the diff spans too many files cleanly. Planner decides.
- **No DB migration.** Period.
- **No prompt changes to threads.py.** Threads stays short-thread shape.
- **No threads cron frequency change.** Threads stays every 4h offset 17 min; long_form's 34-min offset is simply retired.
- **Leave historical planning docs (phase-07/11 PLANs, older quick-task SUMMARYs) untouched.** Only update active-state docs (CLAUDE.md, STATE.md, REQUIREMENTS.md, ROADMAP.md).

## Self-check criteria for planner

- [ ] No code path left where removing `long_form.py` causes an ImportError
- [ ] `classify_format_lightweight` valid_formats set stays aligned with `build_draft_item` branches (both lose the `long_form` entry)
- [ ] `CONTENT_INTERVAL_AGENTS` tuple structure is preserved (just one fewer entry)
- [ ] `ContentDetailModal.tsx` type narrowing on `content_type` works after `long_form: true` removal
- [ ] All tests that reference `sub_long_form`, `long_form` format, or `/agents/long-form` URL are updated or deleted
- [ ] Historical `content_type='long_form'` rows in the DB remain queryable (schema unchanged)
- [ ] CLAUDE.md active prose + new historical note both land in the same commit
