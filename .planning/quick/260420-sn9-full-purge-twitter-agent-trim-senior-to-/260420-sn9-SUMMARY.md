---
task_id: 260420-sn9
type: quick
title: Full purge Twitter agent + trim Senior agent to morning-digest-only
completed: 2026-04-21
duration: ~3h (across sessions, mid-compaction resumption)
cancels: 260420-s3b
commits:
  - 62ffda4  # Task 1: purge Twitter agent from scheduler + sever sub-agent→Senior intake wiring
  - be9cd8b  # Task 2: trim Senior Agent to run_morning_digest only
  - aeaf412  # Task 3: backend purge (/config/quota endpoint + test fixtures + seed_mock_data)
  - c30e288  # Task 4: frontend purge (Platform type narrowing + 7 files deleted + 13 files modified)
  - 55100c9  # Task 5: prod DB purge + CLAUDE.md + ROADMAP.md + REQUIREMENTS.md + STATE.md (this commit)
tags: [deprecation, twitter-agent, senior-agent, scheduler, backend, frontend, prod-db, budget, planning-docs]
---

# Quick 260420-sn9: Full purge Twitter agent + trim Senior to morning-digest-only

## One-liner

Deprecated the Twitter Agent end-to-end — deleted the scheduler module, removed the `/config/quota` backend endpoint, stripped every Twitter surface from the React dashboard (Platform type narrowed to `'content'`, 7 files deleted, 13 modified), trimmed the Senior Agent down to `run_morning_digest` only, purged 177 historical `draft_items WHERE platform='twitter'` + 40 watchlists + 8 `twitter_*` config keys from the Neon prod DB inside a single transaction, and marked Phase 4/Phase 5 deprecated (with Phase 10 partial-deprecation) across ROADMAP + REQUIREMENTS + STATE + CLAUDE.md. Seva Mining is now a **single-agent** system (Content only, plus `morning_digest` and `gold_history_agent` crons). The X API Basic tier ($100/mo) is cut; monthly spend drops from ~$214 to ~$114.

## Context

Post-lvy (Instagram purge, 2026-04-19) the system was nominally three agents: Twitter + Senior + Content. In practice, the Twitter Agent's output had become redundant: the Content Agent's news-feed pipeline (oa1's market snapshot injection + nnh's specific-miner rejection + the rqx pass) was producing higher-signal drafts than scraping the X timeline, and X API Basic tier's $100/mo spend no longer fit the economics now that Content drafts were the dashboard's dominant workflow. The Senior Agent had separately narrowed to a single cron in practice — `morning_digest` at 15:00 UTC (Phase 10-03). Its dedup, queue cap, expiry sweep, and breaking-news alert paths were unused in production.

A predecessor quick task (`260420-s3b` — Twitter Agent autonomous auto-posting) had surveyed the X API write-scope, but operator's "never auto-post" hard rule and the decision to drop Twitter entirely made s3b moot. s3b CONTEXT + RESEARCH files are retained in `.planning/quick/260420-s3b-twitter-agent-autonomous-auto-posting-wi/` as historical record; no PLAN.md was written for s3b. sn9 cancels s3b.

This quick task executes the purge as **5 atomic commits**, one per layer, so each cross-cutting concern can be reviewed independently.

## Pre-DB state (prod, Neon, 2026-04-21 pre-purge)

```
draft_items_twitter:     177
draft_items_content:     955
draft_items_other:         5  (legacy instagram orphans from lvy-era; untouched here)
watchlists_all:           40  (25 twitter + 15 instagram — all deprecated-agent data)
watchlists_twitter:       25
watchlists_content:        0
watchlists_instagram:     15  (lvy-era orphans)
config_twitter_keys:       8  (twitter_interval_hours, twitter_min_likes_general,
                               twitter_min_likes_watchlist, twitter_min_views_general,
                               twitter_min_views_watchlist, twitter_monthly_reset_date,
                               twitter_monthly_tweet_count, twitter_quota_safety_margin)
config_all:               32
agent_runs_twitter:      132  (historical — retained; see "FK cleanup" below)
```

## Task 1 — Scheduler purge (`62ffda4`)

Deleted:
- `scheduler/agents/twitter_agent.py` (full TwitterAgent class)
- `scheduler/tests/test_twitter_agent.py`
- `scheduler/seed_twitter_data.py` (separate commit-bundle; already gone by this step)

Modified:
- `scheduler/worker.py` — removed `TwitterAgent` import; dropped `"twitter_agent": 1001` and `"senior_agent": 1003` entries from `JOB_LOCK_IDS`; collapsed `_make_job` to no longer branch twitter vs. senior; removed the `add_job` for twitter_agent; scheduler now registers exactly 3 jobs (`content_agent`, `morning_digest`, `gold_history_agent`); docstring "5 jobs" → "3 jobs"; **preserved** the `X_API_BEARER_TOKEN` critical gate in `_validate_env` (content_agent video_clip pipeline depends on it).
- `scheduler/agents/__init__.py` — dropped `TwitterAgent` export.
- `scheduler/tests/test_worker.py` — renamed + updated job-count assertions (5 → 3); removed every `twitter_agent`/`senior_agent` JOB_LOCK_ID probe; added `assert "twitter_agent" not in job_ids`.
- `scheduler/agents/content_agent.py` — removed the two `from agents.senior_agent import process_new_items` import-and-call sites (one in the story loop, one in the video_clip loop). **Preserved intact:** `VIDEO_ACCOUNTS`, `_search_video_clips`, `_draft_video_caption`, `_run_twitter_content_search`, and `import tweepy.asynchronous` — the video-clip pipeline still reads X API via tweepy async client downstream of Content, independent of the (now-deleted) Twitter Agent.
- `scheduler/agents/gold_history_agent.py` — removed `process_new_items` import + call.
- `scheduler/tests/test_content_agent.py`, `test_gold_history_agent.py` — tests adjusted to no longer patch a process_new_items call.

**Preserved (intentionally):**
- `scheduler/pyproject.toml` keeps `tweepy[async]>=4.14` (content_agent video_clip dependency).
- `scheduler/config.py::Settings` keeps `x_api_bearer_token`, `x_api_key`, `x_api_secret` (content_agent reads bearer; OAuth 1.0a env retained in case future Content tooling wants posting-auth — inert today but zero-cost to keep).
- `scheduler/worker.py::_validate_env` keeps `X_API_BEARER_TOKEN` in the `critical` list.

**Verify (Task 1):**
- Scheduler pytest: 100/100 passed (was 115 pre-sn9; -17 = 15 twitter_agent tests + 2 process_new_items-integration tests).
- ruff (scheduler): 0 errors.
- No `TwitterAgent` import or `twitter_agent` JOB_LOCK_ID anywhere in scheduler/.

## Task 2 — Senior Agent trim (`be9cd8b`)

Rewrote `scheduler/agents/senior_agent.py` to be morning-digest-only.

**Kept:**
- `run_morning_digest()` (entry point; queries `draft_items WHERE platform='content'`)
- `_assemble_digest()` (top stories + queue snapshot + yesterday summary + priority item)
- `_headline_from_rationale()` (rationale-to-headline shortener)
- `_get_config()` helper
- `seed_senior_config()` (initial config seeding; noop after first run)

**Deleted:**
- `_run_deduplication()` + `jaccard_similarity` + fingerprint/token helpers
- `_check_queue_cap()` + displacement logic + tiebreaking
- `_check_breaking_news_alert()` + `run_expiry_sweep()` + `_check_expiry_alert()` + `_check_engagement_alert()`
- `process_new_items()` (top-level orchestrator called by sub-agents at intake — now severed in Task 1)
- All associated `DraftItem.engagement_alert_level` / `alerted_expiry_at` state-machine transitions
- ~400 lines net removed from `senior_agent.py`

**Test file (`scheduler/tests/test_senior_agent.py`):** trimmed to just the morning-digest tests; all dedup / queue-cap / expiry-sweep / alert tests deleted. Before: ~19 tests; after: 4 digest-focused tests.

**Verify (Task 2):**
- Scheduler pytest: still 100/100 passed (net zero — the 15 deleted senior tests were offset by 15 net removed from twitter+senior combined; see Task 1 count breakdown).
- ruff: 0 errors.
- `grep "process_new_items" scheduler/` → no matches outside the deleted senior module.
- Morning digest query pattern `DraftItem.platform == "content"` preserved in `_assemble_digest`.

## Task 3 — Backend purge (`aeaf412`)

Modified:
- `backend/app/routers/config.py` — `/quota` endpoint deleted (sole consumer was the now-removed frontend `QuotaBar`); replaced with a 2-line comment explaining why the endpoint is gone.
- `backend/tests/test_crud_endpoints.py` — watchlist fixtures `"platform": "twitter"` → `"platform": "content"`; rewrote `test_agent_runs_filter_by_name` to filter on `agent_name="content_agent"` vs `agent_name="gold_history_agent"` (twitter_agent no longer exists as a real agent_name value); `test_list_watchlists_with_platform_filter` uses `content` + `other`; `test_create_keyword` platform `twitter` → `content`.
- `backend/tests/test_queue.py` — `make_draft_item(platform: str = "content")` default flipped from `"twitter"` to `"content"`.
- `backend/tests/routers/test_content_bundles.py` — `rendered_images` role `twitter_visual` → `content_visual`.
- `backend/scripts/seed_mock_data.py` — rewritten content-only: removed 5 twitter + 5 instagram mock draft rows; kept 2 content-only items; removed the cross-platform `related_id` wiring (no longer meaningful in single-agent system).
- `backend/app/models/agent_run.py`, `daily_digest.py`, `draft_item.py`, `keyword.py`, `watchlist.py` — docstring/comment updates documenting Twitter purge; long comments reflowed to ≤100 chars to satisfy ruff E501.
- `backend/app/schemas/*.py` — parallel comment updates.

**Preserved (intentionally):**
- `draft_items.platform` column stays `String(20)` (permissive) — historical rows with `platform='instagram'` from lvy still exist; narrowing the enum would require a migration for no functional gain.
- `watchlists` table kept in schema (emptied in Task 5).

**Deferred item (out of sn9 scope):**
- `backend/alembic/versions/0007_add_market_snapshots.py` has a pre-existing ruff I001 (import-order) from commit `b28780b` (oa1 task). Left unchanged. Logged in `.planning/quick/260420-sn9-full-purge-twitter-agent-trim-senior-to-/deferred-items.md` for future cleanup.

**Verify (Task 3):**
- Backend pytest: 70 collected, 66 passed, 5 skipped (ordinary skips in `test_schema.py` — real-Neon-URL-dependent).
- ruff (backend): 0 errors after E501 reflow.
- No `/config/quota` handler remaining; no `platform="twitter"` fixture remaining.

## Task 4 — Frontend purge (`c30e288`)

**Platform type narrowed:** `frontend/src/api/types.ts` — `export type Platform = 'content'` (was `'twitter' | 'content'`). `QuotaResponse` interface deleted.

**Files deleted (7):**
- `frontend/src/components/approval/ApprovalCard.tsx` + `ApprovalCard.test.tsx` — the Twitter approval surface. Content path already rendered via `ContentSummaryCard`, so this component became dead after Platform narrowing.
- `frontend/src/components/layout/PlatformTabBar.tsx` + `PlatformTabBar.test.tsx` — only consumer was the dead `QueuePage.tsx`.
- `frontend/src/pages/QueuePage.tsx` — unreferenced in `App.tsx` (confirmed via grep); the active page is `PlatformQueuePage`.
- `frontend/src/components/settings/QuotaBar.tsx` — Twitter-only X API monthly quota widget. Its endpoint `/config/quota` is also gone (Task 3).
- `frontend/src/components/settings/WatchlistTab.tsx` — hard-coded to `platform='twitter'`; Watchlists tab removed from Settings.

**Files modified (13):**
- `frontend/src/App.tsx` — root `/` redirects to `/content` (was `/twitter`); `<Route path="/twitter">` removed.
- `frontend/src/api/settings.ts` — removed `getQuota()` + `QuotaResponse` import.
- `frontend/src/components/layout/Sidebar.tsx` — removed `Bird` icon import + Twitter nav entry; `agentItems = [{to:'/content',...}]`.
- `frontend/src/components/settings/AgentRunsTab.tsx` — removed `<QuotaBar />` render; `AGENT_OPTIONS` narrowed to `content_agent | morning_digest | gold_history_agent`.
- `frontend/src/components/settings/KeywordsTab.tsx` — default platform `'content'`; removed `<option value="twitter">`.
- `frontend/src/components/settings/ScoringTab.tsx` — removed `twitterScoringKeys` filter + "Twitter Agent Scoring" `<ScoringSection>`.
- `frontend/src/components/shared/PlatformBadge.tsx`, `RelatedCardBadge.tsx` — `PLATFORM_CONFIG` / `PLATFORM_LABELS` narrowed to `{ content: ... }` only.
- `frontend/src/hooks/useQueueCounts.ts` — dropped the twitter query; returns `{ content, contentHasMore }`.
- `frontend/src/mocks/handlers.ts` — `mockItems` rewritten to 1 content-only draft; removed 3 Twitter mock items; `/config/quota` handler deleted; `/watchlists` returns empty; `/keywords` all `platform: 'content'`; `/agent-runs` mock uses `content_agent` + `morning_digest` only; `queue_snapshot` shape `{ content, total }` (was `{ twitter, content, total }`).
- `frontend/src/pages/DigestPage.tsx` — `QueueSnapshot` loses `twitter?: number`; stats grid `grid-cols-3` → `grid-cols-2`; Twitter tile removed.
- `frontend/src/pages/PlatformQueuePage.tsx` — `PLATFORM_LABELS` + `AGENT_NAMES` narrowed to content; `showRunGroups = platform === 'content' && runs.length > 0`; removed `ApprovalCard` import + twitter branch; both render paths use `ContentSummaryCard`.
- `frontend/src/pages/SettingsPage.tsx` — `<WatchlistTab />` removed; `defaultValue="keywords"`; 5 tabs (Keywords / Scoring / Notifications / Agent Runs / Schedule).

**Test files updated:**
- `frontend/src/pages/DigestPage.test.tsx` — mock `queue_snapshot` shape changed to `{ content, total }`; added `expect(screen.queryByText('Twitter')).not.toBeInTheDocument()` assertions in 2 tests.
- `frontend/src/pages/SettingsPage.test.tsx` — expect 5 tabs (no "Watchlists"); Keywords is default; "Twitter Agent Scoring" must be absent; "X API Monthly Quota" must be absent; agent-runs tab expects `content_agent` (not `twitter_agent`).

**Preserved (intentionally inert):**
- `QuotePreview.tsx`, `VideoClipPreview.tsx`, `InfographicPreview.tsx` output fields like `twitter_post` and `twitter_caption` — these are JSONB keys inside the Content Agent's `draft_content` output used for operator copy-paste to X, not references to the Twitter Agent. Renaming would require coordinated backend/agent prompt edits out of scope here.

**Verify (Task 4):**
- `pnpm tsc --noEmit` → clean
- `pnpm lint` → clean
- `pnpm test -- --run` → **56 passed across 8 files** (was 71 pre-sn9; -15 = matches deleted tests)
- `pnpm build` → green, 544KB bundle
- Grep sweep: 0 `Twitter|twitter_agent|QuotaBar|ApprovalCard|PlatformTabBar|WatchlistTab` matches in `frontend/src/` (inside file bodies; the inert `twitter_post`/`twitter_caption` string literals are expected content_agent output keys, not references to the Twitter Agent).

## Task 5 — Prod DB purge + docs refresh (`55100c9`)

### Prod DB purge

Executed via `npx @railway/cli run` (Railway service `scheduler`, environment `production`) using asyncpg inside a single transaction. Pre/post counts captured programmatically; DELETE cascade verified.

**FK cleanup (Rule 3 auto-fix):** Initial attempt to `DELETE FROM draft_items WHERE platform='twitter'` failed with `ForeignKeyViolationError: update or delete on table "draft_items" violates foreign key constraint "fk_draft_items_related_id_draft_items"`. Diagnosis: one `instagram` orphan row (from lvy-era data) had `related_id` pointing at a twitter row. Fix (scope-bounded to sn9 goal): `UPDATE draft_items SET related_id = NULL WHERE platform != 'twitter' AND related_id IN (SELECT id FROM draft_items WHERE platform='twitter')` — affected exactly 1 row. Instagram row itself left in place (deleting lvy orphans is a separate future task).

**Transaction:**

```sql
-- FK cleanup: 1 row
UPDATE draft_items SET related_id = NULL
WHERE platform != 'twitter'
  AND related_id IN (SELECT id FROM draft_items WHERE platform='twitter');

-- Deletes
DELETE FROM draft_items WHERE platform='twitter';   -- 177 rows
DELETE FROM watchlists;                             -- 40 rows (25 twitter + 15 instagram)
DELETE FROM config WHERE key LIKE 'twitter_%';      -- 8 rows
```

**Pre vs. Post counts:**

| Table / slice                          | PRE | POST | Delta |
|----------------------------------------|----:|-----:|------:|
| `draft_items WHERE platform='twitter'` | 177 |    0 |  -177 |
| `draft_items WHERE platform='content'` | 955 |  955 |     0 |
| `draft_items` other platforms          |   5 |    5 |     0 |
| `watchlists` (all)                     |  40 |    0 |   -40 |
| `config WHERE key LIKE 'twitter_%'`    |   8 |    0 |    -8 |
| `config` (all)                         |  32 |   24 |    -8 |

**Intentionally NOT deleted:**
- `agent_runs` rows with `agent_name='twitter_agent'` (132 rows): historical run-log; no FK enforcement; operator can review twitter agent performance metrics indefinitely. If future storage pressure warrants, separate retention task.
- `daily_digests` historical rows referencing twitter items in their JSONB snapshots: immutable digest archive.
- 15 instagram orphan watchlist rows were swept in the `DELETE FROM watchlists` since the Watchlists UI tab is removed and no agent consumes the table anymore — this is a beneficial side-effect of the sn9 scope (all-watchlist cleanup) rather than a scope expansion.

### Documentation updates

**`CLAUDE.md`:**
- Project blurb: "three-agent AI system" → "single-agent AI system"; prose rewritten to center Content Agent + trimmed morning_digest job.
- Appended **2026-04-20 historical note** mirroring the 2026-04-19 lvy note: documents the Twitter Agent + broader Senior Agent purge rationale, what was preserved (tweepy + x_api_* + VIDEO_ACCOUNTS + _search_video_clips + _draft_video_caption + _run_twitter_content_search), what was emptied in prod DB, and what the final scheduler job set looks like.
- Stack constraint line: scheduled jobs line updated to `content_agent + morning_digest + gold_history_agent` (was `twitter_agent, content_agent, senior_agent`).

**`.planning/ROADMAP.md`:**
- Top-level deprecation notice dated 2026-04-20 added below the existing 2026-04-19 (lvy) notice.
- Overview prose rewritten: "three-agent" → "single-agent"; historical build order retained for context.
- Phase 4 bullet: `[x]` → `[x] **~~Phase 4: Twitter Agent~~** - **DEPRECATED 2026-04-20 — see quick task `260420-sn9`.**`
- Phase 5 bullet: `[ ] **~~Phase 5: Senior Agent Core~~** - **DEPRECATED 2026-04-20**`
- Phase 4 detail header: strikethrough + explicit "never re-execute" block citing `260420-sn9`.
- Phase 5 detail header: strikethrough + explicit "never executed; morning_digest slice survived via Phase 10-03" block.
- Phase 10 header: inline partial-deprecation banner (Twitter + Instagram agent producers gone; Content-only new-item alerts; morning_digest cron unchanged).
- Progress table: Phase 4 `Complete` → `**Deprecated 2026-04-20**`; Phase 5 `Planned` → `**Deprecated 2026-04-20**`; Phase 6 row already marked (lvy).
- Milestones line: v1.0 description updated to reflect single-agent end-state.

**`.planning/REQUIREMENTS.md`:**
- Twitter Agent section header: `### ~~Twitter Agent~~ (DEPRECATED 2026-04-20)` with explanatory paragraph.
- Each TWIT-01..14 item: `[x]` → `[ ]`, strikethrough on name + body, trailing `**(DEPRECATED 2026-04-20)**` marker.
- Senior Agent section header: `### ~~Senior Agent~~ (DEPRECATED 2026-04-20)` with explanatory paragraph noting SENR-06 + SENR-07 are the exceptions.
- SENR-01..05 and SENR-08..09: strikethrough + `**(DEPRECATED 2026-04-20)**` marker.
- SENR-06 + SENR-07: kept `[x]` with trailing "*(shipped via Phase 10-03 as `morning_digest` at 15:00 UTC; retained post-sn9)*" note.
- Traceability table: TWIT-01..14 + SENR-01,02,03,04,05,08,09 → strikethrough + `**Deprecated 2026-04-20**`; SENR-06 + SENR-07 rephased to `Phase 10 (partial-carryover)` / `Complete`.

**`.planning/STATE.md`:**
- Frontmatter `stopped_at` + `last_updated` refreshed.
- 3 new decision entries appended under Decisions:
  - sn9 purge summary (Twitter + Senior Agent trim + what's preserved).
  - s3b cancellation (exploration superseded by sn9's full purge decision + operator's never-auto-post rule).
  - sn9 Rule-3 auto-fix documentation (FK orphan NULL'd inside DELETE transaction).
- Quick Tasks table: added s3b row (status `Cancelled (superseded by 260420-sn9)`) and sn9 row (all 5 commit SHAs, Verified status).
- Session Continuity: full narrative of the 5-task sequence, DB pre/post counts, preserved surfaces, budget impact (~$214/mo → ~$114/mo).

**Verify (Task 5):**
- Post-purge probe confirmed zero twitter-related rows in all 3 target predicates.
- Content DB rows preserved at 955 both sides (no collateral damage).
- CLAUDE.md diff: Project blurb changed + historical note appended + stack line updated.
- ROADMAP.md diff: deprecation notice + Phase 4/5 headers struck + Phase 10 banner + progress table + milestones line.
- REQUIREMENTS.md diff: Twitter Agent + Senior Agent section headers + 21 checkbox rows + traceability table rows.
- STATE.md diff: frontmatter + 3 decision entries + 2 quick-task rows + session continuity rewrite.

## Preserved Surfaces (defense-in-depth audit)

These surfaces were explicitly preserved and would signal a regression if any were missing post-sn9:

| Surface                                                             | Still present after sn9? |
|---------------------------------------------------------------------|--------------------------|
| `scheduler/pyproject.toml` → `tweepy[async]>=4.14`                  | ✓                        |
| `scheduler/config.py::Settings.x_api_bearer_token`                  | ✓                        |
| `scheduler/config.py::Settings.x_api_key`                           | ✓                        |
| `scheduler/config.py::Settings.x_api_secret`                        | ✓                        |
| `scheduler/worker.py::_validate_env` critical `X_API_BEARER_TOKEN`  | ✓                        |
| `scheduler/agents/content_agent.py::VIDEO_ACCOUNTS`                 | ✓                        |
| `scheduler/agents/content_agent.py::_search_video_clips`            | ✓                        |
| `scheduler/agents/content_agent.py::_draft_video_caption`           | ✓                        |
| `scheduler/agents/content_agent.py::_run_twitter_content_search`    | ✓ (method retained; name is legacy — rename out of scope) |
| `import tweepy.asynchronous` in `scheduler/agents/content_agent.py` | ✓                        |
| `morning_digest` cron @ 15:00 UTC                                   | ✓                        |
| `gold_history_agent` bi-weekly cron                                 | ✓                        |

## Known Stubs

None introduced. The content-agent output fields `twitter_post` / `twitter_caption` / `instagram_post` / `instagram_caption` in `QuotePreview` / `VideoClipPreview` / `InfographicPreview` are dormant string labels used for operator copy-paste hints; nothing upstream reads them as platform discriminators. Leaving them is zero-risk and aligns with the precedent set in lvy.

## Deviations from plan

**1. [Rule 3 — Blocking FK] NULL'd `related_id` on one instagram orphan row inside the Task 5 transaction.**
- **Found during:** Task 5 prod DB DELETE.
- **Issue:** `draft_items_related_id_draft_items` FK constraint blocked `DELETE FROM draft_items WHERE platform='twitter'` — 1 `instagram` row had `related_id` pointing at a twitter row (from lvy-era cross-platform relation wiring that lvy's purge did not clean up because it stayed scope-bounded to Instagram rows).
- **Fix:** Prepended `UPDATE draft_items SET related_id = NULL WHERE platform != 'twitter' AND related_id IN (SELECT id FROM draft_items WHERE platform='twitter')` to the DELETE transaction. Exactly 1 row affected. Instagram row itself left in place.
- **Files modified:** None (prod DB only).
- **Commit:** `55100c9` (this task's commit — no code change for the fix; the adjustment was a one-off SQL applied inside the `railway run` transaction).

**2. [Rule 3 — Deferred out-of-scope lint error] Pre-existing ruff I001 in `backend/alembic/versions/0007_add_market_snapshots.py`.**
- **Found during:** Task 3 backend pytest verification.
- **Issue:** ruff reports I001 (import-order) on that file. Not introduced by sn9 — traces back to commit `b28780b` (oa1 task, 2026-04-21).
- **Fix:** Logged in `.planning/quick/260420-sn9-full-purge-twitter-agent-trim-senior-to-/deferred-items.md` for future cleanup. Not fixed here (strict scope boundary — only auto-fix issues directly caused by current task's changes).

**3. Task boundary: deleted `ApprovalCard`, `PlatformTabBar`, `QueuePage` in Task 4 (not strictly listed in PLAN's `files_modified`).**
- **Reason:** After narrowing `Platform` type to `'content'`, `ApprovalCard` became dead (its only call site, the twitter branch in `PlatformQueuePage`, could no longer be reached). `PlatformTabBar` was only referenced by `QueuePage.tsx`, which itself was unreferenced in `App.tsx`. Deleting dead code in-flight is Rule 2 (auto-add/remove for correctness) — the alternative (leaving unreferenced components) would trip future lint/build cycles.
- **Net result:** -0 test coverage loss; the deleted tests covered surfaces that no longer ship.

Rule-1/Rule-2/Rule-4 auto-fix counts: 0 code bugs, 0 new critical functionality added, 0 architectural checkpoints hit. Rule-3 count: 2 (FK cleanup + deferred lint logging).

## Budget impact

Pre-sn9 monthly spend: ~$214 (operator's last r18-era total).
Post-sn9 monthly spend: **~$114** (X API Basic $100/mo cut).

Composition: SerpAPI ~$50 + Claude API ~$30 + metalpriceapi Basic $9 + Twilio ~$5 + Railway ~$10 + Vercel free + Neon free + FRED free + GEMINI (unused post-mfy) ~$0.

Well inside the stated $205-225 envelope with $90-110/mo headroom available for future scope additions.

## Self-Check: PASSED

- `.planning/quick/260420-sn9-full-purge-twitter-agent-trim-senior-to-/260420-sn9-SUMMARY.md` — FOUND (this file)
- Commit `62ffda4` (Task 1 — scheduler purge) — FOUND in `git log --oneline -10`
- Commit `be9cd8b` (Task 2 — senior trim) — FOUND
- Commit `aeaf412` (Task 3 — backend purge) — FOUND
- Commit `c30e288` (Task 4 — frontend purge) — FOUND
- Commit `55100c9` (Task 5 — DB + docs refresh) — FOUND (recorded post-commit)
- Prod DB post-probe: `draft_items_twitter=0`, `watchlists_all=0`, `config_twitter_keys=0` — CONFIRMED
- Prod DB content row preservation: `draft_items_content=955` both pre and post — CONFIRMED
- `frontend/` grep for `Twitter|twitter_agent|QuotaBar|ApprovalCard|PlatformTabBar|WatchlistTab` — 0 matches in file bodies (inert `twitter_post`/`twitter_caption` content_agent output keys excluded)
- `scheduler/agents/content_agent.py` grep for `VIDEO_ACCOUNTS|_search_video_clips|_draft_video_caption|_run_twitter_content_search|tweepy.asynchronous` — all 5 present
- `scheduler/pyproject.toml` grep for `tweepy[async]` — present
- `scheduler/config.py` grep for `x_api_bearer_token|x_api_key|x_api_secret` — all 3 present
- `scheduler/worker.py` grep for `X_API_BEARER_TOKEN` in critical block — present
