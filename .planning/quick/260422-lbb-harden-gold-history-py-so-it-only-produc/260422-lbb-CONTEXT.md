# Quick Task 260422-lbb: Harden gold_history.py for 100% true stories — Context

**Gathered:** 2026-04-22
**Status:** Ready for planning

<domain>
## Task Boundary

Harden `scheduler/agents/content/gold_history.py` so it only produces factually accurate historical stories — no hallucinated names, dates, or numbers. User directive (verbatim): "For gold history, we can leave as is. It needs to actually be a 100% true story."

This is follow-up (d) from the zid debug session (`.planning/debug/resolved/260422-zid-non-bn-agents-produce-zero-items.md`), the fourth of five follow-ups. Scope is gold_history-only; the other 6 sub-agents are not touched.

</domain>

<decisions>
## Implementation Decisions

User reviewed the gray areas and responded "All clear — you decide" → all decisions below are **Claude's Discretion, locked via the user's explicit authorization** to proceed with the Recommended path for every gray area.

### D-01 — Approach: Curated whitelist (Option B)

Replace the current Claude-picker-from-memory flow with a **curated whitelist of pre-researched fact sheets**. The whitelist lives as JSON files in a new directory `scheduler/agents/content/gold_history_stories/` (one file per story, named by slug). Claude no longer picks stories from its training data — it picks a slug from the whitelist (filtered to exclude `gold_history_used_topics`). Fact sheets contain the verified content; Claude only *drafts* from them, never *invents*.

**Why (B) over (A) verification-gate tightening:** User's "100% true story" bar cannot be reliably achieved with SerpAPI verification gating alone — SerpAPI snippets have no semantic guarantee they corroborate a claim, only that keywords overlap. The only way to guarantee accuracy is to ground the drafter on pre-researched material whose provenance has been reviewed.

**Why not (C) hybrid:** Adds complexity (two code paths) for marginal benefit. If the whitelist runs out (which takes months at the every-other-day cadence), we can add a curated-fallback or broaden the whitelist later. Ship the strongest version first.

### D-02 — Fact-sheet sourcing: Seeded canonical stories via SerpAPI multi-source corroboration (Option iii)

The initial whitelist is seeded with ~10-20 canonical gold-industry stories that I (the agent executing this task) research via SerpAPI multi-source corroboration and commit as JSON files as part of this task. User reviews the PR diff before merge.

**Target stories for the seed set (to research during execution):**
- Bre-X Minerals fraud (1997 Busang, Indonesia)
- Frank Giustra / GoldCorp 1994 founding
- Peter Munk / Barrick Gold founding (1983, reverse-merger)
- Hunt brothers silver corner (1979-80 "Silver Thursday")
- Klondike Gold Rush (1896-99)
- Nixon closes the gold window (August 15, 1971)
- Newmont Mining / Carlin Trend Goldstrike
- South African gold mines (Witwatersrand discovery, 1886)
- California Gold Rush (1848-55)
- USSR dumps gold to destabilize market (1960s, Operation Goldfinger era)
- Russia's post-Soviet gold reserves accumulation
- China's strategic gold reserve buildup (2000s-2010s)
- Venezuela's gold repatriation attempt (2011, Chavez)
- Germany's gold repatriation from NY Fed (2013-2017)
- SPDR Gold Trust (GLD) launch 2004
- LBMA London Fix scandal (2014 manipulation probe)
- Swiss referendum on gold reserves (2014, rejected)
- Zimbabwe gold-backed currency ZiG (2024)

I will seed **at least 10** of these. Each fact sheet contains:
- `story_slug` (matches filename)
- `story_title`
- `summary` (1-2 sentences for the Claude picker)
- `verified_facts: [{claim, source_url, published_date}...]` — minimum 5 facts per story, each with a distinct source_url
- `sources: [{url, publisher, accessed_date}...]` — deduplicated source list
- `tags: [...]` — e.g. `["fraud", "1990s", "exploration"]` — for future filtering
- `recommended_arc` — 1-line story arc hint (hook → rising → climax → payoff)

**Rule:** every claim MUST have at least one `source_url`. This is a grep-gated invariant in the plan.

### D-03 — Drafter constraints: Locked to verified_facts, forbidden-invention clause, separate sources field (Options iii + iii)

The drafter prompt is tightened with an explicit, hard-coded "do not invent" clause:

> **FACT FIDELITY (CRITICAL):** You may only use names, dates, dollar figures, place names, and other specifics that appear EXPLICITLY in the `verified_facts` list below. Do NOT invent or infer any new specifics. Narrative connective tissue ("this was shocking because", "the stakes couldn't have been higher") is allowed. New specifics are NOT allowed. If you need a specific detail the facts don't provide, write the sentence without it — do not fabricate.

Every tweet and carousel slide must draw its factual content from `verified_facts`. The drafter is allowed to:
- Reorder facts for dramatic pacing
- Add narrative voice and dramatic framing
- Connect facts with evidence-free commentary ("few outside Toronto knew what was coming")

The drafter is NOT allowed to:
- Introduce new names, dates, dollar figures, percentages, place names, or time periods
- Quote anyone not quoted in `verified_facts`
- Cite specific numbers (crowd sizes, production figures, etc.) not in `verified_facts`

### D-04 — Citation format: Separate `sources` output field (Option iii)

The drafter output gains a new top-level field `sources: [{ref, url, publisher}...]` that mirrors the fact-sheet's source list (deduplicated, with a short `ref` label like `"[1]"`, `"[2]"`). The tweet/slide copy itself remains clean (no inline `[1]` markers cluttering the draft). The approval dashboard already renders the `draft_content` JSON — operators will see the sources alongside the copy when approving. No inline citation markers in the output text.

**Why this over inline citations:** User approves drafts via the dashboard before anything is posted. The audit trail lives in the JSON, not the copy. Cleaner approach for a human-review-before-post workflow.

### D-05 — Verification threshold: N/A (no SerpAPI verification needed)

Since the approach is (B) curated whitelist, the existing `_verify_facts` SerpAPI function is retired — its leakage paths (Leaks 2 + 3 from the task context) are eliminated by construction. Fact sheets are pre-verified at commit time (by me, sourced via SerpAPI multi-source corroboration). The runtime no longer has a "verify claims via SerpAPI" step.

### Claude's Discretion

All five gray areas locked to Recommended paths per user's "All clear — you decide" response. No open questions remain for the planner.

</decisions>

<specifics>
## Specific Ideas

**File layout (proposed, planner to confirm):**
```
scheduler/agents/content/gold_history.py           # hardened run_draft_cycle + drafter
scheduler/agents/content/gold_history_stories/     # NEW directory (curated whitelist)
  ├── __init__.py                                  # loader helper
  ├── bre-x-busang-fraud-1997.json
  ├── giustra-goldcorp-1994.json
  ├── munk-barrick-founding-1983.json
  ├── hunt-brothers-silver-1980.json
  ├── klondike-gold-rush-1896.json
  ├── nixon-closes-gold-window-1971.json
  └── ... (at least 10 total seeded)
scheduler/tests/test_gold_history.py              # existing — add tests for new flow
```

**Fact-sheet JSON schema (proposed, planner to confirm):**
```json
{
  "story_slug": "bre-x-busang-fraud-1997",
  "story_title": "The Bre-X Busang Fraud — The Biggest Gold Scam in History",
  "summary": "Bre-X Minerals salted a remote Borneo core-sample pile with river gold...",
  "tags": ["fraud", "1990s", "exploration", "indonesia"],
  "recommended_arc": "Hook: largest claimed discovery ever. Rising: whole world piles in. Climax: chief geologist 'falls' from helicopter. Payoff: zero gold, billions lost.",
  "verified_facts": [
    {
      "claim": "Bre-X Minerals was a Calgary-based junior gold mining company.",
      "source_url": "https://en.wikipedia.org/wiki/Bre-X",
      "published_date": "2026-03-15"
    },
    ...
  ],
  "sources": [
    {"ref": "[1]", "url": "...", "publisher": "Wikipedia", "accessed_date": "2026-04-22"},
    {"ref": "[2]", "url": "...", "publisher": "Financial Post", "accessed_date": "2026-04-22"},
    ...
  ]
}
```

**Drafter output shape (proposed, preserving existing contract):**
```json
{
  "format": "gold_history",
  "story_title": "...",
  "story_slug": "...",
  "tweets": ["hook tweet (clean copy)", "tweet 2", ...],
  "instagram_carousel": [
    {"slide": 1, "headline": "...", "body": "... (max 15 words)", "visual_note": "..."},
    ...
  ],
  "instagram_caption": "full caption text (clean copy)",
  "sources": [
    {"ref": "[1]", "url": "...", "publisher": "..."},
    ...
  ]
}
```

The `sources` field is NEW. Existing fields preserved for backward-compat with the ContentBundle/DraftItem consumers and the approval dashboard's `LongFormPreview`/gold_history rendering.

**Runtime flow (proposed, planner to confirm):**
1. `_load_whitelist()` — reads all `.json` files from `gold_history_stories/`, returns `[{slug, title, summary, fact_sheet_path}...]`.
2. `_get_used_topics()` — unchanged, still reads `gold_history_used_topics` Config key.
3. `_pick_fresh_slug()` — filters whitelist to slugs NOT in used_topics, returns one (random pick or deterministic — planner decides). Returns None if all used.
4. `_load_fact_sheet(slug)` — loads the JSON fact sheet by slug, returns the full dict.
5. `_draft_gold_history(fact_sheet, *, client)` — new signature: takes the full fact sheet, writes tightened prompt with FACT FIDELITY clause, returns drafter output dict.
6. `content_agent.review(draft_content)` — unchanged compliance gate.
7. Persist ContentBundle + DraftItem as before; `deep_research` field now stores `{"story_slug": slug, "sources": [...]}` (the verified_facts list is already captured in the fact sheet JSON on disk — don't duplicate).

**Tests to add (proposed minimum):**
- `test_whitelist_loads_all_stories` — iterates `.json` files, asserts each has required keys + ≥1 `source_url` per claim.
- `test_pick_fresh_slug_excludes_used` — mock used_topics with 2 slugs, assert the 3rd available slug is returned.
- `test_pick_fresh_slug_returns_none_when_all_used` — mock used_topics with all slugs, assert None returned.
- `test_draft_gold_history_includes_sources_field` — drafter output dict has `sources` key with at least 1 entry.
- `test_draft_gold_history_prompt_contains_fact_fidelity_clause` — prompt string contains the forbidden-invention clause (grep-style assertion inside the test).
- Regression: existing `_pick_story` tests — retire since the function no longer exists OR rename the function and update tests. Planner decides which existing tests to keep/retire.

</specifics>

<canonical_refs>
## Canonical References

- Source file: `scheduler/agents/content/gold_history.py` (current implementation, 425 lines)
- Sibling sub-agents for pattern reference: `scheduler/agents/content/quotes.py`, `video_clip.py` (bespoke flows, not using `run_text_story_cycle`)
- Existing compliance gate: `scheduler/agents/content_agent.py::review()`
- zid debug follow-up (d): `.planning/debug/resolved/260422-zid-non-bn-agents-produce-zero-items.md` — the "hallucination risk" flag
- User directive verbatim: "For gold history, we can leave as is. It needs to actually be a 100% true story."
- Related upstream decision in ep9 SUMMARY: market_snapshot `_HARD_INSTRUCTION` forbids hallucinated current/historical numbers — this task extends the same no-hallucination posture to gold_history

</canonical_refs>
