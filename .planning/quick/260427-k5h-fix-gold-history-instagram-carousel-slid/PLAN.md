# Quick Task 260427-k5h — gold_history slide-renderer fix — PLAN

**Goal:** Replace the broken `slide.get('text', '')` reader at `scheduler/agents/content_agent.py:647` with a multi-line render of `headline` + `body` + `visual_note`. Add a regression test.

**Success criterion:** A unit test feeds a realistic `instagram_carousel` payload through `build_draft_item()`, the resulting `alternatives[0].text` contains every slide's headline, body, and visual_note in the locked multi-line format. `pytest -x` and `ruff check .` both green.

## Tasks

### T1 — Fix the gold_history branch in `build_draft_item`

**File:** `scheduler/agents/content_agent.py`
**Lines:** 635–653

**Current (broken):**
```python
elif fmt == "gold_history":
    tweets = draft.get("tweets", [])
    carousel = draft.get("instagram_carousel", [])
    parts = []
    if tweets:
        parts.append("=== Thread ===\n" + "\n\n".join(str(t) for t in tweets if t))
    if carousel:
        parts.append(
            "=== Instagram Carousel ===\n"
            + "\n\n".join(
                f"Slide {i + 1}: {slide}"
                if isinstance(slide, str)
                else f"Slide {i + 1}: {slide.get('text', '')}"
                for i, slide in enumerate(carousel)
            )
        )
    draft_text = (
        "\n\n".join(parts) if parts else f"Gold History: {draft.get('story_title', '')}"
    )
```

**Replacement:** extract per-slide rendering into a small inline helper that handles three cases:
1. `slide` is a `dict` with the real schema → `Slide N: HEADLINE\n  BODY\n  Visual: VISUAL_NOTE` (each field omitted from output if missing/empty, but the `Slide N:` prefix is always present)
2. `slide` is a `str` (legacy/defensive path that pre-existed) → `Slide N: <str>`
3. anything else → `Slide N:` (empty)

**Implementation sketch:**

```python
elif fmt == "gold_history":
    tweets = draft.get("tweets", [])
    carousel = draft.get("instagram_carousel", [])
    parts = []
    if tweets:
        parts.append("=== Thread ===\n" + "\n\n".join(str(t) for t in tweets if t))
    if carousel:
        slide_lines = []
        for i, slide in enumerate(carousel):
            prefix = f"Slide {i + 1}:"
            if isinstance(slide, str):
                slide_lines.append(f"{prefix} {slide}")
                continue
            if not isinstance(slide, dict):
                slide_lines.append(prefix)
                continue
            headline = (slide.get("headline") or "").strip()
            body = (slide.get("body") or "").strip()
            visual = (slide.get("visual_note") or "").strip()
            block = [f"{prefix} {headline}" if headline else prefix]
            if body:
                block.append(f"  {body}")
            if visual:
                block.append(f"  Visual: {visual}")
            slide_lines.append("\n".join(block))
        parts.append("=== Instagram Carousel ===\n" + "\n\n".join(slide_lines))
    draft_text = (
        "\n\n".join(parts) if parts else f"Gold History: {draft.get('story_title', '')}"
    )
```

Edge-case behavior:
- A slide missing `headline` but having `body`/`visual` still renders (just without the headline on the prefix line)
- A slide that's a bare string still works (legacy compat)
- An empty carousel falls through to the `Gold History: {story_title}` fallback
- The `===` section delimiters and inter-slide `\n\n` blank line are preserved (frontend depends on `whitespace-pre-wrap`)

**Validation:** unit test below + manual REPL with the live AJ Bell's Mould bundle's `draft_content` JSONB.

---

### T2 — Add regression test

**File:** `scheduler/tests/test_content_agent.py`
**Location:** append a new test function near the existing `test_build_draft_item_stores_bundle_id_in_engagement_snapshot` at line 349.

**Test name:** `test_build_draft_item_gold_history_renders_carousel_slides`

**Coverage:**
1. Build a MagicMock bundle with realistic `draft_content`:
   - `format: "gold_history"`
   - `story_title`, `story_slug`, `tweets: ["...", "..."]`
   - `instagram_carousel: [{slide: 1, headline: "...", body: "...", visual_note: "..."}, ...]` × 5 slides
2. Call `content_agent.build_draft_item(bundle, "rationale")`
3. Assert `item.alternatives[0]["text"]` contains:
   - The string `"=== Instagram Carousel ==="`
   - Every slide's headline
   - Every slide's body
   - Every slide's visual_note (with `Visual:` prefix)
   - The string `"=== Thread ==="` (since tweets are also present)
4. Assert NO empty `Slide N:` lines (i.e., the bug regression — `Slide 1:\n\nSlide 2:\n\n...` would be the broken output)

**Bonus assertion:** add a second sub-test (or a separate test fn) that passes a slide WITHOUT `headline` (just `body` + `visual_note`) and confirms the renderer still produces output for that slide rather than silently dropping it.

**Why this test catches the bug:** the broken renderer reads `slide.get('text')` which always returns `None` → empty. The new test asserts headline/body/visual_note text appears in the output, which is impossible with the broken code.

---

### T3 — Validation gates

1. `cd scheduler && uv run pytest -x` → green
2. `cd scheduler && uv run ruff check .` → clean
3. `git diff main -- scheduler/agents/content/ scheduler/agents/content_agent.py scheduler/tests/` → only the gold_history branch + new test
4. Manual REPL check (optional): paste a sample carousel into the new function, eyeball the output

---

### T4 — Commit

Single atomic commit. Message style follows the repo's recent convention (lowercase scope, imperative, references quick-task ID):

```
fix(content_agent): render gold_history carousel slides correctly (k5h)

The gold_history branch of build_draft_item assembled per-slide text by
reading slide.get('text', ''), but the actual carousel schema produced by
sub_gold_history is {slide, headline, body, visual_note} — there is no
'text' field. Net effect: the dashboard detail modal showed `Slide 1:`,
`Slide 2:`, ..., `Slide 5:` with nothing after each colon, even though
the underlying content_bundles.draft_content.instagram_carousel JSONB
was fully populated.

Render each slide as:

    Slide N: HEADLINE
      BODY
      Visual: VISUAL_NOTE

Each field is omitted from output if absent. Legacy string-slide compat
is preserved.

_extract_check_text already reads slide.headline + slide.body correctly
(line 736), so compliance review was unaffected — only the persisted
draft_text blob was broken.

Forward-fix only — existing rows aren't backfilled (volume too low to
justify a script). New rows from the next every-other-day cron tick
render correctly.

Audited the other 5 format renderers (breaking_news, thread, infographic,
gold_media, quote) against their drafter prompts; no other field-name
drift found.
```

---

## Plan-checker scope (FULL mode)

The plan-checker should verify:
1. The replacement code preserves the `=== Thread ===` and `=== Instagram Carousel ===` section markers (frontend rendering depends on these)
2. The slide loop falls through to the `Gold History: {story_title}` fallback when both `tweets` and `carousel` are empty
3. The new test's MagicMock bundle has all the fields `build_draft_item` reads (`story_headline`, `story_url`, `source_name`, `score`, `quality_score`, `id`)
4. No accidental modification of `_extract_check_text` (line 714) — that function is correct and out-of-scope
5. The commit message style matches the recent quick-task convention (`fix(scope): summary (slug)`)

## Verifier scope (FULL mode)

Goal-backward check:
- Did the goal (carousel slides display content in the modal) actually get achieved? Test must prove `alternatives[0].text` contains real slide content.
- Did the fix introduce ANY behavior change for the 5 other formats? Diff must show 0 changes outside the gold_history branch.
- Are existing tests still green?
