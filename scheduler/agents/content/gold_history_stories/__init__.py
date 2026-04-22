"""Curated whitelist of pre-researched gold-industry fact sheets (quick-260422-lbb).

Each fact sheet is a JSON file in this directory named by its ``story_slug``
(e.g. ``bre-x-busang-fraud-1997.json``). The loader validates every story on
load so bad data fails loudly at startup rather than silently poisoning the
drafter.

Design decisions (context: .planning/quick/260422-lbb-harden-gold-history-py-so-it-only-produc/260422-lbb-CONTEXT.md):

  D-01 — Curated whitelist replaces Claude-from-memory picker.
  D-02 — Stories pre-researched at commit time; user reviews PR diff before merge.
  D-03 — Drafter locked to verified_facts via FACT FIDELITY clause; no invented specifics.
  D-04 — Drafter output gains a top-level ``sources`` field for dashboard audit trail.
  D-05 — Runtime SerpAPI verification removed; facts pre-verified at commit time.

Fact-sheet JSON schema::

    {
      "story_slug": "bre-x-busang-fraud-1997",
      "story_title": "...",
      "summary": "1-2 sentence hook for the picker",
      "tags": ["fraud", "1990s", "exploration"],
      "recommended_arc": "Hook → rising → climax → payoff (one line)",
      "verified_facts": [
        {"claim": "...", "source_url": "https://...", "published_date": "YYYY-MM-DD"}
      ],
      "sources": [
        {"ref": "[1]", "url": "...", "publisher": "...", "accessed_date": "2026-04-22"}
      ]
    }

Required story keys: story_slug, story_title, summary, verified_facts, sources.
Required fact keys: claim, source_url (published_date optional for fuzzy historical dates).
Required source keys: url, publisher (ref + accessed_date recommended, not enforced).
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

STORIES_DIR: Path = Path(__file__).parent

REQUIRED_STORY_KEYS: tuple[str, ...] = (
    "story_slug",
    "story_title",
    "summary",
    "verified_facts",
    "sources",
)

REQUIRED_FACT_KEYS: tuple[str, ...] = ("claim", "source_url")

REQUIRED_SOURCE_KEYS: tuple[str, ...] = ("url", "publisher")


def _validate_story(data: dict, filename: str) -> None:
    """Validate a single story dict against the required schema.

    Raises ValueError with a descriptive message if any constraint is violated.
    """
    for k in REQUIRED_STORY_KEYS:
        if k not in data:
            raise ValueError(f"{filename}: missing required story key '{k}'")

    facts = data.get("verified_facts", [])
    if not facts:
        raise ValueError(f"{filename}: verified_facts must be non-empty")
    for i, fact in enumerate(facts):
        if not fact.get("source_url"):
            raise ValueError(
                f"{filename}: verified_facts[{i}] missing required 'source_url' — {fact}"
            )

    sources = data.get("sources", [])
    if not sources:
        raise ValueError(f"{filename}: sources must be non-empty")
    for i, source in enumerate(sources):
        for sk in REQUIRED_SOURCE_KEYS:
            if sk not in source:
                raise ValueError(
                    f"{filename}: sources[{i}] missing required key '{sk}' — {source}"
                )


def load_all_stories() -> list[dict]:
    """Load and validate all JSON fact sheets from this directory.

    Returns a list of story dicts sorted by story_slug for deterministic
    ordering in tests. Raises ValueError on schema violations so bad data
    is caught immediately.
    """
    stories: list[dict] = []
    for path in sorted(STORIES_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise ValueError(f"{path.name}: failed to load — {exc}") from exc
        _validate_story(data, path.name)
        stories.append(data)
    return sorted(stories, key=lambda s: s["story_slug"])


def load_fact_sheet(slug: str) -> dict | None:
    """Load a single fact sheet by story_slug.

    Returns the validated fact-sheet dict, or None if no file with that slug
    exists. Raises ValueError if the file exists but fails schema validation.
    """
    path = STORIES_DIR / f"{slug}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ValueError(f"{path.name}: failed to load — {exc}") from exc
    _validate_story(data, path.name)
    return data
