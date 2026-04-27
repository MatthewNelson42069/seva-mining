# Quick Task 260427-k5h — gold_history slide-renderer fix — CONTEXT

**Mode:** `/gsd:quick --discuss --full`
**Date:** 2026-04-27
**Branch:** `main` (no quick-task branch — small mechanical fix)

## Bug summary

In `scheduler/agents/content_agent.py`, the function `build_draft_item()` (lines 596–688) assembles a human-readable `draft_text` blob per content_type. The `gold_history` branch (lines 635–653) iterates over `instagram_carousel` slides and renders each as:

```python
f"Slide {i + 1}: {slide.get('text', '')}"
```

But the actual slide schema (per the `gold_history.py` drafter prompt at lines 198–208) is:

```json
{"slide": 1, "headline": "...", "body": "...(max 15 words)...", "visual_note": "..."}
```

The field `text` does **not** exist. Every `slide.get('text', '')` returns `""`, so the modal shows `Slide 1:`, `Slide 2:`, …, `Slide 5:` with nothing after each colon — even though the underlying `content_bundles.draft_content.instagram_carousel` JSONB is fully populated correctly.

**Verified live:** queried Neon (the AJ Bell's Mould bundle) — all 5 slides have `headline`, `body`, `visual_note` populated. Bug is purely in the assembler.

## Scope

| Action | File | Lines | Notes |
|--------|------|-------|-------|
| MODIFY | `scheduler/agents/content_agent.py` | 635–653 | Rewrite `gold_history` branch to render `headline` + `body` + `visual_note` per slide |
| ADD    | `scheduler/tests/test_content_agent.py` | new test fn | Unit test exercising the fixed renderer with the real carousel schema |

**UNCHANGED (verified preservation in plan-check):**
- `scheduler/agents/content/gold_history.py` — drafter prompt is the source-of-truth schema; do NOT touch
- `scheduler/agents/content/{breaking_news,threads,quotes,infographics,gold_media}.py` — Q4 audit confirmed no field-name drift in their renderers
- `frontend/**` — modal consumes the assembled blob; no change needed
- `backend/**` — no API surface changes
- `alembic/**` — no schema changes

## Locked discuss-phase decisions

> The user's invocation brief recommended an answer for each gray area. Those are locked here without re-prompting because the brief itself functioned as the discussion.

### Q1 — Slide field display order
**LOCKED:** multi-line form per slide:

```
Slide N: HEADLINE
  BODY
  Visual: VISUAL_NOTE
```

Rationale: the modal has plenty of vertical space; copy-paste-into-image-generator workflow benefits from clear field labels. Compact single-line form would crowd the body sentence (max 15 words) against the visual_note (often 30+ words).

### Q2 — Display `visual_note`?
**LOCKED:** yes, with `Visual:` prefix.

Rationale: when the user copies the bundle to drive a Gemini/R2 image-render workflow (Phase 11), having `visual_note` inline is convenient. The `Visual:` prefix keeps it visually distinct from headline/body (the actual post copy) so the user isn't confused about what's render-direction vs post-copy.

### Q3 — Backfill of existing rows?
**LOCKED:** forward-fix only (option a).

Rationale: there are <20 gold_history items in the DB (every-other-day cadence × ~3 weeks). They'll age out of the queue naturally. If user wants any historical row visible, they can re-trigger a manual run. Backfill scripts add complexity disproportionate to the value at this volume. `DraftItem.alternatives[0].text` is set at draft-creation time — old rows keep the broken text; new rows render correctly.

### Q4 — Audit other format renderers for similar drift?
**LOCKED:** YES — done as part of this task (research step below).

Audit result (single-pass, drafter-prompt vs renderer field names):

| format | drafter output (source of truth) | renderer reads | match? |
|--------|----------------------------------|----------------|--------|
| breaking_news | `tweet`, optional `infographic_brief.{headline,data_points}` | `tweet`, `infographic_brief.{headline,data_points}` | ✅ |
| thread | `tweets: [str]` | `tweets` | ✅ |
| infographic | `twitter_caption`, `data_facts`, `suggested_headline`, `image_prompt` (no `charts` field) | `twitter_caption`, `charts[0].title` (dead-code fallback) | ✅ (works on real schema; `charts` fallback is dead but harmless) |
| gold_history | `tweets`, `instagram_carousel: [{slide, headline, body, visual_note}]`, `instagram_caption` | reads `slide.text` ❌ | **BROKEN** |
| gold_media | `twitter_caption`, `instagram_caption`, `source_account` | same | ✅ |
| quote | `twitter_post`, `instagram_post`, `quote_text`, `speaker`, `speaker_title` | same + speaker fallback | ✅ |

**Conclusion:** only `gold_history` has drift. No collateral fixes required. (The dead `charts[0].title` fallback in the infographic branch is left untouched — fixing it isn't a bug, it's just defensive code from the pre-split era.)

### Q5 — Function name + signature
**ANSWER:** `build_draft_item(content_bundle, rationale: str) -> DraftItem` at `scheduler/agents/content_agent.py:596`. Called by all 6 sub-agents (`scheduler/agents/content/{breaking_news,threads,quotes,infographics,gold_media,gold_history}.py`) immediately after compliance review passes.

The bug at line 647 is **not** in `_extract_check_text` (the compliance-review text extractor at line 714). `_extract_check_text` already reads `slide.headline` + `slide.body` correctly (lines 736–737), so the compliance review path is fine — it's only the persisted `draft_text` blob that's broken.

### Q6 — Consumers of the assembled `draft_text`
**ANSWER:** the only consumer is `DraftItem.alternatives = [{"type": fmt, "text": draft_text}]` (line 682). The frontend detail modal renders `alternatives[0].text` directly. WhatsApp digest formatter does NOT read this — it uses `content_bundle.story_headline` and a separate brief. So fixing this branch fixes the modal display and nothing else.

## Validation gates (FULL mode)

- `cd scheduler && uv run pytest -x` → green (existing 175+ pass + new gold_history renderer test)
- `cd scheduler && uv run ruff check .` → clean
- Preservation diff: `git diff main -- scheduler/agents/content_agent.py scheduler/tests/test_content_agent.py` shows changes ONLY in the gold_history branch + new test. Drafter (`scheduler/agents/content/gold_history.py`) untouched. Other format branches untouched.
- Manual: REPL/test-fixture round-trip with a sample `instagram_carousel` payload produces the expected multi-line output.

## Out of scope (explicit)

- Backfill of existing `draft_items.alternatives` (Q3)
- Frontend renderer changes (modal already handles multi-line `\n` correctly via `whitespace-pre-wrap`)
- Carousel JSONB schema changes
- Phase 11 image-rendering integration
- Cleaning up the dead `charts[0].title` fallback in the infographic branch

## Safety constraints

- DO NOT touch `scheduler/agents/content/gold_history.py` — drafter prompt is source of truth
- DO NOT change the carousel JSONB schema
- DO NOT modify the `_extract_check_text` function — it already reads the right fields, changes there could regress compliance review
