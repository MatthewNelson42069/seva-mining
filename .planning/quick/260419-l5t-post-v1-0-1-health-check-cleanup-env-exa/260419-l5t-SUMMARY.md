---
task: 260419-l5t
type: quick
completed: 2026-04-19
duration: ~60 min
commits:
  - 8bfdfea — fix(quick-l5t): rebuild .env.example + add scheduler/.env symlink
  - 1103fd5 — style(quick-l5t): ruff --fix backend + scheduler (zero lint errors)
  - 6c70d8a — style(quick-l5t): frontend eslint zero — shadcn carve-out + DigestPage useEffect + 3 fixes
  - effc75e — feat(quick-l5t): JWT_SECRET length validator in backend Settings
metrics:
  backend_ruff: "213 → 0"
  scheduler_ruff: "27 → 0"
  frontend_eslint: "7 → 0"
  backend_tests: "69 → 71 passed (5 skipped)"
  scheduler_tests: "115 passed"
  frontend_tests: "74 passed"
---

# Quick Task 260419-l5t: Post-v1.0.1 Health-Check Cleanup Summary

## One-liner

Rebuilt `.env.example` to the 20 vars the code actually reads, wired `scheduler/.env -> ../.env`, drove `ruff check` and `npm run lint` to zero across all three projects, and added a Pydantic v2 `@field_validator("jwt_secret")` that refuses to boot with a JWT_SECRET shorter than 32 bytes.

## Per-task Results

### Task 1 — Rebuild `.env.example` + add `scheduler/.env` symlink

- **Commit:** `8bfdfea` — 1 file changed
- **Before:** `.env.example` had 15 keys including 6 vestigial (`RESEND_API_KEY`, `GOOGLE_NEWS_API_KEY`, `DIGEST_EMAIL_TO`, `REDDIT_CLIENT_ID/SECRET/USER_AGENT`) and missed 10 keys the code actually reads (`JWT_SECRET`, `DASHBOARD_PASSWORD`, `DIGEST_WHATSAPP_TO`, `SERPAPI_API_KEY`, `GEMINI_API_KEY`, `R2_ACCOUNT_ID/ACCESS_KEY_ID/SECRET_ACCESS_KEY/BUCKET/PUBLIC_BASE_URL`). Scheduler process had no `.env` of its own, so `cd scheduler && python worker.py` broke.
- **After:** `.env.example` documents exactly 20 vars in 6 sections (Required: Core infra / Auth / Agent APIs, Optional: WhatsApp / Image rendering, Dev). `scheduler/.env` is a symlink to `../.env` so both services load the same env; the root `.gitignore` `.env` entry already matches it (confirmed via `git check-ignore scheduler/.env`). Verified end-to-end: `cd scheduler && set -a && source .env && set +a && uv run python -c "from config import get_settings; s=get_settings(); print(bool(s.database_url))"` prints `True`.

### Task 2 — Ruff zero, backend + scheduler

- **Commit:** `1103fd5` — 58 files changed
- **Before:** backend 213 errors (178 auto-fixable), scheduler 27 errors (18 auto-fixable). Breakdown: import sort, `typing.Optional` → `str | None`, `datetime.timezone.utc` → `datetime.UTC`, unused imports, line-too-long, module-import-not-at-top, `class Foo(str, Enum)` → `class Foo(StrEnum)`, `Keyword.active == True` → `Keyword.active.is_(True)`, a handful of unused test fixtures.
- **After:** both projects exit 0.
  - `ruff --fix` auto-resolved 204 backend + 18 scheduler.
  - Manual fixes: reflowed 7 comment/declaration lines in models and one alembic migration; added `# noqa: E501` on 10 test-file lines where reflow hurt readability; added `# noqa: E402` on 10 conftest / SQLite-shim imports that deliberately follow env-setup / monkey-patch blocks; swapped `DraftStatus(str, Enum)` and `DraftStatusEnum(str, Enum)` for `StrEnum`; replaced two SQLAlchemy `Keyword.active == True` / `Watchlist.active == True` with `.is_(True)`; dropped unused `original_execute` assignment and prefixed 6 documentation-only test-fixture items with `_` to silence F841. `backend/app/config.py` and a test-env var fixture were also brought along by the import-sort pass — this is why Task 2 touches them (the Task 4 semantic change stacks on top cleanly).
  - Tests unchanged: backend 69 passed, scheduler 115 passed.

### Task 3 — ESLint zero, frontend

- **Commit:** `6c70d8a` — 5 files changed
- **Before:** 7 errors across 6 files (3× react-refresh/only-export-components in shadcn `badge.tsx`/`button.tsx`/`tabs.tsx`; 1× set-state-in-effect in `DigestPage.tsx:154`; 1× set-state-in-effect in `InlineEditor.tsx:27`; 1× impure `Date.now()` in `RenderedImagesGallery.tsx:41`; 1× unused-var `_relatedId` in `RelatedCardBadge.tsx:16`).
- **After:** 0 errors, 74 tests passing, `tsc --noEmit` clean, `npm run build` succeeds (bundle 561.27 kB raw / 167.02 kB gzip — unchanged).
  - `eslint.config.js`: added `files: ['src/components/ui/**']` carve-out disabling `react-refresh/only-export-components` (3 errors).
  - `DigestPage.tsx`: dropped `latestDate` state — now derived as `latestQuery.data?.digest_date ?? null`. Replaced prop-sync `useEffect` with a derived `effectiveDate = currentDate ?? latestDate`. `handlePrev`/`handleNext` now compute a `base = currentDate ?? latestDate` so navigation works even before the user's first click. `isNextDisabled` became `!effectiveDate || effectiveDate === latestDate` (keeps the test expecting "Next disabled while showing latest" green).
  - `InlineEditor.tsx`: replaced `useEffect(() => setEditValue(text) ...)` with the officially-recommended "Storing information from previous renders" pattern — a `prevText` state and a setState-during-render guard.
  - `RenderedImagesGallery.tsx`: the newer `react-hooks/purity` rule rejects `Date.now()` even inside `useMemo`. Replaced with a lazy `useState` initializer (runs once at mount) that captures whether the bundle is within the 10-minute polling window, plus a `useEffect` one-shot `setTimeout` that flips it to `false` when the window closes.
  - `RelatedCardBadge.tsx`: removed the unused `relatedId` prop from the interface and the destructure (component is not currently referenced anywhere else — verified via grep).

### Task 4 — JWT_SECRET length validator

- **Commit:** `effc75e` — 5 files changed
- **Behavior:** `Settings()` now raises `pydantic.ValidationError` when `len(JWT_SECRET) < 32`. The error message includes the actual length (`got 25`), so the failure mode is self-diagnosing.
- **RED → GREEN:**
  - RED: added `test_jwt_secret_valid_length_passes` (32-byte boundary) and `test_jwt_secret_too_short_raises` (25-byte rejected with `JWT_SECRET must be at least 32 bytes` + `"25"` in message). `test_jwt_secret_too_short_raises` failed as expected (`DID NOT RAISE`).
  - GREEN: added `@field_validator("jwt_secret")` in `backend/app/config.py` raising `ValueError(f"JWT_SECRET must be at least 32 bytes for SHA256 HMAC security (got {len(v)})")` when `len(v) < 32`.
- **Collateral fixture updates:** test suites use short JWT_SECRETs in monkeypatched env vars. Updated:
  - `backend/tests/conftest.py` — `_TEST_JWT_SECRET` from 25 to 32 bytes.
  - `backend/tests/test_config.py::test_settings_loads_from_env` — `JWT_SECRET` fixture from `"jwtsecrettest"` (13) to `"a" * 32`.
  - `backend/tests/test_database.py` — `JWT_SECRET` monkeypatched env from `"jwtsecret"` (9) to `"a" * 32`.
  - `backend/tests/test_whatsapp.py` — `Settings(jwt_secret=...)` literal from `"test-jwt-secret"` (15) to `"a" * 32`.
- **Tests:** `pytest tests/test_config.py -q` → 4 passed; full suite `pytest -q` → 71 passed (69 + 2 new).

## Final Metrics

| Metric             | Before | After | Delta |
| ------------------ | -----: | ----: | ----: |
| Backend ruff       |    213 |     0 |  −213 |
| Scheduler ruff     |     27 |     0 |   −27 |
| Frontend ESLint    |      7 |     0 |    −7 |
| Backend pytest     |     69 |    71 |    +2 |
| Scheduler pytest   |    115 |   115 |     0 |
| Frontend vitest    |     74 |    74 |     0 |
| `.env.example` keys (vestigial) | 6 |  0 | −6 |
| `.env.example` keys (total)     | 15 | 20 | +5 |

## Operator Action Required After Merge

**None — false alarm (corrected 2026-04-19 post-merge).**

Initial summary claimed the local `backend/.env` JWT_SECRET was 25 bytes and would block backend boot after this task. Verified live after merge: the real value in `backend/.env` is **64 chars / 32 bytes of entropy**, which passes the new validator cleanly. `cd backend && uv run python -c "from app.main import app"` boots with 27 routes, no ValidationError.

The original misread traced to the `InsecureKeyLengthWarning: The HMAC key is 25 bytes long` warning that appeared in `pytest` output. That warning was emitted by the `pyjwt` library inside test fixtures which set a shorter placeholder (`"dev-secret-change-me-abc12"`, 25 chars) for isolated test runs — not from the real `.env`. Tests continue to pass because the Task 4 fixture updates (`conftest.py`, `test_config.py`, `test_database.py`, `test_whatsapp.py`) bumped those placeholders to `"a" * 32`.

**If you ever want to rotate the JWT_SECRET for good hygiene**, the one-liner is still: `openssl rand -hex 32` → paste into `backend/.env` as the new `JWT_SECRET` value. Existing issued JWTs become invalid after rotation, but this is a single-user tool, so just log in again. Not required — current secret is fine.

## Files Touched (per commit)

**`8bfdfea` (1 file):**
- `.env.example`

**`1103fd5` (58 files):** 47 backend files (ruff-driven across `app/`, `alembic/`, `scripts/`, `tests/`) + 11 scheduler files (`agents/`, `models/`, `tests/`, `worker.py`). Summary: auto-sorted imports, swapped `Optional[T]` for `T | None`, upgraded two enums to `StrEnum`, normalised SQLAlchemy column-truth comparisons, reflowed long lines or added scoped `# noqa` where reflow degraded readability.

**`6c70d8a` (5 files):**
- `frontend/eslint.config.js`
- `frontend/src/pages/DigestPage.tsx`
- `frontend/src/components/approval/InlineEditor.tsx`
- `frontend/src/components/content/RenderedImagesGallery.tsx`
- `frontend/src/components/shared/RelatedCardBadge.tsx`

**`effc75e` (5 files):**
- `backend/app/config.py`
- `backend/tests/test_config.py`
- `backend/tests/conftest.py`
- `backend/tests/test_database.py`
- `backend/tests/test_whatsapp.py`

## Deviations from Plan

1. **[Rule 2 — Critical] Frontend lint rules stricter than plan assumed.** Plan proposed `useMemo` in `RenderedImagesGallery` and a `useRef + setState-during-render` pattern in `InlineEditor`. The project's active ESLint config includes newer `react-hooks/purity`, `react-hooks/refs`, and `react-hooks/rules-of-hooks` rules that also reject both patterns (impure `Date.now()` inside `useMemo`; ref mutation during render). Replaced with:
   - `RenderedImagesGallery`: lazy `useState` initializer + `useEffect` one-shot timer (captures `Date.now()` exactly once at mount, never during a render pass).
   - `InlineEditor`: "Storing information from previous renders" pattern (two `useState` calls, no ref, no effect).
   Both are officially sanctioned React patterns. No behavior change.
2. **[Rule 3 — Blocking] Test fixtures had short JWT_SECRETs that would fail the new validator.** Plan anticipated this ("update that fixture's JWT_SECRET to `'a' * 32`"). Updated 4 files (`conftest.py`, `test_config.py`, `test_database.py`, `test_whatsapp.py`) in the Task 4 commit since they are logically part of "enforcing the validator without breaking the suite". Included them in the `feat` commit rather than splitting them off.
3. **[Minor] `DigestPage` next-button-disabled behavior subtly changed.** Before the refactor, `currentDate === latestDate` was `null === null = true` while both values were unloaded, so the Next button was disabled-at-startup. After dropping `latestDate` state, `currentDate` stays `null` while `latestDate = "YYYY-MM-DD"` once data loads, so the comparison is `null === "..."  = false` and the button becomes enabled. Test `"next button disabled at latest date"` caught this. Fix: `isNextDisabled = !effectiveDate || effectiveDate === latestDate`, which is the correct semantics ("no digest yet OR already at the latest"). All 9 DigestPage tests green.
4. **[Observation, not a change]** `.env.example` actually contains 20 KEY=value lines, but the plan's verify regex `^[A-Z_]\+=` misses keys with digits (`R2_*`, `X_API_*`). Used `^[A-Z_][A-Z0-9_]*=` instead and confirmed exactly 20.

## Self-Check: PASSED

- [x] `.env.example` contains 20 documented env vars (Required: Core / Auth / Agent APIs, Optional: WhatsApp / Image rendering, Dev) with zero vestigial keys.
- [x] `scheduler/.env` is a symlink to `../.env` and matches the root `.gitignore` entry.
- [x] `backend/app/config.py` contains `@field_validator("jwt_secret")` raising `ValueError` when `len(v) < 32`.
- [x] `backend/tests/test_config.py` contains both new tests; all 4 tests in that file pass.
- [x] `frontend/eslint.config.js` contains the `src/components/ui/**` carve-out.
- [x] Backend `ruff check .` → 0 errors. Scheduler `ruff check .` → 0 errors. Frontend `npm run lint` → 0 errors.
- [x] Backend `pytest -q` → 71 passed. Scheduler `pytest -q` → 115 passed. Frontend `npm test -- --run` → 74 passed.
- [x] Frontend `tsc --noEmit` clean. Frontend `npm run build` succeeds (561.27 kB / 167.02 kB gzip).
- [x] All 4 commits present in `git log --oneline -5` with the expected conventional-commit prefixes and hashes (`8bfdfea`, `1103fd5`, `6c70d8a`, `effc75e`).
- [x] `.env`, `backend/.env`, `scheduler/.env` not committed (verified: `scheduler/.env` is a symlink matched by `.gitignore`'s `.env` entry; no `.env` files appear in any of the 4 commits' diffs).
