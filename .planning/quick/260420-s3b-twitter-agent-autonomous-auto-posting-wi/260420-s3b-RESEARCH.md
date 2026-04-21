# Quick Task 260420-s3b: Twitter Agent Autonomous Auto-Posting — Research

**Researched:** 2026-04-21
**Domain:** X (Twitter) API v2 write path, tweepy async, Claude Haiku structured output, SQLAlchemy/Alembic, React Router + TanStack Query
**Confidence:** HIGH on all technical integration points; HIGH on the blocking platform-policy finding below.

---

## ⚠️ CRITICAL FINDING — READ BEFORE PLANNING

**X officially restricted programmatic replies on April 20, 2026 (yesterday).** The restriction is live today and applies to all self-serve tiers including Basic.

**The rule (from @XDevelopers, announcement ID 2026084506822730185):**

> "To help address automated reply spam, programmatic replies via `POST /2/tweets` are now restricted for X API. You can only reply if the original author @mentions you or quotes your post. Non-replies will remain unchanged. Applies to Free, Basic, Pro, Pay-Per-Use."

**What this means for this task:** The core "reply to top-2 gold-sector tweets" flow is **non-functional on Basic tier**. The @sevamining account is not being @-mentioned or quoted by Gold Telegraph, Peter Schiff, or any watchlist account — so every `create_tweet(text=..., in_reply_to_tweet_id=...)` call will be **rejected by the X API**.

**Pricing confirmation:** "Summoned replies" (where the original author mentioned/quoted you) remain at $0.01/post. Other replies are blocked, not merely surcharged.

**Retweets are NOT affected.** `POST /2/users/:id/retweets` still works normally — the restriction is specific to reply posts.

### Operator decision required (before planning proceeds)

Three paths forward. Pick one or task blocks on ambiguity:

| Option | What it means | Effort |
|---|---|---|
| **A. Retweet-only autonomous** | Drop the 3-draft-reply pipeline entirely. Keep only the autonomous retweet gate. Senior agent's `select_best_of_n()` becomes future-work. | Minimal — reuse existing retweet gate logic, just remove the manual-approval step. |
| **B. Proceed anyway, accept 100% reply failure** | Ship the reply path, let it fail in production, log the 403s, manually monitor. Only value: `posted_tweets` schema + dashboard UI gets built for when X reverses course. | Full scope, zero real-world replies posted. |
| **C. Pivot to "reply draft → WhatsApp → operator copies into X app"** | Senior selects best-of-3, but posts via WhatsApp notification (operator pastes into native X app). Preserves the Senior-selection-quality upside without X API reply. | Medium — wires Senior selection + WhatsApp but drops tweepy write path for replies. |

**Recommendation:** Option A. It's the smallest scope that actually posts content autonomously and aligns with the operator's "automate what can be automated" intent. The 3-draft-reply + Senior-select pipeline from CONTEXT.md can be deferred to a future quick-task and revisited if/when X relaxes the rule — the research below still applies when that day comes.

**Rest of this document assumes the operator will confirm one of the three paths.** Findings on tweepy, audit schema, and frontend tab are path-agnostic.

---

## User Constraints (from CONTEXT.md)

### Locked Decisions

1. **3-candidate generation method:** Single Sonnet call returning a 3-item JSON array (not 3 separate calls). Prompt asks for 3 distinct angles — data-point / counter-view / question-hook.
2. **Senior position-bias mitigation:** Shuffle the 3 candidates before passing to Haiku. Record `presented_order` (shuffled order Haiku saw) + `selected_candidate_id` in `posted_tweets` for post-hoc bias analysis. Candidates tagged with stable UUIDs so rationale field stays traceable.
3. **Daily-cap race handling:** Accept small overshoot risk. Strict-serial `SELECT COUNT(*) FROM posted_tweets WHERE posted_at >= date_trunc('day', now() at time zone 'UTC')` + gate on `< 10`. No advisory lock. Rationale: only twitter_agent writes to `posted_tweets`; retweet + reply loops inside a single run are serial; X user-level rate limit is defense-in-depth.
4. **Kill-switch check timing:** Check `config.twitter_auto_post_enabled` once at start of `_run_pipeline()`, cache for the run. 30-minute flip-to-take-effect latency is acceptable.
5. **Models:** `claude-sonnet-4-5` for 3-candidate drafting; `claude-haiku-4-5` for compliance filter AND Senior's `select_best_of_n()`.
6. **Fence-stripping:** Reuse the preprocess from `content_agent.py:558-566` for Haiku JSON responses. Haiku 4.5 wraps JSON in ```` ```json ... ``` ```` even when prompt says bare JSON.
7. **Fail-closed policy:** Every skip path emits a distinctive log line. No silent fall-through.
8. **Naming:** config key `twitter_auto_post_enabled` (string `"true"` / `"false"`); env vars `X_API_CONSUMER_KEY`, `X_API_CONSUMER_SECRET`, `X_API_ACCESS_TOKEN`, `X_API_ACCESS_TOKEN_SECRET` (already in Railway); new table `posted_tweets`; frontend route `/agents/senior`.
9. **CONTEXT.md is canonical:** All 4 OAuth tokens already provisioned; X Developer app permission is "Read and Write"; access tokens regenerated post-permission-flip.

### Claude's Discretion

- Exact Senior `select_best_of_n()` signature and module location inside `senior_agent.py`.
- Exact `posted_tweets` column set (CONTEXT gives direction — "audit every live post" — I pick the columns).
- Frontend route registration mechanics (React Router), styling to match existing pattern.
- Whether to use Anthropic structured outputs (GA for Haiku 4.5) or bare JSON + fence-stripping — see `## Anthropic Haiku structured output` below.

### Deferred Ideas (OUT OF SCOPE)

- Content agent auto-posting — content agent stays manual-approval.
- Temperature variance / sampling alternatives for 3-candidate generation.
- Monitoring dashboard for position-bias analysis (data is logged for future review only).
- Advisory lock for daily-cap race (overshoot risk accepted).

---

## Phase Requirements

| Area | Research Support |
|------|------------------|
| tweepy OAuth 1.0a write client | Constructor verified — single `AsyncClient` handles read + write when all 5 auth params passed. See "Standard Stack" below. |
| `create_tweet` / `retweet` return shapes | Verified via tweepy master source. `response.data["id"]` / `response.data["text"]`. See "Code Examples". |
| X API write quotas | Verified — Basic tier = 10,000 POSTs/month (including retweets). Daily rate limit ~100 posts / 24h. |
| Haiku 4.5 structured output | Verified — Structured Outputs GA as of Nov 2025. CONTEXT's bare-JSON + fence-stripping approach is valid; Structured Outputs is an optional upgrade. |
| `posted_tweets` schema | Verified — next migration number is `0008` in `backend/alembic/versions/`. FK to `agent_runs.id` (UUID PK exists). |
| Frontend Senior Agent tab | Verified — route registration via `App.tsx` Routes + `Sidebar.tsx` NavLink. Matches existing DigestPage read-only pattern. |

---

## Standard Stack

### Already in project, unchanged

| Library | Version | Use |
|---|---|---|
| tweepy[async] | 4.x (4.14.0 current) | X API v2 async client. Already imported as `tweepy.asynchronous.AsyncClient`. |
| anthropic | 0.86.0+ | `AsyncAnthropic` for Sonnet drafting and Haiku compliance/selection. |
| SQLAlchemy 2.0 + asyncpg | current | New `PostedTweet` ORM model in `scheduler/models/` + mirror in `backend/app/models/`. |
| Alembic | 1.14.x | Migration `0008_add_posted_tweets.py` in `backend/alembic/versions/`. |
| React 19 + Vite + Tailwind v4 | current | New page component `frontend/src/pages/SeniorAgentPage.tsx`. |
| TanStack Query v5 | current | New hook `useSeniorPostedTweets` following `useQueue.ts` pattern. |

### NOT needed

- No new dependencies. This task reuses everything already installed.

**Version verification (tweepy):** Latest stable on PyPI is 4.14.0 (Mar 2024). The project uses `tweepy[async]` — already installed with aiohttp + async-lru via optional dep (confirmed in STATE.md `[Phase 04-twitter-agent]` note).

---

## 1. tweepy 4.x AsyncClient — OAuth 1.0a write path

**Confidence:** HIGH (verified against `tweepy/tweepy/asynchronous/client.py` on master).

### Constructor — single client for read + write

```python
AsyncClient(
    bearer_token=None,          # OAuth 2.0 Bearer — used for read operations
    consumer_key=None,          # OAuth 1.0a Consumer Key
    consumer_secret=None,       # OAuth 1.0a Consumer Secret
    access_token=None,          # OAuth 1.0a Access Token (user context)
    access_token_secret=None,   # OAuth 1.0a Access Token Secret
    *,
    return_type=Response,
    wait_on_rate_limit=False,
)
```

**Verified behavior:** A single `AsyncClient` instance with ALL FIVE auth params can handle both read (`get_users_tweets()` → uses bearer) and write (`create_tweet()`, `retweet()` → uses OAuth 1.0a user context). This **overrides CONTEXT.md's assumption of two separate clients**.

**Per-call auth selection:** Methods like `create_tweet()` and `retweet()` take a keyword-only `user_auth=True` parameter (default `True`) → when True, the method uses OAuth 1.0a from the 4 consumer/access tokens. Read methods like `get_users_tweets()` default to bearer token.

**Recommendation:** Extend the existing `self.tweepy_client` in `TwitterAgent.__init__()` to pass all 5 params. Do NOT create a second client — adds complexity without benefit.

```python
self.tweepy_client = tweepy.asynchronous.AsyncClient(
    bearer_token=settings.x_api_bearer_token,
    consumer_key=settings.x_api_consumer_key,
    consumer_secret=settings.x_api_consumer_secret,
    access_token=settings.x_api_access_token,
    access_token_secret=settings.x_api_access_token_secret,
    wait_on_rate_limit=False,
)
```

Then add the 4 new settings to `scheduler/config.py`:

```python
x_api_consumer_key: Optional[str] = None
x_api_consumer_secret: Optional[str] = None
x_api_access_token: Optional[str] = None
x_api_access_token_secret: Optional[str] = None
```

Startup validation in `worker.py::_validate_env()` — add a `write_auth` category that logs WARNING when any of the 4 are missing AND kill-switch is `"true"`.

### `create_tweet()` — reply signature and response

```python
async def create_tweet(
    self, *,
    text=None,
    in_reply_to_tweet_id=None,    # str — parent tweet ID for reply
    quote_tweet_id=None,
    reply_settings=None,
    # ... other params for polls/media/etc not used here
    user_auth=True,                # stays True for OAuth 1.0a write
) -> Response
```

**Response shape (verified via tweepy source + discussion #2042):**

```python
response = await client.create_tweet(text="...", in_reply_to_tweet_id="123")
response.data            # dict: {"id": "1234567890", "text": "the posted text"}
response.data["id"]      # str — the newly created tweet ID → store in posted_tweets
response.data["text"]    # str — what was actually posted (may differ from input if X truncated)
response.errors          # list[dict] — non-empty on partial failure
```

**Key finding:** `response.data` is a **dict**, accessed with `["id"]` / `["text"]` — NOT attribute access. CONTEXT.md asked "does it return tweet_id directly, or nested". Answer: nested one level, at `response.data["id"]`.

### `retweet()` — signature and response

```python
async def retweet(self, tweet_id, *, user_auth=True) -> Response
```

**Response shape:**

```python
response = await client.retweet(tweet_id="1234567890")
response.data          # dict: {"retweeted": True}
```

**Idempotency (MEDIUM confidence — documented by analogy to unretweet):** The unretweet endpoint is documented as idempotent ("succeeds with no action when already unretweeted"). The retweet endpoint is NOT documented as idempotent — expect `tweepy.Forbidden` with X error code 139 ("You have already retweeted this Tweet") when retweeting an already-retweeted post. **Must catch and log, not raise.**

### Rate limit info on response

Tweepy surfaces rate-limit headers via the underlying `aiohttp.ClientResponse` — accessible in `AsyncClient` via `response.response.headers` (nested because `response` is tweepy's `Response` wrapper; `.response` is the raw aiohttp response when available). Standard headers: `x-rate-limit-remaining`, `x-rate-limit-reset` (Unix epoch).

**Practical note:** For a 10-post/day pipeline, proactive header logging is low-value. Catching `tweepy.TooManyRequests` (429) and `tweepy.Forbidden` (403) is sufficient.

---

## 2. X API Basic tier write quotas

**Confidence:** HIGH on monthly and daily caps; MEDIUM on retweet pool sharing (multiple consistent sources but no single definitive official page).

### Quotas (Basic tier, current as of April 2026)

| Dimension | Limit | Source |
|---|---|---|
| POST /2/tweets | **10,000/month** (app-level) | Multiple 2025/2026 sources consistent |
| POST daily rate | **100/24h** (per-user) | Elfsight 2026 guide + others |
| POST /2/users/:id/retweets | Shares the 10,000 monthly POST pool | Inferred — retweets count as "posts" in all pricing docs |
| POST /2/users/:id/retweets (rate) | **50/15min per user** | X docs: "manage Retweets endpoints limited to 50 requests per 15 min" |

**Combined cap is comfortably within limits:** 10 posts/day × 30 days = 300/month, well under 10,000. Daily 100/24h is 10× the CONTEXT cap.

### Quota-exhaustion error codes

| HTTP | tweepy exception | Meaning | Action |
|---|---|---|---|
| 429 | `tweepy.TooManyRequests` | Rate-limit exceeded (per-minute, per-15min, or per-day rolling window) | Log, skip remaining posts this run, retry next cron cycle |
| 403 (error 139) | `tweepy.Forbidden` | Already retweeted | Log "already retweeted — skipping", don't count as failure |
| 403 (no specific code) | `tweepy.Forbidden` | Permission wrong (e.g., read-only tokens despite "read+write" flip), or reply-restriction (see CRITICAL FINDING) | Log distinctive message, skip, do NOT disable kill-switch (single failure != pipeline broken) |
| 401 | `tweepy.Unauthorized` | OAuth creds invalid | Log ERROR, auto-disable kill-switch? **Do not** auto-disable — let operator decide. Loud log is sufficient. |

### Monthly quota exhaustion

Hitting the 10,000/month cap returns **429 with `x-rate-limit-reset` set to the next UTC month boundary**. Hard block until the 1st. At ≤300 posts/month, this is not a real risk unless a bug causes runaway posting.

---

## 3. Anthropic Haiku structured output for "rank best of N"

**Confidence:** HIGH (verified: Structured Outputs GA for Haiku 4.5 as of Nov 2025 per Anthropic blog).

### Two valid approaches — bare JSON is the simpler path

| Approach | Pros | Cons |
|---|---|---|
| **A. Bare JSON + fence-stripping (CONTEXT default)** | Zero new code patterns — reuses `content_agent.py:558-566` exactly. No beta headers. | 1 function call returns wrapped JSON ~50% of the time per pwh findings; preprocess required. |
| **B. Structured Outputs (`response_format: {type: "json_schema", ...}`)** | Guaranteed schema compliance — no fence-stripping needed. | New code pattern introduced for one use case. Small grammar-compile latency on first call. |
| **C. Tool-use with enum parameter** | Most rigid structure — Haiku is forced to "call" a `select_best` tool with `selected_index: int, rationale: str`. | Most verbose code path. Response parsing through `message.content[].input`. |

**Recommendation:** Stick with **Option A** (CONTEXT's locked decision). The fence-stripping preprocess is already battle-tested in this codebase (pwh commit 3525c47, used in 4 locations in `content_agent.py`). Adding Structured Outputs for a single new Haiku call introduces a pattern divergence without material reliability gain at this scale (expected ~50 Haiku calls/day).

**If position-bias proves stubborn in post-hoc analysis**, Option B/C could be revisited in a follow-up.

### Haiku 4.5 quirks (beyond fence-wrapping)

- **Whitespace-only prefix:** Sometimes returns `" ```json\n{...}```"` with leading space. The existing preprocess uses `raw.startswith("```")` — safe because `.strip()` is called first at line 550.
- **Trailing prose after JSON:** Rare but documented — Haiku occasionally appends `"This choice prioritizes..."` after the JSON. Mitigation: the existing `.rsplit("```", 1)[0].strip()` handles the trailing fence; if unfenced, `json.loads()` raises and the fail-closed path kicks in.
- **Null vs missing fields:** Haiku 4.5 tends to use `null` not omit fields. Plan the schema accordingly (`{"selected_candidate_id": "uuid-string", "rationale": "string"}` — no optionals needed).

### Suggested `select_best_of_n()` prompt shape

```json
{
  "selected_candidate_id": "uuid-of-winner",
  "rationale": "One sentence explaining the choice."
}
```

Present candidates tagged by UUID in the prompt body so position-index in the prompt ≠ identifier in the response.

---

## 4. Integration points with existing scheduler code

**Confidence:** HIGH (all files read in full).

### `twitter_agent._run_pipeline()` — where to insert

Current structure (twitter_agent.py:843-1023):

```
Step 1a: Expire stale pending drafts
Step 2:  Quota check (read quota — don't confuse with new posting cap)
Step 1b: Read engagement gate thresholds from DB
Step 3:  Load watchlist
Step 4:  Get since time
Step 5:  Fetch watchlist tweets (watchlist-only per lw4)
Step 6:  Topic filter (GOLD_KEYWORDS + ALWAYS_ENGAGE_HANDLES bypass)
Step 7:  Engagement gate (50 likes floor per lw4 + ALWAYS_ENGAGE_HANDLES bypass)
Step 8:  Score with recency decay
Step 9:  select_top_posts(max_count=5)
Step 10: _process_drafts() — drafts reply + RT alternatives, compliance check, writes DraftItems
Step 11: Update AgentRun record
Step 12: Senior Agent intake (process_new_items)
Step 13: WhatsApp new-item notification
```

**Insertion points for auto-posting:**

1. **Top of `_run_pipeline()` (before Step 1a):** Kill-switch check. Read `config.twitter_auto_post_enabled`, store as `self._auto_post_enabled` for the run. If `"false"`, log `"TwitterAgent: auto-post DISABLED via config — running in draft-only mode"` and fall back to existing flow (keep building DraftItems for manual-approval; skip Step 14).
2. **After Step 9 (top-5 selection):** If auto-post enabled, **cap at top-2** (CONTEXT: "Top-2 tweets/run"). Pass those to a new `_process_autonomous_posts()` method that replaces Step 10 when auto-post is enabled.
3. **New Step 14 (replacing/supplementing Step 10):** Autonomous post pipeline — for each of top-2: single Sonnet call → Haiku compliance filter → Senior `select_best_of_n()` → `create_tweet()` / `retweet()` → INSERT `posted_tweets` row. Per-post try/except that logs but never crashes the loop (EXEC-04).
4. **Retweet gate:** Current code **has no retweet path** — the existing `_process_drafts()` writes `alternatives=[{"type":"reply",...}]` and the legacy `draft_for_post()` module function writes both `reply` and `retweet_with_comment` types but is only used by tests. **CONTEXT is misleading here** — the "retweet gate" is a design intent, not implemented code. A retweet gate must be BUILT as part of this task (not preserved as existing).

**Important discovery:** The live `_draft_for_post()` (class method, line 570) generates **reply alternatives only**. The module-level `draft_for_post()` (line 1131) generates both reply AND retweet-with-comment — but it's unused by the live pipeline, only by legacy tests. If "retweet gate unchanged" means something specific, the operator or planner needs to verify against the intent.

### `senior_agent.py` — where to add `select_best_of_n()`

Current structure: `SeniorAgent` class with instance methods + module-level `process_new_items()` function at line 864.

**Recommendation:** Add `select_best_of_n()` as a **module-level function** (NOT a class method), following the established pattern (`process_new_items`, `extract_fingerprint_tokens`, `jaccard_similarity` — all module-level). This matches CONTEXT's note: "standalone module-level function (not tied to cron)."

```python
# Add at module level in senior_agent.py, e.g., near line 862
async def select_best_of_n(
    candidates: list[dict],           # [{"id": "uuid", "text": "..."}]
    context: dict,                     # {"tweet_text": "...", "author_handle": "..."}
    anthropic_client: AsyncAnthropic,
) -> Optional[dict]:
    """Senior picks the best candidate. Returns {"id", "text", "rationale"} or None on failure."""
    # 1. Shuffle candidates (bias mitigation — locked decision)
    # 2. Build prompt listing shuffled candidates by their stable UUIDs
    # 3. Call claude-haiku-4-5
    # 4. Fence-strip and parse JSON (reuse content_agent.py:552-564 pattern)
    # 5. Return the winning candidate dict (looked up by selected_candidate_id)
    # 6. Fail-closed: on JSONDecodeError / API error, return None → caller skips posting
```

Reason it's module-level: no shared state with `SeniorAgent` class (no DB session, no config lookup — `anthropic_client` is injected). Keeps it importable from twitter_agent without class instantiation.

### `posted_tweets` schema design

**Next migration number:** `0008` (in `backend/alembic/versions/` — scheduler has no separate alembic dir; backend owns migrations per STATE).

Recommended columns (ORM model to mirror `content_bundle.py` style — both `scheduler/models/posted_tweet.py` AND `backend/app/models/posted_tweet.py`):

```python
class PostedTweet(Base):
    __tablename__ = "posted_tweets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_run_id = Column(UUID(as_uuid=True), ForeignKey("agent_runs.id"), nullable=True)
    post_type = Column(String(20), nullable=False)       # "reply" | "retweet"
    tweet_id = Column(String(32), nullable=False)        # X tweet ID returned by create_tweet/retweet
    in_reply_to_tweet_id = Column(String(32))            # parent tweet (for replies only)
    source_tweet_id = Column(String(32))                 # the tweet we retweeted or replied to
    source_account = Column(String(255))                 # @handle of the source post author
    posted_text = Column(Text)                           # the reply text (null for pure retweets)
    score = Column(Numeric(5, 2))                        # composite score of the source tweet
    candidates = Column(JSONB)                           # [{"id":"uuid","text":"..."},...] all 3 drafted
    presented_order = Column(JSONB)                      # ["uuid-1","uuid-2","uuid-3"] shuffled order Haiku saw
    selected_candidate_id = Column(UUID(as_uuid=True))   # which candidate won
    selection_rationale = Column(Text)                   # Senior's rationale
    posted_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_posted_tweets_posted_at", "posted_at"),       # daily cap query uses this
        Index("ix_posted_tweets_tweet_id", "tweet_id", unique=True),  # idempotency guard
        Index("ix_posted_tweets_source_tweet_id", "source_tweet_id"), # retweet dedup lookup
        CheckConstraint("post_type IN ('reply','retweet')", name="ck_posted_tweets_post_type"),
    )
```

**UNIQUE on `tweet_id`** is critical — **PREVENTS THE FOLLOWING BUG:** agent posts, crashes before INSERT, next run re-posts. With UNIQUE, a second identical INSERT raises IntegrityError and the duplicate-post bug is caught loud. Without it, duplicate tweet_id rows silently accumulate and the 10/day cap query undercounts. **Add it.**

**UNIQUE on `source_tweet_id` + `post_type="retweet"`** is also worth considering via partial index, to catch "retweet the same source twice" bugs. Optional — tweepy already returns 403/139 on duplicate retweet, so DB-layer uniqueness is belt-and-braces.

**`agent_runs.id` is UUID PK** — confirmed via `scheduler/models/agent_run.py:11`. FK is safe.

### Naming convention for migration file

Pattern (from `backend/alembic/versions/0007_add_market_snapshots.py`):

- Filename: `0008_add_posted_tweets.py`
- `revision = "0008"`, `down_revision = "0007"`
- Docstring + `Create Date` comment at top
- `op.create_table()` with `sa.PrimaryKeyConstraint`, `sa.CheckConstraint`, `sa.ForeignKeyConstraint`
- Separate `op.create_index()` calls (not embedded in create_table)
- `downgrade()` drops indexes then table in reverse order

---

## 5. Frontend Senior Agent tab

**Confidence:** HIGH (all relevant files read).

### Navigation structure

`frontend/src/components/layout/Sidebar.tsx` defines two arrays:

- `agentItems` — lines 22-35: currently `[Twitter, Content]`, each with `{to, label, icon, badge}`
- `bottomItems` — lines 37-40: currently `[Digest, Settings]`

The NavLink rendering loop iterates both arrays (lines 58-100). **Add one entry to `agentItems`** for the Senior Agent:

```tsx
{
  to: '/agents/senior',
  label: 'Senior',
  icon: <Gavel className="size-4" />,   // or Brain/Sparkles — pick from lucide-react
  badge: null,  // no draft count — this is a read-only activity log
},
```

Since this is a **log view** (not an approval queue), `badge: null` — no count. (If operator wants "today's posts" count later, it's a simple additional query.)

### Route registration

`frontend/src/App.tsx` currently has a `ProtectedRoute` wrapper with 6 routes inside `AppShell`. **Add one route:**

```tsx
<Route path="/agents/senior" element={<SeniorAgentPage />} />
```

CONTEXT specifies the route as `/agents/senior`. Matches existing convention: `/twitter`, `/content`, `/digest`, `/content-review`, `/settings` — flat top-level routes, no nesting. The `/agents/` prefix is a new convention — acceptable but note the sidebar uses `to: '/twitter'` (no `/agents/` prefix). **Small inconsistency worth flagging to operator:** either rename to `/senior` (flat like the others) or migrate Twitter/Content to `/agents/twitter` in a future cleanup. **Recommendation: use `/senior` flat** to match existing pattern. If operator insists on `/agents/senior`, that's fine — just be aware Twitter NavLink uses `to="/twitter"`.

### Page component pattern

Follow `DigestPage.tsx` (read-only log display) — NOT `QueuePage.tsx` (approval queue with mutations).

**Minimal component skeleton:**

```tsx
// frontend/src/pages/SeniorAgentPage.tsx
import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '@/api/client'
import { formatDistanceToNow } from 'date-fns'

interface PostedTweet {
  id: string
  post_type: 'reply' | 'retweet'
  tweet_id: string
  source_tweet_id: string | null
  source_account: string | null
  posted_text: string | null
  score: number | null
  selection_rationale: string | null
  posted_at: string
}

export function SeniorAgentPage() {
  const { data, isLoading, error } = useQuery<PostedTweet[]>({
    queryKey: ['senior-posted-tweets'],
    queryFn: () => apiFetch<PostedTweet[]>('/senior/posted-tweets?days=7'),
    refetchInterval: 60_000,  // every 60s — this is an activity log
  })
  // ...render list grouped by day, with type badge (reply/retweet), linked tweet_id
}
```

### Backend endpoint pattern

Create `backend/app/routers/senior.py` mirroring `agent_runs.py`:

```python
router = APIRouter(
    prefix="/senior",
    tags=["senior"],
    dependencies=[Depends(get_current_user)],
)

@router.get("/posted-tweets", response_model=list[PostedTweetResponse])
async def list_posted_tweets(
    days: int = Query(7, ge=1, le=30),
    db: AsyncSession = Depends(get_db),
):
    cutoff = datetime.now(UTC) - timedelta(days=days)
    stmt = select(PostedTweet).where(PostedTweet.posted_at >= cutoff).order_by(PostedTweet.posted_at.desc())
    result = await db.execute(stmt)
    return [PostedTweetResponse.model_validate(r) for r in result.scalars().all()]
```

Register in `backend/app/main.py` below line 59 (following include_router pattern).

Schema in `backend/app/schemas/posted_tweet.py` — new file following `agent_run.py` schema style.

### TanStack Query + apiFetch 5-line boilerplate

From existing hooks (`useQueue.ts`, `useContentBundle.ts`, and confirmed by `DigestPage.tsx`):

```tsx
const { data, isLoading, error } = useQuery<T>({
  queryKey: ['descriptive-key', ...dependencies],
  queryFn: () => apiFetch<T>('/path'),
  refetchInterval: 60_000,  // optional — polling for live logs
})
```

### Tailwind v4 confirmation

Confirmed current — `frontend/src/index.css` uses `@import "tailwindcss"` (v4 syntax) per Phase 08 decisions. `package.json` has `@tailwindcss/vite` plugin. Use current utility classes (`size-4`, `bg-zinc-900`, `text-amber-400` — all present in Sidebar). Theme palette observed: zinc (bg), amber (accent), white/zinc-400 (text).

---

## 6. Common pitfalls for auto-posting

**Confidence:** HIGH on API behavior; MEDIUM on token-regeneration propagation delay.

### Pitfall 1: OAuth 1.0a token regeneration propagation delay

**Status (MEDIUM confidence):** X does not officially document a delay. Forum reports range from "immediate" to "20 minutes" for a regenerated Access Token to carry the new write permission.

**What goes wrong:** Operator flipped app to "Read and Write", clicked Regenerate. Code deploys. Agent runs. `create_tweet()` returns `403` with a generic "Could not authenticate" — not because tokens are wrong, but because X's token service hasn't propagated the new permission.

**How to avoid:**
- First live run should be **manual smoke test** — post a single tweet via `railway run python -c "..."` and confirm HTTP 201.
- Production kill-switch check on 403: log `"write-auth failure — if tokens were just regenerated, wait 15-20 min and retry"`. Do NOT auto-disable.
- Don't deploy auto-posting immediately after token regeneration. Wait 30 min, then deploy.

**Warning signs:** 403 on FIRST post of first run, but generic `tweepy.Forbidden` (not error 139).

### Pitfall 2: `in_reply_to_tweet_id` and `@username` prepending

**What X does:** The v2 endpoint **does auto-thread** the reply (parent is set correctly, shows in Replies tab of the parent). **X does NOT auto-prepend the @username** in the reply body.

**Implication for this task:** The reply text drafted by Sonnet **should NOT include `@sourcehandle` at the start** — X already threads it; a manual `@` would make it render as `@goldtelegraph_ @goldtelegraph_ ...` (double-mention) if X DID prepend (it doesn't), or just as a visible `@` clutter if it doesn't.

**Recommendation:** Sonnet's system prompt explicitly says **"NEVER prepend @username — the reply is already threaded by the API."** Drop any `@handle` from start of draft text if Sonnet adds one. (A simple regex: `text.lstrip().lstrip("@" + author_handle).lstrip()`.)

### Pitfall 3: Retweet idempotency — error 139

**What goes wrong:** Agent retweets tweet X on Monday. Scheduler restart or bug causes the same tweet to resurface as "qualifying" on Tuesday. Second `retweet()` raises `tweepy.Forbidden` with X error code 139.

**How to avoid:**
- Query `posted_tweets WHERE source_tweet_id = ? AND post_type = 'retweet'` before attempting any retweet. Skip if row exists.
- Wrap `retweet()` in `try/except tweepy.Forbidden` — inspect `exc.api_codes` (tweepy surfaces X error codes as a list on the exception). If `139 in (exc.api_codes or [])`, log as INFO (expected) not WARNING. Still INSERT a row into `posted_tweets` with a marker? No — simpler: just log and move on; the fact that the retweet already exists means a prior row was already inserted.

**Warning sign:** Railway logs show `tweepy.Forbidden` at INFO level regularly — benign. At WARNING level regularly — look for bug in the "has this been retweeted" pre-check.

### Pitfall 4: Daily-cap query uses wrong timezone

**What goes wrong:** `date_trunc('day', now())` uses the DB server timezone (Neon default is UTC, but verify). If Neon is in a non-UTC timezone, the "day" bucket drifts from operator's mental UTC-midnight reset.

**How to avoid:** Use explicit UTC: `date_trunc('day', now() at time zone 'UTC')` — CONTEXT already specifies this. Planner must preserve this exact SQL.

### Pitfall 5: Posted-tweets uniqueness — race with crash

**What goes wrong:** `create_tweet()` succeeds at X. Network blip or crash before the INSERT commits. Next run re-fetches same source tweet (if not yet aged out of the 1-6h recency window), drafts 3 new candidates, posts again. Duplicate in the wild.

**How to avoid:**
- UNIQUE index on `tweet_id` as recommended. Second INSERT fails loudly — at least the *logging* is clean.
- Pre-post check: query `posted_tweets WHERE source_tweet_id = ? AND post_type = 'reply' AND posted_at >= now() - interval '24 hours'`. If row exists, skip. This closes the real-world window.
- Accept residual risk: if X create_tweet succeeds and DB write fails, there's a small window where a second run could repost. Pre-post check mitigates this to "source tweet re-qualifies in next 24h" which is already bounded by the 6h recency decay.

### Pitfall 6: X API 2026-04-20 reply restriction (THE blocker)

See CRITICAL FINDING at top of document. This is the single most important pitfall — it renders the reply path non-functional on Basic tier unless the original author @-mentioned or quoted @sevamining. Current watchlist accounts do not do either.

**Workaround (none on Basic):** Pro tier is not exempt either. Only Enterprise is exempt. Enterprise pricing is $42K+/yr — far outside the $225/mo budget.

---

## Runtime State Inventory

**Trigger check:** This is a feature-add, not a rename/refactor/migration. Per Step 2.5 guidance, this section is included only when trigger applies.

**Nothing found in any category — verified:** No strings renamed, no existing records to migrate, no OS-registered tasks to re-register, no SOPS keys renamed (all 4 X API write env vars are NEW additions, not renames of existing vars).

---

## Environment Availability

**Confidence:** HIGH on the tool/framework inventory; depends on Railway env for the 4 new write tokens.

| Dependency | Required By | Available | Version | Fallback |
|---|---|---|---|---|
| tweepy (with [async]) | AsyncClient write path | ✓ | already installed | — |
| anthropic SDK | Sonnet + Haiku calls | ✓ | 0.86.0+ | — |
| PostgreSQL (Neon) | posted_tweets table | ✓ | 16 | — |
| Alembic | migration 0008 | ✓ | 1.14.x | — |
| X_API_CONSUMER_KEY | OAuth 1.0a | ✓ (per CONTEXT) | Railway env | Kill-switch defaults to `"true"` — missing keys = loud WARNING on startup + every post fails noisily |
| X_API_CONSUMER_SECRET | OAuth 1.0a | ✓ (per CONTEXT) | Railway env | same |
| X_API_ACCESS_TOKEN | OAuth 1.0a | ✓ (per CONTEXT) | Railway env | same |
| X_API_ACCESS_TOKEN_SECRET | OAuth 1.0a | ✓ (per CONTEXT) | Railway env | same |
| X Developer App permission | "Read and Write" | ✓ (per CONTEXT) | N/A | if still "Read only", every write returns 403 — matches regeneration-propagation pitfall |
| Railway scheduler service | code deploy | ✓ | N/A | — |
| Vercel frontend | SeniorAgentPage | ✓ | N/A | — |

**Missing with no fallback:** None expected. If any of the 4 OAuth tokens are actually absent in Railway, the kill-switch doesn't protect against partial-set (code might try to instantiate AsyncClient with `None` for access_token and hit a 401, not a clean error). **Plan must verify all 4 present via `_validate_env()` extension at startup and auto-flip kill-switch to `"false"` if any are missing.**

---

## Validation Architecture

**Confidence:** HIGH (pytest already wired in `pyproject.toml` per Phase 01 note).

### Test Framework

| Property | Value |
|---|---|
| Framework | pytest + pytest-asyncio (asyncio_mode=auto per STATE) |
| Config file | `scheduler/pyproject.toml` [tool.pytest.ini_options] — confirmed in STATE |
| Quick run command | `cd scheduler && pytest -x` (stops at first failure) |
| Full suite command | `cd scheduler && pytest` (full run) |
| Frontend quick | `cd frontend && npm run test -- --run` (vitest single-pass) |
| Backend quick | `cd backend && pytest -x` |

### Phase Requirements → Test Map

| Req (CONTEXT topic) | Behavior | Test Type | Command |
|---|---|---|---|
| AUTO-01: kill-switch skips posting | When config `twitter_auto_post_enabled="false"`, no tweepy write calls made | unit (mocked tweepy) | `pytest scheduler/tests/test_twitter_auto_post.py::test_kill_switch_disabled -x` |
| AUTO-02: daily cap 10 enforced | 11th post attempt returns early, logs "daily cap reached" | unit | `pytest scheduler/tests/test_twitter_auto_post.py::test_daily_cap_blocks -x` |
| AUTO-03: 3 candidates drafted in single Sonnet call | One `client.messages.create` invocation produces list of 3 | unit (mock Anthropic) | `pytest scheduler/tests/test_twitter_draft_3.py -x` |
| AUTO-04: shuffle before Haiku | Verify Sonnet output order != Haiku input order (deterministic seed for test) | unit | `pytest scheduler/tests/test_senior_select_best.py::test_shuffle -x` |
| AUTO-05: Senior `select_best_of_n` returns winning candidate by ID | Haiku returns `{"selected_candidate_id": "..."}`, function returns matching dict | unit | `pytest scheduler/tests/test_senior_select_best.py::test_select_by_id -x` |
| AUTO-06: fence-stripping applied | Haiku returns ```` ```json {"..."}``` ````; function still parses | unit | `pytest scheduler/tests/test_senior_select_best.py::test_fence_strip -x` |
| AUTO-07: compliance filter drops non-compliant before Senior | Haiku says FAIL on 1 of 3; Senior only sees 2 | unit | `pytest scheduler/tests/test_twitter_auto_post.py::test_compliance_filter -x` |
| AUTO-08: `posted_tweets` INSERT on success | Mock `create_tweet` returns id; DB row present after run | integration | `pytest scheduler/tests/test_twitter_auto_post_integration.py::test_reply_logged -x` |
| AUTO-09: UNIQUE `tweet_id` catches duplicate | Second INSERT with same tweet_id raises IntegrityError | migration test | `pytest backend/tests/test_migrations.py::test_posted_tweets_unique -x` |
| AUTO-10: retweet error 139 caught | Mock tweepy.Forbidden with api_codes=[139]; run doesn't crash | unit | `pytest scheduler/tests/test_twitter_auto_post.py::test_retweet_already_done -x` |
| AUTO-11: frontend renders posted tweets | SeniorAgentPage renders list from MSW mock | component | `cd frontend && npm run test SeniorAgentPage` |
| AUTO-12: backend `/senior/posted-tweets` endpoint | Returns list, auth required | backend | `pytest backend/tests/test_senior_router.py -x` |

### Sampling Rate

- **Per task commit:** `cd scheduler && pytest scheduler/tests/test_twitter_auto_post.py -x`
- **Per wave merge:** `cd scheduler && pytest && cd ../backend && pytest && cd ../frontend && npm run test -- --run`
- **Phase gate:** Full suite green + manual smoke test via `railway run` before flipping kill-switch to `"true"` in production.

### Wave 0 Gaps

- [ ] `scheduler/tests/test_twitter_auto_post.py` — new file covering AUTO-01, 02, 07, 10
- [ ] `scheduler/tests/test_twitter_draft_3.py` — new file covering AUTO-03
- [ ] `scheduler/tests/test_senior_select_best.py` — new file covering AUTO-04, 05, 06
- [ ] `scheduler/tests/test_twitter_auto_post_integration.py` — new file covering AUTO-08
- [ ] `backend/tests/test_migrations.py` update — AUTO-09 (or verify existing infrastructure)
- [ ] `backend/tests/test_senior_router.py` — new file covering AUTO-12
- [ ] `frontend/src/pages/SeniorAgentPage.test.tsx` — new file covering AUTO-11 (MSW handler + component test)
- [ ] `frontend/src/mocks/handlers.ts` update — add `/senior/posted-tweets` handler

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|---|---|---|---|
| "Nothing is ever posted automatically" (CLAUDE.md v1) | Autonomous Twitter posting with kill-switch + Senior best-of-N | This task (260420-s3b) | CLAUDE.md MUST be updated — see CONTEXT's canonical_refs |
| Claude Haiku 4.5 + bare JSON prompting | Structured Outputs (optional, GA Nov 2025) | Nov 2025 | CONTEXT locks bare JSON + fence-stripping — consistent with existing codebase pattern. Structured Outputs is a future cleanup. |
| X API free-for-all programmatic replies | **Replies blocked unless summoned** | 2026-04-20 (yesterday) | **BLOCKING for task as scoped.** See CRITICAL FINDING. Only Enterprise ($42K+/yr) exempt. |

**Deprecated / outdated in training data:**
- Old Anthropic model names like `claude-3-5-haiku-latest` — deprecated (per pwh commit 3525c47). Use `claude-haiku-4-5` alias.
- tweepy v1 `API` class — v2 uses `Client` / `AsyncClient` only (already correct in project).

---

## Open Questions

1. **Reply restriction workaround (BLOCKING)**
   - What we know: Programmatic replies require original-author mention/quote. All Basic-tier paths rejected.
   - What's unclear: Whether operator accepts Option A (retweet-only), Option B (build-and-fail), or Option C (WhatsApp relay).
   - Recommendation: Surface to operator before planner writes task list. **Do not proceed with reply path** until operator explicitly confirms awareness of the restriction.

2. **"Retweet gate unchanged" — what existing code is being preserved?**
   - What we know: Live `_draft_for_post()` class method drafts reply alternatives only. Legacy module-level `draft_for_post()` drafts both reply + RT-with-comment but is unused by live pipeline.
   - What's unclear: CONTEXT says "Retweet gate logic unchanged (keep existing `_should_retweet` / equivalent)" — no `_should_retweet` exists in the codebase.
   - Recommendation: Planner clarifies — does CONTEXT mean "build a new retweet gate as part of this task" or "there's existing retweet logic I'm missing"? Default to the former.

3. **Route path: `/agents/senior` vs `/senior`**
   - What we know: Current routes are flat (`/twitter`, `/content`, `/digest`). CONTEXT specifies `/agents/senior`.
   - What's unclear: Operator's intent — new `/agents/` prefix convention, or typo.
   - Recommendation: Use `/agents/senior` per CONTEXT (it's a locked decision). Note the inconsistency in the task summary for future cleanup.

4. **Does the `agent_runs.id` FK add value?**
   - What we know: `agent_runs` is a UUID-PK table; FK would link each post to the run that created it.
   - What's unclear: Whether post-hoc analysis actually needs this link, or whether `posted_at` + time-window query is sufficient.
   - Recommendation: Include the FK with `nullable=True` — cheap storage, enables future run-level analysis. If the agent run fails mid-post, `agent_run_id` stays populated from the run record inserted at the top of `_run_pipeline()`.

---

## Code Examples

### Single AsyncClient, read + write together

```python
# scheduler/agents/twitter_agent.py — replace __init__
def __init__(self) -> None:
    settings = get_settings()
    self.tweepy_client = tweepy.asynchronous.AsyncClient(
        bearer_token=settings.x_api_bearer_token,
        consumer_key=settings.x_api_consumer_key,
        consumer_secret=settings.x_api_consumer_secret,
        access_token=settings.x_api_access_token,
        access_token_secret=settings.x_api_access_token_secret,
        wait_on_rate_limit=False,
    )
    self.anthropic = AsyncAnthropic(api_key=settings.anthropic_api_key)
```

### Posting a reply and capturing the tweet ID

```python
# Inside _post_reply() — new method in TwitterAgent
try:
    response = await self.tweepy_client.create_tweet(
        text=selected_draft_text,
        in_reply_to_tweet_id=source_tweet_id,  # str
    )
    posted_tweet_id = response.data["id"]   # dict access, not attribute
    posted_text_actual = response.data["text"]
except tweepy.Forbidden as exc:
    # Could be reply-restriction (new April 2026 rule) or permission issue
    logger.warning(
        "TwitterAgent: create_tweet forbidden for source %s: %s (codes=%s)",
        source_tweet_id, exc, getattr(exc, "api_codes", None),
    )
    return None
except tweepy.TooManyRequests:
    logger.warning("TwitterAgent: rate-limited on create_tweet — deferring to next run")
    return None
```

### Retweeting with 139 handling

```python
try:
    response = await self.tweepy_client.retweet(tweet_id=source_tweet_id)
    # response.data = {"retweeted": True}
    return source_tweet_id  # the retweeted ID — we use this as the posted_tweets.tweet_id
except tweepy.Forbidden as exc:
    if 139 in (getattr(exc, "api_codes", None) or []):
        logger.info("TwitterAgent: already retweeted %s — skipping (benign)", source_tweet_id)
        return None
    logger.warning("TwitterAgent: retweet forbidden for %s: %s", source_tweet_id, exc)
    return None
```

### Fence-stripping preprocess (reuse from content_agent.py:552-564)

```python
# In senior_agent.select_best_of_n() — reuse this pattern verbatim
try:
    raw = message.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.rsplit("```", 1)[0].strip()
    parsed = json.loads(raw)
except (json.JSONDecodeError, ValueError):
    logger.warning("select_best_of_n: non-JSON response — fail-closed (no post)")
    return None
```

### Daily-cap query (UTC midnight reset)

```python
from sqlalchemy import select, func, text

count_result = await session.execute(
    select(func.count())
    .select_from(PostedTweet)
    .where(PostedTweet.posted_at >= text("date_trunc('day', now() at time zone 'UTC')"))
)
posted_today = count_result.scalar_one()
if posted_today >= 10:
    logger.info("TwitterAgent: daily auto-post cap reached (%d/10) — skipping remaining", posted_today)
    return
```

### Idempotency pre-check before posting

```python
# Before retweet — check we didn't already retweet this source
existing = await session.execute(
    select(PostedTweet.id).where(
        PostedTweet.source_tweet_id == source_tweet_id,
        PostedTweet.post_type == "retweet",
    ).limit(1)
)
if existing.scalar_one_or_none() is not None:
    logger.info("TwitterAgent: source %s already retweeted — skipping", source_tweet_id)
    return
```

---

## Sources

### Primary (HIGH confidence)

- tweepy master source code (`tweepy/asynchronous/client.py`) — AsyncClient constructor + `create_tweet`/`retweet` signatures: https://github.com/tweepy/tweepy/blob/master/tweepy/asynchronous/client.py
- tweepy docs (stable 4.14.0) — Client reference, authentication: https://docs.tweepy.org/en/stable/client.html and https://docs.tweepy.org/en/stable/authentication.html
- X Developer announcement — Programmatic reply restriction (Feb 2026, effective April 20 2026): https://devcommunity.x.com/t/update-to-reply-behavior-in-x-api-v2-restricting-programmatic-replies/257909
- @XDevelopers on X — summoned replies pricing at $0.01 (vs $0.20 non-summoned): https://x.com/XDevelopers/status/2044919377544261979
- @XDevelopers on X — reply restriction announcement: https://x.com/XDevelopers/status/2026084506822730185
- X API Rate Limits (official): https://docs.x.com/x-api/fundamentals/rate-limits
- X API Pricing Update (April 20 2026): https://devcommunity.x.com/t/x-api-pricing-update-owned-reads-now-0-001-other-changes-effective-april-20-2026/263025
- Anthropic Structured Outputs announcement (GA for Haiku 4.5 Nov 2025): https://claude.com/blog/structured-outputs-on-the-claude-developer-platform
- Anthropic Haiku 4.5 model page: https://www.anthropic.com/news/claude-haiku-4-5
- Project codebase (full file reads): twitter_agent.py, senior_agent.py, content_agent.py:540-589, config.py, worker.py, models/*, App.tsx, Sidebar.tsx, backend/alembic/versions/0007_add_market_snapshots.py

### Secondary (MEDIUM confidence)

- X API pricing tiers 2026 (TwitterAPI.io, xpoz.ai, elfsight — multiple consistent sources): https://twitterapi.io/blog/twitter-api-pricing-2025 and https://www.xpoz.ai/blog/guides/understanding-twitter-api-pricing-tiers-and-alternatives/
- Claude Haiku 4.5 production quirks (sider.ai): https://sider.ai/blog/ai-tools/claude-haiku-4_5-in-production-surviving-the-quiet-genius-and-its-sneaky-gotchas
- OAuth 1.0a token regeneration propagation (X community forum, multiple reports): https://devcommunity.x.com/t/oauth-token-regeneration/2129
- tweepy discussion on OAuth 1.0a write pathway (#2042): https://github.com/tweepy/tweepy/discussions/2042

### Tertiary (LOW confidence — flagged for planner validation)

- Retweet-already-retweeted returns error 139 specifically — inferred from v1.1 behavior + tweepy error code mapping; v2 explicit documentation absent. Planner should verify in smoke test.
- Retweet rate limit "50 per 15min per user" — from docs.x.com rate-limits page summary; exact endpoint scoping was not fully verified.

---

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — all libraries verified in project, versions confirmed
- Architecture integration points: HIGH — all source files read in full
- X API reply restriction: HIGH — primary source is X's own developer announcement, confirmed by multiple secondary sources
- X API write quotas: HIGH on monthly/daily caps; MEDIUM on exact endpoint-level retweet rate limit
- tweepy signatures and response shapes: HIGH — verified against master source
- Anthropic Haiku 4.5 quirks: HIGH — consistent with pwh commit findings already in this codebase
- Frontend patterns: HIGH — all component files read
- `posted_tweets` schema: HIGH on column set; MEDIUM on UNIQUE index choice (recommended but not load-tested)
- OAuth 1.0a token propagation delay: MEDIUM — anecdotal forum reports, no official docs

**Research date:** 2026-04-21
**Valid until:** 2026-05-21 (30 days — stable APIs; X pricing/policy pages change unpredictably — re-check the reply restriction status if operator defers this task >30 days)
