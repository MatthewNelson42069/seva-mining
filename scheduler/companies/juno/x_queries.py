"""v3.1 Phase 15 — Juno Weekly Viral Sweeper X recent-search query (D-01, D-02).

Exports `JUNO_SWEEPER_X_QUERY`: a single combined search query per Sunday
cron (D-01). Defence-sector handles + hashtags only — defence-prime equity
cashtags (Lockheed Martin, RTX/Raytheon, Leidos, BAE Systems, General
Dynamics, Northrop Grumman, Boeing, etc.) are EXCLUDED per PROJECT.md
anti-feature on equity/financial signals on defence primes.

Final corrected handle set (D-02 + RESEARCH §1 corrections):

  Think-tanks (3):  @RUSI_org, @CSIS, @IISS_org
  Defence press (4): @defense_news, @BreakingDefense, @DefenseScoop, @JanesINTEL
  Canadian (4):      @CDAInstitute, @CanadianForces, @DavePerryCGAI, @Murray_Brewster
  Hashtags (2):      #defence, #NATO

Corrections vs CONTEXT.md original D-02 (per RESEARCH §1 — 4 of 9 starter
handles would have returned 0 hits as originally spelled):
  - @DefenseNews     -> defense_news (snake_case official handle)
  - @CDA_CDAI        -> CDAInstitute (correct CDA Institute handle)
  - @canadaforces    -> CanadianForces (correct CAF handle)
  - @JanesIntel      -> JanesINTEL (case-variant — official form)
  - ADDED Tier-2 Canadian: @DavePerryCGAI, @Murray_Brewster (RESEARCH §2)

Query length: ~250 chars (well inside X API Basic-tier 512-char limit per
RESEARCH §3 — NOT the 1024-char Academic tier limit that CONTEXT.md
originally cited).

Tunability path (D-02): @CadsiCanada (industry association) + @NationalDefence
(DND official) are RESERVED candidates if v1.0 signal proves thin. Adding
both stays well inside 512 chars (~308 chars after expansion).
"""
from __future__ import annotations

JUNO_SWEEPER_X_QUERY: str = (
    "(from:RUSI_org OR from:CSIS OR from:IISS_org OR "
    "from:defense_news OR from:BreakingDefense OR from:DefenseScoop OR "
    "from:JanesINTEL OR from:CDAInstitute OR from:CanadianForces OR "
    "from:DavePerryCGAI OR from:Murray_Brewster OR "
    "#defence OR #NATO) -is:retweet lang:en"
)
