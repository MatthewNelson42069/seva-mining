# Phase 10 Feed Verification — Phase-0 Output

**Verified:** 2026-05-20
**Total endpoints checked:** 16 (13 Tier-1 defence + 3 TBD)
**Script:** `bash scripts/verify-juno-rss.sh`
**Raw output:** captured to `/tmp/phase-10-feeds.raw` during Wave 0 Task 1

This artifact is the **source-of-truth** for Wave 1 (`10-02-PLAN.md`) when populating `scheduler/companies/juno/feeds.py::JUNO_DEFENCE_FEEDS` and `scheduler/companies/juno/serpapi.py::JUNO_SERPAPI_QUERIES`. Any endpoint with verdict `DROPPED` or `FALLBACK_TO_SERPAPI` is dropped from `JUNO_DEFENCE_FEEDS` and (where appropriate) replaced with a SerpAPI `site:` query.

## Verification Table

| Feed | URL | Bozo | Entries | Verdict |
|------|-----|------|---------|---------|
| defense_news_industry | https://www.defensenews.com/arc/outboundfeeds/rss/category/industry/?outputType=xml | 0 | 25 | ✓ WORKING |
| defense_news_pentagon | https://www.defensenews.com/arc/outboundfeeds/rss/category/pentagon/?outputType=xml | 0 | 25 | ✓ WORKING |
| defense_news_global | https://www.defensenews.com/arc/outboundfeeds/rss/category/global/?outputType=xml | 0 | 25 | ✓ WORKING |
| defense_news_air | https://www.defensenews.com/arc/outboundfeeds/rss/category/air/?outputType=xml | 0 | 25 | ✓ WORKING |
| defense_news_land | https://www.defensenews.com/arc/outboundfeeds/rss/category/land/?outputType=xml | 0 | 25 | ✓ WORKING |
| defense_news_naval | https://www.defensenews.com/arc/outboundfeeds/rss/category/naval/?outputType=xml | 0 | 25 | ✓ WORKING |
| defense_news_space | https://www.defensenews.com/arc/outboundfeeds/rss/category/space/?outputType=xml | 0 | 25 | ✓ WORKING |
| defense_news_unmanned | https://www.defensenews.com/arc/outboundfeeds/rss/category/unmanned/?outputType=xml | 0 | 25 | ✓ WORKING |
| breaking_defense | https://breakingdefense.com/feed/ | 0 | 15 | ✓ WORKING |
| defense_scoop | https://defensescoop.com/feed/ | 0 | 10 | ✓ WORKING |
| rusi_commentary | https://www.rusi.org/rss/latest-commentary.xml | 0 | 20 | ✓ WORKING |
| rusi_publications | https://www.rusi.org/rss/latest-publications.xml | 0 | 20 | ✓ WORKING |
| sipri_combined | https://www.sipri.org/rss/combined.xml | 0 | 10 | ✓ WORKING |
| war_gov | https://www.war.gov/news/rss/?feedtype=press-releases | 1 | 0 | → FALLBACK_TO_SERPAPI |
| nato_news | https://www.nato.int/cps/en/natohq/news.htm?selectedLocale=en&_=feed | 1 | 0 | → FALLBACK_TO_SERPAPI |
| canada_ca_defence | https://www.canada.ca/en/news/web-feeds.html | 1 | 0 | → FALLBACK_TO_SERPAPI |

## Summary

- **Working (13/16) — included in `JUNO_DEFENCE_FEEDS` for Wave 1:**
  - `defense_news_industry`, `defense_news_pentagon`, `defense_news_global`, `defense_news_air`, `defense_news_land`, `defense_news_naval`, `defense_news_space`, `defense_news_unmanned` (8 Defense News sub-feeds, 25 entries each)
  - `breaking_defense` (15 entries)
  - `defense_scoop` (10 entries)
  - `rusi_commentary` (20 entries)
  - `rusi_publications` (20 entries)
  - `sipri_combined` (10 entries)

- **Dropped (0/16):** None — every endpoint returned a response (no `DROPPED` verdicts).

- **Fallback to SerpAPI (3/16) — Wave 1 must add `site:` queries to `JUNO_SERPAPI_QUERIES`:**
  - `war_gov` — RSS endpoint returned bozo=1, 0 entries. Wave 1 add: `site:war.gov defence` or `site:war.gov procurement`.
  - `nato_news` — non-RSS HTML page; Wave 1 add: `site:nato.int press-release` or `site:nato.int news`.
  - `canada_ca_defence` — RSS index page, not a feed itself; Wave 1 add: `site:canada.ca defence` and `site:canada.ca DND` (complements existing D-09 Canadian Procurement query set).

## Total Entry Volume (Wave 1 substrate sizing)

- 8 Defense News sub-feeds × 25 entries = **200 entries/fire**
- Breaking Defense = 15 entries/fire
- DefenseScoop = 10 entries/fire
- RUSI Commentary = 20 entries/fire
- RUSI Publications = 20 entries/fire
- SIPRI Combined = 10 entries/fire
- **Defence News raw substrate ≈ 275 entries/fire** (pre-dedup, pre-relevance-filter)
- After canonical_url dedup (Phase 7 pattern) + Janes/CSIS editorial cut: expect **3-7 bullets** per Sonnet synthesis (per `DEFENCE_NEWS_SYSTEM_PROMPT` D-02 spec).

## Wave 1 Integration Plan (10-02-PLAN.md handoff)

1. Populate `JUNO_DEFENCE_FEEDS: list[tuple[str, str]]` in `scheduler/companies/juno/feeds.py` with the 13 WORKING `(source_name, feed_url)` tuples in the order above.
2. Add 3 SerpAPI `site:` queries to `JUNO_SERPAPI_QUERIES` in `scheduler/companies/juno/serpapi.py`:
   - `site:war.gov defence`
   - `site:nato.int press release`
   - `site:canada.ca defence`
3. NO `DROPPED` endpoints — no further action.
4. Re-run `bash scripts/verify-juno-rss.sh` after Wave 1 to confirm no Defense News URL drift mid-phase (DEF-04 health-check substrate sanity).
