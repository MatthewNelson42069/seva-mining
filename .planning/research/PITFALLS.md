# Pitfalls Research — v2.1 Three-Tab Content Engine

**Domain:** Adding multi-tab nav + Reddit ingestion + first-user-write CRUD to an existing scheduled-cron production system
**Researched:** 2026-05-18
**Confidence:** HIGH (most pitfalls grounded in actual code paths read from the repo)

---

## 1. Reddit Ingestion (praw)

### CRITICAL — praw is sync; blocking the AsyncIOScheduler event loop

**What goes wrong:**
`praw.Reddit` and its `subreddit.hot()` / `subreddit.top()` calls are synchronous blocking I/O. The weekly_sweeper runs inside `AsyncIOScheduler`'s event loop (same process as `with_advisory_lock`, DB sessions, Sonnet calls). A bare `for post in subreddit.hot(limit=25)` call blocks the entire event loop for the duration of the HTTP round-trip. Every other coroutine — including the 08:00/12:00 daily_summary advisory-lock heartbeat — stalls until the Reddit call returns.

**Why it happens:**
`praw` uses `requests` under the hood (sync). `asyncpraw` exists and is the direct async replacement, but developers reaching for the canonical "praw" library miss this distinction.

**How to avoid:**
Use `asyncpraw` (the async fork, maintained in the same `praw-dev` org) instead of `praw`. All calls become `await subreddit.hot(limit=25)` and fit naturally into the existing async codebase. `asyncpraw` is a drop-in API replacement.

If `praw` is chosen instead for any reason (e.g., a specific feature gap), every network call must be wrapped in `asyncio.to_thread(lambda: ...)` — the same pattern already used for `serpapi` calls in `content_agent.py` (`loop.run_in_executor(None, _call)`). Do NOT call praw methods directly in async context.

**Warning signs:**
- Weekly sweeper takes >10s to complete in local testing with real Reddit calls
- Railway logs show daily_summary fires delayed or skipped on Sundays
- APScheduler logs `"Execution of job ... skipped: maximum number of running instances reached"`

**Phase to address:** Reddit ingestion phase (Phase A or whichever phase introduces `weekly_sweeper.py`)

---

### HIGH — praw/asyncpraw client construction is NOT zero-latency; Reddit auth can hang

**What goes wrong:**
`praw.Reddit(client_id=..., client_secret=..., user_agent=...)` (or the asyncpraw equivalent) does not immediately connect — it defers OAuth token fetch to the first API call. But that first API call inside an APScheduler job (e.g., the first `await subreddit.hot()`) will block for as long as Reddit's OAuth endpoint takes to respond. If Reddit's auth endpoint is slow (degraded, rate-limited, or timing out), the entire sweeper hangs without a timeout.

The existing 60s `AsyncAnthropic(timeout=60.0)` pattern in `daily_summary.py` demonstrates the project already knows this problem exists — but the pattern hasn't been pre-applied to the Reddit client.

**How to avoid:**
Set a connection timeout on the asyncpraw session at construction time:
```python
reddit = asyncpraw.Reddit(
    client_id=settings.reddit_client_id,
    client_secret=settings.reddit_client_secret,
    user_agent=settings.reddit_user_agent,
    requestor_kwargs={"timeout": 15},  # 15s ceiling per request
)
```
Wrap the entire Reddit ingestion block in a try/except that captures `asyncpraw.exceptions.AsyncPRAWException`, `asyncio.TimeoutError`, and bare `Exception` — using the same `counts["last_error"]` pattern from `quick-260514-jny` so failures surface in `agent_runs.errors`, not just Railway logs.

**Warning signs:**
- `weekly_sweeper` agent_run stays `status='running'` for >2 minutes
- `reconcile_stale_runs` sweeps a `weekly_sweeper` row to `failed` on the next scheduler boot

**Phase to address:** Reddit ingestion phase

---

### HIGH — Subreddit quarantine/private returns 403; crashes the whole sweeper

**What goes wrong:**
`r/Wallstreetsilver` and similar subreddits can be quarantined. Accessing a quarantined subreddit via praw/asyncpraw raises a 403 error (documented in official praw docs across versions 7.1.4 through current). If the sweeper iterates over a hardcoded list of subreddits without per-subreddit error isolation, a single 403 will abort ALL subreddit fetches — the sweeper produces zero Reddit posts even though 4 out of 5 subreddits were accessible.

**Why it happens:**
The natural implementation is `for sub in SUBREDDIT_LIST: posts += await fetch_subreddit(sub)`. One exception propagates up and kills the loop.

**How to avoid:**
Per-subreddit try/except with graceful degrade — the same section-isolation pattern already used in `run_daily_summary`:
```python
for sub_name in SUBREDDIT_LIST:
    try:
        sub = await reddit.subreddit(sub_name)
        async for post in sub.hot(limit=25):
            posts.append(...)
    except Exception as exc:
        logger.warning("weekly_sweeper: subreddit r/%s failed (%s) — skipping", sub_name, type(exc).__name__)
        counts["subreddit_errors"].append(f"{sub_name}: {type(exc).__name__}")
```
Log the skip; do NOT re-raise. The sweeper completes with partial data and marks the subreddit_errors in `agent_runs.errors`.

**Warning signs:**
- `r/Wallstreetsilver` or `r/Gold_and_Silver` appear in subreddit_errors on first deploy
- Weekly card has zero Reddit posts section despite the sweeper completing

**Phase to address:** Reddit ingestion phase

---

### MEDIUM — Reddit user-agent string causes aggressive rate limiting if generic

**What goes wrong:**
Reddit's API rules require a descriptive user-agent in the format `<platform>:<app ID>:<version string> (by /u/<reddit username>)`. A generic UA (e.g., `Python/asyncpraw` or `Mozilla/5.0`) causes Reddit to rate-limit more aggressively and can result in requests being silently dropped or returning 403.

**How to avoid:**
Set `REDDIT_USER_AGENT` in Railway env to a specific string, e.g., `"seva-mining-viral-sweeper/0.1 (by /u/<owner-reddit-handle>)"`. This requires a one-time decision on which Reddit account "owns" the app (used at reddit.com/prefs/apps setup). Document this in the Railway env-var setup runbook (mirrors the X Developer Portal runbook in CLAUDE.md).

**Warning signs:**
- Intermittent 429 responses even at low request volume
- Reddit calls succeed locally but fail on Railway

**Phase to address:** Reddit ingestion phase (env var setup step)

---

### MEDIUM — REDDIT_CLIENT_SECRET logged at startup alongside other env vars

**What goes wrong:**
`_validate_env()` in `worker.py` logs whether env vars are SET/MISSING. The current implementation logs `bool(settings.x_api_bearer_token)` etc. — presence only, not value. If v2.1 adds `REDDIT_CLIENT_ID/SECRET/USER_AGENT` to the log block carelessly (e.g., `logger.info("REDDIT_CLIENT_SECRET: %s", settings.reddit_client_secret)`), the secret will appear in Railway log stream.

**How to avoid:**
In `_validate_env()`, add Reddit vars to the `optional` dict (presence-only check, same as `SERPAPI_API_KEY`):
```python
optional["REDDIT_CLIENT_ID"] = bool(settings.reddit_client_id)
optional["REDDIT_CLIENT_SECRET"] = bool(settings.reddit_client_secret)
optional["REDDIT_USER_AGENT"] = bool(settings.reddit_user_agent)
```
Never log the value, only the boolean. Mirror exactly the existing pattern.

**Phase to address:** Reddit ingestion phase

---

## 2. Story Virality Compute

### HIGH — JSONB gold_news array extraction shape must match HIGH-4 contract exactly

**What goes wrong:**
The virality compute queries `daily_summaries.raw_sources_jsonb` for the past 7 days. The HIGH-4 contract (documented in `daily_summary.py` line 591) defines the JSONB shape as:
```
{"gold_news": [{"title": str, "link": str, "source_name": str, "score": float, "published_at": str|None}]}
```
The virality code must navigate `row.raw_sources_jsonb["gold_news"]` to get the story list. If any call site in the past ever wrote a different shape (e.g., direct dict assignment without the HIGH-4 wrapper, a test fixture with `"stories"` instead of `"gold_news"`), the virality compute silently returns 0 cross-references for those rows.

Additionally: `raw_sources_jsonb` is typed as `JSONB` in the ORM model but retrieved as Python `dict` by SQLAlchemy + asyncpg. If a row was written with `raw_sources_jsonb=None` (the failure-path in `run_daily_summary`'s `except` block), iterating `row.raw_sources_jsonb["gold_news"]` raises `TypeError: 'NoneType' object is not subscriptable`.

**How to avoid:**
Defensive extraction with None guard:
```python
stories = (row.raw_sources_jsonb or {}).get("gold_news", [])
```
Add a unit test that exercises a row where `raw_sources_jsonb` is `None` (failure row) — the virality compute must return empty for that row, not raise.

**Phase to address:** Weekly sweeper phase

---

### HIGH — Title-based dedup must be applied WITHIN a summary row before cross-summary count

**What goes wrong:**
The virality algorithm counts how many daily_summary rows (across 14 rows over 7 days) contain a given story. But a story can appear in the TOP 20 list of the same row more than once if dedup was imperfect at ingest time (different URLs for the same story slipping through URL-dedup but not title-dedup). If not deduplicated per-row before counting, one story appears to cross-reference itself within the same row, inflating its virality count.

**How to avoid:**
Before cross-summary counting, apply title-based dedup within each row's `gold_news` list using the existing `deduplicate_stories` pattern (SequenceMatcher 0.85 threshold already in `content_agent.py`). This is a one-liner: run `deduplicate_stories(stories_for_row)` on each row's list before adding to the aggregate cross-reference dict.

**Phase to address:** Weekly sweeper phase

---

### MEDIUM — URL canonicalization before link-based dedup (UTM params, mobile vs desktop)

**What goes wrong:**
The virality compute groups stories by title similarity (SequenceMatcher 0.85). If the implementation uses URL equality as a secondary grouping key without canonicalization, two versions of the same story (`https://bloomberg.com/...?utm_source=email` and `https://bloomberg.com/...`) appear as different stories and split the cross-reference count, diluting the virality signal for that story.

**How to avoid:**
For any URL-based grouping (even as a secondary key), strip query parameters and normalize trailing slashes before comparison:
```python
from urllib.parse import urlparse, urlunparse
def canonical_url(url: str) -> str:
    p = urlparse(url.lower())
    return urlunparse(p._replace(query="", fragment=""))
```
Primary grouping key should always be title similarity (more robust than URL). URL canonical is a tiebreaker only.

**Phase to address:** Weekly sweeper phase

---

### LOW — O(N²) title similarity is tractable at N=210 but should be measured

**What goes wrong:**
14 rows × 15 stories/row = 210 story records. SequenceMatcher O(N²) = ~44,100 comparisons. In Python this is fast (~0.5-2s depending on string lengths) but it runs synchronously inside the async event loop. If future data volume grows (GOLD_TOP_N was recently bumped 12→20, and could grow again), this becomes a latency issue.

**How to avoid:**
Add a timing log for the dedup pass: `logger.info("virality_dedup: %d stories, %.2fs", n, elapsed)`. If it exceeds 1s, move the dedup pass to `asyncio.to_thread`. No action required for v2.1 launch, but the measurement flag should be in the code from day one.

**Phase to address:** Weekly sweeper phase

---

## 3. Weekly Sonnet "Content Angles" Generation

### HIGH — Reddit post bodies can exceed token budget without truncation

**What goes wrong:**
Some Reddit posts (especially r/Gold_and_Silver long-form discussions) can be 1,000-2,000 words. If all selected Reddit posts are passed full-body to the Sonnet prompt, the input token count can reach 8,000-12,000 tokens for a 5-post sample. This is within Sonnet's context window but:
1. Costs more than necessary (the weekly_sweeper must stay within the ~$200/month budget)
2. Can push toward Sonnet's output limit when the prompt demands 3 structured angles

**How to avoid:**
Truncate each Reddit post body to 500 characters before including in the Sonnet user prompt (mirrors the existing `[:500]` truncation in `content_agent.py` line 290 for the format classifier). Apply the same ceiling to story titles (truncate at 200 chars). Document the truncation in the prompt comment: "# Bodies truncated to 500 chars to control token budget."

**Warning signs:**
- Anthropic API returns `max_tokens` truncation warnings in response metadata
- Weekly Sonnet call costs >$0.10/week (visible in Anthropic usage dashboard)

**Phase to address:** Weekly sweeper phase

---

### HIGH — Sonnet content angles must stay within the gold bull thesis; no bearish drift

**What goes wrong:**
If Reddit posts that week are dunking on gold (e.g., r/Wallstreetsilver posts arguing gold is overvalued), Sonnet will incorporate that bearish sentiment into the content angles unless explicitly prohibited. A bearish angle in the weekly card contradicts the project's locked bull-thesis rule (GOLD_NEWS_SYSTEM_PROMPT explicitly states this).

**How to avoid:**
The weekly_sweeper Sonnet system prompt must include an explicit constraint:
```
All three content angles MUST support the gold bull thesis — gold price going higher,
central bank demand, inflation hedge, etc. Do NOT produce an angle that is neutral or
bearish toward gold price, regardless of what the Reddit posts contain. If Reddit
posts express bearish sentiment, extract the underlying data point and reframe it
through the bull lens, or discard it.
```
This is a direct analogue of the GOLD_NEWS_SYSTEM_PROMPT "stories that DO NOT advance the bull thesis should be excluded" rule.

**Phase to address:** Weekly sweeper phase

---

### HIGH — Timeout wrapping for weekly Sonnet call must mirror post-ii6 pattern exactly

**What goes wrong:**
The post-ii6 fix set `AsyncAnthropic(timeout=60.0)` in `daily_summary.py`. The weekly_sweeper constructs its own Anthropic client. If the client is constructed without an explicit timeout, it inherits the SDK default (600s). A hung Sonnet call will hold the event loop (or in-thread executor) for up to 10 minutes — long enough to block the next scheduler tick and stall the entire worker process.

**How to avoid:**
Construct the Anthropic client with an explicit 60s timeout in `weekly_sweeper.py`, identical to `daily_summary.py`:
```python
anthropic_client = AsyncAnthropic(
    api_key=settings.anthropic_api_key, timeout=60.0,
)
```
A single weekly Sonnet call is lower risk than the 2×-daily call, but the pattern must be consistent across all agents.

**Phase to address:** Weekly sweeper phase

---

### MEDIUM — Hallucinated facts in content angles; grounding constraint required

**What goes wrong:**
Sonnet may synthesize plausible-sounding gold price figures or analyst quotes that are NOT in the supplied Reddit posts or viral stories. Without an explicit grounding constraint, the content angles could contain invented data points that mislead the operator when used for social-media planning.

**How to avoid:**
Add a grounding rule to the Sonnet system prompt:
```
Use ONLY facts, figures, and claims present in the supplied Reddit posts and viral stories.
Do NOT introduce outside knowledge, invented price targets, or analyst names not
mentioned in the supplied inputs.
```
Mirror the MOD-5 grounding rule already applied in `daily_summary.py` (published_at injection to prevent date hallucination).

**Phase to address:** Weekly sweeper phase

---

## 4. Calendar CRUD (First User-Write Surface)

### CRITICAL — Date field sends as DATE but FastAPI/Pydantic may interpret as datetime with TZ conversion

**What goes wrong:**
The frontend user is in PT (UTC-7/8). When creating or patching a calendar item with `date: "2026-05-20"`, Pydantic may silently convert a Python `date` field into a UTC datetime if the model uses `datetime` instead of `date`. A user clicks "Wednesday May 20" and the server stores `2026-05-19` (Tuesday) because the midnight PT datetime rolled back to the previous UTC day during serialization.

This is the classic timezone-off-by-one bug. It will be invisible in development (both client and server on same machine) but visible on Railway (UTC server, PT user).

**Why it happens:**
Developers reach for `datetime` for all date/time fields. SQLAlchemy's `Date` column type is distinct from `DateTime`. If the model uses `Column(DateTime)` instead of `Column(Date)`, Postgres stores a full timestamp and Pydantic serializes it with timezone context on reads.

**How to avoid:**
- SQLAlchemy model: `date = Column(Date, nullable=False)` (NOT `DateTime`)
- Pydantic schema: `date: datetime.date` (NOT `datetime.datetime`)
- Frontend: send explicit `"YYYY-MM-DD"` string, never a JS `Date` object
- Backend: parse as `date` type; no timezone conversion happens on a bare date
- Add a test: create a calendar item with `date="2026-05-20"`, read it back, assert `response["date"] == "2026-05-20"` — run this test with the server process in UTC timezone (`TZ=UTC pytest`)

**Warning signs:**
- Calendar items created in the evening PT appear on the previous day's grid cell

**Phase to address:** Calendar CRUD phase

---

### HIGH — Optimistic UI rollback not wired on PATCH failure; orphaned UI state

**What goes wrong:**
TanStack Query `useMutation` optimistic updates require a three-step pattern: `onMutate` (apply optimistic update + snapshot old data), `onError` (restore snapshot), `onSettled` (invalidate query). If `onError` is omitted or only calls `invalidateQueries` (not `setQueryData` with the snapshot), the calendar grid shows the new date after a failed drag-and-drop, permanently out of sync with the DB until the user refreshes.

**Why it happens:**
The `onMutate` snapshot pattern is non-obvious. Developers write the happy path (optimistic update + invalidation on success) and miss the rollback.

**How to avoid:**
```typescript
const mutation = useMutation({
  mutationFn: (vars: { id: string; date: string }) =>
    api.patch(`/calendar/${vars.id}`, { date: vars.date }),
  onMutate: async (vars) => {
    await queryClient.cancelQueries({ queryKey: ['calendar'] })
    const snapshot = queryClient.getQueryData(['calendar'])
    queryClient.setQueryData(['calendar'], (old) => /* apply optimistic */)
    return { snapshot }  // returned context is passed to onError
  },
  onError: (_err, _vars, context) => {
    queryClient.setQueryData(['calendar'], context?.snapshot)
  },
  onSettled: () => {
    queryClient.invalidateQueries({ queryKey: ['calendar'] })
  },
})
```
This pattern is required for ALL calendar mutations (create, update, delete, reschedule). Test the rollback path explicitly: mock the PATCH endpoint to return 500 and assert the UI restores the pre-drag position.

**Phase to address:** Calendar CRUD phase

---

### HIGH — Empty title allowed by frontend but rejected by backend — silent UX failure

**What goes wrong:**
A calendar item with an empty title string is meaningless in the grid view. If the backend validates `title: str` (non-empty) and the frontend does not pre-validate before firing the mutation, the mutation returns 422, and without proper error surfacing the user sees no feedback — the modal closes, the grid refreshes, and the item is gone (it was never created).

**How to avoid:**
Both layers must validate:
- Frontend: disable submit button when `title.trim() === ""`, show inline error message
- Backend: Pydantic `@field_validator("title")` that raises `ValueError` if `title.strip() == ""`; FastAPI returns 422 with a detail message that the frontend can display as a toast

**Phase to address:** Calendar CRUD phase

---

### MEDIUM — No `updated_at` field makes mutation ordering ambiguous in dev tools

**What goes wrong:**
For a single-user system, last-write-wins is acceptable (no real concurrent edit conflict). But without an `updated_at` column on `calendar_items`, there is no server-side audit trail for "when was this item last changed." This matters during debugging: if an item appears in the wrong state, there is no timestamp to cross-reference with Railway logs.

**How to avoid:**
Add `updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())` to the `calendar_items` model. The PATCH endpoint need not enforce any optimistic concurrency (no `If-Match` header required for single-user), but the field must be present for observability. Include it in the `CalendarItemResponse` Pydantic schema so the frontend can display "last edited: ..." in the detail view.

**Phase to address:** Calendar CRUD phase (migration + model)

---

## 5. Tab Nav Route Restructure

### CRITICAL — shadcn Tabs `value` prop must be driven by React Router location, not local state

**What goes wrong:**
The shadcn `Tabs` primitive has two modes: uncontrolled (internal state, `defaultValue`) and controlled (`value` + `onValueChange`). If the tab is implemented with `defaultValue="news-funnel"` and `onValueChange` only calls `navigate()`, a browser Back/Forward click changes the URL but does NOT update the `Tabs` value prop — the wrong tab appears highlighted while the correct page content renders via React Router's `<Outlet />`. This splits the tab UI from the router state.

**Why it happens:**
Developers wire `onValueChange → navigate()` (tab click → URL change) but miss the reverse: URL change → tab highlight update. The tab only re-renders when its `value` prop changes.

**How to avoid:**
Drive the `value` prop from `useLocation()`:
```typescript
const location = useLocation()
const activeTab = location.pathname === '/' ? 'news-funnel'
  : location.pathname === '/calendar' ? 'calendar'
  : location.pathname === '/viral' ? 'viral'
  : 'news-funnel'
return (
  <Tabs value={activeTab} onValueChange={(v) => navigate(v === 'news-funnel' ? '/' : `/${v}`)}>
    ...
  </Tabs>
)
```
The tab highlights, browser back/forward, and direct URL entry all stay in sync.

**Phase to address:** Tab nav / UI restructure phase

---

### HIGH — v2.0 redirects `/queue` and `/agents/:slug` must survive the route restructure

**What goes wrong:**
`App.tsx` currently defines:
```tsx
<Route path="/queue" element={<Navigate to="/" replace />} />
<Route path="/agents/:slug" element={<Navigate to="/" replace />} />
```
These "bookmark-grace" redirects (FEED-04) point to `/`. After v2.1, `/` becomes the tabbed layout with the News Funnel tab active — which is the correct target. BUT: if the route restructure moves `<AppShell />` to a different nesting level (e.g., adding a layout wrapper above it), these `<Navigate to="/" replace />` statements may no longer be inside the `<ProtectedRoute />` subtree, making them publicly accessible without auth. Also, if `"/"` changes meaning (e.g., redirects to `/news-funnel`), the redirect targets must be updated in lockstep.

**How to avoid:**
Keep the redirect routes inside `<ProtectedRoute />` — never let them escape to public routes. After v2.1's route restructure, explicitly test: visit `/queue` as an authenticated user → confirm redirect to the News Funnel tab content. The test must verify the *rendered page*, not just the URL.

**Phase to address:** Tab nav / UI restructure phase

---

### HIGH — AppHeader max-width `max-w-[720px]` conflicts with 3-tab layout at narrow desktop widths

**What goes wrong:**
`AppHeader.tsx` uses `max-w-[720px] mx-auto`. The News Funnel feed content at 720px is appropriate. But the shadcn `Tabs` primitive added to the header area renders tab labels inside that 720px constraint. With 3 medium-length labels ("News Funnel", "Content Calendar", "Weekly Viral") plus the brand mark + logout button, the header will overflow at 720px on standard 1280px desktop displays.

**How to avoid:**
Either:
1. Move the tab nav below the header (in a sub-header bar), keeping `max-w-[720px]` for the brand + logout row only
2. Widen the header `max-w` to `max-w-[960px]` or `max-w-[1100px]` for the tab row only

Option 1 is lower-risk (no layout cascade). The tab nav sits in its own `<nav>` bar between `<AppHeader />` and `<main>`, styled with `border-b border-zinc-800`. This mirrors the Linear-style pattern (top bar → sub-nav → content area).

**Phase to address:** Tab nav / UI restructure phase

---

### MEDIUM — Tab URL paths must be decided before building the Calendar and Viral pages

**What goes wrong:**
If the Tab nav phase builds tab navigation using `defaultValue` with no URL routing, and the Calendar phase later adds `react-router` integration to `/calendar`, the routing patterns conflict. Each phase will need to redo the other's work.

**How to avoid:**
Decide tab URL mapping before writing any tab code:
- Tab 1 (News Funnel) → `/` (preserves v2.0 canonical URL, no redirect needed)
- Tab 2 (Content Calendar) → `/calendar`
- Tab 3 (Weekly Viral Sweeper) → `/viral`

Add all three `<Route>` entries in the same phase as the tab nav, even if the Calendar and Viral page components are stubs initially. This locks the URL contract before content is built.

**Phase to address:** Tab nav / UI restructure phase (establish URL contract first)

---

## 6. shadcn Tabs + Linear UI Redesign

### HIGH — shadcn Tabs must be installed from the Tailwind v4 branch, not main

**What goes wrong:**
The project is on Tailwind CSS v4. The main `shadcn/ui` branch targets Tailwind v3. Installing Tabs via `npx shadcn@latest add tabs` without confirming the v4 branch produces a component with v3 utility class syntax that either silently renders incorrectly or requires manual v4 migration. This is a pre-existing risk noted in `CLAUDE.md` ("verify Tailwind v4 compatibility — the `tailwind-v4` branch of shadcn is the correct one").

**How to avoid:**
Confirm the shadcn CLI init was done with the `tailwind-v4` branch (`npx shadcn@canary add tabs` or via the component installer on `ui.shadcn.com` with v4 confirmed). Verify the installed `components/ui/tabs.tsx` uses CSS custom property-based color references (e.g., `bg-background`, `text-foreground`) rather than hardcoded Tailwind v3 color classes. If unsure: compare the generated file against the `tailwind-v4` branch source at https://ui.shadcn.com/docs/components/radix/tabs.

**Phase to address:** Tab nav / UI restructure phase (before any other shadcn Tabs work)

---

### HIGH — Tailwind v4 dark mode defaults changed: class-based dark mode strategy requires explicit opt-in

**What goes wrong:**
Tailwind v4 defaults dark mode to `@media (prefers-color-scheme: dark)` — the media-query strategy — removing the v3 class-based `dark:` strategy that relies on a `class="dark"` attribute on `<html>`. The project is locked to dark theme (no toggle). If the app was initialized under v3's class-based strategy (the common Linear-inspired pattern) and v4 is now active, all existing `dark:` utilities may have stopped working, or are conditionally active based on OS preference rather than a fixed class.

**How to avoid:**
Audit current Tailwind config / CSS: confirm whether `dark:` class-based strategy is declared. If it is, add `@custom-variant dark (&:is(.dark *));` to the v4 CSS config to preserve the class-based behavior. If it isn't, the app is already using media-query dark mode and works correctly on any OS in dark mode — but the Linear-style UI redesign's amber-gold token additions must use CSS custom properties, not rely on `dark:` class prefix.

**Phase to address:** UI redesign phase

---

### MEDIUM — New color tokens in the UI redesign must not clobber existing `zinc-*` references in AppHeader

**What goes wrong:**
`AppHeader.tsx` uses hardcoded Tailwind classes: `border-zinc-800`, `bg-zinc-900`, `text-zinc-400`, `text-zinc-100`. The Linear-style redesign introduces amber-gold accents and a refined palette. If the redesign changes Tailwind's default `zinc` token values via `@theme` overrides (e.g., redefining `--color-zinc-900`), the AppHeader's existing classes will render with the new values unexpectedly — possibly invisible text or wrong background.

**How to avoid:**
Do the UI redesign in a single pass, not piecemeal. Before merging, do a visual review of AppHeader, SummaryFeedPage, and all existing card components using the new token set. Prefer ADDING new semantic tokens (e.g., `--color-surface`, `--color-surface-elevated`) and migrating existing components to them, rather than redefining the `zinc` scale.

**Phase to address:** UI redesign phase — one comprehensive pass only

---

### MEDIUM — Vite chunk-size warning will worsen; lazy-load Calendar and Viral pages

**What goes wrong:**
Adding @dnd-kit (for drag-and-drop), shadcn Tabs, the Calendar page, and the Viral page to the bundle increases main chunk size. The v2.0 build already triggers Vite's 500 KiB warning. Without code-splitting, all three tab pages load on initial auth — the user pays the Calendar and Viral page parse cost even if they only use the News Funnel.

**How to avoid:**
Lazy-load the Calendar and Viral page components:
```typescript
const CalendarPage = React.lazy(() => import('@/pages/CalendarPage'))
const ViralPage = React.lazy(() => import('@/pages/ViralPage'))
```
Wrap the route subtree in `<Suspense fallback={<div className="p-8 text-zinc-500">Loading...</div>}>`. This is the standard Vite + React Router code-splitting pattern. `@dnd-kit` should be in the same lazy chunk as CalendarPage (it is only needed there).

**Phase to address:** Tab nav / UI restructure phase (establish lazy-load boundary when routes are added)

---

## 7. Advisory Lock + Cron Discipline

### CRITICAL — Lock ID 1019 must be added to JOB_LOCK_IDS BEFORE registering weekly_sweeper

**What goes wrong:**
The OPS-02 uniqueness assertion at module import time (`assert len(set(JOB_LOCK_IDS.values())) == len(JOB_LOCK_IDS)`) prevents duplicate IDs. But it only catches duplicates within the dict — it does NOT catch a new job registered directly in `build_scheduler()` without being added to `JOB_LOCK_IDS`. If `weekly_sweeper` uses a hardcoded lock ID that happens to equal an existing ID (e.g., someone picks `1017` thinking "daily_summary uses 1018"), the two jobs will silently skip each other on every fire.

**How to avoid:**
Add `"weekly_sweeper": 1019` to `JOB_LOCK_IDS` BEFORE any other work. The OPS-02 assertion will then guard against future collisions. Confirm 1010-1018 are accounted for:
- 1005: midday_digest (dead code, reserved)
- 1010-1016: sub-agent dead code (reserved)
- 1017: daily_summary
- 1018: daily_summary_prune
- 1019: weekly_sweeper (NEXT FREE)

**Phase to address:** Weekly sweeper phase — first task in that phase

---

### HIGH — reconcile_stale_runs must be extended to include agent_name='weekly_sweeper'

**What goes wrong:**
`reconcile_stale_runs()` sweeps ALL `agent_runs` rows where `status='running'` and `started_at < cutoff`. The query uses no `agent_name` filter — it already handles `weekly_sweeper` automatically by design. BUT: the 30-minute `threshold_minutes` was calibrated for the daily_summary's worst-case runtime. The weekly sweeper's expected runtime (Reddit fetch ~5s + virality compute ~2s + Sonnet call ~15s = ~25s) fits within 30 minutes easily. No change required — but this must be explicitly verified, not assumed.

**How to avoid:**
Add a comment in `reconcile_stale_runs()` noting that the 30-minute threshold covers all registered agents including weekly_sweeper. Add a test: insert a `weekly_sweeper` agent_run row with `status='running'` and `started_at=now - 31 min`, run `reconcile_stale_runs()`, assert the row is now `status='failed'`.

**Phase to address:** Weekly sweeper phase

---

### HIGH — Weekly sweeper Sunday 08:00 PT CronTrigger uses the same misfire_grace_time as daily_summary

**What goes wrong:**
`build_scheduler()` sets `misfire_grace_time=1800` globally (30 minutes). A Railway deploy that completes between 08:00 and 08:30 PT on a Sunday will catch the weekly sweeper via the grace window. BUT: a Railway deploy that completes AFTER 08:30 PT on a Sunday will miss the weekly sweep entirely — it will not fire until the following Sunday.

APScheduler 3.x documents that `day_of_week='sun'` is valid and that the `timezone` parameter on `CronTrigger` correctly handles DST transitions (the 08:00-09:00 hour is well outside the DST-ambiguous 01:00-02:00 window — same safety check already documented for daily_summary in `worker.py` MOD-1 comment).

**How to avoid:**
Document the "first deploy may miss" scenario in the weekly_sweeper agent file (mirror the midday_digest retiming comment pattern in `worker.py`). Provide a manual trigger escape hatch: `python -m agents.weekly_sweeper` can be run directly from Railway's shell to produce the first sweep without waiting for Sunday. This is the same pattern the user would use for any missed first fire.

**Phase to address:** Weekly sweeper phase

---

## 8. Database Migration

### CRITICAL — `down_revision` chain must reference 0010 exactly; Alembic will refuse to run on mismatch

**What goes wrong:**
Alembic builds its migration chain by following `down_revision` pointers. If the new migration(s) reference `down_revision = '0009'` but the actual last migration is `'0010'`, Alembic raises `CommandError: Can't locate revision identified by '0009'` and refuses to run `alembic upgrade head`. The entire Railway deploy fails (migrations run before app start on deploy).

**How to avoid:**
Before writing the v2.1 migration file: `alembic heads` to confirm the current head. The `down_revision` in the new file must equal this output exactly (not assumed from memory). Add a CI check: `alembic check` (Alembic 1.9+) verifies the migration chain is consistent without running migrations.

**Phase to address:** Database migration phase (first task)

---

### HIGH — Two new tables should ship as one migration for atomicity within the same deploy

**What goes wrong:**
If `0011_add_calendar_items` and `0012_add_weekly_sweeps` ship in the same Railway deploy but the deploy fails between the two migrations (e.g., Neon connection timeout during migration), the database is in a partial state: `calendar_items` exists but `weekly_sweeps` does not. The backend code that expects both tables will throw `ProgrammingError: table weekly_sweeps does not exist` on startup, making the app non-recoverable without manual intervention.

**How to avoid:**
Ship `calendar_items` and `weekly_sweeps` as ONE migration file (`0011_add_calendar_and_sweeps`) if they ship in the same deploy. Alembic migration files are transactional in Postgres — both tables are created atomically or neither is. Only split them across separate migrations if they ship in separate deploys (different phases).

**Phase to address:** Database migration phase

---

### HIGH — Dual-model parity: `weekly_sweeps` and `calendar_items` each need a parity test

**What goes wrong:**
The project has an established pattern (Phase B precedent): every new SQLAlchemy model must have a parity test verifying that the scheduler model (`scheduler/models/`) and the backend model (`backend/app/models/`) are byte-identical. If only the backend model has the new column (or vice versa), writes from the scheduler worker produce DB rows that the backend API cannot read correctly.

The parity test catches this at test time rather than at deploy time.

**How to avoid:**
Add `scheduler/tests/test_calendar_item_model.py` and `scheduler/tests/test_weekly_sweep_model.py` that:
1. Import both model classes
2. Assert `scheduler_model.__tablename__ == backend_model.__tablename__`
3. Assert column names match (using `sqlalchemy.inspect`)

This mirrors the existing Phase B parity test pattern. Run these tests in CI before merge.

**Phase to address:** Database migration phase (alongside model creation)

---

### MEDIUM — `agent_run_id` FK on `weekly_sweeps` should be `SET NULL ON DELETE` (mirror daily_summaries)

**What goes wrong:**
`daily_summaries.agent_run_id` is a nullable FK with `SET NULL ON DELETE` — if an agent_run row is deleted (e.g., manual cleanup), the summary row is preserved with `agent_run_id=NULL` rather than cascade-deleted. If `weekly_sweeps.agent_run_id` is defined as `CASCADE DELETE` instead, manual cleanup of agent_run rows would silently delete weekly sweep data. Given that sweeps are produced once weekly and represent high-signal content, data loss on cleanup would be noticeable.

**How to avoid:**
```python
agent_run_id = Column(UUID(as_uuid=True), ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True)
```
Mirror `daily_summaries` exactly. `calendar_items` has no FK (standalone table) — no ondelete behavior needed.

**Phase to address:** Database migration phase

---

## Phase-to-Pitfall Mapping

| Pitfall | Category | Severity | Prevention Phase |
|---------|----------|----------|-----------------|
| praw sync blocks event loop | Reddit | CRITICAL | Reddit ingestion phase |
| asyncpraw timeout not set | Reddit | HIGH | Reddit ingestion phase |
| Subreddit 403 crashes sweeper | Reddit | HIGH | Reddit ingestion phase |
| Weak user-agent causes rate limiting | Reddit | MEDIUM | Reddit ingestion phase (env setup) |
| SECRET logged in _validate_env | Reddit | MEDIUM | Reddit ingestion phase |
| JSONB None guard missing | Virality | HIGH | Weekly sweeper phase |
| Title dedup within-row before cross-count | Virality | HIGH | Weekly sweeper phase |
| URL canonicalization for dedup | Virality | MEDIUM | Weekly sweeper phase |
| O(N²) timing not measured | Virality | LOW | Weekly sweeper phase |
| Reddit post body blows token budget | Sonnet | HIGH | Weekly sweeper phase |
| Bearish angles in content suggestions | Sonnet | HIGH | Weekly sweeper phase |
| Sonnet timeout not set (60s) | Sonnet | HIGH | Weekly sweeper phase |
| Hallucinated facts in angles | Sonnet | MEDIUM | Weekly sweeper phase |
| Date field TZ off-by-one (DATE vs datetime) | Calendar | CRITICAL | Calendar CRUD phase |
| Optimistic rollback not wired | Calendar | HIGH | Calendar CRUD phase |
| Empty title passes frontend | Calendar | HIGH | Calendar CRUD phase |
| No updated_at column | Calendar | MEDIUM | Calendar CRUD phase (migration) |
| Tabs value not driven by router location | Tab nav | CRITICAL | Tab nav phase |
| v2.0 redirects escape ProtectedRoute | Tab nav | HIGH | Tab nav phase |
| AppHeader 720px constraint overflow | Tab nav | HIGH | Tab nav phase |
| Tab URL paths decided too late | Tab nav | MEDIUM | Tab nav phase (first) |
| shadcn Tabs from v3 branch | UI | HIGH | Tab nav phase |
| Tailwind v4 dark mode strategy change | UI | HIGH | UI redesign phase |
| Color tokens clobber existing zinc refs | UI | MEDIUM | UI redesign phase |
| Bundle size / no lazy loading | UI | MEDIUM | Tab nav phase |
| Lock 1019 not in JOB_LOCK_IDS | Cron | CRITICAL | Weekly sweeper phase (first task) |
| reconcile_stale_runs coverage | Cron | HIGH | Weekly sweeper phase |
| Sunday 08:00 misfire on first deploy | Cron | HIGH | Weekly sweeper phase |
| down_revision chain mismatch | Migration | CRITICAL | Migration phase (first task) |
| Two tables in separate migrations same deploy | Migration | HIGH | Migration phase |
| Dual-model parity tests missing | Migration | HIGH | Migration phase |
| agent_run_id FK should be SET NULL | Migration | MEDIUM | Migration phase |

---

## Sources

- `daily_summary.py` — post-jny error capture pattern, post-ii6 60s timeout, HIGH-4 JSONB shape discipline (read directly)
- `content_agent.py` — post-m51 coalesce pattern, cache TTL, SequenceMatcher 0.85 dedup, `run_in_executor` pattern for sync libs (read directly)
- `worker.py` — advisory lock IDs 1005/1010-1018, OPS-02 uniqueness assertion, CronTrigger pattern, reconcile_stale_runs, _validate_env (read directly)
- `summaries.py` — auth pattern via `Depends(get_current_user)` at router level (read directly)
- `App.tsx` — v2.0 redirect routes `/queue` and `/agents/:slug` (read directly)
- `AppShell.tsx` / `AppHeader.tsx` — max-w-[720px] constraint, existing zinc color classes (read directly)
- PRAW official docs (v7.1.4/7.7.1/current) — quarantined subreddit 403 behavior, user-agent requirements, rate limiting
- asyncpraw GitHub / readthedocs — async drop-in replacement, `requestor_kwargs={"timeout": N}` pattern
- APScheduler 3.11.2 docs — CronTrigger `day_of_week='sun'` valid, misfire_grace_time behavior
- TanStack Query v5 docs — optimistic update `onMutate`/`onError`/`onSettled` three-step pattern
- Tailwind CSS v4 migration guide — dark mode strategy change (`@media` default vs class-based), CSS custom property color tokens, `@apply` breakage
- shadcn/ui v4 branch docs — Tabs primitive installation, Radix UI compatibility

---

*Pitfalls research for: v2.1 Three-Tab Content Engine + UI Polish*
*Researched: 2026-05-18*
