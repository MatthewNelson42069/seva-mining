# Quick Task 260421-eoe: Split Content Agent into 7 sub-agents — Research

**Researched:** 2026-04-21
**Domain:** APScheduler concurrency, PostgreSQL async worker queues, React Router v6 + TanStack Query v5
**Confidence:** HIGH on APScheduler + SQLAlchemy patterns; MEDIUM on concurrency specifics (claims verified against CONTEXT volume assumptions, not benchmarked)

---

## ⚠️ Post-Research Architecture Pivot (2026-04-21)

**After this research was written, the operator pivoted the architecture:**
Content Agent no longer runs a cron. It is now a review-service-only module exposing `fetch_stories()` (shared SerpAPI/RSS ingestion with 30-min in-memory cache) and `review(draft)` (Haiku compliance gate called inline by sub-agents). Each sub-agent is self-contained within a single tick: fetch → type-filter → draft → review → write.

**What this changes in the findings below:**

| Research finding | Status after Phase C pivot |
|---|---|
| Stagger strategy (`start_date` offsets `+0/+17/+34/+51/+68/+85/+102` min) | ✅ STILL VALID |
| Per-sub-agent advisory lock IDs 1010–1016 | ✅ STILL VALID (retire content_agent=1003 and gold_history_agent=1005 since those crons are removed) |
| `job_defaults={'max_instances': 1, 'misfire_grace_time': 300, 'coalesce': True}` | ✅ STILL VALID |
| Neon pool bump to `pool_size=15` | ✅ STILL VALID |
| React Router data-driven `/agents/:slug` | ✅ STILL VALID |
| TanStack Query hierarchical queryKey | ✅ STILL VALID |
| Polling handoff `WHERE draft_content IS NULL` | ❌ MOOT — sub-agents now self-contained, no cross-tick handoff |
| `_gate_draft()` private method on ContentAgent | ❌ REPLACED — `review()` is now a public method called by sub-agents |
| 30-min deferred-gate latency | ❌ MOOT — gate is inline, zero latency |
| `research_context` JSONB migration | ❌ MOOT — no cross-tick state to persist |
| Scheduler job count: 9 (content_agent + morning_digest + 7 sub-agents) | ❌ CHANGED → 8 (morning_digest + 7 sub-agents). No content_agent cron. |
| `content_agent_interval_hours=3` in worker.py:188 | ❌ DELETE this setting — cron removed |

**Staggering, lock IDs, APScheduler config, and frontend routing carry over unchanged. Polling handoff + deferred-gate latency sections are superseded by the inline `review()` call.**

---

## User Constraints (from CONTEXT.md)

### Locked Decisions

- **Orchestrator split:** Content Agent = INGEST → CLASSIFY → GATE (no drafting). 7 sub-agents = pure drafters.
- **Cadence:** 7 × APScheduler cron jobs, every 2 hours each, staggered.
- **Compliance gate:** Deferred — Content Agent's own next tick picks up ungated drafts (worst-case ~30min latency).
- **Gold History fold-in:** Existing `scheduler/agents/gold_history_agent.py` moves to `scheduler/agents/content/gold_history.py`, adopts same `run_draft_cycle()` signature.
- **Directory:** `scheduler/agents/content/` namespace; orchestrator stays at `scheduler/agents/content_agent.py`.
- **Frontend routes:** `/agents/<slug>` (7 tabs, sidebar priority order: breaking-news, threads, long-form, quotes, infographics, gold-media, gold-history).
- **Combined queue removed entirely.** Root redirect → `/agents/breaking-news`.
- **Video clip:** DB value stays `video_clip`; module `video_clip.py`; UI tab labeled "Gold Media".

### Claude's Discretion

- Gate module extraction as `_gate_draft()` private method on ContentAgent.
- Data-driven `CONTENT_SUB_AGENTS` registration list in `worker.py`.
- Test file split 1:1 with new modules.
- Worker concurrency / `max_instances` settings — researcher to confirm.

### Deferred Ideas (OUT OF SCOPE)

- Breaking-news event-mode (faster cadence trigger).
- Operator will revisit cadence later.
- Any schema changes or new content_type values.

---

## Summary

- **Stagger with explicit `start_date` offsets** (not `jitter`). Allocate 7 slots across the 2h window at ~17-minute intervals so no two sub-agents fire within the same minute. One lock_id per sub-agent (1004–1010) — advisory locks are defense-in-depth against deploy overlap, not for intra-scheduler serialization (single-process single-scheduler never double-fires a job).
- **Polling handoff is correct at this scale.** `WHERE content_type = X AND draft_content IS NULL` is the right query. **Do NOT add `FOR UPDATE SKIP LOCKED`** — the per-sub-agent advisory lock already guarantees no two ticks of the same sub-agent run concurrently. Failed draft → bundle stays `draft_content=NULL` → retries next cycle. That is the desired semantic; no retry counter needed.
- **30-min deferred-gate latency is fine.** No operator-facing UX impact (human reviewer isn't staring at the queue real-time). A separate "gate-only" cron adds moving parts without material improvement. Do not add.
- **APScheduler config:** `job_defaults={'max_instances': 1, 'misfire_grace_time': 300, 'coalesce': True}`. 1 event loop / 1 Railway container handles 9 async jobs comfortably — each job's wall time is 10–60s of mostly-awaiting-IO (Anthropic + DB). No event-loop starvation risk at this scale.
- **Frontend: data-driven route array.** Define `CONTENT_AGENT_TABS` once, render via `.map()` over a single `<Route path="/agents/:slug" element={<PerAgentQueuePage />} />`, read `useParams().slug` to pick the TanStack Query key. No 7 duplicated route elements.

**Primary recommendation:** Ship deferred-gate + polling + per-sub-agent advisory locks + explicit `start_date` staggering. Don't over-engineer — this workload is tiny (≤10 bundles/day/type), and every "just in case" mechanism here is complexity looking for a problem.

---

## 1. Staggering strategy

### The mechanics

APScheduler's `IntervalTrigger(hours=2)` fires at `start_date + n * interval`. To stagger 7 jobs with the same 2h cadence, **set a different `start_date` per job**. This is the documented, idiomatic approach. Source: [APScheduler 3.11.2 interval trigger docs](https://apscheduler.readthedocs.io/en/3.x/modules/triggers/interval.html).

**Do not use `jitter`** for this purpose. `jitter` adds *random* offset per-firing (intended for scattering N workers across a fleet). You want *deterministic* staggering so two sub-agents never collide, and so logs are predictable.

### Recommended slot allocation

7 sub-agents × 2h window = one slot every ~17 minutes. Aligned to clean boundaries where practical:

| Sub-agent | `start_date` offset from scheduler start | Human-readable fire times (example: scheduler starts 00:00) |
|-----------|------------------------------------------|-------------------------------------------------------------|
| breaking_news | +0 min | 00:00, 02:00, 04:00, … |
| threads | +17 min | 00:17, 02:17, 04:17, … |
| long_form | +34 min | 00:34, 02:34, 04:34, … |
| quotes | +51 min | 00:51, 02:51, 04:51, … |
| infographics | +68 min (1h08) | 01:08, 03:08, 05:08, … |
| gold_media (video_clip) | +85 min (1h25) | 01:25, 03:25, 05:25, … |
| gold_history | +102 min (1h42) | 01:42, 03:42, 05:42, … |

**Priority ordering matches CONTEXT.md sidebar order** — most important drafter fires first after a restart, ensuring fastest "time to first breaking-news draft" on deploys.

**Note on gold_history:** CONTEXT locks it into the 2h-sub-agent pattern. The current `gold_history_agent` runs bi-weekly Sunday 09:00 UTC (cron, not interval). Since the new sub-agent drafts on-demand from `content_bundles WHERE content_type='gold_history' AND draft_content IS NULL`, the **content_type must first be written by an upstream producer**. Today that's `GoldHistoryAgent.run()` itself. The split makes this subtle — see **Pitfalls** below.

### Implementation sketch

```python
from datetime import datetime, timedelta, timezone
from apscheduler.triggers.interval import IntervalTrigger

CONTENT_SUB_AGENTS: list[tuple[str, str, str, int, int]] = [
    # (module_path, class_name, job_id, lock_id, offset_minutes)
    ("agents.content.breaking_news", "BreakingNewsAgent", "sub_breaking_news", 1004, 0),
    ("agents.content.threads",       "ThreadsAgent",       "sub_threads",       1005, 17),
    ("agents.content.long_form",     "LongFormAgent",      "sub_long_form",     1006, 34),
    ("agents.content.quotes",        "QuotesAgent",        "sub_quotes",        1007, 51),
    ("agents.content.infographics",  "InfographicsAgent",  "sub_infographics",  1008, 68),
    ("agents.content.video_clip",    "VideoClipAgent",     "sub_video_clip",    1009, 85),
    ("agents.content.gold_history",  "GoldHistoryAgent",   "sub_gold_history",  1010, 102),
]

now = datetime.now(timezone.utc)
for module_path, class_name, job_id, lock_id, offset in CONTENT_SUB_AGENTS:
    start_date = now + timedelta(minutes=offset)
    scheduler.add_job(
        _make_sub_agent_job(module_path, class_name, job_id, lock_id, engine),
        trigger=IntervalTrigger(hours=2, start_date=start_date),
        id=job_id,
        name=f"{class_name} — every 2h (offset +{offset}m)",
        coalesce=True,
        max_instances=1,
        misfire_grace_time=300,
    )
```

### Lock ID allocation

**Current `JOB_LOCK_IDS`** (from `scheduler/worker.py:51-55`):

```python
"content_agent": 1003,
"morning_digest": 1005,          # ⚠ collision risk below
"gold_history_agent": 1009,      # ⚠ will be removed when gold_history folds into sub-agents
```

**Proposal — no collisions:**

```python
JOB_LOCK_IDS = {
    # Orchestrator + standalone jobs
    "content_agent": 1003,
    "morning_digest": 1001,      # MOVE — 1005 is now a sub-agent slot
    # Sub-agents (NEW — 1004–1010 block)
    "sub_breaking_news": 1004,
    "sub_threads":       1005,
    "sub_long_form":     1006,
    "sub_quotes":        1007,
    "sub_infographics":  1008,
    "sub_video_clip":    1009,
    "sub_gold_history":  1010,
}
```

⚠ **`morning_digest` is currently 1005.** Moving it to 1001 (unused) is required to free 1005 for `sub_threads`. Alternatively, shift all sub-agent IDs to `1010–1016` and leave `morning_digest=1005` alone — cleaner but less tidy numerically. **Recommendation: shift sub-agents to `1010–1016`** — easier, no risk of Railway scheduler-restart-mid-deploy holding a stale 1005 from the old `morning_digest` binding. See **Pitfalls**.

**Final recommended allocation:**

```python
JOB_LOCK_IDS = {
    "content_agent": 1003,
    "morning_digest": 1005,       # unchanged
    # Sub-agents
    "sub_breaking_news": 1010,
    "sub_threads":       1011,
    "sub_long_form":     1012,
    "sub_quotes":        1013,
    "sub_infographics":  1014,
    "sub_video_clip":    1015,
    "sub_gold_history":  1016,
}
```

**Key property:** each sub-agent has its OWN lock ID — they run **concurrently**, not serialized. The only thing the lock prevents is *the same sub-agent firing twice* (deploy overlap). Concurrency at this scale (max 9 async jobs on 1 event loop, each ~10–60s of awaited IO) is safe on Railway single-worker.

### Why not "serialize everything on one lock"?

Tempting for simplicity, but bad: one slow sub-agent (e.g., `video_clip` hitting X API quota wait) would block all 6 others. Per-job locks + async concurrency costs nothing and preserves isolation. Sub-agents already don't share state — each reads/writes different `content_type` rows.

**Confidence:** HIGH. Source: [APScheduler IntervalTrigger docs](https://apscheduler.readthedocs.io/en/3.x/modules/triggers/interval.html), existing `scheduler/worker.py` advisory-lock pattern (battle-tested since Phase 1).

---

## 2. Handoff pattern

### Polling query (standard)

Each sub-agent on every tick:

```python
async def run_draft_cycle(self) -> None:
    async with AsyncSessionLocal() as session:
        # 1. Pick up ungated drafts of my type
        result = await session.execute(
            select(ContentBundle)
            .where(ContentBundle.content_type == self.CONTENT_TYPE)
            .where(ContentBundle.draft_content.is_(None))
            .order_by(ContentBundle.created_at.asc())
            .limit(self.BATCH_LIMIT)  # e.g. 5
        )
        bundles = result.scalars().all()

        for bundle in bundles:
            try:
                draft = await self._draft(bundle)
                bundle.draft_content = draft
                # NOTE: do NOT set compliance_passed here — Content Agent's GATE step owns that.
            except Exception as exc:
                logger.error("Sub-agent %s failed on bundle %s: %s",
                             self.__class__.__name__, bundle.id, exc)
                # Leave draft_content=NULL → retries next cycle.
                continue

        await session.commit()
```

### Do I need `SELECT ... FOR UPDATE SKIP LOCKED`?

**No.** Two facts make it unnecessary:

1. **Per-sub-agent advisory lock** — `with_advisory_lock(conn, lock_id, ...)` already guarantees two instances of `sub_breaking_news` never run concurrently. A sub-agent processing a bundle is the only worker of its type for that 2h slot.
2. **Cross-sub-agent isolation** — `breaking_news` never touches `threads` bundles. The `content_type` filter enforces a hard partition; workers of different types cannot contend for the same row.

**When SKIP LOCKED would be needed (and why it's not our case):** multiple workers processing the *same* queue (e.g., N Celery workers consuming a shared FIFO). You'd use SKIP LOCKED to let worker A grab row 1 while worker B grabs row 2 without blocking. We have 1 worker per row-partition, so there's no contention to resolve.

**Source verification:** [SQLAlchemy 2.0 SKIP LOCKED discussion](https://github.com/sqlalchemy/sqlalchemy/discussions/10460), [Postgres SKIP LOCKED as a queue — Neon guide](https://neon.com/guides/queue-system). Both describe multi-worker-per-partition scenarios; neither matches our single-worker-per-type topology.

### Crash / mid-draft failure semantics

- **LLM API error during draft:** exception caught in the `for bundle in bundles:` loop, `draft_content` stays NULL, bundle retried on next tick (2h later). This is the desired semantic.
- **Full worker crash mid-transaction:** `session.commit()` hasn't fired → Postgres rolls back → `draft_content` stays NULL → retried next tick.
- **LLM succeeds but `session.commit()` fails (rare, e.g., Neon cold-start timeout mid-write):** same outcome — rollback, retry.

### Should we add a retry counter / dead-letter?

**No, not now.** The current `ContentAgent` already absorbs failures silently (logs + continues). Adding a counter ("attempts=N, if N>3 mark failed") is defensible but adds a column migration + new dashboard state + no concrete operational need. Operator can spot persistently-ungated bundles by eyeballing the queue — volume is ~10 bundles/day/type max.

**If you ever do want this:** use a simple `draft_attempts INTEGER DEFAULT 0` column — no dead-letter table. Increment in the `except` branch, skip when `draft_attempts >= 3`. Defer until operational evidence demands it.

### Claim-then-draft pattern (ruled out)

A "worker claims row with UPDATE ... SET claimed_at = now() WHERE draft_content IS NULL" pattern would be overkill:

- The advisory lock already prevents concurrent claims from the same sub-agent.
- Adding `claimed_at` means handling stale claims (what if worker crashed between claim and draft?), which demands a stale-claim-reaper — more machinery than the problem warrants.

**Confidence:** HIGH. Polling + partition-by-content_type + per-job advisory lock is the minimum-complexity correct pattern for this scale.

---

## 3. Gate placement

### The tradeoff

| Option | Latency to gate | Complexity | UX impact |
|--------|----------------|------------|-----------|
| **A. Deferred (locked)** — Content Agent's cron picks up ungated drafts | 0–30 min | Lowest — 1 cron | Human reviewer sees "awaiting compliance" state briefly |
| B. Fast gate-only cron (every 5 min) | 0–5 min | +1 cron, +1 lock ID | Marginally fresher queue; human reviewer unlikely to notice |
| C. Inline gate in each sub-agent | 0 min | 7 call sites + circular-import risk | Zero wait; tightly couples sub-agents to gate logic |

### Recommendation: ship A (deferred). Do NOT add B.

**Why 30-min latency is fine:**

1. **Human review is asynchronous.** The operator reviews the queue 1–3 times per day (per STATE.md usage patterns). They are NOT refreshing the dashboard waiting for draft N. A 30-min worst-case delay is invisible at human-review cadence.
2. **Content is already "old" relative to breaking news.** By the time a story is ingested → classified → drafted → gated → reviewed → copy-pasted to Twitter, minutes-to-hours of wall time have passed. Shaving 30 min off the gate step does nothing meaningful for the end-to-end pipeline.
3. **LLM-drafted content queues are not latency-sensitive in this product.** Unlike trading systems, every minute saved has marginal dollar value. The operator's stated constraint is *signal quality*, not latency.

**Why NOT to add a gate-only cron (option B):**

- Extra cron + extra lock ID + extra `JOB_LOCK_IDS` entry + extra APScheduler startup logs + extra moving part to debug.
- For saving max ~25 minutes of latency per draft in an already-async review flow.
- The content_agent cron already runs every 3h (currently — `content_agent_interval_hours=3` per `scheduler/worker.py:188`). CONTEXT.md describes "next tick (~30min)" but the actual current cadence is **3 hours** on prod, not 30 minutes. Worst-case gate latency is therefore ~3h, not 30min — still fine for this product, but **flag this to the planner**.

### What CONTEXT.md slightly misstates

CONTEXT.md:33-35 says "Content Agent's cron (~30min) has a GATE step" but `scheduler/worker.py:188` has `content_agent_interval_hours=3`. If you want faster gate turnaround, consider **shortening `content_agent` cadence to 1h** (touches 1 config value, no new cron). That's the minimum-change way to bound latency if the operator wants it tighter. **Ask the user** before shipping — it's a config tweak, not an architecture decision.

**Confidence:** HIGH on "deferred gate is fine for this product." MEDIUM on the specific latency number — depends on which interval (1h vs 3h) the planner picks.

---

## 4. APScheduler config

### Recommended settings

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.executors.asyncio import AsyncIOExecutor

scheduler = AsyncIOScheduler(
    executors={
        "default": AsyncIOExecutor(),
    },
    job_defaults={
        "coalesce": True,          # if 2+ firings missed during sleep/restart, run ONCE, not N times
        "max_instances": 1,         # never run same job concurrently (hard fail-safe; advisory lock is the real guard)
        "misfire_grace_time": 300,  # 5 min — Neon cold starts + deploy restarts can easily eat 60s
    },
    timezone="UTC",
)
```

### Why these values

- **`coalesce=True`:** if Railway redeploys and the scheduler is down for 5 minutes, a 2h job that "should have fired" once during that gap runs ONCE on resume — not multiple times. Critical: otherwise a long deploy could trigger a backlog burst. [APScheduler docs — coalesce](https://apscheduler.readthedocs.io/en/3.x/userguide.html).
- **`max_instances=1`:** safety belt. Advisory lock is primary. This is defense-in-depth at the APScheduler layer (prevents the scheduler itself from even submitting a second invocation while the first is running).
- **`misfire_grace_time=300`:** 5 minutes. Railway deploys + Neon serverless wake-ups can introduce 30–90s delays. Default is 1s, which is way too tight and will cause legitimate misfire warnings.
- **AsyncIOExecutor (default on AsyncIOScheduler):** correct for async jobs. No thread pool needed. **Do NOT set `pool_size`** — that's a thread/process executor concept; AsyncIOExecutor schedules coroutines on the main loop directly.

### Event-loop starvation risk (9 concurrent jobs)

**Very low at this scale.** Each job's wall time breaks down roughly:

| Phase | Wall time | CPU-bound? |
|-------|-----------|------------|
| DB SELECT ungated bundles | 50–200ms | No (await asyncpg) |
| Anthropic API call per bundle | 3–15s | No (await httpx) |
| DB UPDATE draft_content | 50–200ms | No |
| Total per sub-agent tick | 3–60s | Mostly awaiting |

**Event-loop saturation happens when CPU-bound code blocks the loop for >50ms.** Our jobs are 99% awaited IO. Even if 3 sub-agents happen to fire within the same minute (won't happen with our staggering, but hypothetically), they all interleave cleanly on the event loop.

**The real risk** is **not** the event loop. It's:

1. **Anthropic concurrent-request limits.** Anthropic's default rate limit for Claude Sonnet is ~50 RPM on pay-as-you-go tier. 9 jobs firing simultaneous Sonnet calls = 9 concurrent requests, well under any limit.
2. **Neon connection pool.** SQLAlchemy `AsyncSession` borrows a connection from the asyncpg pool. Default pool size is 5. With 9 jobs + potentially 1 user-triggered API call overlapping, you could exhaust. **Recommendation: bump `pool_size` to 15 in `database.py`** (still well under Neon free tier's 100-connection limit).

**Verify before shipping:**
```python
# scheduler/database.py — confirm/set
engine = create_async_engine(
    DATABASE_URL,
    pool_size=15,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=300,
)
```

### Memory/CPU on Railway

- `AsyncAnthropic` client: ~2MB resident + per-request httpx buffers. 9 instances = ~20MB. Trivial on Railway's 512MB worker container.
- No thread pool growth — pure asyncio.
- Railway single-worker is fine; **do not** spawn multiple workers (duplicate scheduler = duplicate job runs; advisory lock would catch it but it's wasteful).

**Confidence:** HIGH on config values (direct from APScheduler 3.x docs + `agronholm/apscheduler` issue tracker). MEDIUM on the pool_size=15 recommendation (back-of-envelope; operator should monitor Neon dashboard after deploy).

---

## 5. Frontend routing

### Pattern: one dynamic route + params-driven page

**Do NOT** write 7 `<Route>` elements. Define a single param route and let the page resolve content_type from `useParams`.

### Implementation sketch

```tsx
// frontend/src/config/agentTabs.ts
export type AgentTab = {
  slug: string;             // URL slug used in /agents/:slug
  contentType: string;       // DB content_type value
  label: string;              // sidebar label + page H1
  priority: number;           // sidebar ordering
};

export const CONTENT_AGENT_TABS: AgentTab[] = [
  { slug: "breaking-news", contentType: "breaking_news", label: "Breaking News", priority: 1 },
  { slug: "threads",       contentType: "thread",        label: "Threads",       priority: 2 },
  { slug: "long-form",     contentType: "long_form",     label: "Long-form",     priority: 3 },
  { slug: "quotes",        contentType: "quote",         label: "Quotes",        priority: 4 },
  { slug: "infographics",  contentType: "infographic",   label: "Infographics",  priority: 5 },
  { slug: "gold-media",    contentType: "video_clip",    label: "Gold Media",    priority: 6 },
  { slug: "gold-history",  contentType: "gold_history",  label: "Gold History",  priority: 7 },
];
```

```tsx
// frontend/src/App.tsx
import { CONTENT_AGENT_TABS } from "@/config/agentTabs";
import { PerAgentQueuePage } from "@/pages/PerAgentQueuePage";

<Route element={<AppShell />}>
  <Route path="/" element={<Navigate to="/agents/breaking-news" replace />} />

  {/* Single dynamic route — page reads :slug and resolves content_type */}
  <Route path="/agents/:slug" element={<PerAgentQueuePage />} />

  <Route path="/digest" element={<DigestPage />} />
  <Route path="/settings" element={<SettingsPage />} />
</Route>
```

```tsx
// frontend/src/pages/PerAgentQueuePage.tsx
import { useParams, Navigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { CONTENT_AGENT_TABS } from "@/config/agentTabs";
import { fetchQueue } from "@/api/queue";

export function PerAgentQueuePage() {
  const { slug } = useParams<{ slug: string }>();
  const tab = CONTENT_AGENT_TABS.find((t) => t.slug === slug);

  // Unknown slug → bounce to default
  if (!tab) return <Navigate to="/agents/breaking-news" replace />;

  const { data, isLoading, error } = useQuery({
    // ⚠ queryKey MUST include content_type — otherwise tab switches hit cached data for wrong type
    queryKey: ["queue", "content", tab.contentType],
    queryFn: () => fetchQueue({ platform: "content", contentType: tab.contentType }),
  });

  // ... render draft cards
}
```

```tsx
// frontend/src/components/layout/Sidebar.tsx
import { NavLink } from "react-router-dom";
import { CONTENT_AGENT_TABS } from "@/config/agentTabs";

<nav>
  <div className="sidebar-section">Agents</div>
  {CONTENT_AGENT_TABS
    .sort((a, b) => a.priority - b.priority)
    .map((tab) => (
      <NavLink
        key={tab.slug}
        to={`/agents/${tab.slug}`}
        className={({ isActive }) => (isActive ? "active" : "")}
      >
        {tab.label}
      </NavLink>
    ))}
</nav>
```

### TanStack Query v5 specifics

- **queryKey MUST include contentType** as a separate array element: `["queue", "content", tab.contentType]`. Missing this → switching tabs shows cached data from the previous tab.
- **Invalidation pattern:** to invalidate ALL agent queues at once (e.g., after approving a draft), call `queryClient.invalidateQueries({ queryKey: ["queue", "content"] })`. The hierarchical structure means v5 does partial matching — invalidating `["queue", "content"]` invalidates all `["queue", "content", *]`. Source: [TanStack Query v5 invalidation docs](https://tanstack.com/query/v5/docs/framework/react/guides/query-invalidation).
- **Per-tab invalidation** (e.g., after drafting a specific type): `queryClient.invalidateQueries({ queryKey: ["queue", "content", "breaking_news"] })`.

### Backend queue endpoint

`backend/app/routers/queue.py` needs a `content_type` query parameter:

```python
@router.get("/queue")
async def list_queue(
    platform: str,
    content_type: str | None = None,      # NEW
    session: AsyncSession = Depends(get_session),
) -> list[DraftItemResponse]:
    stmt = select(DraftItem).where(DraftItem.platform == platform)
    if content_type is not None:
        # Join to ContentBundle → filter on content_type
        stmt = stmt.join(ContentBundle, DraftItem.content_bundle_id == ContentBundle.id)
        stmt = stmt.where(ContentBundle.content_type == content_type)
    # ... existing ordering / limit
```

**Confidence:** HIGH on the routing pattern (standard React Router v6 + TanStack Query v5 idiom). MEDIUM on the exact backend join shape — planner should verify `DraftItem.content_bundle_id` relationship direction against `backend/app/models/draft_item.py`.

---

## Pitfalls / gotchas

### 1. Who produces `gold_history` bundles?

The existing `GoldHistoryAgent.run()` is **both** a producer (picks a historical story, verifies facts via SerpAPI) AND a drafter. Under the new split:

- **Producer responsibility** (picking a fresh story from `gold_history_used_topics`, verifying facts) must stay somewhere.
- **Drafter responsibility** (Claude Sonnet drama-first drafting) moves to `content/gold_history.py`.

**Resolution options:**

a) **Keep producer + drafter fused in `content/gold_history.py`** (simplest — runs every 2h but only writes a bundle if a new story is due that cycle; gated by `used_topics` dedup).

b) **Move producer into the ContentAgent classifier** (creates a `gold_history` bundle bi-weekly from the orchestrator; drafter picks it up).

**Recommendation: option (a).** `gold_history` is self-scheduling by nature (bi-weekly via `used_topics` guard). The sub-agent can run every 2h harmlessly — most cycles write nothing because no new story is due. This matches the existing `GoldHistoryAgent` behavior but fits the new sub-agent signature (`run_draft_cycle() -> None` writes bundles OR no-ops).

**Planner must decide this explicitly.** CONTEXT.md says "folds into the same pattern" but is ambiguous on producer/drafter split. Flag for user confirmation if option (a) isn't obviously right.

### 2. Which cron writes the `content_bundle` row?

The handoff contract is: **ContentAgent writes the bundle (with `content_type` + `draft_content=NULL`); the sub-agent fills `draft_content`.** This means:

- `_research_and_draft()` in `content_agent.py` — currently writes bundle WITH draft_content filled — must be split. The **research** parts (fetching article body, corroborating sources) stay in ContentAgent. The **drafting** parts move to the sub-agent.
- **The sub-agent may need access to `article_text`, `sources`, `market_snapshot`** — whatever the current drafter receives as input. Those need to be persisted on the `content_bundle` row (or rehydrated by the sub-agent from `source_url`) so the sub-agent has enough context to draft.

**Research-heavy gotcha:** `_research_and_draft()` currently does `fetch_article(story["url"])` → passes `article_text` to Sonnet. If the sub-agent runs 15+ minutes later, should it re-fetch (freshest) or rely on persisted text (cheaper, matches orchestrator's view of the story)? Persisted is safer — article URLs can 404 minutes later.

**Recommendation:** add a `research_context` JSONB column to `content_bundles` (or reuse `draft_content` with a shape like `{"stage": "research", "article_text": "...", "sources": [...]}` pre-draft, then overwrite with `{"stage": "drafted", "post": "..."}`). **Planner picks.** Option 1 (new column) is cleaner but needs a migration; option 2 (reuse field) avoids migration but makes the `draft_content IS NULL` handoff query fragile.

**⚠ Strong recommendation: add a new column.** The `draft_content IS NULL` query is the handoff contract — overloading the field with pre-draft state will cause bugs.

### 3. Market snapshot — does each sub-agent re-fetch?

Current `ContentAgent.run()` fetches market snapshot ONCE per run (via `fetch_market_snapshot()` at start of `_run_pipeline`). All 5 drafter calls within one run share the same snapshot.

After split: if each sub-agent fetches its own snapshot on every tick, you'd hit `metalpriceapi.com` Basic plan (10k req/mo) ~7× more than today. That's 7 × (24h / 2h) × 30 days = **2,520 req/mo** for snapshots alone, vs. current ~360/mo. Still well under 10k, but wasteful.

**Recommendation:** **persist `market_snapshot_id` on the `content_bundle`** at ContentAgent classify-time. Sub-agent reads it from DB by FK. No re-fetch. This is the right pattern anyway — snapshot should be pinned to the moment-of-story-selection, not moment-of-drafting-15min-later.

**Already-existing infrastructure:** `market_snapshots` table exists (from quick-oa1). Add `content_bundles.market_snapshot_id UUID REFERENCES market_snapshots(id)` in the same migration that adds `research_context`.

### 4. Advisory lock ID collision during deploy transition

When the old `gold_history_agent` (lock_id 1009 in current `worker.py`) stops being registered and `sub_video_clip` (proposed lock_id 1009) starts, there's a Railway-redeploy window where:

- Old worker process holds lock 1009 for `gold_history_agent.run()` (bi-weekly cron, mid-flight).
- New worker starts, tries to acquire 1009 for `sub_video_clip` → `pg_try_advisory_lock` returns False → **new job silently skips until old worker releases**.

This is **actually fine** — the new sub-agent just waits one tick (2h) and retries. But logs will show "skipped — lock held" during the deploy, which is noise.

**Cleaner: pick non-overlapping lock IDs.** Proposed allocation `1010–1016` for the 7 sub-agents leaves `1009` untouched and avoids the transient skip.

### 5. Content Agent's GATE step needs ordering

ContentAgent's new orchestration (INGEST → CLASSIFY → GATE) means within a single tick, GATE runs on bundles drafted in **previous** ticks by sub-agents. Make sure the order of operations is:

```python
async def run(self):
    # 1. Gate previously-drafted bundles (from sub-agent prior ticks)
    await self._gate_pending_drafts(session)
    # 2. Ingest + classify new stories → write new content_bundles (draft_content=NULL)
    await self._run_pipeline(session, agent_run)
```

NOT in reverse order. Gating first ensures ungated drafts are released to the queue as soon as ContentAgent runs, even if the ingest phase fails.

### 6. `classify_format_lightweight` → `content_type` mapping

Current classifier returns strings like `"breaking_news"`, `"thread"`, `"long_form"`, `"quote"`, `"infographic"`. Those are the `content_type` values sub-agents filter on. **Verify exact string match** — if classifier returns `"long-form"` but sub-agent queries `content_type="long_form"`, nothing matches and drafts never happen.

Grep `classify_format_lightweight` return values in `content_agent.py:266` and confirm every label maps to an extant sub-agent module.

### 7. `video_clip` needs X API quota check in sub-agent

`_search_video_clips()` currently reads `twitter_monthly_tweet_count` + `twitter_monthly_quota_limit` from Config before querying X API. That quota check logic must move **with** the function into `content/video_clip.py`. Don't leave it stranded in the orchestrator.

### 8. Test collection when modules don't yet exist (Wave 0 pattern)

STATE.md shows past phases use `pytest.skip()` BEFORE lazy imports in Wave 0 test stubs so missing modules register as SKIPPED not ERROR. Apply the same pattern for the new sub-agent test files during the initial task commit (modules don't exist → tests can still collect → green CI).

### 9. `frontend/src/pages/PlatformQueuePage.tsx` vs new `PerAgentQueuePage.tsx`

CONTEXT.md mentions "adapt `PlatformQueuePage.tsx` for per-agent content_type filter." Two options:

a) **Adapt in place:** add `contentType?: string` prop, make it optional, drive it from route param.
b) **New page:** `PerAgentQueuePage.tsx` next to (or replacing) `PlatformQueuePage.tsx`.

Option (a) is less churn but keeps a prop that's always set in the new world. Option (b) is cleaner. Since the combined `/content` route is being deleted entirely (CONTEXT locks "combined queue removed"), `PlatformQueuePage` has no remaining caller post-refactor — **rename to `PerAgentQueuePage.tsx`**, delete the dead `platform` prop, drive everything off the route param.

### 10. Railway deploy order

The scheduler and the backend are separate Railway services sharing the same DB. If the frontend deploys first (new routes pointing at `?content_type=` filter) before the backend (which doesn't yet support the query param) → tabs return 400s. Deploy order: **backend first, then frontend**. Scheduler can deploy any time after the DB migration runs.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-asyncio (auto mode) for scheduler; vitest 2.x for frontend |
| Config file | `scheduler/pyproject.toml` → `[tool.pytest.ini_options]`; `frontend/vite.config.ts` |
| Quick run command | `cd scheduler && uv run pytest -x`; `cd frontend && pnpm test` |
| Full suite command | `cd scheduler && uv run pytest && cd ../backend && uv run pytest && cd ../frontend && pnpm test && pnpm lint && pnpm build` |

### Phase Requirements → Test Map

| Req | Behavior | Test Type | Automated Command | File Exists? |
|-----|----------|-----------|-------------------|-------------|
| Sub-agent poll + draft | `BreakingNewsAgent.run_draft_cycle()` picks up bundles where content_type='breaking_news' AND draft_content IS NULL, drafts, commits | unit | `uv run pytest scheduler/tests/test_breaking_news.py -x` | ❌ Wave 0 |
| Orchestrator gate step | `ContentAgent._gate_pending_drafts()` picks up bundles where draft_content IS NOT NULL AND compliance_passed IS NULL, gates, commits | unit | `uv run pytest scheduler/tests/test_content_agent.py::test_gate_pending_drafts -x` | ❌ Wave 0 |
| Stagger config | 7 sub-agent jobs registered in scheduler with distinct start_date offsets | unit | `uv run pytest scheduler/tests/test_worker.py::test_sub_agent_staggering -x` | ❌ Wave 0 |
| Per-sub-agent advisory lock | 7 distinct lock_ids in JOB_LOCK_IDS; advisory lock wraps each sub-agent job | unit | `uv run pytest scheduler/tests/test_worker.py::test_sub_agent_lock_ids -x` | ❌ Wave 0 |
| Frontend route resolution | `/agents/:slug` resolves known slugs; unknown → redirect to `/agents/breaking-news` | unit (vitest + MSW) | `pnpm test PerAgentQueuePage` | ❌ Wave 0 |
| Backend content_type filter | `GET /queue?platform=content&content_type=thread` returns only threads | integration | `uv run pytest backend/tests/test_queue.py::test_queue_content_type_filter -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `cd scheduler && uv run pytest -x` (scheduler unit tests only — fast, ~10s)
- **Per wave merge:** `cd scheduler && uv run pytest && cd ../backend && uv run pytest && cd ../frontend && pnpm test`
- **Phase gate:** Full suite green + `pnpm lint` + `pnpm build` + `ruff check` before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `scheduler/tests/test_breaking_news.py` (+ 6 other sub-agent test files)
- [ ] `scheduler/tests/test_worker.py` — extend existing or add if missing (for stagger / lock_id / registration tests)
- [ ] `frontend/src/pages/PerAgentQueuePage.test.tsx` — route param → contentType resolution + TanStack Query key
- [ ] `frontend/src/config/agentTabs.ts` test — ordering + slug→contentType mapping sanity
- [ ] `backend/tests/test_queue.py` — extend for `content_type` query param

---

## Project Constraints (from CLAUDE.md)

- **Never auto-post to any platform.** Out of scope by design — sub-agents write `draft_content`, GATE step stamps `compliance_passed`, human copies to clipboard. No outbound posting code anywhere.
- **Single-process scheduler on Railway** — `--workers 1`. Confirmed by existing `worker.py`. Sub-agent pattern does not change this.
- **APScheduler 3.11.2 only** — no v4 alpha. Confirmed compatible with all patterns above.
- **SQLAlchemy 2.0 async only** — no v1 `Session`. All new code uses `AsyncSession` from `async_sessionmaker`.
- **Pydantic v2 only** — `model_config = ConfigDict(...)`, not v1 class-based `Config`.
- **Neon free tier, pooled endpoint** — `pool_size=15` recommendation is within limits.
- **Anthropic `AsyncAnthropic`** — all LLM calls in new sub-agents use the existing async client pattern.
- **Budget:** no new paid services introduced. metalpriceapi already paid-for; FRED free. No Redis, no Celery.
- **Never skip hooks** — standard commit hooks (ruff, vitest, eslint) apply to every task commit.

---

## Sources

### Primary (HIGH confidence)

- [APScheduler 3.11.2 IntervalTrigger docs](https://apscheduler.readthedocs.io/en/3.x/modules/triggers/interval.html) — `start_date` + `jitter` parameter semantics
- [APScheduler 3.x User guide](https://apscheduler.readthedocs.io/en/3.x/userguide.html) — `coalesce`, `max_instances`, `misfire_grace_time`, `job_defaults`
- [APScheduler base scheduler module](https://apscheduler.readthedocs.io/en/3.x/modules/schedulers/base.html) — AsyncIOScheduler + AsyncIOExecutor
- [TanStack Query v5 Query Invalidation](https://tanstack.com/query/v5/docs/framework/react/guides/query-invalidation) — hierarchical queryKey invalidation
- [React Router v6 Routing docs](https://reactrouter.com/start/declarative/routing) — dynamic params via `:slug` and `useParams`
- `scheduler/worker.py` — existing advisory lock pattern (`with_advisory_lock`, `JOB_LOCK_IDS`, `_make_job`)
- `scheduler/agents/content_agent.py:1440` — existing `_run_pipeline` structure (ingest → dedup → score → classify → draft → comply → persist)
- `scheduler/agents/gold_history_agent.py` — existing standalone sub-agent pattern (reference shape for new modules)

### Secondary (MEDIUM confidence)

- [SQLAlchemy FOR UPDATE SKIP LOCKED discussion #10460](https://github.com/sqlalchemy/sqlalchemy/discussions/10460) — confirms pattern + API shape
- [Neon — Queue System using SKIP LOCKED](https://neon.com/guides/queue-system) — reference for when SKIP LOCKED IS warranted (multi-worker FIFO); ours is not that topology
- [APScheduler Issue #296 — max_instances with misfires](https://github.com/agronholm/apscheduler/issues/296) — corroborates 5-min `misfire_grace_time` for variable workloads

### Tertiary (LOW confidence — flagged for validation)

- None — all recommendations above are grounded in primary sources or existing project code.

---

## Metadata

**Confidence breakdown:**

- Staggering strategy: **HIGH** — direct from APScheduler docs + existing lock-ID pattern.
- Handoff pattern: **HIGH** — correct topology analysis against SKIP LOCKED's multi-worker-queue use case.
- Gate placement: **HIGH** on recommendation; MEDIUM on exact latency (depends on `content_agent_interval_hours` value — flag to planner).
- APScheduler config: **HIGH** on config values; MEDIUM on `pool_size` (back-of-envelope).
- Frontend routing: **HIGH** — standard React Router v6 + TanStack Query v5 pattern.
- Pitfalls: MEDIUM — based on code reads of `content_agent.py` + `gold_history_agent.py` + `worker.py`; planner should validate each gotcha during task breakdown.

**Research date:** 2026-04-21
**Valid until:** 2026-05-21 (APScheduler 3.x stable, TanStack Query v5 stable, React Router v6 stable — no imminent breaking releases)
