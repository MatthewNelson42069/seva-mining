---
status: passed
---

# Verification — 260424-i8b

**Task goal:** Split WhatsApp notifications into per-run firehose (sub_breaking_news + sub_threads) and 12:30 PT midday digest (infographics + quotes + gold_media + gold_history with SQL-enforced exclusion).

**Verified against commit:** 9c783f0 (feat) + 3704c8d (docs) + 8b02684 (merge)

---

## Truth 1 — Per-run hook gating

**Claim:** Hook fires ONLY for `sub_breaking_news` + `sub_threads` AND `items_queued > 0`. Inserted after `agent_run.status = "completed"`. Empty runs send nothing.

**Evidence:**

`scheduler/agents/content/__init__.py` L383–416:

- `_persisted_items: list[str] = []` initialized at L154 alongside `items_queued = 0`.
- Accumulator appended at L331–336 inside `if compliance_ok:` block, gated by `if agent_name in {"sub_breaking_news", "sub_threads"}:`.
- Dispatch block inserted at L384–416, immediately after `agent_run.status = "completed"` (L383), before the surrounding `except Exception as exc:` at L417.
- Gate on L388: `if agent_name in {"sub_breaking_news", "sub_threads"} and items_queued > 0:` — the `items_queued > 0` condition guarantees empty runs send nothing.
- `whatsapp` import at L34: `from services import whatsapp`.

**Tests confirming:** `test_per_run_hook_fires_for_breaking_news_with_items_queued_gt_zero`, `test_per_run_hook_fires_for_threads_with_items_queued_gt_zero`, `test_per_run_hook_skipped_for_other_agents`, `test_per_run_hook_skipped_when_items_queued_zero` — all passing.

**verdict: pass**

---

## Truth 2 — Midday digest + runtime filter

**Claim:** Digest fires at 12:30 America/Los_Angeles. Content ENFORCED-EXCLUDED at SQL query layer inside `_assemble_digest` via `content_type` filter.

**Evidence:**

`scheduler/worker.py` L350–357:
```python
scheduler.add_job(
    _make_midday_digest_job(engine),
    trigger=CronTrigger(
        hour=12,
        minute=30,
        timezone="America/Los_Angeles",
    ),
    id="midday_digest",
    name="Midday Digest — daily at 12:30 America/Los_Angeles",
)
```
Old `morning_digest` id and `hour=7` are absent from the file. `JOB_LOCK_IDS` at L96 shows `"midday_digest": 1005`.

`scheduler/agents/senior_agent.py` L112–122 — `_firehose_exists_subq` NOT EXISTS subquery built once from `ContentBundle.story_url == DraftItem.source_url` and `ContentBundle.content_type.in_(self._excluded_content_types)`. Applied via `.where(~_firehose_exists_subq)` on all 4 DraftItem queries (approved L134–135, rejected L149–150, expired L164–165, top_stories L180–181). Guard at L113: `if self._excluded_content_types:` — skipped when empty (back-compat).

This is enforced at SQL level — not documentation-only. The subquery is inside the ORM `.where()` clause, not a post-fetch Python filter.

**Tests confirming:** `test_digest_is_registered_as_midday_at_1230_pt`, `test_assemble_digest_excludes_firehose_content_types` — both passing. The senior_agent test verifies the compiled SQL contains `content_type` or `content_bundles`.

**verdict: pass**

---

## Truth 3 — Chunking contract

**Claim:** `send_agent_run_notification` chunks at ≤1500 chars/chunk on tweet boundaries. Single-chunk: NO `[agent 1/1]` prefix. Multi-chunk: `[<short> X/N]` prefix on every chunk.

**Evidence:**

`scheduler/services/whatsapp.py` L109–154 (`build_chunks`):

- `short_name = agent_name.removeprefix("sub_")` at L130 — strips prefix for header.
- Single item header: `f"[{short_name}] {n} approved:"` — no chunk number.
- Greedy packing loop L140–146: appends `current` to `chunks` when `len(tentative) > max_chunk_chars`, starts new chunk with bare `block` (no repeated header).
- Single-chunk early return at L149–150: `if len(chunks) == 1: return chunks` — NO `[X/N]` prefix added.
- Multi-chunk path L153–154: `return [f"[{short_name} {i}/{total}]\n{c}" for i, c in enumerate(chunks, start=1)]` — every chunk gets `[short X/N]` prefix.

`send_agent_run_notification` L157–198: iterates chunks sequentially, returns SIDs. Early exit on `sid is None` (credentials missing) without sending remaining chunks.

**Tests confirming:** 8 tests in `test_whatsapp.py` — single-chunk no-prefix, multi-chunk prefix format, never-split-item, 1500-char budget, short name stripping, dispatch order, empty items short-circuit, creds-missing early stop — all passing.

**verdict: pass**

---

## Truth 4 — Failure mode + JSON notes merge

**Claim:** Twilio failure is silent-continue. `agent_run.status` stays `completed`. ERROR log emitted. `whatsapp_per_run_*` keys JSON-merged into `agent_run.notes` (NOT string concat).

**Evidence:**

`scheduler/agents/content/__init__.py` L391–415:

- Dispatch is inside its own `try/except Exception as wa_exc:` (L391/403) — entirely separate from the outer `except Exception as exc:` at L417 that sets `status = "failed"`. A `TwilioRestException` is caught at L403, not L417.
- On exception: `logger.error(...)` at L404–408 (ERROR level confirmed).
- `whatsapp_status_key = "whatsapp_per_run_failed"` at L409.
- Notes merge at L413–415:
  ```python
  existing_notes = json.loads(agent_run.notes) if agent_run.notes else {}
  existing_notes[whatsapp_status_key] = whatsapp_status_val
  agent_run.notes = json.dumps(existing_notes)
  ```
  This is a dict update + `json.dumps`, never string concatenation.
- Same merge logic applies to `whatsapp_per_run_sent` (L401–402) and `whatsapp_per_run_skipped` (L398–399).

**Tests confirming:** `test_per_run_hook_twilio_failure_is_silent` — asserts `agent_run.status == "completed"`, `json.loads(agent_run.notes)` is a dict, contains both `"candidates"` AND `"whatsapp_per_run_failed"`. `test_per_run_hook_success_merges_into_notes_dict` — asserts JSON dict contains `"whatsapp_per_run_sent"` alongside `"candidates"`. Both passing.

**verdict: pass**

---

## Truth 5 — Zero-diff + narrow-diff preservation

**Zero-diff gate (git diff main~3 main -- <paths>):**

```
scheduler/agents/content/breaking_news.py  — EMPTY (no output)
scheduler/agents/content/threads.py        — EMPTY
scheduler/agents/content/quotes.py         — EMPTY
scheduler/agents/content/infographics.py   — EMPTY
scheduler/agents/content/gold_media.py     — EMPTY
scheduler/agents/content/gold_history.py   — EMPTY
scheduler/agents/content_agent.py          — EMPTY
backend/                                   — EMPTY
frontend/                                  — EMPTY
alembic/                                   — EMPTY
```

All 6 sub-agent modules, `content_agent.py`, `backend/`, `frontend/`, `alembic/` show zero diff vs main~3. VERIFIED.

**Narrow-diff gate (git diff main~3 main -- scheduler/agents/senior_agent.py):**

Lines changed — exactly and only:

1. `+from models.content_bundle import ContentBundle` — new import (Path A subquery)
2. `def __init__(self) -> None` → `def __init__(self, excluded_content_types: frozenset[str] | None = None) -> None` — new kwarg
3. `+ self._excluded_content_types: frozenset[str] = excluded_content_types or frozenset()` — assignment + comment
4. `_firehose_exists_subq = None` + `if self._excluded_content_types:` + subquery construction block (L112–122) — filter setup
5. 4x refactor of `await session.execute(...)` to `_q = (...)\n_q = _q.where(...)\nresult = await session.execute(_q)` for approved, rejected, expired, top_stories — minimal structural change required to apply the conditional `.where()`.

Lines NOT changed: `run_morning_digest` function name (retained), WhatsApp template body (`📊 Morning Digest`), `_headline_from_rationale`, `_get_config`, `seed_senior_config`, `DailyDigest` write, per-agent send pattern, try/except structure. VERIFIED.

Note: The query refactor from inline `await session.execute(...)` to `_q = (...)` with conditional `.where()` is classified as permitted — it is mechanically required to apply a conditional filter clause and introduces no logic change. The diff shows no other lines touched.

**verdict: pass**

---

## Test results

```
Full suite:   166 passed, 55 warnings, 0 failures, 0 errors
Targeted:     49 passed (tests/test_whatsapp.py + test_worker.py + test_senior_agent.py + test_content_wrapper.py)
ruff check .: All checks passed (clean)
```

The 55 warnings are pre-existing unawaited coroutine RuntimeWarnings in mock setup, unrelated to this task.

---

## Summary

All 5 truths verified. The implementation matches every contract in the PLAN exactly:

- Per-run hook is in the correct location (after `agent_run.status = "completed"`, before the outer `except`), gated correctly, silent on empty runs.
- Digest fires at 12:30 PT with `id="midday_digest"` and `JOB_LOCK_IDS["midday_digest"] = 1005` (no lock churn). Runtime SQL filter via NOT EXISTS subquery on `ContentBundle.content_type` — enforcement is in SQL, not just a constant.
- Chunking correctly omits `[1/1]` prefix for single chunks and applies `[short X/N]` for multi-chunk. `build_chunks` is a pure helper; `send_agent_run_notification` stops on `None` SID.
- Twilio failures are caught in an inner `try/except`, status remains `"completed"`, and notes are JSON-merged (dict update, not string concat).
- All 6 sub-agent modules + `content_agent.py` + `backend/` + `frontend/` + `alembic/` are zero-diff. `senior_agent.py` narrow-diff shows only the 5 permitted change categories.

**Status: passed — all 5 truths verified, 166 tests green, all preservation gates empty.**
