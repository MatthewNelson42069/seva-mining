# v2.1 Three-Tab Content Engine — FEATURES Research

**Project:** Seva Mining v2.1 — Three-Tab Content Engine
**Mode:** Ecosystem / Feature Research
**Domain:** Personal intelligence + content-planning tool for a solo gold-sector operator
**Confidence:** HIGH (praw/Reddit API), MEDIUM (subreddit subscriber counts), HIGH (virality dedup strategy), HIGH (content angle prompt structure)
**Researched:** 2026-05-18

---

## TABLE STAKES — Must Ship in v2.1

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Tab navigation (3 tabs) | The entire v2.1 premise — without it there is no product | S | shadcn `Tabs` (Radix primitive), `value` controlled by URL hash so deep-linking works |
| Calendar CRUD (create/edit/delete items) | A calendar without editable items is a read-only view | M | `calendar_items` table, REST endpoints, TanStack Query optimistic mutations |
| Weekly Reddit ingestion (Sunday cron) | The sweeper's primary content source — without it the card is empty | M | asyncpraw read-only, 4-5 subreddits, `subreddit.top(time_filter='week', limit=10)` |
| Story virality compute | Differentiates the sweeper from a raw Reddit dump | M | SQL + Python over `daily_summaries.raw_sources_jsonb.gold_news[]` |
| Sonnet content-angle generation | The output that makes the sweeper actionable | M | Single call, ~1000 tokens, 3 angles |
| Weekly sweep card UI (Tab 3) | Surface for all three sweeper outputs | M | Three sections in one card: Reddit posts, viral stories, content angles |
| Linear-style UI redesign | The visual refresh is explicitly in scope | M | Dark + amber-500, Inter, generous whitespace, shadcn components |

---

## DIFFERENTIATORS — Nice-to-Have in v2.1

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Tag color-coding on calendar | At-a-glance content-type scanning | S | Fixed color map per tag slug (thread=blue, video=red, podcast=purple); CSS custom properties |
| Today highlight on calendar | Orientation — user instantly knows "now" | S | Bold border + subtle `amber-500/10` background tint on current day cell |
| Drag-and-drop reschedule | Faster than dropdowns for adjacent-day moves | L | `@dnd-kit/core` — see DnD section. Recommend deferring |
| Day hover "+ Add" hint | Discoverability for empty cells | S | CSS `hover:` reveal on each day cell |
| Reddit post score display | Shows why a post made the list | S | `score` field from praw `Submission.score`; render as badge |
| Weekly sweep history | Browse past weeks' cards | M | Tab 3 shows only the latest `weekly_sweeps` row by default; add a week-picker dropdown |

---

## ANTI-FEATURES — Never Ship in v2.1

| Feature | Why Avoid | What to Do Instead |
|---------|-----------|-------------------|
| AI content drafting | v1.0 sub-agents are retired; scope creep | Calendar items are plain text notes; no AI involvement |
| Autoposting | Hard prohibition in PROJECT.md | User copies text and posts manually |
| WhatsApp ping for sweeper | User did not request it; adds delivery complexity for marginal value | Defer to v2.2; Option B (user visits the tab on Sunday) |
| WhatsApp ping for calendar items | Deferred per PROJECT.md | Defer to v2.2 |
| Live macro indicators (FRED API) | Explicitly deferred to v2.2 in PROJECT.md | The Macro Economic Stats section in Tab 1 stays as-is |
| Mobile-responsive UI | Desktop-only constraint preserved | No change |
| DnD for calendar (in v2.1) | High complexity-to-value ratio for a single user with low calendar density | Ship date-dropdown reschedule in v2.1; revisit DnD in v2.2 |

---

## FEATURE DEPENDENCIES

```
Tab Navigation (shadcn Tabs)
    └──required by──> Tab 1: News Funnel (existing content moved into tab)
    └──required by──> Tab 2: Content Calendar
    └──required by──> Tab 3: Weekly Viral Sweeper

DB: calendar_items table + REST CRUD
    └──required by──> Content Calendar UI (Tab 2)
    └──required by──> Optimistic UI via TanStack Query

DB: weekly_sweeps table
    └──required by──> Weekly Sweep Card UI (Tab 3)
    └──required by──> Sunday cron job

Sunday cron (APScheduler)
    └──requires──> asyncpraw Reddit ingestion
    └──requires──> Story virality compute (queries daily_summaries)
    └──requires──> Sonnet content-angle generation
    └──all three must complete──> weekly_sweeps INSERT

Story virality compute
    └──requires──> at least 7 days of daily_summaries rows with raw_sources_jsonb.gold_news
    (implies: sweeper will return sparse/empty results if run before v2.0 has been live 7 days — already satisfied since v2.0 shipped 2026-05-06)

Linear-style UI redesign
    └──enhances──> Tab 1, Tab 2, Tab 3
    └──conflicts with──> none (purely additive CSS/component layer)
```

---

## REDDIT INGESTION — Detailed Findings

### Auth Pattern (HIGH confidence)

Read-only script application: provide only `client_id`, `client_secret`, `user_agent`. PRAW defaults to read-only mode when no `username`/`password` is given.

```python
import asyncpraw

reddit = asyncpraw.Reddit(
    client_id=settings.reddit_client_id,
    client_secret=settings.reddit_client_secret,
    user_agent=settings.reddit_user_agent,  # e.g. "SevaMiningSweeper/1.0 by seva_mining"
)
reddit.read_only = True  # defensive assertion
```

Three env vars needed: `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USER_AGENT`. Setup: reddit.com/prefs/apps → "create app" → type "script" → redirect URI `http://localhost:8080` (unused).

### API Call Pattern (HIGH confidence — praw stable docs)

```python
async for submission in reddit.subreddit("gold").top(time_filter="week", limit=10):
    post = {
        "title": submission.title,
        "score": submission.score,  # net upvotes (ups - downs)
        "url": submission.url,
        "permalink": f"https://reddit.com{submission.permalink}",
        "subreddit": submission.subreddit.display_name,
        "num_comments": submission.num_comments,
        "is_self": submission.is_self,  # True = text post
    }
```

`time_filter='week'` is the correct parameter name. Valid values: `"hour"`, `"day"`, `"week"`, `"month"`, `"year"`, `"all"`. Use `"week"` — aligns exactly with the Sunday sweep window.

**Sort order recommendation:** `top(time_filter='week')` over `hot()`. Hot ranks by a decay-weighted score that heavily favors recent posts — a post from Tuesday may outrank a more-engaged post from Monday. `top(time_filter='week')` uses net score as the ranking signal with no time decay, so it surfaces the most-voted content from the past 7 days regardless of day.

**Engagement metric recommendation:** Use `submission.score` directly. Do not use `num_comments` as primary ranking; it inflates controversial posts. Secondary signal: `score / max(num_comments, 1)` as a quality filter to exclude low-score high-comment flamewars, but don't rank by it.

**Post type:** Ingest both text posts (`is_self=True`) and link posts.

**Comments:** Do NOT ingest top comments in v2.1.

### Rate limits (HIGH confidence)

Free tier: 100 authenticated requests per minute. A Sunday sweep calling 5 subreddits × 10 posts each = 5 API calls plus ~5 for auth/metadata = well under 100 QPM. Zero rate-limit risk.

### Subreddit Viability Assessment

| Subreddit | Est. Subscribers | Activity Profile | Verdict | Notes |
|-----------|-----------------|-----------------|---------|-------|
| r/gold | ~50K–80K | Moderate posting, mix of prices/charts/news | **VIABLE** | Primary macro-gold community; quality signal |
| r/Wallstreetsilver | ~160K | High posting volume; silver-heavy; anti-establishment framing | **VIABLE** | Largest precious metals sub; silver overlaps with gold narrative |
| r/silverbugs | ~50K | Collector-hobbyist tone; lower virality for strategic content | **MARGINAL** | Drops easily if limit forces a cut; physical stacking focus |
| r/Gold_and_Silver | ~15K–30K | Low volume; combined PMs focus | **MARGINAL** | Smaller community; likely redundant with r/gold + r/Wallstreetsilver |
| r/Gold_Silver_Crypto | ~5K–15K | Very low activity | **NOT VIABLE** | Too small; crypto framing dilutes gold-specific signal |
| r/wallstreetbets (filtered) | ~15M | Massive but gold/mining mentions are rare (<1% of posts) | **NOT VIABLE AS A SUBREDDIT** | Flair filtering in WSB is unreliable; gold tickers ($GLD, $GDX) appear in comments not titles; too noisy for a weekly sweep at `limit=10` |
| r/investing | ~2M | Broad investing; gold mentioned sporadically | **MARGINAL** | Would need keyword post-filter to surface gold content; not worth the complexity |

**Recommended subreddit list (4 subreddits):**

```python
SWEEP_SUBREDDITS = ["gold", "Wallstreetsilver", "silverbugs", "Gold_and_Silver"]
```

Keep r/silverbugs and r/Gold_and_Silver despite MARGINAL rating because the sweep fetches `limit=10` per sub and the total API cost is 4 calls. Drop r/Gold_Silver_Crypto entirely (too small) and skip r/wallstreetbets (noise-to-signal ratio unacceptable).

---

## STORY VIRALITY COMPUTE — Detailed Findings

### Data Source

`daily_summaries.raw_sources_jsonb.gold_news` is an array of objects, each with shape:
```python
{"title": str, "link": str, "source_name": str, "score": float, "published_at": str}
```
This is confirmed from `_build_gold_news_section()` in `daily_summary.py` lines 203–217. The `link` field is the canonical story URL.

### Query Strategy (HIGH confidence — directly from codebase)

Pull `raw_sources_jsonb` from all `daily_summaries` rows in the past 7 days, flatten the `gold_news` arrays, then group and count.

```python
# Pseudo-SQL
SELECT raw_sources_jsonb->'gold_news' AS stories
FROM daily_summaries
WHERE generated_at >= NOW() - INTERVAL '7 days'
  AND status IN ('completed', 'partial')
```

In Python: unnest the JSONB arrays, extract `link` and `title` per story, then group.

### Dedup Strategy Recommendation (HIGH confidence)

**Use URL canonicalization, not SequenceMatcher on URLs.** Reason: URL SequenceMatcher at 0.85 would conflate `kitco.com/2026/01/article.html` with `kitco.com/2026/02/article.html` if they share 87% of URL characters — a false positive. URL strings are structured identifiers, not prose. The right dedup for URLs is canonical normalization:

```python
from urllib.parse import urlparse, urlunparse, parse_qs

def canonical_url(url: str) -> str:
    """Strip tracking params, lowercase hostname, remove trailing slash."""
    parsed = urlparse(url.lower().strip())
    STRIP_PARAMS = {"utm_source","utm_medium","utm_campaign","utm_content",
                    "utm_term","fbclid","gclid","ref","source","_ga"}
    qs = {k: v for k, v in parse_qs(parsed.query).items() if k not in STRIP_PARAMS}
    clean = parsed._replace(
        query="&".join(f"{k}={v[0]}" for k, v in sorted(qs.items())),
        fragment=""
    )
    path = clean.path.rstrip("/") or "/"
    return urlunparse(clean._replace(path=path))
```

After canonicalization, group by canonical URL. For stories that share a canonical URL across multiple daily_summaries rows, count distinct `daily_summaries` rows (not total occurrences). A story appearing in 2 fires per day × 7 days = 14 occurrences should count as 7 distinct days, not 14.

**Cross-source virality vs. frequency:** Use **distinct source_name count** as the primary virality signal. A story covered by bloomberg.com + northernminer.com + goldswitzerland.com = 3 distinct sources = highly viral. A story that appeared only on fxstreet.com 7 times in 7 fires = 1 distinct source = not viral. Formula:

```python
virality_score = len(set(story["source_name"] for story in story_group))
```

Output shape: list of `(canonical_title, canonical_url, distinct_source_count, latest_seen_at)`, sorted by `distinct_source_count` descending, top 5.

---

## SONNET CONTENT-ANGLE GENERATION — Recommended Prompt

**Model:** `claude-sonnet-4-6` (consistent with `SONNET_MODEL` in daily_summary.py)
**Max tokens:** 1000 (3 angles × ~300 tokens each)
**Timeout:** 60.0 seconds (consistent with post-ii6 pattern)

### System Prompt

```
You are a tactical content strategist for a gold-sector social media account. Your reader is a solo operator who monitors the gold market and publishes 4-5 times per week. You receive two signals: top Reddit posts from gold/silver communities this week, and the most cross-referenced news stories from the past 7 days.

Your job: identify 3 specific content angles the operator should consider this week.

Each angle must:
- Connect a Reddit signal (what investors are actually discussing) with a mainstream/institutional signal (what the news is covering)
- Identify the gap or narrative tension between them — that gap is where the interesting content lives
- Suggest a concrete framing or hook, not a generic topic
- Stay within the operator's voice: senior analyst, data-driven, cites specifics, Bloomberg commodities desk energy
- Never mention Seva Mining. Never give financial advice (no buy/sell signals).

Output format:
**Angle 1: [Short title]**
Reddit signal: [what the community is talking about and why it's getting traction]
Mainstream signal: [what the news coverage is saying]
Your angle: [specific framing or hook the operator could use]

**Angle 2: [Short title]**
[same structure]

**Angle 3: [Short title]**
[same structure]

No preamble. No postamble. Three angles only.
```

### User Prompt Template

```python
def build_sweeper_user_prompt(
    reddit_posts: list[dict],
    viral_stories: list[dict],
) -> str:
    reddit_block = "\n".join(
        f"- [{p['subreddit']}] {p['title']} (score: {p['score']})"
        for p in reddit_posts[:10]
    )
    viral_block = "\n".join(
        f"- {s['title']} (covered by {s['source_count']} sources: {', '.join(s['sources'][:3])})"
        for s in viral_stories[:5]
    )
    return (
        f"TOP REDDIT POSTS THIS WEEK (gold/silver communities):\n{reddit_block}\n\n"
        f"MOST CROSS-REFERENCED NEWS STORIES (past 7 days):\n{viral_block}\n\n"
        "Generate 3 content angles."
    )
```

**Rationale:** Mirrors the `GOLD_NEWS_SYSTEM_PROMPT` bull-thesis framing philosophy (every output must connect to a concrete insight) but reframed as "tactical content strategy." The "gap between Reddit and mainstream" instruction is the key differentiator — it forces Sonnet to produce angles based on narrative tension rather than restating the top headline.

---

## CONTENT CALENDAR UX — Detailed Findings

### Week start: Monday (ISO/EU convention)

Recommendation: **Mon–Sun**. Rationale: content planning for a professional operator aligns naturally with the ISO business week (Mon = start of work cycle). Most professional content tools (Notion calendar, Linear) default to Mon start.

### Today highlighting

Both a bold border (`ring-2 ring-amber-500`) and a subtle background tint (`bg-amber-500/5`) on the current day cell.

### Items per day

No hard cap in DB, but visually clip at 3 items with a "+N more" overflow badge. Handle overflow in the render layer only.

### Tag color-coding

Fixed color map per tag slug. Recommended initial set:

```typescript
const TAG_COLORS: Record<string, string> = {
  thread:   "bg-blue-500/20 text-blue-300",
  video:    "bg-red-500/20 text-red-300",
  podcast:  "bg-purple-500/20 text-purple-300",
  image:    "bg-green-500/20 text-green-300",
  article:  "bg-amber-500/20 text-amber-300",
  idea:     "bg-zinc-500/20 text-zinc-300",
};
const DEFAULT_TAG_COLOR = "bg-zinc-700/40 text-zinc-400";
```

### Empty cells

Show a "+ Add" hint button on hover only (`opacity-0 group-hover:opacity-100 transition-opacity`).

### Drag-and-drop vs. date dropdown

**Recommendation: Ship date-dropdown reschedule in v2.1. Defer DnD to v2.2.**

`@dnd-kit/core` for a calendar grid requires implementing custom `DragOverlay`, collision detection across a 7-column grid with overflow handling, touch vs. mouse event differences, and keyboard accessibility. ~300–500 lines of plumbing for a single-user tool where the user rarely reschedules more than 1–2 items per session. A date `<select>` dropdown on the edit modal achieves the same reschedule outcome in ~20 lines.

If DnD is added in v2.2, `@dnd-kit/core` is the correct library.

### Click-to-edit

Click any calendar item → open an inline popover or slide-over panel with: title (text input), date (date picker), tag (dropdown), markdown notes (textarea with basic MD preview toggle). Do not use a full-page modal.

---

## SUNDAY CRON DESIGN — Recommendation

**Recommendation: Separate cron at 08:00 PT Sunday.**

Rationale:
- 08:00 PT — gives Reddit a full week of posts to accumulate through Saturday.
- Do NOT tie the sweeper to the 08:00 daily summary as a side-effect. Coupling them means a sweeper timeout could delay the daily summary, and a failed daily summary would suppress the sweeper output. Separate cron jobs = independent failure domains.

APScheduler registration:

```python
scheduler.add_job(
    run_weekly_sweep,
    CronTrigger(day_of_week="sun", hour=8, minute=0, timezone="America/Los_Angeles"),
    id="weekly_sweep",
    max_instances=1,
    misfire_grace_time=1800,
)
```

This mirrors the `_make_daily_summary_job` pattern in `worker.py`. The sweep should have its own idempotency check (60-minute window pattern) to guard against misfire double-fires.

---

## WHATSAPP FOR SWEEPER

**Recommendation: No WhatsApp for the sweeper in v2.1.**

The user did not mention WhatsApp for the sweeper. The sweeper is a Sunday morning read, not a real-time alert. The web feed is the primary surface. Defer to v2.2 if the user requests it after using v2.1.

---

## FEATURE PRIORITIZATION MATRIX

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Tab navigation | HIGH | LOW | P1 |
| Calendar CRUD + DB | HIGH | MEDIUM | P1 |
| Reddit ingestion (asyncpraw) | HIGH | MEDIUM | P1 |
| Story virality compute | HIGH | MEDIUM | P1 |
| Sonnet content-angle generation | HIGH | LOW | P1 |
| Weekly sweep card UI | HIGH | MEDIUM | P1 |
| Linear UI redesign | HIGH | MEDIUM | P1 |
| Tag color-coding | MEDIUM | LOW | P2 |
| Today highlight | MEDIUM | LOW | P2 |
| Day hover "+ Add" hint | MEDIUM | LOW | P2 |
| Reddit post score badge | MEDIUM | LOW | P2 |
| Week history picker (Tab 3) | MEDIUM | MEDIUM | P2 |
| Drag-and-drop calendar | MEDIUM | HIGH | P3 (v2.2) |
| WhatsApp sweeper delivery | LOW | LOW | P3 (v2.2) |

---

## DEPENDENCY SEQUENCING FOR ROADMAP

The roadmapper should sequence phases as follows based on dependencies:

**Phase 1: DB foundation + tab shell**
- `weekly_sweeps` table (Alembic migration)
- `calendar_items` table (Alembic migration)
- shadcn `Tabs` shell in App.tsx (Tab 1 = existing feed, Tab 2 = placeholder, Tab 3 = placeholder)
- All existing v2.0 routes preserved; Tab 1 wraps existing `SummaryFeedPage` component

**Phase 2: Content Calendar (Tab 2)**
- REST CRUD endpoints for `calendar_items`
- Weekly grid view component (Mon–Sun, today highlight, tag colors, hover hints)
- Click-to-edit panel with date dropdown reschedule
- TanStack Query optimistic mutations

**Phase 3: Weekly Viral Sweeper (Tab 3)**
- asyncpraw integration (Reddit ingestion function, Sunday cron registration)
- Story virality compute (SQL query + URL canonicalization + distinct-source count)
- Sonnet content-angle call
- `weekly_sweeps` INSERT with idempotency check
- Sweep card UI component

**Phase 4: UI polish**
- Linear-style redesign applied globally (dark + amber-500, Inter, whitespace tokens)
- shadcn component audit — replace any ad-hoc form elements

This sequencing works because: Phase 1 provides the structural shell needed by Phases 2 and 3 independently; Phase 2 and 3 can be developed in parallel if bandwidth allows; Phase 4 is a pure CSS/component layer that does not affect logic.

---

## OPEN QUESTIONS / GAPS

1. **r/Gold subscriber count:** Confirm actual subscriber count by visiting reddit.com/r/gold before finalizing the subreddit list.

2. **`REDDIT_USER_AGENT` string format:** Reddit requires a descriptive user agent. Convention: `"<platform>:<app_id>:<version> (by /u/<reddit_username>)"`. For non-commercial read-only use: `"SevaMiningSweeper/1.0 by sevabot"` is sufficient.

3. **`r/wallstreetbets` gold-tagged posts:** If the user wants WSB exposure in v2.2, a keyword post-filter (`"gold" in submission.title.lower()`) after fetching `limit=100` from r/investing or r/stocks would be a cleaner approach than targeting WSB directly.

4. **`weekly_sweeps` idempotency key:** Should be `week_start` (the Sunday of the swept week), not `generated_at`. The idempotency check is: "does a `weekly_sweeps` row already exist with `week_start = this_sunday`?"

---

## Sources

- PRAW stable documentation — authentication: https://praw.readthedocs.io/en/stable/getting_started/authentication.html (HIGH confidence)
- PRAW quick start — subreddit listing methods: https://praw.readthedocs.io/en/stable/getting_started/quick_start.html (HIGH confidence)
- Reddit API free tier rate limits 2026: https://octolens.com/blog/reddit-api-pricing (MEDIUM confidence)
- Reddit API app creation guide 2026: https://redaccs.com/reddit-api-guide/ (MEDIUM confidence)
- URL deduplication / canonicalization best practices: https://potentpages.com/web-crawler-development/web-crawlers-and-hedge-funds/deduplication-canonicalization-preventing-double-counts-and-phantom-signals (MEDIUM confidence)
- shadcn Tabs component: https://ui.shadcn.com/docs/components/radix/tabs (HIGH confidence)
- shadcn dark mode + amber theme: https://ui.shadcn.com/docs/theming and https://www.shadcn.io/theme/amber-minimal (HIGH confidence)
- dnd-kit React drag-and-drop complexity: https://www.blog.brightcoding.dev/2025/08/21/the-ultimate-drag-and-drop-toolkit-for-react-a-deep-dive-into-dnd-kit/ (MEDIUM confidence)
- r/WallStreetSilver ~160K subscribers: https://subredditstats.com/r/Wallstreetsilver (MEDIUM confidence)
- Silver Gold Bull precious metals Reddit communities: https://silvergoldbull.com/education/5-best-precious-metals-communities-on-reddit/ (MEDIUM confidence)
