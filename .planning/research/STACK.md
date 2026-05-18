# Research: STACK additions for v2.1 Three-Tab Content Engine + UI Polish

**Project:** Seva Mining v2.1 Three-Tab Content Engine + UI Polish
**Mode:** Ecosystem — Stack additions only
**Confidence:** HIGH (all versions verified against PyPI/npm directly or via official docs)
**Generated:** 2026-05-18

## Stack Additions — Verdict Table

| Package | Verdict | Where it goes | Reason |
|---------|---------|--------------|--------|
| `asyncpraw ~7.8` | ADD | scheduler `pyproject.toml` | Reddit ingestion for weekly_sweeper; async-native, officially maintained |
| `shadcn Tabs` | ADD (copy-paste) | frontend, `npx shadcn@latest add tabs` | Top-level tab navigation; already on Tailwind v4 branch |
| `@dnd-kit/core ^6.3` + `@dnd-kit/sortable ^10.0` | SKIP — use date dropdown | frontend | DnD on a weekly calendar grid is significantly more complex than it looks; single-user tool does not justify the implementation cost |
| `@fontsource-variable/inter` | SKIP | frontend | Current font is Geist Variable (`@fontsource-variable/geist` already in `index.css`); switching to Inter requires a CSS variable replacement; not worth it unless design explicitly demands Inter |
| Any markdown editor library | SKIP | frontend | Plain `<textarea>` + `react-markdown` render on save is sufficient; existing `react-markdown ^10.1.0` + `rehype-sanitize ^6.0.0` already covers read rendering |
| `difflib.SequenceMatcher` | SKIP | scheduler | Python stdlib; already imported in `content_agent.py` line 31 |
| Any posting library (tweepy write, instagram-private-api, etc.) | SKIP | — | Phase B stays dormant |
| Any analytics SDK | SKIP | — | Out of scope |
| Any new auth library | SKIP | — | Single-user bcrypt+JWT stays |
| APScheduler 4.0 | SKIP | — | Prohibited in CLAUDE.md "What NOT to Use" |

## Backend: Reddit Ingestion

### asyncpraw vs praw — Recommendation: asyncpraw

**VERDICT: ADD `asyncpraw>=7.8.1` to `scheduler/pyproject.toml`**

The weekly_sweeper runs inside `AsyncIOScheduler` on the asyncio event loop. Plain `praw` is sync-only — calling it directly in an async job blocks the event loop (same reason `requests` is banned per CLAUDE.md). Two options:

1. `asyncpraw` — async-native, official sister package, same `praw-dev` GitHub org, same API surface with `await` added. Version 7.8.1, released 2024-12-21, Production/Stable classification, Python 3.8+. Uses `aiohttp` internally.
2. `praw` 7.8.1 via `asyncio.to_thread()` — works but is an explicit workaround for what asyncpraw solves by design. Adding `asyncio.to_thread` calls throughout the sweeper module adds noise with no benefit.

The PRAW docs explicitly state: "If you plan on using PRAW in an asynchronous environment, it is strongly recommended to use Async PRAW." No stability concerns — asyncpraw 7.8.1 is production-stable and tracks praw releases in lockstep.

**asyncpraw is the right choice.** praw is not needed alongside it (asyncpraw is a drop-in replacement, not a companion package).

Sources: [asyncpraw PyPI](https://pypi.org/project/asyncpraw/) | [asyncpraw docs](https://asyncpraw.readthedocs.io/en/stable/) | [praw docs — async recommendation](https://praw.readthedocs.io/en/stable/)

**Confidence: HIGH**

### Reddit API Auth — confirmed

Read-only public access (subreddit posts) uses the "script" app type with OAuth client credentials. No Reddit account login is required — only `client_id` + `client_secret` + `user_agent`. The user creates an app at `https://www.reddit.com/prefs/apps` (same one-time setup pattern as SerpAPI/Twilio).

asyncpraw init pattern (read-only):
```python
reddit = asyncpraw.Reddit(
    client_id=settings.reddit_client_id,
    client_secret=settings.reddit_client_secret,
    user_agent=settings.reddit_user_agent,  # e.g. "script:seva-mining-sweeper:v1.0 (by u/<username>)"
)
```

**New env vars:** `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USER_AGENT` (3 new Railway secrets, consistent with existing pattern).

Sources: [asyncpraw Quick Start](https://asyncpraw.readthedocs.io/en/stable/getting_started/quick_start.html) | [Reddit OAuth2 wiki](https://github.com/reddit-archive/reddit/wiki/oauth2)

**Confidence: HIGH**

### Rate Limits

Reddit API allows 100 requests per minute for OAuth-authenticated access (the most cited figure across official docs; also reported as 60 req/min in some secondary sources — treat 60 as the conservative floor). asyncpraw respects `X-Ratelimit-*` response headers automatically and waits when under its `ratelimit_seconds` threshold (default: 5 seconds). For the weekly_sweeper: fetching `hot(limit=25)` from 5 subreddits = 5–10 API calls total, once per week. Rate limits are a non-issue at this frequency.

Sources: [PRAW ratelimits docs](https://praw.readthedocs.io/en/stable/getting_started/ratelimits.html)

**Confidence: HIGH**

### Advisory Lock for weekly_sweeper

Currently used: 1005, 1010–1018. Next free: **1019**. Assign `"weekly_sweeper": 1019` in `JOB_LOCK_IDS`. The OPS-02 uniqueness assertion in `worker.py` will catch any future collision at import time.

**Confidence: HIGH** (direct grep of worker.py)

## Frontend: Tabs

### shadcn Tabs — ADD

**VERDICT: ADD via `npx shadcn@latest add tabs`**

The shadcn `Tabs` primitive is built on Radix UI's Tabs, is included in the Tailwind v4 branch, and is React 19 compatible (shadcn CLI confirmed: "all components are updated for Tailwind v4 and React 19"). It copies a `tabs.tsx` file into your components directory — no new npm dependency.

Install: `npx shadcn@latest add tabs`

This gives `<Tabs>`, `<TabsList>`, `<TabsTrigger>`, `<TabsContent>` — the exact primitives needed for the top-level 3-tab layout in `App.tsx`.

Sources: [shadcn/ui Tailwind v4 docs](https://ui.shadcn.com/docs/tailwind-v4) | [shadcn Tabs component](https://ui.shadcn.com/docs/components/radix/tabs)

**Confidence: HIGH**

## Frontend: Calendar Drag-and-Drop — SKIP @dnd-kit, use date dropdown

**VERDICT: SKIP `@dnd-kit/core`. Use a date-dropdown edit approach in the item edit dialog.**

The honest assessment of DnD on a weekly calendar grid:

`@dnd-kit/core` 6.3.1 (peer deps: React >=16.8.0, compatible with React 19) is the correct modern choice if DnD is needed — 6KB core, accessible, actively maintained (2.8M weekly downloads), react-beautiful-dnd is deprecated and must not be used. `@dnd-kit/sortable` 10.0.0 also available.

However, DnD on a _calendar grid_ is a different problem from DnD on a list. A weekly grid has 7 drop targets (days), each is a `useDroppable` zone, and dragged items must snap to a new day column. The implementation requires: custom collision detection, drop zone highlight states, visual feedback on the dragged card, and optimistic mutation of the `calendar_items.day` field through TanStack Query's mutation pipeline. None of this is provided by a preset — it's all custom code.

For a single-user planning tool where the primary need is "move this item to Tuesday," a date dropdown in the edit dialog achieves the same outcome in 20 lines: `<select>` of day names → `PATCH /calendar-items/{id}` → TanStack Query `invalidateQueries`. The UX is slightly less slick but entirely adequate for an internal tool.

**Recommendation:** date-dropdown in the edit dialog. If the drag-and-drop feel proves frustrating in actual use, adding `@dnd-kit` as a v2.2 enhancement is low-risk given its React compatibility.

**Confidence: HIGH (technical assessment); MEDIUM (UX judgment)**

## Frontend: Typography — No New Font Library Needed

**VERDICT: SKIP `@fontsource-variable/inter` or `@fontsource/inter`.**

The current font stack is **Geist Variable** (`@fontsource-variable/geist` is in `package.json` at `^5.2.8` and imported in `index.css` as `'Geist Variable'`). The v2.1 spec says "refined Inter typography at varied weights (400/500/600/700)" — but Geist Variable is a variable font that already supports all those weights via `font-weight`. Switching to Inter requires changing the `@import`, the `--font-sans` CSS variable, and removing the Geist import. This is a one-line CSS change if desired, not a research question.

Decision for roadmap: Either keep Geist (it reads at the same quality level as Inter for a dense data UI), or swap to Inter by replacing the `@fontsource-variable/geist` import with `@fontsource-variable/inter` and updating `--font-sans`. Both packages are the same size, same Fontsource organization, same install pattern. No new npm category required — it's a package swap, not a new dependency.

**Confidence: HIGH (direct file read)**

## Story Virality Compute — No New Library

**VERDICT: SKIP any new dedup/similarity library.**

`difflib.SequenceMatcher` is Python stdlib and is **already imported in `content_agent.py` line 31** (`import difflib`). The existing `deduplicate_stories()` function uses it with the 0.85 ratio threshold. The weekly_sweeper's story virality compute (count cross-references across feeds over 7 days) can reuse this exact function directly — it already takes `stories: list[dict]` with `link` and `title` keys.

**Confidence: HIGH (direct code read)**

## Markdown Editing for Calendar Notes — No New Library

**VERDICT: SKIP markdown editor libraries (`@uiw/react-md-editor`, `react-mde`, etc.).**

Calendar item notes are optional and low-frequency (personal planning surface, single user). A plain `<textarea>` in the edit dialog is sufficient for input. On save, the note string is stored as-is. On display in the weekly grid, the existing `react-markdown ^10.1.0` renders it. This is the same pattern used elsewhere in the app and requires zero new packages.

**Confidence: HIGH**

## Sonnet Call Pattern for Weekly Sweeper

The new "3 content angles" call in the weekly_sweeper should mirror `daily_summary.py` exactly:

- Model: `SONNET_MODEL = "claude-sonnet-4-6"` (line 56)
- Timeout: `AsyncAnthropic(api_key=..., timeout=60.0)` (line 504 pattern)
- Max tokens: Start at 800–1000 (3 short angle suggestions, less than the 1500-token bull-thesis brief). No new anthropic SDK version needed — `anthropic>=0.86.0` already in both `pyproject.toml` files.

**Confidence: HIGH (direct code read)**

## Migration Pattern for v2.1 Tables

Two new tables: `calendar_items`, `weekly_sweeps`. Follow `0010_add_daily_summaries.py` exactly:

- Hand-written only (no `--autogenerate`, per MOD-2 pitfall in that migration's docstring)
- `op.create_table` + `op.create_index` only
- `gen_random_uuid()` server default for UUID PKs
- `postgresql.JSONB` for any JSON fields (e.g., `weekly_sweeps.content_angles_json`, `weekly_sweeps.raw_reddit_posts_json`)
- Revision IDs: `0011_add_calendar_items.py`, `0012_add_weekly_sweeps.py` (chain sequentially)

**Confidence: HIGH**

## "What NOT to Add" Confirmation

All existing CLAUDE.md prohibitions apply unchanged to v2.1:

| Banned | Status in v2.1 |
|--------|---------------|
| APScheduler 4.0 alpha | Not added — 3.11.2 stays |
| SQLAlchemy 1.x patterns | Not added — 2.0 async only |
| `requests` in async routes | Not added — httpx stays |
| Pydantic v1 patterns | Not added — v2 only |
| Celery | Not added |
| `create_engine()` sync | Not added |
| Autoposting libraries | Not added — Phase B dormant |
| Analytics SDKs | Not added |
| New auth libraries | Not added |

**Confidence: HIGH**

## Complete Change Summary for Roadmap

**scheduler/pyproject.toml — ADD one line:**
```
"asyncpraw>=7.8.1",
```

**frontend — ADD via CLI (no npm install, copy-paste only):**
```bash
npx shadcn@latest add tabs
```

**New Railway env vars (3):**
```
REDDIT_CLIENT_ID
REDDIT_CLIENT_SECRET
REDDIT_USER_AGENT
```

**New advisory lock ID:**
```
"weekly_sweeper": 1019
```

**No other stack changes. Everything else the existing stack already covers.**

## Open Questions

None that block the roadmap. The one judgment call (DnD vs date-dropdown) has been resolved in favor of the dropdown. If the user ever wants to revisit DnD, `@dnd-kit/core ^6.3` + `@dnd-kit/sortable ^10.0` are the packages — both React 19 compatible, both verified.
