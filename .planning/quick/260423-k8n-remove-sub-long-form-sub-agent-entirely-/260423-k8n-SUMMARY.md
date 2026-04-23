---
task_id: 260423-k8n
type: quick
title: Remove sub_long_form Sub-Agent Entirely (Topology 7→6)
completed: 2026-04-23
duration: ~90m
commits: ["<pending>"]
tags: [sub-agent-removal, topology, 7-to-6, long_form-purge, cleanup]
subsystem: scheduler + backend + frontend + docs
---

# Quick Task 260423-k8n: Remove sub_long_form Sub-Agent Entirely

## One-liner

Fully purged the `sub_long_form` sub-agent from Seva Mining's scheduler, backend, frontend, and active planning docs — reducing the topology from 7 sub-agents to 6 (`sub_breaking_news`, `sub_threads`, `sub_quotes`, `sub_infographics`, `sub_gold_media`, `sub_gold_history`). The scheduler drops from 8 jobs to 7. Historical `content_type='long_form'` DB rows are preserved untouched. The `long_form_post` thread compat field (ThreadPreview.tsx + content_agent.py thread branch) is retained.

## Context

**Why now:** User request: "I want to fully get rid of long-form. If there is more longer-form content, it should just fall under threads. Makes things simpler." Sub_long_form had been producing output but added complexity without clear differentiated value — the threads sub-agent already handles longer analytical perspectives in a 3-5 tweet format.

**Precedent pattern:** Mirrors the `260419-lvy` (Instagram purge) and `260420-sn9` (Twitter + Senior purge) precedents. Partially unwinds `260419-r0r` (long_form 400-char floor) and `260421-eoe` (the 7-sub-agent split that created `sub_long_form`).

**Decision locks (from --discuss phase):**
- Q1-A: Threads stays short-thread shape — no prompt change
- Q2-A: 4h cron slot (offset 34 min) deleted entirely, not reassigned
- Q3-A: No Alembic migration — historical DB rows preserved as archival data
- Q4-A: Remove route + nav entry entirely (bookmark-breakage acceptable for single-user tool)
- Q6-A: Delete `long_form.py` + `test_long_form.py` entirely (matches lvy Instagram pattern)
- Q7-A: Update active counts to "6" + add historical note (2026-04-23)

## Task 1 — Scheduler + Tests Purge

**Files deleted:**
- `scheduler/agents/content/long_form.py` (full drafter module)
- `scheduler/tests/test_long_form.py` (4 tests)

**Files modified:**
- `scheduler/worker.py` — removed `long_form` import, `"sub_long_form": 1012` from `JOB_LOCK_IDS`, `("sub_long_form", ...)` tuple from `CONTENT_INTERVAL_AGENTS`, docstrings updated (8 jobs → 7 jobs), log format string updated
- `scheduler/agents/content_agent.py` — removed `long_form` from `valid_formats` set (4 elements now: breaking_news, thread, infographic, quote), from Haiku prompt text, from `build_draft_item` `elif fmt == "long_form"` branch, from `_extract_check_text` `elif fmt == "long_form"` branch, from module docstring (L16), from `classify_format_lightweight` docstring (L214), from `fetch_stories` docstring (L878)
- `scheduler/agents/content/__init__.py` — updated docstring from "7 sub-agents" to "6 sub-agents", "5 of 7" to "4 of 6" sub-agents using `run_text_story_cycle`, `sort_by` docstring drops `long_form` from list
- `scheduler/models/content_bundle.py` — removed `long_form` from `content_type` column comment
- `scheduler/agents/content/quotes.py` — removed `long_form` from docstring
- `scheduler/tests/test_worker.py` — updated 5 tests: `test_sub_agents_total_six` (7→6), staggering offsets ([0,17,34]→[0,17]), lock IDs dict (removed `sub_long_form:1012`), retired crons set (added `sub_long_form` assertion), `test_scheduler_registers_7_jobs` (8→7), interval cadences dict (removed `sub_long_form:4`)
- `scheduler/tests/test_content_agent.py` — updated `test_classify_format_lightweight_returns_sub_agent_filter_strings` to check 4 strings and assert `long_form` absent
- `scheduler/tests/test_content_init.py` — updated comment from "4 other sub-agents" to "3 other sub-agents", removed `long_form` from list

**Verification:** `uv run pytest scheduler/ -x` → 127 passed (was 131; −4 from test_long_form.py deletion). `uv run ruff check scheduler/` → clean.

## Task 2 — Backend Docstring Cleanup

**Files modified:**
- `backend/app/models/content_bundle.py` — removed `long_form` from `content_type` column comment (L17)
- `backend/app/routers/queue.py` — removed `long_form` from docstring content_type enumeration (L63)

**No code/behavior change — comment edits only. No Alembic migration (Q3-A).**

**Verification:** `grep -rn "long_form|LongForm" backend/ --include="*.py"` → 0 matches. `uv run pytest backend/ -x` → 69 passed, 5 skipped (unchanged).

## Task 3 — Frontend + Tests Purge

**Files deleted:**
- `frontend/src/components/content/LongFormPreview.tsx`

**Files modified:**
- `frontend/src/config/agentTabs.ts` — removed `long-form` entry from `CONTENT_AGENT_TABS` (6 entries now), updated comment header from "7 content sub-agent tabs" to "6"
- `frontend/src/components/approval/ContentDetailModal.tsx` — removed `import { LongFormPreview }`, removed `long_form: true` from `FORMAT_RENDERERS`, removed `case 'long_form': return <LongFormPreview draft={draft} />` from switch
- `frontend/src/components/settings/AgentRunsTab.tsx` — removed `{ value: 'sub_long_form', label: 'long_form' }` from `AGENT_OPTIONS`, updated comment from "7 sub-agents" to "6"
- `frontend/src/components/approval/__tests__/ContentDetailModal.test.tsx` — deleted Test 3 (`renders LongFormPreview when bundle.content_type === "long_form"` block at L153-172); Test 2's thread fixture `long_form_post: 'Long form version here.'` at L136 **PRESERVED** (thread-compat field)
- `frontend/src/pages/PerAgentQueuePage.test.tsx` — deleted `renders the Long-form tab and queries with contentType=long_form` test block (L90-98)

**Explicit preservations:**
- `frontend/src/components/content/ThreadPreview.tsx` L8, L14 — `long_form_post?: string` field and `longFormPost` const — KEPT (thread-format compat, Q1-A)
- `ContentDetailModal.test.tsx` L136 — `long_form_post: 'Long form version here.'` inside Test 2's thread fixture — KEPT (thread-compat, not long_form content type)

**Verification:**
- `grep -rn "long_form|LongForm|long-form|sub_long_form" frontend/src/ --include="*.ts" --include="*.tsx" | grep -v ".test."` → only ThreadPreview.tsx (L8, L14) + k8n tombstone comments
- `tsc --noEmit` → 0 errors
- `pnpm lint` → clean
- `pnpm test --run` → 54 passed (was 56; −2: ContentDetailModal Test 3 + PerAgentQueuePage Long-form tab)
- `pnpm build` → success (533.77 kB)

## Task 4 — Docs Refresh

**Files modified:**
- `CLAUDE.md` — updated opening paragraph: "7-sub-agent" → "6-sub-agent", "7 content types" → "6 content types" (removed long-form from list). Updated Constraints stack line: "eight scheduled jobs: 7 sub-agents" → "seven scheduled jobs: 6 sub-agents". Appended new `> **Historical note (2026-04-23):**` blockquote below the sn9 note. Historical sn9 note (mentioning sub_long_form in its agent list) left UNTOUCHED (it is history).
- `.planning/STATE.md` — updated frontmatter `stopped_at` and `last_updated`, added k8n row to Quick Tasks Completed table, added decision entry to Decisions log, updated "Stopped at" in session footer
- `.planning/REQUIREMENTS.md` — appended `(long_form format retired 2026-04-23 — see quick 260423-k8n)` to CONT-09; updated CREV-06 to remove `long_form` from active formats list with retirement note
- `.planning/ROADMAP.md` — added retirement notes to Phase 7 bullet, Phase 11 bullet, Phase 7 goal success criterion 3, Phase 11 success criterion 2, Phase 11 scope decisions (image formats bullet)

## Preserved Surfaces (Regression Guards)

| Surface | Reason | Status |
|---------|--------|--------|
| `ThreadPreview.tsx` L8, L14 — `long_form_post?: string` | Thread-format compat field — thread sub-agent outputs a long-form X companion post | KEPT |
| `content_agent.py` L676 — `parts.append(draft_content.get("long_form_post", ""))` inside `elif fmt == "thread":` | Thread draft compliance check assembles all thread text including the long-form companion | KEPT |
| `ContentDetailModal.test.tsx` L136 — `long_form_post: 'Long form version here.'` in Test 2 thread fixture | Thread fixture must include `long_form_post` per ThreadDraft interface | KEPT |
| `scheduler/agents/content/threads.py` prompt (no change) | Q1-A: threads stays short-thread shape, zero prompt change | KEPT |
| DB schema `content_bundles.content_type = String(50)` | Q3-A: no migration — historical `long_form` rows preserved as archival | KEPT |
| Lock ID 1012 (sub_long_form) | Retired, not reassigned — DB advisory locks auto-release | RETIRED (intentional) |

## Known Stubs

None. All changes are complete removals or tombstone documentation. The `long_form_post` thread compat field retention is intentional (Q1-A decision lock), not a stub.

## Deviations from Plan

**[Rule 1 - Bug / Oversight] One additional test in test_worker.py required updating:**

- **Found during:** T5 (first pytest run after T1-T5 changes)
- **Issue:** `test_sub_agents_total_seven` asserted `len(CONTENT_INTERVAL_AGENTS) + len(CONTENT_CRON_AGENTS) == 7` — this test was not in the PLAN.md enumeration (plan listed 4 test lines at L98, L128, L146, L174 but omitted this structural-count test at L77-81)
- **Fix:** Updated test to `test_sub_agents_total_six` asserting `== 6` (2 interval + 4 cron)
- **Files modified:** `scheduler/tests/test_worker.py`
- **Commit:** included in atomic commit

**[Docstring cleanup] quotes.py had an overlooked `long_form` mention:**

- **Found during:** Gate 1.1 grep
- **Issue:** `scheduler/agents/content/quotes.py` L202 docstring read "dedup only against other quotes vs breaking_news / threads / long_form" — technically still true (historical rows), but cleaner to remove
- **Fix:** Updated docstring to drop `long_form` from the list
- **Files modified:** `scheduler/agents/content/quotes.py`
- **Commit:** included in atomic commit

## Test Count Movement

| Suite | Before | After | Delta |
|-------|--------|-------|-------|
| `scheduler/` pytest | 131 | 127 | −4 (`test_long_form.py` deleted) |
| `backend/` pytest | 69 passed, 5 skipped | 69 passed, 5 skipped | 0 |
| `frontend/` vitest | 56 | 54 | −2 (ContentDetailModal Test 3 + PerAgentQueuePage Long-form tab) |

## Self-Check

**Files deleted — confirmed gone:**
- `scheduler/agents/content/long_form.py` — DELETED
- `scheduler/tests/test_long_form.py` — DELETED
- `frontend/src/components/content/LongFormPreview.tsx` — DELETED

**Explicit keeps — confirmed present:**
- `frontend/src/components/content/ThreadPreview.tsx` L8, L14 — `long_form_post` compat field — PRESENT
- `scheduler/agents/content_agent.py` L676 — `parts.append(draft_content.get("long_form_post", ""))` inside thread branch — PRESENT
- `ContentDetailModal.test.tsx` L136 — thread fixture `long_form_post` — PRESENT

**Validation gates:**
- Gate 1.1: `grep "long_form|sub_long_form|LongForm" scheduler/ --include="*.py"` → only k8n tombstone comments + `long_form_post` compat field at content_agent.py:676 + threads.py:86 prompt spec + test_content_agent.py assertion verifying absence
- Gate 1.2: `grep -n "sub_long_form" scheduler/worker.py` → only tombstone comments (lines 99-100, 266)
- Gate 1.3: Deleted files confirmed absent
- Gate 1.4: `uv run pytest scheduler/ -x` → 127 passed
- Gate 1.5: `uv run ruff check scheduler/` → clean
- Gate 2.1: `grep -rn "long_form|LongForm" backend/ --include="*.py"` → 0 matches
- Gate 2.2: `uv run pytest backend/ -x` → 69 passed, 5 skipped
- Gate 3.1: Frontend non-test long_form grep → only ThreadPreview.tsx (L8, L14) + k8n tombstone comments
- Gate 3.2: `tsc --noEmit` → 0 errors
- Gate 3.3: `pnpm lint` → clean
- Gate 3.4: `pnpm test --run` → 54 passed
- Gate 3.5: `pnpm build` → success
- Gate 4.1: `grep -n "7-sub-agent|7 sub-agents" CLAUDE.md | grep -v "^[0-9]*:>"` → 0 matches (all surviving refs are inside historical blockquotes)
- Gate 4.2: `grep -c "6-sub-agent" CLAUDE.md` → 2; `grep -c "Historical note (2026-04-23)" CLAUDE.md` → 1
- Gate 4.3: `grep -c "260423-k8n" .planning/STATE.md` → ≥3

**Commit SHA:** `<pending>` — update after commit lands
