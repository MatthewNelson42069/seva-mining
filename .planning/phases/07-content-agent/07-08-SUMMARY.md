---
phase: 07-content-agent
plan: "08"
subsystem: content-agent
tags: [twitter, video-clip, quote, tweepy, dual-platform, content-formats]
dependency_graph:
  requires: [07-06]
  provides: [video_clip-content-type, quote-content-type, twitter-search-content-agent]
  affects: [scheduler/agents/content_agent.py]
tech_stack:
  added: [tweepy.asynchronous.AsyncClient]
  patterns: [dual-platform-drafting, quota-aware-twitter-search, error-isolated-pipeline]
key_files:
  created: []
  modified:
    - scheduler/agents/content_agent.py
decisions:
  - "VIDEO_ACCOUNTS capped at first 5 for API query length limits — Twitter query length constraints"
  - "Fixed score 7.5 for Twitter-sourced video_clip and quote bundles — no RSS scoring pipeline for Twitter-native content"
  - "speaker_title defaults to 'Author, macro investor' for quote tweets — Claude improves in draft"
  - "quote format added as choosable from article RSS/SerpAPI content in _research_and_draft() Sonnet prompt"
  - "Senior analyst voice directives added to Sonnet system prompt: lead with number, surface non-obvious insight"
metrics:
  duration: "~5 minutes"
  completed: "2026-04-07"
  tasks_completed: 2
  files_modified: 1
---

# Phase 07 Plan 08: Video Clip + Quote Content Types Summary

Added video_clip and quote content types to the content agent: Tweepy client searches Twitter for video posts from VIDEO_ACCOUNTS (has:videos) and text quotes from QUOTE_ACCOUNTS (-has:media), Claude Sonnet drafts dual-platform captions (Twitter + Instagram), compliance is checked, and both formats produce ContentBundles and DraftItems integrated into the existing pipeline.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Tweepy client + video/quote Twitter search methods | bf039d9 | content_agent.py |
| 2 | Video/quote Claude drafting + compliance + DraftItem extension | 9971748 | content_agent.py |

## Decisions Made

- **VIDEO_ACCOUNTS capped at 5 per query**: Twitter API query length limits — only first 5 of 7 accounts used in the `from:` OR clause. Remaining 2 (Mining, Newaborngold) are not searched.
- **Fixed score 7.5 for Twitter-sourced content**: Video clips and quote tweets sourced from Twitter don't go through the RSS scoring pipeline (relevance/recency/credibility). Score 7.5 is above the 7.0 threshold, ensuring they qualify for the Senior Agent queue.
- **quote format added to _research_and_draft() prompt**: The Sonnet prompt now recognizes quote as a choosable format when a compelling quote is found in article/RSS content — not just from direct Twitter search.
- **Senior analyst voice instructions added to system prompt**: "First line is always the most impactful data point. Lead with the number. Surface ONE non-obvious insight not in the original article." — per CONTEXT.md voice requirements.
- **twitter_monthly_quota_limit config key**: Uses `twitter_monthly_quota_limit` (defaulting to 10,000) alongside the existing `twitter_monthly_tweet_count` — consistent with TwitterAgent's quota tracking but with a separate limit key for flexibility.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Functionality] Added `_run_twitter_content_search()` extraction method**
- **Found during:** Task 1 implementation
- **Issue:** The plan's `_run_pipeline()` integration called `_search_video_clips()` and `_search_quote_tweets()` inline, but this would make `_run_pipeline()` very large. When 07-07 adds its own changes to `_run_pipeline()` (multi-story loop), having the Twitter search inline would create difficult merge conflicts.
- **Fix:** Extracted all video/quote Twitter search processing into `_run_twitter_content_search()` — a separate method called at end of `_run_pipeline()`. Clean interface point that 07-07's changes don't touch.
- **Files modified:** `scheduler/agents/content_agent.py`
- **Commit:** bf039d9

**2. [Rule 2 - Missing Functionality] Added `_set_config_str()` helper**
- **Found during:** Task 1 quota implementation
- **Issue:** The content agent's existing `_get_config()` returns a string (not a Config row object like TwitterAgent's version), so there was no way to write config values back to the DB for quota tracking.
- **Fix:** Added `_set_config_str()` upsert helper that mirrors TwitterAgent's `_set_config()` pattern, enabling `_search_video_clips()` and `_search_quote_tweets()` to increment `twitter_monthly_tweet_count` after each search.
- **Files modified:** `scheduler/agents/content_agent.py`
- **Commit:** bf039d9

### Notes on 07-07 Compatibility

07-07 (multi-story, breaking_news, feed expansion) was not yet applied in this worktree. 07-08's additions are designed to integrate cleanly:
- `_run_pipeline()` addition is a single method call at the very end: `await self._run_twitter_content_search(session, agent_run)`
- `_extract_check_text()` additions are `elif` branches — no conflicts with 07-07's `breaking_news` branch
- `build_draft_item()` additions are `elif` branches — no conflicts with 07-07's `breaking_news` branch
- The Twitter search section is fully isolated in `_run_twitter_content_search()` — 07-07's multi-story refactor of the main loop does not affect it

## Verification

- VIDEO_ACCOUNTS (7 accounts) and QUOTE_ACCOUNTS (5 accounts) exist as module-level constants
- ContentAgent.__init__ creates self.tweepy_client from settings.x_api_bearer_token
- `_search_video_clips()` queries with `has:videos` + filters to type=='video' attachments
- `_search_quote_tweets()` queries with `-has:media` + filters to >=10 likes
- Both methods check `twitter_monthly_tweet_count` before searching and increment after
- `_draft_video_caption()` and `_draft_quote_post()` exist and return structured dict | None
- `_extract_check_text()` handles video_clip (twitter/instagram_caption) and quote (all 3 text fields)
- `build_draft_item()` handles video_clip (@account summary) and quote (speaker + text preview)
- All 6 plan verification checks passed via automated test

## Known Stubs

None — all methods are fully implemented. Twitter API calls require live credentials which are correctly wired from settings.x_api_bearer_token.

## Self-Check: PASSED

- [x] `scheduler/agents/content_agent.py` contains `VIDEO_ACCOUNTS` — FOUND
- [x] `scheduler/agents/content_agent.py` contains `QUOTE_ACCOUNTS` — FOUND
- [x] `scheduler/agents/content_agent.py` contains `tweepy_client` in `__init__` — FOUND
- [x] `scheduler/agents/content_agent.py` contains `_search_video_clips` — FOUND
- [x] `scheduler/agents/content_agent.py` contains `_search_quote_tweets` — FOUND
- [x] `scheduler/agents/content_agent.py` contains `_draft_video_caption` — FOUND
- [x] `scheduler/agents/content_agent.py` contains `_draft_quote_post` — FOUND
- [x] `_extract_check_text` handles `video_clip` and `quote` — VERIFIED
- [x] `build_draft_item` handles `video_clip` and `quote` — VERIFIED
- [x] Commit bf039d9 — FOUND
- [x] Commit 9971748 — FOUND
