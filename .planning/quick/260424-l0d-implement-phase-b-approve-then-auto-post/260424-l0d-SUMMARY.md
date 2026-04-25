---
phase: 260424-l0d
plan: 01
type: execute
status: complete
completed: 2026-04-24
branch: worktree-agent-a98a47fd
commits:
  - 50c43d4 feat(backend): alembic 0009 + dual-model parity for x post-state (l0d)
  - 7d6a9ff feat(backend): x_poster service + 11 unit tests (l0d)
  - add1f1e feat(backend): POST /items/{id}/post-to-x route + integration tests (l0d)
  - 39dc9ee feat(frontend): Post-to-X button + confirm modal + state badges (l0d)
  - 7abb171 docs(claude): scope auto-posting rule + X Developer Portal runbook (l0d)
files_changed: 24
insertions: 1709
deletions: 8
tests:
  backend: 92 passed, 5 skipped (unrelated)
  frontend: 59 passed
preservation_gate: passed (empty diff against scheduler/agents/, scheduler/worker.py, scheduler/services/whatsapp.py)
---

# Phase B (quick-260424-l0d) — Approve→Post-to-X Summary

User-initiated approve→post-to-X capability for two text-only content types
(`breaking_news`, `thread`) with atomic state-machine transitions, OAuth
1.0a User Context posting via `tweepy.AsyncClient`, irreversibility-safe
confirmation UX, and a feature-flagged simulate mode for safe iteration in
dev/staging.

## What Shipped

### Backend

- **Alembic migration `0009_add_x_post_state_to_draft_items.py`** — adds
  five columns to `draft_items` (`approval_state` VARCHAR(16) NOT NULL
  DEFAULT 'pending', `posted_tweet_id` VARCHAR(32), `posted_tweet_ids`
  JSONB, `posted_at` TIMESTAMPTZ, `post_error` TEXT) plus a CHECK
  constraint limiting `approval_state` to the 5-value enum and a partial
  index on `(approval_state)` WHERE `approval_state != 'pending'` to keep
  the dashboard's post-state filter cheap. Forward and reverse migrations
  use `op.batch_alter_table` for SQLite compatibility (Pitfall 1) and the
  upgrade is idempotent against partial reruns.
- **Dual-model parity** — `backend/app/models/draft_item.py` and
  `scheduler/models/draft_item.py` both gain the same 5 columns. The
  scheduler model is read-only with respect to these columns (no agent
  writes them) but must include them so the scheduler's SELECTs don't
  throw on missing-column errors after the migration.
- **Config flag** — `X_POSTING_ENABLED: bool = False` and
  `X_POSTING_SIM_PREFIX: str = "sim-"` added to both `app/config.py` and
  `scheduler/config.py`. The route reads the flag via `get_settings()` so
  the lru_cache must be cleared between tests that toggle it
  (`conftest.py` autouse fixture handles this).
- **`x_poster` service** (`backend/app/services/x_poster.py`) — wraps
  `tweepy.AsyncClient` OAuth 1.0a with two entry points:
  - `post_single_tweet(text) -> str` for breaking_news
  - `post_thread(tweets) -> tuple[list[str], PostError | None]` for thread
    posts; returns `(ids_so_far, error_or_None)` so the route can
    distinguish first-tweet failure (no IDs) from mid-thread failure
    (some IDs + error).
  - `PostError(code, message)` dataclass wraps tweepy exceptions
    (`TooManyRequests`, `Unauthorized`, `Forbidden`, `BadRequest`,
    `TwitterServerError`, generic `TweepyException`) into the
    `"{code}:{message}"` format persisted to `draft_items.post_error`.
- **`POST /items/{item_id}/post-to-x` route**
  (`backend/app/routers/post_to_x.py`) — auth-gated via
  `Depends(get_current_user)` at the router level. Single transaction
  flow:

      BEGIN
      SELECT * FROM draft_items WHERE id = $1 FOR UPDATE
      -- short-circuit on already-posted (idempotency)
      -- resolve content_bundle via engagement_snapshot.content_bundle_id
      -- branch on bundle.content_type (breaking_news | thread only)
      -- simulate-mode: write `sim-{uuid4()}` ID without calling tweepy
      -- real-mode: call x_poster.post_single_tweet / post_thread
      -- write approval_state + posted_* columns (success or failure)
      COMMIT

  The lock is held through the tweepy round-trip — acceptable for a
  single-user internal tool. `statement_timeout=15s` is the worst-case
  upper bound. The `_build_locked_select` helper is exposed so tests can
  compile the same statement and assert that the generated postgres SQL
  contains `FOR UPDATE` (SQLite no-ops the lock at runtime, so we test
  the syntactic intent against the postgresql dialect).
- **Phase B scope guard** — content_type ∉ {breaking_news, thread}
  returns 400 with the message `content_type 'X' out of scope for Phase
  B; supported: breaking_news, thread`. Quotes + gold_history (B.5) and
  media-bearing types (B+) are explicit non-goals.

### Frontend

- **Types** (`frontend/src/api/types.ts`) — `ApprovalState` union
  (`'pending' | 'posted' | 'failed' | 'discarded' | 'posted_partial'`),
  `PostToXResponse` interface, and 5 new optional fields on
  `DraftItemResponse` so the queue surface can render post-state.
- **API client** (`frontend/src/api/queue.ts`) — `postItemToX(id)` →
  `POST /items/{id}/post-to-x` returning `PostToXResponse`.
- **`usePostToX` hook** — TanStack Query mutation toasting per terminal
  state: `posted` → success "Posted to X" with View on X action;
  `posted_partial` → warning "Thread posted partially" with first-tweet
  link; `failed` → error toast with `post_error`; `already_posted` →
  info toast (no-op idempotent re-call). All non-sim tweet IDs get a
  clickable `https://x.com/i/web/status/{id}` action; sim-IDs do not.
  Invalidates `['queue', platform]` on success.
- **`PostToXConfirmModal`** — read-only preview rendering breaking_news
  as a single block and threads as a numbered list, with the verbatim D6
  warning text "This will immediately post to your X account. You can't
  undo this." Cancel + "Post to X" buttons disable while pending; button
  label flips to "Posting…" during the in-flight request.
- **`ContentDetailModal`** — gates a "Post to X" footer button on
  contentType ∈ {breaking_news, thread} AND approval_state ∉ {posted,
  posted_partial}. The close button is suppressed when the Post-to-X
  button is shown (cleaner footer layout); when hidden, the standard
  close button returns. Pulls preview text from `bundle.draft_content`
  (`tweet` for breaking_news, `tweets` array for thread).
- **`ContentSummaryCard`** — post-state badges next to the format badge.
  Color mapping: green for `posted`, amber for `posted_partial`, red
  for `failed`, neutral for `discarded`. `pending` shows no badge by
  design — the absence is the pending signal.

### Tests

- **`backend/tests/test_x_poster.py`** — 11 unit tests covering happy
  single-tweet, happy thread, mid-thread failure, all 5 tweepy exception
  classes mapped to PostError, OAuth init from config.
- **`backend/tests/test_post_to_x.py`** — 12 integration tests covering
  simulate-mode happy paths (BN + thread), idempotent re-call,
  404-on-missing, missing/invalid bundle 400s, out-of-scope
  content_type 400, real-mode happy paths (mocked tweepy), 429 →
  failed state, partial-thread → posted_partial state, auth 401, and
  `_build_locked_select` SQL compile assertion proving `FOR UPDATE` is
  in the generated postgres SQL.
- **`scheduler/tests/test_draft_item_model.py`** — model parity test
  proving the scheduler model exposes the same 5 new columns.
- **`frontend/src/components/approval/__tests__/PostToXConfirmModal.test.tsx`**
  — 5 component tests covering both content types, action handlers,
  pending state, and closed state.

### Docs

- **CLAUDE.md "What NOT to Use" rewrite** — the single row "Auto-posting
  to any platform" is replaced with "Unattended auto-posting to any
  platform". The new row separates the actual risk profile (scheduled or
  agent-driven posting with no human in the loop — permanently out of
  scope) from user-initiated approve→post-to-X (now explicitly in
  scope). Names the new route, the supported content_types, and keeps
  the "never expose 'post all queued'" prohibition intact.
- **X Developer Portal Runbook** — 5-step setup, with the sequencing
  constraint that matters: app User authentication settings flipped to
  Read+Write **before** Access Token regen (otherwise the regenerated
  tokens silently carry only Read scope and `tweepy.create_tweet()`
  returns 403). Documents `X_POSTING_ENABLED` env-var rollback path
  (toggle to false → route reverts to writing sim-IDs without redeploy).

## Decisions Made (CONTEXT.md trace)

| ID  | Decision                                                                    | Where it landed |
| --- | --------------------------------------------------------------------------- | --------------- |
| D1  | Phase B scope: breaking_news + thread only                                  | `_PHASE_B_CONTENT_TYPES` set in `post_to_x.py` |
| D2  | `X_POSTING_ENABLED` flag + `sim-{uuid4}` IDs in simulate mode               | `config.py` + route branches |
| D3  | `SELECT ... FOR UPDATE` row lock + state-check idempotency                  | `_build_locked_select` helper |
| D4  | Atomic flow: single transaction holds lock through tweepy round-trip       | `async with db.begin():` block |
| D5  | State machine: `pending → posted | failed | discarded | posted_partial`     | `ApprovalState` StrEnum |
| D6  | Post-state columns on `draft_items` (orthogonal to `status`)                | Migration 0009 + dual-model parity |
| D7  | Mid-thread failure → `posted_partial`, no auto-rollback                     | Thread branch in route |
| D8  | OAuth 1.0a User Context (4 keys, not Bearer)                                | `x_poster.py` AsyncClient init |
| D9  | No pre-flight rate-limit check; rely on tweepy 429                          | `PostError` mapping for `TooManyRequests` |
| D10 | Modal-based explicit confirmation                                           | `PostToXConfirmModal` |
| D11 | `post_error = "{code}:{message}"` format                                    | All branches in route |
| D12 | CLAUDE.md narrow row rewrite                                                | T5 commit `7abb171` |
| D13 | Byte-for-byte draft fidelity (no silent transforms)                         | Route reads `bundle.draft_content` verbatim |
| D14 | Dev/test safety: all tests mock tweepy; `X_POSTING_ENABLED=false` default   | conftest fixture + test design |
| D15 | Single X handle per deployment                                              | OAuth env-var triplet, no per-account routing |

## Verification Gates

- Backend tests: `92 passed, 5 skipped` (skipped are pre-existing,
  unrelated to l0d).
- Frontend tests: `59 passed`.
- TypeScript: `tsc -b` clean.
- ESLint: clean.
- Frontend build: `vite build` green (`544 KB` JS bundle, gzipped 164 KB
  — same chunk-size warning as before, not introduced by this work).
- Preservation gate: `git diff main -- scheduler/agents/ scheduler/worker.py scheduler/services/whatsapp.py scheduler/agents/senior_agent.py scheduler/agents/content_agent.py` is empty.

## Deferred to a Follow-Up Quick Task

- **Alembic up-down-up cycle against PostgreSQL** — the migration was
  validated at the syntactic level (forward + reverse SQL inspected,
  dual-model parity tests passing) but not run end-to-end against a
  Postgres instance from this worktree session because no local Postgres
  was available. The migration uses `op.batch_alter_table` for SQLite
  compatibility but the `CHECK` constraint and `JSONB` column require
  Postgres for a real cycle test. Recommend running
  `DATABASE_URL=$NEON_DEV_URL alembic upgrade head && alembic downgrade -1 && alembic upgrade head`
  against the Neon dev branch once before merging to main.
- **Phase B.5** — quotes + gold_history support. Out of scope by
  decision D1; the route's content_type guard returns 400 for these
  formats today.
- **Phase B+** — media-bearing types (gold_media, infographic). Need
  `tweepy.upload_media` plumbing and a different draft_content shape;
  not started.

## How to Flip from Simulate to Real

1. Complete the X Developer Portal Runbook in CLAUDE.md (5 steps).
2. Set `X_API_KEY`, `X_API_SECRET`, `X_ACCESS_TOKEN`,
   `X_ACCESS_TOKEN_SECRET` in Railway env (the API service, not the
   scheduler — only the API process posts).
3. Set `X_POSTING_ENABLED=true` in Railway env.
4. Redeploy the API service (env-var changes require a restart for
   `get_settings()`'s lru_cache to repopulate).
5. Open a draft in the dashboard, click "Post to X", confirm. The toast
   should link to a real `https://x.com/i/web/status/{tweet_id}` URL.
6. To roll back: unset `X_POSTING_ENABLED` (or set to `false`) and
   redeploy. The route reverts to writing sim-IDs immediately.
