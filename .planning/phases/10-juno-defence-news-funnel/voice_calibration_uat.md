# Voice Calibration UAT — Phase 10 DEF-10

**Run date:** 2026-05-19 (UAT script created and dispatched at this date; live synthesis BLOCKED on Anthropic API auth gate — see "Run Status" below)
**Corpus:** [voice_calibration_uat_corpus.md](./voice_calibration_uat_corpus.md) (8 hand-curated defence stories)
**Synthesis approach:** Option B — Inline dry-run via `scheduler/scripts/uat_voice_calibration.py`. The script exercises the same production code path (`_build_juno_defence_news_section`, `_build_juno_canadian_procurement_section`-equivalent inline, `classify_story` from `agents/juno_relevance.py`, `_build_juno_world_events_section`-equivalent inline, all wrapped in `call_with_refusal_guard` from `agents/juno_refusal_detector.py`) with the curated 8-story fixture as input.

---

## Run Status: BLOCKED on Authentication Gate

The first dispatch attempt at 2026-05-19 hit an Anthropic API authentication error:

```
anthropic.AuthenticationError: Error code: 401 - {'type': 'error', 'error':
{'type': 'authentication_error', 'message': 'invalid x-api-key'}, 'request_id':
'req_011CbD4NKo57LvRX4FF9hJKN'}
```

The `ANTHROPIC_API_KEY` value sourced from `/Users/matthewnelson/seva-mining/.env` is `sk-ant-api03...` (109 chars — correct shape) but the API rejected it. The key may have been rotated/revoked between Phase 9 and Phase 10. Production Railway env has a separate `ANTHROPIC_API_KEY` (the Seva `daily_summary` cron has been running successfully against it for weeks — see Phase 7+ SUMMARY artifacts), so the production key is known-good.

**Resolution paths (operator picks one — see CHECKPOINT below):**

1. **Operator provides a working `ANTHROPIC_API_KEY` to the shell environment** (export it, paste it, or update `.env`), then planner re-runs `cd scheduler && uv run python scripts/uat_voice_calibration.py > /tmp/uat_output.md` and pastes the markdown into the "Sample Output" section below. THEN operator reviews against the 7-criterion bar.

2. **Operator reads the corpus + script + production code path WITHOUT live synthesis** and approves the calibration on architecture/code grounds alone (i.e., trust that the production code path — which has been independently unit-tested in Wave 2 against mocked Sonnet — will produce voice-matching output when fired against this curated corpus). Less rigorous; only acceptable if operator explicitly accepts the risk.

3. **Operator defers Task 3 by marking the checkpoint REJECTED with category "auth gate"** — planner re-runs once auth is resolved. Cron stays DISABLED (per the JUNO_CRON_ENABLED=false default added in Task 2 of this plan). Wave 4 cannot proceed until Task 3 closes APPROVED.

---

## Sample Output

_(Populate this section AFTER operator resolves the auth gate per Option 1 above. Re-run the UAT script with a working key and paste the Sonnet markdown output for each section verbatim.)_

### 🛡️ Defence News
_(Pending live synthesis — `_build_juno_defence_news_section(client, DEFENCE_STORIES)` against Stories 1-2 from corpus.)_

### 🇨🇦 Canadian Procurement
_(Pending live synthesis — inline Sonnet call against Stories 3+8 from corpus, using `DEFENCE_NEWS_SYSTEM_PROMPT` + `JUNO_SONNET_MAX_PROCUREMENT=1000` per production config.)_

### 🌐 World Events Relevant to Defence
_(Pending live synthesis — `classify_story` Haiku filter on Stories 4-7, then Sonnet synthesis on whichever survive the `confidence >= 0.7 AND is_relevant AND category != not_relevant` threshold.)_

---

## Haiku Classifier Verdicts (Stories 4-7)

_(Populate after live re-run.)_

| Story | is_relevant | category | confidence | survives_threshold |
|-------|-------------|----------|------------|--------------------|
| 4 (Ukraine ATACMS — conflict-zone) | ?     | ? | 0.??  | ? |
| 5 (EUV controls — sanctions_export) | ? | ? | 0.??  | ? |
| 6 (Apple Vision — should reject)  | ?     | ? | 0.??  | ? |
| 7 (Skydio drone — dual-use)       | ?     | ? | 0.??  | ? |

---

## Refusal-Detector Diagnostics

_(Populate after live re-run. Each section's `_diag` dict carries `refusal_detected`, `retry_attempted`, `first_attempt_excerpt` per `call_with_refusal_guard` contract.)_

- Defence News section: `refusal_detected=?`, retry_attempted=?
- Canadian Procurement section: `refusal_detected=?`, retry_attempted=?
- World Events section: `refusal_detected=?`, retry_attempted=?

---

## 7-Criterion Pass Bar (RESEARCH §Voice UAT Pass Criteria)

| # | Criterion | Pass / Fail | Operator Notes |
|---|-----------|-------------|----------------|
| 1 | **Voice match** — reads like Janes/CSIS desk brief (qualitative) | ? | _(operator notes after reading Sample Output)_ |
| 2 | **Anti-tactical clause holds** — zero matches for `force posture\|order of battle\|OOB\|troop movement\|capability gap\|targeting` in Sample Output sections | ? | grep result: _(N matches)_ |
| 3 | **Source attribution complete** — ≥95% bullets end with `(Source Name)` per regex `\(\w[\w\s]+\)$` | ? | regex match rate: _(N/M)_ |
| 4 | **Section balance** — Defence News 3-7, Canadian Procurement 3-5, World Events 5-7 bullets | ? | actual counts: _(N1/N2/N3)_ |
| 5 | **No refusals** — `refusal_detected=false` on all 3 sections | ? | see Refusal-Detector Diagnostics |
| 6 | **Borderline cases** — Apple Vision (Story 6) `is_relevant=false`; climate+def (corpus Story 8, routed to Procurement) handled cleanly | ? | Story 6 verdict + Story 8 inclusion behaviour |
| 7 | **Dual-use exclusion** — Story 7 (Skydio consumer drone) does NOT appear in World Events output | ? | grep World Events markdown for `Skydio` or `consumer drone` |

### Pass Bar Verification Commands

```bash
# Criterion 2 — anti-tactical clause grep
grep -iE "force posture|order of battle|OOB|troop movement|capability gap|targeting" \
  .planning/phases/10-juno-defence-news-funnel/voice_calibration_uat.md \
  | grep -v "^| 2 " | grep -v "Anti-tactical"
# Expect: zero matches in Sample Output sections

# Criterion 3 — source attribution regex
grep -E "^- " voice_calibration_uat.md | grep -E "\(\w[\w\s]+\)$" | wc -l
grep -E "^- " voice_calibration_uat.md | wc -l
# Compute ratio; >= 0.95 = pass

# Criterion 7 — dual-use exclusion
grep -A 100 "World Events Relevant to Defence" voice_calibration_uat.md \
  | grep -iE "skydio|consumer drone|X10D"
# Expect: zero matches
```

---

## Operator Sign-Off

**Verdict:** [ ] APPROVED  [ ] REJECTED

**If REJECTED:**
- Failure category: _{voice mismatch | refusal | dual-use leak | regional skew | auth gate | other}_
- Required revisions: _{operator's specific prompt-tuning instructions for planner to iterate on `DEFENCE_NEWS_SYSTEM_PROMPT` (scheduler/companies/juno/prompts.py) or `RELEVANCE_SYSTEM_PROMPT` (scheduler/agents/juno_relevance.py)}_
- Re-run UAT: required → planner edits prompts, current artifact archived to `voice_calibration_uat_v1_rejected.md`, fresh `voice_calibration_uat.md` written on next iteration

**If APPROVED:**
- Approval timestamp: _{YYYY-MM-DD HH:MM PT}_
- Cron-enable next step: Wave 4 (10-05-PLAN.md) runs integration smoke with `JUNO_CRON_ENABLED=true`; operator flips Railway env var only after smoke confirms one clean fire writes the expected row shape
- APPROVED string marker (required for verify-work grep gate): _{add the literal string `APPROVED` here on a line of its own when the verdict is approved}_

---

## Artifact Inventory

- **Corpus:** [voice_calibration_uat_corpus.md](./voice_calibration_uat_corpus.md) — 8 hand-curated defence stories with URLs, titles, sources, section buckets, and why-curated rationale
- **UAT script:** `/Users/matthewnelson/seva-mining/scheduler/scripts/uat_voice_calibration.py` — one-shot dispatcher exercising the production code path against the curated corpus
- **Production prompt under test:** `/Users/matthewnelson/seva-mining/scheduler/companies/juno/prompts.py::DEFENCE_NEWS_SYSTEM_PROMPT` (Janes/CSIS voice + anti-tactical clause + 3-section structure)
- **Production classifier under test:** `/Users/matthewnelson/seva-mining/scheduler/agents/juno_relevance.py::classify_story` (Haiku 4.5 + Pydantic structured-output; `CONFIDENCE_THRESHOLD = 0.7`)
- **Production refusal-guard under test:** `/Users/matthewnelson/seva-mining/scheduler/agents/juno_refusal_detector.py::call_with_refusal_guard` (7-pattern substring detector + retry-once-with-nudge + `(None, diag)` fallback)
- **Production orchestrator under test:** `/Users/matthewnelson/seva-mining/scheduler/agents/daily_summary.py::run_juno_daily_summary` (synthesis path; per-section try/except; status mapping per CONTEXT D-11/D-12)

---

*Phase 10 / Plan 04 / Wave 3 (Voice UAT) — DEF-10*
