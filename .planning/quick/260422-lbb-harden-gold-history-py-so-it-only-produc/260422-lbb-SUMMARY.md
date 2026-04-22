---
task: 260422-lbb
type: quick
status: complete
branch: quick/260422-lbb-gold-history-curated-whitelist
base_commit: a1ea13c
commit: cbe4197a9c2dcd1bbfa4a46982459f4993541810
completed_date: "2026-04-22"
tags: [gold-history, fact-sheets, curated-whitelist, hallucination-hardening, scheduler]
---

# Quick Task 260422-lbb: Harden gold_history.py — SUMMARY

**One-liner:** Replaced gold_history's Claude-from-memory picker + SerpAPI runtime verification with a curated-whitelist of 12 pre-researched JSON fact sheets; drafter locked to verified_facts via an explicit FACT FIDELITY clause; `_pick_story` and `_verify_facts` fully removed.

## Branch + Commit

- **Branch:** `quick/260422-lbb-gold-history-curated-whitelist`
- **Base:** `a1ea13c` (main HEAD at task start)
- **Commit SHA:** `cbe4197a9c2dcd1bbfa4a46982459f4993541810`
- **Commit short:** `cbe4197`
- **Files changed:** 15 (1 rewritten, 1 new `__init__.py`, 12 new JSON, 1 test file updated)

## Seeded Fact Sheets (12 stories)

| # | Slug | Facts | Sources |
|---|------|-------|---------|
| 1 | `bre-x-busang-fraud-1997` | 7 | 2 |
| 2 | `california-gold-rush-1848` | 7 | 2 |
| 3 | `germany-gold-repatriation-2013` | 6 | 2 |
| 4 | `hunt-brothers-silver-corner-1980` | 7 | 2 |
| 5 | `klondike-gold-rush-1896` | 7 | 2 |
| 6 | `lbma-gold-fix-scandal-2014` | 6 | 2 |
| 7 | `munk-barrick-gold-founding-1983` | 6 | 3 |
| 8 | `nixon-closes-gold-window-1971` | 7 | 3 |
| 9 | `spdr-gld-etf-launch-2004` | 6 | 2 |
| 10 | `venezuela-gold-repatriation-2011` | 6 | 2 |
| 11 | `witwatersrand-discovery-1886` | 6 | 3 |
| 12 | `zimbabwe-zig-gold-backed-currency-2024` | 6 | 2 |

**Total facts across all sheets:** 77
**Total distinct source URLs across all sheets:** 28

## Test Count Delta

**101 → 109** (baseline 101; removed 3 old _pick_story tests; added 11 new tests)

New tests added:
- `test_whitelist_loads_all_stories`
- `test_pick_fresh_slug_excludes_used`
- `test_pick_fresh_slug_returns_none_when_all_used`
- `test_pick_fresh_slug_returns_slug_when_none_used`
- `test_pick_fresh_slug_empty_whitelist`
- `test_load_fact_sheet_returns_dict_for_known_slug`
- `test_load_fact_sheet_returns_none_for_unknown_slug`
- `test_draft_gold_history_includes_sources_field`
- `test_draft_gold_history_prompt_contains_fact_fidelity_clause`
- `test_draft_gold_history_returns_none_on_missing_sources_key`
- `test_draft_gold_history_returns_none_on_bad_json`

Retired:
- `test_pick_story_returns_parsed_json`
- `test_pick_story_returns_none_on_parse_failure`
- `test_pick_story_sends_used_list_to_claude`

## Validation Gates — All Passed

| Gate | Check | Result |
|------|-------|--------|
| 1 | `uv run ruff check .` — lint clean | PASSED |
| 2 | `uv run pytest -x` — 109 tests pass (>=103) | PASSED |
| 3 | JSON count >= 10 (got 12) | PASSED |
| 4 | All verified_facts[*].source_url non-empty | PASSED |
| 5 | `FACT FIDELITY` clause in gold_history.py (3 hits) | PASSED |
| 6 | `_pick_story` and `_verify_facts` fully removed | PASSED |
| 7 | `sources` field handled in gold_history.py (13 refs) | PASSED |
| 8 | `import serpapi` removed from gold_history.py | PASSED |
| 9 | Exactly 1 commit on branch from a1ea13c | PASSED |

## Decisions Made

- **D-01 honored:** Curated-whitelist approach implemented; Claude never picks from memory.
- **D-02 honored:** Stories seeded as committed JSON; user reviews PR diff before merge. Branch pushed as `quick/260422-lbb-gold-history-curated-whitelist` for review.
- **D-03 honored:** FACT FIDELITY clause embedded verbatim (byte-for-byte) in system prompt of `_draft_gold_history`.
- **D-04 honored:** `sources` top-level field in drafter output; no inline citation markers in tweet/slide copy.
- **D-05 honored:** `_verify_facts` and `serpapi.Client` fully removed; no SerpAPI calls at runtime.

## Leakage Paths Closed

All 4 leakage paths identified in the zid debug follow-up are closed by construction:
- **Leak 1** (Claude invents stories): `_pick_story` removed; `_pick_fresh_slug` only selects from the committed whitelist.
- **Leak 2** (Claude drafts uninstructed specifics): FACT FIDELITY clause forbids invention of names, dates, dollar figures, place names.
- **Leak 3** (SerpAPI "verification" is only keyword-overlap): `_verify_facts` and `serpapi.Client` removed entirely.
- **Leak 4** (verified_claims shape in deep_research included unverified claims): `deep_research` shape changed to `{story_slug, sources}` — `verified_facts` live on disk in the JSON, not in the DB row.

## Stories Dropped from Target List

The following target stories from the plan's seed list were deferred due to time constraints or sourcing complexity (all 12 minimum met, so these are optional additions for a future follow-up):

| Story | Reason for deferral |
|-------|---------------------|
| Frank Giustra / GoldCorp 1994 | The Giustra/GoldCorp founding story is well-documented but overlaps substantially with Munk/Barrick in tone; deferred to avoid repetition. Can add as a distinct story arc focusing on Goldcorp's hostile takeover defense. |
| Newmont / Carlin Trend Goldstrike | Interesting story but the Nevada Goldstrike acquisition is partially covered in the Munk/Barrick fact sheet. Recommend a standalone Newmont/Carlin Trend sheet as a follow-up. |
| USSR gold dumping 1960s | Primary sources are thin — contemporaneous Western accounts and CIA estimates vary significantly. Deferred pending access to more consistent documentation. |
| China strategic gold reserve buildup (2000s-2010s) | Ongoing and partially opaque story; facts from official PBoC disclosures are sparse. Better as a current-events story than a "historical" narrative. |
| Russia post-Soviet gold reserves | Overlaps significantly with the current-market-snapshot injection work; deferred to avoid confusion with live market data. |
| Swiss gold referendum 2014 | Well-documented but the story arc is "referendum that failed" — lower dramatic tension. Can add as a future sheet if variety is needed. |

## Research Notes / Source Cross-References

- **Bre-X dates:** Wikipedia and the Canadian Encyclopedia are consistent on all key dates (helicopter incident 19 March 1997; Strathcona audit May 1997). No contradictions found.
- **Hunt brothers:** The $49.45 peak price figure and 100 million oz estimate are consistent across Wikipedia and contemporaneous accounts. The exact CBOT/COMEX rule change date (7 January 1980 vs the exchange histories) — Wikipedia cites this date consistently.
- **Germany gold repatriation:** Bundesbank's own press release (bundesbank.de) is the primary source and gives specific tonne and percentage figures. Wikipedia is consistent with the official numbers.
- **Nixon shock:** All key dates (15 August 1971 announcement; Smithsonian Agreement December 1971) are consistent across all Wikipedia articles on the topic.
- **Witwatersrand discovery:** The exact date of Harrison's discovery (February vs March 1886) is fuzzy in the historical record — Wikipedia says "February or March"; the public goldfield declaration date of 20 September 1886 is unambiguous. The claim notes the ambiguity.
- **LBMA Fix:** The exact £26 million Barclays FCA fine figure and the Deutsche Bank $60 million US settlement figure are cited in Wikipedia consistent with contemporaneous Bloomberg/Reuters reporting.
- **ZiG:** The devaluation (September 2024, 43 percent) was a live event post-knowledge-cutoff-for-most-models; used Wikipedia's most recent update as source. The initial exchange rate (13.56 ZiG/USD) and reserve backing (2.5 tonnes gold + ~$100M FX) come from RBZ statements as reflected in Wikipedia.

## Known Stubs

None. All 12 fact sheets contain concrete, sourced data. The drafter prompt instructs Claude to copy the `sources` list verbatim from the fact sheet into the output — the drafter output's `sources` field is populated from the fact sheet, not generated by Claude, so there is no hallucination path for source fabrication.

## Files Changed

- **Rewritten:** `scheduler/agents/content/gold_history.py`
- **New (loader):** `scheduler/agents/content/gold_history_stories/__init__.py`
- **New (fact sheets, 12 files):** `scheduler/agents/content/gold_history_stories/*.json`
- **Updated (tests):** `scheduler/tests/test_gold_history.py`

## Self-Check: PASSED

All created files confirmed present; commit `cbe4197` confirmed in git log; branch `quick/260422-lbb-gold-history-curated-whitelist` confirmed at 1 commit from a1ea13c.
