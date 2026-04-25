# Quick Task 260424-l0d: Phase B — approve→auto-post to X (Twitter) — Context

**Gathered:** 2026-04-24
**Status:** Ready for research + planning

<domain>
## Task Boundary

Implement **Phase B: approve→auto-post to X** — the user approves a draft item on the dashboard via an explicit confirm-click; the system immediately posts it to X (Twitter) using `tweepy` v2 `create_tweet` with OAuth 1.0a User Context. Single-user tool; no unattended posting, no scheduler-triggered posting, no batch posting. Every post is user-initiated and tied to exactly one draft_items row.

**Narrow MVP scope (D1 locked):** Phase B ships **text-only posting for `breaking_news` + `thread` content_types ONLY**. Single-tweet `breaking_news` exercises the vanilla create_tweet call; multi-tweet `thread` exercises the client-side reply-chain orchestration via `in_reply_to_tweet_id`. These two end-to-end validate the full Phase B pattern. `quotes` + `gold_history` (also text-only) are deferred to a tiny Phase B.5 follow-up — they become a per-content-type registration in the postable-types map after Phase B's pattern is proven. `gold_media` + `infographics` stay out of Phase B entirely (they need `tweepy.media_upload` + X API media endpoints — a fundamentally different auth/upload pattern) and are explicit Phase B+ scope.

**CLAUDE.md override (locked upfront):** The "Auto-posting to any platform / Never implement" row in `CLAUDE.md`'s "What NOT to Use" table is narrowly rewritten — user-initiated, explicit per-item approve-to-post becomes in-scope. Unattended auto-posting (scheduled posting, batch posting, cron-triggered posting, anything not user-initiated) remains permanently out of scope. Edit to the `CLAUDE.md` row happens in the docs commit of this task.

</domain>

<decisions>
## Implementation Decisions

### D1 — Content-type scope (from discuss Q1)
- **Phase B ships:** `breaking_news` + `thread` text-only.
- **Deferred to Phase B.5:** `quotes` + `gold_history` (text-only, trivial additions — just register in the postable-types map once the pattern is proven).
- **Explicitly out of scope for Phase B+:** `gold_media` + `infographics` (require `tweepy.media_upload` — different X API surface, different auth semantics, different error modes).
- **Rationale:** breaking_news is the single-tweet happy-path case; thread is the reply-chain case. If both ship cleanly, the remaining text types are a lines-of-code add. Narrowing the MVP keeps the first end-to-end flow small and the failure modes easy to reason about.

### D2 — Feature flag default behavior (from discuss Q2)
- **`X_POSTING_ENABLED=false` (dev default):** endpoint simulates success. DB row gets `approval_state='posted'`, `posted_tweet_id='sim-{uuid4}'`, `posted_at=now()`. Frontend flows work end-to-end in dev without real tweets. Returns 200.
- **`X_POSTING_ENABLED=true` (prod):** endpoint calls tweepy `create_tweet` for real.
- **Rationale:** user wants to exercise the dashboard approve flow locally/in CI without touching the live X account. "sim-" prefix makes dev rows trivially filterable out of any future metrics/audits. No special "disabled" UI state — the frontend treats simulated posts identically to real posts (it's the same state machine transition, just a different tweet_id shape).
- **Safety:** a second env-var `X_POSTING_SIM_PREFIX=sim-` (configurable, default `sim-`) namespaces simulated tweet_ids so they can never collide with real X IDs (which are long numeric strings). Tests assert real tweet_ids match `^\d+$` and simulated ones match `^sim-[0-9a-f-]+$`.

### D3 — Idempotency strategy (from discuss Q3)
- **SELECT FOR UPDATE + state check inside a single transaction.**
- Endpoint flow: `BEGIN → SELECT * FROM draft_items WHERE id=$1 FOR UPDATE → check approval_state → call tweepy → UPDATE draft_items SET approval_state='posted', posted_tweet_id=..., posted_at=... WHERE id=$1 → COMMIT`.
- Second concurrent call blocks on the row lock, reads `approval_state='posted'` after the first commits, returns HTTP 200 with `{already_posted: true, posted_tweet_id: <existing>}`.
- **Rationale:** PostgreSQL row locks are cheap, the approve endpoint is low-QPS (single user clicking buttons), and correctness over cleverness.
- **Alternative considered:** optimistic CAS (`UPDATE … WHERE approval_state='pending' RETURNING …`). Rejected because it requires a two-phase state machine (pending → posting → posted) and adds a crashed-in-posting-state recovery concern that `SELECT FOR UPDATE` avoids — the tx holds the lock through the tweepy call, so there is no interstitial "in flight, not committed" state.
- **Risk:** tweepy call inside the open tx holds the lock for the duration of the HTTP round-trip to X (expected ~200-500ms, worst case ~5s). Acceptable for a single-user tool. Sets statement_timeout at 15s to bound worst case.

### D4 — Posting trigger model (from user brief Q1)
- **Atomic** — the approve endpoint synchronously calls tweepy and returns 200 only after the post succeeds (or 5xx on failure). No background poster, no queue. Pairs with D3.

### D5 — State machine (from user brief Q2 + D3)
- **States:** `pending` (default at bundle creation) → `posted` | `failed` | `discarded`.
- **Thread partial state:** `posted_partial` for the case where tweet N of M in a thread succeeds but tweet N+1 fails. Only reachable for `content_type='thread'`.
- **No `approved` intermediate state** — because D4 is atomic; approve is not a distinct state from posted in the happy path.
- **Discarded:** user can also reject drafts (separate endpoint/button, not Phase B scope, but the state value exists so future work slots in).

### D6 — Column placement
- **On `draft_items` table.** Deferred-to-research confirmation of the exact model file path + column types. The user brief leans toward `draft_items` and this matches the `per-variant approval` semantic (the draft_item is what the user picks and approves; `content_bundles` is the upstream story ingestion row).
- **New columns on `draft_items`:**
  - `approval_state` — enum (`pending`, `posted`, `failed`, `discarded`, `posted_partial`), default `pending`, NOT NULL.
  - `posted_tweet_id` — TEXT NULLable (single-tweet content_types store the one ID; threads store the first tweet's ID here and the full list in `posted_tweet_ids`).
  - `posted_tweet_ids` — JSONB NULLable array of tweet_id strings for threads (null for single-tweet content_types).
  - `posted_at` — TIMESTAMPTZ NULLable.
  - `post_error` — TEXT NULLable (tweepy exception `str()` + error code).
- **Why both `posted_tweet_id` AND `posted_tweet_ids`:** `posted_tweet_id` is the canonical "link to post" (always set to the first tweet's ID on success); `posted_tweet_ids` is the detail for threads. Single-tweet rows have `posted_tweet_id` set and `posted_tweet_ids=null`.

### D7 — Thread posting mechanics (from user brief Q4)
- **Client-side reply-chain orchestration inside the approve handler.**
- Flow: `for i, tweet_text in enumerate(thread_tweets): if i == 0: resp = client.create_tweet(text=tweet_text) else: resp = client.create_tweet(text=tweet_text, in_reply_to_tweet_id=prev_id); prev_id = resp.data['id']; posted_ids.append(resp.data['id'])`.
- **Partial-failure semantics:** if tweet N of M fails (any tweepy exception), stop immediately, set `approval_state='posted_partial'`, `posted_tweet_ids=[<ids posted so far>]`, `posted_tweet_id=<first id>`, `post_error='thread posted {N-1}/{M}: <exc>'`.
- **No automatic rollback** — we do NOT auto-delete the successfully-posted tweets on partial failure. User sees the partial state in the dashboard and decides whether to manually delete on X, manually add more tweets, or leave as-is.
- **No automatic retry** — the endpoint attempts exactly once. Retries are a new user action.
- **Frontend behavior:** `posted_partial` state shows an amber banner on the draft card with "Posted X/N tweets" + link to the first tweet + list of posted IDs + the error message.

### D8 — Authentication (from user brief Q6)
- **OAuth 1.0a User Context (4 keys).** Required for posting on a user's behalf.
  - `x_api_key` (consumer key) — already exists in config.
  - `x_api_secret` (consumer secret) — already exists in config.
  - `X_ACCESS_TOKEN` — **NEW** env var. User-scoped token from X Developer Portal.
  - `X_ACCESS_TOKEN_SECRET` — **NEW** env var. Paired with access token.
- Bearer token (`X_API_BEARER_TOKEN`) is app-auth and **cannot post** on behalf of the user. Bearer stays untouched in config (still used by the sn9-preserved gold_media X API search path).
- tweepy v2 Client construction: `tweepy.asynchronous.AsyncClient(consumer_key=..., consumer_secret=..., access_token=..., access_token_secret=...)`.
- Research phase confirms exact tweepy async Client API surface.

### D9 — Rate limits (research target, from user brief Q5)
- Research phase confirms X API v2 Basic tier POST /2/tweets limits (last public reference: ~50 writes/24h per user).
- Plan must NOT do pre-flight rate-limit checks inside the endpoint; it relies on tweepy raising `TooManyRequests` (429) and maps that to `approval_state='failed'` + `post_error='rate_limited'`. User sees the error and decides to retry later.
- If research shows Basic tier is far more restrictive than expected, flag as a discuss follow-up (but still ship the plan — the endpoint handles 429 correctly either way).

### D10 — Confirmation UX (from user brief Q8)
- **Modal-based explicit confirmation.** Button on draft card → modal opens → shows full tweet text (for single-tweet) or numbered list of tweets (for threads) → "Cancel" (left) / "Post to X" (right, primary). Second click on primary triggers the mutation.
- Modal is dismissible via Esc + clicking outside + Cancel button.
- **Rationale:** prevents misfires. Single-user internal tool but the stakes of an accidental post are high.
- **Concrete copy (frontend constant):** Title = "Post to X?" Body = "This will immediately post to your X account. You can't undo this." (no account-handle interpolation — avoids hardcoded branding; the handle is whatever the OAuth tokens resolve to). Buttons = "Cancel" / "Post to X".

### D11 — Error taxonomy (from user brief Q9)
- **`post_error` column stores structured string:** `"{code}:{message}"` — e.g., `"429:too_many_requests"`, `"401:unauthorized"`, `"403:duplicate"`, `"500:server_error"`.
- **tweepy exception mapping in `x_poster.py`:** `TooManyRequests → 429`, `Unauthorized → 401`, `Forbidden → 403`, `BadRequest → 400`, `HTTPException → 500`, `TweepyException (catch-all) → 500`.
- **Frontend** shows a red banner on draft card with humanized error message for known codes ("X rate limit hit — try again tomorrow" for 429, "Duplicate tweet — X rejected this content" for 403, etc.). Unknown codes show the raw `post_error` string.

### D12 — CLAUDE.md override scope (from user brief Q12)
- **Narrow rewrite only.** Replace the "Auto-posting to any platform" row in the "What NOT to Use" table with:
  - Column 1 (Avoid): `Unattended auto-posting to any platform`
  - Column 2 (Why): `Scheduled/cron/batch posting creates compliance and reputational risk. Every post must be explicitly user-initiated per-item via dashboard approve button (Phase B). No unattended posting regardless of trigger.`
  - Column 3 (Use Instead): `Dashboard approve→post (Phase B) for user-initiated posts. Clipboard copy for anything not postable via Phase B.`
- No broader CLAUDE.md changes.

### D13 — Draft fidelity (from user brief Q13)
- **Byte-for-byte identity between preview and post.** The text submitted to tweepy is exactly the `draft_content.tweet` field for breaking_news, or exactly the `draft_content.thread_tweets` list (joined per-tweet) for threads.
- **No silent transforms.** No truncation, emoji normalization, URL shortening, trailing-whitespace trim, or character-count coercion in x_poster.py. If the draft exceeds X's 280-char per-tweet limit, tweepy raises `BadRequest` and we surface the error.
- **Research target:** audit the current frontend preview components (ThreadPreview / BreakingNewsPreview) + the content_agent.py draft generation path to confirm no transform is applied between DB storage and preview rendering that the poster would fail to replicate.

### D14 — Dev/test posting safety
- **All unit + integration tests mock tweepy client.** No test makes a real X API call.
- `X_POSTING_ENABLED=false` default in all non-prod environments (Railway sets `X_POSTING_ENABLED=true` explicitly for prod).
- No "dry run" flag in the endpoint itself — D2's simulate-success in dev is the dry-run equivalent.
- Test file `test_x_poster.py` exercises: single-tweet success, thread happy path, thread partial failure, 429/401/403/400/500 error mapping, simulated-mode returns sim-{uuid} without calling tweepy.

### D15 — Posting target (single-account scope)
- **Single X handle per deployment.** OAuth tokens are global per-app. Whatever user the `X_ACCESS_TOKEN` resolves to is the posting target. No per-draft handle selection.
- Multi-account support (future) would need a `draft_items.target_handle` column + per-handle OAuth token storage — explicit non-goal for Phase B.

### Claude's Discretion

Not pre-locked — the planner + executor resolve these during implementation:
- Exact FastAPI route path (e.g., `POST /api/drafts/{draft_item_id}/approve-and-post` vs `POST /api/drafts/{draft_item_id}/post`). Planner picks based on existing backend route conventions (research will surface the established prefix).
- Which backend module owns `x_poster.py` — likely `backend/app/services/x_poster.py` (follows the FastAPI services pattern) but could live in `scheduler/services/` if there's a structural reason. Research confirms.
- Alembic revision number — will be whatever comes after the latest head. Research confirms `alembic current`.
- Whether `approval_state` enum is a true PostgreSQL ENUM or a `VARCHAR(16)` + CHECK constraint. Planner picks — leaning toward CHECK constraint (easier to extend via migration without enum-altering surgery).
- Exact frontend component file paths and button placement within them. Research surfaces the ThreadPreview / BreakingNewsPreview structure.
- JWT auth middleware integration — confirm existing backend auth dependency and wire it into the approve-and-post route as a dependency injection.
- Pydantic response model shape for the approve endpoint — planner designs a minimal `ApproveAndPostResponse` (fields: approval_state, posted_tweet_id, posted_tweet_ids, posted_at, post_error).

</decisions>

<specifics>
## Specific Ideas

**Reference files from the codebase (user brief + session context):**
- `scheduler/models/` — home of draft_items / content_bundles models.
- `backend/app/` (exact layout TBD by research) — home of FastAPI routes.
- `alembic/versions/` — migration dir. Latest revision confirmed by research (`alembic current`).
- `frontend/src/api/types.ts` — TypeScript types; adding new approval_state enum + response shape.
- `frontend/src/` — ThreadPreview / BreakingNewsPreview / draft card components.
- `CLAUDE.md` line: `| Auto-posting to any platform | Out of scope by design. Never implement. Even accidental partial implementation creates compliance and reputational risk for the client. | Clipboard copy + direct link only |` — this is the exact row to rewrite per D12.
- `.env.example` (if it exists; otherwise the pydantic-settings Settings class) for new env var registration.

**Tweepy reference pattern (from user brief):**
```python
import tweepy
client = tweepy.asynchronous.AsyncClient(
    consumer_key=settings.x_api_key,
    consumer_secret=settings.x_api_secret,
    access_token=settings.x_access_token,
    access_token_secret=settings.x_access_token_secret,
)
# Single tweet
resp = await client.create_tweet(text=draft_text)
tweet_id = resp.data["id"]
# Thread
prev_id = None
ids = []
for t in thread_tweets:
    kwargs = {"text": t}
    if prev_id:
        kwargs["in_reply_to_tweet_id"] = prev_id
    resp = await client.create_tweet(**kwargs)
    prev_id = resp.data["id"]
    ids.append(prev_id)
```

**Test scaffolding pattern (from content_agent.py test suite):**
- Mock tweepy AsyncClient via `unittest.mock.AsyncMock` for `create_tweet`.
- Exercise error paths by configuring the mock to raise each tweepy exception class.

**Safety behaviors that MUST be preserved verbatim:**
- `scheduler/agents/content/{breaking_news.py, threads.py, quotes.py, infographics.py, gold_media.py, gold_history.py}` — zero diff (this task does not touch drafting).
- `scheduler/agents/content_agent.py` — zero diff (Haiku gate + fetch_stories unchanged).
- `scheduler/worker.py` — zero diff (no new cron jobs).
- `scheduler/services/whatsapp.py` — zero diff.
- `scheduler/agents/senior_agent.py` — zero diff.
- `scheduler/models/` — ONLY the new columns on draft_items (no renames, no drops, no other table changes).
- `alembic/versions/` — ONLY a new forward-migration file (no edits to existing migrations).

</specifics>

<canonical_refs>
## Canonical References

- tweepy v2 async client docs: https://docs.tweepy.org/en/stable/asynchronous.html — confirm in research.
- tweepy Client.create_tweet: https://docs.tweepy.org/en/stable/client.html#tweepy.Client.create_tweet
- X API v2 POST /2/tweets endpoint: https://developer.x.com/en/docs/x-api/tweets/manage-tweets/api-reference/post-tweets
- X API v2 access levels + rate limits: https://developer.x.com/en/docs/x-api/getting-started/about-x-api
- FastAPI dependency injection patterns: https://fastapi.tiangolo.com/tutorial/dependencies/
- SQLAlchemy 2.0 row locks: https://docs.sqlalchemy.org/en/20/orm/queryguide/query.html#selecting-for-update
- APScheduler + SQLAlchemy tx boundaries (reference for concurrent-access patterns).

**Session + prior task references:**
- `CLAUDE.md` — the "What NOT to Use" table row for "Auto-posting" is the one to edit.
- `.planning/STATE.md` — post-kqa state; this task ships as next STATE row.
- `.planning/quick/260424-j5i-*/260424-j5i-CONTEXT.md` — reference for CONTEXT structure + decision-locking conventions.
- `.planning/quick/260424-i8b-*/` — reference for the prior notification/webhook pattern (similar atomic-write + DB-row state machine pattern).

</canonical_refs>
