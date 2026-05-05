# Pitfalls Research

**Domain:** v2.0 Daily Summary Feed — integrating a scheduled daily news summary into an existing news-ingestion system
**Researched:** 2026-05-05
**Confidence:** HIGH (based on direct code inspection of m49/m51-era production files in worker.py, content_agent.py, whatsapp.py)

---

## Critical Pitfalls

### CRIT-1: Duplicate WhatsApp delivery — morning_digest + daily_summary both registered

**What goes wrong:**
`morning_digest` (lock ID 1005, job ID `midday_digest`) is still registered in `worker.py`'s `build_scheduler()` when the new `daily_summary` cron is added. Both jobs fire, both call `send_whatsapp_message`. The user receives two separate messages per fire window. Worse: if `morning_digest` references the old approval-flow pipeline while `daily_summary` references the new `daily_summaries` table, the user sees a duplicate plus a stale message within the same minute.

**Why it happens:**
v2.0 retires `morning_digest` "as dead code, don't strip" — it is natural to add the new cron in a separate commit without removing the old one, especially because the retirement instruction says not to delete code.

**How to avoid:**
In the SAME commit that adds `daily_summary` to `CONTENT_CRON_AGENTS` (or as its own standalone `scheduler.add_job` call), remove the `scheduler.add_job(...)` call for `midday_digest` from `build_scheduler()`. The `_make_midday_digest_job` factory and the `"midday_digest": 1005` dict entry in `JOB_LOCK_IDS` can remain as dead code — but the registration MUST be removed. Test: confirm `len(_scheduler.get_jobs())` in startup logs reflects the new count and no `midday_digest` appears in `_scheduler.get_jobs()`.

**Warning signs:**
Two WhatsApp messages arriving within seconds of each other on the first post-pivot cron fire.

**Phase to address:**
The phase that registers `daily_summary` in `worker.py` — same commit, not a follow-up.

---

### CRIT-2: Advisory lock ID collision — accidental reuse of retired or gap IDs

**What goes wrong:**
`JOB_LOCK_IDS` in `worker.py` uses 1005 (`midday_digest`) and 1010-1016 (six sub-agents). Lock ID 1012 is a gap left by `sub_long_form` retirement. If `daily_summary` or `daily_summary_prune` is assigned 1012 (or any ID currently in the dict), `pg_try_advisory_lock` either silently refuses to acquire when the retired-but-still-registered old job holds the lock, or the two jobs race — producing zero output with no error log. The log message would read `"Job daily_summary: skipped (advisory lock held by another instance)"` with no concurrent instance running.

**Why it happens:**
Advisory locks are bare integers in Postgres — no semantic ownership. A developer scanning the dict and seeing 1012 is unused would naturally fill it.

**How to avoid:**
Reserve IDs 1020 and 1021 explicitly. Add to `JOB_LOCK_IDS`:
```python
"daily_summary": 1020,
"daily_summary_prune": 1021,
# Gap 1017-1019 reserved for future use — do NOT fill without checking production
```
Assert uniqueness at startup: `assert len(set(JOB_LOCK_IDS.values())) == len(JOB_LOCK_IDS)` — this costs nothing and catches collisions immediately.

**Warning signs:**
`Job daily_summary: skipped (advisory lock held by another instance)` appearing at the scheduled fire time with no other scheduler process running.

**Phase to address:**
Phase that creates the `daily_summary` cron registration.

---

### CRIT-3: Multiple summary fires during Railway restart churn — misfire_grace_time interaction

**What goes wrong:**
`build_scheduler()` sets `misfire_grace_time=1800` (30 min) globally. APScheduler fires a coalesced missed run once when the scheduler restarts if the missed fire was within the grace window. With `coalesce=True` and `max_instances=1`, this is correct for a single process lifetime. The danger: Railway occasionally produces a flappy restart sequence (start → crash → start → crash → start) across the 08:00 PT window. Each process restart creates a new scheduler instance. Three restarts within the 30-minute grace window = three scheduler lifetimes = three coalesced fires = three summaries + three WhatsApp messages. The m49 fix (CronTrigger + coalesce) prevents the IntervalTrigger "fire every 10 seconds" pattern but does NOT prevent "fire once per process start if within grace window."

**Why it happens:**
The m49 pattern was validated against a single clean restart. Flappy restarts during a bad Railway deploy expose the per-lifetime coalesce behavior.

**How to avoid:**
Add a database-level idempotency guard in the `daily_summary` agent function, BEFORE writing any row or sending any WhatsApp:
```python
existing = await session.execute(
    select(DailySummary).where(
        DailySummary.fire_time >= now - timedelta(minutes=30),
        DailySummary.status.in_(["running", "complete"]),
    )
)
if existing.scalar_one_or_none():
    logger.info("daily_summary: skipping — recent run already exists within grace window")
    return
```
This mirrors what `reconcile_stale_runs` does for `agent_runs` rows. It is the correct defense for any job where exactly-once semantics matter.

**Warning signs:**
Multiple `daily_summaries` rows with `generated_at` within 5 minutes of each other on the same day. WhatsApp burst of identical summaries.

**Phase to address:**
Phase that writes the `daily_summary` agent run logic.

---

### CRIT-4: fetch_stories() cache contamination — sharing sub-agent scored results with the summary

**What goes wrong:**
`fetch_stories()` caches on `int(time.time() // 1800)`. The `daily_summary` cron fires at 08:00 PT and 12:00 PT. `sub_breaking_news` fires every hour at HH:00 UTC — that is 00:00, 01:00, 02:00, ... 15:00 PT. If `sub_breaking_news` fires at 08:00 UTC (= 01:00 PT) and `daily_summary` fires at 08:00 PT (= 15:00 UTC), they do NOT share a bucket — different 30-minute windows. So the contamination is not from a concurrent hit but from a different concern: the `score` field on cached stories is calibrated for sub-agent approval queue selection (relevance × 0.4, recency × 0.3, credibility × 0.3), and the `predicted_format` label is an artifact for sub-agent content-type routing. If `daily_summary` calls `fetch_stories()` and uses `story['score']` to rank the top 5 gold headlines, it is using approval-queue scores — which are reasonable but subtly wrong for summary ranking (recency matters more for summaries; credibility should be weighted higher).

More importantly: if a sub-agent fires within the same 30-minute bucket as `daily_summary` (e.g., `sub_breaking_news` at HH:00 UTC fires at 15:00 UTC = 08:00 PT on the nose), `daily_summary` will get a cache hit. This is harmless performance-wise but means the summary gets sub-agent-scored stories with `predicted_format` keys that have no meaning in the summary context — and a future developer might accidentally filter on `predicted_format` to get "only breaking news stories," excluding valid summary material.

**How to avoid:**
Do NOT use `fetch_stories()` directly in `daily_summary`. Implement a thin `fetch_stories_for_summary()` wrapper that bypasses the shared bucket cache and uses its own isolated cache key (e.g., `"summary_" + str(bucket)`), or simply calls `_do_fetch()` directly. Strip `predicted_format` from the returned stories before passing to the summary agent — or assert its absence in tests.

**Warning signs:**
Summary cards showing `predicted_format` in `raw_sources_jsonb` JSONB. Sub-agent run logs showing "cache hit" at the same timestamp as a daily_summary fire.

**Phase to address:**
Phase that implements the `daily_summary` agent's gold news ingestion.

---

## High Pitfalls

### HIGH-1: Ontario law filter — false positives from political speech

**What goes wrong:**
A Sonnet prompt asking "Is this a new Ontario mining-favourable law or policy?" returns `keep=True` for: "Ontario Premier announces intention to streamline mining permits" (political intent, no enacted law), "Mining industry welcomes government's pro-development stance" (editorial), "Ontario minister praises mining sector at conference" (speech). None of these are new laws. Over 30 days, the Ontario law section fills with noise and the user stops trusting it.

**Why it happens:**
Without explicit negative examples, Sonnet pattern-matches on "Ontario + mining + positive sentiment" — exactly what the existing `is_gold_relevant_or_systemic_shock` function in `content_agent.py` avoids by including detailed REJECT examples with specific company names and scenarios.

**How to avoid:**
The Ontario law filter prompt MUST include:

Positive examples (KEEP): "Bill 71, Building Ontario Act, amends Mining Act s.XX effective Jan 1 2026" — "Ontario Regulation 123/26 reduces royalty rates for junior explorers, effective April 2026"

Negative examples (REJECT): "Premier says Ontario is open for business" (intent, not law) — "Mining association praises new policy direction" (industry reaction) — "Ontario government studying changes to permitting" (study, not enacted) — "Government announces consultation on mining reform" (pre-legislative)

Require: the article must mention a specific bill number, regulation number, or enacted/effective date to qualify. Return structured JSON: `{"is_law": bool, "bill_or_reg_number": str|null, "reason": str}` for auditability.

Pass the article BODY (first 1500 chars via the existing `fetch_article()` in `content_agent.py`), not just headline + snippet.

**Warning signs:**
Ontario law section averaging more than 1 article per 3 days in the first two weeks — that rate is too high for enacted Ontario mining law.

**Phase to address:**
Phase that implements Ontario law ingestion + Sonnet filter.

---

### HIGH-2: Ontario law filter — false negatives on bills with opaque names

**What goes wrong:**
"Bill 71, the Building Ontario Act, 2026" amends the Mining Act in section 47. The bill name does not say "mining." A headline-only filter rejects this. This is the highest-value signal for the Ontario law section — the cross-domain legislative change the user most wants surfaced — and it disappears silently.

**Why it happens:**
The existing `is_gold_relevant_or_systemic_shock` function explicitly avoids this by checking `title + summary`, not title alone. An Ontario law filter built hastily from the headline would make the same mistake.

**How to avoid:**
Pass the full article body (first 1500 chars) to the Ontario law filter. If `fetch_article()` returns `success=False`, fall back to headline + snippet — do not discard. Add to the filter prompt: "Search the article body for references to: Mining Act, Mineral Tenure Act, Ontario Geological Survey Act, Aggregate Resources Act, Crown lands, royalty, exploration permit, or staking regulation."

Synthetic test: pass "Building Ontario Act amends Mining Act" — confirm `is_law=True`. This test case must be in the test suite before merge.

**Warning signs:**
Zero Ontario law hits in a month when the Ontario legislature was actively in session (Ontario Hansard is publicly searchable — verify against it).

**Phase to address:**
Phase that implements Ontario law ingestion + Sonnet filter.

---

### HIGH-3: Prune-vs-read race — frontend 404 on a just-deleted row

**What goes wrong:**
The `daily_summary_prune` cron runs `DELETE FROM daily_summaries WHERE generated_at < NOW() - INTERVAL '30 days'`. Simultaneously, the feed page has rendered a card. The user clicks the card to view the detail route `GET /summaries/{id}`. If the row was deleted between the list render and the detail fetch, the API returns 404. Neon PgBouncer in transaction mode handles MVCC correctly (reads see a consistent snapshot), so the race is not a data integrity issue — it is a UX issue.

**Why it happens:**
Prune crons are typically implemented as simple DELETEs without considering in-flight frontend requests against just-pruned rows.

**How to avoid:**
Two-part mitigation:
1. Frontend: `GET /summaries/{id}` returning 404 must produce "This summary is no longer available" toast + auto-redirect to `/`, not an unhandled error screen.
2. Backend: consider soft delete — add a `pruned_at TIMESTAMP` column; the prune cron sets it instead of hard-deleting; the feed query filters `WHERE pruned_at IS NULL`; an optional weekly hard-delete batch runs during low-traffic hours.

Additionally: Neon PgBouncer in transaction mode routes each statement to potentially a different backend connection. Advisory locks acquired in one statement do NOT persist to the next statement in the same "logical session." The prune cron MUST acquire and release its advisory lock within the same `engine.connect()` context (which `with_advisory_lock` already does correctly) — do not attempt to hold the lock across a disconnection.

**Warning signs:**
Frontend 404 errors in browser console appearing at predictable clock times (around the prune cron schedule). Visible in Railway API access logs as `GET /summaries/{id} 404` in bursts.

**Phase to address:**
Phase that implements the 30-day prune cron + `GET /summaries/{id}` detail endpoint.

---

### HIGH-4: JSONB schema drift on raw_sources_jsonb — no validation gate

**What goes wrong:**
`raw_sources_jsonb` on `daily_summaries` stores article URLs + headlines per section. Future shape changes (rename `url` to `link`, add `published_date`, add `section` discriminator) are not caught by Alembic migrations — Postgres JSONB has no column-level schema enforcement. A phase-3 change renames a key; the phase-1 read query silently returns `None` for every affected field. The breakage reaches production because there is no migration gate to enforce the change.

**Why it happens:**
The existing codebase uses JSONB for `draft_items.alternatives` with no Pydantic model validating the output shape — a developer extending that pattern to `raw_sources_jsonb` would naturally skip the validation layer.

**How to avoid:**
Define and use a Pydantic model on write:
```python
class RawSource(BaseModel):
    url: str
    headline: str
    section: Literal["gold_news", "ontario_law", "ontario_stats"]
    published_date: datetime | None = None

class DailySummaryRawSources(BaseModel):
    sources: list[RawSource]
```
The `daily_summary` agent writes: `raw_sources=DailySummaryRawSources(sources=[...]).model_dump()`. The `GET /summaries/{id}` endpoint validates on read using the same model. Any future schema change requires updating the Pydantic model — that is a code change surfaced in review, not a silent JSONB mutation.

**Warning signs:**
Frontend showing empty source lists or `undefined` for source fields after a backend change that touched the summary writer.

**Phase to address:**
Phase that creates the `daily_summaries` table migration.

---

### HIGH-5: WhatsApp message length — 3-section summary exceeds 1600 chars

**What goes wrong:**
Twilio's hard limit is 1600 characters per message. A 3-section summary with 5 gold headlines + 2 Ontario law hits + 1 Ontario stats note easily reaches 1200-2500 characters. The existing `build_chunks()` in `whatsapp.py` handles chunking at a 1500-char safety margin, but it was designed for numbered draft-item lists. A 3-section summary chunked mid-section produces incoherent messages — the gold section header appears in message 1, the gold bullets split across messages 1 and 2.

**Why it happens:**
`send_agent_run_notification` and `build_chunks` were designed for the approval-flow firehose. v2.0's summary has structured sections that do not fit the item-list chunking pattern.

**How to avoid:**
Do NOT use `build_chunks` for `daily_summary` WhatsApp delivery. Instead, send a teaser message that links to the web feed:
```
Summary as of 08:00 PT — 2026-05-05
• Gold: 5 stories (markets up 0.8% on tariff news)
• Ontario law: 1 update
• Ontario stats: no new data
Full summary: https://seva-mining-smm.vercel.app/
```
This fits under 300 characters, never chunks, and is the correct architecture — the web feed is the primary surface; WhatsApp is the notification. Log `len(teaser_message)` on every send and assert < 400 chars.

**Warning signs:**
WhatsApp messages arriving as `[daily_summary 1/3]`, `[daily_summary 2/3]`, `[daily_summary 3/3]` — technically correct but signals the wrong design choice.

**Phase to address:**
Phase that implements WhatsApp delivery for `daily_summary`.

---

### HIGH-6: Anthropic cost overrun — using Sonnet for the Ontario law relevance filter

**What goes wrong:**
If the Ontario law filter uses `claude-sonnet-4-6` (the model used in `_score_relevance` in `content_agent.py`), the cost calculation is: ~30 Ontario articles × Sonnet × 2 fires/day × 30 days ≈ 1800 Sonnet calls/month for the Ontario law filter alone. Combined with gold news scoring (~120 articles × 2 fires/day = 7200 calls/month) and 2 summary write calls/day, total Anthropic spend exceeds the $30-50 AI budget.

**Why it happens:**
`content_agent.py` uses `claude-sonnet-4-6` for `_score_relevance` — a developer extending that pattern to the Ontario law filter would naturally reach for the same model without recalculating the cost at new call volume.

**How to avoid:**
Ontario law relevance filter: use `claude-haiku-4-5` — the same model as `classify_format_lightweight` and the gold gate `is_gold_relevant_or_systemic_shock` (which defaults to `config.get("content_gold_gate_model", "claude-haiku-4-5")`). Only the final summary WRITE call (one per fire) should use Sonnet.

Budget estimate with Haiku for filtering:
- ~30 Ontario articles × Haiku × 2/day × 30 days ≈ $5/month
- ~120 gold articles × Haiku × 2/day × 30 days ≈ $20/month
- 2 Sonnet summary writes/day × 30 days ≈ $2/month
- Total ≈ $27/month — within the $30-50 budget with headroom

Make the filter model configurable: `ontario_law_filter_model` DB config key defaulting to `"claude-haiku-4-5"`, matching the pattern of `content_gold_gate_model`.

**Warning signs:**
Anthropic dashboard showing unexpectedly high Sonnet usage from the scheduler service starting after v2.0 deploy.

**Phase to address:**
Phase that implements the Ontario law ingestion + relevance filter.

---

## Moderate Pitfalls

### MOD-1: DST transitions — 08:00 and 12:00 PT are safe, but document why

**What goes wrong:**
Nothing — these specific times are safe. APScheduler with `timezone='America/Los_Angeles'` handles DST correctly. The 08:00 and 12:00 fire times do not fall in the ambiguous 01:00-02:00 window during fall-back. However, if the fire times are ever changed in a future sprint, a developer might not know that times between 01:00-02:00 PT are problematic.

**How to avoid:**
Add a comment at the CronTrigger registration:
```python
CronTrigger(hour=8, minute=0, timezone="America/Los_Angeles")
# 08:00 PT is outside the DST-ambiguous 01:00-02:00 window.
# If you change this time, verify the new time is not 01:00-02:00 PT.
```
No additional code needed — the CronTrigger handles spring-forward and fall-back automatically.

**Warning signs:**
Missing or duplicate fire on the first Sunday in November or second Sunday in March. Check the `daily_summaries` table on those dates.

**Phase to address:**
Phase that creates the `daily_summary` CronTrigger registration.

---

### MOD-2: Alembic migration 0010 — accidentally touching the ApprovalState enum

**What goes wrong:**
Migration 0010 adds the `daily_summaries` table. If Alembic autogenerate is used (`alembic revision --autogenerate`), it compares ALL models to the current DB state. If any model drift exists in the `ApprovalState` enum (defined in migration 0009), autogenerate emits spurious `op.execute("CREATE TYPE ...")` or `op.alter_column` DDL. Postgres enums are notoriously difficult to modify post-creation — a failed migration on an enum in production can leave the database in a partial state requiring manual repair.

**Why it happens:**
Alembic autogenerate is convenient but inspects every model, not just the changed one. It is easy to run `--autogenerate` without reviewing the generated diff carefully.

**How to avoid:**
Write migration 0010 by hand: `alembic revision -m "add_daily_summaries"` (no `--autogenerate`). The migration body should contain ONLY:
1. `op.create_table("daily_summaries", ...)`
2. `op.create_index(...)` on `generated_at` (needed for the prune `WHERE generated_at < NOW() - INTERVAL '30 days'` query)

Review the migration file before running `alembic upgrade head` in production. Confirm the file contains no `op.execute` statements referencing `approvalstate` or any existing enum type.

**Warning signs:**
Migration 0010's `upgrade()` function contains `CREATE TYPE` or `ALTER TYPE` DDL referencing `approvalstate`.

**Phase to address:**
Phase that creates the `daily_summaries` table migration.

---

### MOD-3: SerpAPI quota — daily_summary fires are cache-cold by design

**What goes wrong:**
`fetch_stories()` caches on a 30-minute bucket. In v1.0, `sub_breaking_news` fires every hour — the cache was warm for most of the day, amortizing SerpAPI calls across many hits. With v2.0 retiring those sub-agents, only `daily_summary` calls the ingestion — at 08:00 and 12:00 PT, 4 hours apart. Each fire is a fresh full ingestion: 17 `SERPAPI_KEYWORDS` × 5 results each = 85 SerpAPI searches. Two fires/day × 30 days = 60 full ingestions/month, ~5,100 search result fetches/month.

The $50/mo SerpAPI plan provides approximately 5,000-6,000 searches/month depending on tier. This is right at the limit with minimal headroom.

**How to avoid:**
Reduce `SERPAPI_KEYWORDS` from 17 to 10 for the summary use case. The sub-agents needed broad coverage for format diversity (infographics needed different signals than threads). The summary only needs the top gold + macro stories. A `SUMMARY_SERPAPI_KEYWORDS` constant with the 10 highest-signal keywords avoids modifying the existing `SERPAPI_KEYWORDS` constant (which should remain in place for any future sub-agent resurrection).

Verify the SerpAPI plan quota in the dashboard before v2.0 go-live.

**Warning signs:**
SerpAPI returning empty results or 429 errors in Railway logs after day 15-20 of the month.

**Phase to address:**
Phase that implements the `daily_summary` agent's gold news ingestion.

---

### MOD-4: Stale TanStack Query cache — new summary not appearing while tab is open

**What goes wrong:**
TanStack Query's default stale time is 0ms — it refetches on every mount. But the feed component is mounted once when the user opens the page. If the 12:00 PT summary fires while the tab is open (user opened it after the 08:00 summary), the new summary does not appear until the user navigates away and back. The data is stale in the query cache but no refetch fires while the component is mounted.

**How to avoid:**
Set `refetchInterval: 5 * 60 * 1000` on the `useSummaries()` hook. This is safe — `GET /summaries` is a lightweight `SELECT * FROM daily_summaries ORDER BY generated_at DESC LIMIT 30`. When the refetch detects a new `id` or `generated_at` that wasn't in the previous result, show a "New summary available" banner prompting the user to scroll to the top.

**Warning signs:**
User reports "I don't see the 12:00 summary until I hard-refresh the page."

**Phase to address:**
Phase that implements the web feed frontend.

---

### MOD-5: Hallucinated dates in Sonnet summary output

**What goes wrong:**
When Sonnet writes the summary narrative, it may produce "The Bank of Canada raised rates in March 2025" when the article is from March 2024. For the Ontario stats section, Sonnet might write "as of Q1 2025" when the most recent StatCan release is Q3 2024. This is a known Sonnet pattern — it anchors to training data rather than the article's stated date.

**Why it happens:**
Sonnet is prompted to write a narrative but is not explicitly grounded to each article's `published_date`.

**How to avoid:**
Include `published_date` in every article passed to the summary write prompt. Add an explicit instruction:
```
For every factual claim in your summary, use ONLY dates explicitly stated in the provided articles.
Do NOT infer, estimate, or use training knowledge for dates.
If an article does not include a date, write "recently" rather than inventing a date.
```
Post-process: scan the output for 4-digit years outside the range `[current_year - 1, current_year]` and log a WARNING if found — do not send a summary containing dates from 3+ years ago without review.

**Warning signs:**
Summary cards showing dates 1-2 years in the past for what were presented as current news articles.

**Phase to address:**
Phase that implements the Sonnet summary write prompt.

---

### MOD-6: Failure alert deadlock — WhatsApp send failure during summary failure

**What goes wrong:**
If `daily_summary` fails AND the failure-alert WhatsApp send also fails (Twilio sandbox session expired, credentials rotated), `send_whatsapp_message` raises `TwilioRestException` after one retry. If the failure-alert call is made inline in the `daily_summary` job function, the `TwilioRestException` propagates up to `with_advisory_lock`, which catches it (EXEC-04 — worker must survive), logs it, and releases the lock. The original error is lost. The user never learns the summary failed.

**Why it happens:**
The natural pattern is `try: run_summary() except: send_failure_alert()` — but this does not protect against the alert itself failing.

**How to avoid:**
Wrap the failure alert send in its own try/except that NEVER re-raises:
```python
try:
    await send_whatsapp_message(
        f"SUMMARY FAILED: {section_name} — {type(original_exc).__name__}: {str(original_exc)[:200]}"
    )
except Exception as alert_exc:
    logger.error(
        "daily_summary failure alert ALSO failed (%s) — original error was: %s. "
        "Check Railway logs at %s.",
        type(alert_exc).__name__,
        original_exc,
        datetime.now(timezone.utc).isoformat(),
    )
    # Do not re-raise — EXEC-04
```
The alert message MUST include which section failed (gold_news / ontario_law / ontario_stats), the error type, and a timestamp so the user can locate the Railway log entry.

**Warning signs:**
A `daily_summaries` row with `status='failed'` in the DB and no corresponding WhatsApp notification received on that date.

**Phase to address:**
Phase that implements the WhatsApp failure-alert hook for `daily_summary`.

---

## Minor Pitfalls

### MIN-1: Markdown XSS — rendering Claude output without sanitization

**What goes wrong:**
Sonnet returns markdown. If the frontend renders it with `dangerouslySetInnerHTML` or an unsanitized renderer, a `<script>` tag in the Sonnet output creates an XSS vector. Probability is low (Sonnet does not typically emit script tags in summaries), but it is a trivially-preventable class of vulnerability.

**How to avoid:**
Use `react-markdown` (which rejects `<script>` tags by default) with `allowedElements` explicitly set to `['p', 'ul', 'ol', 'li', 'strong', 'em', 'a', 'h3', 'h4', 'blockquote']`. Never use `dangerouslySetInnerHTML` on LLM output.

**Phase to address:**
Phase that implements the web feed frontend rendering.

---

### MIN-2: Ontario stats empty-state indistinguishable from ingestion failure

**What goes wrong:**
Ontario stats (StatCan / OGS) release monthly or quarterly. Most daily fires produce no new stats — this is expected. If the empty state renders as a blank section or a generic "No data" message, the user cannot distinguish "no new stats released this month" (correct) from "the stats ingestion is broken" (problem). After weeks of correct empty states, the user stops noticing — and when the ingestion actually breaks, it looks the same.

**How to avoid:**
Two distinct states persisted in the `daily_summaries` row:
1. `ontario_stats_status = "no_new_data"` + `ontario_stats_last_data_date = <date>` → render: "No new Ontario stats since 2026-04-01"
2. `ontario_stats_status = "error"` → render: "Ontario stats unavailable — check agent logs" (distinct visual treatment, links to `/settings/agent-runs`)

The `last_data_date` should be a column on `daily_summaries`, not inferred by querying previous rows — querying previous rows is fragile when the prune cron runs.

**Phase to address:**
Phase that implements the Ontario stats section + empty-state design.

---

### MIN-3: Frontend route /queue bookmark breaks on pivot day

**What goes wrong:**
The old `/queue` route was the primary URL used by the user. After v2.0 replaces it with `/`, any browser bookmark pointing to `/queue` returns a 404 — a bad first impression on the first open after deploy.

**How to avoid:**
Add a React Router redirect: `<Route path="/queue" element={<Navigate to="/" replace />} />`. Include it in the phase that ships the new feed page. Add a `// TODO: remove after 2026-07-05` comment. Remove after 60 days.

**Phase to address:**
Phase that implements the web feed frontend.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Retire sub-agents as dead code (not stripped) | Fast pivot, no regression risk on retired code | Tests for retired sub-agents keep passing; dead code accumulates; cognitive overhead | Acceptable for v2.0; strip in v2.1 after 30 days confidence |
| No Pydantic model for JSONB raw_sources_jsonb | One less abstraction layer | Silent schema drift; breaks go undetected until production shows empty fields | Never for fields read by the frontend |
| WhatsApp teaser-only message (no full content) | Constant message size, zero chunking logic | User cannot read summary content offline — must open web feed | Acceptable — web feed is the primary surface |
| Single misfire_grace_time=1800 for all jobs | Simple global config, reuses m49 pattern | daily_summary and prune cron have different recovery needs; prune should NOT fire multiple times in a restart burst | Use DB-level idempotency guard (CRIT-3) as defense-in-depth |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Twilio Sandbox | Sandbox session expires if user has not sent a message in 24h; `send_whatsapp_message` returns `None` (credentials present, but session lapsed) — success looks the same as failure | Move to production Twilio sender before v2.0 go-live; sandbox is correct for local dev only |
| Neon PgBouncer (transaction mode) | Using `pg_try_advisory_lock` and expecting it to persist across multiple statements — PgBouncer routes each statement to potentially a different backend connection | Advisory locks work when acquired and released within a single `engine.connect()` context — which `with_advisory_lock` already does correctly; prune cron must use the same pattern |
| APScheduler + asyncio Python 3.12+ | Calling `asyncio.get_event_loop()` inside an async job function — deprecated in Python 3.10+, raises DeprecationWarning in 3.12 | Use `asyncio.get_running_loop()` inside async job functions; `_do_fetch` in `content_agent.py` uses `get_event_loop()` — new daily_summary code should use `get_running_loop()` |
| SerpAPI in async context | Calling `serpapi_client.search()` synchronously inside an async function without `run_in_executor` — blocks the event loop | Use `loop.run_in_executor(None, _call)` pattern from `_fetch_all_serpapi` |

---

## "Looks Done But Isn't" Checklist

- [ ] **Dual registration removed:** Startup logs show `midday_digest` is absent from `_scheduler.get_jobs()` output
- [ ] **Advisory lock uniqueness:** `assert len(set(JOB_LOCK_IDS.values())) == len(JOB_LOCK_IDS)` passes at startup; daily_summary=1020, daily_summary_prune=1021
- [ ] **WhatsApp teaser length:** `len(teaser_message)` logged and confirmed < 400 chars on first real fire
- [ ] **Ontario law filter has negative examples:** Prompt string reviewed and confirmed to contain at least one REJECT example before merge
- [ ] **Ontario law filter uses Haiku:** Model config key confirmed as `claude-haiku-4-5`; not `claude-sonnet-4-6`
- [ ] **JSONB Pydantic model validates on write:** Unit test: write a malformed `RawSource` — confirm `ValidationError` raised
- [ ] **DB-level idempotency guard:** `daily_summary` agent queries for recent rows before writing; unit test simulates two concurrent fires
- [ ] **Prune 404 handled gracefully:** Frontend shows "no longer available" message on `GET /summaries/{id}` 404 — not an error screen
- [ ] **Ontario stats shows last_data_date:** Empty-state component renders a specific date string, not just "No data"
- [ ] **`/queue` redirect in place:** Browser navigation to `/queue` redirects to `/` with 301

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| CRIT-1: Duplicate WhatsApp dual registration | Phase that registers `daily_summary` cron | `midday_digest` absent from `get_jobs()` at startup |
| CRIT-2: Advisory lock ID collision | Phase that registers `daily_summary` cron | Lock ID uniqueness assertion passes; 1020 and 1021 assigned |
| CRIT-3: Multiple fires on Railway restart | Phase that writes `daily_summary` agent logic | Integration test: two scheduler starts 5 min apart → one `daily_summaries` row |
| CRIT-4: fetch_stories() cache contamination | Phase that implements gold news ingestion for summary | Unit test: summary story list has no `predicted_format` keys |
| HIGH-1: Ontario law false positives | Phase that implements Ontario law filter | Manual review: first week's Ontario law section has zero political-speech articles |
| HIGH-2: Ontario law false negatives | Phase that implements Ontario law filter | Synthetic test: "Building Ontario Act amends Mining Act" → `is_law=True` |
| HIGH-3: Prune-vs-read race | Phase that implements prune cron + detail endpoint | Frontend handles `GET /summaries/{id}` 404 with redirect |
| HIGH-4: JSONB schema drift | Phase that creates `daily_summaries` migration | `RawSource` Pydantic model exists and used in writer |
| HIGH-5: WhatsApp >1600 chars | Phase that implements WhatsApp delivery | `len(teaser_message)` asserted < 400 on send |
| HIGH-6: Anthropic cost (Sonnet for filtering) | Phase that implements Ontario law filter | Filter model confirmed as `claude-haiku-4-5` |
| MOD-2: Alembic enum collision | Phase that creates `daily_summaries` migration | Migration 0010 contains no `CREATE TYPE` / `ALTER TYPE` referencing `approvalstate` |
| MOD-3: SerpAPI quota | Phase that implements gold news ingestion | `SUMMARY_SERPAPI_KEYWORDS` ≤ 10 keywords |
| MOD-5: Hallucinated dates | Phase that implements Sonnet summary write prompt | Prompt contains date-grounding instruction; post-process warns on out-of-range years |
| MOD-6: Failure alert deadlock | Phase that implements WhatsApp failure-alert hook | Alert send wrapped in its own try/except; original error preserved in log |

---

## Sources

- Direct code inspection: `/Users/matthewnelson/seva-mining/scheduler/worker.py` — JOB_LOCK_IDS (1005, 1010-1016), misfire_grace_time=1800, coalesce=True, max_instances=1, CronTrigger pattern, reconcile_stale_runs implementation
- Direct code inspection: `/Users/matthewnelson/seva-mining/scheduler/agents/content_agent.py` — _CACHE_LOCK held microseconds only, coalesce pattern via _FETCH_IN_FLIGHT Future, cache bucket = `int(time.time() // 1800)`, parallel scoring via asyncio.gather, Sonnet model = `claude-sonnet-4-6`, Haiku model = `claude-haiku-4-5` for is_gold_relevant_or_systemic_shock
- Direct code inspection: `/Users/matthewnelson/seva-mining/scheduler/services/whatsapp.py` — 1500-char safety margin in build_chunks, single-retry pattern, graceful skip on missing credentials returning None
- `.planning/PROJECT.md` — v2.0 milestone spec, Ontario law/stats hard parts, stack contract, lock ID history
- Neon PgBouncer transaction-mode behavior: advisory locks require session-mode connection to persist across statements (documented in Neon connection pooling docs)
- APScheduler 3.x coalesce + misfire_grace_time behavior: fires once per missed window within a single scheduler instance lifetime — new process start = new scheduler instance

---
*Pitfalls research for: v2.0 Daily Summary Feed (seva-mining)*
*Researched: 2026-05-05*
