# Research: Phase B — approve-then-auto-post to X

**Researched:** 2026-04-24
**Domain:** FastAPI mutation endpoint + tweepy v2 async OAuth1 posting + Postgres row lock + React modal UX
**Confidence:** HIGH (codebase paths verified by direct read; tweepy + X API surfaces verified by official docs)

## Summary

The codebase is in better shape for this task than CONTEXT.md guessed. Backend FastAPI is well-organized (`routers/` + `services/` + `models/` + `schemas/`), there is a clean JWT dependency (`get_current_user` in `app/dependencies.py`) already applied as a router-level `dependencies=[Depends(get_current_user)]` on every other auth-gated router, the dialog primitive is already available in shadcn (`components/ui/dialog.tsx`), and there is an established TanStack Query mutation pattern (`useApprove.ts`).

Three structural facts the planner MUST internalize before writing tasks:

1. **`approve` already exists.** `PATCH /items/{id}/approve` is the existing "approve & copy to clipboard" endpoint (`backend/app/routers/queue.py:139`). It transitions `draft_items.status: pending → approved`. Phase B's new endpoint must NOT collide. Recommended path: `POST /items/{item_id}/post-to-x` (or `POST /items/{item_id}/approve-and-post`). Phase B introduces a NEW column `approval_state` orthogonal to existing `status` — both stay.
2. **The text to post lives on `content_bundles.draft_content`, not `draft_items`.** `draft_items.draft_content` does NOT exist. The link is `draft_items.engagement_snapshot["content_bundle_id"]` → `content_bundles.id` → `content_bundles.draft_content` (JSONB). The poster must fetch the bundle. For thread, the field is `draft_content.tweets` (list of strings) NOT `thread_tweets`. For breaking_news it is `draft_content.tweet` (single string). CONTEXT.md D7's pseudocode used `thread_tweets` — the actual key is `tweets`.
3. **`tweepy` is in scheduler but NOT backend.** `scheduler/pyproject.toml:11` has `tweepy[async]>=4.14`; `backend/pyproject.toml` does NOT. The plan MUST add tweepy to `backend/pyproject.toml` (and `uv lock` in backend).

**Primary recommendation:** Build `backend/app/services/x_poster.py` (a thin wrapper around `tweepy.asynchronous.AsyncClient`), register a new `backend/app/routers/post_to_x.py` router with one `POST /items/{item_id}/post-to-x` endpoint guarded by `Depends(get_current_user)`, write a single forward-only Alembic migration `0009_*.py` adding 5 columns to `draft_items`, and add a confirm-modal + post-mutation hook to the frontend. Keep the existing approve-and-copy flow untouched; users can still use it for non-Phase-B content types.

---

## Backend structure + conventions

**Layout (verified by `ls`):**
```
backend/
├── alembic/
│   ├── env.py              # imports app.models — adds new columns auto-detected
│   ├── versions/0001..0008 # numeric prefix N_slug.py convention
│   └── ...
├── alembic.ini             # file_template set but team uses plain N_slug.py manually
├── app/
│   ├── main.py             # FastAPI app + 9 include_router() calls
│   ├── auth.py             # bcrypt + JWT (HS256, 7-day expiry)
│   ├── config.py           # pydantic-settings Settings — single source of env vars
│   ├── database.py         # async engine + AsyncSessionLocal + get_db dependency
│   ├── dependencies.py     # get_current_user (JWT bearer)
│   ├── models/             # 9 SQLAlchemy models, all registered in __init__.py
│   ├── routers/            # 9 routers, file-per-resource convention
│   ├── schemas/            # pydantic v2 request/response models
│   └── services/           # currently only whatsapp.py — x_poster.py belongs here
├── pyproject.toml          # MISSING tweepy — must add
└── tests/conftest.py       # SQLite in-memory + dependency_overrides[get_db]
```

**Router registration pattern (`backend/app/main.py:8-16, 51-59`):**
```python
from app.routers.queue import router as queue_router
# ...
app.include_router(queue_router)  # no extra prefix; router defines own prefix
```

**Auth-gated router pattern (`backend/app/routers/content_bundles.py:27-31`):**
```python
router = APIRouter(
    prefix="/content-bundles",
    tags=["content-bundles"],
    dependencies=[Depends(get_current_user)],
)
```
The same `dependencies=[Depends(get_current_user)]` line is used by `queue.py`, `watchlists.py`, `keywords.py`, `agent_runs.py`, `digests.py`, `content.py`, `config.py`, `content_bundles.py`. The `auth.py` router is the only public one. Phase B's new router follows this exact pattern.

**DB session pattern (`backend/app/database.py:46-49`):**
```python
async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
```
Used as `db: AsyncSession = Depends(get_db)` in route signatures. Session lifecycle: per-request, auto-closed.

**Existing approve endpoint (`backend/app/routers/queue.py:139-167`)** transitions `status: pending → approved/edited_approved` with state-machine enforcement via `_enforce_transition()`. It does NOT touch any X API. The new Phase B endpoint runs in PARALLEL — ignores `status` entirely, manipulates the new `approval_state` column instead.

**File-per-resource convention is firm.** New router → new file `backend/app/routers/post_to_x.py` (or `posts.py`); new service → `backend/app/services/x_poster.py`; new schema → `backend/app/schemas/post_to_x.py` (or merge into existing `draft_item.py`).

---

## draft_items + content_bundles schema

### `draft_items` — current columns (`backend/app/models/draft_item.py:27-65`)

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | gen_random_uuid via `default=uuid.uuid4` |
| `platform` | String(20) NOT NULL | currently always `"content"` |
| **`status`** | **`draftstatus` ENUM NOT NULL** default `pending` | **EXISTING — DO NOT TOUCH.** Values: `pending`, `approved`, `edited_approved`, `rejected`, `expired`. Owns the dashboard approval state machine. |
| `source_url` / `source_text` / `source_account` | Text/String | story metadata |
| `follower_count` | Numeric(12,0) | |
| `score` / `quality_score` | Numeric(5,2) | |
| `alternatives` | JSONB NOT NULL default `[]` | per-draft variants — first element is the canonical text; structure: `[{"text": "...", "type": "thread", "label": "Draft A"}, ...]` |
| `rationale` | Text | |
| `urgency` | String(20) | |
| `related_id` | UUID FK self | |
| `rejection_reason` | Text | JSON-serialized `{"category": ..., "notes": ...}` |
| `edit_delta` | Text | original first alternative when user inline-edits |
| `expires_at` / `decided_at` / `created_at` / `updated_at` | TIMESTAMPTZ | |
| `event_mode` | String(20) | |
| `engagement_snapshot` | JSONB | **CRITICAL: contains `{"content_bundle_id": "<uuid string>"}` — the link to the bundle that holds the post text.** |
| `engagement_alert_level` / `alerted_expiry_at` | String(20) / TIMESTAMPTZ | Senior-agent legacy |

**Indexes:** `status`, `platform`, `created_at`, `expires_at`.

**No `draft_content` column on draft_items.** This is the most important schema fact for the planner. The post text MUST be fetched from the linked content_bundle.

**No collision risk.** `approval_state`, `posted_tweet_id`, `posted_tweet_ids`, `posted_at`, `post_error` — none of these names are used. The existing `status` column is enum `draftstatus` and serves the dashboard approve/reject lifecycle. Phase B's `approval_state` is a separate, orthogonal column that tracks the post-to-X result.

**Schema parity gotcha.** `backend/app/models/draft_item.py` and `scheduler/models/draft_item.py` MUST be edited identically (the scheduler uses bare `from models.base import Base` while backend uses `from app.models.base import Base`). The codebase keeps them in lockstep. Migration runs from `backend/` only — alembic env imports `app.models`.

### `content_bundles` — current columns (`backend/app/models/content_bundle.py:10-29`)

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `story_headline` | Text NOT NULL | |
| `story_url` | Text | |
| `source_name` | String(255) | |
| `content_type` | String(50) | values: `breaking_news`, `thread`, `quote`, `infographic`, `gold_media`, `gold_history` |
| `score` / `quality_score` | Numeric(5,2) | |
| `no_story_flag` | Boolean | |
| `deep_research` | JSONB | |
| **`draft_content`** | **JSONB** | **THE POST TEXT LIVES HERE.** Format-specific shape. |
| `compliance_passed` | Boolean | |
| `rendered_images` | JSONB | media (Phase 11) |
| `created_at` | TIMESTAMPTZ | |

**`draft_content` JSON shapes (verified):**

| content_type | Phase B scope? | `draft_content` shape | Text-extraction path |
|--------------|----------------|------------------------|----------------------|
| `breaking_news` | ✓ ships in B | `{"format": "breaking_news", "tweet": "...", "infographic_brief": {...}, "_rationale": "...", "_key_data_points": [...]}` (`scheduler/agents/content/breaking_news.py:102-130`) | `draft_content["tweet"]` |
| `thread` | ✓ ships in B | `{"format": "thread", "tweets": ["t1", "t2", ...], "long_form_post": "..."}` (`scheduler/agents/content/threads.py:88-93`) | `draft_content["tweets"]` (list) |
| `quote` | deferred B.5 | (different shape, three-field text) | TBD in B.5 |
| `gold_history` | deferred B.5 | `{"tweets": [...], ...}` (`scheduler/agents/content/gold_history.py:197`) | `draft_content["tweets"]` |
| `gold_media` / `infographic` | deferred B+ | media-bearing | requires `media_upload` |

**Critical naming correction vs CONTEXT.md.** D7's pseudocode iterates `thread_tweets`. The actual JSONB key is `tweets`. The frontend `ThreadPreview.tsx:13` reads `d.tweets`. The post-to-X handler MUST read `draft_content["tweets"]`.

### Why `draft_items` (not `content_bundles`) is correct for `approval_state`

CONTEXT.md D6 leans `draft_items`. Confirmed correct. Reasons surfaced from codebase:
- One bundle can have multiple draft variants (`alternatives` array on draft_items). Per-bundle approval would lose this granularity.
- The dashboard already keys card-level state machine on `draft_items.status`. `approval_state` joins `status` on the same row — natural locality for the UI.
- All existing approve/reject mutations target `/items/{item_id}/...` — Phase B's endpoint follows that prefix.

---

## Alembic state + migration naming

**Current head:** `0008` — `0008_rename_video_clip_to_gold_media.py`. New revision: **`0009`**.

**Filename convention (verified by `ls backend/alembic/versions/`):** `NNNN_<snake_case_slug>.py` — purely numeric prefix, NOT the date-based template in `alembic.ini`. The `file_template` in `alembic.ini` is unused; the team manually names new files. Recommended filename: `0009_add_x_post_state_to_draft_items.py`.

**Inside the file:**
```python
revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None
```
(Pattern from `0008_rename_video_clip_to_gold_media.py:11-14`.)

**Migration generation flow.** `backend/alembic/env.py:9-22` imports `app.models` so all models are registered with `Base.metadata`. Adding new columns to `app/models/draft_item.py` and running `alembic revision --autogenerate -m "..." --rev-id 0009` will produce the diff. **Recommendation: write the migration by hand (not autogenerate).** Reason: per-CONTEXT.md D6 the planner is leaning toward CHECK constraint (`approval_state VARCHAR(16)` + `CHECK (approval_state IN (...))`) over a true PG ENUM, and the existing `draftstatus` enum was created via raw `CREATE TYPE` SQL (`backend/alembic/versions/0001_initial_schema.py` — see comment in `draft_item.py:19` "create_type=False because migration creates the type explicitly"). Hand-writing the migration sidesteps autogenerate's enum creation behavior.

**Run command:** Migrations run from `backend/` directory. Locally: `cd backend && uv run alembic upgrade head`. Production: railway runs `alembic upgrade head` before app start (per stack notes).

**Connection nuance:** `env.py:30` strips `?sslmode=require` from `DATABASE_URL` because asyncpg uses `connect_args={"ssl": True}` instead. No change needed.

**Test DB caveat.** `backend/tests/conftest.py:17` uses `sqlite+aiosqlite:///:memory:`. SQLite does NOT enforce `SELECT ... FOR UPDATE` row locks (it parses but ignores). Idempotency tests that exercise the lock semantics must run against Postgres, OR use mocked-db unit tests that assert the SQL contains `FOR UPDATE`. The existing `test_queue.py` uses `MagicMock` for DraftItem rather than a real engine — same pattern works for x_poster tests.

---

## tweepy v2 async client reference

**Confirmed via tweepy 4.14 official docs.**

**Import path:** `tweepy.asynchronous.AsyncClient` — already used at `scheduler/agents/content/gold_media.py:268`:
```python
import tweepy.asynchronous
tweepy_client = tweepy.asynchronous.AsyncClient(
    bearer_token=settings.x_api_bearer_token,
    wait_on_rate_limit=True,
)
```

**OAuth 1.0a User Context constructor (the Phase B pattern):**
```python
import tweepy.asynchronous
client = tweepy.asynchronous.AsyncClient(
    consumer_key=settings.x_api_key,
    consumer_secret=settings.x_api_secret,
    access_token=settings.x_access_token,
    access_token_secret=settings.x_access_token_secret,
)
```
All four params are `str | None`. AsyncClient also accepts `bearer_token`, `return_type`, `wait_on_rate_limit`. Pass exactly the four OAuth1 params for posting; do NOT pass `bearer_token` simultaneously (tweepy uses bearer for app-auth endpoints, OAuth1 for user-auth — keeping them separate avoids accidental fallback).

**`create_tweet` signature (kwargs we use):**
```python
resp = await client.create_tweet(
    text="...",                    # str | None
    in_reply_to_tweet_id=prev_id,  # int | str | None — for thread replies
    user_auth=True,                # default True; required for OAuth1 path
)
```
Other kwargs exist (poll_*, quote_tweet_id, reply_settings, media_ids) — not used in Phase B.

**Response shape: `resp.data["id"]` (dict subscript, NOT attribute).** Confirmed via official tweepy create_tweet example (`https://github.com/tweepy/tweepy/blob/master/examples/API_v2/create_tweet.py` line 32: `https://twitter.com/user/status/{response.data['id']}`). The `data` attribute is a dict-like with `id` (string) and `text` (string).

**Exception classes (all from `import tweepy` directly, no submodule):**

| Exception | HTTP status | Phase B mapping (per D11) |
|-----------|-------------|---------------------------|
| `tweepy.BadRequest` | 400 | `post_error="400:bad_request"` (catches duplicate, oversize, malformed) |
| `tweepy.Unauthorized` | 401 | `post_error="401:unauthorized"` |
| `tweepy.Forbidden` | 403 | `post_error="403:forbidden"` (often duplicate-content under v2) |
| `tweepy.NotFound` | 404 | `post_error="404:not_found"` (rare for create) |
| `tweepy.TooManyRequests` | 429 | `post_error="429:rate_limited"` |
| `tweepy.TwitterServerError` | 5xx | `post_error="5xx:server_error"` |
| `tweepy.HTTPException` | (parent of all above) | catch-all when status doesn't fit |
| `tweepy.TweepyException` | (root) | catch-all for non-HTTP errors |

All HTTP-tier exceptions inherit from `HTTPException` and expose: `.response`, `.api_errors`, `.api_codes`, `.api_messages`. The HTTP status code is on `.response.status_code`. Useful for richer logging but not required for the column write — `f"{e.response.status_code}:{e.api_messages[0] if e.api_messages else 'unknown'}"` is a clean format string.

**Catch order in `x_poster.py`:** catch the specific subclasses BEFORE `HTTPException` to avoid swallowing — Python except is first-match.

**Sources:**
- tweepy v2 AsyncClient: https://docs.tweepy.org/en/stable/asyncclient.html
- tweepy exceptions: https://docs.tweepy.org/en/stable/exceptions.html
- tweepy create_tweet example: https://github.com/tweepy/tweepy/blob/master/examples/API_v2/create_tweet.py

---

## X API v2 Basic tier posting limits

**Tier landscape (2026, verified):**
- **Basic** (legacy, $200/mo, no longer available to new signups as of Feb 2026): full read + write access to most v2 endpoints.
- **Pro** (legacy, ~$5K/mo): higher write allocation.
- **Pay-per-use** (default for new signups in 2026): $0.01/post creation, no monthly cap.

The CONTEXT.md/CLAUDE.md reference to `Basic tier ($100/mo) — read-only access` is stale. Current Basic is $200/mo and includes write access. This is research-surfaced, not action-required for Phase B (the codebase does not encode the cost in any logic that needs updating).

**POST /2/tweets rate limits per X official docs (https://docs.x.com/x-api/fundamentals/rate-limits):**

| Limit type | Value (per user, OAuth1 user-context) |
|------------|---------------------------------------|
| Per 15-minute window | **100 requests** |
| Per 24-hour window | **10,000 requests** (note: monthly post-write quota will hit first on Basic) |
| Per app (separate bucket) | not relevant — we always run user-auth |
| Monthly write quota (Basic tier) | ~50,000 writes/month (from postproxy.dev pricing summary) |

Sources differ on Basic monthly quota — public docs no longer publish a hard per-tier monthly cap because the tier is being deprecated for new signups. The endpoint-level 24h/15min limits are still authoritative and what tweepy will surface as 429s.

**For a single-user, single-account, manually-clicked Phase B flow:** rate limits are functionally infinite. A user clicking approve once every few minutes won't approach any limit. The endpoint relies on tweepy raising `TooManyRequests` (429) on actual hit; no pre-flight quota check. Per D9.

**Rate-limit response headers (all three returned on every response, including 200):**
- `x-rate-limit-limit` — max requests in window
- `x-rate-limit-remaining` — remaining in window
- `x-rate-limit-reset` — unix timestamp when window resets

These are accessible via `tweepy.HTTPException.response.headers["x-rate-limit-reset"]` on a 429 if Phase B+ wants to display a "retry after" hint. Not in scope for Phase B but easy to surface in `post_error` later.

**OAuth scope confirmed (https://docs.x.com/x-api/posts/creation-of-a-post):** POST /2/tweets accepts `OAuth2UserToken` (scopes: `tweet.read`, `tweet.write`, `users.read`) OR `UserToken` (HTTP OAuth = OAuth 1.0a User Context). Phase B uses the latter — D8 is correct.

**Sources:**
- X API rate limits canonical: https://docs.x.com/x-api/fundamentals/rate-limits
- X API pricing 2026 summary: https://postproxy.dev/blog/x-api-pricing-2026/
- POST /2/tweets endpoint reference: https://docs.x.com/x-api/posts/creation-of-a-post

---

## OAuth 1.0a User Context setup (runtime prerequisites)

**Phase B does NOT run a 3-legged OAuth flow at runtime.** Tokens are pre-generated once in the X Developer Portal and stored as env vars. Confirmed via tweepy authentication docs (https://docs.tweepy.org/en/stable/authentication.html) and X Developer Portal flow.

**Setup checklist (one-time, owner-side, NOT in code):**

1. **X Developer Portal → Project → App → "User authentication settings".** Set permissions to **"Read and Write"** (default is "Read"). This MUST be done BEFORE generating the access token. An access token generated under Read-only permissions cannot post — it will return 403 Forbidden, even with all four keys correct.
2. **X Developer Portal → App → "Keys and tokens" tab → "Access Token and Secret" → "Generate".** This produces the user-context token+secret pair. Format: long base64-ish strings (~50 chars), no expiry — they last until explicitly revoked or the app permissions are changed (changing permissions invalidates existing tokens).
3. **Token regeneration if Read+Write was toggled AFTER tokens were generated:** must regenerate. The tokens in your hand are still Read-only.
4. Store as env vars:
   - `X_API_KEY` — already in config (consumer key)
   - `X_API_SECRET` — already in config (consumer secret)
   - `X_ACCESS_TOKEN` — NEW (per D8)
   - `X_ACCESS_TOKEN_SECRET` — NEW (per D8)
5. The user the access token belongs to is the posting target. Posts go to whatever account was logged in when the developer-portal "Generate" button was clicked. Per D15, single-account is the explicit Phase B scope.

**Most common failure mode (confirmed via X dev community):** "I have all four keys, why is it returning 403?" — almost always: permissions were Read-only when access token was generated. Fix: set Read+Write FIRST, then regenerate access token.

**Documentation cue for the README/runbook:** The plan's docs commit should add a one-paragraph "Production prerequisites" note: enable Read+Write, generate access token AFTER, copy four keys to Railway env. This is doc-level, not test-level — no automated check is feasible here.

---

## Frontend component structure

**Mounted layout (verified `frontend/src/`):**
```
src/
├── api/
│   ├── client.ts           # apiFetch<T> — handles 401 redirect, JSON content-type, Bearer token
│   ├── queue.ts            # approveItem, rejectItem, getQueue — POST /api/items/...
│   ├── types.ts            # DraftStatus, DraftItemResponse, ContentBundle types
│   └── ...
├── components/
│   ├── approval/
│   │   ├── ContentSummaryCard.tsx   # the approve/reject card — Phase B button goes HERE
│   │   ├── ContentDetailModal.tsx   # detail modal — render-format dispatcher (lines 117-133)
│   │   ├── RejectPanel.tsx
│   │   └── InlineEditor.tsx
│   ├── content/
│   │   ├── BreakingNewsPreview.tsx  # reads draft.tweet (line 17)
│   │   ├── ThreadPreview.tsx        # reads draft.tweets (list, line 13)
│   │   ├── QuotePreview.tsx
│   │   ├── GoldMediaPreview.tsx
│   │   └── InfographicPreview.tsx
│   └── ui/
│       ├── dialog.tsx                # ALREADY EXISTS — Dialog, DialogContent, DialogHeader,
│       │                             #   DialogTitle, DialogDescription, DialogFooter (base-ui)
│       ├── button.tsx
│       ├── badge.tsx
│       └── ...
├── hooks/
│   ├── useApprove.ts        # the reference mutation pattern — see below
│   ├── useReject.ts
│   ├── useQueue.ts
│   └── useContentBundle.ts
└── pages/
    └── PerAgentQueuePage.tsx   # mounts ContentSummaryCard via useQueue + groupByRun
```

**Existing approve mutation pattern (`frontend/src/hooks/useApprove.ts:1-19`):** This is the canonical reference for Phase B's new `usePostToX` mutation:
```typescript
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { approveItem } from '@/api/queue'
import { toast } from 'sonner'

export function useApprove(platform: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, editedText }: { id: string; editedText?: string }) =>
      approveItem(id, editedText),
    onSuccess: (data, variables) => {
      const textToCopy = variables.editedText ?? data.alternatives?.[0]?.text ?? ''
      navigator.clipboard.writeText(textToCopy)
      toast.success('Approved — copied to clipboard')
      queryClient.invalidateQueries({ queryKey: ['queue', platform] })
    },
  })
}
```

**Phase B pattern (recommended `usePostToX.ts`):**
```typescript
export function usePostToX(platform: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id }: { id: string }) => postItemToX(id),
    onSuccess: (data) => {
      if (data.approval_state === 'posted') toast.success(`Posted to X — ${data.posted_tweet_id}`)
      else if (data.approval_state === 'posted_partial') toast.warning(`Partial: ${data.post_error}`)
      else toast.error(`Failed: ${data.post_error}`)
      queryClient.invalidateQueries({ queryKey: ['queue', platform] })
    },
    onError: (err) => toast.error(`Network error: ${err.message}`),
  })
}
```

**Dialog primitive: ALREADY AVAILABLE.** `components/ui/dialog.tsx` exports `Dialog`, `DialogTrigger`, `DialogContent`, `DialogHeader`, `DialogTitle`, `DialogDescription`, `DialogFooter`, `DialogClose`, `DialogPortal`, `DialogOverlay`. Built on `base-ui/react`. Already used by `ContentDetailModal.tsx`. Phase B's confirm modal is a NEW small component, e.g. `frontend/src/components/approval/PostToXConfirmModal.tsx`, that uses these same exports.

**Where to put the "Post to X" button.** `ContentSummaryCard.tsx:161-176` shows the action-button row (Approve / Reject). Adding a third button "Post to X" here is the natural placement. Alternative: include the button only on the detail modal (`ContentDetailModal.tsx`) so the user is forced to view full preview first — this matches D10's intent of preventing misfires. **Recommendation: button on the modal only**, since the card view doesn't show enough text to confirm what's being posted. The modal already renders the full preview via `ThreadPreview`/`BreakingNewsPreview`.

**Wiring path:** detail modal → "Post to X" button → opens `PostToXConfirmModal` (nested dialog or replacing) → "Post to X" primary button → calls `usePostToX().mutate({id})`.

**Text extraction in the modal (for the confirm step body):**
- For `breaking_news`: `bundle.draft_content.tweet`
- For `thread`: `bundle.draft_content.tweets` (render numbered list)

The `bundle` object is already available in `ContentDetailModal.tsx:38` via `useContentBundle(bundleId)`.

**Type additions (`frontend/src/api/types.ts`):**
```typescript
export type ApprovalState = 'pending' | 'posted' | 'failed' | 'discarded' | 'posted_partial'
export interface PostToXResponse {
  approval_state: ApprovalState
  posted_tweet_id?: string
  posted_tweet_ids?: string[]
  posted_at?: string
  post_error?: string
}
```
Add `approval_state`, `posted_tweet_id`, etc. to `DraftItemResponse` interface. The frontend `DraftStatus` type stays unchanged.

**Existing copy-to-clipboard buttons (`BreakingNewsPreview.tsx:34-43`, `ThreadPreview.tsx:33-45`).** Stay. They are not the approve flow — they are the manual paste flow. Phase B SUPPLEMENTS clipboard copy, doesn't replace.

---

## Auth middleware integration

**JWT dependency (`backend/app/dependencies.py:10-20`):**
```python
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> str:
    try:
        payload = decode_token(credentials.credentials)
        return payload["sub"]    # always "operator" (single-user system)
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
```

Returns the string `"operator"` (the single-user `sub` claim per `auth.py:19`). Routes that don't need the value can ignore it; the dependency itself is what enforces auth. Token expiry: 7 days (`auth.py:9`).

**Wiring pattern.** Either:
- Router-level (preferred, matches all 8 other gated routers): `APIRouter(prefix="/...", dependencies=[Depends(get_current_user)])`
- Per-route: `async def post_to_x(..., _user: str = Depends(get_current_user)): ...` — less idiomatic in this codebase.

**Test pattern (`backend/tests/conftest.py:115-119`):** `authed_client` fixture pre-sets `Authorization: Bearer <token>` header. Phase B's tests use this fixture for happy-path; for 401 testing use bare `client` with no header.

**No auth refactor needed.** The dependency is mature and used by every mutating endpoint already.

---

## Env var registration

**Add to `backend/app/config.py:` Settings class (lines 28-29 currently has `x_api_key` / `x_api_secret`):**
```python
x_access_token: str | None = None
x_access_token_secret: str | None = None
x_posting_enabled: bool = False
x_posting_sim_prefix: str = "sim-"
```

**Add to `scheduler/config.py:` Settings class (lines 22-23):** same four lines. Scheduler has `extra="ignore"` so it won't crash on backend-only vars, but the four new vars are tiny and shared cleanly.

**Add to `.env.example` (after line 23):**
```env
# Phase B: OAuth 1.0a User Context for posting (requires Read+Write app perms — see runbook)
X_ACCESS_TOKEN=
X_ACCESS_TOKEN_SECRET=

# Phase B: feature flag — false in dev/CI (simulates), true in prod
X_POSTING_ENABLED=false
# Phase B: prefix for simulated tweet IDs in dev (must not collide with real X numeric IDs)
X_POSTING_SIM_PREFIX=sim-
```

**Naming convention (verified against existing entries):** uppercase env var name, lowercase pydantic attribute, snake_case both sides. `case_sensitive=False` in `SettingsConfigDict` so casing is forgiving.

**Test conftest update (`backend/tests/conftest.py:25-28`):** add `os.environ["X_ACCESS_TOKEN"] = "test-access"` and `os.environ["X_ACCESS_TOKEN_SECRET"] = "test-secret"` to the env-var setup block. Default `X_POSTING_ENABLED` stays unset (Settings default `False`) — tests run in simulate mode, no tweepy calls.

**`tweepy[async]>=4.14` to `backend/pyproject.toml`:** add to `dependencies` list. Run `uv lock` in `backend/`. Scheduler already has it; this is purely backend-side.

---

## Test fixtures + mocking patterns

**Pattern reference (`scheduler/tests/test_gold_media.py:42-58`):** existing tweepy mock template the planner can mirror in `backend/tests/test_x_poster.py`:

```python
from unittest.mock import AsyncMock, MagicMock, patch

@pytest.mark.asyncio
async def test_create_tweet_happy_path():
    tweepy_client = AsyncMock()
    response = MagicMock()
    response.data = {"id": "1234567890123456789", "text": "..."}
    tweepy_client.create_tweet = AsyncMock(return_value=response)
    # ... test body
```

**Error-path pattern:**
```python
import tweepy
@pytest.mark.asyncio
async def test_rate_limited():
    tweepy_client = AsyncMock()
    fake_resp = MagicMock(); fake_resp.status_code = 429
    exc = tweepy.TooManyRequests(fake_resp)
    exc.api_messages = ["Too many requests"]
    tweepy_client.create_tweet = AsyncMock(side_effect=exc)
    # ... assert post_error == "429:Too many requests" or similar
```

**Existing queue test pattern (`backend/tests/test_queue.py:24-54`):** shows how to MagicMock a DraftItem ORM row and override `get_db` via `app.dependency_overrides`. Phase B endpoint tests follow this pattern; no real DB engine needed for unit tests.

**Integration test for `SELECT FOR UPDATE` semantics:** SQLite cannot enforce row locks. Either (a) skip the concurrency-correctness test in unit tier and rely on hand-checked Postgres behavior, (b) write the test to assert the SQL contains `FOR UPDATE` via a mock-engine spy, or (c) introduce a Postgres-only integration test in `backend/tests/integration/` (currently no such directory). **Recommendation: option (b)** — assert the generated SQL contains `FOR UPDATE` via SQLAlchemy's `Select.compile()` output. Cheap, deterministic, doesn't require a Postgres test container.

---

## Don't Hand-Roll

| Problem | Don't build | Use instead | Why |
|---------|-------------|-------------|-----|
| OAuth1 signing for X API | Custom `requests` + HMAC-SHA1 signing | `tweepy.asynchronous.AsyncClient` | Tweepy handles the full OAuth1 dance + nonce/timestamp/signature correctly. Already a project dependency in scheduler — extend to backend. |
| HTTP error → status code mapping | If/else on `e.response.status_code` | `except tweepy.TooManyRequests` / `Unauthorized` / etc. by class | tweepy's exception hierarchy IS the mapping. Catching by class is more readable and matches D11 verbatim. |
| Idempotency token | New column `idempotency_key`, hashed-body lookup, expiring TTL | `SELECT FOR UPDATE` on the existing PK + state-check | Per D3, single-user QPS, native pg semantics, no extra schema, no expiry concerns. |
| Optimistic concurrency state machine | `pending → posting → posted` with crash-recovery sweeper | `pending → posted` under one lock-held tx | Per D3 alternative-considered. Single-user, ~500ms tweepy round-trip — locking through the call is the cleanest correct approach. |
| Dialog primitives | Custom modal with manual focus trap + escape handling | `components/ui/dialog.tsx` (already exists) | Ships with Esc, click-outside, focus-trap, ARIA. Used elsewhere in the codebase. |
| Per-tier rate-limit math | Pre-flight quota counter | Catch `TooManyRequests` and surface | Per D9. The single-user click rate is well below any tier limit; pre-flight checks add complexity for no benefit. |
| Tweet text validation (length, mention rules) | Custom 280-char + URL-shortener-aware checker | Let tweepy/X reject as `BadRequest` | Per D13 — byte-for-byte fidelity. Frontend already shows the text; if user approves over-280, the X error surfaces cleanly. |

---

## Common Pitfalls

### Pitfall 1: 403 Forbidden on first real post
**What goes wrong:** All four keys configured, endpoint returns 403 from X. **Why:** access token was generated when app permissions were Read-only; toggling to Read+Write afterward does NOT retroactively upgrade existing tokens. **How to avoid:** runbook step — enable Read+Write FIRST, regenerate access token AFTER. Surface this in the docs commit.

### Pitfall 2: SQLite test backend silently passes locking tests
**What goes wrong:** Test asserts concurrent calls don't double-post; passes against SQLite because SQLite parses `FOR UPDATE` but doesn't enforce it. Bug ships to Postgres. **How to avoid:** assert SQL syntax (option b above) or add a Postgres-backed integration test. Prefer the assertion approach for Phase B speed.

### Pitfall 3: Long lock hold during tweepy call
**What goes wrong:** tweepy round-trip is 200-500ms typical, can be 5-15s on a slow X API day. The DB row lock blocks other writes to that exact draft row. For a single-user system this is fine, but mention it in the route docstring + set `statement_timeout = 15s` per D3 risk note. **How to avoid:** don't extend the tx scope beyond what's needed; do all derivation (build text from bundle, format payload) BEFORE `BEGIN`.

### Pitfall 4: Mismatch between preview text and posted text
**What goes wrong:** The preview component normalizes whitespace, then x_poster.py reads from a different field that wasn't normalized — user sees "X" in preview, posts "Y". **How to avoid:** the planner should add a verification step — both `BreakingNewsPreview.tsx:17` and `x_poster.py` MUST read from `draft_content.tweet`/`draft_content.tweets`. Confirmed `BreakingNewsPreview` does NO transforms (uses `whitespace-pre-wrap`, `typeof check`). Same for `ThreadPreview.tsx`. D13 byte-for-byte requirement is satisfied by reading the exact same JSONB path on both sides.

### Pitfall 5: scheduler/models vs backend/app/models drift
**What goes wrong:** New columns added to `backend/app/models/draft_item.py` only — scheduler can't read them, breaking content_agent's draft writes. **How to avoid:** edit BOTH model files identically. Migration runs from backend/ but the scheduler imports the same DB. (CONTEXT.md "specifics" notes `scheduler/models/` — confirmed.)

### Pitfall 6: `tweepy` not in backend/pyproject.toml
**What goes wrong:** `from tweepy.asynchronous import AsyncClient` raises ImportError at backend startup. **How to avoid:** add to `backend/pyproject.toml dependencies` and run `uv lock`. Easy to forget because scheduler has it.

### Pitfall 7: Catch-order for tweepy exceptions
**What goes wrong:** `except tweepy.HTTPException` placed before `except tweepy.TooManyRequests` — Python takes the first match, so 429s go into the wrong bucket. **How to avoid:** specific exceptions FIRST, then `HTTPException`, then `TweepyException`.

### Pitfall 8: `engagement_snapshot["content_bundle_id"]` is a string, not a UUID
**What goes wrong:** Direct comparison or join logic treats it as `UUID` type. The JSONB stores it as text (per `scheduler/agents/content_agent.py:687: str(content_bundle.id)`). **How to avoid:** `UUID(snapshot["content_bundle_id"])` to cast back, or compare via `cast(ContentBundle.id, String)` as `queue.py:81` does.

---

## Code Examples

### Backend service skeleton (`backend/app/services/x_poster.py`)
```python
import logging
from typing import Literal

import tweepy
import tweepy.asynchronous

from app.config import get_settings

logger = logging.getLogger(__name__)


class PostError(Exception):
    """Internal error wrapper. .code is HTTP-status-like, .message is humanized."""
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"{code}:{message}")


def _build_client() -> tweepy.asynchronous.AsyncClient:
    s = get_settings()
    return tweepy.asynchronous.AsyncClient(
        consumer_key=s.x_api_key,
        consumer secret=s.x_api_secret,
        access_token=s.x_access_token,
        access_token_secret=s.x_access_token_secret,
    )


async def post_single_tweet(text: str) -> str:
    """Returns the new tweet's id on success, raises PostError on failure."""
    client = _build_client()
    try:
        resp = await client.create_tweet(text=text, user_auth=True)
        return resp.data["id"]
    except tweepy.TooManyRequests as e:
        raise PostError("429", _msg(e)) from e
    except tweepy.Unauthorized as e:
        raise PostError("401", _msg(e)) from e
    except tweepy.Forbidden as e:
        raise PostError("403", _msg(e)) from e
    except tweepy.BadRequest as e:
        raise PostError("400", _msg(e)) from e
    except tweepy.HTTPException as e:
        code = str(getattr(e.response, "status_code", "500"))
        raise PostError(code, _msg(e)) from e
    except tweepy.TweepyException as e:
        raise PostError("500", str(e)) from e


async def post_thread(tweets: list[str]) -> tuple[list[str], PostError | None]:
    """Returns (posted_ids_so_far, optional_error). Caller writes posted_partial state on partial failure."""
    client = _build_client()
    posted: list[str] = []
    prev_id: str | None = None
    for text in tweets:
        kwargs: dict = {"text": text, "user_auth": True}
        if prev_id is not None:
            kwargs["in_reply_to_tweet_id"] = prev_id
        try:
            resp = await client.create_tweet(**kwargs)
        except tweepy.TooManyRequests as e:
            return posted, PostError("429", _msg(e))
        except tweepy.HTTPException as e:
            code = str(getattr(e.response, "status_code", "500"))
            return posted, PostError(code, _msg(e))
        except tweepy.TweepyException as e:
            return posted, PostError("500", str(e))
        new_id = resp.data["id"]
        posted.append(new_id)
        prev_id = new_id
    return posted, None


def _msg(e: tweepy.HTTPException) -> str:
    if getattr(e, "api_messages", None):
        return e.api_messages[0]
    return str(e)
```

### Backend route skeleton (`backend/app/routers/post_to_x.py`)
```python
import uuid
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.content_bundle import ContentBundle
from app.models.draft_item import DraftItem
from app.services import x_poster

router = APIRouter(
    tags=["post-to-x"],
    dependencies=[Depends(get_current_user)],
)


@router.post("/items/{item_id}/post-to-x")
async def post_to_x(item_id: UUID, db: AsyncSession = Depends(get_db)):
    settings = get_settings()
    # 1. Lock + load draft (single tx)
    async with db.begin():
        result = await db.execute(
            select(DraftItem).where(DraftItem.id == item_id).with_for_update()
        )
        item = result.scalar_one_or_none()
        if item is None:
            raise HTTPException(status_code=404, detail="Item not found")
        if item.approval_state == "posted":
            return {"already_posted": True, "posted_tweet_id": item.posted_tweet_id, ...}

        # 2. Resolve bundle text
        bundle_id = (item.engagement_snapshot or {}).get("content_bundle_id")
        bundle = await db.get(ContentBundle, UUID(bundle_id))
        content_type = bundle.content_type
        draft_content = bundle.draft_content or {}

        # 3. Branch on content_type (Phase B: breaking_news + thread only)
        if content_type == "breaking_news":
            text = draft_content["tweet"]
            if settings.x_posting_enabled:
                try:
                    tweet_id = await x_poster.post_single_tweet(text)
                except x_poster.PostError as e:
                    item.approval_state = "failed"
                    item.post_error = f"{e.code}:{e.message}"
                    item.posted_at = datetime.now(UTC)
                    return _serialize(item)
            else:
                tweet_id = f"{settings.x_posting_sim_prefix}{uuid.uuid4()}"
            item.approval_state = "posted"
            item.posted_tweet_id = tweet_id
            item.posted_tweet_ids = None
            item.posted_at = datetime.now(UTC)
        elif content_type == "thread":
            tweets = draft_content["tweets"]
            if settings.x_posting_enabled:
                ids, err = await x_poster.post_thread(tweets)
                if err and not ids:
                    item.approval_state = "failed"; item.post_error = f"{err.code}:{err.message}"
                elif err:
                    item.approval_state = "posted_partial"
                    item.posted_tweet_id = ids[0]; item.posted_tweet_ids = ids
                    item.post_error = f"thread {len(ids)}/{len(tweets)}: {err.code}:{err.message}"
                else:
                    item.approval_state = "posted"
                    item.posted_tweet_id = ids[0]; item.posted_tweet_ids = ids
            else:
                sim_ids = [f"{settings.x_posting_sim_prefix}{uuid.uuid4()}" for _ in tweets]
                item.approval_state = "posted"
                item.posted_tweet_id = sim_ids[0]; item.posted_tweet_ids = sim_ids
            item.posted_at = datetime.now(UTC)
        else:
            raise HTTPException(status_code=400, detail=f"content_type '{content_type}' not in Phase B scope")

        return _serialize(item)
```

(Full type hints and serialization elided — illustrative only.)

### Migration skeleton (`backend/alembic/versions/0009_add_x_post_state_to_draft_items.py`)
```python
"""Add Phase B X post-state columns to draft_items.

Revision ID: 0009
Revises: 0008
Create Date: 2026-04-24
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "draft_items",
        sa.Column("approval_state", sa.String(16), nullable=False, server_default="pending"),
    )
    op.create_check_constraint(
        "ck_draft_items_approval_state",
        "draft_items",
        "approval_state IN ('pending','posted','failed','discarded','posted_partial')",
    )
    op.add_column("draft_items", sa.Column("posted_tweet_id", sa.Text(), nullable=True))
    op.add_column("draft_items", sa.Column("posted_tweet_ids", postgresql.JSONB(), nullable=True))
    op.add_column(
        "draft_items",
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("draft_items", sa.Column("post_error", sa.Text(), nullable=True))
    op.create_index("ix_draft_items_approval_state", "draft_items", ["approval_state"])


def downgrade() -> None:
    op.drop_index("ix_draft_items_approval_state", table_name="draft_items")
    op.drop_column("draft_items", "post_error")
    op.drop_column("draft_items", "posted_at")
    op.drop_column("draft_items", "posted_tweet_ids")
    op.drop_column("draft_items", "posted_tweet_id")
    op.drop_constraint("ck_draft_items_approval_state", "draft_items", type_="check")
    op.drop_column("draft_items", "approval_state")
```

---

## Open questions

1. **Should the "Post to X" button live on `ContentSummaryCard` or only on `ContentDetailModal`?** Card is faster for power users; modal forces preview. Discretion item per CONTEXT.md. **Recommendation: modal-only** (matches D10 intent of preventing misfires — user must see full text before confirming).

2. **Should the route path be `POST /items/{id}/post-to-x` or `POST /items/{id}/approve-and-post`?** Per CONTEXT.md "Claude's Discretion". The existing PATCH `/items/{id}/approve` does NOT post — keeping these distinct in name avoids cognitive collision. **Recommendation:** `POST /items/{item_id}/post-to-x`. Verb `POST` (not `PATCH`) is right for "create a side effect" semantics. The path name `post-to-x` is unambiguous about the side-effect target.

3. **Should `X_POSTING_ENABLED` default to `False` in `Settings`, or be required (no default)?** Defaulting `False` (per D2) means a missing env var in prod silently simulates — that's a deploy footgun. **Recommendation:** keep `False` default per D2 (matches dev simplicity), but plan verification step asserts `X_POSTING_ENABLED=true` in Railway prod env (manual + scripted check on deploy).

4. **What happens if `engagement_snapshot["content_bundle_id"]` is missing or stale?** Possible for old `draft_items` predating the link convention. **Recommendation:** 400 response with `detail="No content_bundle linked"` — surface to UI as red banner. Phase B-scope rows are all post-Phase-11 so this should never fire in practice.

5. **`tweepy[async]` vs `tweepy>=4.14` in `backend/pyproject.toml`?** Scheduler uses `tweepy[async]`. The `[async]` extra installs `aiohttp`. Backend already uses `httpx`. **Recommendation: `tweepy[async]>=4.14`** — match scheduler exactly, and `aiohttp` install size is small (~2MB). Avoids dependency resolution conflicts between the two services.

---

## Recommendations for planner

**Task ordering (suggested):**

1. **Migration.** Hand-write `0009_add_x_post_state_to_draft_items.py`. Add the 5 columns + check constraint + index. Mirror columns onto BOTH `backend/app/models/draft_item.py` AND `scheduler/models/draft_item.py`. (Why first: subsequent code can `from app.models.draft_item import DraftItem` and access new attributes.)

2. **Config + dependency wiring.** Add `tweepy[async]>=4.14` to `backend/pyproject.toml`; run `uv lock`. Add 4 env-var attrs to `backend/app/config.py:Settings` AND `scheduler/config.py:Settings`. Add to `.env.example`. Add to `backend/tests/conftest.py` env-var setup.

3. **Service.** `backend/app/services/x_poster.py` with `post_single_tweet()` and `post_thread()` and the `PostError` wrapper. Unit tests in `backend/tests/test_x_poster.py` covering: happy single, happy thread, partial-thread fail, each tweepy exception class, simulate-mode bypass.

4. **Schemas.** Add `ApprovalState` enum + `PostToXResponse` to `backend/app/schemas/draft_item.py` (or new `post_to_x.py`). Update `DraftItemResponse` to include the new fields.

5. **Router.** `backend/app/routers/post_to_x.py` — single endpoint. Wire into `backend/app/main.py`. Tests in `backend/tests/test_post_to_x.py`: happy path (simulate mode), already-posted idempotency, 404 not-found, content_type-out-of-scope 400, partial-thread 200 with posted_partial state, FOR UPDATE assertion (compile SQL, regex check).

6. **Frontend types.** Update `frontend/src/api/types.ts` with `ApprovalState`, `PostToXResponse`, extended `DraftItemResponse`.

7. **Frontend API + hook.** `frontend/src/api/queue.ts` — add `postItemToX(id)`. `frontend/src/hooks/usePostToX.ts` — mirror `useApprove.ts`.

8. **Frontend confirm modal.** `frontend/src/components/approval/PostToXConfirmModal.tsx`. Use existing `Dialog` primitives. Renders the post text via existing `BreakingNewsPreview`/`ThreadPreview` (read-only mode).

9. **Frontend wire-in.** `ContentDetailModal.tsx` — add "Post to X" button in `DialogFooter` for `breaking_news` and `thread` content types only. Opens `PostToXConfirmModal`.

10. **Display banners for partial/failed states.** Edit `ContentSummaryCard.tsx` to show amber banner when `approval_state === "posted_partial"` (with `post_error` text + posted IDs), red banner when `"failed"`, green check when `"posted"` (with link to `https://x.com/_/status/{posted_tweet_id}` if not sim-prefix).

11. **CLAUDE.md docs commit.** Per D12, rewrite the single "Auto-posting" row in the "What NOT to Use" table. Verbatim text from CONTEXT.md D12.

12. **README/runbook entry.** Either inline in CLAUDE.md or a new `docs/POSTING.md`: 5-step prereq for new owners (enable Read+Write, generate access token, copy 4 keys to Railway, set `X_POSTING_ENABLED=true`, verify via single test post).

**Test architecture notes:**
- All tests in unit tier mock tweepy. Zero network calls.
- Use `app.dependency_overrides[get_db]` to swap in a MagicMock session for endpoint tests.
- The `FOR UPDATE` assertion is a syntactic check on the SQL — sufficient for unit tests; a true concurrency test requires Postgres and is out of scope for Phase B unless the planner wants a single integration test.
- The `authed_client` fixture in `conftest.py:115` is the right entry for endpoint tests.

**Migration reversibility:** All 5 column adds are reversible (downgrade drops them). The check constraint can be re-added if the column is restored. Safe forward + backward.

**No scheduler changes.** D14, the safety-preserved-list in CONTEXT.md, mandates zero scheduler diffs except for `scheduler/models/draft_item.py` mirror update + scheduler/config.py 4 env-var add. No new cron jobs, no edits to content sub-agents, no changes to gold_media's existing tweepy bearer-token client.

**Deferred for B.5 (already structured for):** the `content_type` switch in the router is the registration point. Adding `quote` and `gold_history` is a few lines extending the elif ladder with text-extraction logic for those `draft_content` shapes. No schema changes, no service-layer changes.

---

## Sources

### Primary (HIGH confidence)
- tweepy AsyncClient docs: https://docs.tweepy.org/en/stable/asyncclient.html
- tweepy exceptions reference: https://docs.tweepy.org/en/stable/exceptions.html
- tweepy create_tweet example (response.data['id']): https://github.com/tweepy/tweepy/blob/master/examples/API_v2/create_tweet.py
- tweepy authentication (OAuth1 user-context): https://docs.tweepy.org/en/stable/authentication.html
- X API rate limits (canonical): https://docs.x.com/x-api/fundamentals/rate-limits
- X API POST /2/tweets (auth scopes): https://docs.x.com/x-api/posts/creation-of-a-post

### Secondary (MEDIUM confidence)
- X API 2026 pricing summary: https://postproxy.dev/blog/x-api-pricing-2026/
- 403 Forbidden tweepy diagnosis (community): https://devcommunity.x.com/t/403-forbidden-when-posting-tweets-via-tweepy-x-api-v2-app-id-32776118/262973 (page returned 403 to fetch but the issue title alone confirms the canonical answer about Read-vs-Read+Write tokens)

### Tertiary (LOW confidence — verify in implementation)
- Basic-tier monthly write quota (~50,000) — postproxy.dev only; X official docs no longer publish a tier-by-tier monthly cap. **Mitigation:** the endpoint relies on tweepy's 429 detection — quota fudge factor is irrelevant to correctness.

### Codebase (verified by direct read)
- `backend/app/main.py`, `app/config.py`, `app/auth.py`, `app/dependencies.py`, `app/database.py`
- `backend/app/models/draft_item.py`, `models/content_bundle.py`, `models/__init__.py`
- `backend/app/routers/queue.py`, `routers/auth.py`, `routers/content_bundles.py`
- `backend/app/services/whatsapp.py`, `app/schemas/draft_item.py`
- `backend/alembic/env.py`, `alembic.ini`, `versions/0001..0008_*.py`
- `backend/tests/conftest.py`, `tests/test_queue.py`
- `backend/pyproject.toml`, `scheduler/pyproject.toml`
- `scheduler/agents/content/breaking_news.py`, `agents/content/threads.py`, `agents/content/gold_media.py`
- `scheduler/agents/content_agent.py:687` (engagement_snapshot.content_bundle_id link)
- `scheduler/config.py`, `scheduler/tests/test_gold_media.py`
- `frontend/src/api/types.ts`, `api/queue.ts`, `api/client.ts`
- `frontend/src/hooks/useApprove.ts`
- `frontend/src/components/approval/{ContentSummaryCard,ContentDetailModal}.tsx`
- `frontend/src/components/content/{BreakingNewsPreview,ThreadPreview}.tsx`
- `frontend/src/components/ui/dialog.tsx`
- `.env.example`
- `CLAUDE.md:96` (Auto-posting row)

## Metadata

**Confidence breakdown:**
- Backend layout + conventions: HIGH (every file path verified by Read).
- draft_items / content_bundles schema: HIGH (model files read in full).
- Alembic naming + state: HIGH (versions dir listed; head is 0008).
- tweepy v2 API surface: HIGH (official docs + working codebase reference at `gold_media.py:268`).
- X API rate limits: MEDIUM-HIGH (canonical docs.x.com confirms 100/15min, 10000/24hr per user at endpoint level; tier-specific monthly caps are MEDIUM since X has shifted to pay-per-use and pricing pages no longer publish per-tier monthly post quotas authoritatively).
- OAuth 1.0a setup prerequisites: HIGH (tweepy auth docs + multiple X dev community sources agree on the Read+Write-before-token-generation gotcha).
- Frontend layout: HIGH (every relevant file read, mutation pattern + dialog primitive confirmed available).
- Test patterns: HIGH (conftest read; mock tweepy precedent in scheduler/tests/test_gold_media.py).

**Research date:** 2026-04-24
**Valid until:** 2026-05-24 (tweepy 4.14 stable; X API surface unlikely to shift in 30 days; codebase paths captured at HEAD).
