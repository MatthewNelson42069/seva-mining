"""Juno tenant config (Phase 9 stub — Phase 10 fills the lists).

v3.0 Phase 9 (per CONTEXT.md "Claude's Discretion" — minimal ~30-line
skeleton). Ships a minimal stub so the Juno daily_summary cron can fire and
write a status='partial' daily_summaries row from Phase 9 onward. Phase 10
(DEF-01..10) replaces the empty lists with real defence RSS feeds + SerpAPI
queries + Sonnet system prompt.
"""
from .feeds import JUNO_DEFENCE_FEEDS
from .prompts import DEFENCE_NEWS_SYSTEM_PROMPT
from .serpapi import JUNO_SERPAPI_QUERIES

__all__ = [
    "JUNO_DEFENCE_FEEDS",
    "JUNO_SERPAPI_QUERIES",
    "DEFENCE_NEWS_SYSTEM_PROMPT",
]
