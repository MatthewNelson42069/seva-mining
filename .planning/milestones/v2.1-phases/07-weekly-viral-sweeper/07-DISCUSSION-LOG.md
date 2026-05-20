# Phase 7: Weekly Viral Sweeper - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `07-CONTEXT.md` — this log preserves the alternatives considered.

**Date:** 2026-05-19
**Phase:** 07-weekly-viral-sweeper
**Areas discussed:** Scope direction, Reddit API prereq, Subreddit list, Sweep card UI, X API pivot follow-ups

---

## Gray Area #1: Scope Direction

| Option | Description | Selected |
|--------|-------------|----------|
| Full sweeper as specced (Recommended) | Sunday cron + Reddit ingestion + virality + Sonnet 3-angle generation + react-markdown card | ✓ |
| Lean — drop AI content-angle generation | Keep Reddit + virality + card UI, skip Sonnet | |
| Even leaner — manual trigger only, no cron | Drop scheduler registration entirely; manual fire via button or Railway shell | |

**User's choice:** Full sweeper as specced.
**Notes:** AI here serves the operator (reads + summarizes external signals), unlike Phase 6 where AI was dropped because the operator does the writing themselves.

---

## Gray Area #2: Reddit API Prereq

| Option | Description | Selected |
|--------|-------------|----------|
| Not yet — walk me through it | Add a pre-flight step: reddit.com/prefs/apps + 3 env vars | |
| Already done | Skip prereq section in CONTEXT.md | |
| Defer to execution time | Skip the prereq question; executor prompts when needed | |

**User's response (free-text):** *"We dont need the reddit API, just go based off the X API"*

**Effect:** **Major pivot.** All Reddit-related decisions collapse — drop SWEEP-01 (asyncpraw dependency), drop SWEEP-02 (Reddit env vars), rephrase SWEEP-04/05 (reddit_ingest.py → x_ingest.py with X search query). Reused the existing $100/mo X API Basic subscription that already powers the Content Agent's `video_clip` pipeline.

---

## Gray Area #3: Subreddit List

| Option | Description | Selected |
|--------|-------------|----------|
| All 4 from spec (Recommended) | gold, Wallstreetsilver, silverbugs, Gold_and_Silver | |
| Drop the 2 marginal subs | Keep only gold + Wallstreetsilver | |
| Different list — let me name them | User-provided list | |

**User's response (free-text):** *"lets use twitter API"*

**Effect:** Made moot by Gray Area #2 pivot. No subreddit list needed.

---

## Gray Area #4: Sweep Card UI Shape

| Option | Description | Selected |
|--------|-------------|----------|
| Stacked sections (Recommended) | One scrolling card with three sections in order | ✓ |
| Three tabs inside the card | Sub-tabs: 'Reddit' / 'Stories' / 'Angles' | |
| Accordion (collapsible sections) | Three collapsible sections, expand one at a time | |

**User's choice:** Stacked sections.
**Notes:** Matches how the daily summary feed already renders content (SummaryFeedPage pattern). Tabs/Accordion concept implicitly renamed from "Reddit" to "X" given the source pivot.

---

## X API Follow-up Batch (post-pivot)

### Search Query Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Combined: keywords + cashtags + hashtags (Recommended) | `("gold price" OR ... OR $GOLD OR ... OR #gold ...) -is:retweet -is:reply lang:en` | ✓ |
| Tickers/cashtags only | `($GOLD OR $GLD OR $GDX OR $NEM OR $AEM) -is:retweet -is:reply lang:en` | |
| Keywords only | `("gold price" OR "gold market" OR "gold mining" OR "central bank gold") -is:retweet -is:reply lang:en` | |

**User's choice:** Combined.
**Notes:** Captures keyword chatter (journalists/analysts), cashtag chatter (finance traders), and hashtag chatter (retail) in a single API call.

### Engagement Threshold

| Option | Description | Selected |
|--------|-------------|----------|
| Top by ranking, no threshold (Recommended) | `sort_order="relevancy"` + post-fetch re-rank by `likes + retweets*2 + replies*1.5` | ✓ |
| Hard floor: 100+ likes | Filter <100 likes before ranking | |
| Hard floor: 500+ likes (retired Twitter Agent default) | Filter <500 likes — high signal but risks empty weeks | |

**User's choice:** Top by ranking, no threshold.
**Notes:** Weekly cadence makes empty-week risk meaningful; no hard floor preferred. Post-fetch engagement re-rank gives quality without gating.

### Result Count

| Option | Description | Selected |
|--------|-------------|----------|
| Top 10 (Recommended) | max_results=100 for substrate, display top 10. ~400 tweets/month quota cost (4% of 10K) | ✓ |
| Top 5 | max_results=50, display 5. ~200/month (2%) | |
| Top 15 | max_results=100, display 15. ~400/month (4%) | |

**User's choice:** Top 10.
**Notes:** Matches the original Reddit spec count; gives Sonnet enough substrate to find 3 angles without making the card too long to skim.

### Wrap-up

| Option | Description | Selected |
|--------|-------------|----------|
| Looks good — write context (Recommended) | Sufficient signal; write CONTEXT.md and DISCUSSION-LOG.md | ✓ |
| Specify search query manually | User provides custom X query string | |
| Discuss quota coordination (twitter_monthly_*) | Discuss read/write of shared counter | |
| Discuss insufficient-signal threshold tuning | Tune `fewer than 3 X posts OR fewer than 3 viral stories` → fallback | |

**User's choice:** Write context.
**Notes:** Quota coordination + insufficient-signal threshold left as Claude's Discretion (planner picks).

---

## Claude's Discretion

The following items were noted as planner-decided rather than user-decided:

- Quota counter coordination mechanism (SELECT FOR UPDATE vs naive read-then-write — single-process scheduler with 1 weekly fire makes naive fine)
- X API rate-limit handling (already covered by `tweepy.AsyncClient(wait_on_rate_limit=True)` default)
- Sweep-card width / typography reuse from daily summary feed (`max-w-[720px]`, Geist Variable)
- History-week-picker UX (dropdown label format)
- Exact transaction shape for the idempotency check + agent_runs INSERT
- Whether the sweeper should also set `twitter_monthly_tweet_count` += `len(results)` (recommended: yes, mirror gold_media.py)

## Deferred Ideas

Pulled out of Phase 7 scope and parked in `<deferred>` section of CONTEXT.md:

- **SWEEP-REDDIT-v22:** Reddit ingestion as complementary signal (no plan to revisit unless X proves too narrow)
- **SWEEP-X-USERLIST-v22:** Curated analyst watchlist (re-introduces curation burden the operator dropped)
- **SWEEP-CASHTAG-PRIMARY-v22:** Cashtags-only query variant (easy one-line revisit)
- **SWEEP-DnD-PRIORITY-v22:** Drag-to-pin reorder in the UI
- **SWEEP-WHATSAPP-v22:** Sunday morning WhatsApp ping (was already deferred to v2.2 in ROADMAP)
- **SWEEP-HISTORY-COMPARE-v22:** Side-by-side compare of two weeks
