# Phase 8: Dashboard Views and Digest — Research

**Researched:** 2026-04-02
**Domain:** React frontend page implementation, FastAPI config endpoints, TanStack Query data-fetching patterns
**Confidence:** HIGH — All decisions are locked in CONTEXT.md, codebase is fully inspectable, stack is established.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

1. **Infographic preview:** Stat cards layout — no chart rendering, no SVG. Section header (INFOGRAPHIC BRIEF label + visual_structure Badge + Copy button), headline, key stats list (bold stat + source link), caption block.
2. **Settings page layout:** Tabbed sections using existing `tabs.tsx` shadcn component. 5 tabs: Watchlists, Keywords, Scoring, Notifications, Agent Runs. SETT-08 quota widget at the bottom/top of Agent Runs tab. SETT-07 schedule config in a 6th tab (Schedule) or within Agent Runs — display + DB write only, note "Changes take effect on next worker restart."
3. **Digest history navigation:** Previous/Next arrow buttons + date in header. On mount fetch `/digests/latest`, decrement/increment date by 1 day. "→" disabled when `currentDate === latestDate`. No date picker.
4. **Content approve flow:** Same `useApprove` hook as Twitter/Instagram. Clipboard text determined by `format_type`: infographic → `caption_text`, long_form → `draft_content.post`, thread → tweets array joined `"\n\n"`. Toast: "Approved — copied to clipboard."

### Claude's Discretion

None specified — all decisions are locked.

### Deferred Ideas (OUT OF SCOPE)

- Dark mode toggle
- Mobile/responsive layout optimization
- Bulk approve/reject across multiple items
- Export/download of agent run logs
- Agents actually reading scoring weights from DB at runtime (Phase 9)
- Scheduler reading schedule intervals from DB to reschedule jobs dynamically (Phase 9)
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DGST-01 | Dashboard page renders today's morning digest cleanly | DigestPage.tsx is a stub; GET /digests/latest and GET /digests/{date} are fully implemented |
| DGST-02 | Shows top 5 stories, queue snapshot, yesterday's summary, priority alert | DailyDigest model has all 4 JSONB fields; render defensively per CONTEXT note |
| DGST-03 | Historical digests viewable | Previous/Next navigation pattern locked; GET /digests/{date} returns 404 for missing dates |
| CREV-01 | Dashboard page for today's content bundle | ContentPage.tsx stub; GET /content/today returns ContentBundleResponse |
| CREV-02 | Full draft displayed with format choice and rationale | draft_content JSONB + format_type + deep_research all present in ContentBundleResponse schema |
| CREV-03 | All sources listed with links | deep_research JSONB — render corroborating sources from this field defensively |
| CREV-04 | Infographic preview when applicable | Stat cards layout locked; draft_content shape documented in CONTEXT.md |
| CREV-05 | Approve to queue for posting | useApprove hook + clipboard logic; DraftItem lookup via GET /queue?platform=content&status=pending |
| SETT-01 | Watchlist management for X | GET/POST/PATCH/DELETE /watchlists all exist; WatchlistCreate/Update/Response schemas confirmed |
| SETT-02 | Watchlist management for Instagram | Same endpoints, filtered by platform=instagram |
| SETT-03 | Keyword management | GET/POST/PATCH/DELETE /keywords all exist; KeywordResponse uses `term` (not `keyword`) field — critical type correction needed |
| SETT-04 | Scoring parameter configuration | GET /config + PATCH /config/{key} are the 2 missing backend endpoints; Config model (key PK, value Text) exists |
| SETT-05 | Agent run log display | GET /agent-runs?days=7&agent_name=X fully implemented; AgentRunResponse schema confirmed |
| SETT-06 | Notification preferences | Same GET /config + PATCH /config/{key} endpoints as SETT-04 |
| SETT-07 | Agent schedule configuration | Same config endpoints; display + DB write only; note about worker restart required |
| SETT-08 | X API quota usage display with visual indicator | GET /config/quota already exists; returns {monthly_tweet_count, quota_safety_margin, monthly_cap, reset_date} |
</phase_requirements>

---

## Summary

Phase 8 is a pure frontend-plus-two-backend-endpoints phase. All 3 pages (DigestPage, ContentPage, SettingsPage) are empty stubs. Every backend endpoint they need is already built and tested — with the exception of `GET /config` and `PATCH /config/{key}`, which require new route handlers in the existing `backend/app/routers/config.py` file alongside the existing `/config/quota` route.

The frontend stack is fully established: React 19, Tailwind v4, shadcn/ui (tabs, badge, button, separator, textarea, dialog), TanStack Query v5, Zustand v5, MSW for testing, Vitest + Testing Library. All component patterns (hooks, mutations, cache invalidation, toast, clipboard) are proven in the approval card and queue page work. This phase follows those same patterns exactly.

The most important correctness detail is a type mismatch between the CONTEXT.md TypeScript interface and the actual backend schema: the keyword field is named `term` in the Pydantic schema and database, not `keyword`. The TypeScript types in `frontend/src/api/types.ts` must use `term`, not `keyword`, for `KeywordCreate` and `KeywordResponse`.

**Primary recommendation:** Wire up the three pages in order of complexity — DigestPage first (read-only display), ContentPage second (read + one mutation), SettingsPage last (multiple tabs + two new backend endpoints). The backend config endpoints can be built in Wave 0 before the frontend tabs that depend on them.

---

## Standard Stack

All libraries are already installed. No new dependencies are needed for this phase.

### Core (in use)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| React | 19.2.4 | UI framework | Established in project |
| TanStack Query | 5.96.0 | Server state, caching, mutations | Established — all queue pages use it |
| Zustand | 5.0.12 | UI-only client state | Established — approval card store pattern |
| Tailwind CSS | 4.2.2 | Utility styling | Established via @tailwindcss/vite plugin |
| shadcn/ui | latest (v4 branch) | Component primitives | Copy-paste components already in /ui/ |
| Sonner | 2.0.7 | Toast notifications | Already wired via `<Toaster />` in layout |
| date-fns | 4.1.0 | Date formatting | Installed, used for timestamps |
| Vitest | 4.1.2 | Frontend unit/component tests | Established; config in vite.config.ts |
| MSW | 2.12.14 | API mocking in tests | Established; handlers.ts + node.ts exist |
| pytest-asyncio | 1.3.0 | Backend async tests | asyncio_mode=auto in pyproject.toml |
| httpx + aiosqlite | installed | Backend test client + in-memory SQLite | Pattern established in test_crud_endpoints.py |

### No New Dependencies

This phase requires no `npm install` or `uv add` calls. All libraries are present.

---

## Architecture Patterns

### Pattern 1: TanStack Query + API module per resource

Every new data fetch follows this structure (established by QueuePage):

1. Create an API module in `frontend/src/api/` (e.g., `digests.ts`, `content.ts`, `settings.ts`)
2. Each module exports typed async functions calling `apiFetch<T>(url)`
3. Page components use `useQuery({ queryKey: [...], queryFn: ... })` directly
4. Mutations use `useMutation({ mutationFn, onSuccess: () => queryClient.invalidateQueries(...) })`

**Query key conventions** (locked in CONTEXT.md):
```typescript
['digest', 'latest']          // GET /digests/latest
['digest', date]              // GET /digests/{date}
['content', 'today']          // GET /content/today
['agentRuns', agentName, days] // GET /agent-runs
['watchlists', platform]      // GET /watchlists?platform=X
['keywords', platform]        // GET /keywords?platform=X
['config']                    // GET /config
['quota']                     // GET /config/quota
```

### Pattern 2: Digest navigation state (local component state, not Zustand)

DigestPage owns its own navigation state. No shared store needed:
```typescript
// Local state within DigestPage
const [currentDate, setCurrentDate] = useState<string | null>(null)
const [latestDate, setLatestDate] = useState<string | null>(null)

// On mount: useQuery(['digest', 'latest']) → set both to digest.digest_date
// Prev: decrement by 1 day, set currentDate, new query fires via key change
// Next: increment by 1 day — disabled when currentDate === latestDate
```

The `date` key in `['digest', date]` drives the query automatically when `currentDate` changes. This is the standard TanStack Query pattern for dependent queries — no imperative `refetch()` calls needed.

### Pattern 3: Config PATCH upsert backend

The `Config` model uses `key` as the primary key (not a UUID). The PATCH handler must upsert:
```python
# backend/app/routers/config.py — new endpoint
@router.patch("/{key}")
async def update_config(key: str, body: ConfigUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Config).where(Config.key == key))
    entry = result.scalar_one_or_none()
    if entry:
        entry.value = body.value
    else:
        entry = Config(key=key, value=body.value)
        db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return {"key": entry.key, "value": entry.value}
```

The `Config.key` column is `String(100)` and is the primary key, not a UUID. The `PATCH /config/{key}` route path parameter is the literal key string (e.g., `content_relevance_weight`), not an ID.

### Pattern 4: ContentPage DraftItem lookup

The ContentPage requires two sequential queries:
1. `GET /content/today` → ContentBundle
2. `GET /queue?platform=content&status=pending` → items array, take `items[0]`

These are independent queries (different query keys), both fetched on mount. The render logic branches on the combination of results:
- No bundle (404): show empty state "No content bundle today"
- Bundle with `no_story_flag=True`: show `EmptyState` variant "No strong story found today" with score
- Bundle found, DraftItem found: show full review UI with Approve/Reject
- Bundle found, no DraftItem: show read-only bundle info with status badge (already actioned)

### Pattern 5: Settings tab mutations with optimistic feedback

Settings mutations follow the pattern: user edits → save button → `useMutation` fires → `onSuccess` invalidates cache → TanStack Query refetches. No optimistic updates needed (these are config values, not time-sensitive). Use `isPending` from the mutation to disable the Save button during in-flight requests.

For watchlist/keyword CRUD: each row has inline edit + delete. Deletion uses `useMutation` with `onSuccess: () => queryClient.invalidateQueries(['watchlists', platform])`.

### Pattern 6: MSW handler extension for new endpoints

The test setup uses MSW with `onUnhandledRequest: 'error'`. Every new endpoint tested in a component test **must** have a handler in `frontend/src/mocks/handlers.ts`. Failing to add handlers causes `beforeAll` errors in all component tests (cascading failures). New handlers to add:
- `GET /digests/latest`
- `GET /digests/:date`
- `GET /content/today`
- `GET /queue?platform=content&status=pending`
- `GET /watchlists`
- `GET /keywords`
- `GET /agent-runs`
- `GET /config`
- `GET /config/quota`
- `PATCH /config/:key`
- `POST /watchlists`, `PATCH /watchlists/:id`, `DELETE /watchlists/:id`
- `POST /keywords`, `PATCH /keywords/:id`, `DELETE /keywords/:id`

### Recommended project structure additions

```
frontend/src/
├── api/
│   ├── digests.ts          # NEW: getLatestDigest, getDigestByDate
│   ├── content.ts          # NEW: getTodayContent
│   └── settings.ts         # NEW: all watchlist/keyword/agentRun/config/quota funcs
├── pages/
│   ├── DigestPage.tsx      # REPLACE stub
│   ├── ContentPage.tsx     # REPLACE stub
│   └── SettingsPage.tsx    # REPLACE stub
└── mocks/
    └── handlers.ts         # EXTEND with all new endpoint handlers

backend/app/routers/
└── config.py               # ADD GET /config and PATCH /config/{key} to existing file
```

### Anti-Patterns to Avoid

- **Using `keyword` instead of `term` for keyword field name:** The Pydantic schema and DB column use `term`. The CONTEXT.md TypeScript type has a discrepancy — use `term` from the backend schema.
- **Importing `Config` model from backend in scheduler:** Scheduler maintains its own model mirrors. Not relevant to this phase (frontend-only changes + one backend file), but do not create a new scheduler model.
- **Calling `create_engine()` sync in new backend code:** All DB access uses `create_async_engine` + `AsyncSession`. The existing config.py router already follows this pattern.
- **Storing server data in Zustand:** TanStack Query owns all API data. Zustand is only for UI-only state (which modal is open, which tab is active, fading card IDs). Do not put digest/content/settings data in the Zustand store.
- **Not adding MSW handlers before component tests:** The setup file uses `onUnhandledRequest: 'error'`. Every new API endpoint exercised in a component test requires a corresponding MSW handler. Add all handlers in Wave 0 before writing component tests.
- **Forgetting `engagement_snapshot` on the content DraftItem:** The content DraftItem's `engagement_snapshot` JSONB holds `{"content_bundle_id": "<uuid>"}`. This links the DraftItem to its ContentBundle. The existing `DraftItemResponse` type uses `unknown` for this field — access it via type assertion when needed.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Progress bar for quota | Custom SVG/canvas bar | Tailwind `w-[{pct}%]` on a div inside a container div | One-liner, no library needed |
| Date formatting | `new Date().toLocaleDateString()` | `date-fns format(parseISO(date), 'EEEE, MMMM d, yyyy')` | Consistent with existing use of date-fns in the project; handles ISO string parsing correctly |
| Clipboard copy | `document.execCommand('copy')` | `navigator.clipboard.writeText(text)` | Already used in ApprovalCard handleApprove; non-blocking async |
| Toast notifications | Custom toast state | `toast.success()` from `sonner` | Already wired to Toaster in layout |
| API fetch boilerplate | `fetch()` + headers + error handling | `apiFetch<T>(url, options?)` from `frontend/src/api/client.ts` | Handles auth header injection and error throws |
| Table sort/filter | Custom sort logic | Simple `Array.sort()` in component or query-param filtering via backend | Agent runs filtered by backend; no client-side sort library needed |

---

## Critical Type Corrections

The CONTEXT.md TypeScript interfaces contain one discrepancy versus the actual backend schema:

**Keyword field name:** CONTEXT.md shows `keyword: string` in `KeywordCreate`. The backend Pydantic schema (`backend/app/schemas/keyword.py`) uses `term: str`. The database column is `term`. The TypeScript type MUST use `term`, not `keyword`.

Correct TypeScript types (confirmed from backend schemas):

```typescript
// Confirmed from backend/app/schemas/keyword.py
export interface KeywordCreate {
  term: string          // NOT keyword — this is the actual backend field name
  platform?: string
  weight?: number
  active?: boolean
}
export interface KeywordResponse {
  id: string
  term: string          // NOT keyword
  platform?: string
  weight?: number
  active: boolean
  created_at: string
  updated_at?: string
}

// Confirmed from backend/app/schemas/watchlist.py
// WatchlistCreate, WatchlistUpdate, WatchlistResponse match CONTEXT.md — no corrections needed

// Confirmed from backend/app/schemas/agent_run.py
// AgentRunResponse matches CONTEXT.md — no corrections needed

// Config model: key is String(100) primary key (not UUID), value is Text
// ConfigEntry matches CONTEXT.md — confirmed correct
```

The `DailyDigestResponse` and `ContentBundleResponse` TypeScript interfaces in CONTEXT.md match the Pydantic schemas exactly.

---

## Common Pitfalls

### Pitfall 1: JSONB fields rendered without null-checks

**What goes wrong:** `digest.top_stories.map(...)` crashes when `top_stories` is null or an unexpected shape. All 4 JSONB fields on DailyDigest (`top_stories`, `queue_snapshot`, `priority_alert`, `yesterday_approved`/`rejected`/`expired`) can be null.

**Why it happens:** The Pydantic schema types all JSONB fields as `Optional[Any]`. The TypeScript type correctly uses `unknown`. But component code that casts to a concrete type without checking first will throw at runtime.

**How to avoid:** Defensive rendering pattern:
```typescript
const stories = Array.isArray(digest.top_stories) ? digest.top_stories : []
const snapshot = digest.queue_snapshot as { twitter?: number; instagram?: number; content?: number } | null
```

**Warning signs:** TypeScript compiler won't catch this — it only manifests at runtime with real or missing data.

### Pitfall 2: 404 from /content/today treated as error instead of empty state

**What goes wrong:** TanStack Query's `isError` state triggers an error display when `GET /content/today` returns 404 (no bundle exists yet). This shows an error UI instead of a graceful "no content today" empty state.

**Why it happens:** `apiFetch` throws on non-2xx responses. TanStack Query catches the throw and sets `isError = true`.

**How to avoid:** Use `throwOnError: false` in the query options, or catch 404 specifically and return `null`:
```typescript
queryFn: async () => {
  try {
    return await getTodayContent()
  } catch (e: unknown) {
    if (e instanceof Error && e.message.includes('404')) return null
    throw e
  }
}
```
Then check `data === null` to show the empty state. Same pattern needed for `GET /digests/latest` when no digests exist yet.

### Pitfall 3: Config save overwrites all keys instead of one

**What goes wrong:** A "Save" button in the Scoring tab calls `PATCH /config/{key}` once per field in the form. If the form has 4 fields and the user only changed 1, all 4 fire separate PATCH requests — not wrong, but potentially confusing if one fails partway through.

**Why it happens:** The `PATCH /config/{key}` endpoint is per-key. There is no batch endpoint.

**How to avoid:** Track `dirtyFields` in local form state. On save, only PATCH keys whose values differ from the originally fetched config. This is the correct approach — it also avoids needlessly touching config keys the user didn't change.

### Pitfall 4: Date navigation with date-fns parseISO vs new Date()

**What goes wrong:** `digest_date` from the API is `"YYYY-MM-DD"` (a date string, not ISO datetime). `new Date("2026-04-02")` interprets this as UTC midnight, which can render as the previous day in the operator's local timezone.

**Why it happens:** JavaScript `Date` constructor treats date-only strings as UTC. If the user is west of UTC, `new Date("2026-04-02")` displayed as local time shows April 1.

**How to avoid:** Use `date-fns/parseISO` which preserves the date, or add the time component: `new Date("2026-04-02T00:00:00")` to force local time interpretation. Better: format the string directly without creating a Date object when just displaying "April 2, 2026":
```typescript
import { parse, format } from 'date-fns'
const displayDate = format(parse(digestDate, 'yyyy-MM-dd', new Date()), 'EEEE, MMMM d, yyyy')
```

### Pitfall 5: Config key primary key vs UUID route pattern

**What goes wrong:** Copying the watchlist/keyword router pattern for `PATCH /config/{key}` and using `UUID` type annotation for the path parameter. Config keys are string slugs (`content_relevance_weight`), not UUIDs.

**Why it happens:** All other PATCH endpoints in the project use `UUID` path parameters. Config is the exception — its primary key is a `String(100)`.

**How to avoid:** The `PATCH /config/{key}` route parameter is `key: str`, not `key: UUID`. The router implementation must use `String` comparison, not UUID casting.

---

## Code Examples

Verified from codebase inspection:

### Existing apiFetch client pattern (confirmed from frontend/src/api/client.ts usage)
```typescript
// New api modules follow this exact shape used by queue.ts
import { apiFetch } from './client'
import type { DailyDigestResponse } from './types'

export async function getLatestDigest(): Promise<DailyDigestResponse> {
  return apiFetch<DailyDigestResponse>('/digests/latest')
}

export async function getDigestByDate(date: string): Promise<DailyDigestResponse> {
  return apiFetch<DailyDigestResponse>(`/digests/${date}`)
}
```

### Config upsert backend pattern (new, follows existing router style)
```python
# backend/app/routers/config.py — add alongside existing /quota route
from sqlalchemy.dialects.postgresql import insert as pg_insert

class ConfigUpdate(BaseModel):
    value: str

@router.get("")
async def list_config(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Config))
    return [{"key": r.key, "value": r.value} for r in result.scalars().all()]

@router.patch("/{key}")
async def update_config(key: str, body: ConfigUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Config).where(Config.key == key))
    entry = result.scalar_one_or_none()
    if entry:
        entry.value = body.value
    else:
        entry = Config(key=key, value=body.value)
        db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return {"key": entry.key, "value": entry.value}
```

### Quota progress bar (Tailwind, no library)
```tsx
// Example: 3,400 / 10,000 = 34% usage
const pct = Math.min(100, Math.round((quota.monthly_tweet_count / quota.monthly_cap) * 100))
const barColor = pct >= 80 ? 'bg-red-500' : pct >= 60 ? 'bg-yellow-500' : 'bg-green-500'

<div className="w-full bg-gray-100 rounded-full h-2">
  <div className={`${barColor} h-2 rounded-full transition-all`} style={{ width: `${pct}%` }} />
</div>
<p className="text-xs text-muted-foreground mt-1">
  {quota.monthly_tweet_count.toLocaleString()} / {quota.monthly_cap.toLocaleString()} reads used
  {quota.reset_date && ` — resets ${quota.reset_date}`}
</p>
```

### Content approve clipboard logic (format_type branching)
```typescript
function getClipboardText(bundle: ContentBundleResponse): string {
  const draft = bundle.draft_content as Record<string, unknown> | null
  if (!draft) return ''
  switch (bundle.format_type) {
    case 'infographic':
      return (draft.caption_text as string) ?? ''
    case 'long_form':
      return (draft.post as string) ?? ''
    case 'thread': {
      const tweets = draft.tweets as string[] ?? []
      return tweets.join('\n\n')
    }
    default:
      return JSON.stringify(draft)
  }
}
```

### Infographic stat cards render
```tsx
// draft_content shape for infographic (from CONTEXT.md)
interface InfographicDraft {
  format: 'infographic'
  headline: string
  key_stats: Array<{ stat: string; source: string; source_url: string }>
  visual_structure: string
  caption_text: string
}

function InfographicPreview({ draft }: { draft: InfographicDraft }) {
  return (
    <div className="space-y-3 border rounded-lg p-4">
      <div className="flex items-center gap-2">
        <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Infographic Brief
        </span>
        <Badge variant="outline">{draft.visual_structure}</Badge>
        <Button size="sm" variant="ghost" onClick={() => navigator.clipboard.writeText(draft.caption_text)}>
          Copy caption
        </Button>
      </div>
      <p className="font-semibold">{draft.headline}</p>
      <ul className="space-y-2">
        {draft.key_stats.map((s, i) => (
          <li key={i} className="text-sm">
            <span className="font-medium">{s.stat}</span>
            <a href={s.source_url} target="_blank" rel="noopener noreferrer"
               className="block text-xs text-muted-foreground hover:underline">
              {s.source}
            </a>
          </li>
        ))}
      </ul>
      <p className="text-sm text-muted-foreground">{draft.caption_text}</p>
    </div>
  )
}
```

---

## Environment Availability

Step 2.6: SKIPPED — Phase 8 has no new external dependencies. All required tools (Node, Python, uv, pytest, vitest) are already in use by the project. No new services, CLIs, or runtimes are introduced.

---

## Runtime State Inventory

Step 2.5: SKIPPED — Phase 8 is not a rename/refactor/migration phase. No stored data, registered state, or build artifacts need updating.

---

## Validation Architecture

`workflow.nyquist_validation` is `true` in `.planning/config.json`. This section is required.

### Test Framework

| Property | Value |
|----------|-------|
| Backend framework | pytest + pytest-asyncio 1.3.0; asyncio_mode=auto |
| Backend config | `[tool.pytest.ini_options]` in `backend/pyproject.toml` |
| Backend quick run | `cd backend && uv run pytest tests/test_crud_endpoints.py -x -q` |
| Backend full suite | `cd backend && uv run pytest -x -q` |
| Frontend framework | Vitest 4.1.2 + Testing Library 16.3.2 + MSW 2.12.14 |
| Frontend config | `test` block in `frontend/vite.config.ts` |
| Frontend quick run | `cd frontend && npm run test -- --run` |
| Frontend full suite | `cd frontend && npm run test -- --run` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DGST-01 | DigestPage renders today's digest with all fields | component | `npm run test -- --run DigestPage` | Wave 0 |
| DGST-02 | Shows top_stories list, queue_snapshot cards, yesterday summary, priority_alert banner | component | `npm run test -- --run DigestPage` | Wave 0 |
| DGST-03 | Prev/Next navigation fetches adjacent dates; → disabled at latest; 404 shows "no digest" | component | `npm run test -- --run DigestPage` | Wave 0 |
| CREV-01 | ContentPage renders today's bundle; shows empty state on 404 | component | `npm run test -- --run ContentPage` | Wave 0 |
| CREV-02 | Draft content and format_type rendered correctly per format | component | `npm run test -- --run ContentPage` | Wave 0 |
| CREV-03 | deep_research sources listed with links | component | `npm run test -- --run ContentPage` | Wave 0 |
| CREV-04 | Infographic stat cards rendered when format_type=infographic | component | `npm run test -- --run ContentPage` | Wave 0 |
| CREV-05 | Approve calls useApprove; clipboard gets correct text per format_type | component | `npm run test -- --run ContentPage` | Wave 0 |
| SETT-01 | Watchlist tab shows X entries; add/edit/delete work | component | `npm run test -- --run SettingsPage` | Wave 0 |
| SETT-02 | Watchlist tab filters by platform=instagram | component | `npm run test -- --run SettingsPage` | Wave 0 |
| SETT-03 | Keywords tab shows term/platform/weight/active; CRUD works | component | `npm run test -- --run SettingsPage` | Wave 0 |
| SETT-04 | Scoring tab loads config keys, save PATCHes only dirty fields | component | `npm run test -- --run SettingsPage` | Wave 0 |
| SETT-05 | Agent Runs tab shows last 7 days; agent filter dropdown works | component | `npm run test -- --run SettingsPage` | Wave 0 |
| SETT-06 | Notifications tab edits whatsapp config keys and saves | component | `npm run test -- --run SettingsPage` | Wave 0 |
| SETT-07 | Schedule tab shows editable intervals; save note displayed | component | `npm run test -- --run SettingsPage` | Wave 0 |
| SETT-08 | Quota widget shows progress bar with correct percentage | component | `npm run test -- --run SettingsPage` | Wave 0 |
| SETT-04 (backend) | GET /config returns all config rows | integration | `cd backend && uv run pytest tests/test_crud_endpoints.py::test_list_config -x` | Wave 0 |
| SETT-04 (backend) | PATCH /config/{key} upserts correctly; returns {key, value} | integration | `cd backend && uv run pytest tests/test_crud_endpoints.py::test_patch_config -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `cd backend && uv run pytest -x -q` + `cd frontend && npm run test -- --run`
- **Per wave merge:** Full suite in both backend and frontend
- **Phase gate:** Both suites green before `/gsd:verify-work`

### Wave 0 Gaps

Backend:
- [ ] `backend/tests/test_crud_endpoints.py` — add `_Config` SQLite model and `test_list_config`, `test_patch_config_update`, `test_patch_config_create` test functions (the `_TestBase` SQLite infrastructure already exists in this file)

Frontend:
- [ ] `frontend/src/pages/DigestPage.test.tsx` — component tests for DGST-01, DGST-02, DGST-03
- [ ] `frontend/src/pages/ContentPage.test.tsx` — component tests for CREV-01 through CREV-05
- [ ] `frontend/src/pages/SettingsPage.test.tsx` — component tests for SETT-01 through SETT-08
- [ ] `frontend/src/mocks/handlers.ts` — extend with all new endpoint handlers (15 new routes listed in Pattern 6 above) **before any component test is written**

No new framework installs required — Vitest, MSW, and Testing Library are already configured and working (ApprovalCard.test.tsx passes).

---

## Sources

### Primary (HIGH confidence)

All findings are based on direct inspection of the project codebase:

- `backend/app/routers/config.py` — confirmed existing `/config/quota` route; Config model structure
- `backend/app/models/config.py` — confirmed `key` is String(100) PK, `value` is Text
- `backend/app/routers/digests.py` — confirmed GET /digests/latest and GET /digests/{date}
- `backend/app/routers/content.py` — confirmed GET /content/today
- `backend/app/routers/agent_runs.py` — confirmed GET /agent-runs with agent_name + days params
- `backend/app/routers/watchlists.py` — confirmed full CRUD pattern
- `backend/app/routers/keywords.py` — confirmed full CRUD pattern; `term` field name verified
- `backend/app/schemas/keyword.py` — **confirmed `term` (not `keyword`)** — critical correction to CONTEXT.md type
- `backend/app/schemas/watchlist.py` — confirmed field names match CONTEXT.md
- `backend/app/schemas/agent_run.py` — confirmed field names match CONTEXT.md
- `backend/app/schemas/daily_digest.py` — confirmed Optional[Any] for all JSONB fields
- `backend/app/schemas/content_bundle.py` — confirmed ContentBundleResponse field names
- `backend/tests/test_crud_endpoints.py` — confirmed SQLite _TestBase pattern for new config tests
- `frontend/src/api/types.ts` — confirmed existing types; identifies where new types slot in
- `frontend/src/api/queue.ts` — confirmed `apiFetch` usage pattern
- `frontend/src/hooks/useApprove.ts` — confirmed mutation + cache invalidation pattern
- `frontend/src/components/approval/ApprovalCard.tsx` — confirmed approve flow and clipboard pattern
- `frontend/src/components/approval/ApprovalCard.test.tsx` — confirmed Vitest + MSW + QueryClientProvider wrapper pattern
- `frontend/src/mocks/handlers.ts` — confirmed MSW handler structure; identified gaps for new endpoints
- `frontend/src/test/setup.ts` — confirmed `onUnhandledRequest: 'error'` (critical for Wave 0)
- `frontend/vite.config.ts` — confirmed Vitest config: jsdom, globals, setupFiles
- `frontend/package.json` — confirmed all dependencies present; no new installs needed
- `.planning/config.json` — confirmed `nyquist_validation: true`

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries verified from package.json
- Architecture: HIGH — patterns confirmed from existing working code
- Pitfalls: HIGH — identified from schema inspection (term vs keyword) and known JavaScript date behavior
- Test strategy: HIGH — existing test infrastructure fully inspected and understood

**Research date:** 2026-04-02
**Valid until:** 2026-05-02 (stable stack; no fast-moving dependencies)
