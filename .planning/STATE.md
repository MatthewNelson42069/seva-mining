---
gsd_state_version: 1.0
milestone: v1.0.1
milestone_name: — Content Preview and Rendered Images
status: v1.0.1 complete
stopped_at: Completed Phase 11 — v1.0.1 milestone shipped
last_updated: "2026-04-19T22:30:00.000Z"
progress:
  total_phases: 11
  completed_phases: 9
  total_plans: 68
  completed_plans: 56
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-30)

**Core value:** Every piece of content the system drafts must be genuinely valuable to the gold conversation it enters — a data point, an insight, a connection no one else made.
**Current focus:** v1.0.1 shipped — awaiting next milestone definition

## Current Position

Phase: Not started (v1.0.2 TBD)
Plan: Not started

## Performance Metrics

**Velocity:**

- Total plans completed: 0
- Average duration: -
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**

- Last 5 plans: none yet
- Trend: -

*Updated after each plan completion*
| Phase 01 P02 | 279 | 3 tasks | 13 files |
| Phase 01 P04 | 5 | 3 tasks | 8 files |
| Phase 01 P05 | 2 | 2 tasks | 6 files |
| Phase 01 P06 | 3 | 2 tasks | 6 files |
| Phase 02-fastapi-backend P04 | 163 | 2 tasks | 3 files |
| Phase 03 P03 | 191 | 2 tasks | 11 files |
| Phase 03 P04 | ~20 | 2 tasks | 7 files |
| Phase 04-twitter-agent P01 | 5 | 2 tasks | 11 files |
| Phase 04-twitter-agent P02 | 426 | 2 tasks | 12 files |
| Phase 04-twitter-agent P03 | 1320 | 1 tasks | 1 files |
| Phase 04-twitter-agent P04 | 124 | 2 tasks | 3 files |
| Phase 04-twitter-agent P05 | 15 | 1 tasks | 4 files |
| Phase 04-twitter-agent P05 | 15 | 2 tasks | 4 files |
| Phase 05-senior-agent-core P01 | ~8 | 2 tasks | 9 files |
| Phase 05-senior-agent-core P02 | 440m | 1 tasks | 2 files |
| Phase 05-senior-agent-core P03 | 15 min | 1 tasks | 2 files |
| Phase 05-senior-agent-core P04 | 20 | 1 tasks | 2 files |
| Phase 05 P05 | 2 minutes | 1 tasks | 2 files |
| Phase 06-instagram-agent P01 | 5 min | 2 tasks | 3 files |
| Phase 06-instagram-agent P02 | 10 | 1 tasks | 2 files |
| Phase 06 P03 | 129 | 1 tasks | 2 files |
| Phase 06 P04 | 207 | 2 tasks | 2 files |
| Phase 06 P05 | 8m | 1 tasks | 3 files |
| Phase 07-content-agent P01 | 2 | 2 tasks | 6 files |
| Phase 07-content-agent P02 | - | 2 tasks | 3 files |
| Phase 07-content-agent P03 | - | 1 tasks | 1 files |
| Phase 07-content-agent P04 | - | 1 tasks | 1 files |
| Phase 07-content-agent P05 | 5 | 2 tasks | 3 files |
| Phase 08-dashboard-views-and-digest P01 | 8 | 2 tasks | 10 files |
| Phase 08-dashboard-views-and-digest P03 | 15 | 2 tasks | 7 files |
| Phase 08 P02 | 32 | 1 tasks | 6 files |
| Phase 08-dashboard-views-and-digest P04 | 612 | 2 tasks | 9 files |
| Phase 08-dashboard-views-and-digest P06 | checkpoint | 1 tasks | 0 files |
| Phase 09-agent-execution-polish P01 | 8 | 2 tasks | 4 files |
| Phase 09-agent-execution-polish P02 | 2 | 2 tasks | 4 files |
| Phase 07-content-agent P07 | 10 | 2 tasks | 1 files |
| Phase 07-content-agent P08 | 5 | 2 tasks | 1 files |
| Phase 07 P09 | 2 | 2 tasks | 1 files |
| Phase 07 P10 | 3 | 2 tasks | 3 files |
| Phase 10-senior-agent-whatsapp-notifications P01 | 2 | 2 tasks | 2 files |
| Phase 10 P03 | 525589 | 2 tasks | 7 files |
| Phase 11 P01 | 45 min | 5 tasks | 22 files |
| Phase 11 P02 | 11 min | 2 tasks | 3 files |
| Phase 11 P03 | 3 min | 2 tasks | 3 files |
| Phase 11 P04 | 3 min | 1 tasks | 2 files |
| Phase 11 P05 | 5 min | 2 tasks | 4 files |
| Phase 11 P06 | 15 min | 2 tasks | 9 files |
| Phase 11 P07 | checkpoint | 3 tasks | 3 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Pre-build]: Separate scheduler worker from API server — crash isolation, prevents duplicate execution
- [Pre-build]: Full schema from day one including JSONB alternatives array — no schema migration debt later
- [Pre-build]: APScheduler 3.11.2 only — v4.x alpha has breaking API changes
- [Pre-build]: shadcn/ui tailwind-v4 branch only — main branch targets Tailwind v3
- [Phase 01]: pytest config embedded in pyproject.toml [tool.pytest.ini_options] — no separate pytest.ini
- [Phase 01]: asyncio_mode=auto in both projects — eliminates need for @pytest.mark.asyncio decorator on individual tests
- [Phase 01]: asyncpg SSL: strip sslmode=require from URL, use connect_args ssl=True — asyncpg rejects sslmode as URL param
- [Phase 01]: FastAPI lifespan used for engine.dispose() on shutdown — cleaner than deprecated on_event pattern
- [Phase 01]: test_schema.py skip condition checks for real neon.tech URL to prevent env var leakage from test_health.py fake DATABASE_URL
- [Phase 01]: APScheduler 3.11.2 AsyncIOScheduler with advisory lock — numReplicas=1 is primary prevention, pg_try_advisory_lock is defense-in-depth
- [Phase 02-02]: Queue router uses no prefix — /queue and /items/{id}/* are separate top-level paths matching spec, not nested under /queue prefix
- [Phase 02-02]: VALID_TRANSITIONS dict is single source of truth for state machine — only DraftStatus.pending has allowed targets
- [Phase 02-fastapi-backend]: asyncio.to_thread wraps synchronous Twilio SDK to avoid blocking the FastAPI event loop in WhatsApp service
- [Phase 02-fastapi-backend]: Retry-once on TwilioRestException with logging (D-16): warning on attempt 1, error on attempt 2, re-raise
- [Phase 03-03]: QueuePage runs all 3 platform queries in parallel to populate badge counts — queries are cheap and avoids tab-switch loading delays
- [Phase 03-03]: PlatformTabBar is prop-driven (no internal state) — QueuePage owns active tab state for testability
- [Phase 03-03]: NavLink end={true} only for root '/' route — prevents matching /settings as Queue-active state
- [Phase 03-04]: RelatedCardBadge uses callback prop (onSwitchPlatform) not Zustand — active platform is local QueuePage state
- [Phase 03-04]: ContentSummaryCard stopPropagation on buttons — card body click opens modal, buttons don't trigger modal
- [Phase 03-04]: Seed script builds own async engine from DATABASE_URL — avoids importing Settings which requires all env vars
- [Phase 04-twitter-agent]: tweepy[async] extra required — tweepy.asynchronous needs aiohttp + async-lru installed via [async] optional dep
- [Phase 04-twitter-agent]: Test stubs use per-function lazy imports so all 20 tests are collectable before agent module exists (Wave 0 correct RED state)
- [Phase 04-twitter-agent]: Pure scoring functions are module-level (not class methods) for direct testability in TDD
- [Phase 04-twitter-agent]: tweepy[async] extra required for AsyncClient — base tweepy missing aiohttp dep
- [Phase 04-twitter-agent]: scheduler/models/ mirrors backend/app/models/ — scheduler has no access to backend package
- [Phase 04-twitter-agent]: Two-model LLM pattern: Sonnet for drafting quality, Haiku for compliance speed/cost
- [Phase 04-twitter-agent]: Fail-safe compliance: ambiguous LLM response = block (not pass) for Seva Mining/financial advice check
- [Phase 04-twitter-agent]: Module-level wrapper functions (draft_for_post, filter_compliant_alternatives, build_draft_item) use __new__ to bypass __init__ for test injection
- [Phase 04-twitter-agent]: TwitterAgent instantiated inside job closure (not at build time) to avoid import side effects at test collection
- [Phase 04-twitter-agent]: All 25 watchlist accounts seeded at relationship_value=5 per user request (maximum priority for initial seed)
- [Phase 04-twitter-agent]: Backend models must be kept in sync with scheduler models manually — no shared package, each service owns its own copy of the model
- [Phase 05-senior-agent-core]: Wave 0 test stubs put pytest.skip() BEFORE the lazy import — ensures 19 tests show as 'skipped' not 'error' when senior_agent module doesn't exist yet
- [Phase 05-senior-agent-core]: migration 0004 adds both engagement_alert_level (engagement alert dedup) and alerted_expiry_at (expiry alert dedup) to draft_items in a single migration
- [Phase 05-senior-agent-core]: Jaccard similarity >= 0.40 threshold for story dedup, configurable via senior_dedup_threshold config key (default 0.40); lookback 24h via senior_dedup_lookback_hours
- [Phase 05-senior-agent-core]: cashtag-aware regex r'$[a-z0-9]+|\b\w+\b' preserves dollar-prefixed tokens like $gld and $2400 as atomic fingerprint units
- [Phase 05-senior-agent-core]: ORDER BY score ASC, expires_at ASC tiebreaking — soonest-expiring tied-score item is displaced; no special-case branch needed
- [Phase 05-senior-agent-core]: process_new_items module-level function uses lazy SeniorAgent instantiation to avoid circular imports from TwitterAgent call site
- [Phase 05-senior-agent-core]: run_expiry_sweep does NOT call _check_breaking_news_alert (that fires at item intake via process_new_item); engagement dedup uses one-way state machine null->watchlist->viral via engagement_alert_level column
- [Phase 05]: _headline_from_rationale splits on period-space to avoid splitting decimal numbers; queue_snapshot total computed in Python; yesterday_approved includes empty items list; var_2 truncated at last semicolon-space boundary within 200 chars
- [Phase 06-instagram-agent]: Wave 0 test stubs use pytest.skip() BEFORE lazy import — ensures 15 tests show as 'skipped' not 'error' when instagram_agent module doesn't exist yet; uv sync --all-extras required to preserve dev dependencies when adding prod deps
- [Phase 06-instagram-agent]: passes_engagement_gate accepts datetime parameter (not post_age_hours float) to match existing test stub signatures from Plan 01
- [Phase 06-instagram-agent]: select_top_posts named without instagram_ prefix to match Wave 0 test stubs
- [Phase 06]: Module-level functions (draft_for_post, check_compliance, build_draft_item_expiry) in instagram_agent.py for direct test injection without class instantiation
- [Phase 06]: Pre-screen '#' and 'seva mining' locally before calling Claude Haiku — avoids LLM cost for obvious compliance blocks
- [Phase 06]: Fail-safe compliance: only explicit 'pass' substring returns True; everything else blocks draft
- [Phase 06]: asyncio.sleep(2**attempt) gives 1s/2s backoff; 3 total attempts; empty list returned after exhaustion
- [Phase 06]: _check_critical_failure returns count only; alert at exactly consecutive_zeros==2 in _run_pipeline (dedup)
- [Phase 06]: Seed script uses 15 Instagram accounts (best-effort from 25 Twitter entities); 10 skipped with no active IG presence
- [Phase 07-content-agent]: Wave 0 test stubs use pytest.skip() BEFORE lazy import in content agent tests — ensures 16 tests show SKIPPED not ERROR during Wave 0 when module doesn't exist
- [Phase 07-content-agent]: ContentBundle scheduler mirror uses datetime.now(timezone.utc) lambda instead of deprecated datetime.utcnow — timezone-aware default
- [Phase 07-content-agent]: Content agent seed script only seeds config keys (no watchlists/keywords) — agent uses RSS + SerpAPI not platform watchlists
- [Phase 07-content-agent]: RSS_FEEDS and SERPAPI_KEYWORDS are module-level constants — accessible as ca.RSS_FEEDS and ca.SERPAPI_KEYWORDS in tests without class instantiation
- [Phase 07-content-agent]: run() creates and commits AgentRun immediately before pipeline starts — status visible even if pipeline crashes mid-flight
- [Phase 07-content-agent]: _extract_check_text is module-level (not class method) — consistent with established pattern for testable pure functions
- [Phase 08-dashboard-views-and-digest]: MSW /config/quota handler listed before /config/:key to prevent generic param matching quota path
- [Phase 08-dashboard-views-and-digest]: KeywordCreate.term field (not keyword) throughout frontend types — matches backend schema exactly
- [Phase 08-dashboard-views-and-digest]: ContentPage tests use vi.mock for API modules instead of MSW server.use() — relative fetch URLs cannot be intercepted in jsdom/Node.js MSW environment
- [Phase 08]: localStorage mock via vi.stubGlobal required for apiFetch tests — jsdom does not provide localStorage by default; any component calling apiFetch on render needs this mock in beforeEach
- [Phase 08]: useEffect syncs TanStack Query data to local state in DigestPage — direct render-time setState causes silent test failures
- [Phase 08-dashboard-views-and-digest]: JSDOM URL must be set to http://localhost:3000 in vitest config so MSW relative path handlers resolve to matching fetch URLs
- [Phase 08-dashboard-views-and-digest]: Human verification checkpoint approved — all three dashboard pages confirmed correct by operator
- [Phase 09-agent-execution-polish]: Twitter _get_config returns Optional[Config], so threshold reads use int(_cfg.value) if _cfg else default pattern — consistent with existing quota reads
- [Phase 09-agent-execution-polish]: Default parameter values in passes_engagement_gate match previous hardcoded values — backward compatibility preserved for existing tests without changes
- [Phase 09-agent-execution-polish]: expiry_sweep and morning_digest scheduler config keys placed in seed_content_data.py — scheduler-level concerns with no agent home; content seed is closest match
- [Phase 09-agent-execution-polish]: build_scheduler changed to async def to support await _read_schedule_config(engine) at startup; APScheduler API unaffected since main() already async
- [Phase 07-content-agent]: RSS_FEEDS expanded to 8 (reuters, bloomberg, goldseek, investing); SERPAPI_KEYWORDS to 10 (macro/inflation terms)
- [Phase 07-content-agent]: breaking_news format added as 4th Sonnet option with urgency-preference and senior analyst voice in system prompt
- [Phase 07-content-agent]: Multi-story pipeline with per-story error isolation replaces single-story; _is_already_covered_today() for cross-run dedup
- [Phase 07-content-agent]: VIDEO_ACCOUNTS capped at first 5 for API query length limits; fixed score 7.5 for Twitter-sourced content (video_clip, quote); _run_twitter_content_search() extracted as separate method for clean 07-07 merge; quote format added as choosable from article content in Sonnet prompt
- [Phase 07]: Sonnet prompt rewritten as central format decision engine for all 7 content types with Instagram design system (#F0ECE4/#0C1B32/#D4AF37) and historical pattern SerpAPI verification fallback
- [Phase 07]: GoldHistoryAgent uses fixed baseline score 8.0 for curated history stories (not RSS-scored)
- [Phase 07]: story slug tracked in Config before DraftItem creation so partial failures never cause story re-selection
- [Phase 10-senior-agent-whatsapp-notifications]: Phase 10: Switched whatsapp.py from content_sid (Meta-approved template SIDs) to body (free-form text) — Twilio sandbox accepts free-form without template approval; TEMPLATE_SIDS and send_whatsapp_template() removed
- [Phase 10]: Phase 10-03: expiry_sweep removed from scheduler; morning_digest at 15:00 UTC; WhatsApp failure non-fatal in run_morning_digest
- [Phase 11]: Used _get_render_bundle_job() helper for patchable ImportError-safe lazy scheduler import — Allows monkeypatching in tests without needing to patch a local import; scheduler agents/__init__.py causes tweepy ImportError in backend process which is caught gracefully
- [Phase 11-02]: genai_types.GenerateImagesConfig (plural) is the correct class name in google-genai 1.73.1 — RESEARCH.md had typo GenerateImageConfig (singular)
- [Phase 11-02]: Per-role retry (not per-bundle): each role gets 3 independent attempts; partial renders (e.g. 3/4) written as partial list; empty list on all-roles-failed
- [Phase 11-02]: Role names use twitter_visual/instagram_slide_1/2/3 convention to match RenderedImage schema; quote=2 roles not 1 per PLAN.md test behaviors
- [Phase 11-03]: Backend rerender endpoint uses asyncio.create_task in the backend's own event loop — cross-process scheduler.add_job is not possible (backend and scheduler are separate Railway services)
- [Phase 11-05]: TanStack Query v5 refetchInterval callback receives a query object (not (data, query) like v4); tests exercise the callback directly by extracting the query from the cache to avoid vi.useFakeTimers deadlocks
- [Phase 11-06]: RenderedImagesGallery mounted only for infographic + quote formats (D-04); other formats never render image skeletons
- [Phase 11-07]: importlib.util.spec_from_file_location bypasses scheduler/agents/__init__.py tweepy import in the backend process; scheduler/config.py uses extra="ignore" to tolerate backend-only env vars in the shared .env
- [2026-04-19 / quick 260419-lvy]: Instagram Agent (Phase 6) fully deprecated and purged from codebase — Apify scraping not viable, $50/mo spend cut; Seva Mining is now a three-agent system (Twitter + Senior + Content). Frontend IG UI removed, scheduler IG job removed, Apify deps removed from scheduler/backend. Content agent still emits instagram_post/instagram_caption/instagram_brief/carousel fields and image_render still emits IG slide roles, but nothing downstream consumes them (no migration written — safe no-op data).
- [2026-04-19 / quick 260419-lvy]: Content queue page now groups by agent_run matching Twitter pattern (showRunGroups = platform === 'twitter' || 'content'); content branch renders ContentSummaryCard inside grouped layout.

### Pending Todos

None yet.

### Quick Tasks Completed

| # | Description | Date | Commit | Status | Directory |
|---|-------------|------|--------|--------|-----------|
| 260407-n9t | Content agent schedule fix (6am/12pm PST) + enhanced WhatsApp notification with titles | 2026-04-07 | 9bc17e1 | | [260407-n9t](./quick/260407-n9t-content-agent-schedule-fix-and-enhanced-/) |
| 260407-neq | Switch content agent from two cron jobs to single interval trigger every 2 hours | 2026-04-07 | 8b1e22e | | [260407-neq](./quick/260407-neq-switch-content-agent-to-interval-every-2/) |
| 260409-qe8 | Fix Twitter engagement gate (None impression_count skips views check) + content agent non-ISO date fallback | 2026-04-09 | aecc81b | | [260409-qe8](./quick/260409-qe8-fix-twitter-engagement-gate-and-content-/) |
| 260419-ko3 | Fix 8 pre-existing test failures (backend + scheduler + frontend) | 2026-04-19 | 0cd0432 | | [260419-ko3](./quick/260419-ko3-fix-8-pre-existing-test-failures-across-/) |
| 260419-l5t | Post-v1.0.1 health-check cleanup: env.example hygiene, ruff+eslint lint-zero, JWT_SECRET length assertion | 2026-04-19 | 8bfdfea | Verified | [260419-l5t](./quick/260419-l5t-post-v1-0-1-health-check-cleanup-env-exa/) |
| 260419-lvy | Full purge Instagram agent + content queue run-grouping (deprecated Phase 6) | 2026-04-19 | b2ff329 / accf735 / 2eb9125 / 4ab94e7 | Verified | [260419-lvy](./quick/260419-lvy-full-purge-instagram-agent-content-queue/) |
| 260419-n4f | Content agent relevance cleanup — Bloomberg commodities swap, drop Investing.com, sharpen prompt, two-bucket gold gate, restore 7.0 threshold | 2026-04-19 | 502ae3e / 010926d / 2cfc9cb | Verified | [260419-n4f](./quick/260419-n4f-content-agent-relevance-cleanup-swap-blo/) |
| 260419-r0r | Long_form 400-char minimum floor + sharpen thread vs long_form prompt (thread=fact-rich, long_form=article-style) | 2026-04-20 | f30dd44 / 14caedc | Verified | [260419-r0r](./quick/260419-r0r-enforce-400-char-minimum-floor-on-long-f/) |
| 260419-rqx | Content agent tuning — 3h cadence, 0.40 recency weight, top-5 Haiku format-first pipeline, listicle rejection in gold gate | 2026-04-20 | 663d6d8 / 7fb5517 / af37d3c | Verified | [260419-rqx](./quick/260419-rqx-content-agent-tuning-pass-cadence-top-5-/) |
| 260419-si2 | Display Gemini-rendered images inline on content queue cards with role label, Dialog enlarge, and fetch+blob Download | 2026-04-20 | 1ff7f07 / 8a2d991 | Verified | [260419-si2](./quick/260419-si2-display-rendered-images-on-dashboard-app/) |

### Blockers/Concerns

- [Phase 1]: Twilio WhatsApp templates must be submitted to Meta during Phase 1 — approval takes 1-7 business days. Confirm whether a WhatsApp Business account already exists for Seva Mining before starting Phase 1 planning.
- [Phase 1]: Verify Neon free tier connection limit before setting pool_size — may need adjustment from default 5/10.
- [Phase 7]: SerpAPI plan selection needed before Content Agent — 100 searches/mo on basic plan may be insufficient for daily multi-topic runs.

## Session Continuity

Last session: 2026-04-20T03:47:00.000Z
Last activity: 2026-04-20 - Completed quick task 260419-si2: Display rendered_images on dashboard approval card with inline preview, click-to-enlarge modal, and per-image download button
Stopped at: Completed quick task 260419-si2 — inline rendered-image gallery on ContentSummaryCard with Dialog enlarge and Download
Resume file: None
