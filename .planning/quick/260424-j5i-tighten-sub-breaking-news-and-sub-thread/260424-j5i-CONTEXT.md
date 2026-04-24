# Quick Task 260424-j5i: Tighten sub_breaking_news + sub_threads to "top-of-top" — Context

**Gathered:** 2026-04-24
**Status:** Ready for planning

<domain>
## Task Boundary

Tighten story selection for `sub_breaking_news` and `sub_threads` so the per-run firehose WhatsApp messages (just shipped in i8b) carry only the highest-signal gold + critical-minerals coverage. Currently both agents approve-for-drafting every story passing the Haiku gate + compliance — quality filtering is happening at the gate layer (binary yes/no), not at the selection layer (best-of-N).

User quote driving this: *"Breaking news and thread should be the top of the top news stories regarding gold and general critical mineral development. Most recent, most relevant, the best stories."*

**Applies ONLY to:** breaking_news + threads. Other 4 sub-agents (quotes, infographics, gold_media, gold_history) have their own selection logic and are out-of-scope.

### Recon summary (grounded in real code, not assumed)
- `scheduler/agents/content/breaking_news.py:125-129` — calls `run_text_story_cycle(agent_name, content_type, draft_fn)` with NO `max_count`, NO `sort_by`. Approves everything.
- `scheduler/agents/content/threads.py:122-127` — calls `run_text_story_cycle(..., max_count=2)` (no `sort_by`). Top 2 by RECENCY, not composite quality.
- `scheduler/agents/content/infographics.py:359-364` — already uses `max_count=2, sort_by="score"`. This is the pattern we propagate to breaking_news + threads.
- `scheduler/agents/content_agent.py:144-158` — composite score = `(relevance × 0.4 + recency × 0.3 + credibility × 0.3) × 10`, scaled 0-10. Every story already carries this score; breaking_news/threads just don't sort on it.
- `scheduler/agents/content_agent.py:111-129` — `recency_score`: 5-bucket curve <3h=1.0 / <6h=0.8 / <12h=0.6 / <24h=0.4 / ≥24h=0.2. Azerbaijan $3B (1d old) lands at 0.2 → composite ~6.8 for a Bloomberg story.
- No `BREAKING_NEWS_SCORE` / `THREADS_SCORE` constants exist. The Haiku `is_gold_relevant_or_systemic_shock` gate is binary. Composite score is purely a sort key today.
</domain>

<decisions>
## Implementation Decisions

### D1 — Top-N cap with composite-score sort
**Locked:**
- `breaking_news.py` → `max_count=3, sort_by="score"`
- `threads.py` → keep `max_count=2`, add `sort_by="score"` (switch from recency to composite sort)

Rationale: the existing `sort_by="score"` machinery in `content/__init__.py:199-210` is battle-tested by infographics. We just wire breaking_news + threads to use it. Volume ceiling: 3 × 12 runs/day = 36 breaking_news WhatsApps/day max, 2 × 12 = 24 threads/day max. Scannable and user-approved ("cap=3" recommendation accepted).

### D2 — Minimum composite-score floor (new filter)
**Locked:** `min_score = 6.5` applied ONLY to breaking_news + threads, evaluated AFTER Haiku gate + compliance but BEFORE persist.

Why 6.5:
- Azerbaijan $3B (Bloomberg, 1d old, relevance ~0.8): composite = (0.8×0.4 + 0.2×0.3 + 1.0×0.3)×10 = 6.8 → **passes** (barely)
- Typical routine gold-price-ticker (relevance 0.5, recency 0.6, credibility 0.6): composite = (0.5×0.4 + 0.6×0.3 + 0.6×0.3)×10 = 5.6 → **filtered**
- US-EU critical minerals deal (Reuters, fresh, relevance 0.9): composite = (0.9×0.4 + 1.0×0.3 + 1.0×0.3)×10 = 9.6 → **passes easily**

Operational effect: on quiet runs (all stories score <6.5), the agent approves 0 items → firehose sends NO WhatsApp (silent = nothing to notify, per i8b contract). Good UX — better than forcing mediocre content into the top-N slots.

**Implementation knob:** expose as a module-level constant so future tuning is one-line:
- Either a new parameter on `run_text_story_cycle(..., min_score: float | None = None)`, OR
- Module-level constants `BREAKING_NEWS_MIN_SCORE = 6.5` and `THREADS_MIN_SCORE = 6.5` in each sub-agent file, read inside their `run_draft_cycle`.

**Prefer parameter on `run_text_story_cycle`** — centralizes the filtering logic, matches the existing `max_count` / `sort_by` parameter shape. Other sub-agents can opt in later (default=None = disabled).

### D3 — Recency curve softening (<48h bucket)
**Locked:** expand `recency_score` from 5 → 6 buckets:
```
<3h   → 1.0   (unchanged)
<6h   → 0.8   (unchanged)
<12h  → 0.6   (unchanged)
<24h  → 0.4   (unchanged)
<48h  → 0.3   (NEW — softens the 24h cliff)
≥48h  → 0.2   (unchanged)
```

Rationale: the current curve cliffs at exactly 24h (0.4 → 0.2). A Bloomberg/Reuters story that breaks at t=0 and gets ingested at t=25h loses 50% of its recency signal overnight. Adding a <48h=0.3 bucket gives it one more day of runway before falling to the floor. This benefits high-credibility late-catch stories (Azerbaijan-class cases) without materially changing behavior for fresh content.

Side effects:
- Affects ALL 6 sub-agents' sorting, not just breaking_news + threads. (Acceptable — the change is strictly monotonic: no story gets LESS recency signal, some get MORE.)
- One-line change inside `recency_score`. Updates existing test(s) that assert 0.2 at 25h to expect 0.3.

### D4 — No Haiku-gate prompt changes
**Locked:** `is_gold_relevant_or_systemic_shock` at `content_agent.py:~440-487` stays untouched. Today's misses (Azerbaijan, EU-US critical minerals) were **never-fetched** bucket per htu's DB evidence — addressed by htu's keyword expansion, not by gate tuning. The gate already lists "rare-earth restrictions" and "geopolitics/systemic shock" as KEEP triggers. Broad enough.

### D5 — No analyst draft-prompt changes
**Locked:** The "senior gold analyst" voice/tone framing in `breaking_news.py` / `threads.py` draft prompts stays untouched. This is not a voice tuning task; it's a selection tuning task.

### D6 — Scope of `min_score` enforcement
**Locked:** `min_score` is checked in `run_text_story_cycle` AFTER the Haiku gate passes AND AFTER the compliance review passes (both already happen inline for each candidate). The flow becomes:
```
for story in candidates (sorted by composite desc if sort_by=score):
    if already_covered_today: continue
    if not Haiku_gate.keep: continue
    article = fetch_article(...)
    draft = draft_fn(...)
    review = compliance_review(draft)
    if not review.approved: continue
    # NEW: min_score check here (uses story["score"] — already populated upstream)
    if min_score is not None and story["score"] < min_score: continue
    persist + items_queued += 1
    if max_count and items_queued >= max_count: break
```

Rationale for placement AFTER compliance (not before): compliance is cheap relative to draft+review round-trips, so checking it here doesn't matter much for cost. But more importantly, placing the `min_score` check at the end means we get full telemetry on how often the floor actually kicks in (count of "approved-but-floored" items in `agent_run.notes`). Good observability for future tuning.

**Alternative considered & rejected:** check `min_score` BEFORE Haiku/compliance to save Claude API calls. Rejected because (a) the cost impact is negligible at our volume, and (b) post-gate observability is more valuable.

### D7 — Telemetry additions
**Locked:** `agent_run.notes` for breaking_news + threads should carry the new dimension:
- New key: `"floored_by_min_score": <count>` — stories that passed Haiku + compliance but failed the composite floor.
- Existing keys stay: `candidates`, `drafted`, `compliance_blocked`, `queued`, `top_by_score`.
- Already a JSON merge per i8b hardening, so this just adds one key.

### D8 — Remove "rare earth restrictions" keyword (folded in from mid-task user directive)
**User quote:** *"Lets get the rare earth key word out of there"*

**Locked:** delete `"rare earth restrictions"` from `SERPAPI_KEYWORDS` in `scheduler/agents/content_agent.py:79`. This is one of the 8 keywords added by htu (260424-htu) under the "# Expansion (htu) — critical minerals + sovereign gold coverage" comment block.

Rationale: user feedback after htu shipped — the rare-earth keyword is pulling too many off-theme results (rare-earth policy pieces that don't map to gold). Removing it narrows ingestion back toward gold + broader critical-minerals policy (we keep `"critical minerals"`, `"strategic metals"`, `"mineral supply chain"`, `"US China metals"` which are more on-signal). Keyword count drops 18 → 17.

**Explicitly PRESERVE (no edit):** the two "rare-earth" mentions in the Haiku gate prompt at `content_agent.py:449` and `content_agent.py:496` — those are narrative examples of systemic-shock framing, not ingestion keywords. D4 locks the Haiku gate prompt as untouched.

**Test impact:** `scheduler/tests/test_content_agent.py:66` has an assertion referencing `"rare earth restrictions"` (likely a `SERPAPI_KEYWORDS` membership check). The researcher must confirm the exact assertion shape and the executor removes it.

### D9 — Threads cron cadence 4h → 3h (folded in from mid-task user directive)
**User quote:** *"Breaking news should run every two hours / Threads should run every 3 hours"*

**Locked:**
- `sub_breaking_news`: stays at `IntervalTrigger(hours=2)` (already correct — no change needed; recorded here so the executor verifies current state)
- `sub_threads`: `IntervalTrigger(hours=4)` → `IntervalTrigger(hours=3)` in `scheduler/worker.py:117`

Rationale: threads was moved 2h → 4h in vxg (260422-vxg) as part of a cadence rebalance. User now wants 3h — halfway back. Staggers remain: `sub_breaking_news` offset 0, `sub_threads` offset 17min. With threads at 3h interval the offset still fires inside the first hour of each run cycle, no collision logic changes.

**Test impact:** any assertion in `scheduler/tests/test_worker.py` against the 4h interval must be updated to 3h. Researcher must confirm the assertion exists and where.

**Scope-relaxation:** this promotes `scheduler/worker.py` from ZERO-DIFF to NARROW-DIFF for j5i. The diff is strictly a `6` → `4` ... wait, we're changing from `interval_hours=4` to `interval_hours=3` — touches exactly one integer literal inside `CONTENT_INTERVAL_AGENTS` tuple `("sub_threads", threads.run_draft_cycle, "Threads", 1011, 17, 4)` → `... 17, 3)`. Comments at L8-11, L108-111, L117, L312-317, L328 reference the "4h" cadence narratively and must be updated for honesty. That widens the diff slightly but is still narrow (tuple literal + 5-6 comment lines).

### Claude's Discretion
- Exact parameter name: `min_score` vs `min_composite_score` — leaning `min_score` for brevity; executor picks.
- Whether to expose the 6.5 as a module-level constant in breaking_news.py/threads.py or inline as a literal at the call site: leaning module-level constant (`BREAKING_NEWS_MIN_SCORE = 6.5`, `THREADS_MIN_SCORE = 6.5`) so operators can tune per-agent without editing shared infrastructure.
- Test file organization: extend existing `test_breaking_news.py` / `test_threads.py` / `test_content_agent.py` if they exist; otherwise add minimal test to `test_content_wrapper.py` (shared `run_text_story_cycle` tests already live there per i8b).

</decisions>

<specifics>
## Specific Ideas

**Scope constraints — MODIFY:**
- `scheduler/agents/content/breaking_news.py` — add `max_count=3, sort_by="score", min_score=BREAKING_NEWS_MIN_SCORE` to `run_text_story_cycle` call; declare `BREAKING_NEWS_MIN_SCORE = 6.5` constant
- `scheduler/agents/content/threads.py` — add `sort_by="score", min_score=THREADS_MIN_SCORE` to existing `run_text_story_cycle` call (keep `max_count=2`); declare `THREADS_MIN_SCORE = 6.5` constant
- `scheduler/agents/content/__init__.py` — extend `run_text_story_cycle` signature with `min_score: float | None = None` parameter; add check at the post-compliance persist point; increment `floored_by_min_score` counter; include it in the JSON notes
- `scheduler/agents/content_agent.py` — (a) update `recency_score` (L111-129) to add <48h=0.3 bucket; (b) **[D8]** remove `"rare earth restrictions"` entry from `SERPAPI_KEYWORDS` list at L79; (c) update the "# Expansion (htu)" comment at L77 if it now counts wrong (8 → 7 additions)
- `scheduler/worker.py` — **[D9]** change `sub_threads` interval from `4` to `3` in `CONTENT_INTERVAL_AGENTS` at L117; update narrative comments at L8-11, L108-111, L312-317, L328 from "4h" to "3h" wherever they reference the threads cadence (breaking_news stays 2h untouched)

**Scope constraints — TESTS (MODIFY or create):**
- `scheduler/tests/test_content_agent.py` — new test asserting `recency_score(25h_ago) == 0.3` (old: 0.2); preserve existing tests for the other buckets; **[D8]** remove the `"rare earth restrictions"` assertion at L66
- `scheduler/tests/test_content_wrapper.py` — new test(s): `min_score` filters stories below threshold; `floored_by_min_score` counter is populated; when all stories fall below threshold, `items_queued == 0` and `status="completed"` (not "failed")
- `scheduler/tests/test_breaking_news.py` and `test_threads.py` — if they exist, extend to assert the new constants are at the expected values and are passed to `run_text_story_cycle`
- `scheduler/tests/test_worker.py` — **[D9]** if there is any assertion against `sub_threads` interval being 4h, update to 3h. Researcher must confirm the assertion's exact location.

**Scope constraints — ZERO DIFF (verify `git diff main -- <path>` is empty):**
- `scheduler/agents/content/{quotes,infographics,gold_media,gold_history}.py` — different selection logic, not affected
- `scheduler/services/whatsapp.py`, `scheduler/agents/senior_agent.py` — notification plumbing (i8b territory)
- `backend/`, `frontend/`, `alembic/`, `scheduler/models/`
- The Haiku gate prompt (including its `rare-earth` example-language at content_agent.py:449 and :496) AND the draft prompts in breaking_news.py / threads.py — only TUNABLES + KEYWORDS + SCHEDULE change, not PROMPTS
- **NOT on this list any more:** `scheduler/worker.py` — promoted to NARROW-DIFF by D9

**Validation gates:**
```bash
cd scheduler
uv run pytest tests/test_content_agent.py tests/test_content_wrapper.py tests/test_worker.py -x -v   # new tests green
uv run pytest -x                                                                                       # full suite green
uv run ruff check .                                                                                    # clean

# grep proofs (from repo root)
grep -n "BREAKING_NEWS_MIN_SCORE\s*=\s*6\.5" scheduler/agents/content/breaking_news.py   # match
grep -n "THREADS_MIN_SCORE\s*=\s*6\.5" scheduler/agents/content/threads.py               # match
grep -n 'max_count=3' scheduler/agents/content/breaking_news.py                           # match
grep -n 'sort_by="score"' scheduler/agents/content/breaking_news.py                       # match
grep -n 'sort_by="score"' scheduler/agents/content/threads.py                             # match
grep -n "min_score" scheduler/agents/content/__init__.py                                  # match
grep -n "48h\|< 48\|age_hours < 48" scheduler/agents/content_agent.py                      # match (new bucket)
grep -n "floored_by_min_score" scheduler/agents/content/__init__.py                        # match

# D8 proofs — keyword gone
grep -n "rare earth restrictions" scheduler/agents/content_agent.py                        # NO match in SERPAPI_KEYWORDS context
grep -cn "^    \"" scheduler/agents/content_agent.py | head                                 # SERPAPI_KEYWORDS now 17 entries, not 18

# D9 proofs — threads on 3h
grep -n '"sub_threads".*3' scheduler/worker.py                                              # match (tuple with 3 as interval_hours)
grep -cn '"sub_threads".*4)' scheduler/worker.py                                             # 0 (no lingering 4h tuple)

# preservation diffs (all must be empty) — worker.py dropped; whatsapp.py + senior_agent.py kept
git diff main -- scheduler/agents/content/quotes.py \
               scheduler/agents/content/infographics.py \
               scheduler/agents/content/gold_media.py \
               scheduler/agents/content/gold_history.py \
               scheduler/services/whatsapp.py \
               scheduler/agents/senior_agent.py \
               backend/ frontend/ alembic/ scheduler/models/
```

**Research phase must confirm:**
- Exact line range of `recency_score` + whether the 48h bucket addition will break any existing test assertions
- Whether `test_breaking_news.py` / `test_threads.py` exist (if not, add to test_content_wrapper.py only)
- DB score distribution over last 7 days for breaking_news/threads-eligible stories — to sanity-check the 6.5 floor (does it bin ~40% of current approvals as expected, or ~10%, or ~80%?)
- Any call-site in content_agent.py that uses `recency_score` directly and might be affected by the new bucket (search for `recency_score(` usage)
- **[D8]** Exact shape of the `"rare earth restrictions"` assertion in `scheduler/tests/test_content_agent.py:66` — is it a `"X" in SERPAPI_KEYWORDS` check, a length check, or an exact-list equality? Determines whether one line is edited or a full fixture replaced.
- **[D9]** Whether `scheduler/tests/test_worker.py` asserts the `sub_threads` interval explicitly (e.g., `assert interval_hours == 4`) or just checks the tuple shape. Determines whether test updates are required.
</specifics>

<canonical_refs>
## Canonical References

- `scheduler/agents/content_agent.py:111-129` — current `recency_score` (5 buckets)
- `scheduler/agents/content_agent.py:144-158` — composite score formula
- `scheduler/agents/content/__init__.py:84-130` — `run_text_story_cycle` signature (extend here)
- `scheduler/agents/content/__init__.py:199-210` — existing composite sort machinery
- `scheduler/agents/content/infographics.py:359-364` — reference call site using `max_count=2, sort_by="score"`
- `scheduler/agents/content/breaking_news.py:122-129` — current non-capped non-scored call
- `scheduler/agents/content/threads.py:115-127` — current cap=2 recency-sorted call
- **Related tasks:**
  - `260424-htu` — keyword expansion (never-fetched fix)
  - `260424-i8b` — notification firehose + midday digest
  - `260422-zid` — prior cap=2 introduction on threads.py, "debug session" comment explains current sort_by=published_at rationale
  - `260422-vxg` — `GOLD_MEDIA_SCORE=7.5` / `GOLD_HISTORY_SCORE=8.0` precedent for score floors (but THOSE floors gate fixed-score Twitter-sourced content, not Haiku-gated news)
  - `260423-lvp` — `infographics.py` pattern `max_count=2, sort_by="score"` we're propagating
</canonical_refs>
