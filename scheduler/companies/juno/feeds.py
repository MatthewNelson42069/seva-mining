"""Juno defence RSS feeds — Phase 10 DEF-01.

Tier-1 ONLY for v3.0 (per CONTEXT D-10). Tier-2 deferred to v3.1+.

Source-of-truth for the list:
`.planning/phases/10-juno-defence-news-funnel/phase-10-feed-verification.md`
(Wave 0 Phase-0 verification per D-13/D-14). 13/16 endpoints returned
verdict=WORKING; the 3 FALLBACK_TO_SERPAPI endpoints (war.gov, nato.int,
canada.ca defence) are NOT in this list — see JUNO_SERPAPI_QUERIES in
scheduler/companies/juno/serpapi.py.

Per-feed bozo + recent-history health-check (D-12) consumes this list in
scheduler/agents/daily_summary.py::run_juno_daily_summary (Wave 2).
"""

# (source_name, feed_url) tuples — WORKING verdicts from Wave 0 artifact
# (.planning/phases/10-juno-defence-news-funnel/phase-10-feed-verification.md).
# 13 Tier-1 defence feeds total: 8 Defense News sub-feeds + Breaking Defense
# + DefenseScoop + RUSI Commentary + RUSI Publications + SIPRI Combined.
# Raw substrate ~275 entries/fire pre-dedup / pre-relevance-filter.
JUNO_DEFENCE_FEEDS: list[tuple[str, str]] = [
    ("defense_news_industry", "https://www.defensenews.com/arc/outboundfeeds/rss/category/industry/?outputType=xml"),
    ("defense_news_pentagon", "https://www.defensenews.com/arc/outboundfeeds/rss/category/pentagon/?outputType=xml"),
    ("defense_news_global", "https://www.defensenews.com/arc/outboundfeeds/rss/category/global/?outputType=xml"),
    ("defense_news_air", "https://www.defensenews.com/arc/outboundfeeds/rss/category/air/?outputType=xml"),
    ("defense_news_land", "https://www.defensenews.com/arc/outboundfeeds/rss/category/land/?outputType=xml"),
    ("defense_news_naval", "https://www.defensenews.com/arc/outboundfeeds/rss/category/naval/?outputType=xml"),
    ("defense_news_space", "https://www.defensenews.com/arc/outboundfeeds/rss/category/space/?outputType=xml"),
    ("defense_news_unmanned", "https://www.defensenews.com/arc/outboundfeeds/rss/category/unmanned/?outputType=xml"),
    ("breaking_defense", "https://breakingdefense.com/feed/"),
    ("defense_scoop", "https://defensescoop.com/feed/"),
    ("rusi_commentary", "https://www.rusi.org/rss/latest-commentary.xml"),
    ("rusi_publications", "https://www.rusi.org/rss/latest-publications.xml"),
    ("sipri_combined", "https://www.sipri.org/rss/combined.xml"),
]
