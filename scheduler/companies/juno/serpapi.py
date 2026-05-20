"""Juno SerpAPI google_news queries — Phase 10 DEF-02 + DEF-05.

Two-purpose query list:
  1. Canadian Procurement substrate (DEF-05 / D-09) — DND/PSPC have no
     clean RSS; SerpAPI site:-restricted queries fill the gap. 7 queries
     × 1 fire/day × 30 days = 210 calls/month at $15/1K = $3.15/mo
     inside the existing $50/mo cap (~$5.25/mo Juno total per RESEARCH).
  2. SerpAPI fallback for Tier-1 RSS feeds that failed Phase-0 verification
     per Wave 0 artifact (D-13/D-14). FALLBACK_TO_SERPAPI verdicts get a
     site: query here instead of (source_name, url) in JUNO_DEFENCE_FEEDS.
     Wave 0 returned 3 FALLBACK_TO_SERPAPI feeds: war.gov, nato.int,
     canada.ca defence.

NOTE: Per RESEARCH §Open Question 1 — recommend morning-fire only (08:05 PT)
for SerpAPI; 12:05 PT fire re-uses raw_sources_jsonb from morning fire.
Wave 2 (10-03-PLAN.md) implements this gating.
"""

# Query strings — 7 Canadian-procurement (D-09) + 3 SerpAPI fallback (D-13/D-14).
JUNO_SERPAPI_QUERIES: list[str] = [
    # === Canadian Procurement (DEF-05 / D-09) — 7 queries ===
    # Government sites — direct DND/PSPC procurement signal
    "site:canada.ca defence",
    "site:canadiandefencereview.com",
    "site:pspc-spac.gc.ca",
    "site:tpsgc-pwgsc.gc.ca",
    # Topic queries — wider net for contract / procurement language
    '"DND contract"',
    '"RCAF procurement"',
    '"Royal Canadian Navy contract"',

    # === SerpAPI fallback for Tier-1 RSS feeds that failed Phase-0 (D-13/D-14) ===
    # phase-10-feed-verification.md verdict=FALLBACK_TO_SERPAPI rows.
    # canada.ca FALLBACK_TO_SERPAPI is already represented by "site:canada.ca defence"
    # in the Canadian Procurement block above (intentional overlap — single query
    # serves both purposes per Wave 0 artifact §Wave 1 Integration Plan step 2).
    "site:war.gov defence",
    "site:nato.int press release",
    "site:canada.ca DND",
]
