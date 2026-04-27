# Quick Task 260427-k5h — gold_history slide-renderer fix — SUMMARY

**Shipped:** 2026-04-27
**Workflow:** `/gsd:quick --discuss --full`
**Branch:** `main` (no quick-task branch — small mechanical fix)

## What changed

| File | Change | Lines |
|------|--------|-------|
| `scheduler/agents/content_agent.py` | Rewrote the `gold_history` branch of `build_draft_item()` (lines 635–653 → 635–668). Replaced broken `slide.get('text', '')` with multi-line render of `headline` + `body` + `visual_note`. | +27 / -8 |
| `scheduler/tests/test_content_agent.py` | Added 4 regression tests + 1 helper (`_make_gold_history_bundle`). | +130 / 0 |

**Total:** +157 / -8 across 2 files.

## Why

The dashboard detail modal for `gold_history` items showed `Slide 1:`, `Slide 2:`, …, `Slide 5:` with empty text after each colon — even though the underlying `content_bundles.draft_content.instagram_carousel` JSONB was fully populated with correct `headline` / `body` / `visual_note` for every slide. Verified live via Neon SQL on the AJ Bell's Mould bundle: every slide field present and populated.

Root cause: pure backend assembler bug in `build_draft_item()`. The `gold_history` branch iterated over slides reading `slide.get('text', '')`, but the schema produced by `scheduler/agents/content/gold_history.py:198-208` is `{slide, headline, body, visual_note}` — there is no `text` field. Every read returned `""`.

The compliance-review path (`_extract_check_text` at line 714) was unaffected — it already reads `slide.headline + slide.body` correctly at lines 736–737. Only the persisted `DraftItem.alternatives[0].text` blob (which the modal displays) was broken.

## Locked discuss-phase decisions

- **Q1 — slide display format:** multi-line, each field on its own indented line — `Slide N: HEADLINE\n  BODY\n  Visual: VISUAL_NOTE`. Plenty of vertical modal space + benefits the copy-paste-into-image-generator workflow.
- **Q2 — include `visual_note`:** yes, with `Visual:` prefix to distinguish render-direction from post-copy.
- **Q3 — backfill existing rows:** NO. Forward-fix only. <20 existing rows; they age out naturally. Backfill scripts disproportionate to the value.
- **Q4 — audit other format renderers for similar drift:** YES, done inline. **Result: only `gold_history` had drift.** Every other format renderer matches its drafter's output schema (`breaking_news`/`thread`/`infographic`/`gold_media`/`quote`). The dead `charts[0].title` fallback in the infographic branch is harmless and left alone.

## Validation

- `cd scheduler && uv run pytest -x` → **184 passed** (180 prior + 4 new), 0.95s
- `cd scheduler && uv run ruff check .` → clean
- Preservation diff: `git diff main -- scheduler/agents/content/ scheduler/agents/senior_agent.py scheduler/services/whatsapp.py backend/ frontend/ alembic/ scheduler/models/` returns 0 bytes (drafter `gold_history.py` untouched, other 5 sub-agents untouched, frontend untouched, backend untouched, schema unchanged)
- Manual REPL with the live-prod schema (3-slide payload) produced:

  ```
  === Thread ===
  Gold has not peaked. History suggests this rally has further to run.

  1971 ended the gold standard. The price has been discovering its level ever since.

  === Instagram Carousel ===
  Slide 1: Gold Has Not Peaked
    History says the biggest move may still be ahead.
    Visual: Full-bleed warm cream #F0ECE4 background. Bold serif headline.

  Slide 2: 1971 Set the Stage
    Nixon shock ended the gold standard, freeing the price.
    Visual: Vintage newspaper clipping motif, sepia tone.

  Slide 3: Today Looks Different
    Real rates positive, dollar strong, yet gold rallies.
    Visual: Side-by-side chart: gold vs DXY.
  ```

  Matches the locked Q1/Q2 spec exactly.

## Why this slipped through

The pre-existing `test_build_draft_item_stores_bundle_id_in_engagement_snapshot` only exercised the `breaking_news` branch — no `gold_history` coverage in the renderer. The 4 new tests close that gap and serve as the regression guard.

## Post-deploy

- After Railway picks this up, the next every-other-day `sub_gold_history` cron tick (12:00 PT) will write a new ContentBundle whose `DraftItem.alternatives[0].text` renders the carousel correctly. Existing rows still show the broken text and will age out of the queue naturally.
- If user wants any specific historical row visible, they can manually re-trigger a run, but no automation is planned.

## Follow-ups

- None. The infographic branch's dead `charts[0].title` fallback is unchanged — defensive code from the pre-split era; not a bug.
