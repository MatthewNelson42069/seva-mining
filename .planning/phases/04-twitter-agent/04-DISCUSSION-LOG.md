# Phase 4: Twitter Agent - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-01
**Phase:** 04-twitter-agent
**Areas discussed:** Account Watchlist

---

## Account Watchlist

### Starting approach

| Option | Description | Selected |
|--------|-------------|----------|
| Build list together | Suggest accounts by category, user confirms | ✓ |
| User provides list | User supplies handles directly | |

---

### Media / News accounts

| Option | Description | Selected |
|--------|-------------|----------|
| @KitcoNews | Kitco News — the definitive gold price and market news outlet | ✓ |
| @WGCouncil | World Gold Council — official industry body | ✓ |
| @BullionVault | BullionVault — gold price platform with regular market commentary | ✓ |
| @Reuters / @BloombergMkts | Reuters and Bloomberg Markets | ✓ |

**User's choice:** All four selected.

---

### Analyst / Commentator accounts

| Option | Description | Selected |
|--------|-------------|----------|
| @PeterSchiff | Peter Schiff — CEO Euro Pacific Capital, prolific gold bull | ✓ |
| @JimRickards | Jim Rickards — author, gold standard advocate | ✓ |
| @GoldSeekCom | GoldSeek — gold news aggregator | ✓ |
| @RealVision | Real Vision Finance — macro/gold commentary | ✓ |

**User's choice:** All four selected.

---

### Mining major accounts

| Option | Description | Selected |
|--------|-------------|----------|
| Newmont + Barrick | Two largest gold miners globally | ✓ |
| Agnico + Kinross | Mid-tier majors with active social presence | ✓ |
| Franco-Nevada + Wheaton | Streaming/royalty companies | ✓ |
| Skip mining cos for now | Rely on keyword monitoring | |

**User's choice:** All three groups (6 accounts total).

---

### ETF / Fund accounts

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — SPDR + VanEck | @SPDR_ETFs (GLD) and @VanEck (GDX/GDXJ) | ✓ |
| Yes — SPDR only | @SPDR_ETFs only | |
| No ETFs | Skip ETF accounts | |

**User's choice:** Both SPDR and VanEck.

---

### Additional accounts (user-provided)

User added 8 more accounts directly:
- `@GoldTelegraph_`
- `@TaviCosta`
- `@Mike_maloney`
- `@MacleodFinance`
- `@DanielaCambone`
- `@WSBGold`
- `@Frank_Giustra`
- `@RonStoeferle`

---

### Engagement gate refinement (user-initiated change)

User specified: "The requirements is 500+ likes, but let's also make it 40k views + as well. Both requirements"

This changed the original OR-based gate to an AND-based gate with a views component:
- Non-watchlist: 500+ likes **AND** 40,000+ views (both required)
- Watchlist: 50+ likes **AND** 5,000+ views (both required)

| Option | Description | Selected |
|--------|-------------|----------|
| 50+ likes AND 5k views | Lower bar for trusted watchlist accounts | ✓ |
| 50+ likes only | Original spec, no views requirement | |
| Same as non-watchlist | 500 likes + 40k views regardless | |

---

### Topic filter for watchlist accounts (user-initiated requirement)

User specified: "The tweets from any of these accounts have to be about gold for it to be flagged"

| Option | Description | Selected |
|--------|-------------|----------|
| Keyword presence check | Fast, zero API cost keyword scan | |
| Lightweight Claude call | Brief Claude classification | |
| Both — keyword first, Claude fallback | Keyword check first; Claude confirms borderline cases | ✓ |

---

### Trending non-watchlist tweets (user-initiated requirement)

User specified: "if there is highly trending tweets about gold that are not from these accounts, those should be mentioned as well"

| Option | Description | Selected |
|--------|-------------|----------|
| 500+ likes AND 40k views | Same gate as standard non-watchlist | ✓ |
| 1k+ likes AND 100k+ views | Raise bar for unknown accounts | |
| 100k+ views only | Prioritise reach over engagement | |

---

### Priority scoring (relationship_value)

| Option | Description | Selected |
|--------|-------------|----------|
| Tiered by influence | Analysts/news = 5, majors = 3, others = 2 | |
| All equal at 3 | Uniform starting point | |
| All at 5 | Maximum priority for all watchlist accounts | ✓ |

**User's choice:** All watchlist accounts set to `relationship_value = 5`.

---

## Claude's Discretion

- Keyword/cashtag seed list for the `keywords` table
- Draft style details (reply length, RT-with-comment format)
- Compliance checker prompt wording
- Quota counter storage location
- Exact Claude fallback topic classification prompt

## Deferred Ideas

None surfaced during discussion.
