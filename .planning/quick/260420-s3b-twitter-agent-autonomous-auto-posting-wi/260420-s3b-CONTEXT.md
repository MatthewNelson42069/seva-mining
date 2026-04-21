# Quick Task 260420-s3b: Twitter Agent Autonomous Auto-Posting — Context

**Gathered:** 2026-04-21
**Status:** CANCELLED — scope pivoted

## Cancellation Notice (2026-04-21)

This task was cancelled before planning/execution. Two blocking findings from the research phase drove the pivot:

1. **X API restricted programmatic replies on 2026-04-20** (day before research). Every `create_tweet(in_reply_to_tweet_id=...)` targeting non-summoning accounts returns 403. Full finding preserved in `260420-s3b-RESEARCH.md` section "⚠️ CRITICAL FINDING".
2. **Operator decision:** Rather than reduce scope to retweet-only (which felt heavy for the expected output), user elected to **delete the Twitter agent entirely** and focus the system on Content agent only.

Follow-up task: full purge of Twitter agent (modeled after Instagram purge 260419-lvy) + trim Senior agent to "morning digest over content_bundles" only. See `.planning/quick/` for the new task directory.

Valuable research findings from this task (tweepy single-client OAuth 1.0a pattern, X API Basic write quotas, Haiku position-bias mitigation, Structured Outputs GA, fence-stripping lessons) remain useful if Twitter writing is ever re-scoped — preserved in `260420-s3b-RESEARCH.md`.

---

<domain>
## Task Boundary

Convert Twitter agent from manual-approval to autonomous auto-posting. Specifically:

- Pull top-2 qualifying tweets per run (ranked by existing score).
- For each of those 2 tweets: draft **3 reply alternatives**, Haiku compliance filter drops non-compliant ones, Senior agent's new `select_best_of_n()` function picks the best compliant candidate, tweepy OAuth 1.0a user-context client posts as a reply.
- Retweet gate logic unchanged (keep existing `_should_retweet` / equivalent).
- Combined reply + retweet cap = **10 posts/day** (UTC midnight reset).
- Kill-switch: `config.twitter_auto_post_enabled = "true" | "false"` (default `"true"`). `"false"` → skip posting entirely, log the disable.
- New `posted_tweets` audit table captures every live post.
- New frontend **Senior Agent** activity tab shows the log (posts-already-live, not a draft queue).
- Content agent (threads, long_form, quote, breaking_news, infographic, video_clip) is **untouched** — manual approval preserved.

This reverses the original CLAUDE.md principle "Nothing is ever posted automatically." CLAUDE.md must be updated as part of the task.

**Operator has explicitly authorized this pivot.** (User is project owner, single-operator system.)
</domain>

<decisions>
## Implementation Decisions

### 3-candidate generation method

- **DECISION: Single Sonnet call returning a 3-item JSON array.**
- Prompt asks for 3 distinct angles (e.g., "generate 3 reply alternatives, each taking a different angle — one with a data-point, one with a counter-view, one as a question/hook").
- Expected cost: ~$0.01/tweet × 2 tweets/run × ~8 runs/day ≈ $0.16/day ≈ $5/mo.
- Rationale: Diversity comes from prompt framing — Sonnet is capable enough to produce 3 distinct angles in one shot without needing 3× the API spend. If diversity turns out to be insufficient in practice (e.g., 3 candidates are near-duplicates), revisit with a `--full` follow-up task to add temperature variance.

### Senior position-bias mitigation (Claude's Discretion)

- **DECISION: Shuffle the 3 candidates before passing them to Haiku.** Candidates are tagged with a stable UUID for traceability (so the rationale field still references the right one), but their position in the Haiku prompt is randomized.
- Rationale: LLM-as-judge has well-documented position bias toward index 0. Shuffling is the cheapest, most reliable mitigation. No ongoing monitoring required.
- Record both `presented_order` (shuffled order Haiku saw) and `selected_candidate_id` in `posted_tweets` → enables post-hoc analysis of whether bias persists despite shuffling.

### Daily-cap race condition (Claude's Discretion)

- **DECISION: Accept small overshoot risk (strict-serial check, no advisory lock).** Check `SELECT COUNT(*) FROM posted_tweets WHERE posted_at >= date_trunc('day', now() at time zone 'UTC')` immediately before each post. Gate on `< 10`.
- Rationale: **Only `twitter_agent` writes to `posted_tweets` — content_agent is out of scope for this task and continues to use the existing manual-approval `draft_items` flow.** Retweet + reply loops within a single twitter_agent run are serial inside the same Python event loop — no real concurrency. Worst-case: twitter_agent cron fires twice within seconds (e.g., after a Railway restart), both read count=9, both post → 11. X API has its own user-level rate limit (~500/mo default), so defense-in-depth is built in. Advisory lock adds complexity without real-world benefit at this scale.

### Kill-switch check timing (Claude's Discretion)

- **DECISION: Check once at start of `_run_pipeline()`, cache for the run.**
- Rationale: "Instant disable" means "no redeploy, just flip the bool." A 30-minute delay to next cron cycle for the flip to take effect is acceptable — the concern is not sub-second response, it's avoiding deploy roll. Checking per-post adds N DB round-trips with no meaningful safety gain (if the user flips mid-run, the worst case is 1-2 more posts before the next cycle picks up the new value). Single check + cache is simpler and still honors the operator intent.
</decisions>

<specifics>
## Specific Ideas

- **4 OAuth 1.0a tokens already provisioned in Railway scheduler env:** `X_API_CONSUMER_KEY`, `X_API_CONSUMER_SECRET`, `X_API_ACCESS_TOKEN`, `X_API_ACCESS_TOKEN_SECRET` (verified via Railway dashboard screenshot). Read-only Bearer token `X_API_BEARER_TOKEN` remains in place for read operations (unchanged client).
- **X Developer app permission:** Set to "Read and Write" (per operator). Access tokens were regenerated post-permission-flip (standard footgun). Final live-post verification will catch any 403 if tokens are still read-only despite flip.
- **anthropic model:** `claude-haiku-4-5` for both compliance check (existing) and new `select_best_of_n()`. Matches pwh task's verified alias. Sonnet (`claude-sonnet-4-5`) stays for the 3-candidate drafting.
- **Fence-stripping pattern:** Reuse the preprocess from `content_agent.py:558-566` (established in pwh commit `3525c47`) — Haiku 4.5 wraps JSON in ```` ```json ... ``` ```` fences. Applies to Senior's JSON response too.
- **Fail-closed policy:** every skip path emits a distinctive log line. No silent fall-through. (Lesson from pwh: silent fail-open = silent feature disable.)
- **Naming:**
  - Config key: `twitter_auto_post_enabled` (stored as string `"true"` | `"false"` per existing `config` table convention)
  - Env vars: `X_API_CONSUMER_KEY`, `X_API_CONSUMER_SECRET`, `X_API_ACCESS_TOKEN`, `X_API_ACCESS_TOKEN_SECRET` (confirmed)
  - Table: `posted_tweets`
  - Frontend route: `/agents/senior` (matches existing `/agents/*` convention per CLAUDE.md update note)
</specifics>

<canonical_refs>
## Canonical References

- **CLAUDE.md** — project charter; MUST be updated at end of task to reflect auto-posting pivot:
  - Remove "Nothing is ever posted automatically"
  - Remove "Auto-posting | Never implement" row from "What NOT to Use"
  - Update X API constraint from "read-only" to "read + write (OAuth 1.0a user-context for Twitter agent auto-posting)"
  - Add note: "Twitter agent posts autonomously (replies + retweets, 10/day combined cap, Senior-agent best-of-3 selection, kill-switch via config table). Content agent remains manual-approval."
- **pwh commits** (`87878e1` / `50720f1` / `3525c47`) — `claude-haiku-4-5` alias + fence-stripping pattern
- **.planning/STATE.md** — current project state (post-r18)
- **Existing `posted_tweets` pattern:** none — this is a new table. Model after `content_bundles` for ORM style.
- **Existing `_run_pipeline` structure:** `scheduler/agents/twitter_agent.py` — preserve overall shape; add pre-draft ranking cap + post-draft Senior selection + post step + audit-log INSERT.
- **Frontend existing pattern:** `frontend/src/pages/` or `frontend/src/components/queue/*` — Senior Agent activity tab follows the same TanStack Query + apiFetch + Tailwind layout convention. Distinct from queue: this is a read-only log, not approval-gated.
</canonical_refs>
