---
phase: quick-260419-lvy
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  # --- Task 1: Backend + Scheduler + env purge ---
  - scheduler/agents/instagram_agent.py          # DELETE
  - scheduler/tests/test_instagram_agent.py      # DELETE
  - scheduler/seed_instagram_data.py             # DELETE
  - scheduler/agents/__init__.py
  - scheduler/worker.py
  - scheduler/config.py
  - scheduler/pyproject.toml                     # drop apify-client dep
  - scheduler/tests/test_worker.py               # update job-set expectations + remove APIFY env seed
  - scheduler/tests/test_twitter_agent.py        # remove APIFY env seed
  - scheduler/tests/test_content_agent.py        # remove APIFY env seed
  - scheduler/tests/agents/test_image_render.py  # remove APIFY env seed (IG-slide test data stays)
  - backend/app/config.py
  - backend/app/models/watchlist.py              # comment only
  - backend/app/models/keyword.py                # comment only
  - backend/app/models/draft_item.py             # comment only
  - backend/app/schemas/watchlist.py             # comment only (str remains unvalidated)
  - backend/app/schemas/keyword.py               # comment only
  - backend/app/schemas/content_bundle.py        # comment only
  - backend/tests/test_config.py                 # drop APIFY_API_TOKEN key
  - backend/tests/test_database.py               # drop APIFY_API_TOKEN setenv
  - backend/tests/test_whatsapp.py               # drop apify_api_token kwarg
  - .env.example
  # --- Task 2: Frontend purge ---
  - frontend/src/api/types.ts
  - frontend/src/App.tsx
  - frontend/src/components/layout/PlatformTabBar.tsx
  - frontend/src/components/layout/Sidebar.tsx
  - frontend/src/hooks/useQueueCounts.ts
  - frontend/src/pages/QueuePage.tsx
  - frontend/src/pages/DigestPage.tsx
  - frontend/src/components/shared/PlatformBadge.tsx
  - frontend/src/components/shared/RelatedCardBadge.tsx
  - frontend/src/components/content/VideoClipPreview.tsx
  - frontend/src/components/content/QuotePreview.tsx
  - frontend/src/components/content/RenderedImagesGallery.tsx
  - frontend/src/components/settings/AgentRunsTab.tsx
  - frontend/src/components/settings/WatchlistTab.tsx
  - frontend/src/components/settings/KeywordsTab.tsx
  - frontend/src/mocks/handlers.ts
  - frontend/src/components/layout/PlatformTabBar.test.tsx
  - frontend/src/components/approval/__tests__/ContentDetailModal.test.tsx
  - frontend/src/pages/DigestPage.test.tsx
  - frontend/src/pages/SettingsPage.test.tsx
  # --- Task 3: Content queue run-grouping ---
  - frontend/src/pages/PlatformQueuePage.tsx
  # --- Task 4: Planning doc deprecation notes ---
  - .planning/ROADMAP.md
  - .planning/REQUIREMENTS.md
  - .planning/STATE.md
  - CLAUDE.md
autonomous: true
requirements:
  - "INST-01 through INST-12 (deprecated: Instagram agent purged, not implemented)"

must_haves:
  truths:
    - "Instagram no longer appears as a selectable platform anywhere in the dashboard (no tab, no sidebar link, no route, no queue counter, no settings option)."
    - "Scheduler no longer imports, schedules, or runs InstagramAgent — build_scheduler() returns 4 jobs (content_agent, twitter_agent, morning_digest, gold_history_agent); instagram_agent job ID is absent."
    - "APIFY_API_TOKEN no longer appears in backend Settings, scheduler Settings, or .env.example (.env.example shrinks from 20 secret keys to 19)."
    - "Content queue cards render grouped under 'Pulled from agent run at HH:mm · MMM d' headers when content_agent runs exist, matching the existing Twitter pattern."
    - "Backend pytest suite: 71 passed (unchanged). Scheduler pytest suite: ~98 passed (115 − 17 IG tests). Frontend vitest: 74 passed minus any IG-specific assertions that were removed; no new failures."
    - "ruff check on backend and scheduler reports 0 errors. npm run lint on frontend reports 0 errors. npx tsc --noEmit is clean. npm run build succeeds."
    - "ROADMAP.md, REQUIREMENTS.md, STATE.md, and CLAUDE.md each carry a visible deprecated note dated 2026-04-19 (260419-lvy) documenting the Instagram agent removal while preserving historical Phase 6 / INST-* plan references."
  artifacts:
    - path: "scheduler/agents/instagram_agent.py"
      provides: "DELETED — Instagram Agent module removed"
      contains: "(file must not exist)"
    - path: "scheduler/tests/test_instagram_agent.py"
      provides: "DELETED — Instagram Agent test file removed"
      contains: "(file must not exist)"
    - path: "scheduler/seed_instagram_data.py"
      provides: "DELETED — Instagram seed script removed"
      contains: "(file must not exist)"
    - path: "scheduler/worker.py"
      provides: "No InstagramAgent import, no instagram_agent branch in _make_job, no instagram_agent scheduler.add_job call, no apify_api_token reference in _validate_env"
      min_lines: 300
    - path: "scheduler/config.py"
      provides: "Settings class with no apify_api_token field"
      min_lines: 30
    - path: "backend/app/config.py"
      provides: "Settings class with no apify_api_token field"
      min_lines: 45
    - path: "scheduler/pyproject.toml"
      provides: "apify-client dependency removed from [project].dependencies"
    - path: ".env.example"
      provides: "APIFY_API_TOKEN line removed; '# Apify — Instagram scraper' section header removed"
    - path: "frontend/src/api/types.ts"
      provides: "Platform = 'twitter' | 'content'; RenderedImage.role = 'twitter_visual' (IG slide variants dropped)"
    - path: "frontend/src/components/layout/PlatformTabBar.tsx"
      provides: "PLATFORMS array has 2 entries (twitter, content) — no instagram"
    - path: "frontend/src/pages/PlatformQueuePage.tsx"
      provides: "showRunGroups includes 'content' platform; AGENT_NAMES maps content→'content_agent'; grouped-branch renders ContentSummaryCard for content platform"
      min_lines: 180
    - path: ".planning/ROADMAP.md"
      provides: "Phase 6 Instagram Agent section has a DEPRECATED banner dated 2026-04-19 (260419-lvy)"
    - path: ".planning/REQUIREMENTS.md"
      provides: "INST-01 through INST-12 have a `(deprecated 2026-04-19 — 260419-lvy)` marker"
    - path: "CLAUDE.md"
      provides: "Project description reads 'monitors the gold sector on X (Twitter)' — no Instagram; apify-client row removed from stack table; historical note about removal at 2026-04-19 present"
  key_links:
    - from: "scheduler/worker.py"
      to: "JOB_LOCK_IDS dict and build_scheduler add_job calls"
      via: "registered job set"
      pattern: "instagram_agent"
      expected: "absent (grep for 'instagram_agent' in scheduler/worker.py returns 0 matches)"
    - from: "frontend/src/pages/PlatformQueuePage.tsx"
      to: "showRunGroups boolean"
      via: "platform check"
      pattern: "platform === 'twitter' \\|\\| platform === 'content'"
    - from: "frontend/src/pages/PlatformQueuePage.tsx"
      to: "grouped-branch item renderer"
      via: "group.items.map"
      pattern: "platform === 'content' \\? <ContentSummaryCard"
    - from: "scheduler/tests/test_worker.py"
      to: "expected_ids set in test_all_five_jobs_registered"
      via: "test assertion"
      pattern: "expected_ids = \\{[^}]*\"content_agent\"[^}]*\"twitter_agent\"[^}]*\"morning_digest\"[^}]*\"gold_history_agent\"[^}]*\\}"
      expected: "4 entries, no 'instagram_agent'; test name may be renamed to test_all_four_jobs_registered"
---

<objective>
Full purge of the Instagram Agent from the Seva Mining codebase (Option C — no historical data to preserve) and addition of agent-run grouping to the Content queue matching the existing Twitter pattern.

Purpose:
1. The Instagram Agent was built in Phase 6 but never ran in production. Apify scraping infrastructure and APIFY_API_TOKEN are unused overhead. Keeping dead code causes drift (see 260419-l5t cleanup touching APIFY env values) and confuses the roadmap/requirements story.
2. The Content queue currently renders a flat list while the Twitter queue groups items by agent run with timestamped headers. Bringing Content to the same pattern makes the dashboard consistent for the operator.

Output:
- Scheduler: `instagram_agent.py`, `seed_instagram_data.py`, `test_instagram_agent.py` deleted; worker registers 4 jobs (was 5); `apify-client` dep and `APIFY_API_TOKEN` env removed; scheduler pytest count drops from ~115 to ~98.
- Backend: `apify_api_token` field removed from `Settings`; Python model/schema comments updated; backend pytest unchanged at 71.
- Frontend: `Platform` type narrowed to `'twitter' | 'content'`; Instagram tab, sidebar link, route, queue counter, settings options, and rendered-image IG slide role all removed; `npm test -- --run` passes minus any IG-specific assertions; build/lint/typecheck clean.
- Content queue: `showRunGroups` extended to `content` platform with `ContentSummaryCard` rendering inside the grouped branch.
- Planning docs: ROADMAP / REQUIREMENTS / STATE / CLAUDE.md carry visible deprecated markers; history preserved.

Each task lands as a single atomic commit. Four commits total. No migration, no push to origin.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/ROADMAP.md
@.planning/REQUIREMENTS.md
@CLAUDE.md
@.env.example

<!-- Code files: read only what's relevant to each task -->
@scheduler/worker.py
@scheduler/config.py
@scheduler/agents/__init__.py
@scheduler/pyproject.toml
@scheduler/tests/test_worker.py
@backend/app/config.py
@backend/app/models/watchlist.py
@backend/app/models/keyword.py
@backend/app/models/draft_item.py
@backend/app/schemas/watchlist.py
@backend/app/schemas/keyword.py
@backend/app/schemas/content_bundle.py
@frontend/src/api/types.ts
@frontend/src/App.tsx
@frontend/src/components/layout/PlatformTabBar.tsx
@frontend/src/components/layout/Sidebar.tsx
@frontend/src/hooks/useQueueCounts.ts
@frontend/src/pages/QueuePage.tsx
@frontend/src/pages/PlatformQueuePage.tsx
@frontend/src/pages/DigestPage.tsx
@frontend/src/mocks/handlers.ts
@frontend/src/components/content/VideoClipPreview.tsx
@frontend/src/components/content/RenderedImagesGallery.tsx
@frontend/src/components/content/QuotePreview.tsx
@frontend/src/components/shared/PlatformBadge.tsx
@frontend/src/components/shared/RelatedCardBadge.tsx
@frontend/src/components/settings/AgentRunsTab.tsx
@frontend/src/components/settings/WatchlistTab.tsx
@frontend/src/components/settings/KeywordsTab.tsx
@frontend/src/components/layout/PlatformTabBar.test.tsx
@frontend/src/components/approval/__tests__/ContentDetailModal.test.tsx
@frontend/src/pages/DigestPage.test.tsx
@frontend/src/pages/SettingsPage.test.tsx

<interfaces>
<!-- Key contracts the executor needs. Extracted from codebase. -->
<!-- Do not re-explore. -->

Scheduler worker currently registers 5 jobs (from scheduler/worker.py build_scheduler):
  content_agent, twitter_agent, instagram_agent, morning_digest, gold_history_agent
  with JOB_LOCK_IDS = {twitter_agent:1001, instagram_agent:1002, content_agent:1003,
  morning_digest:1005, gold_history_agent:1009}.
After purge: 4 jobs (no instagram_agent), JOB_LOCK_IDS entry 1002 removed.

scheduler/tests/test_worker.py currently has an assertion:
  `expected_ids = {"content_agent", "twitter_agent", "instagram_agent",
                   "morning_digest", "gold_history_agent"}`
  and the test function is `test_all_five_jobs_registered`.
  A later test `test_build_scheduler_has_5_jobs_no_expiry_sweep` asserts
  `len(job_ids) == 5`. Both must be updated to 4 jobs.
  An earlier test uses `"instagram_agent"` as the lock-label string in a call
  to `with_advisory_lock(...)` — replace that test's label with another existing
  job name (e.g., "twitter_agent") or delete the assertion entirely.

frontend Platform type (src/api/types.ts):
  export type Platform = 'twitter' | 'instagram' | 'content'   → 'twitter' | 'content'
  RenderedImage.role:
    'twitter_visual' | 'instagram_slide_1' | 'instagram_slide_2' | 'instagram_slide_3'
    → 'twitter_visual'

frontend/src/pages/PlatformQueuePage.tsx has the grouping logic pattern on
line 112: `const showRunGroups = platform === 'twitter' && runs.length > 0`
and an AGENT_NAMES map at line 21: `{twitter: 'twitter_agent'}`.
The unified-branch renderer at lines 161-168 handles `platform === 'content' ? <ContentSummaryCard /> : <ApprovalCard />`.
After change: showRunGroups covers both twitter and content; AGENT_NAMES also maps
`content: 'content_agent'`; the grouped branch's `group.items.map` uses the
same ContentSummaryCard/ApprovalCard conditional.

ContentBundle internals (deep inside content_agent.py) still emit
instagram_post / instagram_caption / instagram_brief / instagram_carousel JSON
and image_render_agent still renders instagram_slide_* images for infographic
and quote formats. These are NOT removed in this task — they are content-side
cross-posting artifacts, not the Instagram destination-platform agent.
Frontend simply stops rendering them (VideoClipPreview, QuotePreview,
RenderedImagesGallery drop their IG branches). Scheduler pytest file
scheduler/tests/agents/test_image_render.py and test_image_render_prompts.py
reference "instagram_slide_*" in test data — LEAVE those references intact;
they are asserting the image_render_agent's role emission, not the IG destination.
Only remove the `os.environ.setdefault("APIFY_API_TOKEN", ...)` line from
test_image_render.py (line 31).

backend tests that currently seed APIFY_API_TOKEN via setenv/Settings kwargs:
  backend/tests/test_config.py line 38   → drop APIFY_API_TOKEN dict entry
  backend/tests/test_database.py line 20 → drop monkeypatch.setenv line
  backend/tests/test_whatsapp.py line 29 → drop apify_api_token="test-token" kwarg
All three files: no other IG refs.

Expected post-task test counts:
  Backend pytest: 71 (unchanged)
  Scheduler pytest: 115 − 17 (IG test file) = 98 (± a couple if test_worker.py splits any assertions)
  Frontend vitest: 74 − the IG-specific `it()` blocks removed (see Task 2 test edits) + 0 new tests = ~70-72
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Purge Instagram from backend + scheduler + env vars</name>
  <files>
    scheduler/agents/instagram_agent.py (DELETE),
    scheduler/tests/test_instagram_agent.py (DELETE),
    scheduler/seed_instagram_data.py (DELETE),
    scheduler/agents/__init__.py,
    scheduler/worker.py,
    scheduler/config.py,
    scheduler/pyproject.toml,
    scheduler/tests/test_worker.py,
    scheduler/tests/test_twitter_agent.py,
    scheduler/tests/test_content_agent.py,
    scheduler/tests/agents/test_image_render.py,
    backend/app/config.py,
    backend/app/models/watchlist.py,
    backend/app/models/keyword.py,
    backend/app/models/draft_item.py,
    backend/app/schemas/watchlist.py,
    backend/app/schemas/keyword.py,
    backend/app/schemas/content_bundle.py,
    backend/tests/test_config.py,
    backend/tests/test_database.py,
    backend/tests/test_whatsapp.py,
    .env.example
  </files>
  <action>
    Delete files (use `rm`, commit the deletions):
      - scheduler/agents/instagram_agent.py
      - scheduler/tests/test_instagram_agent.py
      - scheduler/seed_instagram_data.py

    scheduler/agents/__init__.py:
      Remove "- Instagram Agent: Phase 6 (placeholder)" line from docstring.
      (The file currently only imports/exports TwitterAgent, so no InstagramAgent
      import to remove. Verify with grep before saving.)

    scheduler/worker.py:
      1. Delete `from agents.instagram_agent import InstagramAgent` (around line 24).
      2. Delete `"instagram_agent": 1002,` entry from JOB_LOCK_IDS dict.
      3. Delete the entire `elif job_name == "instagram_agent":` branch (5 lines)
         inside `_make_job().job()`.
      4. Delete the `instagram_interval_hours` default from the `defaults` dict in
         `_read_schedule_config` AND remove the line that reads it and the
         scheduler.add_job(..., id="instagram_agent", ...) block in build_scheduler.
      5. Update the `logger.info("Schedule config: ...")` format string to drop
         `instagram=%dh` and its argument.
      6. In `_validate_env`, remove `"APIFY_API_TOKEN": bool(settings.apify_api_token)`
         from the `optional` dict.
      7. In `_make_job` docstring, remove the `instagram_agent: InstagramAgent().run()
         [Phase 6 — INST-01]` line.

    scheduler/config.py:
      Remove `apify_api_token: Optional[str] = None` line (around line 26).

    scheduler/pyproject.toml:
      Remove `"apify-client==2.5.0",` line from the `dependencies` list
      (around line 14). Run `cd scheduler && uv sync --all-extras` afterwards to
      regenerate uv.lock (uv.lock is NOT in files_modified because uv regenerates
      it automatically; but stage it with `git add scheduler/uv.lock`).

    scheduler/tests/test_worker.py:
      1. Delete the `os.environ.setdefault("APIFY_API_TOKEN", "x")` line (line 24).
      2. In `test_job_exception_does_not_propagate`, change the lock-label argument
         from `"instagram_agent"` to `"twitter_agent"` (line 67) — the test is
         about generic advisory-lock behavior, label is incidental.
      3. In `test_all_five_jobs_registered`: rename to `test_all_four_jobs_registered`;
         update `expected_ids` to `{"content_agent", "twitter_agent", "morning_digest",
         "gold_history_agent"}`; update the docstring comment.
      4. In `test_build_scheduler_has_5_jobs_no_expiry_sweep`: rename to
         `test_build_scheduler_has_4_jobs_no_expiry_sweep`; change
         `assert len(job_ids) == 5` to `== 4`; remove the `"instagram_agent" in job_ids`
         assertion if present (there isn't one currently, but double-check).
      5. In `test_read_schedule_config_defaults_no_expiry_sweep`: add an assertion
         `assert "instagram_interval_hours" not in source` to pin the cleanup.

    scheduler/tests/test_twitter_agent.py and scheduler/tests/test_content_agent.py:
      Delete the `os.environ.setdefault("APIFY_API_TOKEN", "test-apify-token")`
      line (test_twitter_agent.py line 26; test_content_agent.py similar — grep
      to find exact line). Leave all other env defaults and test bodies intact.

    scheduler/tests/agents/test_image_render.py:
      Delete line 31: `os.environ.setdefault("APIFY_API_TOKEN", "test-apify-token")`.
      DO NOT touch any "instagram_slide_*" or "instagram_brief" test fixtures —
      those assert the image_render_agent's role-emission behavior which is
      unrelated to the Instagram destination-platform agent being purged.
      Same rule for test_image_render_prompts.py — leave it untouched.

    backend/app/config.py:
      Remove `apify_api_token: str | None = None` (line 31).

    backend/app/models/watchlist.py:
      Line 14 comment: `# twitter, instagram` → `# twitter`.

    backend/app/models/keyword.py:
      Line 13 comment: `# twitter, instagram, content, or null=all` →
      `# twitter, content, or null=all`.

    backend/app/models/draft_item.py:
      Line 31 comment: `# twitter, instagram, content` → `# twitter, content`.

    backend/app/schemas/watchlist.py:
      Line 8 comment: `# twitter or instagram` → `# twitter` (platform field
      remains `str` — no Literal validation, so runtime behavior unchanged).

    backend/app/schemas/keyword.py:
      Line 9 comment: `# twitter, instagram, content, or null=all` →
      `# twitter, content, or null=all`.

    backend/app/schemas/content_bundle.py:
      Line 26 comment: update to drop the instagram_slide_* enumeration —
      change to `# "twitter_visual" (IG slide roles still emitted by image_render
      but frontend renders only twitter_visual after 260419-lvy)`.
      DO NOT add a Literal — role field stays `str` so existing DB rows with
      instagram_slide_* values remain loadable.

    backend/tests/test_config.py:
      Delete line 38: `"APIFY_API_TOKEN": "apifytest",` entry from the
      `required_vars` dict.

    backend/tests/test_database.py:
      Delete line 20: `monkeypatch.setenv("APIFY_API_TOKEN", "apifytest")`.

    backend/tests/test_whatsapp.py:
      Delete line 29: `apify_api_token="test-token",` kwarg from the
      `_make_settings()` Settings() call.

    .env.example:
      Delete the `APIFY_API_TOKEN=` line (line 26) AND its comment header
      `# Apify — Instagram scraper` (line 25). The block between SerpAPI and
      Twilio should collapse cleanly. File now contains 19 secret env keys
      (down from 20). Leave all other sections untouched.

    Verification sweep (run before committing):
      - `grep -rn "instagram_agent\|InstagramAgent\|apify\|Apify\|APIFY" scheduler/ backend/` —
        only allowed surviving matches: scheduler/tests/agents/test_image_render*.py
        with `instagram_slide_*` or `instagram_brief` string fixtures (they test
        the role-emission contract of image_render_agent, not the IG agent);
        scheduler/agents/content_agent.py with `instagram_post`, `instagram_caption`,
        `instagram_brief`, `instagram_carousel` (these are content-bundle output
        fields for cross-posting, NOT the IG agent — leave them alone per user
        constraint "Do NOT write a DB migration"); backend/app/schemas/content_bundle.py
        updated comment.
      - `grep -rn "apify-client" scheduler/` → only scheduler/uv.lock lock entries;
        scheduler/pyproject.toml should have zero matches.

    Commands to run after edits:
      cd backend && uv run pytest -q           # expect: 71 passed
      cd scheduler && uv sync --all-extras     # regenerate uv.lock without apify-client
      cd scheduler && uv run pytest -q         # expect: ~98 passed (was 115)
      cd backend && uv run ruff check .        # expect: 0 errors
      cd scheduler && uv run ruff check .      # expect: 0 errors

    Commit:
      git add -A   # picks up deletions + edits + uv.lock regeneration
      git commit -m "feat(quick-lvy): purge Instagram from backend + scheduler + env vars"

      Do NOT push.
  </action>
  <verify>
    <automated>
cd /Users/matthewnelson/seva-mining/backend && uv run pytest -q 2>&1 | tail -5 \
  && cd /Users/matthewnelson/seva-mining/scheduler && uv run pytest -q 2>&1 | tail -5 \
  && cd /Users/matthewnelson/seva-mining/backend && uv run ruff check . 2>&1 | tail -3 \
  && cd /Users/matthewnelson/seva-mining/scheduler && uv run ruff check . 2>&1 | tail -3 \
  && test ! -f /Users/matthewnelson/seva-mining/scheduler/agents/instagram_agent.py \
  && test ! -f /Users/matthewnelson/seva-mining/scheduler/tests/test_instagram_agent.py \
  && test ! -f /Users/matthewnelson/seva-mining/scheduler/seed_instagram_data.py \
  && ! grep -q "APIFY_API_TOKEN" /Users/matthewnelson/seva-mining/.env.example \
  && ! grep -q "apify_api_token" /Users/matthewnelson/seva-mining/backend/app/config.py /Users/matthewnelson/seva-mining/scheduler/config.py \
  && ! grep -q "instagram_agent\|InstagramAgent" /Users/matthewnelson/seva-mining/scheduler/worker.py \
  && echo "TASK 1 VERIFY: PASS"
    </automated>
  </verify>
  <done>
    - Three files (instagram_agent.py, test_instagram_agent.py, seed_instagram_data.py) deleted
    - scheduler/worker.py has 0 matches for 'instagram' / 'InstagramAgent' / 'apify_api_token'
    - scheduler/config.py and backend/app/config.py have no apify_api_token field
    - scheduler/pyproject.toml has no apify-client dependency
    - .env.example has no APIFY_API_TOKEN line and is now 19 secret-keys
    - backend/app/models + schemas have updated platform comments, no Literal enforcement added
    - Backend pytest: 71 passed; Scheduler pytest: ~98 passed; ruff on both: 0 errors
    - Atomic commit `feat(quick-lvy): purge Instagram from backend + scheduler + env vars` landed (not pushed)
  </done>
</task>

<task type="auto">
  <name>Task 2: Purge Instagram from frontend + tests</name>
  <files>
    frontend/src/api/types.ts,
    frontend/src/App.tsx,
    frontend/src/components/layout/PlatformTabBar.tsx,
    frontend/src/components/layout/Sidebar.tsx,
    frontend/src/hooks/useQueueCounts.ts,
    frontend/src/pages/QueuePage.tsx,
    frontend/src/pages/DigestPage.tsx,
    frontend/src/components/shared/PlatformBadge.tsx,
    frontend/src/components/shared/RelatedCardBadge.tsx,
    frontend/src/components/content/VideoClipPreview.tsx,
    frontend/src/components/content/QuotePreview.tsx,
    frontend/src/components/content/RenderedImagesGallery.tsx,
    frontend/src/components/settings/AgentRunsTab.tsx,
    frontend/src/components/settings/WatchlistTab.tsx,
    frontend/src/components/settings/KeywordsTab.tsx,
    frontend/src/mocks/handlers.ts,
    frontend/src/components/layout/PlatformTabBar.test.tsx,
    frontend/src/components/approval/__tests__/ContentDetailModal.test.tsx,
    frontend/src/pages/DigestPage.test.tsx,
    frontend/src/pages/SettingsPage.test.tsx
  </files>
  <action>
    frontend/src/api/types.ts:
      1. Line 2: `export type Platform = 'twitter' | 'instagram' | 'content'`
         → `export type Platform = 'twitter' | 'content'`
      2. Line 54: `role: 'twitter_visual' | 'instagram_slide_1' | 'instagram_slide_2' | 'instagram_slide_3'`
         → `role: 'twitter_visual'`

    frontend/src/components/layout/PlatformTabBar.tsx:
      Remove `{ value: 'instagram', label: 'Instagram' },` from PLATFORMS array
      (line 12). Result: 2 entries (twitter, content).

    frontend/src/components/layout/Sidebar.tsx:
      Remove the Instagram agentItems entry (lines 30-34). Also remove the
      `Camera` icon import from lucide-react (line 2) — unused after removal.
      `counts.instagram` / `counts.instagramHasMore` references removed along
      with the item.

    frontend/src/hooks/useQueueCounts.ts:
      1. Remove the `ig = useQuery(...)` block for instagram (lines 19-23).
      2. Remove `instagram: ...` and `instagramHasMore: ...` from the returned
         object.
      3. Remove `instagram: number; instagramHasMore: boolean;` from the
         QueueCounts interface.

    frontend/src/App.tsx:
      Remove the `<Route path="/instagram" element={<PlatformQueuePage platform="instagram" />} />`
      line (line 22).

    frontend/src/pages/QueuePage.tsx (legacy tabbed queue page):
      1. Remove `const instagramQuery = useQueue('instagram')` (line 15).
      2. Remove `const instagramCount = ...` (line 19).
      3. Remove `instagram: instagramCount,` from the counts object (line 24).
      4. Remove `instagram: instagramQuery,` from the activeQuery map (line 28).
      NOTE: the counts object must still be typed as `Record<Platform, number>`
      — after Platform is narrowed to 'twitter' | 'content', this object only
      has those two keys, which is correct.

    frontend/src/pages/DigestPage.tsx:
      1. Remove `instagram?: number` from the QueueSnapshot interface
         (line 13).
      2. Remove the Instagram stats card (the middle card, lines 259-262 that
         render `snapshot.instagram`).
      3. Update the grid from `grid-cols-4` to `grid-cols-3` (line 254).
      (DigestPage shows platform stats in the stats row; removing Instagram
      reduces to Twitter + Content + Yesterday = 3 cards.)

    frontend/src/components/shared/PlatformBadge.tsx:
      Remove `instagram: { label: 'Instagram', icon: Camera },` from
      PLATFORM_CONFIG. Also remove `Camera` from the lucide-react import —
      unused after removal.

    frontend/src/components/shared/RelatedCardBadge.tsx:
      Remove `instagram: 'Instagram',` from PLATFORM_LABELS.

    frontend/src/components/content/VideoClipPreview.tsx:
      1. Remove `instagram_caption?: string` from VideoClipDraft interface.
      2. Remove all instagram_caption handling in the component body:
         delete `const instagramCaption = typeof d.instagram_caption === ...` line;
         in the empty-state check, change `if (!twitterCaption && !instagramCaption)`
         to `if (!twitterCaption)`;
         delete the entire `{instagramCaption && (<div>...</div>)}` block that
         renders the Instagram caption column;
         change the grid from `md:grid-cols-2` to a single column (remove the
         grid wrapper or switch to `grid-cols-1`).
      3. Remove `Instagram caption` string and `'Instagram caption copied'` toast.

    frontend/src/components/content/QuotePreview.tsx:
      1. Remove `instagram_post?: string` from QuoteDraft interface.
      2. Remove all instagram_post handling: the `instagramPost` variable,
         the empty-state condition, the Instagram column rendering,
         the `'Instagram post copied'` toast. Simplify grid to single column.

    frontend/src/components/content/RenderedImagesGallery.tsx:
      1. ROLE_ORDER array: keep only `'twitter_visual'`. Type narrowed by
         updated RenderedImage type.
      2. ROLE_LABELS: keep only `twitter_visual: 'Twitter / X'`.
      3. expectedCount logic (line 52): update to
         `const expectedCount = contentType === 'infographic' || contentType === 'quote' ? 1 : 0`
         (both formats now render just 1 twitter_visual; IG slides are no longer
         displayed even though image_render_agent may still emit them to R2).
      4. Update the skeleton grid from 4 columns (line 85 `grid-cols-2 md:grid-cols-4`)
         to a single column (`grid-cols-1` or drop the grid wrapper).
      5. Display grid (line 97) same: drop `md:grid-cols-4` — single image.

    frontend/src/components/settings/AgentRunsTab.tsx:
      Remove `{ value: 'instagram_agent', label: 'instagram_agent' },` from
      AGENT_OPTIONS (line 18).

    frontend/src/components/settings/WatchlistTab.tsx:
      1. Change `useState<'twitter' | 'instagram'>('twitter')` to
         `useState<'twitter'>('twitter')` (line 22) — there's only one platform
         now. Alternatively, since there's only one value, simplify by removing
         the platform toggle buttons (lines 105-121) and the state variable
         entirely, using `'twitter'` as a constant.
      2. Remove the Instagram toggle button (lines 114-120) and any
         `platform === 'instagram'` branches (follower_threshold input becomes
         unreachable — remove those conditionals; delete addFollowerThreshold
         / editFollowerThreshold state and their form inputs; Follower Threshold
         column stays in the table but always renders `—`; OR cleaner: remove
         the Follower Threshold column entirely since it's dead code).
         PREFER: remove Follower Threshold column + all follower_threshold
         state/inputs/conditionals. Simpler.
      3. Empty-state message: "No twitter watchlist entries yet." (only one
         platform) — or keep the `${platform}` interpolation with platform
         always `'twitter'`.

    frontend/src/components/settings/KeywordsTab.tsx:
      Remove `<option value="instagram">instagram</option>` from the add-form
      platform select (line 112). Leaves twitter + content options.

    frontend/src/mocks/handlers.ts:
      1. Remove all mockItems entries with `platform: 'instagram'` — entries
         with ids starting '44444444' and '55555555' (lines 64-98).
      2. `queue_snapshot` in /digests/latest and /digests/:date: remove
         `instagram: 2` / `instagram: 0` keys.
      3. In /watchlists handler: remove the `wl-2` instagram entry
         (lines 226-234).
      4. In /agent-runs handler: remove the `instagram_agent` entry (line 293).

    Test file updates (remove only the IG-specific assertions, leave
    non-IG assertions intact):

    frontend/src/components/layout/PlatformTabBar.test.tsx:
      1. defaultCounts at top: remove `instagram: 0,` (line 9).
      2. Test "renders three tabs": rename to "renders two tabs: Twitter, Content";
         remove `expect(screen.getByText('Instagram')).toBeInTheDocument()` (line 23).
      3. "shows badge counts" test: remove `instagram: 3,` from counts, remove
         `expect(screen.getByText('3')).toBeInTheDocument()`.
      4. "calls onTabChange" test: change the click target from 'Instagram' to
         'Content' and expect `'content'` (lines 58-59).

    frontend/src/components/approval/__tests__/ContentDetailModal.test.tsx:
      1. Test 5 (quote): remove `instagram_post: 'Gold never lies. #gold',`
         from the draft fixture (line 187). The Twitter post assertion still
         covers the QuotePreview render contract.
      2. Test 6 (video_clip): remove
         `instagram_caption: 'Gold market analysis. #gold #mining',`
         (line 216).

    frontend/src/pages/DigestPage.test.tsx:
      1. mockLatestDigest.queue_snapshot (line 31): remove `instagram: 2,`.
      2. Test "renders today digest with all sections": remove
         `expect(screen.getByText('Instagram')).toBeInTheDocument()` (line 107).
      3. "no priority alert" test or similar with `instagram: 0` in
         queue_snapshot (line 169): remove `instagram: 0,`.

    frontend/src/pages/SettingsPage.test.tsx:
      1. Delete entire test "watchlists tab platform toggle filters entries"
         (lines 36-50) — toggle no longer exists after WatchlistTab simplification.
      2. Delete entire test "watchlists tab shows follower threshold for instagram
         entries" (lines 65-80) — column removed.
      3. Delete entire test "watchlists tab add form shows follower threshold input
         for instagram" (lines 82-101) — input removed.
      Net: 14 − 3 = 11 tests in SettingsPage.test.tsx after edits.

    Commands to run after edits:
      cd frontend && npm run lint 2>&1 | tail -3        # expect: 0 errors
      cd frontend && npx tsc --noEmit 2>&1 | tail -3    # expect: no TS errors
      cd frontend && npm test -- --run 2>&1 | tail -5   # expect: passing
      cd frontend && npm run build 2>&1 | tail -5       # expect: succeeds

    Verification sweep before commit:
      grep -rn "instagram\|Instagram" frontend/src/api frontend/src/components/layout \
        frontend/src/components/shared frontend/src/hooks frontend/src/pages frontend/src/App.tsx
      # Expected matches: ZERO in the listed paths.
      # Surviving IG references in frontend/src/components/content/*.tsx and
      # frontend/src/mocks/handlers.ts: none after edits.
      # Surviving IG references in frontend/src/components/settings/* : none.

    Commit:
      git add -A
      git commit -m "feat(quick-lvy): purge Instagram from frontend + tests"
      Do NOT push.
  </action>
  <verify>
    <automated>
cd /Users/matthewnelson/seva-mining/frontend && npm run lint 2>&1 | tail -3 \
  && cd /Users/matthewnelson/seva-mining/frontend && npx tsc --noEmit 2>&1 | tail -3 \
  && cd /Users/matthewnelson/seva-mining/frontend && npm test -- --run 2>&1 | tail -5 \
  && cd /Users/matthewnelson/seva-mining/frontend && npm run build 2>&1 | tail -5 \
  && ! grep -rn "instagram\|Instagram" /Users/matthewnelson/seva-mining/frontend/src/api /Users/matthewnelson/seva-mining/frontend/src/components/layout /Users/matthewnelson/seva-mining/frontend/src/components/shared /Users/matthewnelson/seva-mining/frontend/src/hooks /Users/matthewnelson/seva-mining/frontend/src/App.tsx \
  && echo "TASK 2 VERIFY: PASS"
    </automated>
  </verify>
  <done>
    - Platform type narrowed to `'twitter' | 'content'`
    - /instagram route, sidebar link, and queue counter removed
    - Shared components (PlatformBadge, RelatedCardBadge) and content preview
      components (VideoClip, Quote, RenderedImagesGallery) have zero IG branches
    - Settings tabs (Watchlist, Keywords, AgentRuns) have zero IG options
    - MSW handlers and test fixtures stripped of IG mock data
    - IG-specific test assertions removed from 4 test files
    - `npm run lint` 0 errors, `npx tsc --noEmit` clean, `npm test -- --run` passing,
      `npm run build` succeeds
    - Atomic commit `feat(quick-lvy): purge Instagram from frontend + tests` landed (not pushed)
  </done>
</task>

<task type="auto">
  <name>Task 3: Group content queue by agent run (match Twitter pattern)</name>
  <files>
    frontend/src/pages/PlatformQueuePage.tsx
  </files>
  <action>
    This task depends on Task 2 (Platform type narrowed, IG branches gone) so
    the executor can assume `platform: 'twitter' | 'content'` and no IG cases.

    Edits to frontend/src/pages/PlatformQueuePage.tsx:

    1. PLATFORM_LABELS (line 14): already only has twitter + content after Task 2
       cleanup — verify with grep before editing; no change needed if Task 2 left
       it as `{ twitter: 'Twitter', content: 'Content' }`. If still has
       `instagram: 'Instagram'`, remove it.

    2. AGENT_NAMES map (line 21): change from
         const AGENT_NAMES: Partial<Record<Platform, string>> = {
           twitter: 'twitter_agent',
         }
       to
         const AGENT_NAMES: Partial<Record<Platform, string>> = {
           twitter: 'twitter_agent',
           content: 'content_agent',
         }
       The key `'content_agent'` matches the `agent_name` written by
       ContentAgent.run() (confirmed at scheduler/agents/content_agent.py line 1645).

    3. showRunGroups (line 112): change from
         const showRunGroups = platform === 'twitter' && runs.length > 0
       to
         const showRunGroups = (platform === 'twitter' || platform === 'content') && runs.length > 0

    4. Grouped-branch renderer (lines 134-144): update the `group.items.map`
       inside the showRunGroups branch to render ContentSummaryCard for
       content items, matching the non-grouped branch's pattern:
         // before
         {group.items.map((item) => (
           <ApprovalCard key={item.id} item={item} platform={platform} />
         ))}
         // after
         {group.items.map((item) =>
           platform === 'content' ? (
             <ContentSummaryCard key={item.id} item={item} />
           ) : (
             <ApprovalCard key={item.id} item={item} platform={platform} />
           )
         )}

    5. No changes to the groupByRun() function — its logic works for any
       platform as long as items have `created_at` and runs have `started_at`.
       DraftItem.created_at is populated for all platforms (seen in
       backend/app/models/draft_item.py line 47), so content items group
       correctly against content_agent runs.

    6. Fallback behavior — if `getAgentRuns('content_agent', 7)` returns an
       empty array (first-ever run, or test environment with empty mock),
       `showRunGroups` becomes false (runs.length === 0) and the non-grouped
       branch renders the flat list. No user-facing regression for fresh
       installs.

    7. Do NOT add a new test file. The PlatformQueuePage has no existing test
       file, and the user constraint says "otherwise skip new test (scope creep)".
       The MSW /agent-runs handler in frontend/src/mocks/handlers.ts (edited
       in Task 2) already returns a content_agent run, so runtime behavior is
       exercised transitively by any page-level render test if/when added.

    Commands to run after edits:
      cd frontend && npm run lint 2>&1 | tail -3         # expect: 0 errors
      cd frontend && npx tsc --noEmit 2>&1 | tail -3     # expect: clean
      cd frontend && npm test -- --run 2>&1 | tail -5    # expect: passing
      cd frontend && npm run build 2>&1 | tail -5        # expect: succeeds

    Manual smoke note for the user (informational — do NOT add a checkpoint):
      After `npm run dev`, navigate to /content — content queue should display
      grouped sections with "Pulled from agent run at HH:mm · MMM d" headers
      (matching Twitter's appearance).

    Commit:
      git add frontend/src/pages/PlatformQueuePage.tsx
      git commit -m "feat(quick-lvy): group content queue by agent run (match Twitter pattern)"
      Do NOT push.
  </action>
  <verify>
    <automated>
grep -q "platform === 'twitter' || platform === 'content'" /Users/matthewnelson/seva-mining/frontend/src/pages/PlatformQueuePage.tsx \
  && grep -q "content: 'content_agent'" /Users/matthewnelson/seva-mining/frontend/src/pages/PlatformQueuePage.tsx \
  && grep -q "platform === 'content' ? (" /Users/matthewnelson/seva-mining/frontend/src/pages/PlatformQueuePage.tsx \
  && cd /Users/matthewnelson/seva-mining/frontend && npm run lint 2>&1 | tail -3 \
  && cd /Users/matthewnelson/seva-mining/frontend && npx tsc --noEmit 2>&1 | tail -3 \
  && cd /Users/matthewnelson/seva-mining/frontend && npm test -- --run 2>&1 | tail -5 \
  && echo "TASK 3 VERIFY: PASS"
    </automated>
  </verify>
  <done>
    - `showRunGroups` includes content platform when runs exist
    - AGENT_NAMES maps content → 'content_agent' (matches scheduler's agent_name)
    - Grouped branch renders ContentSummaryCard for content items, ApprovalCard
      for Twitter items
    - Lint/typecheck/tests/build clean
    - Atomic commit `feat(quick-lvy): group content queue by agent run (match Twitter pattern)` landed (not pushed)
  </done>
</task>

<task type="auto">
  <name>Task 4: Add deprecated notes to ROADMAP + REQUIREMENTS + STATE + CLAUDE.md</name>
  <files>
    .planning/ROADMAP.md,
    .planning/REQUIREMENTS.md,
    .planning/STATE.md,
    CLAUDE.md
  </files>
  <action>
    The goal is to preserve history (INST-* requirement IDs, Phase 6 plans,
    original descriptions) while making the deprecation unmistakable at first
    read. No deletions of historical records.

    .planning/ROADMAP.md:
      1. Phase list item (line 20): change
           - [ ] **Phase 6: Instagram Agent** - Apify scraper integration, ...
         to
           - [ ] **Phase 6: Instagram Agent (deprecated — removed in 260419-lvy)** - Apify scraper integration, ...
      2. At the top of the "### Phase 6: Instagram Agent" section (before the
         Goal line, after the `### Phase 6: Instagram Agent` heading), insert:

           > **⚠️ DEPRECATED (2026-04-19) — Instagram agent removed in quick task 260419-lvy.**
           > Agent never ran in production. Code purged from codebase; DB schema retained
           > (platform column is String(20), not an enum, so historical-IG values would
           > remain queryable if they existed). APIFY_API_TOKEN env var also removed.
           > This section is preserved as a historical record of the planned work.

      3. Progress table at the bottom: leave the Phase 6 row as-is (shows
         "0/5 | Planned") but add a status note: change "Planned" cell to
         "Deprecated (260419-lvy)".

    .planning/REQUIREMENTS.md:
      1. Section "### Instagram Agent" heading — append a one-line deprecation
         marker directly below the heading:

           ### Instagram Agent

           > *(deprecated 2026-04-19 — 260419-lvy: agent code purged, requirements retained for history)*

      2. Each INST-01 through INST-12 bullet — append ` (deprecated 2026-04-19 — 260419-lvy)`
         at the end of the bullet, AFTER the existing text. Do NOT rewrite
         the bullet text itself. Example transformation:

           - [x] **INST-01**: Agent monitors Instagram via Apify scraper ... every 4 hours
           → - [x] **INST-01**: Agent monitors Instagram via Apify scraper ... every 4 hours (deprecated 2026-04-19 — 260419-lvy)

      3. Traceability table at the bottom: for each INST-01 through INST-12
         row, change the Status column from "Complete" to
         "Deprecated (260419-lvy)". Do NOT delete the rows.

      4. Coverage note at the bottom: add one bullet beneath the existing
         coverage list: `- Deprecated (not counted against open coverage): 12 (INST-01 through INST-12)`

    .planning/STATE.md:
      Find the `**Current focus:**` line (line 22) and adjacent project-summary
      area. No Instagram reference currently on line 9 (that line is a YAML
      progress field). Instead, scan the full file for any "Instagram"
      occurrences using grep. The only expected match is in the Decisions
      section (historical phase notes like `[Phase 06-instagram-agent]`) — those
      are historical log entries and must be preserved verbatim.

      Add ONE new line to the "Decisions" section (under Recent decisions, at
      the bottom of that block):

        - [260419-lvy]: Instagram Agent fully purged — code, tests, seed, APIFY env, frontend platform all removed. DB schema retained (platform is String(20), not enum). Phase 6 and INST-* preserved in docs as deprecated history. Content queue now groups by agent run matching Twitter pattern.

      No other edits to STATE.md. STATE progress counters stay as-is (they
      reflect the snapshot before this quick task).

    CLAUDE.md:
      1. `## Project` section (around line 6): change the opening paragraph from
           "A four-agent AI system that monitors the gold sector on X (Twitter) and Instagram 24/7 ..."
         to
           "A three-agent AI system that monitors the gold sector on X (Twitter) 24/7 ..."

      2. Same paragraph: update "four-agent" to "three-agent" throughout if it
         appears elsewhere in the opening.

      3. `### Constraints` block (around lines 10-22):
         - Remove the `- **Instagram**: Apify scraper (~$50/mo) ...` line
           (line 14).
         - Update the `- **Budget**` line: `~$255-275/month total operating cost`
           → `~$205-225/month total operating cost` (subtract Apify $50/mo).
         - Leave WhatsApp, SerpAPI, AI, etc. lines as-is.

      4. `## Technology Stack` table: find the `apify-client` row (around
         line 45) and remove the entire row.

      5. `### Supporting Libraries` and other tables: no apify references —
         verify with grep.

      6. `## Alternatives Considered` table (line 78): remove the row mentioning
         `apify-client` and `Playwright/Selenium DIY scraping` — this whole
         comparison is moot now. OR retain as "Out-of-scope: Instagram
         scraping considerations (removed 2026-04-19)." — PREFER: remove
         the row entirely since we no longer do IG scraping.

      7. `## What NOT to Use` table: remove the `instagram-private-api` row
         (around line 93) — we no longer do any IG scraping so this
         warning is obsolete.

      8. `## Stack Patterns by Variant` section: paragraph mentions the 4
         agents `(Senior, Content, Twitter, Instagram)` — change to
         `(Senior, Content, Twitter)`.

      9. At the very bottom of the `## Project` section (before the
         `<!-- GSD:project-end -->` tag), add a historical note line:

           *Instagram monitoring removed 2026-04-19 (quick task 260419-lvy).*

      10. Sources list at the bottom of the Technology Stack section: remove
          the apify-client PyPI source link line.

    Verification sweep before commit:
      grep -in "instagram\|apify" .planning/ROADMAP.md .planning/REQUIREMENTS.md CLAUDE.md
      # Expected matches: only inside the deprecated banners, historical bullets,
      # and section headings documenting the deprecation. No apify-client /
      # APIFY_API_TOKEN references outside historical notes.

      grep -c "deprecated 2026-04-19 — 260419-lvy" .planning/REQUIREMENTS.md
      # Expected: at least 13 (section marker + 12 INST bullets)

    Commands to run after edits:
      (no code tests — these are doc changes)

    Commit:
      git add .planning/ROADMAP.md .planning/REQUIREMENTS.md .planning/STATE.md CLAUDE.md
      git commit -m "docs(quick-lvy): deprecated notes in ROADMAP + REQUIREMENTS + STATE + CLAUDE.md for Instagram agent"
      Do NOT push.
  </action>
  <verify>
    <automated>
grep -q "DEPRECATED (2026-04-19) — Instagram agent removed in quick task 260419-lvy" /Users/matthewnelson/seva-mining/.planning/ROADMAP.md \
  && grep -q "(deprecated 2026-04-19 — 260419-lvy)" /Users/matthewnelson/seva-mining/.planning/REQUIREMENTS.md \
  && test $(grep -c "deprecated 2026-04-19 — 260419-lvy" /Users/matthewnelson/seva-mining/.planning/REQUIREMENTS.md) -ge 13 \
  && grep -q "260419-lvy" /Users/matthewnelson/seva-mining/.planning/STATE.md \
  && grep -q "three-agent AI system" /Users/matthewnelson/seva-mining/CLAUDE.md \
  && ! grep -qi "apify-client" /Users/matthewnelson/seva-mining/CLAUDE.md \
  && grep -q "Instagram monitoring removed 2026-04-19" /Users/matthewnelson/seva-mining/CLAUDE.md \
  && echo "TASK 4 VERIFY: PASS"
    </automated>
  </verify>
  <done>
    - ROADMAP.md Phase 6 has DEPRECATED banner; Phase 6 row in progress table
      shows "Deprecated (260419-lvy)"
    - REQUIREMENTS.md has deprecation marker on Instagram Agent section AND
      on each of the 12 INST-* bullets; Traceability table INST rows show
      "Deprecated (260419-lvy)"
    - STATE.md Decisions list has a 2026-04-19 entry for the 260419-lvy purge
    - CLAUDE.md describes the product as three-agent (was four-agent), has no
      Instagram/apify references except the historical removal note, and the
      Budget line is $205-225/month
    - Atomic commit `docs(quick-lvy): deprecated notes in ROADMAP + REQUIREMENTS + STATE + CLAUDE.md for Instagram agent` landed (not pushed)
  </done>
</task>

</tasks>

<verification>
Phase-wide verification after all four tasks commit:

```bash
# 1. Git log shows exactly 4 new commits with the expected subjects
cd /Users/matthewnelson/seva-mining && git log --oneline -4 | grep -E "quick-lvy"
# Expected: 4 lines, subjects:
#   docs(quick-lvy): deprecated notes in ROADMAP + REQUIREMENTS + STATE + CLAUDE.md for Instagram agent
#   feat(quick-lvy): group content queue by agent run (match Twitter pattern)
#   feat(quick-lvy): purge Instagram from frontend + tests
#   feat(quick-lvy): purge Instagram from backend + scheduler + env vars

# 2. No surviving Instagram destination-platform references
grep -rn "InstagramAgent\|instagram_agent\|apify_api_token\|APIFY_API_TOKEN" \
  /Users/matthewnelson/seva-mining/scheduler/worker.py \
  /Users/matthewnelson/seva-mining/scheduler/config.py \
  /Users/matthewnelson/seva-mining/backend/app/config.py \
  /Users/matthewnelson/seva-mining/.env.example \
  /Users/matthewnelson/seva-mining/frontend/src/
# Expected: 0 matches

# 3. Deleted files absent
test ! -e /Users/matthewnelson/seva-mining/scheduler/agents/instagram_agent.py
test ! -e /Users/matthewnelson/seva-mining/scheduler/tests/test_instagram_agent.py
test ! -e /Users/matthewnelson/seva-mining/scheduler/seed_instagram_data.py

# 4. All three test suites green
cd /Users/matthewnelson/seva-mining/backend && uv run pytest -q              # 71 passed
cd /Users/matthewnelson/seva-mining/scheduler && uv run pytest -q            # ~98 passed
cd /Users/matthewnelson/seva-mining/frontend && npm test -- --run            # ~71 passed

# 5. Lint + build clean
cd /Users/matthewnelson/seva-mining/backend && uv run ruff check .
cd /Users/matthewnelson/seva-mining/scheduler && uv run ruff check .
cd /Users/matthewnelson/seva-mining/frontend && npm run lint
cd /Users/matthewnelson/seva-mining/frontend && npm run build

# 6. Content run-grouping active
grep "platform === 'twitter' || platform === 'content'" \
  /Users/matthewnelson/seva-mining/frontend/src/pages/PlatformQueuePage.tsx

# 7. Deprecation notes present
grep "DEPRECATED (2026-04-19)" /Users/matthewnelson/seva-mining/.planning/ROADMAP.md
grep "three-agent AI system" /Users/matthewnelson/seva-mining/CLAUDE.md
```

Manual smoke (informational, not blocking):
  After `npm run dev` in frontend and `python -m worker` in scheduler, visiting
  the dashboard should show only Twitter + Content tabs in the sidebar; the
  /content page should render grouped by agent run headers.
</verification>

<success_criteria>
1. Four atomic commits on the current branch with the exact subjects specified, in the order (Task 1, Task 2, Task 3, Task 4). No merge commits. No push to origin.
2. Backend `uv run pytest -q`: 71 passed, 0 failed, 0 errors.
3. Scheduler `uv run pytest -q`: ~98 passed (was 115 − 17 IG tests), 0 failed, 0 errors. Small deviation (±2) acceptable if test_worker.py assertions split/merge.
4. Frontend `npm test -- --run`: ~70-72 passed (was 74 − ~3-4 IG-only assertions/tests), 0 failed.
5. `ruff check` on backend and scheduler: 0 errors.
6. Frontend `npm run lint`: 0 errors. `npx tsc --noEmit`: clean. `npm run build`: exit 0.
7. `grep -rn "InstagramAgent\|instagram_agent\|apify_api_token\|APIFY_API_TOKEN"` across non-doc source returns 0 matches.
8. `.env.example` contains exactly 19 secret-bearing env var lines (was 20).
9. All 4 deprecated banners/markers visible in ROADMAP, REQUIREMENTS, STATE, and CLAUDE.md with dates and quick-task ID.
10. Visiting `/content` in the dashboard renders agent-run group headers identical in style to `/twitter`.
</success_criteria>

<output>
After completion, create `.planning/quick/260419-lvy-full-purge-instagram-agent-content-queue/260419-lvy-SUMMARY.md` with:
- Date (2026-04-19), 4 commit SHAs with subjects, files changed count
- Test-count deltas (backend, scheduler, frontend before/after)
- Explicit note: "Did NOT write DB migration. Historical rows with platform='instagram' remain in DB untouched (platform is String(20), not an enum). Content Agent still emits instagram_post/caption/carousel/slide JSON internally — only the Instagram destination-platform agent, env, and UI surfaces were purged."
- Explicit note: "Did NOT push to origin. User to push manually when ready."
</output>
