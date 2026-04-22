# GSD Debug Knowledge Base

Resolved debug sessions. Used by `gsd-debugger` to surface known-pattern hypotheses at the start of new investigations.

---

## 260422-gmb — sub_gold_media consistent 0-items (silent empty result)
- **Date:** 2026-04-22
- **Error patterns:** 0 items, items_found=0, items_queued=0, notes=None, sub_gold_media, gold_media, X search, video clips, silent empty, has:videos, tweepy
- **Root cause:** Two compounding bugs in `_search_gold_media_clips` introduced by vxg (68b21d1): (1) `gold` keyword in X query eliminated 100% of results from the 3 accounts that actually post native videos (BloombergTV/ReutersBiz/FT never include "gold" in video tweet text); (2) `GOLD_MEDIA_ACCOUNTS[:5]` slice excluded FT (position 5), one of only 3 productive accounts.
- **Fix:** Drop `[:5]` slice (use all 7 accounts); drop `gold` keyword from X query (LLM quality bar handles gold relevance via 3-criteria gate); add per-stage telemetry counters to `agent_run.notes` on both zero-return and success paths.
- **Files changed:** scheduler/agents/content/gold_media.py
---
