---
phase: 07-content-agent
plan: "09"
subsystem: content-agent
tags: [content-agent, infographic, instagram-design-system, historical-pattern, gold-history, dual-platform, sonnet-prompt]
dependency_graph:
  requires: [07-07, 07-08]
  provides: [infographic-instagram-brief, historical-pattern-verification, gold-history-compliance, all-7-format-sonnet-prompt]
  affects: [scheduler/agents/content_agent.py]
tech_stack:
  added: []
  patterns: [dual-platform-infographic, historical-serpapi-verification, instagram-design-system-brief]
key_files:
  created: []
  modified:
    - scheduler/agents/content_agent.py
decisions:
  - "Sonnet system prompt rewritten: senior gold analyst voice, lead with number, non-obvious insight, no Seva Mining, no financial advice"
  - "User prompt presents 5 selectable formats (thread/long_form/breaking_news/infographic/quote); video_clip and gold_history noted as NOT chosen here"
  - "Infographic format expanded to include mode (current_data/historical_pattern), twitter_caption, instagram_brief sub-object with #F0ECE4/#0C1B32/#D4AF37 design system"
  - "Historical pattern SerpAPI verification: _search_corroborating(pattern) called after Sonnet; zero results falls back to current_data mode with logged warning"
  - "_extract_check_text infographic now extracts twitter_caption, instagram_brief.headline+caption, historical_context fields; caption_text retained for backward compat"
  - "gold_history handler added to both _extract_check_text and build_draft_item"
  - "build_draft_item infographic summary includes mode and notes instagram brief presence"
metrics:
  duration: "~2 minutes"
  completed: "2026-04-07"
  tasks_completed: 2
  files_modified: 1
---

# Phase 07 Plan 09: Expanded Infographic + Instagram Design System + Gold History Format Summary

Rewrote `_research_and_draft()` Sonnet prompt to be the central format decision engine for all 7 content types with dual-platform output, Instagram design system (#F0ECE4/#0C1B32/#D4AF37), historical_pattern infographic mode with SerpAPI verification fallback, and extended `_extract_check_text()` + `build_draft_item()` to fully handle the expanded infographic structure and gold_history format.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Rewrite Sonnet prompt with all 7 formats + Instagram design system + historical mode | b38a94b | scheduler/agents/content_agent.py |
| 2 | Extend compliance + DraftItem for infographic instagram_brief and gold_history format | 26d3b05 | scheduler/agents/content_agent.py |

## Decisions Made

- **Sonnet prompt rewrite**: System prompt simplified to the 5-sentence senior analyst voice spec from 07-CONTEXT.md. User prompt rebuilt as a proper format decision engine presenting all 7 options, with video_clip and gold_history explicitly noted as NOT chosen here.
- **Infographic dual-platform**: The expanded infographic structure now requires `twitter_caption` (1-3 sentences for X) and `instagram_brief` sub-object (headline, key_stats, visual_structure, caption) for both current_data and historical_pattern modes.
- **Instagram design system in prompt**: Brand colors (#F0ECE4 warm cream, #0C1B32 deep navy, #D4AF37 metallic gold), a16z minimalist aesthetic, max 15 words per slide, gold accent on 1-2 elements. Included as instruction #4 in the user prompt, triggered for infographic and quote formats.
- **Historical pattern verification**: After Sonnet call, if `format == "infographic"` and `mode == "historical_pattern"`, calls `self._search_corroborating(historical_context["pattern"])`. Zero results → sets mode to `"current_data"`, sets `historical_context` to `None`, logs warning.
- **Backward compat in _extract_check_text**: Kept `caption_text` extraction alongside new `twitter_caption` — existing infographic records without `twitter_caption` still pass compliance checking correctly.
- **gold_history handler**: Both `_extract_check_text` and `build_draft_item` now handle `gold_history` format — extracts all tweets, carousel slide headlines+bodies, and instagram_caption for compliance; summary shows story_title, tweet count, slide count.

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — all logic is fully implemented. Gold history format compliance and DraftItem building is wired and ready; the gold_history job itself (Plan 10) will produce actual gold_history ContentBundles.

## Self-Check: PASSED

- [x] `instagram_brief` appears in `scheduler/agents/content_agent.py` — VERIFIED (grep -c returns 2)
- [x] `F0ECE4` color code in prompt — VERIFIED (line 936)
- [x] `0C1B32` and `D4AF37` in prompt — VERIFIED (line 936)
- [x] `historical_pattern` referenced 5+ times — VERIFIED (grep -c returns 5)
- [x] `breaking_news` format preserved — VERIFIED (grep -c returns 7)
- [x] `video_clip` NOT chosen instruction present — VERIFIED (line 928)
- [x] `gold_history` NOT chosen instruction present — VERIFIED (line 929)
- [x] `_extract_check_text` gold_history handler at line 411 — VERIFIED
- [x] `build_draft_item` gold_history handler at line 413 — VERIFIED
- [x] Historical pattern fallback log message present — VERIFIED (line 1017)
- [x] `_extract_check_text` infographic test: Gold Record, Twitter cap, IG Head, IG Caption, Pattern — ALL PASSED
- [x] `_extract_check_text` gold_history test: Hook tweet, Slide1, Full caption — ALL PASSED
- [x] Commit b38a94b — FOUND
- [x] Commit 26d3b05 — FOUND
