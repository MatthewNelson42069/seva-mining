---
task: 260422-lbb
type: quick
mode: execute
branch_from: main
base_commit: a1ea13c
worktree_branch: quick/260422-lbb-gold-history-curated-whitelist
files_modified:
  - scheduler/agents/content/gold_history.py
  - scheduler/agents/content/gold_history_stories/__init__.py
  - scheduler/agents/content/gold_history_stories/*.json  # ≥10 NEW files
  - scheduler/tests/test_gold_history.py
autonomous: true
requirements: [quick-260422-lbb]
must_haves:
  truths:
    - "gold_history.run_draft_cycle() produces drafts grounded ONLY in pre-verified fact sheets — no Claude-from-memory story picking"
    - "Every factual claim surfaced in a gold_history draft traces back to a source_url in the curated fact-sheet JSON"
    - "Drafter prompt contains the verbatim FACT FIDELITY clause forbidding invention of names/dates/numbers"
    - "Drafter output includes a top-level `sources` field mirroring the fact-sheet sources (deduplicated, with ref labels)"
    - "At least 10 canonical gold-industry stories are seeded as committed JSON fact sheets"
    - "Legacy leakage paths (_pick_story Claude-from-memory + _verify_facts SerpAPI runtime verification) are fully removed — not just commented out"
    - "Full scheduler test suite remains green (no regression from the 101-test baseline)"
  artifacts:
    - path: "scheduler/agents/content/gold_history_stories/__init__.py"
      provides: "load_all_stories() loader + per-story schema validation"
      exports: ["load_all_stories", "load_fact_sheet", "STORIES_DIR"]
    - path: "scheduler/agents/content/gold_history_stories/*.json"
      provides: "≥10 curated fact sheets, one per canonical story"
      contains: "story_slug, story_title, summary, verified_facts[{claim, source_url, published_date}], sources[{ref, url, publisher, accessed_date}], tags, recommended_arc"
    - path: "scheduler/agents/content/gold_history.py"
      provides: "Curated-whitelist run_draft_cycle — no Claude-picker, no SerpAPI runtime verification"
      contains: "_pick_fresh_slug, _load_fact_sheet, _draft_gold_history with FACT FIDELITY clause"
    - path: "scheduler/tests/test_gold_history.py"
      provides: "Updated test suite covering the new flow (≥5 new tests, retired _pick_story/_verify_facts tests)"
      contains: "test_whitelist_loads_all_stories, test_pick_fresh_slug_excludes_used, test_pick_fresh_slug_returns_none_when_all_used, test_draft_gold_history_includes_sources_field, test_draft_gold_history_prompt_contains_fact_fidelity_clause"
  key_links:
    - from: "scheduler/agents/content/gold_history.py::run_draft_cycle"
      to: "scheduler/agents/content/gold_history_stories/__init__.py::load_all_stories"
      via: "import + _pick_fresh_slug call"
      pattern: "load_all_stories|from .gold_history_stories"
    - from: "scheduler/agents/content/gold_history.py::_draft_gold_history"
      to: "fact_sheet.verified_facts"
      via: "prompt-embedded verified_facts list + FACT FIDELITY clause"
      pattern: "FACT FIDELITY"
    - from: "scheduler/agents/content/gold_history.py::run_draft_cycle"
      to: "ContentBundle.draft_content"
      via: "draft_content dict includes `sources` top-level field"
      pattern: "\"sources\""
---

<objective>
Replace `gold_history.py`'s Claude-picks-from-memory + SerpAPI-runtime-verification pipeline with a curated-whitelist flow: stories are pre-researched and committed as JSON fact sheets, Claude only *drafts* from them (locked to the verified_facts list by an explicit FACT FIDELITY clause). This eliminates the hallucination risk identified in the zid debug follow-up and satisfies the user's "100% true story" bar.

Purpose: The current flow asks Claude to pick a gold-industry story from its training data and then asks SerpAPI to verify the claims — both steps are leakage paths. Claude can invent names/dates/dollar figures in the draft even when the picker is sound, and SerpAPI keyword overlap is not semantic verification. The only way to guarantee accuracy is to pre-ground the drafter on reviewed material.

Output: A new `gold_history_stories/` directory with ≥10 committed fact-sheet JSONs; a rewritten `gold_history.py` that loads from the whitelist; updated tests; single atomic commit on a worktree branch.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
</execution_context>

<context>
@.planning/quick/260422-lbb-harden-gold-history-py-so-it-only-produc/260422-lbb-CONTEXT.md
@scheduler/agents/content/gold_history.py
@scheduler/agents/content/quotes.py
@scheduler/tests/test_gold_history.py
@scheduler/models/content_bundle.py

<interfaces>
<!-- Key contracts the executor needs. Extracted from the current codebase. -->
<!-- Use these directly — no further codebase exploration needed. -->

From scheduler/agents/content_agent.py (unchanged, called inline):
```python
async def review(draft: dict) -> dict:
    # Haiku compliance gate. Returns {"compliance_passed": bool, "rationale": str, ...}

def build_draft_item(content_bundle, rationale: str):
    # Creates DraftItem for the approval queue. platform='content', urgency='low'.
```

From scheduler/models/content_bundle.py (unchanged — JSONB fields, no migration needed):
```python
class ContentBundle:
    story_headline: Text               # = story_title
    content_type: String(50)           # = "gold_history"
    score: Numeric(5,2)                # = GOLD_HISTORY_SCORE (8.0)
    no_story_flag: Boolean
    deep_research: JSONB               # NEW shape: {"story_slug": ..., "sources": [...]}
    draft_content: JSONB               # drafter output dict, now includes top-level "sources"
    compliance_passed: Boolean
```

From scheduler/agents/content/gold_history.py (to be retained):
```python
CONTENT_TYPE = "gold_history"
AGENT_NAME  = "sub_gold_history"
GOLD_HISTORY_SCORE = 8.0
async def _get_used_topics(session) -> list[str]   # KEEP unchanged
async def _add_used_topic(session, slug) -> None   # KEEP unchanged
```

From scheduler/agents/content/gold_history.py (to be deleted — do NOT keep behind a flag):
```python
async def _pick_story(used_topics, *, client) -> dict | None       # DELETE
async def _verify_facts(key_claims, *, serpapi_client) -> list[dict]  # DELETE
```

Fact-sheet JSON schema (authoritative — from CONTEXT.md §Specific Ideas):
```json
{
  "story_slug": "bre-x-busang-fraud-1997",
  "story_title": "...",
  "summary": "1-2 sentence hook for the picker",
  "tags": ["fraud", "1990s", "exploration"],
  "recommended_arc": "Hook → rising → climax → payoff (one line)",
  "verified_facts": [
    {"claim": "...", "source_url": "https://...", "published_date": "YYYY-MM-DD"}
  ],
  "sources": [
    {"ref": "[1]", "url": "...", "publisher": "...", "accessed_date": "2026-04-22"}
  ]
}
```

New drafter output shape (preserves existing contract, adds `sources`):
```json
{
  "format": "gold_history",
  "story_title": "...",
  "story_slug": "...",
  "tweets": ["hook tweet", "..."],
  "instagram_carousel": [
    {"slide": 1, "headline": "...", "body": "...(≤15 words)...", "visual_note": "..."}
  ],
  "instagram_caption": "...",
  "sources": [{"ref": "[1]", "url": "...", "publisher": "..."}]
}
```
</interfaces>
</context>

<research_guidance>
**This task is front-loaded with factual research.** Seeding ≥10 fact sheets is the bulk of the executor's work. Estimate ~30-40% of task time on research alone.

**Recommended research pattern per story:**
1. `WebSearch` for `{story_slug_phrase} wikipedia` (e.g. `"Bre-X Minerals Busang fraud wikipedia"`)
2. `WebFetch` the Wikipedia URL. Extract 5-7 concrete factual claims with the wiki URL as `source_url`. Facts must be specific: names, dates, dollar figures, place names, percentages. NO general background statements like "gold mining is important."
3. `WebSearch` for 1-2 supplementary authoritative sources (contemporaneous news, SEC filings, LBMA archives, academic write-ups, Financial Post / Reuters / Bloomberg retrospectives). `WebFetch` each and pull ≥1 additional claim per source.
4. Deduplicate sources into the top-level `sources: []` array with `ref` labels `[1]`, `[2]`, etc.
5. Tag the story (`fraud`, `1990s`, `exploration`, `market-event`, `company-build`, `central-bank`, etc.).
6. Write a one-line `recommended_arc` (hook → rising → climax → payoff).
7. Validate the JSON file against the loader schema before moving on.

**Minimum floor per story:** 5 verified_facts, 1 source_url per fact, ≥2 deduplicated sources overall.

**Target seed set (pick ≥10 from this list — from CONTEXT.md §D-02):**
- Bre-X Minerals fraud (1997 Busang, Indonesia)
- Frank Giustra / GoldCorp 1994 founding
- Peter Munk / Barrick Gold founding (1983, reverse-merger)
- Hunt brothers silver corner (1979-80 "Silver Thursday")
- Klondike Gold Rush (1896-99)
- Nixon closes the gold window (August 15, 1971)
- Newmont Mining / Carlin Trend Goldstrike
- South African gold mines (Witwatersrand discovery, 1886)
- California Gold Rush (1848-55)
- USSR dumps gold to destabilize market (1960s)
- Russia's post-Soviet gold reserves accumulation
- China's strategic gold reserve buildup (2000s-2010s)
- Venezuela's gold repatriation attempt (2011, Chavez)
- Germany's gold repatriation from NY Fed (2013-2017)
- SPDR Gold Trust (GLD) launch 2004
- LBMA London Fix scandal (2014 manipulation probe)
- Swiss referendum on gold reserves (2014, rejected)
- Zimbabwe gold-backed currency ZiG (2024)

Pick 10-12 that have rich Wikipedia articles + strong secondary sources. Favor stories with clear dramatic arcs (Bre-X, Hunt brothers, Nixon, Klondike, Bre-X) over thinly-documented ones.
</research_guidance>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Build whitelist loader + seed ≥10 fact-sheet JSONs + rewrite gold_history.py + update tests (single atomic task)</name>

  <files>
    scheduler/agents/content/gold_history_stories/__init__.py  # NEW
    scheduler/agents/content/gold_history_stories/*.json       # NEW — ≥10 files
    scheduler/agents/content/gold_history.py                   # REWRITE (keep _get_used_topics/_add_used_topic)
    scheduler/tests/test_gold_history.py                       # UPDATE
  </files>

  <behavior>
    Test expectations — write or update these FIRST (RED), then implement (GREEN). Baseline: 101 tests. Retire 3 old tests (test_pick_story_returns_parsed_json, test_pick_story_returns_none_on_parse_failure, test_pick_story_sends_used_list_to_claude), update test_module_surface (remove _pick_story/_verify_facts, add _pick_fresh_slug/_load_fact_sheet), add ≥5 new tests. Net: 101 - 3 + ≥5 = ≥103 tests.

    New tests to add (per CONTEXT.md §Specific Ideas):
    - `test_whitelist_loads_all_stories` — `load_all_stories()` returns ≥10 entries; every entry has required keys (`story_slug`, `story_title`, `summary`, `verified_facts`, `sources`); every item in `verified_facts` has a non-empty `source_url`; every item in `sources` has `url` and `publisher`.
    - `test_pick_fresh_slug_excludes_used` — given a whitelist of [slugA, slugB, slugC] and used_topics=[slugA, slugB], `_pick_fresh_slug` returns `slugC`.
    - `test_pick_fresh_slug_returns_none_when_all_used` — given whitelist=[slugA] and used_topics=[slugA], returns None.
    - `test_load_fact_sheet_returns_dict_for_valid_slug` — given a real seeded slug, returns a dict with all required keys.
    - `test_load_fact_sheet_raises_or_returns_none_for_unknown_slug` — planner choice (None is fine) — assert the behavior matches impl.
    - `test_draft_gold_history_includes_sources_field` — mock Claude response returning JSON with `sources`; assert drafter output dict has non-empty `sources` list.
    - `test_draft_gold_history_prompt_contains_fact_fidelity_clause` — capture the call_args, assert the string "FACT FIDELITY" appears in the composed prompt (system or user message).

    Updated `test_module_surface` expectations:
    - `_pick_story` and `_verify_facts` are NOT attributes of the module (use `hasattr` / `getattr(..., None)`).
    - `_pick_fresh_slug`, `_load_fact_sheet`, `_draft_gold_history`, `_get_used_topics`, `_add_used_topic`, `run_draft_cycle` ARE callable attributes.
  </behavior>

  <action>
    **Step 1 — Create the worktree branch from main at a1ea13c:**

    ```bash
    cd /Users/matthewnelson/seva-mining
    git fetch origin main
    git worktree add -b quick/260422-lbb-gold-history-curated-whitelist \
      /tmp/seva-260422-lbb a1ea13c
    cd /tmp/seva-260422-lbb
    ```

    **Step 2 — Build the loader helper FIRST (the contract other work depends on):**

    Create `scheduler/agents/content/gold_history_stories/__init__.py` with:
    - `STORIES_DIR = Path(__file__).parent` constant.
    - `REQUIRED_STORY_KEYS = ("story_slug", "story_title", "summary", "verified_facts", "sources")`.
    - `REQUIRED_FACT_KEYS = ("claim", "source_url")` — `published_date` is optional (some historical events have fuzzy dates); `source_url` is MANDATORY.
    - `REQUIRED_SOURCE_KEYS = ("url", "publisher")` — `ref` + `accessed_date` recommended but not enforced (keeps loader tolerant).
    - `def _validate_story(data: dict, filename: str) -> None` — raises `ValueError(f"{filename}: missing key {k}")` for any missing required key; raises if `verified_facts` is empty or any fact lacks `source_url`; raises if `sources` is empty.
    - `def load_all_stories() -> list[dict]` — iterates `STORIES_DIR.glob("*.json")`, skips `__init__.py`-style non-data files, loads each JSON, validates, returns the list of dicts sorted by `story_slug` (deterministic order for tests).
    - `def load_fact_sheet(slug: str) -> dict | None` — reads `STORIES_DIR / f"{slug}.json"`; returns the validated dict, or None if the file doesn't exist. Uses `load_all_stories()` cache is fine OR direct file read — either is acceptable.
    - Module docstring: explain the curated-whitelist contract, cite `quick-260422-lbb`, link back to CONTEXT.md decision IDs D-01 through D-05.

    **Step 3 — Research + write ≥10 fact-sheet JSONs (BULK OF THE WORK):**

    For each story (≥10 from the seed list in the research_guidance section above), follow the research pattern:
    1. WebSearch `"{story phrase} wikipedia"` (e.g. `"Bre-X Minerals Busang fraud wikipedia"`).
    2. WebFetch the Wikipedia URL. Extract 5-7 specific factual claims (names, dates, dollar figures, place names, percentages). Each gets the wiki URL as `source_url`.
    3. WebSearch 1-2 supplementary authoritative sources (contemporaneous news, SEC filings, LBMA archives, Financial Post / Reuters / Bloomberg retrospectives, academic writeups). WebFetch each, pull ≥1 claim per source.
    4. Build the dedup'd `sources: []` array with `[1]`, `[2]`, ... refs.
    5. Tag the story.
    6. Write the one-line `recommended_arc`.
    7. Save as `scheduler/agents/content/gold_history_stories/{story_slug}.json` with UTF-8, 2-space indent.

    **Floor per story: ≥5 verified_facts, each with a non-empty source_url, ≥2 dedup'd sources.**

    After all ≥10 are written, run this grep invariant to gut-check:

    ```bash
    python3 -c "
    import json, pathlib
    for p in pathlib.Path('scheduler/agents/content/gold_history_stories').glob('*.json'):
        d = json.loads(p.read_text())
        assert d['verified_facts'], f'{p.name}: empty verified_facts'
        for f in d['verified_facts']:
            assert f.get('source_url'), f'{p.name}: fact missing source_url — {f}'
        assert len(d['sources']) >= 1, f'{p.name}: empty sources'
        print(f'{p.name}: OK — {len(d[\"verified_facts\"])} facts, {len(d[\"sources\"])} sources')
    "
    ```

    **Step 4 — Rewrite `scheduler/agents/content/gold_history.py`:**

    Preserve (do NOT modify):
    - Top-of-file constants: `CONTENT_TYPE`, `AGENT_NAME`, `GOLD_HISTORY_SCORE`.
    - `_get_used_topics(session)` and `_add_used_topic(session, slug)` — these Config helpers are correct and unchanged.

    Delete (remove completely — do NOT leave commented-out):
    - `_pick_story` function — entire `async def _pick_story` block.
    - `_verify_facts` function — entire `async def _verify_facts` block.
    - The `serpapi` import (if only used by `_verify_facts`).
    - The `serpapi_client = serpapi.Client(api_key=settings.serpapi_api_key)` line in `run_draft_cycle`.

    Add:
    ```python
    import random
    from .gold_history_stories import load_all_stories, load_fact_sheet
    ```

    Add `_pick_fresh_slug(used_topics: list[str], whitelist: list[dict]) -> str | None`:
    - Filters whitelist to entries whose `story_slug` is NOT in used_topics.
    - If empty, returns None.
    - Otherwise returns a random choice's `story_slug` (use `random.choice` — planner decides random over deterministic; random avoids the "always picks the same next story" pattern).
    - Pure function (no I/O, no async). Easy to unit test.

    Add `_load_fact_sheet(slug: str) -> dict | None` as a thin wrapper that calls `load_fact_sheet` from the loader module. (Keeps the `gold_history.py` surface area consistent with existing underscore-helper pattern for test-mocking ease.)

    Rewrite `_draft_gold_history(fact_sheet: dict, *, client: AsyncAnthropic) -> dict | None`:
    - New signature: takes the full fact_sheet dict (NOT separate story_title/story_slug/verified_facts args).
    - Build the prompt with these VERBATIM blocks:
      * System prompt: keep the drama-first gold analyst framing from the current impl. Add the FACT FIDELITY clause as a distinct paragraph.
      * User prompt: includes `story_title`, `story_slug`, `summary`, `recommended_arc`, the full `verified_facts` list rendered as a bulleted list of `- {claim} [ref: {source_url}]`, and the full `sources` list.
    - **FACT FIDELITY clause (verbatim from CONTEXT.md §D-03 — must appear EXACTLY, case-preserved, in the prompt so the `grep -c "FACT FIDELITY" scheduler/agents/content/gold_history.py` invariant hits):**

    > **FACT FIDELITY (CRITICAL):** You may only use names, dates, dollar figures, place names, and other specifics that appear EXPLICITLY in the `verified_facts` list below. Do NOT invent or infer any new specifics. Narrative connective tissue ("this was shocking because", "the stakes couldn't have been higher") is allowed. New specifics are NOT allowed. If you need a specific detail the facts don't provide, write the sentence without it — do not fabricate.

    - Instruct Claude to return JSON with the new shape: `format`, `story_title`, `story_slug`, `tweets`, `instagram_carousel`, `instagram_caption`, AND the new top-level `sources` field (mirrored from the fact_sheet).
    - On JSON parse, require `sources` in the `required` tuple alongside the existing keys. If missing, log a warning and return None (parity with current required-keys check).
    - Preserve: `model="claude-sonnet-4-6"`, `max_tokens=2048`, markdown-fence stripping, exception handling (JSONDecodeError + general Exception).

    Rewrite `run_draft_cycle()` per CONTEXT.md §Specific Ideas "Runtime flow":
    1. Load settings + anthropic client. **Do NOT instantiate `serpapi.Client`.**
    2. Open AsyncSession, create AgentRun row as before.
    3. `used_topics = await _get_used_topics(session)`.
    4. `whitelist = load_all_stories()` (sync call — loader reads ~10-20 small files once, fine in async context).
    5. `slug = _pick_fresh_slug(used_topics, whitelist)`. If None → write a `no_story_flag=True` ContentBundle with `story_headline="Gold History: all curated stories used"`, set agent_run notes `{"reason": "whitelist_exhausted"}`, mark completed, return.
    6. `fact_sheet = _load_fact_sheet(slug)`. If None (shouldn't happen since slug came from the whitelist, but belt-and-braces) → treat like drafting failure: `no_story_flag=False`, `compliance_passed=False`, `deep_research={"story_slug": slug, "reason": "fact_sheet_load_failed"}`, no DraftItem, return.
    7. `draft_content = await _draft_gold_history(fact_sheet, client=anthropic_client)`. If None → write failure bundle with `deep_research={"story_slug": slug, "sources": fact_sheet["sources"]}`, mark used (so we don't retry), return.
    8. `review_result = await content_agent.review(draft_content)`.
    9. Write ContentBundle: `story_headline=fact_sheet["story_title"]`, `content_type=CONTENT_TYPE`, `score=GOLD_HISTORY_SCORE`, `deep_research={"story_slug": slug, "sources": fact_sheet["sources"]}` (per CONTEXT.md §Specific Ideas: do NOT duplicate `verified_facts` here — it lives on disk in the JSON), `draft_content=draft_content`, `compliance_passed=review_result["compliance_passed"]`.
    10. `await _add_used_topic(session, slug)` regardless of compliance (parity with current impl — avoids retry loops on drafts that keep failing compliance).
    11. If compliance failed: notes `{"reason": "compliance_failed", ...}`, do NOT create DraftItem, return.
    12. Else: `rationale = f"Gold History: {story_title}. Grounded in {len(fact_sheet['verified_facts'])} pre-verified facts from {len(fact_sheet['sources'])} sources."` → `item = content_agent.build_draft_item(bundle, rationale)` → session.add(item).
    13. Update agent_run: `items_queued=1`, notes with `story_slug`, `story_title`, `fact_count`, `source_count`, `content_bundle_id`.
    14. Finally block: same as current — `agent_run.ended_at = now_utc`, session.commit().

    Rewrite the module docstring: drop the "Claude Sonnet picker" description; describe the curated-whitelist model, reference the `gold_history_stories/` directory, cite `quick-260422-lbb`. Keep the APScheduler cadence info (every other day at 12:00 LA). Keep the requirements list (CONT-07, CONT-14, CONT-15, CONT-16, CONT-17).

    **Step 5 — Update `scheduler/tests/test_gold_history.py`:**

    Retire these tests (delete, don't skip):
    - `test_pick_story_returns_parsed_json`
    - `test_pick_story_returns_none_on_parse_failure`
    - `test_pick_story_sends_used_list_to_claude`

    Update `test_module_surface`:
    - Remove `assert callable(gold_history._pick_story)` and `assert callable(gold_history._verify_facts)`.
    - Add `assert callable(gold_history._pick_fresh_slug)` and `assert callable(gold_history._load_fact_sheet)`.
    - Add a negative assertion: `assert not hasattr(gold_history, "_pick_story")` and `assert not hasattr(gold_history, "_verify_facts")` — proves the old functions are actually gone, not just renamed.

    Keep: `test_get_used_topics_returns_empty_when_missing`, `test_get_used_topics_parses_json_value`, `test_get_used_topics_handles_malformed_json` — these still exercise retained helpers.

    Add new tests (all `@pytest.mark.asyncio` only where async; the loader tests are sync):

    ```python
    def test_whitelist_loads_all_stories():
        from agents.content.gold_history_stories import load_all_stories
        stories = load_all_stories()
        assert len(stories) >= 10, f"expected ≥10 seeded stories, got {len(stories)}"
        for s in stories:
            for k in ("story_slug", "story_title", "summary", "verified_facts", "sources"):
                assert k in s, f"{s.get('story_slug', '?')}: missing {k}"
            assert s["verified_facts"], f"{s['story_slug']}: empty verified_facts"
            for f in s["verified_facts"]:
                assert f.get("source_url"), f"{s['story_slug']}: fact missing source_url"
            assert s["sources"], f"{s['story_slug']}: empty sources"


    def test_pick_fresh_slug_excludes_used():
        whitelist = [{"story_slug": "a"}, {"story_slug": "b"}, {"story_slug": "c"}]
        slug = gold_history._pick_fresh_slug(["a", "b"], whitelist)
        assert slug == "c"


    def test_pick_fresh_slug_returns_none_when_all_used():
        whitelist = [{"story_slug": "a"}]
        assert gold_history._pick_fresh_slug(["a"], whitelist) is None


    def test_load_fact_sheet_returns_dict_for_known_slug():
        # Use a real seeded slug — any committed story works; pick one deterministically.
        from agents.content.gold_history_stories import load_all_stories
        some_slug = load_all_stories()[0]["story_slug"]
        sheet = gold_history._load_fact_sheet(some_slug)
        assert sheet is not None
        assert sheet["story_slug"] == some_slug


    def test_load_fact_sheet_returns_none_for_unknown_slug():
        assert gold_history._load_fact_sheet("nonexistent-slug-xyz-123") is None


    @pytest.mark.asyncio
    async def test_draft_gold_history_includes_sources_field():
        client = AsyncMock()
        response = MagicMock()
        response.content = [MagicMock(text=json.dumps({
            "format": "gold_history",
            "story_title": "T",
            "story_slug": "t",
            "tweets": ["hook"],
            "instagram_carousel": [{"slide": 1, "headline": "h", "body": "b", "visual_note": "v"}],
            "instagram_caption": "cap",
            "sources": [{"ref": "[1]", "url": "https://x", "publisher": "X"}],
        }))]
        client.messages.create = AsyncMock(return_value=response)
        fact_sheet = {
            "story_slug": "t",
            "story_title": "T",
            "summary": "s",
            "recommended_arc": "h→r→c→p",
            "verified_facts": [{"claim": "c", "source_url": "https://x"}],
            "sources": [{"ref": "[1]", "url": "https://x", "publisher": "X"}],
        }
        draft = await gold_history._draft_gold_history(fact_sheet, client=client)
        assert draft is not None
        assert "sources" in draft
        assert len(draft["sources"]) >= 1


    @pytest.mark.asyncio
    async def test_draft_gold_history_prompt_contains_fact_fidelity_clause():
        client = AsyncMock()
        response = MagicMock()
        response.content = [MagicMock(text=json.dumps({
            "format": "gold_history", "story_title": "T", "story_slug": "t",
            "tweets": ["h"], "instagram_carousel": [], "instagram_caption": "c",
            "sources": [{"ref": "[1]", "url": "https://x", "publisher": "X"}],
        }))]
        client.messages.create = AsyncMock(return_value=response)
        fact_sheet = {
            "story_slug": "t", "story_title": "T", "summary": "s",
            "recommended_arc": "arc",
            "verified_facts": [{"claim": "c", "source_url": "https://x"}],
            "sources": [{"ref": "[1]", "url": "https://x", "publisher": "X"}],
        }
        await gold_history._draft_gold_history(fact_sheet, client=client)
        # Inspect both system prompt and user message for the clause.
        _, kwargs = client.messages.create.call_args
        system = kwargs.get("system", "")
        user = kwargs["messages"][0]["content"]
        assert "FACT FIDELITY" in system or "FACT FIDELITY" in user
    ```

    **Step 6 — Run validation gates and commit:**

    See `<verify>` for the gate commands.

    **Step 7 — Atomic commit:**

    ```bash
    cd /tmp/seva-260422-lbb
    git add scheduler/agents/content/gold_history.py \
            scheduler/agents/content/gold_history_stories/ \
            scheduler/tests/test_gold_history.py
    git status  # sanity check: nothing else staged
    git commit -m "$(cat <<'EOF'
feat(scheduler): replace gold_history Claude-picker with curated fact-sheet whitelist (quick-260422-lbb)

Retires the Claude-picks-from-memory + SerpAPI-runtime-verification flow that
risked hallucinated names, dates, and dollar figures in gold_history drafts.
New flow:

- NEW scheduler/agents/content/gold_history_stories/ — curated whitelist of
  pre-researched fact sheets (one JSON per canonical story). ≥10 seeded:
  Bre-X, Giustra/GoldCorp, Munk/Barrick, Hunt brothers, Klondike, Nixon gold
  window, Witwatersrand, California Gold Rush, LBMA Fix probe, GLD launch,
  Germany gold repatriation, et al. Each fact sheet: ≥5 verified_facts, each
  with a distinct source_url, plus a deduplicated sources array.
- Loader helper load_all_stories() with per-story schema validation.
- _pick_story + _verify_facts FULLY REMOVED (not commented out). Leaks 1-4
  from the zid debug follow-up eliminated by construction.
- _pick_fresh_slug filters whitelist to unused slugs (random pick).
- _draft_gold_history now takes a full fact_sheet and locks the drafter to
  the verified_facts list via an explicit FACT FIDELITY clause forbidding
  invention of names, dates, dollar figures, place names, percentages.
- Drafter output gains a top-level `sources` field (clean copy in tweets/
  slides, audit trail in the JSON for the approval dashboard).
- Tests: 3 _pick_story tests retired, 7 new tests added covering whitelist
  load, fresh-slug selection, fact-sheet load, sources field, and FACT
  FIDELITY clause presence.

Zero schema changes. Zero backend/frontend changes. Other 6 sub-agents
untouched. Full test suite remains green.

Follow-up (d) from the zid debug session.
EOF
)"
    git log --oneline -1
    ```

    **Step 8 — Push the branch (do NOT merge to main — user reviews the PR diff per D-02):**

    ```bash
    git push -u origin quick/260422-lbb-gold-history-curated-whitelist
    ```

    Report the branch name + commit SHA in the completion summary.
  </action>

  <verify>
    <automated>
      cd /Users/matthewnelson/seva-mining && (
        set -euo pipefail

        # 1. Lint clean
        cd scheduler && uv run ruff check . || { echo "FAIL: ruff"; exit 1; }

        # 2. Full test suite passes (≥103 tests — 101 baseline - 3 retired + ≥5 new)
        TEST_COUNT=$(uv run pytest --collect-only -q 2>&1 | grep -E "^[0-9]+ tests collected" | awk '{print $1}')
        echo "Collected tests: $TEST_COUNT"
        [ "$TEST_COUNT" -ge 103 ] || { echo "FAIL: expected ≥103 tests, got $TEST_COUNT"; exit 1; }
        uv run pytest -x || { echo "FAIL: pytest"; exit 1; }

        cd /Users/matthewnelson/seva-mining

        # 3. Fact-sheet count ≥10
        JSON_COUNT=$(find scheduler/agents/content/gold_history_stories -name "*.json" | wc -l | tr -d ' ')
        [ "$JSON_COUNT" -ge 10 ] || { echo "FAIL: expected ≥10 fact-sheet JSONs, got $JSON_COUNT"; exit 1; }
        echo "Fact sheets: $JSON_COUNT"

        # 4. Every verified_facts entry has a source_url (grep-gated invariant)
        python3 -c "
import json, pathlib, sys
missing = []
for p in pathlib.Path('scheduler/agents/content/gold_history_stories').glob('*.json'):
    d = json.loads(p.read_text())
    for i, f in enumerate(d.get('verified_facts', [])):
        if not f.get('source_url'):
            missing.append(f'{p.name}[{i}]: {f}')
if missing:
    print('FAIL: facts missing source_url:'); [print(m) for m in missing]; sys.exit(1)
print(f'All facts across {len(list(pathlib.Path(\"scheduler/agents/content/gold_history_stories\").glob(\"*.json\")))} files have source_url')
" || exit 1

        # 5. FACT FIDELITY clause landed verbatim in gold_history.py
        FIDELITY=$(grep -c "FACT FIDELITY" scheduler/agents/content/gold_history.py || true)
        [ "$FIDELITY" -ge 1 ] || { echo "FAIL: FACT FIDELITY clause missing from gold_history.py"; exit 1; }

        # 6. Old functions fully removed
        OLD=$(grep -cE "_pick_story|_verify_facts" scheduler/agents/content/gold_history.py || true)
        [ "$OLD" = "0" ] || { echo "FAIL: _pick_story/_verify_facts still referenced ($OLD hits)"; exit 1; }

        # 7. Sources field handling present
        SOURCES=$(grep -c "sources" scheduler/agents/content/gold_history.py || true)
        [ "$SOURCES" -ge 1 ] || { echo "FAIL: sources field not handled in gold_history.py"; exit 1; }

        # 8. serpapi import removed (leakage paths gone)
        SERP=$(grep -cE "^import serpapi|^from serpapi" scheduler/agents/content/gold_history.py || true)
        [ "$SERP" = "0" ] || { echo "FAIL: serpapi import still present in gold_history.py"; exit 1; }

        # 9. Single atomic commit on the worktree branch
        cd /tmp/seva-260422-lbb 2>/dev/null && {
            COMMITS=$(git rev-list --count a1ea13c..HEAD)
            [ "$COMMITS" = "1" ] || { echo "FAIL: expected exactly 1 commit on branch, got $COMMITS"; exit 1; }
            echo "Branch: $(git branch --show-current) @ $(git rev-parse --short HEAD)"
        }

        echo "ALL GATES PASSED"
      )
    </automated>
  </verify>

  <done>
    - `scheduler/agents/content/gold_history_stories/__init__.py` exists with `load_all_stories` + `load_fact_sheet` + schema validation.
    - ≥10 fact-sheet `*.json` files committed under `scheduler/agents/content/gold_history_stories/`.
    - Every `verified_facts[*].source_url` is non-empty (Python loop gate passes).
    - `scheduler/agents/content/gold_history.py` has `_pick_fresh_slug`, `_load_fact_sheet`, and a rewritten `_draft_gold_history` — `_pick_story` and `_verify_facts` are gone.
    - `FACT FIDELITY` appears at least once in `gold_history.py`.
    - `sources` appears at least once in `gold_history.py` (field handling).
    - `import serpapi` is gone from `gold_history.py`.
    - `scheduler/tests/test_gold_history.py` has the 3 old `_pick_story` tests retired, `test_module_surface` updated (negative hasattr assertions included), and ≥5 new tests added (baseline was 6 tests in this file → target ≥8 tests in this file; overall suite ≥103 tests).
    - `cd scheduler && uv run ruff check .` exits 0.
    - `cd scheduler && uv run pytest -x` exits 0.
    - Exactly 1 commit on `quick/260422-lbb-gold-history-curated-whitelist` branching from `a1ea13c`.
    - Branch pushed to origin — user reviews the PR diff before merge per D-02.
  </done>
</task>

</tasks>

<verification>
The task is complete when the `<automated>` gate block passes end-to-end. That block encodes all 7 validation gates from the planning_requirements plus two extras (serpapi import removed, single-commit invariant).

**Overall quality bar (cross-cutting, read before marking done):**
1. Every surface fact in every seeded JSON is traceable to at least one real URL. No placeholder URLs, no fabricated publications.
2. The FACT FIDELITY clause text appears byte-for-byte as specified (copy it from CONTEXT.md §D-03 — do not paraphrase).
3. `run_draft_cycle` no longer instantiates `serpapi.Client` — the runtime never hits SerpAPI for gold_history (the `settings.serpapi_api_key` may still be read elsewhere for other agents; just don't use it here).
4. The `deep_research` field in the persisted ContentBundle has the new shape `{"story_slug": ..., "sources": [...]}` — no legacy `verified_claims` key (that was a leakage-of-intent field name and the facts now live on disk in the fact sheet JSON).
5. Existing tests for retained helpers (`_get_used_topics`, `_add_used_topic`) continue to pass unmodified.
</verification>

<success_criteria>
- All `<verify>` gates pass (lint clean, full suite green, ≥10 fact sheets, all source_urls present, FACT FIDELITY verbatim, old functions gone, sources field present, serpapi import gone, single atomic commit).
- Branch `quick/260422-lbb-gold-history-curated-whitelist` exists on origin with base `a1ea13c` + 1 commit.
- Leakage paths 1-4 identified in the zid debug session are closed by construction (not just behind a verification gate).
- Hallucination risk on gold_history drafts is reduced to: "Claude may only rearrange pre-verified facts and add evidence-free narrative connective tissue."
- Other 6 sub-agents (breaking_news, threads, long_form, quotes, infographics, video_clip) are untouched — their files are not in the commit diff.
- Zero backend, frontend, DB schema, Alembic migration, or config-key changes.
- User can review the PR diff before merge (D-02 requirement).
</success_criteria>

<output>
After completion, create `.planning/quick/260422-lbb-harden-gold-history-py-so-it-only-produc/260422-lbb-SUMMARY.md` with:
- Branch name + commit SHA.
- List of seeded story slugs (≥10).
- Test count delta (e.g. "101 → 105").
- Confirmation each validation gate passed.
- Any stories that were attempted but dropped (e.g. insufficient sourcing) — so the user knows which canonical stories still need seeding in a follow-up.
- Any research surprises or contradictions found between sources (e.g. conflicting dates across Wikipedia vs contemporaneous news) — documented for the user's review.
</output>
