# Phase 15 — Juno Weekly Viral Sweeper — Voice Calibration UAT

> **Operator artifact** capturing the manual smoke-fire of `run_juno_weekly_sweeper()` and the 6-criteria voice UAT verdict.
>
> **Purpose:** D-07 step 3 — operator validates the Sonnet output against the Janes/CSIS desk voice anchor + anti-feature negative space BEFORE flipping `JUNO_SWEEPER_CRON_ENABLED=true` in Railway env vars (D-07 step 4 — out-of-band action AFTER this artifact signs off APPROVED).
>
> **Precedent:** Mirrors Phase 10's voice UAT precedent verbatim. Defence content's higher refusal-rate risk (RESEARCH §4 Anthropic-Pentagon dispute Feb–Apr 2026) makes the human voice check load-bearing — automated tests verify the FORBID-block bytes are present, but only the operator can confirm Sonnet output ACTUALLY reads as Janes/CSIS desk vs. drifting into tactical/operational territory.

---

## Operator Runbook (D-07 step 2 — manual smoke fire)

> Read this section once before firing. The smoke fire is non-destructive (writes ONE `weekly_sweeps` row + ONE `agent_runs` row — both idempotency-safe; re-firing within 60 minutes is skipped per the Phase 9 `status.in_(['running','completed','partial'])` filter).

### Prerequisites

| Requirement | Where | How to verify |
|-------------|-------|---------------|
| Phase 15 plans 01–06 deployed to Railway | scheduler service | Boot log: `ENV JUNO_SWEEPER_CRON_ENABLED: false (juno_weekly_sweeper cron disabled — flip after voice UAT)` |
| Cron is **DISABLED** (smoke fire bypasses cron) | Railway env | `JUNO_SWEEPER_CRON_ENABLED` UNSET or `false`. Smoke fire invokes the orchestrator DIRECTLY via `python -m agents.juno_weekly_sweeper` — does NOT depend on the cron being enabled. |
| `JUNO_ANTHROPIC_API_KEY` (or shared `ANTHROPIC_API_KEY` fallback per Phase 12 D-01) | Railway env or local | Phase 12 resolver `get_anthropic_client('juno', ...)` will route to Juno's key with shared fallback |
| `X_API_BEARER_TOKEN` | Railway env or local | tweepy `search_recent_tweets` call needs Basic-tier credentials |
| Production DB credentials | Railway env or local | `DATABASE_URL` pointing at the production Neon instance (or a high-fidelity staging DB with Juno daily_summaries seeded under the Plan 15-01 schema) |

### Step 1 — Fire the sweeper

Open a Railway shell on the scheduler service (or a local terminal with the same env vars set), then:

```bash
cd scheduler
python -m agents.juno_weekly_sweeper
```

**What happens:**

1. Module's `__main__` block at line 583 calls `asyncio.run(run_juno_weekly_sweeper())`.
2. INFO logs trace the 6-step orchestrator: idempotency check → `agent_runs` INSERT (status='running') → per-tenant Anthropic resolver call (HARDCODED literal `'juno'` per Phase 12 D-07) → `fetch_top_x_posts(JUNO_SWEEPER_X_QUERY)` → `_compute_juno_virality()` (3-sub-array union over `defence_news` + `canadian_procurement` + `world_events`) → `call_with_refusal_guard()` (Phase 10 D-05 reused verbatim) → `weekly_sweeps` INSERT.
3. **Expected outcomes (any of the three is acceptable for proceeding to the voice UAT):**
   - **Happy path** — one `weekly_sweeps` row written with `company_id='juno'`, `status='completed'`, 3 content angles in `content_angles_md`
   - **Backfill window (D-03b)** — `status='partial'` with `raw_sources_jsonb.substrate_summary.insufficient_signal_path` set + `INSUFFICIENT_SIGNAL_FALLBACK` copy in `content_angles_md`. Acceptable for first 0–2 post-deploy sweeps until ~7 days of new-schema Juno `daily_summaries` rows accumulate.
   - **Refusal-detector second-attempt fail** — `status='partial'` with `raw_sources_jsonb.refusal_diagnostic` populated + `REFUSAL_FALLBACK_COPY` in `content_angles_md`. Acceptable — refusal-detector wrap behaved per Phase 10 contract; document under Criterion 6 verdict.
   - **NOT acceptable:** `status='failed'` (catastrophic) — investigate `agent_runs.notes` for the traceback before re-firing.

### Step 2 — Pull the persisted row

```sql
-- Inspect the just-written row
SELECT
    id,
    generated_at,
    status,
    content_angles_md,
    raw_sources_jsonb->'substrate_summary' AS substrate_summary,
    raw_sources_jsonb->'refusal_diagnostic' AS refusal_diag,
    raw_sources_jsonb->'x_search_query'    AS x_search_query
FROM weekly_sweeps
WHERE company_id = 'juno'
ORDER BY generated_at DESC
LIMIT 1;
```

Also pull the corresponding `agent_runs` row for refusal-detector observability:

```sql
SELECT id, agent_name, status, started_at, completed_at, notes
FROM agent_runs
WHERE agent_name = 'juno_weekly_sweeper'
ORDER BY started_at DESC
LIMIT 1;
```

Copy the `content_angles_md` value into the "Sample Sonnet Output" section below verbatim (within a ```` ```markdown ```` fence).

### Step 3 — Apply the 6 voice UAT criteria

Read each criterion's PASS/FAIL definition below, evaluate against the persisted output, then mark PASS / FAIL / N/A and add a sentence of notes in the verdict ledger.

### Step 4 — Record the final verdict + sign off

- **APPROVED** — all 6 criteria PASS (or 5 PASS + soft criterion notes are non-blocking). Operator commits to flipping `JUNO_SWEEPER_CRON_ENABLED=true` in Railway scheduler service Variables next.
- **DEFERRED — needs iteration** — 1–2 criteria FAIL but not blockers. Phase 15 ships at `status='partial-allowed'`; specific fixes documented in the verdict ledger for a v3.2 prompt-iteration backlog item.
- **REJECTED** — multiple criteria FAIL or a blocker (e.g., tactical/operational leak, defence-prime cashtag, < 3 angles consistently). Phase 15 needs additional plan(s) before the env-gate flip; orchestrator routes back to `/gsd:plan-phase 15 --gaps` with the specific failing criteria.

### Step 5 — (On APPROVED) flip the env gate — OUT-OF-BAND ACTION (NOT part of this checkpoint)

1. Railway dashboard → scheduler service → Variables
2. Add new variable: `JUNO_SWEEPER_CRON_ENABLED` = `true`
3. Railway redeploys the scheduler service (~1–2 min)
4. Verify boot logs show:
   - `ENV JUNO_SWEEPER_CRON_ENABLED: true (juno_weekly_sweeper cron WILL register at Sun 08:00 PT)`
   - `juno_weekly_sweeper cron ENABLED via JUNO_SWEEPER_CRON_ENABLED=true env var`
5. Next Sunday 08:00 PT America/Los_Angeles, the real cron fires for the first time.

**Rollback path:** Unset / remove the env var in Railway → next deploy registers no cron → no Sunday fire (no data deletion needed; existing `weekly_sweeps` rows survive).

---

## Smoke Fire Metadata

> Operator fills this section after Step 1 + Step 2 above.

| Field | Value |
|-------|-------|
| Date/time fired (UTC) | _TBD — fill after smoke fire_ |
| Date/time fired (PT) | _TBD_ |
| Environment | _production / staging_ |
| Operator | _initials_ |
| Persisted `weekly_sweeps.id` | _UUID from query in Step 2_ |
| Persisted row `status` | _completed / partial / (NOT failed)_ |
| Corresponding `agent_runs.id` | _UUID_ |
| `agent_runs.status` | _completed / failed_ |
| Substrate-window status (D-03b backfill caveat) | _backfilled / accumulating / N/A_ |
| `refusal_detected` flag in `agent_runs.notes` | _true / false_ |
| First-attempt refusal? | _yes / no_ |
| Retry-with-framing-nudge produced clean output? | _yes / no / N/A_ |
| Anthropic API spend (estimated) | _~$0.05–0.20 per smoke fire_ |

---

## Sample Sonnet Output (`content_angles_md`)

> Paste the full `content_angles_md` column value from Step 2 verbatim inside the fence.

```markdown
TBD — operator pastes the Sonnet output here after running the smoke fire.
```

---

## 6-Criteria Voice UAT Verdict

> Criteria reproduced **verbatim** from `15-CONTEXT.md` `<specifics>` lines 248–254 (the canonical voice UAT contract; mirror of Phase 10 precedent).

### Criterion 1 — Voice: Janes/CSIS desk

**Statement:** Each angle reads as Janes/CSIS desk (sober, sourced-with-receipts, geopolitical context — NOT tactical/operational).

- **PASS =** all 3 angles read as defence-trade-press analyst voice (Janes desk brief / CSIS analysis / IISS Military Balance / Defense News editorial)
- **FAIL =** any angle reads as op-ed / advocacy / forum chatter / tactical-analyst voice

**Verdict:** [ ] PASS  [ ] FAIL  [ ] N/A

**Notes:**
_TBD — operator fills in_

---

### Criterion 2 — Quantity: exactly 3 angles

**Statement:** Exactly 3 angles (not 2, not 4 — Sonnet sometimes drifts).

- **PASS =** exactly 3 `### Angle N:` headers (or equivalent angle delimiters) in `content_angles_md`
- **FAIL =** anything else; Sonnet is drifting and the prompt may need tightening in v3.2

**Verdict:** [ ] PASS  [ ] FAIL  [ ] N/A

**Observed count:** _N angles_

**Notes:**
_TBD_

---

### Criterion 3 — Task contract: X signal + news signal

**Statement:** Each angle connects an X signal with a news-week signal (the sweeper's task contract).

- **PASS =** all 3 angles have BOTH an X (Twitter) signal AND a mainstream defence-news signal with concrete attribution
- **FAIL =** any angle conflates the two, has only one (X-only or news-only), or fabricates an X signal not in the supplied substrate

**Verdict:** [ ] PASS  [ ] FAIL  [ ] N/A

**Notes:**
_TBD_

---

### Criterion 4 — Anti-feature: no defence-prime cashtags / equity signals

**Statement:** No defence-prime cashtags, no troop-movement / OOB / capability-gap / targeting analysis. (This criterion bundles two anti-feature classes per CONTEXT specifics line 252.) For Criterion 4 evaluate the **equity/financial** half:

- **PASS =** zero defence-prime stock tickers, P/E ratios, share-price movements, earnings, dividends, or buy/sell framings on LMT, RTX, NOC, BA, GD, BAESY, LDOS, or any other defence prime
- **FAIL =** even one equity bullet → check the negative-space DO-NOT list in `JUNO_SWEEPER_SYSTEM_PROMPT`; may need iteration in v3.2

**Verdict:** [ ] PASS  [ ] FAIL  [ ] N/A

**Notes:**
_TBD_

---

### Criterion 5 — Anti-feature: no tactical/operational content + refusal-detector behavior

**Statement (split):** This criterion bundles the **tactical/operational** half of CONTEXT line 252 with the **refusal-detector** check on CONTEXT line 253.

#### 5a — Anti-tactical clause held

- **PASS =** zero troop-movement / OOB (order-of-battle) / capability-gap / targeting / force-posture / force-disposition analysis under ANY framing. If a source story crossed into operational territory, the angle summarizes market/industry implications only and notes operational details were excluded.
- **FAIL =** any angle leaks operational analysis → the FORBID clause string-equality contract is intact but Sonnet may have drifted around it; iterate prompt in v3.2.

**Verdict (5a):** [ ] PASS  [ ] FAIL  [ ] N/A

#### 5b — Refusal-detector wrap behaved

> CONTEXT line 253: "If refusal-detector fired, retry-with-framing-nudge produced clean output OR row persisted with `status='partial'` + diagnostic note."

- **PASS =** EITHER (a) no first-attempt refusal detected (clean happy path) OR (b) first-attempt refusal → retry-with-framing-nudge produced clean angles_md OR (c) second-attempt refusal → row persisted with `status='partial'` + `refusal_diagnostic` populated in `raw_sources_jsonb` + `REFUSAL_FALLBACK_COPY` visible in `content_angles_md`
- **FAIL =** visible refusal text in `content_angles_md` WITHOUT `status='partial'` being set (refusal-detector did NOT engage when it should have)

**Verdict (5b):** [ ] PASS  [ ] FAIL  [ ] N/A

**Notes (both):**
_TBD — operator records the `refusal_detected` flag from agent_runs.notes + the path taken_

---

### Criterion 6 — Voice differentiation from Seva's Bloomberg-gold-desk

**Statement:** Tone differentiates clearly from Seva's Bloomberg-gold-desk voice (eye check).

- **PASS (eye check):**
  - Seva sweeper reads as Bloomberg commodities-desk energy — gold-bull-thesis bias, "flows tell a different story" framing, dollar-strength/Fed-pivot/Asian-buyer-demand angles
  - Juno sweeper reads as Janes/CSIS desk energy — sober, neutral-on-conflict, contract values + vendor names + policy instruments + procurement timelines
- **FAIL (soft):** if voices read as too similar, the `JUNO_SWEEPER_SYSTEM_PROMPT` may need iteration in v3.2 to push harder on the voice anchor. This is NOT a Phase 15 blocker — it is a soft check / tunability signal.

> **Eye-check procedure:** If a recent Seva `weekly_sweeps` row exists, query it and side-by-side read both `content_angles_md` values. If no recent Seva sweep is available, skip and mark N/A — Criterion 6 is the only criterion where N/A is a valid disposition.

**Verdict:** [ ] PASS  [ ] FAIL  [ ] N/A (no recent Seva sweep for comparison)

**Notes:**
_TBD_

---

## Voice Differentiation (BONUS — supplementary notes for Criterion 6)

> Optional free-form section for side-by-side voice comparison if a recent Seva sweep is available. Useful for documenting v3.2 prompt-iteration ideas even when Criterion 6 passes.

| Dimension | Seva Bloomberg-gold-desk | Juno Janes/CSIS desk | Differentiated? |
|-----------|--------------------------|----------------------|------------------|
| Voice anchor | _e.g., "flows tell a different story"_ | _e.g., "$X.XB contract awarded to {vendor}"_ | _yes / no_ |
| Vocabulary | _e.g., basis points, vol, futures curve_ | _e.g., procurement, doctrine, force posture (mentioned NOT analyzed), capability roadmap_ | _yes / no_ |
| Audience signal | _gold-fund desk, commodities trader_ | _think-tank analyst, defence-trade-press reader_ | _yes / no_ |
| Source attribution | _e.g., Kitco / Bloomberg / GoldHub_ | _e.g., Janes / CSIS / IISS / Defense News_ | _yes / no_ |

**Eye-check verdict:** _voices differentiate clearly / voices read similar / no recent Seva sweep available_

**v3.2 prompt-iteration ideas (if any):**
_TBD — operator notes any voice-anchor pushes that would sharpen the differentiation_

---

## Final Verdict

> ONE of the following three. Mark only one. Plan acceptance check (`grep -cE "^## Final Verdict$"`) expects exactly this header — do NOT rename.

- [ ] **APPROVED** — all 6 criteria PASS (or 5 PASS + Criterion 6 N/A); operator will flip `JUNO_SWEEPER_CRON_ENABLED=true` in Railway next (out-of-band, AFTER this artifact signs off)
- [ ] **DEFERRED — needs iteration** — 1–2 criteria FAIL but not blockers; phase ships at `status='partial-allowed'`; v3.2 backlog updated with: _list specific criteria + iteration plan_
- [ ] **REJECTED** — multiple criteria FAIL or a blocker (e.g., tactical/operational leak or defence-prime equity bullet); orchestrator routes back to `/gsd:plan-phase 15 --gaps` with: _list specific failing criteria + what additional plans Phase 15 needs_

**Verdict rationale (1–3 sentences):**
_TBD — operator's overall summary of how the smoke fire went and why this verdict_

---

## Operator Sign-off

| Field | Value |
|-------|-------|
| Operator initials | _TBD_ |
| Date (PT) | _TBD_ |
| Resume signal sent to orchestrator | _approved / deferred: <details> / rejected: <details>_ |
| Post-approval action: flip `JUNO_SWEEPER_CRON_ENABLED=true` in Railway | _DONE / PENDING / NOT-YET-APPROVED_ |
| First real Sunday cron fire expected | _YYYY-MM-DD 08:00 PT — fill if APPROVED_ |

---

## Appendix — Reference Material

### A1. The 6 voice UAT criteria (verbatim from `15-CONTEXT.md` `<specifics>` lines 248–254)

> Reproduced here so the artifact is self-contained — if the operator references this file long after Phase 15 closes, the canonical criteria are preserved in-line.

1. Each angle reads as Janes/CSIS desk (sober, sourced-with-receipts, geopolitical context — NOT tactical/operational)
2. Exactly 3 angles (not 2, not 4 — Sonnet sometimes drifts)
3. Each angle connects an X signal with a news-week signal (the sweeper's task contract)
4. No defence-prime cashtags, no troop-movement / OOB / capability-gap / targeting analysis
5. If refusal-detector fired, retry-with-framing-nudge produced clean output OR row persisted with `status='partial'` + diagnostic note
6. Tone differentiates clearly from Seva's Bloomberg-gold-desk voice (eye check)

### A2. Resume-signal contract (per `15-07-PLAN.md` `<resume-signal>` lines 204–209)

Reply to the orchestrator with one of:

- `approved` — all 6 criteria PASS; voice_calibration_uat.md verdict is APPROVED; operator will flip `JUNO_SWEEPER_CRON_ENABLED=true` in Railway next (out-of-band)
- `deferred: <list specific criteria + iteration plan>` — non-blocker FAILs; phase ships, prompt iteration deferred to v3.2
- `rejected: <list specific criteria + what additional plans Phase 15 needs>` — blocker; phase needs more work before env-gate flip

### A3. D-03b backfill caveat (per `15-CONTEXT.md` D-03b + `15-05-SUMMARY.md` Outstanding Concerns)

Existing Juno `daily_summaries` rows from the past 7 days may have empty arrays under the new keys (`defence_news` / `canadian_procurement` / `world_events`) if they were written BEFORE Plan 15-01's substrate-keys writer deployed. First 0–2 smoke fires post-deploy may produce `status='partial'` with `INSUFFICIENT_SIGNAL_FALLBACK` copy in `content_angles_md` and `substrate_summary.insufficient_signal_path=true` in `raw_sources_jsonb`. **This is expected behavior — not a UAT failure.** The voice UAT can still proceed against whatever Sonnet output the orchestrator produced (X posts alone may drive synthesis; the 3-angle structure must still be evaluable). Document under the relevant criterion notes.

### A4. Cron status at the time of this UAT

- Phase 15 cron is **DISABLED by default** (per Plan 15-06 D-07 step 1 — `JUNO_SWEEPER_CRON_ENABLED` unset).
- Smoke fire is operator-initiated via `python -m agents.juno_weekly_sweeper` against the production DB (or high-fidelity staging).
- After operator approves UAT, the final step is out-of-band: flip `JUNO_SWEEPER_CRON_ENABLED=true` in Railway. Next Sunday 08:00 PT America/Los_Angeles fires for real.

### A5. Hard-stop blockers (REJECT immediately if observed)

- Any defence-prime cashtag (`$LMT`, `$RTX`, `$NOC`, `$BA`, `$GD`, `$BAESY`, `$LDOS`, etc.) in any angle → REJECT — anti-feature violation per PROJECT.md
- Any troop-movement / OOB / targeting / force-disposition analysis under any framing → REJECT — anti-tactical clause must hold
- `weekly_sweeps.status='failed'` (catastrophic) → REJECT this smoke fire; investigate `agent_runs.notes` traceback before re-firing

### A6. Soft signals (note in verdict but do NOT block APPROVED)

- 2 angles or 4 angles (instead of exactly 3) → DEFER for prompt-tightening in v3.2
- Voices read similar to Seva's Bloomberg-gold-desk (Criterion 6 fails) → DEFER soft-criterion for v3.2 voice-anchor push
- `status='partial'` due to D-03b backfill window → APPROVE if angle structure is still evaluable; re-fire after ~7 days of new-schema rows accumulate for a clean confirmation run

---

*Phase: 15-juno-weekly-viral-sweeper*
*Plan: 07*
*Artifact created: 2026-05-20 (pre-smoke-fire — operator fills metadata + verdict sections after firing)*
*Source criteria: `15-CONTEXT.md` `<specifics>` lines 248–254 (verbatim)*
