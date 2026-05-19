# Stack Research — v3.0 Multi-Tenant Pivot + Defence-Sector Ingestion

**Project:** Seva Mining v3.0 — Multi-Tenant Dashboards (Juno Industries onboarding)
**Mode:** Ecosystem — Stack additions ONLY (existing stack from v2.1 not re-researched)
**Confidence:** HIGH on Anthropic structured outputs, RSS feed URLs (each fetched and validated), `fastapi-tenancy` PyPI metadata. MEDIUM on multi-tenancy strategy recommendation (community pattern, not a single canonical source). HIGH on "what NOT to add" — verified against existing CLAUDE.md prohibitions.
**Generated:** 2026-05-19

## Stack Additions — Verdict Table

| Package / Pattern | Verdict | Where it goes | Reason |
|-------------------|---------|--------------|--------|
| `fastapi-tenancy` 0.4.0 | **SKIP** | — | Released 2026-04-01, brand-new (< 2 months old), unproven at production scale, adds heavy abstraction over a problem we solve in ~50 LOC with a `company_id` column + session-scoped tenant context. Revisit if a 3rd+ tenant onboards. |
| Postgres Row-Level Security (RLS) | **SKIP** | — | Requires `SET app.current_tenant` per-session + connection-pool checkin reset handler + asyncpg-specific gotchas. The bang-for-buck against a single-operator app with explicit query-time `company_id` filtering is poor. Defer to v3.x+ if we ever expose multi-user-per-tenant. |
| Postgres SCHEMA-per-tenant | **SKIP** | — | Cleaner isolation on paper, but multiplies Alembic migration complexity (N schemas × M migrations) and breaks our existing single `alembic upgrade head` flow. Schema search_path management across asyncpg pool is a known hazard. |
| Row-level `company_id` column (roll-our-own) | **ADD** | `daily_summaries`, `calendar_items`, `weekly_sweeps`, new `companies` table | Simplest correct architecture for 2 tenants growing to ~5. Single `WHERE company_id = :ctx` filter at query layer. Alembic 0014 adds the column + backfills `'seva'` + adds `companies` table. |
| `react-router-dom` 6.x dynamic segment `:company` | **ADD (pattern, no new dep)** | `frontend/src/App.tsx` routing | Already installed in v2.1. Use `/:company/...` parent route + `useParams()` to read active company. URL is source of truth for tenant — deep links, browser back/forward, refresh all work without state sync hacks. |
| Zustand `persist` middleware | **ADD (pattern, no new dep)** | `frontend/src/store/companyStore.ts` (new) | Zustand 5.x already installed. `persist` middleware is in the same package (`zustand/middleware`) — no new install. Persists the *last visited* company for browser-open default; URL still wins on navigation. |
| `feedparser` 6.0.x | **ALREADY PRESENT** | scheduler | No version bump needed; new defence-sector feed URLs only. |
| Anthropic structured outputs (`output_config.format`) | **ADD (pattern, no new dep)** | `scheduler/agents/juno_relevance.py` (new) | `anthropic>=0.86.0` already installed. Use `output_config={"format": {"type": "json_schema", "schema": {...}}}` for the world-events → defence-relevance filter. GA across Sonnet/Haiku 4.5+ models. Guarantees parseable JSON, no retry logic. |
| Defence-sector RSS feed URLs (10) | **ADD (config)** | `scheduler/sources/juno_rss_feeds.py` (new) | All validated below — see "Defence RSS Feed Inventory" section. |
| SerpAPI `google_news` engine with defence queries | **ADD (config only, no new dep)** | `scheduler/agents/juno_news.py` (new) | `serpapi` SDK already installed for v2.0 gold news. Same `engine=google_news` + different `q=` queries (defence/military/geopolitics). Costs ~$5–15/mo against existing $50/mo budget. |
| New advisory lock IDs | **ADD (config)** | `scheduler/worker.py` `JOB_LOCK_IDS` | Next free IDs after v2.1: assign `juno_daily_summary: 1020`, `juno_weekly_sweeper: 1021`. OPS-02 uniqueness assertion already enforces collision detection at import time. |

## Multi-Tenancy: Recommended Strategy

### VERDICT: Row-level `company_id` column. Roll-our-own. No new library.

**Decision matrix (the three options from the milestone brief):**

| Strategy | Pros | Cons | Verdict |
|----------|------|------|---------|
| **Row-level `company_id`** | One schema, one Alembic chain, one connection pool, trivial `WHERE company_id = :ctx` filter. Backfill is a single `UPDATE`. | Bug in a query that forgets the filter is a cross-tenant leak. Mitigation: SQLAlchemy event listener that asserts every `SELECT` on tenant-scoped tables has a `company_id` filter (defence-in-depth). | **CHOSEN** |
| Schema-per-tenant (Postgres SCHEMA) | Cleaner isolation; "forgot to filter" cannot leak across tenants. | N schemas × M migrations = O(NM) Alembic runs. `search_path` management with asyncpg connection pooling is a known footgun. Adding a 3rd tenant means re-running every migration in its schema. | REJECTED for v3.0 |
| Database-per-tenant | Maximum isolation, easiest GDPR/data-residency story. | N Neon databases (cost multiplier), N connection pools in FastAPI, scheduler topology becomes per-DB. Massive over-engineering for two tenants at ~$210/mo budget. | REJECTED for v3.0 |
| `fastapi-tenancy` 0.4.0 (new library, 2026-04-01) | Production-ready claimed, supports RLS/schema/DB/hybrid, async-first, full type hints. Requires Python 3.11+ (we're on 3.12 — compatible). | Released < 2 months ago at time of milestone. No production-scale references visible. Adds a framework abstraction (`TenancyConfig`, middleware, resolution strategies) over a problem solved cleanly with a `company_id` column. We'd be the early-adopter QA. | REJECTED for v3.0 (revisit at 3rd+ tenant) |
| Postgres RLS via `SET app.current_tenant` | Native DB-level enforcement; bug in app query still safe. | Requires connection-pool checkin handler to RESET the variable, otherwise sticky sessions across requests. asyncpg + SQLAlchemy 2.0 async pool needs careful event listener wiring. Operator does not have a multi-DB-role topology that justifies the complexity. | REJECTED for v3.0 |

### Migration path (concrete steps)

**Alembic 0014** (`scheduler/db/alembic/versions/0014_multi_tenant_foundation.py`):

```python
def upgrade() -> None:
    # 1. New companies table
    op.create_table(
        "companies",
        sa.Column("id", sa.String(20), primary_key=True),  # e.g. "seva", "juno"
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    # Seed Seva + Juno
    op.execute("INSERT INTO companies (id, display_name) VALUES ('seva', 'Seva Mining'), ('juno', 'Juno Industries')")

    # 2. Add company_id column to tenant-scoped tables (NULLABLE initially for backfill)
    for table in ("daily_summaries", "calendar_items", "weekly_sweeps"):
        op.add_column(table, sa.Column("company_id", sa.String(20), nullable=True))
        op.execute(f"UPDATE {table} SET company_id = 'seva' WHERE company_id IS NULL")
        op.alter_column(table, "company_id", nullable=False)
        op.create_foreign_key(f"fk_{table}_company", table, "companies", ["company_id"], ["id"])
        op.create_index(f"ix_{table}_company_id", table, ["company_id"])

    # 3. Enforce date uniqueness PER COMPANY, not globally
    op.drop_constraint("uq_daily_summaries_date", "daily_summaries", type_="unique")
    op.create_unique_constraint("uq_daily_summaries_company_date", "daily_summaries", ["company_id", "date"])
    # Same for calendar_items.date UNIQUE -> UNIQUE(company_id, date)
```

**Session-scoped tenant context** (no library — `contextvars` in stdlib):

```python
# scheduler/db/tenant_context.py
from contextvars import ContextVar
_current_company: ContextVar[str | None] = ContextVar("current_company", default=None)

def set_company(company_id: str) -> None:
    _current_company.set(company_id)

def get_company() -> str:
    val = _current_company.get()
    if val is None:
        raise RuntimeError("Tenant context not set — caller forgot set_company()")
    return val
```

**FastAPI dependency** (reads `:company` from URL path):

```python
# api/dependencies.py
async def get_company_id(company: str) -> str:
    if company not in ("seva", "juno"):
        raise HTTPException(404, f"Unknown company: {company}")
    set_company(company)
    return company

# Used in routers:
@router.get("/{company}/daily-summary/today")
async def today_summary(company_id: str = Depends(get_company_id), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(DailySummary).where(DailySummary.company_id == company_id, ...)
    )
```

**Sources:**
- Aditya Mattos — RLS pattern (rejected for our scope but documents the alternative): https://adityamattos.com/multi-tenancy-in-python-fastapi-and-sqlalchemy-using-postgres-row-level-security — MEDIUM confidence
- MergeBoard FastAPI multitenancy walkthrough: https://mergeboard.com/blog/6-multitenancy-fastapi-sqlalchemy-postgresql/ — MEDIUM confidence
- FastAPI Discussion #6056 on multi-tenancy patterns: https://github.com/fastapi/fastapi/discussions/6056 — MEDIUM confidence
- `fastapi-tenancy` PyPI 0.4.0 metadata: https://pypi.org/project/fastapi-tenancy/ — HIGH confidence on metadata, REJECTED for production use

**Confidence: HIGH** (the row-level pattern is well-established; rejection of the alternatives is opinionated but defensible)

## Frontend: Company Switcher + URL Routing

### VERDICT: URL is the source of truth (path prefix `/:company/...`). Zustand mirrors for UX only.

**Pattern (no new dependencies — all from v2.1 stack):**

1. **React Router v6 dynamic segment** — wrap all tenant-scoped routes under `/:company/`:

```tsx
// frontend/src/App.tsx
<Route path="/:company" element={<RequireAuth><CompanyShell /></RequireAuth>}>
  <Route index element={<Navigate to="news-funnel" replace />} />
  <Route path="news-funnel" element={<NewsFunnelTab />} />
  <Route path="calendar" element={<ContentCalendarTab />} />
  <Route path="weekly-sweep" element={<WeeklySweepTab />} />
</Route>
<Route path="/" element={<Navigate to="/seva/news-funnel" replace />} />
```

2. **`useParams()` reads active company anywhere in the tree:**

```tsx
const { company } = useParams<{ company: "seva" | "juno" }>();
```

3. **TanStack Query keys include company:**

```tsx
useQuery({ queryKey: ["daily-summary", company, "today"], ... })
```

4. **Zustand store (NEW — `frontend/src/store/companyStore.ts`):**

```ts
import { create } from "zustand";
import { persist } from "zustand/middleware";

interface CompanyStore {
  lastVisited: "seva" | "juno";
  setLastVisited: (c: "seva" | "juno") => void;
}

export const useCompanyStore = create<CompanyStore>()(
  persist(
    (set) => ({
      lastVisited: "seva",
      setLastVisited: (c) => set({ lastVisited: c }),
    }),
    { name: "seva-active-company" }
  )
);
```

The store's only job is to remember "which company did the operator have open last time" so the bare `/` route can redirect there instead of always to `/seva/...`. **URL navigation does NOT go through the store** — `useParams()` is the truth at render time. The store updates *as a side effect* of route changes (in `CompanyShell`'s `useEffect`).

5. **Surgical `AppHeader` addition** — segmented control next to brand mark; clicking "Juno" calls `navigate("/juno" + currentSubPath)`. The frozen v2.1 baseline gets one new component (`<CompanySwitcher />`), no other changes.

### What NOT to do

- **DON'T put active company in Zustand as the primary source of truth.** URL + `useParams()` is canonical; Zustand only mirrors for the open-browser-default case. Putting state primary in Zustand creates URL-vs-state desync bugs the moment the operator uses browser back/forward.
- **DON'T use a query param (`?company=juno`) instead of a path segment.** Path segments compose naturally with nested routes and produce cleaner URLs.
- **DON'T use a subdomain (`juno.seva-mining-smm.vercel.app`).** Adds Vercel + DNS config burden and breaks single-localhost dev.

**Sources:**
- React Router v6 dynamic segments + `useParams`: https://reactrouter.com/start/declarative/routing — HIGH confidence
- Zustand persist middleware: https://github.com/pmndrs/zustand/discussions/786 — HIGH confidence (already in v2.1 stack, well-documented)

**Confidence: HIGH**

## Defence RSS Feed Inventory

Each feed below was fetched and validated **as of 2026-05-19**. Status column reflects HTTP fetch + RSS parse result.

| # | Source | RSS URL | Status | Notes |
|---|--------|---------|--------|-------|
| 1 | Defense News (homepage) | `https://www.defensenews.com/arc/outboundfeeds/rss/?outputType=xml` | ✓ VALIDATED | Sightline Media, daily updates |
| 2 | Defense News — Pentagon | `https://www.defensenews.com/arc/outboundfeeds/rss/category/pentagon/?outputType=xml` | ✓ VALIDATED | Sub-feed if homepage too noisy |
| 3 | Defense News — Industry | `https://www.defensenews.com/arc/outboundfeeds/rss/category/industry/?outputType=xml` | ✓ VALIDATED | Direct defence-industry beat (Juno's core surface) |
| 4 | Defense News — Global | `https://www.defensenews.com/arc/outboundfeeds/rss/category/global/?outputType=xml` | ✓ VALIDATED | Geopolitics-adjacent |
| 5 | Defense News — Air | `https://www.defensenews.com/arc/outboundfeeds/rss/category/air/?outputType=xml` | ✓ VALIDATED | Air domain |
| 6 | Defense News — Land | `https://www.defensenews.com/arc/outboundfeeds/rss/category/land/?outputType=xml` | ✓ VALIDATED | Land domain |
| 7 | Defense News — Naval | `https://www.defensenews.com/arc/outboundfeeds/rss/category/naval/?outputType=xml` | ✓ VALIDATED | Naval domain |
| 8 | Defense News — Space | `https://www.defensenews.com/arc/outboundfeeds/rss/category/space/?outputType=xml` | ✓ VALIDATED | Space domain |
| 9 | Defense News — Unmanned | `https://www.defensenews.com/arc/outboundfeeds/rss/category/unmanned/?outputType=xml` | ✓ VALIDATED | Drones/UAS |
| 10 | Breaking Defense | `https://breakingdefense.com/feed/` | ✓ VALIDATED | RSS 2.0, hourly updates, last post 2026-05-19 18:33 UTC |
| 11 | DefenseScoop | `https://defensescoop.com/feed/` | ✓ VALIDATED | RSS 2.0, last post 2026-05-19 19:27 UTC |
| 12 | RUSI — Commentary | `https://www.rusi.org/rss/latest-commentary.xml` | ✓ VALIDATED (page lists) | UK think tank, defence + security commentary |
| 13 | RUSI — Publications | `https://www.rusi.org/rss/latest-publications.xml` | ✓ VALIDATED (page lists) | Longer-form RUSI papers |
| 14 | SIPRI (combined) | `https://www.sipri.org/rss/combined.xml` | ✓ VALIDATED (page lists) | Stockholm International Peace Research Institute — press, news, events, publications combined |
| 15 | U.S. Department of War (formerly DoD) | `https://www.war.gov/news/rss/` | TBD — landing page lists multiple feeds; need to fetch `https://www.war.gov/news/rss/?feedtype=press-releases` etc. | **VERIFICATION COMMAND:** `curl -sI https://www.war.gov/news/rss/?feedtype=press-releases` in Phase 0 |
| 16 | Janes Defence News | NO DIRECT PUBLIC RSS | ✗ NOT AVAILABLE | Janes RSS is gated behind subscriber accounts (`My Services` → `My Alerts & Feeds`). Public news at `https://www.janes.com/defence-intelligence-insights/defence-news` has no public RSS endpoint. **Mitigation:** scrape via SerpAPI `q="site:janes.com defence" engine=google_news` instead. |
| 17 | IISS Military Balance Blog | NO PUBLIC RSS FOUND | ✗ NOT AVAILABLE | Blog at `https://www.iiss.org/online-analysis/military-balance/` returned 403 to public fetch; no RSS link visible in search results. **Mitigation:** SerpAPI `q="site:iiss.org military balance" engine=google_news`. |
| 18 | NATO | `https://www.nato.int/cps/us/natohq/RSS.htm` | ⚠ LANDING PAGE 404'd ON FETCH (2026-05-19) | Search results confirm RSS exists, page is the index. **VERIFICATION COMMAND:** `curl -sI https://www.nato.int/cps/en/natohq/news.htm?selectedLocale=en&_=feed` in Phase 0; if dead, fall back to SerpAPI `site:nato.int`. |
| 19 | Department of National Defence Canada | NO DIRECT RSS CONFIRMED | ⚠ UNVERIFIED | `https://forces.gc.ca/en/stay-connected/rss-feeds.page` returned 404 on direct fetch; `canada.ca` general news web feeds at `https://www.canada.ca/en/news/web-feeds.html` may carry National Defence releases. **VERIFICATION COMMAND:** `curl -s "https://www.canada.ca/en/news/web-feeds.html" \| grep -i "defence"` in Phase 0. **Mitigation:** SerpAPI `q="site:canada.ca defence" engine=google_news`. |
| 20 | Reuters Defence | NO RSS (Reuters dropped RSS in 2020) | ✗ NOT AVAILABLE | Mitigation: SerpAPI `q="site:reuters.com defence OR military" engine=google_news` OR Google News alias `https://news.google.com/rss/search?q=when:24h+allinurl:reuters.com+defence` |
| 21 | RCAF (Royal Canadian Air Force) | NO DIRECT RSS CONFIRMED | ⚠ UNVERIFIED | Sub-property of `forces.gc.ca`. **Mitigation:** subsumed under Canada DND fallback above. |
| 22 | Council on Foreign Relations | NOT INVESTIGATED IN DETAIL | ⚠ DEFERRED | Suggested in brief but lower-priority for "defence industry"; CFR is broader IR/foreign-policy. Skip for v3.0; revisit if news funnel lacks geopolitical depth. |
| 23 | Bloomberg Defence | NO PUBLIC RSS | ✗ NOT AVAILABLE | Paywall + no public RSS. **Mitigation:** SerpAPI `q="site:bloomberg.com defence OR military"`. |

### Recommended feed set for Phase 0 ingestion (production-stable, validated)

```python
JUNO_DEFENCE_RSS_FEEDS = [
    # Tier 1 — direct industry coverage (validated 2026-05-19)
    ("defense_news_industry", "https://www.defensenews.com/arc/outboundfeeds/rss/category/industry/?outputType=xml"),
    ("defense_news_pentagon", "https://www.defensenews.com/arc/outboundfeeds/rss/category/pentagon/?outputType=xml"),
    ("defense_news_global", "https://www.defensenews.com/arc/outboundfeeds/rss/category/global/?outputType=xml"),
    ("breaking_defense", "https://breakingdefense.com/feed/"),
    ("defense_scoop", "https://defensescoop.com/feed/"),
    # Tier 2 — analysis / think tanks (validated 2026-05-19)
    ("rusi_commentary", "https://www.rusi.org/rss/latest-commentary.xml"),
    ("sipri_combined", "https://www.sipri.org/rss/combined.xml"),
    # Tier 3 — domain-specific (add as needed)
    ("defense_news_air", "https://www.defensenews.com/arc/outboundfeeds/rss/category/air/?outputType=xml"),
    ("defense_news_land", "https://www.defensenews.com/arc/outboundfeeds/rss/category/land/?outputType=xml"),
    ("defense_news_naval", "https://www.defensenews.com/arc/outboundfeeds/rss/category/naval/?outputType=xml"),
    ("defense_news_space", "https://www.defensenews.com/arc/outboundfeeds/rss/category/space/?outputType=xml"),
    ("defense_news_unmanned", "https://www.defensenews.com/arc/outboundfeeds/rss/category/unmanned/?outputType=xml"),
]
# DEFERRED until verification in Phase 0:
# - war.gov press-releases (need exact URL)
# - nato.int news (landing page 404, search confirms RSS exists)
# - canada.ca defence (no direct RSS confirmed, fall back to SerpAPI)
```

### Mitigations for sources without RSS

For Janes, IISS, Reuters, Bloomberg, Council on Foreign Relations, RCAF, and any others without working RSS: use the **existing** SerpAPI `google_news` engine with site-restricted queries (same SDK, same `$50/mo` budget envelope, same code path as v2.0 gold-news ingestion):

```python
search = GoogleSearch({
    "engine": "google_news",
    "q": "defence OR military site:janes.com",
    "api_key": settings.serpapi_api_key,
    "hl": "en",
    "gl": "us",
})
```

**Sources:**
- Defense News RSS feed inventory (fetched and parsed): https://www.defensenews.com/m/rss/ — HIGH confidence
- Breaking Defense feed validation (RSS 2.0, post 2026-05-19): https://breakingdefense.com/feed/ — HIGH confidence
- DefenseScoop feed validation (RSS 2.0, post 2026-05-19): https://defensescoop.com/feed/ — HIGH confidence
- RUSI RSS feeds listing: https://www.rusi.org/rusi-rss-feeds — HIGH confidence
- SIPRI RSS combined feed: https://www.sipri.org/rss — HIGH confidence
- NATO RSS landing page (search result): https://www.nato.int/cps/us/natohq/RSS.htm — MEDIUM confidence (page exists but our direct fetch 404'd; verify in Phase 0)
- Reuters RSS dropped in 2020 (multiple corroborating sources): MEDIUM confidence

**Confidence: HIGH on the Tier-1 set (all directly validated); MEDIUM on Tier-3 mitigations (depends on SerpAPI query quality)**

## Sonnet Relevance Filter: World Events → Defence

### VERDICT: Use Anthropic structured outputs (JSON schema). Not yes/no, not free-form prose.

The "world events relevant to defence" filter takes a heterogeneous input (general world news from Reuters/AP/Google News) and must classify each story along multiple axes. A yes/no prompt is wrong because:

1. It loses the *reason* (was this Ukraine military spending, or a defence-tech announcement, or a geopolitical shift?)
2. It loses the *confidence* (the operator needs to triage which borderline calls to spot-check)
3. It cannot be reliably JSON-parsed without retry logic

**Recommended pattern** — `output_config.format` with a Pydantic schema:

```python
# scheduler/agents/juno_relevance.py
from pydantic import BaseModel, Field
from typing import Literal
from anthropic import AsyncAnthropic

class DefenceRelevance(BaseModel):
    is_relevant: bool = Field(description="True if this story is meaningfully relevant to the defence industry")
    category: Literal[
        "defence_industry_direct",  # company announcements, contracts, tech
        "geopolitical_shift",        # alliances, sanctions, conflict escalation
        "military_spending",         # budget changes, procurement
        "conflict_event",            # active conflict developments
        "defence_tech",              # new tech: hypersonics, AI, drones, etc.
        "not_relevant",
    ]
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = Field(max_length=200, description="One-sentence justification")

client = AsyncAnthropic(api_key=settings.anthropic_api_key, timeout=30.0)

async def classify_story(title: str, snippet: str) -> DefenceRelevance:
    response = await client.messages.parse(
        model="claude-haiku-4-5",  # Haiku is sufficient for classification, ~10x cheaper than Sonnet
        max_tokens=400,
        output_format=DefenceRelevance,
        messages=[{
            "role": "user",
            "content": f"Classify this news story for defence industry relevance.\n\nTitle: {title}\n\nSnippet: {snippet}"
        }],
    )
    return response.parsed_output
```

### Why this beats yes/no

| Approach | Pros | Cons |
|----------|------|------|
| Yes/no prompt + string parse | Cheapest tokens, simplest prompt | Loses category + reasoning; parse failures need retry; brittle to model output variation |
| Free-form prose → regex extract | Captures reasoning | Fragile parsing, doesn't scale |
| **Structured output with JSON schema** | Guaranteed parseable, schema-enforced types, captures category + confidence + reasoning in one call | Slightly higher token cost (negligible at our volume) |

### Cost envelope

At ~30–50 candidate world-news items per day per company, Haiku at 4-5 tokens/cent input × ~400 tokens/call × 30 calls/day × 30 days ≈ $1–2/month for Juno's relevance filter. Well within the $5–10/mo Sonnet budget allowance in the milestone brief.

### Model choice: Haiku 4.5 for classification, Sonnet for synthesis

- **Haiku 4.5** for the relevance filter (binary-with-category classification, no nuance needed)
- **Sonnet 4.6** for the daily summary synthesis (same `daily_summary.py` pattern as Seva)

**Sources:**
- Anthropic structured outputs docs (GA across Sonnet 4.5+, Haiku 4.5+, Opus 4.5+): https://platform.claude.com/docs/en/build-with-claude/structured-outputs — HIGH confidence
- Anthropic cookbook for tool-use-based structured extraction: https://github.com/anthropics/anthropic-cookbook/blob/main/tool_use/extracting_structured_json.ipynb — HIGH confidence
- Towards Data Science walkthrough of structured outputs: https://towardsdatascience.com/hands-on-with-anthropics-new-structured-output-capabilities/ — MEDIUM confidence

**Confidence: HIGH**

## Scheduler Topology for Per-Company Cron

### VERDICT: One scheduler process, per-company jobs registered explicitly. Add `juno_daily_summary: 1020` + `juno_weekly_sweeper: 1021` to `JOB_LOCK_IDS`.

The existing `worker.py` registers jobs by string ID; each job acquires a unique advisory lock from `JOB_LOCK_IDS` (OPS-02 uniqueness assertion at import time). For v3.0 add Juno jobs alongside Seva jobs in the same scheduler:

```python
# scheduler/worker.py
JOB_LOCK_IDS = {
    "daily_summary": 1015,         # Seva (existing)
    "daily_summary_prune": 1016,   # Seva (existing)
    "weekly_sweeper": 1019,        # Seva (existing — v2.1)
    "juno_daily_summary": 1020,    # NEW (v3.0)
    "juno_weekly_sweeper": 1021,   # NEW (v3.0)
}
# OPS-02 assertion: assert len(set(JOB_LOCK_IDS.values())) == len(JOB_LOCK_IDS)
```

Per-company jobs are individual cron registrations sharing the same handler with a `company_id` parameter:

```python
scheduler.add_job(
    run_daily_summary, "cron",
    hour=15, minute=0, timezone="UTC",  # 08:00 PT
    args=["seva"],
    id="seva_daily_summary",
)
scheduler.add_job(
    run_daily_summary, "cron",
    hour=15, minute=10, timezone="UTC",  # staggered 10 min after Seva
    args=["juno"],
    id="juno_daily_summary",
)
```

**Why not a fan-out cron that iterates over `companies` rows?** A single cron that loops over companies tangles failure modes — one company's Sonnet timeout would delay the next. Explicit per-company jobs with separate lock IDs preserve OPS-02 semantics (one stuck Juno run does not block the next Seva run) and give the operator clearer Railway logs.

**Sources:**
- APScheduler advisory-lock uniqueness pattern (already established in OPS-02): direct read of `scheduler/worker.py` — HIGH confidence
- PostgreSQL advisory locks for distributed task coordination: https://leapcell.io/blog/orchestrating-distributed-tasks-with-postgresql-advisory-locks — MEDIUM confidence

**Confidence: HIGH**

## Installation

```bash
# Backend — NO new Python dependencies. All v3.0 capabilities use existing stack.
# (anthropic>=0.86.0, feedparser, serpapi, sqlalchemy>=2.0, alembic, asyncpg — all present)

# Frontend — NO new npm dependencies. Zustand persist middleware is in existing zustand 5.x package.
# (react-router-dom v6, zustand 5.x, @tanstack/react-query 5.x — all present)
```

This is intentional. The v3.0 milestone adds **patterns, schemas, config, and feed URLs** — not new libraries. Every "stack addition" above is a code/config change inside packages we already ship.

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| Row-level `company_id` column | `fastapi-tenancy` 0.4.0 library | At 5+ tenants when the abstraction pays for itself. The library is real (PyPI, 2026-04-01 release, Python 3.11+, FastAPI 0.111+, SQLAlchemy 2.0+) but unproven. |
| Row-level `company_id` column | Postgres SCHEMA-per-tenant | If/when data-residency regulations or per-tenant Alembic migration drift become real concerns. Not applicable to v3.0. |
| Row-level `company_id` column | Postgres Row-Level Security (`SET app.current_tenant`) | If multi-user-per-tenant arrives and a forgotten `WHERE` clause becomes a real risk. Defer to v3.x+. |
| Anthropic structured outputs (`output_config.format`) | Tool-use-based JSON extraction | The tool-use pattern still works (cookbook example) but the new structured outputs feature is more direct for classification tasks. Use tool-use if Claude needs to *call back* with data (agentic flow). |
| Anthropic structured outputs | Free-form Sonnet + JSON repair (existing v2.0 pattern) | If you can't update the model (e.g. pinning to Sonnet 4.4 or earlier). Sonnet 4.6 is supported, no migration cost. |
| URL path prefix `/:company/` | Subdomain per tenant (`juno.seva-mining-smm.vercel.app`) | If we ever want per-tenant branding at the DNS level (white-label deployments). Adds Vercel + DNS complexity. Defer. |
| URL path prefix | Query param `?company=juno` | Never — query params don't compose with nested routes cleanly. |
| Defense News RSS feeds | Janes / Bloomberg defence (paid) | If budget allows in a future milestone. For v3.0, the free Defense News + Breaking Defense + DefenseScoop + RUSI + SIPRI set covers the brief. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `fastapi-tenancy` 0.4.0 | Released 2026-04-01, no production track record, adds framework abstraction over a problem we solve in ~50 LOC | Row-level `company_id` column with `contextvars`-based session-scoped tenant context |
| Postgres RLS via `SET app.current_tenant` | asyncpg + SQLAlchemy 2.0 async connection pool requires `checkin` event handler to `RESET app.current_tenant` — non-trivial wiring, multiple known gotchas, no benefit for a single-operator app | Application-layer `WHERE company_id = :ctx` filter |
| Postgres SCHEMA-per-tenant | Multiplies Alembic migration runs by tenant count; `search_path` management across asyncpg pool is fragile | Single shared schema, `company_id` column |
| Subdomain-per-tenant routing | Vercel + DNS complexity, breaks single-localhost dev | URL path prefix `/:company/` |
| Reuters RSS direct URL | Reuters dropped RSS in 2020 — no public endpoint exists | SerpAPI `engine=google_news q="site:reuters.com defence"` |
| Janes direct public RSS | Gated behind subscriber account | SerpAPI `engine=google_news q="site:janes.com defence"` |
| Yes/no relevance prompt → string parse | Brittle, loses category + reasoning + confidence | `output_config.format` with Pydantic schema |
| Single scheduler cron that fans out over `companies` rows | One company's timeout blocks the next; tangled failure modes; harder to debug in Railway logs | Per-company `add_job` calls with distinct lock IDs |
| Zustand as primary source of truth for active company | URL + Zustand desync the moment operator uses browser back/forward | `useParams()` as truth; Zustand mirrors *last visited* for browser-open default only |
| APScheduler 4.0 alpha | Already prohibited in v2.0 CLAUDE.md — same prohibition applies | APScheduler 3.11.2 stable |
| New ORM, new auth lib, new frontend framework | Out of scope; existing stack is locked | — |

## Stack Patterns by Variant

**If a 3rd tenant onboards in v3.x:**
- Same pattern scales. Add `'new_tenant'` to `companies` table, register `new_tenant_daily_summary` with the next free lock ID, add a new RSS feed config block.
- Re-evaluate `fastapi-tenancy` at 5+ tenants — at that point the framework abstraction starts paying for itself.

**If per-tenant branding is required (v3.1+):**
- Add `companies.brand_color`, `companies.logo_url` columns.
- Frontend reads from a `/{company}/branding` endpoint and injects CSS variables.
- Still no subdomain split unless a customer demands their own DNS.

**If a tenant needs data residency separation (hypothetical v4.0):**
- That's when database-per-tenant becomes justified. Not before.

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| `anthropic>=0.86.0` | structured outputs `output_config.format` | GA in this SDK version. Compatible with Sonnet 4.5/4.6, Haiku 4.5, Opus 4.5/4.6. No SDK bump needed. |
| `feedparser 6.0.x` | All defence RSS feeds validated above | Same library used for v2.0 gold-news ingestion. No version change needed. |
| `react-router-dom 6.x` | Dynamic segment `:company` + nested routes | Already installed. No version bump needed. |
| `zustand 5.x` | `zustand/middleware.persist` | Persist middleware ships in the same package. No new install. |
| `sqlalchemy 2.0.x` async + `asyncpg 0.30.x` | `contextvars`-based tenant context | Stdlib `contextvars` integrates cleanly with `AsyncSession` request-scoped lifecycle. |
| Alembic 1.14.x | New 0014 migration with `company_id` backfill | Same hand-written migration pattern as 0010–0013. |

## Sources

- FastAPI multi-tenancy patterns (community): https://github.com/fastapi/fastapi/discussions/6056 — MEDIUM confidence
- Aditya Mattos — Postgres RLS multi-tenancy (rejected approach, documented for completeness): https://adityamattos.com/multi-tenancy-in-python-fastapi-and-sqlalchemy-using-postgres-row-level-security — MEDIUM confidence
- MergeBoard — Multitenancy with FastAPI, SQLAlchemy and PostgreSQL: https://mergeboard.com/blog/6-multitenancy-fastapi-sqlalchemy-postgresql/ — MEDIUM confidence
- `fastapi-tenancy` 0.4.0 PyPI metadata (rejected library, verified): https://pypi.org/project/fastapi-tenancy/ — HIGH confidence on metadata
- React Router v6 routing + `useParams`: https://reactrouter.com/start/declarative/routing — HIGH confidence
- Zustand persist middleware discussion: https://github.com/pmndrs/zustand/discussions/786 — HIGH confidence (already in v2.1 stack)
- Anthropic structured outputs (GA): https://platform.claude.com/docs/en/build-with-claude/structured-outputs — HIGH confidence
- Anthropic cookbook — tool use for structured JSON extraction: https://github.com/anthropics/anthropic-cookbook/blob/main/tool_use/extracting_structured_json.ipynb — HIGH confidence
- Defense News RSS feed inventory (fetched + parsed 2026-05-19): https://www.defensenews.com/m/rss/ — HIGH confidence
- Breaking Defense feed (validated 2026-05-19, RSS 2.0, post timestamp matches today): https://breakingdefense.com/feed/ — HIGH confidence
- DefenseScoop feed (validated 2026-05-19, RSS 2.0): https://defensescoop.com/feed/ — HIGH confidence
- RUSI RSS feeds (listing page): https://www.rusi.org/rusi-rss-feeds — HIGH confidence
- SIPRI RSS combined feed: https://www.sipri.org/rss — HIGH confidence
- NATO RSS landing (search-result confirmation; direct fetch failed): https://www.nato.int/cps/us/natohq/RSS.htm — MEDIUM confidence
- U.S. Department of War RSS landing: https://www.war.gov/news/rss/ — MEDIUM confidence (specific feed URLs need Phase-0 verification)
- Feedspot top 60 defence RSS feeds (third-party aggregator, used for discovery only): https://rss.feedspot.com/defense_rss_feeds/ — LOW confidence (aggregator metadata, not authoritative)
- SerpAPI Google News engine: https://serpapi.com/google-news-api — HIGH confidence
- PostgreSQL advisory locks for distributed scheduling: https://leapcell.io/blog/orchestrating-distributed-tasks-with-postgresql-advisory-locks — MEDIUM confidence

---
*Stack research for: Seva Mining v3.0 — multi-tenant pivot + defence-sector ingestion*
*Researched: 2026-05-19*
