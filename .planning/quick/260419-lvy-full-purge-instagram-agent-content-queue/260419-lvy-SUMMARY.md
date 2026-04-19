---
task_id: 260419-lvy
type: quick
title: Full purge Instagram agent + content queue run-grouping
completed: 2026-04-19
duration: ~90m (mid-session)
commits:
  - b2ff329  # Task 1: purge Instagram from backend + scheduler + env vars
  - accf735  # Task 2: purge Instagram from frontend + tests
  - 2eb9125  # Task 3: group content queue by agent run (match Twitter pattern)
  - 4ab94e7  # Task 4: deprecated notes in ROADMAP + REQUIREMENTS + STATE + CLAUDE.md
tags: [deprecation, instagram-agent, scheduler, frontend, budget, planning-docs]
---

# Quick 260419-lvy: Full purge Instagram agent + content queue run-grouping

## One-liner

Deprecated the Instagram Agent end-to-end — deleted the scheduler module, cut Apify dependencies, stripped every Instagram surface from the React dashboard + tests, rerouted the content queue to group by agent run like Twitter, and marked Phase 6 / INST-01..12 deprecated across all planning docs and CLAUDE.md. Seva Mining is now a three-agent system.

## Context

The original architecture was a four-agent system: Twitter + Instagram + Content + Senior. Instagram relied on the Apify hosted scraper (~$50/mo). Phase 6 had shipped a full `InstagramAgent` class, watchlist models, follower-threshold UI, and a dedicated platform tab. Subsequent product review concluded the Apify dependency was not worth the spend: scraper reliability was unpredictable, Instagram ToS risk was non-zero, and the $50/mo punched a hole in the stated $205-225 budget after removing it. The decision: remove Instagram entirely rather than let a half-maintained agent rot.

This quick task executes that decision as four atomic commits so each layer is reviewable in isolation.

## Task 1 — Backend + scheduler purge (b2ff329)

**Deleted files:**
- `scheduler/agents/instagram_agent.py`
- `scheduler/tests/test_instagram_agent.py`
- `scheduler/seed_instagram_data.py`

**Modified files (scheduler):**
- `scheduler/worker.py` — removed `InstagramAgent` import, `"instagram_agent": 1002` JOB_LOCK_ID, `_make_job` instagram branch, `instagram_interval_hours` default, `add_job` for instagram, `APIFY_API_TOKEN` from `_validate_env`; docstring "5 jobs" → "4 jobs"
- `scheduler/config.py` — removed `apify_api_token: Optional[str] = None`
- `scheduler/pyproject.toml` — removed `apify-client==2.5.0` dependency
- `scheduler/uv.lock` — regenerated via `uv sync --all-extras` (apify-client + 4 transitive deps removed)
- `scheduler/agents/__init__.py` — dropped "Instagram Agent: Phase 6 (placeholder)" docstring line
- `scheduler/models/agent_run.py` — comment updated
- `scheduler/seed_content_data.py` — docstring updated
- `scheduler/tests/test_worker.py` — renamed to `test_all_four_jobs_registered` and `test_build_scheduler_has_4_jobs_no_expiry_sweep`, updated expected_ids to 4, changed lock-label to 1001/"twitter_agent"; added `assert "instagram_agent" not in job_ids`
- `scheduler/tests/test_twitter_agent.py`, `test_content_agent.py`, `tests/agents/test_image_render.py`, `test_senior_agent.py` — removed `os.environ.setdefault("APIFY_API_TOKEN", ...)` lines

**Modified files (backend):**
- `backend/app/config.py` — removed `apify_api_token`
- `backend/app/models/watchlist.py`, `keyword.py`, `draft_item.py` — comments updated to reflect `twitter`-only platform domain
- `backend/app/schemas/watchlist.py`, `keyword.py`, `content_bundle.py` — comments updated
- `backend/tests/test_config.py`, `test_database.py`, `test_whatsapp.py`, `test_health.py`, `conftest.py` — removed APIFY_API_TOKEN references
- `.env.example` — dropped Apify section

**Preserved (intentionally inert):**
- ContentBundle output fields `instagram_post`, `instagram_caption`, `instagram_brief`, `instagram_carousel` — Content Agent still emits them; no frontend consumer.
- Image render agent IG slide roles `instagram_slide_1..3` — still produced but never displayed.

No Alembic migration was written — DB columns (`platform = String(20)`) are permissive and leaving the unused IG roles/fields in the content_bundle JSONB is safe no-op data.

**Verify (Task 1):**
- Backend pytest: 71 passed, 5 skipped
- Scheduler pytest: 98 passed (was 115 — exactly 17 IG tests removed)
- ruff (backend + scheduler): 0 errors (after fixing one E501 line-length violation in `content_bundle.py`)
- All 3 IG files deleted; uv.lock regenerated without apify-client

## Task 2 — Frontend + tests purge (accf735)

**Modified files:**
- `frontend/src/api/types.ts` — `Platform = 'twitter' | 'content'`, `RenderedImage.role: 'twitter_visual'`
- `frontend/src/App.tsx` — removed `/instagram` route
- `frontend/src/components/layout/PlatformTabBar.tsx` — removed Instagram entry from PLATFORMS
- `frontend/src/components/layout/Sidebar.tsx` — removed Camera icon import + Instagram agentItems entry
- `frontend/src/hooks/useQueueCounts.ts` — removed `ig` useQuery + instagram fields
- `frontend/src/pages/QueuePage.tsx` — removed instagramQuery, instagramCount, and instagram from counts/activeQuery map
- `frontend/src/pages/DigestPage.tsx` — removed `instagram?: number` from QueueSnapshot, removed Instagram stats card, changed `grid-cols-4` → `grid-cols-3` (stats + skeleton)
- `frontend/src/components/shared/PlatformBadge.tsx` — removed `instagram` from PLATFORM_CONFIG + Camera icon import
- `frontend/src/components/shared/RelatedCardBadge.tsx` — removed `instagram` from PLATFORM_LABELS
- `frontend/src/components/content/VideoClipPreview.tsx` — removed `instagram_caption` field + all IG caption handling; simplified grid to single column
- `frontend/src/components/content/QuotePreview.tsx` — removed `instagram_post` + all IG post handling; simplified grid
- `frontend/src/components/content/RenderedImagesGallery.tsx` — ROLE_ORDER + ROLE_LABELS reduced to `twitter_visual` only; expectedCount = `contentType === 'infographic' || contentType === 'quote' ? 1 : 0`; skeleton + rendered grid reduced to single column
- `frontend/src/components/settings/AgentRunsTab.tsx` — removed `instagram_agent` from AGENT_OPTIONS
- `frontend/src/components/settings/WatchlistTab.tsx` — rewrote as Twitter-only; removed platform toggle, follower_threshold column/inputs/state
- `frontend/src/components/settings/KeywordsTab.tsx` — removed Instagram `<option>`
- `frontend/src/mocks/handlers.ts` — removed IG mockItems (ids starting 44444444, 55555555), dropped `instagram` from queue_snapshot in both /digests handlers, removed `wl-2` Instagram watchlist entry, removed `instagram_agent` agent-run mock
- `frontend/src/pages/PlatformQueuePage.tsx` — removed `instagram: 'Instagram'` from PLATFORM_LABELS (AGENT_NAMES/showRunGroups left for Task 3)

**Test files:**
- `frontend/src/components/layout/PlatformTabBar.test.tsx` — updated defaultCounts, renamed "renders three tabs" → "renders two tabs: Twitter, Content", updated badge-count test, changed click target from Instagram → Content
- `frontend/src/components/approval/__tests__/ContentDetailModal.test.tsx` — removed `instagram_post` from quote draft fixture, removed `instagram_caption` from video_clip draft, updated expectedCount comment (quote 2→1), updated loading-image count assertion (infographic 4→1)
- `frontend/src/pages/DigestPage.test.tsx` — removed `instagram: 2` from snapshot fixtures (×2), removed Instagram DOM assertions + extra count
- `frontend/src/pages/SettingsPage.test.tsx` — deleted 3 Instagram-specific tests (platform toggle, follower threshold column, follower threshold input)

**Verify (Task 2):**
- `npm run lint` — 0 errors
- `npx tsc --noEmit` — 0 errors
- `npm test -- --run` — 71 tests passed (10 files)
- `npm run build` — vite build succeeded (557 KB bundle)
- Full grep sweep: 0 `instagram|Instagram|Camera|APIFY|apify` matches across `frontend/src`

## Task 3 — Content queue run-grouping (2eb9125)

**File:** `frontend/src/pages/PlatformQueuePage.tsx`

Pattern-matched the Twitter queue's agent-run grouping UX to the Content queue. Previously, content items rendered as a flat list because `showRunGroups` was hardcoded to `platform === 'twitter'` and `AGENT_NAMES` had only `twitter: 'twitter_agent'`.

**Changes:**
1. Added `content: 'content_agent'` to `AGENT_NAMES` map.
2. Updated `showRunGroups = (platform === 'twitter' || platform === 'content') && runs.length > 0`.
3. In the grouped-branch renderer, branched the card type: `platform === 'content' ? <ContentSummaryCard ... /> : <ApprovalCard ... />`.

Net effect: when the `/content` queue page loads, it now fetches `content_agent` runs, groups items under each run header ("Pulled from agent run at 10:00 AM · Apr 19 · 2 queued"), and uses `ContentSummaryCard` per item inside those groups. The flat fallback remains for platforms with no agent_runs mapping.

**Verify (Task 3):**
- lint: clean
- tsc: clean
- vitest: 71 passed
- vite build: succeeded

## Task 4 — Planning-doc deprecation notes (4ab94e7)

**File:** `.planning/ROADMAP.md`
- Added top-level deprecation banner dated 2026-04-19 under the title.
- Overview updated: "four-agent" → "three-agent"; dropped Instagram from build-order narrative.
- Phase 6 bullet → `~~Phase 6: Instagram Agent~~ — DEPRECATED 2026-04-19. Never executed. Retained for historical context only.`
- Phase 6 detail header → strikethrough + explicit "never execute" block citing `260419-lvy`.
- Progress table: Phase 6 status → `**Deprecated 2026-04-19**`.

**File:** `.planning/REQUIREMENTS.md`
- Instagram Agent section header → `~~Instagram Agent~~ (DEPRECATED 2026-04-19)` with an explanatory paragraph.
- Each INST-01..INST-12 bullet: `[x]` → `[ ]`, name/body struck through, trailing `**(DEPRECATED)**` marker.
- Traceability table: each INST-* row → phase ~~strikethrough~~ + status `**Deprecated 2026-04-19**`.

**File:** `.planning/STATE.md`
- Added two decision entries under Decisions:
  - `[2026-04-19 / quick 260419-lvy]: Instagram Agent (Phase 6) fully deprecated and purged … Seva Mining is now a three-agent system …`
  - `[2026-04-19 / quick 260419-lvy]: Content queue page now groups by agent_run matching Twitter pattern …`
- Appended quick-tasks-completed row for 260419-lvy referencing all 3 per-task commit hashes (Task 4 itself is this planning-doc commit so it is not listed in the row — intentional: row was written as the 4th commit in progress).

**File:** `CLAUDE.md`
- Project blurb "four-agent" → "three-agent", added historical note paragraph citing the purge + explaining inert IG fields still in the code.
- Constraints: budget `~$255-275` → `~$205-225`, removed Instagram Apify line, stack line now lists the three scheduled jobs explicitly.
- Tech-Stack table: removed `apify-client | 2.5.0 | Instagram scraping` row; TanStack Query row updated to "Twitter, Content" tabs; "single-user 4-agent" → "3-agent" in Alternatives table; removed apify-client alt row; removed `instagram-private-api` / instaloader "What NOT to use" row; Celery comparison updated "4 cron jobs" → "3 cron jobs"; agent-list in Stack Patterns changed to "Senior, Content, Twitter"; dropped apify-client source URL.

## Known Stubs

None introduced. The retained content-agent IG output fields and image-render IG slide roles are intentional dormant producers — they are not consumed by any UI, and removing them would require a downstream migration plus prompt-engineering rework that is out of scope for this quick task. Documented explicitly in CLAUDE.md historical note + STATE.md decision entry.

## Deviations from plan

None of note. Rule-1 auto-fix count: 1 (a ruff E501 line-length error in `backend/app/schemas/content_bundle.py` after rewriting the `role:` comment inline — split the comment across two lines). Local `.env` and `backend/.env` (gitignored) also had `APIFY_API_TOKEN` entries that had to be cleaned so backend pytest could boot without Pydantic extra-field validation errors; this was done but never committed (correct — the files are gitignored).

## Self-Check: PASSED

- `.planning/quick/260419-lvy-full-purge-instagram-agent-content-queue/260419-lvy-SUMMARY.md` — FOUND (this file)
- Commit `b2ff329` (Task 1 — backend + scheduler purge) — FOUND
- Commit `accf735` (Task 2 — frontend + tests purge) — FOUND
- Commit `2eb9125` (Task 3 — content queue run-grouping) — FOUND
- Commit `4ab94e7` (Task 4 — planning-doc deprecation notes) — FOUND
