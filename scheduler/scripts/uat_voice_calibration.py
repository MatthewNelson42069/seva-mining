"""Phase 10 DEF-10 — Voice Calibration UAT one-shot script.

Runs Sonnet 4.6 + Haiku 4.5 against the 8-story curated corpus from
.planning/phases/10-juno-defence-news-funnel/voice_calibration_uat_corpus.md
and emits a markdown report to stdout.

Usage:
    cd scheduler && uv run python scripts/uat_voice_calibration.py > /tmp/uat_output.md

Requires ANTHROPIC_API_KEY in env (sourced from .env via dotenv).

Pure dry-run — no DB writes, no production cron fire. Exercises the exact
production code path (_build_juno_defence_news_section,
_build_juno_canadian_procurement_section, classify_story, survives_threshold,
call_with_refusal_guard) with curated fixture input.

Phase 10 Wave 3 / 10-04-PLAN.md Task 3.
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Make scheduler/ importable when running from anywhere
SCHEDULER_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCHEDULER_DIR))

# Load .env BEFORE importing anything that reads settings
try:
    from dotenv import load_dotenv  # type: ignore[import-untyped]
    load_dotenv(SCHEDULER_DIR.parent / ".env")
except Exception:
    pass

# Set required env defaults BEFORE settings load (in case .env isn't fully populated)
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://fake-pooler.neon.tech/db?sslmode=require"
)
os.environ.setdefault("TWILIO_ACCOUNT_SID", "x")
os.environ.setdefault("TWILIO_AUTH_TOKEN", "x")
os.environ.setdefault("TWILIO_WHATSAPP_FROM", "whatsapp:+1x")
os.environ.setdefault("DIGEST_WHATSAPP_TO", "whatsapp:+1x")
os.environ.setdefault("X_API_BEARER_TOKEN", "x")
os.environ.setdefault("X_API_KEY", "x")
os.environ.setdefault("X_API_SECRET", "x")
os.environ.setdefault("FRONTEND_URL", "https://x.com")

from anthropic import AsyncAnthropic  # noqa: E402

from agents.daily_summary import (  # noqa: E402
    _build_juno_defence_news_section,
    _build_juno_world_events_section,
    JUNO_SONNET_MODEL,
    JUNO_SONNET_MAX_PROCUREMENT,
    JUNO_SONNET_TIMEOUT,
)
from agents.juno_refusal_detector import call_with_refusal_guard  # noqa: E402
from agents.juno_relevance import (  # noqa: E402
    classify_story,
    survives_threshold,
    DefenceRelevance,
)
from companies.juno.prompts import DEFENCE_NEWS_SYSTEM_PROMPT  # noqa: E402
from config import get_settings  # noqa: E402


# -----------------------------------------------------------------------------
# Corpus — 8 hand-curated defence stories, matching the corpus markdown
# (.planning/phases/10-juno-defence-news-funnel/voice_calibration_uat_corpus.md)
# -----------------------------------------------------------------------------

DEFENCE_STORIES: list[dict] = [
    {
        "source_name": "Defense News",
        "title": "Lockheed Martin wins $1.8B PAC-3 Missile Segment Enhancement contract",
        "summary": (
            "Lockheed Martin's Missiles and Fire Control business unit was awarded "
            "a $1.84B contract modification for additional PAC-3 Missile Segment "
            "Enhancement (MSE) interceptors. The deal covers production lot 32 "
            "deliveries and includes spare parts, ground support equipment, and "
            "engineering services through Q4 2028. The PAC-3 MSE is the high-end "
            "variant of the Patriot air-defense system's interceptor family and has "
            "been heavily drawn down by deliveries to Ukraine, Saudi Arabia, and "
            "South Korea. Army officials cited 'urgent replenishment requirements' "
            "in the contract justification."
        ),
        "link": "https://www.defensenews.com/industry/2026/05/15/lockheed-pac-3-mse-contract-award/",
        "published": "2026-05-15",
    },
    {
        "source_name": "Defense News",
        "title": "Raytheon awarded $500M JADC2 follow-on contract for joint C2 integration",
        "summary": (
            "Raytheon Intelligence & Space received a $500M follow-on contract for "
            "continued development of the Joint All-Domain Command and Control "
            "(JADC2) integration framework. The award extends prior work on "
            "connecting Army, Navy, and Air Force C2 systems via a common data "
            "fabric. Pentagon officials emphasized the focus on 'interoperability "
            "across service-specific battle management systems,' not on weapons "
            "employment. The contract runs through Q2 2029 with an option for a "
            "$250M extension."
        ),
        "link": "https://www.defensenews.com/pentagon/2026/05/14/raytheon-jadc2-followon-award/",
        "published": "2026-05-14",
    },
]

CANADIAN_PROCUREMENT_STORIES: list[dict] = [
    {
        "source_name": "canada.ca",
        "title": "DND announces P-8A Poseidon delivery schedule under $5.9B CMMA program",
        "summary": (
            "The Department of National Defence confirmed that Boeing will deliver "
            "the first two of 16 P-8A Poseidon maritime patrol aircraft to the "
            "Royal Canadian Air Force in late 2027, with the full fleet operational "
            "by 2033. The aircraft replace the legacy CP-140 Aurora fleet under the "
            "$5.9B (CAD) Canadian Multi-Mission Aircraft (CMMA) program. Defence "
            "Minister stated the new aircraft will 'modernize Canada's surveillance "
            "and anti-submarine warfare capabilities in the Arctic and North "
            "Atlantic.' Industrial offsets include Canadian content commitments "
            "from Boeing's Winnipeg facility."
        ),
        "link": "https://www.canada.ca/en/department-national-defence/news/2026/05/p-8a-delivery-schedule.html",
        "published": "2026-05-13",
    },
    # Climate+defence story routed to Canadian Procurement (Story 8 — low-confidence accept)
    {
        "source_name": "canada.ca",
        "title": "Canada's federal climate plan includes $1.2B in defence-base resiliency funding",
        "summary": (
            "Environment and Climate Change Canada released the 2026 federal "
            "climate adaptation strategy, which includes $1.2B (CAD) over five "
            "years for resiliency upgrades to Canadian Armed Forces bases. The "
            "funding covers seawalls at CFB Esquimalt and CFB Halifax, drainage "
            "upgrades at five Arctic stations, and grid resilience for CFB "
            "Trenton. The plan was developed jointly with DND and PSPC. The "
            "funding sits inside the broader $14B (CAD) climate adaptation "
            "envelope but represents the first time DND infrastructure has been "
            "explicitly carved out as a discrete budget line."
        ),
        "link": "https://www.canada.ca/en/environment-climate-change/news/2026/05/climate-defence-base-resiliency.html",
        "published": "2026-05-12",
    },
]

# World Events stories — these flow through Haiku classifier first.
WORLD_EVENTS_STORIES: list[dict] = [
    # Story 4 — Active conflict (Ukraine ATACMS)
    {
        "source_name": "Reuters World",
        "title": "Ukraine receives latest ATACMS delivery from US under Presidential Drawdown Authority",
        "summary": (
            "The United States completed delivery of an additional tranche of "
            "Army Tactical Missile System (ATACMS) munitions to Ukraine under "
            "the Presidential Drawdown Authority. The package, valued at "
            "approximately $400M, brings cumulative ATACMS deliveries to Ukraine "
            "to over 350 missiles since the program began. Ukrainian officials "
            "confirmed receipt without disclosing specific deployment locations. "
            "The shipment was authorized under the Biden administration's October "
            "2024 policy update permitting Ukraine to use US-supplied long-range "
            "munitions against military targets inside internationally recognized "
            "Russian territory."
        ),
        "link": "https://www.reuters.com/world/europe/ukraine-atacms-delivery-2026-05-13",
        "published": "2026-05-13",
    },
    # Story 5 — Sanctions/Export controls (EUV)
    {
        "source_name": "Reuters World",
        "title": "US imposes new EUV export controls on China, expanding Entity List by 17 firms",
        "summary": (
            "The Bureau of Industry and Security announced new export controls "
            "restricting shipments of Extreme Ultraviolet (EUV) lithography "
            "systems, components, and design software to China. The controls add "
            "17 Chinese semiconductor firms to the Entity List, including "
            "subsidiaries of SMIC and YMTC. ASML, the sole producer of EUV "
            "systems, indicated the new rules will affect approximately $2.3B in "
            "annual revenue. Commerce Secretary cited 'national security "
            "concerns' related to military-grade chip production. China's "
            "Commerce Ministry called the action 'discriminatory' and signaled "
            "potential retaliation against US semiconductor inputs."
        ),
        "link": "https://www.reuters.com/business/2026/05/12/us-euv-export-controls-china-expansion",
        "published": "2026-05-12",
    },
    # Story 6 — Borderline (Apple Vision — SHOULD REJECT)
    {
        "source_name": "Bloomberg",
        "title": "Apple Vision Pro 2 launches with defense-grade encryption, eyes enterprise market",
        "summary": (
            "Apple unveiled the second-generation Vision Pro headset at WWDC "
            "2026, highlighting new 'defense-grade AES-256 encryption' for "
            "enterprise communications. The device targets the enterprise "
            "productivity market with starting price $2,499. Apple cited "
            "interest from Fortune 500 companies including JPMorgan and Boeing's "
            "commercial aviation division for collaboration and training use "
            "cases. The company explicitly noted the device is 'not designed for "
            "or marketed to defense or government customers' and does not carry "
            "ITAR classification."
        ),
        "link": "https://www.bloomberg.com/news/2026/05/14/apple-vision-pro-2-defense-grade-encryption",
        "published": "2026-05-14",
    },
    # Story 7 — Borderline (Skydio drone — DUAL-USE EXCLUSION)
    {
        "source_name": "TechCrunch",
        "title": "Skydio releases X10D consumer drone with dual-use applications for first responders",
        "summary": (
            "Skydio launched the X10D, a new consumer-targeted autonomous drone "
            "with marketing emphasis on dual-use applications including first-"
            "responder, search-and-rescue, and infrastructure inspection "
            "scenarios. The $1,999 drone uses Skydio's autonomy software stack "
            "and is sold direct-to-consumer with no export restrictions. Skydio "
            "CEO noted that 'the same autonomy capabilities serve enterprise and "
            "government customers under separate SKUs,' though the X10D itself "
            "is not classified or restricted."
        ),
        "link": "https://techcrunch.com/2026/05/13/skydio-x10d-consumer-drone-dual-use",
        "published": "2026-05-13",
    },
]


async def _build_canadian_procurement_curated(
    client: AsyncAnthropic, stories: list[dict]
) -> tuple[str | None, dict]:
    """Inline Canadian Procurement synthesis using the curated stories.

    Mirrors the production path in _build_juno_canadian_procurement_section
    (Sonnet 4.6, JUNO_SONNET_MAX_PROCUREMENT, DEFENCE_NEWS_SYSTEM_PROMPT,
    refusal-guard) but skips the SerpAPI step — instead feeds the curated
    canada.ca stories directly to Sonnet.
    """
    bullets = "\n\n".join(
        f"- {s.get('title','')}\n  "
        f"{(s.get('summary','') or '')[:500]} "
        f"({s.get('source_name', 'unknown')})"
        for s in stories
    )
    user_prompt = (
        "Synthesize the following Canadian defence procurement signals into a "
        "Canadian Procurement section. Output 3-5 bullets in markdown, each "
        "ending with `(Source Name)` attribution. Extract contract values "
        "where present. Use the section header "
        "`### 🇨🇦 Canadian Procurement`.\n\n"
        f"{bullets}"
    )
    return await call_with_refusal_guard(
        client,
        model=JUNO_SONNET_MODEL,
        max_tokens=JUNO_SONNET_MAX_PROCUREMENT,
        system=DEFENCE_NEWS_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        section_name="canadian_procurement",
    )


async def _classify_world_events(
    client: AsyncAnthropic, stories: list[dict]
) -> list[tuple[dict, DefenceRelevance | None, bool]]:
    """Run Haiku classifier on each World Events story.

    Returns list of (story, classifier_result_or_None, survives_threshold).
    """
    results: list[tuple[dict, DefenceRelevance | None, bool]] = []
    for s in stories:
        try:
            verdict = await classify_story(
                client,
                title=s.get("title", ""),
                snippet=s.get("summary", ""),
            )
        except Exception as exc:  # noqa: BLE001
            print(
                f"WARN: classify_story raised on {s.get('title','?')[:50]}: "
                f"{type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            results.append((s, None, False))
            continue
        survives = survives_threshold(verdict)
        results.append((s, verdict, survives))
    return results


async def _build_world_events_curated(
    client: AsyncAnthropic,
    classifier_results: list[tuple[dict, DefenceRelevance | None, bool]],
) -> tuple[str | None, dict]:
    """Inline World Events synthesis from the classifier-survived stories.

    Mirrors _build_juno_world_events_section synthesis path (Sonnet 4.6,
    DEFENCE_NEWS_SYSTEM_PROMPT, refusal-guard).
    """
    survived = [
        (s, verdict) for (s, verdict, ok) in classifier_results if ok and verdict is not None
    ]
    if not survived:
        return (
            "",
            {
                "world_events_survived": 0,
                "world_events_total_seen": len(classifier_results),
            },
        )

    bullets = "\n\n".join(
        f"- **{rel.category}** ({rel.confidence:.2f}): {s.get('title','')}\n"
        f"  {(s.get('summary','') or '')[:400]} ({s.get('source_name','?')})"
        for (s, rel) in survived[:25]
    )
    user_prompt = (
        "Synthesize the following defence-relevant world-events stories "
        "(pre-filtered by relevance classifier) into a World Events Relevant "
        "to Defence section. Output 5-7 bullets in markdown, each ending with "
        "`(Source Name)`. Use the section header "
        f"`### 🌐 World Events Relevant to Defence`.\n\n{bullets}"
    )
    from agents.daily_summary import JUNO_SONNET_MAX_WORLD

    text, diagnostic = await call_with_refusal_guard(
        client,
        model=JUNO_SONNET_MODEL,
        max_tokens=JUNO_SONNET_MAX_WORLD,
        system=DEFENCE_NEWS_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        section_name="world_events",
    )
    diagnostic["world_events_total_seen"] = len(classifier_results)
    diagnostic["world_events_survived"] = len(survived)
    diagnostic["world_events_categories"] = {
        rel.category: sum(
            1 for (_, v, ok) in classifier_results if ok and v is not None and v.category == rel.category
        )
        for (_, rel) in survived
    }
    return (text, diagnostic)


def _format_classifier_table(
    results: list[tuple[dict, DefenceRelevance | None, bool]],
) -> str:
    """Markdown table of classifier verdicts."""
    rows = [
        "| Story | is_relevant | category | confidence | survives_threshold |",
        "|-------|-------------|----------|------------|--------------------|",
    ]
    story_short = {
        "Ukraine receives latest ATACMS": "4 (Ukraine ATACMS)",
        "US imposes new EUV export controls": "5 (EUV controls)",
        "Apple Vision Pro 2 launches": "6 (Apple Vision)",
        "Skydio releases X10D": "7 (Skydio drone)",
    }
    for s, verdict, survives in results:
        title = s.get("title", "?")
        label = next(
            (v for k, v in story_short.items() if k in title), title[:30]
        )
        if verdict is None:
            rows.append(f"| {label} | (error) | (error) | -- | False |")
        else:
            rows.append(
                f"| {label} | {verdict.is_relevant} | {verdict.category} | "
                f"{verdict.confidence:.2f} | {survives} |"
            )
    return "\n".join(rows)


async def main() -> None:
    settings = get_settings()
    if not settings.anthropic_api_key:
        print("ERROR: ANTHROPIC_API_KEY not set in env", file=sys.stderr)
        sys.exit(1)

    client = AsyncAnthropic(
        api_key=settings.anthropic_api_key, timeout=JUNO_SONNET_TIMEOUT,
    )

    # -------------------------------------------------------------------------
    # Section 1: Defence News (Stories 1-2)
    # -------------------------------------------------------------------------
    print("# Voice Calibration UAT — Sample Sonnet Output", file=sys.stderr)
    print("Running Defence News synthesis (Sonnet 4.6, Stories 1-2)...", file=sys.stderr)
    defence_md, defence_diag = await _build_juno_defence_news_section(
        client, DEFENCE_STORIES
    )

    # -------------------------------------------------------------------------
    # Section 2: Canadian Procurement (Stories 3 + 8)
    # -------------------------------------------------------------------------
    print("Running Canadian Procurement synthesis (Sonnet 4.6, Stories 3+8)...", file=sys.stderr)
    procurement_md, procurement_diag = await _build_canadian_procurement_curated(
        client, CANADIAN_PROCUREMENT_STORIES
    )

    # -------------------------------------------------------------------------
    # Section 3: World Events — classifier first, then synthesis (Stories 4-7)
    # -------------------------------------------------------------------------
    print("Running Haiku classifier on World Events candidates (Stories 4-7)...", file=sys.stderr)
    classifier_results = await _classify_world_events(client, WORLD_EVENTS_STORIES)

    print("Running World Events synthesis (Sonnet 4.6)...", file=sys.stderr)
    world_md, world_diag = await _build_world_events_curated(client, classifier_results)

    # -------------------------------------------------------------------------
    # Emit markdown report to stdout
    # -------------------------------------------------------------------------
    print("## Defence News\n")
    print(defence_md or "(refusal-detected — would write SECTION_UNAVAILABLE_COPY)")
    print()
    print(f"_Diagnostic: {defence_diag}_\n")

    print("## Canadian Procurement\n")
    print(procurement_md or "(refusal-detected — would write SECTION_UNAVAILABLE_COPY)")
    print()
    print(f"_Diagnostic: {procurement_diag}_\n")

    print("## World Events Relevant to Defence\n")
    print(world_md or "(refusal-detected — would write SECTION_UNAVAILABLE_COPY)")
    print()
    print(f"_Diagnostic: {world_diag}_\n")

    print("## Haiku Classifier Verdicts (Stories 4-7)\n")
    print(_format_classifier_table(classifier_results))
    print()


if __name__ == "__main__":
    asyncio.run(main())
