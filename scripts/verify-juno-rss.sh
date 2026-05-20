#!/usr/bin/env bash
# scripts/verify-juno-rss.sh (NEW — Phase 10 Wave 0)
#
# Verify ALL 16 Juno defence RSS endpoints. Output is pipe-delimited so
# phase-10-feed-verification.md can be auto-generated.
#
# Format: feed_name|feed_url|bozo|entries_count|verdict
# verdict: WORKING | DROPPED | FALLBACK_TO_SERPAPI
#
# Usage:
#   bash scripts/verify-juno-rss.sh > .planning/phases/10-juno-defence-news-funnel/feed-verification.raw
#   then human-curate into phase-10-feed-verification.md
#
# Implementation notes:
# - Uses feedparser via `cd scheduler && uv run python -c` so the verification
#   runs through the exact dependency the production code path will use.
# - 16 endpoints = 13 Tier-1 defence feeds + 3 TBD endpoints (D-13).
# - Set -u is enabled (catches unbound vars); -e is NOT set so a single
#   feed failure doesn't abort the run.

set -u

FEEDS=(
    # Tier-1 — 13 sub-feeds (research/STACK.md 2026-05-19)
    "defense_news_industry|https://www.defensenews.com/arc/outboundfeeds/rss/category/industry/?outputType=xml"
    "defense_news_pentagon|https://www.defensenews.com/arc/outboundfeeds/rss/category/pentagon/?outputType=xml"
    "defense_news_global|https://www.defensenews.com/arc/outboundfeeds/rss/category/global/?outputType=xml"
    "defense_news_air|https://www.defensenews.com/arc/outboundfeeds/rss/category/air/?outputType=xml"
    "defense_news_land|https://www.defensenews.com/arc/outboundfeeds/rss/category/land/?outputType=xml"
    "defense_news_naval|https://www.defensenews.com/arc/outboundfeeds/rss/category/naval/?outputType=xml"
    "defense_news_space|https://www.defensenews.com/arc/outboundfeeds/rss/category/space/?outputType=xml"
    "defense_news_unmanned|https://www.defensenews.com/arc/outboundfeeds/rss/category/unmanned/?outputType=xml"
    "breaking_defense|https://breakingdefense.com/feed/"
    "defense_scoop|https://defensescoop.com/feed/"
    "rusi_commentary|https://www.rusi.org/rss/latest-commentary.xml"
    "rusi_publications|https://www.rusi.org/rss/latest-publications.xml"
    "sipri_combined|https://www.sipri.org/rss/combined.xml"
    # 3 TBD endpoints (D-13)
    "war_gov|https://www.war.gov/news/rss/?feedtype=press-releases"
    "nato_news|https://www.nato.int/cps/en/natohq/news.htm?selectedLocale=en&_=feed"
    "canada_ca_defence|https://www.canada.ca/en/news/web-feeds.html"
)

echo "feed_name|feed_url|bozo|entries_count|verdict"
for entry in "${FEEDS[@]}"; do
    NAME="${entry%%|*}"
    URL="${entry#*|}"
    # Use feedparser via inline Python — matches the production code path.
    # `cd scheduler && uv run python` so feedparser is resolved in the
    # scheduler venv (matches DEF-04 health-check production behavior).
    RESULT=$(cd scheduler && uv run python -c "
import feedparser
try:
    f = feedparser.parse('$URL')
    print(f'{int(f.bozo)}|{len(f.entries)}')
except Exception:
    print('-1|0')
" 2>/dev/null)
    BOZO="${RESULT%%|*}"
    COUNT="${RESULT#*|}"
    if [[ "$BOZO" == "0" && "$COUNT" -gt 0 ]]; then
        VERDICT="WORKING"
    elif [[ "$BOZO" == "-1" ]]; then
        VERDICT="DROPPED"
    else
        VERDICT="FALLBACK_TO_SERPAPI"
    fi
    echo "$NAME|$URL|$BOZO|$COUNT|$VERDICT"
done
