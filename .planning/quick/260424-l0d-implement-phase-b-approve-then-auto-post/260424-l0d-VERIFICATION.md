---
phase: 260424-l0d
verified: 2026-04-24T22:00:00Z
status: human_needed
score: 12/12 must-have truths verified, 1 deferred for human (live PG migration cycle)
re_verification:
  previous_status: none
  previous_score: n/a
gaps: []
human_verification:
  - test: "Run alembic up-down-up against a real Postgres instance (Neon dev branch)"
    expected: "DATABASE_URL=$NEON_DEV_URL alembic upgrade head && alembic downgrade -1 && alembic upgrade head all clean"
    why_human: "Local SQLite suite passes; the CHECK constraint + JSONB column require Postgres for a real cycle test. SUMMARY explicitly flags this as deferred."
  - test: "End-to-end real-mode flip with X Developer Portal credentials"
    expected: "Configure X_API_KEY/SECRET + X_ACCESS_TOKEN/SECRET (Read+Write scope), set X_POSTING_ENABLED=true, click Post to X on a breaking_news draft, confirm a real https://x.com/i/web/status/{id} link appears in the toast"
    why_human: "Requires real X Developer Portal app config and a posted tweet — cannot be programmatically verified without external service interaction."
---

# Phase B Quick Task 260424-l0d: Approve→Post-to-X — Verification Report

**Task Goal:** Implement Phase B: user-initiated per-item approve→auto-post to X via tweepy v2 OAuth 1.0a User Context. Narrow MVP: text-only `{breaking_news, thread}`. New orthogonal `approval_state` column. Atomic `POST /items/{id}/post-to-x`. Frontend "Post to X" button + confirmation Dialog. Simulated success when `X_POSTING_ENABLED=false`. CLAUDE.md narrow rewrite.

**Verified:** 2026-04-24T22:00:00Z
**Status:** human_needed (12/12 truths automatically verified; 2 items routed to user)
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| #  | Truth | Status | Evidence |
| -- | ----- | ------ | -------- |
| 1  | POST /items/{item_id}/post-to-x returns 200 with `approval_state='posted'` + `posted_tweet_id` on happy path | VERIFIED | `tests/test_post_to_x.py::test_simulate_happy_breaking_news` + `test_real_happy_breaking_news` PASS |
| 2  | Second identical POST returns 200 with `already_posted=true` and same posted_tweet_id (idempotency via SELECT FOR UPDATE + state check) | VERIFIED | `tests/test_post_to_x.py::test_idempotency_already_posted` PASS; route line 109 `if item.approval_state == ApprovalState.posted.value: return _to_response(item, already_posted=True)` |
| 3  | Thread partial-failure persists `approval_state='posted_partial'` with `posted_tweet_ids` of partial IDs and post_error populated | VERIFIED | `tests/test_post_to_x.py::test_real_thread_partial_failure` PASS; `body["post_error"].startswith("thread posted 2/3:")` asserted |
| 4  | `X_POSTING_ENABLED=false` writes `posted_tweet_id='sim-{uuid}'` WITHOUT calling tweepy — no network I/O | VERIFIED | `tests/test_post_to_x.py::test_simulate_happy_breaking_news` asserts `fake_post_single.assert_not_awaited()` and id `startswith('sim-')` |
| 5  | tweepy 429/401/403/400/5xx exceptions map to `post_error='{code}:{message}'` and `approval_state='failed'` | VERIFIED | `tests/test_x_poster.py` 5 exception tests all PASS; route writes `f"{e.code}:{e.message}"` (line 181); catch-order verified TooManyRequests→Unauthorized→Forbidden→BadRequest→HTTPException→TweepyException |
| 6  | `approval_state` column exists with NOT NULL default 'pending' and CHECK constraint limiting values to {pending, posted, failed, discarded, posted_partial} in BOTH backend + scheduler models | VERIFIED | `0009_add_x_post_state_to_draft_items.py` lines 27-65 (column + CHECK + index); `backend/app/models/draft_item.py` lines 62-68; `scheduler/models/draft_item.py` lines 60-66 (byte-identical 5 columns); `scheduler/tests/test_draft_item_model.py` parity test PASS |
| 7  | Alembic 0009 upgrades cleanly from 0008 AND downgrades cleanly back to 0008 | VERIFIED-SYNTACTIC | Migration file syntactically clean; `revision="0009"`, `down_revision="0008"`. **Live-Postgres cycle deferred to human verification** per SUMMARY. SQLite test suite (which exercises the model) passes 92/97. |
| 8  | Frontend "Post to X" button appears in ContentDetailModal footer for `content_type ∈ {breaking_news, thread}` only | VERIFIED | `ContentDetailModal.tsx` lines 58-62: `canPostToX = (contentType === 'breaking_news' || contentType === 'thread') && approval_state !== 'posted' && !== 'posted_partial'`; lines 150-158 render button |
| 9  | Confirmation Dialog opens on button click, shows full tweet text, Cancel dismisses without mutation, "Post to X" primary triggers usePostToX mutation | VERIFIED | `PostToXConfirmModal.tsx` (full Dialog + DialogTitle "Post to X?" + verbatim D10 description + Cancel/Post buttons); `__tests__/PostToXConfirmModal.test.tsx` 5 tests PASS (in 59 frontend tests overall) |
| 10 | CLAUDE.md "Auto-posting to any platform" row narrowly rewritten per D12 (unattended posting still prohibited; user-initiated per-item is now in-scope) | VERIFIED | CLAUDE.md "What NOT to Use" row: "Unattended auto-posting to any platform" — substance matches D12 with light wording flexibility (acceptable per task). New "X Developer Portal — Approve→Post-to-X Runbook" section added (allowed deviation per task instructions). |
| 11 | Preservation: git diff main against scheduler/agents/, scheduler/worker.py, scheduler/services/whatsapp.py, scheduler/agents/senior_agent.py, scheduler/agents/content_agent.py is empty | VERIFIED | `git diff main -- ...` returned no output; `git diff main -- scheduler/agents/content/ --stat` returned 0 files |
| 12 | Existing PATCH /items/{id}/approve endpoint remains unchanged and functional (orthogonal status column untouched) | VERIFIED | `backend/tests/test_queue.py` PASSED (no diff to `routers/queue.py`); `test_queue.py` only +8 lines defensive fixture update for `approval_state="pending"` (an allowed deviation) |

**Score:** 12/12 truths verified. Truth 7 has a syntactic-only verification with live-PG cycle flagged for user.

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `backend/alembic/versions/0009_add_x_post_state_to_draft_items.py` | forward + reverse migration for 5 new columns + check constraint + index | VERIFIED | 76 lines; `revision = "0009"`, `down_revision = "0008"`; upgrade adds 5 columns + CHECK constraint + index; downgrade reverses in correct order |
| `backend/app/models/draft_item.py` | SQLAlchemy model with new columns: approval_state, posted_tweet_id, posted_tweet_ids, posted_at, post_error | VERIFIED | All 5 columns added at lines 62-68 with correct types (String(16), Text, JSONB, DateTime(tz), Text) |
| `scheduler/models/draft_item.py` | identical parity — same 5 columns visible to scheduler | VERIFIED | Byte-identical 5 column definitions at lines 60-66 |
| `backend/app/services/x_poster.py` | async post_single_tweet() + post_thread() + PostError wrapper + tweepy exception mapping | VERIFIED | 119 lines; exports `post_single_tweet`, `post_thread`, `PostError`, `_build_client`, `_msg` |
| `backend/app/routers/post_to_x.py` | POST /items/{item_id}/post-to-x route, auth-gated via Depends(get_current_user) | VERIFIED | 236 lines; router has `prefix="/items"`, `dependencies=[Depends(get_current_user)]`; route at `/{item_id}/post-to-x`; uses `_build_locked_select` with `with_for_update()` |
| `backend/app/schemas/draft_item.py` | ApprovalState enum + PostToXResponse pydantic model | VERIFIED | `ApprovalState` StrEnum (5 values) at lines 17-28; `PostToXResponse` BaseModel at lines 75-90; `DraftItemResponse` extended with all 5 new optional fields |
| `backend/pyproject.toml` | tweepy[async]>=4.14 dependency added | VERIFIED | Line 21: `"tweepy[async]>=4.14",` |
| `backend/tests/test_x_poster.py` | unit tests for service: happy single, happy thread, partial thread, all tweepy exceptions | VERIFIED | 227 lines, 11 tests (all PASS): happy single/thread, partial thread, first-tweet-fail, 5 exception classes, FOR UPDATE compile |
| `backend/tests/test_post_to_x.py` | route tests: simulate happy, idempotency, 404, content-type-out-of-scope 400, partial-thread, FOR UPDATE SQL assertion | VERIFIED | 430 lines, 12 tests (all PASS): simulate BN/thread, idempotency, 404, missing-bundle 400, out-of-scope 400, real-mode happy/partial/429, auth 401, FOR UPDATE compile |
| `frontend/src/hooks/usePostToX.ts` | TanStack Query mutation hook | VERIFIED | 63 lines; exports `usePostToX(platform)`; mirrors useApprove pattern; toasts per terminal state; invalidates `['queue', platform]` |
| `frontend/src/components/approval/PostToXConfirmModal.tsx` | confirmation Dialog component reusing components/ui/dialog.tsx | VERIFIED | 91 lines; uses Dialog primitives; verbatim D10 copy "This will immediately post to your X account. You can't undo this."; Title "Post to X?"; Cancel/Post to X buttons |
| `frontend/src/api/types.ts` | ApprovalState + PostToXResponse types; DraftItemResponse extended | VERIFIED | `ApprovalState` union (5 values), `PostToXResponse` interface, `DraftItemResponse` extended with 5 optional fields |
| `CLAUDE.md` | narrowly rewritten "Auto-posting" row per D12 | VERIFIED | Row "Unattended auto-posting to any platform" with substance matching D12; additive runbook section is allowed-deviation per task |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| `backend/app/routers/post_to_x.py` | `backend/app/services/x_poster.py` | `from app.services import x_poster; await x_poster.post_single_tweet(text)` | WIRED | Line 45 imports `x_poster`; lines 176, 209 call `x_poster.post_single_tweet(text)` and `x_poster.post_thread(tweets)` |
| `backend/app/routers/post_to_x.py` | `backend/app/models/content_bundle.py` | `db.get(ContentBundle, UUID(item.engagement_snapshot['content_bundle_id']))` | WIRED | Lines 115-131 read `engagement_snapshot.content_bundle_id`, cast to UUID, `db.get(ContentBundle, bundle_uuid)`; reads `bundle.draft_content['tweet']` (BN) and `['tweets']` (thread) — NOT obsolete `draft_content` field on draft_items |
| `backend/app/routers/post_to_x.py` | `backend/app/dependencies.py` | router-level `dependencies=[Depends(get_current_user)]` | WIRED | Line 50: `dependencies=[Depends(get_current_user)]`; auth verified by `test_auth_401` |
| `backend/app/main.py` | `backend/app/routers/post_to_x.py` | `include_router(post_to_x_router)` | WIRED | Line 15: `from app.routers.post_to_x import router as post_to_x_router`; Line 61: `app.include_router(post_to_x_router)` |
| `frontend/src/components/approval/ContentDetailModal.tsx` | `frontend/src/components/approval/PostToXConfirmModal.tsx` | button onClick opens nested Dialog | WIRED | Line 13 imports PostToXConfirmModal; line 153 button onClick `setShowPostConfirm(true)`; lines 164+ render modal |
| `frontend/src/components/approval/PostToXConfirmModal.tsx` | `frontend/src/hooks/usePostToX.ts` | `mutation.mutate({id})` | WIRED | Wired from ContentDetailModal: `const postToXMutation = usePostToX(item.platform)` (line 58); `handleConfirmPost()` calls `postToXMutation.mutate({id: item.id}, ...)` (lines 77-86); modal `onConfirm={handleConfirmPost}` |
| `frontend/src/hooks/usePostToX.ts` | `frontend/src/api/queue.ts` | `postItemToX(id) → apiFetch('/api/items/{id}/post-to-x', {method: 'POST'})` | WIRED | Hook line 2 imports `postItemToX`; queue.ts line 43 `postItemToX(id) → apiFetch('/items/${id}/post-to-x', {method: 'POST'})` |

All 7 key links VERIFIED.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Backend full test suite green | `cd backend && uv run pytest -x -q` | 92 passed, 5 skipped (5 skips pre-existing, unrelated) | PASS |
| Backend ruff clean | `cd backend && uvx ruff check .` | "All checks passed!" | PASS |
| Scheduler full test suite green | `cd scheduler && uv run pytest -x -q` | 180 passed, 63 warnings (warnings pre-existing) | PASS |
| Scheduler ruff clean | `cd scheduler && uvx ruff check .` | "All checks passed!" | PASS |
| Frontend lint clean | `cd frontend && npm run lint` | exit 0, no output | PASS |
| Frontend tests green | `cd frontend && npm test -- --run` | 9 test files, 59 tests passed | PASS |
| Frontend build (incl. tsc -b) | `cd frontend && npm run build` | "✓ built in 193ms" (544 KB JS, 56 KB CSS — same chunk warning as before) | PASS |
| x_poster service unit tests | `cd backend && uv run pytest tests/test_x_poster.py -v` | 11/11 PASS | PASS |
| post_to_x route integration tests | `cd backend && uv run pytest tests/test_post_to_x.py -v` | 12/12 PASS | PASS |
| Preservation gate (scheduler + agents) | `git diff main -- scheduler/agents/ scheduler/worker.py scheduler/services/whatsapp.py scheduler/agents/senior_agent.py scheduler/agents/content_agent.py` | empty diff | PASS |
| No content/* changes (out-of-scope check) | `git diff main -- scheduler/agents/content/ --stat` | empty | PASS |

All 11 spot-checks PASS.

### Decision Audit (CONTEXT.md D1-D15)

| Decision | Where Implemented | Status |
| -------- | ----------------- | ------ |
| D1 — Phase B scope: breaking_news + thread only | `_PHASE_B_CONTENT_TYPES = {"breaking_news", "thread"}` (post_to_x.py:55); 400 returned for others (test_content_type_out_of_scope_400) | VERIFIED |
| D2 — X_POSTING_ENABLED + sim-{uuid4} | config.py default `False`; route lines 164-171 + 198-207 sim path | VERIFIED |
| D3 — SELECT FOR UPDATE + state-check idempotency | `_build_locked_select(item_id)` calls `.with_for_update()` (post_to_x.py:65); `test_for_update_compiles` asserts SQL contains "FOR UPDATE" | VERIFIED |
| D4 — Atomic single-tx posting | `async with db.begin():` envelope (post_to_x.py:96); tweepy call inside the lock | VERIFIED |
| D5 — State machine: pending/posted/failed/discarded/posted_partial | `ApprovalState` StrEnum; CHECK constraint with all 5 values | VERIFIED |
| D6 — column placement on draft_items (orthogonal to status) | All 5 columns on draft_items; status untouched; `approval_state` orthogonal per docstring | VERIFIED |
| D7 — Client-side reply-chain + partial-failure | `post_thread` returns `(ids, err)` tuple (x_poster.py:87-119); `posted_partial` written when err and ids (post_to_x.py:217-228) | VERIFIED |
| D8 — OAuth 1.0a User Context (4 keys) | `_build_client()` passes consumer_key/secret + access_token/secret; bearer NOT passed | VERIFIED |
| D9 — No pre-flight rate-limit check; rely on tweepy 429 | `tweepy.TooManyRequests` caught, mapped to 429 PostError | VERIFIED |
| D10 — Modal-based explicit confirmation | `PostToXConfirmModal` with verbatim D10 copy "This will immediately post to your X account. You can't undo this." | VERIFIED |
| D11 — `post_error = "{code}:{message}"` | All branches in post_to_x.py write `f"{e.code}:{e.message}"` (lines 181, 215) and partial path adds `"thread posted N/M: ..."` prefix | VERIFIED |
| D12 — CLAUDE.md narrow rewrite | "Unattended auto-posting" row substance matches; additive runbook section is allowed-deviation per task | VERIFIED |
| D13 — Byte-for-byte draft fidelity | Route reads `bundle.draft_content["tweet"]` / `["tweets"]` directly, no transforms; `whitespace-pre-wrap` preserved in modal | VERIFIED |
| D14 — Dev/test safety | All tests mock tweepy (`AsyncMock`); X_POSTING_ENABLED unset by default in conftest | VERIFIED |
| D15 — Single X handle per deployment | OAuth tokens are global env vars; no per-draft target_handle | VERIFIED |

### Allowed Deviations Confirmed

| Deviation | Justified? | Notes |
| --------- | ---------- | ----- |
| Additive "X Developer Portal — Approve→Post-to-X Runbook" section in CLAUDE.md | YES | Allowed per task instructions; sensible doc expansion. Substance is the 5-step prereq runbook from PLAN T5. Includes the Read+Write-before-token-regen warning (RESEARCH Pitfall 1). |
| 8-line defensive fixture update in `backend/tests/test_queue.py` (adding `approval_state="pending"`) | YES | Allowed per task instructions; necessary downstream of T1 schema change (the helper that builds DraftItem mocks needs the new field). |
| Alembic up-down-up cycle was syntactically validated but not run against live Postgres | YES | Flagged as "human-verify recommended" not blocker per task instructions. SUMMARY explicitly notes this with command for Neon dev branch. |

### Anti-Patterns Found

None. The route uses correct patterns:
- Catch-order specific-before-generic (TooManyRequests→Unauthorized→Forbidden→BadRequest→HTTPException→TweepyException)
- Single transaction (`async with db.begin():`)
- `with_for_update()` for row lock
- UUID cast on `engagement_snapshot["content_bundle_id"]` (Pitfall 8)
- `bundle.draft_content["tweet"]` / `["tweets"]` (correct field per RESEARCH)
- All tests mock tweepy (zero network I/O)
- Idempotent short-circuit before tweepy call

### Requirements Coverage

| Requirement | Description | Status | Evidence |
| ----------- | ----------- | ------ | -------- |
| PHASE-B-D1 | content-type scope: breaking_news + thread text-only | SATISFIED | _PHASE_B_CONTENT_TYPES set; 400 returned for others |
| PHASE-B-D2 | X_POSTING_ENABLED feature flag + simulate mode | SATISFIED | config.py + route branches |
| PHASE-B-D3 | SELECT FOR UPDATE + state-check idempotency | SATISFIED | `_build_locked_select` + idempotency short-circuit |
| PHASE-B-D4 | atomic posting trigger model | SATISFIED | `async with db.begin():` envelope |
| PHASE-B-D5 | approval_state machine (5 values) | SATISFIED | ApprovalState StrEnum + CHECK constraint |
| PHASE-B-D6 | column placement on draft_items (orthogonal to status) | SATISFIED | All 5 columns on draft_items, status unmodified |
| PHASE-B-D7 | client-side thread reply-chain + partial-failure semantics | SATISFIED | post_thread tuple return + posted_partial state |
| PHASE-B-D8 | OAuth 1.0a User Context (4 keys) | SATISFIED | _build_client passes 4 OAuth1 keys, no bearer |
| PHASE-B-D9 | rate limits: rely on tweepy 429 | SATISFIED | TooManyRequests → 429 PostError |
| PHASE-B-D10 | modal-based explicit confirmation UX | SATISFIED | PostToXConfirmModal w/ verbatim copy |
| PHASE-B-D11 | error taxonomy "{code}:{message}" | SATISFIED | All exception paths use this format |
| PHASE-B-D12 | CLAUDE.md narrow rewrite | SATISFIED | Row rewritten + additive runbook (allowed) |
| PHASE-B-D13 | byte-for-byte draft fidelity | SATISFIED | Direct field reads, no transforms |
| PHASE-B-D14 | dev/test safety: mock tweepy + default false | SATISFIED | All tests use AsyncMock; conftest doesn't set X_POSTING_ENABLED |
| PHASE-B-D15 | single X handle per deployment | SATISFIED | OAuth env vars are global |

All 15 requirements SATISFIED.

### Human Verification Required

#### 1. Live-Postgres Migration Cycle

**Test:** Run alembic up-down-up against a real Postgres instance (Neon dev branch).
**Command:** `DATABASE_URL=$NEON_DEV_URL cd backend && uv run alembic upgrade head && uv run alembic downgrade -1 && uv run alembic upgrade head`
**Expected:** All three commands succeed cleanly with no errors. Verify the 5 columns + CHECK constraint + index exist after upgrade and are gone after downgrade.
**Why human:** Local SQLite cannot enforce CHECK constraints + JSONB types. The migration is syntactically clean and the model parity tests pass, but a real Postgres cycle is the only way to confirm prod-equivalent behavior. SUMMARY.md explicitly flags this as deferred.

#### 2. End-to-End Real-Mode Posting

**Test:** Configure X Developer Portal app with Read+Write permissions per CLAUDE.md runbook, generate Access Token after Read+Write toggle, set 4 X env vars + X_POSTING_ENABLED=true on Railway, redeploy backend, click Post to X on a real breaking_news draft.
**Expected:** Confirmation modal opens with full tweet text → click "Post to X" → toast appears with "Posted to X — View on X" action; clicking action opens a real https://x.com/i/web/status/{numeric_id} URL (NOT sim-prefixed). DB row shows `approval_state='posted'` with the real numeric posted_tweet_id.
**Why human:** Requires real X Developer Portal credentials, real Railway deployment, and creates a real tweet. Cannot be programmatically verified without external service interaction. The simulate-mode + mocked-tweepy test suite covers all the code paths; this last gate proves the auth/network plumbing.

### Gaps Summary

No gaps found. All 12 must-have truths are automatically verified, all 13 required artifacts exist with substantive implementations, all 7 key links are wired, all 15 D-decisions are correctly implemented, and all test gates (backend pytest, scheduler pytest, frontend lint+test+build, both ruff suites, preservation gate) pass.

The only items not auto-verified are:
1. Live Postgres alembic up-down-up cycle (deferred to human, per task instructions)
2. Real X API posting flow (requires external X Developer Portal config + a real tweet)

Both are listed in `human_verification:` for the user to action.

---

## Verdict

**Status: human_needed** — Phase B implementation is complete and correct against all 12 must-have truths, all 13 required artifacts, all 7 key links, all 15 decisions, and all 11 test gates. Two items legitimately require external resources (live Postgres + real X Developer Portal) and are routed to the user for confirmation. No code-level gaps remain.

The codebase is ready to merge to main once the user confirms (a) the alembic migration cycles cleanly against the Neon dev branch, and (b) — when ready — the live-mode flip with real X credentials posts a real tweet end-to-end. The simulate-mode default makes (b) entirely opt-in; the rest of the system is safe to ship without it.

---

_Verified: 2026-04-24T22:00:00Z_
_Verifier: Claude (gsd-verifier, opus 4.7)_
_Worktree: /Users/matthewnelson/seva-mining/.claude/worktrees/agent-a98a47fd_
_Branch: worktree-agent-a98a47fd_
