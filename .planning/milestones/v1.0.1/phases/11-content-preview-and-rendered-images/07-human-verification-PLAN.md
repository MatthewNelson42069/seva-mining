---
phase: 11-content-preview-and-rendered-images
plan: 07
type: execute
wave: 4
depends_on: [11-04, 11-06]
files_modified:
  - .planning/ROADMAP.md
  - .planning/STATE.md
  - .planning/REQUIREMENTS.md
autonomous: false
requirements: [CREV-02, CREV-06, CREV-07, CREV-08, CREV-09, CREV-10]

must_haves:
  truths:
    - "Operator confirms end-to-end: approve an infographic bundle in staging, watch 4 rendered images appear in the modal within ~2 minutes"
    - "Operator confirms regen button triggers a fresh render that replaces images"
    - "Operator confirms silent-fail path: an invalid GEMINI_API_KEY results in brief-only display with no modal error and no WhatsApp alert"
    - "Operator confirms R2 public URLs actually serve the PNGs (HTTP 200 when clicked directly)"
    - "Operator confirms R2 bucket + public access are provisioned and the env vars match Railway settings"
    - "ROADMAP.md Phase 11 checkbox is marked complete; v1.0.1 milestone is fully landed"
    - "REQUIREMENTS.md CREV-06/07/08/09/10 are marked Complete in the traceability table"
    - "STATE.md is updated to reflect Phase 11 complete and v1.0.1 shipped"
  artifacts:
    - path: ".planning/ROADMAP.md"
      provides: "Updated Phase 11 status (complete) and milestone marker"
      contains: "[x] **Phase 11"
    - path: ".planning/STATE.md"
      provides: "Updated current_position to Phase 12 (if any) or v1.0.1 milestone complete"
  key_links:
    - from: ".planning/ROADMAP.md"
      to: "Phase 11 status + v1.0.1 milestone progress table row"
      via: "checkbox + Completed date"
      pattern: "Phase 11"
---

<objective>
Verify Phase 11 end-to-end against a live deploy (Railway backend + scheduler + Vercel frontend) and mark the v1.0.1 milestone shipped. This is the final gate — everything automated is green before we reach this plan; here the operator confirms that Imagen + R2 + the polling modal behave as designed on a real bundle.

Purpose: Close out the v1.0.1 milestone with operator sign-off per ROADMAP.md Phase 11 success criteria 1-6.

Output: Updated ROADMAP / STATE / REQUIREMENTS reflecting completion; any follow-up work logged as new quick tasks or Phase 11.1 candidates.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/REQUIREMENTS.md
@.planning/phases/11-content-preview-and-rendered-images/11-CONTEXT.md
@.planning/phases/11-content-preview-and-rendered-images/11-VALIDATION.md
@.planning/phases/11-content-preview-and-rendered-images/11-04-SUMMARY.md
@.planning/phases/11-content-preview-and-rendered-images/11-06-SUMMARY.md
</context>

<tasks>

<task type="auto" tdd="false">
  <name>Task 1: Deploy to staging + pre-checkpoint automated smoke</name>
  <files>
    (no files modified — runs deploy commands only)
  </files>
  <read_first>
    /Users/matthewnelson/seva-mining/.planning/phases/11-content-preview-and-rendered-images/11-01-SUMMARY.md,
    /Users/matthewnelson/seva-mining/.planning/phases/11-content-preview-and-rendered-images/11-04-SUMMARY.md,
    /Users/matthewnelson/seva-mining/.planning/phases/11-content-preview-and-rendered-images/11-06-SUMMARY.md
  </read_first>
  <action>
    Run a deploy-readiness preflight:
      1. Confirm migrations applied locally: `cd /Users/matthewnelson/seva-mining/backend && uv run alembic current | grep -q "0006"`
      2. Confirm all three suites pass:
         - `cd /Users/matthewnelson/seva-mining/backend && uv run pytest`
         - `cd /Users/matthewnelson/seva-mining/scheduler && uv run pytest`
         - `cd /Users/matthewnelson/seva-mining/frontend && npm run test -- --run`
      3. Confirm frontend builds: `cd /Users/matthewnelson/seva-mining/frontend && npm run build`
      4. Confirm backend + scheduler deps resolve: `cd backend && uv sync --all-extras` and `cd scheduler && uv sync --all-extras`

    If the user's Railway/Vercel workflow auto-deploys from main branch on merge, push the merge and wait for deploy confirmation. If deploys are manual, run:
      - Backend: `cd backend && railway up --service seva-mining-backend` (or equivalent based on Railway project config)
      - Scheduler: `cd scheduler && railway up --service seva-mining-scheduler`
      - Frontend: `cd frontend && vercel --prod` (or rely on Vercel's git integration)

    After deploys complete, tail Railway logs for both services and confirm startup logs:
      - Scheduler: "Scheduler worker started." + "ENV GEMINI_API_KEY: SET" (or equivalent log line added in Plan 01)
      - Backend: FastAPI uvicorn startup with no import errors
    If GEMINI_API_KEY or R2 env vars are missing from Railway settings, STOP and flag — the human must provision them before continuing.

    Record in the task output:
      - Backend deploy URL
      - Scheduler service uptime confirmation
      - Frontend deploy URL
      - Any env var warnings found in logs
  </action>
  <verify>
    <automated>cd /Users/matthewnelson/seva-mining/backend && uv run pytest && cd /Users/matthewnelson/seva-mining/scheduler && uv run pytest && cd /Users/matthewnelson/seva-mining/frontend && npm run test -- --run && npm run build</automated>
  </verify>
  <acceptance_criteria>
    - All three pytest/vitest suites pass
    - Frontend builds without error
    - Migration 0006 is applied locally
    - Logs (if accessible via Railway CLI) show both services started cleanly with GEMINI_API_KEY and R2_* vars present
    - Deploy URLs recorded in task output
  </acceptance_criteria>
  <done>
    Full test suite green, build clean, staging deploys live with correct env vars. Ready for human verification.
  </done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 2: Human verification — end-to-end on staging</name>
  <files>
    (no files modified — operator walks through the manual checks)
  </files>
  <read_first>
    /Users/matthewnelson/seva-mining/.planning/phases/11-content-preview-and-rendered-images/11-VALIDATION.md (§Manual-Only Verifications)
  </read_first>
  <what-built>
    The full Phase 11 stack is deployed:
    - Alembic migration 0006 applied to Neon
    - ContentAgent enqueues render jobs for infographic + quote bundles
    - image_render_agent generates Imagen 4 images and uploads to R2
    - Backend GET /content-bundles/{id} + POST /content-bundles/{id}/rerender endpoints live
    - Frontend ContentDetailModal with format-aware rendering + rendered images gallery + regen button
  </what-built>
  <how-to-verify>
    Walk through each of these five checks on the live staging environment. Record results in the plan SUMMARY.

    **Check 1 — Live Imagen render on a new infographic bundle (CREV-07 + CREV-08 + D-05)**
      1. Trigger the Content Agent manually (or wait for the next 2-hour cron tick) on staging.
      2. When the agent commits an infographic bundle, open the dashboard and click the Content queue card for that bundle.
      3. The modal should open immediately with the InfographicPreview showing headline + key_stats + caption (D-13 — brief renders before images).
      4. Within ~2 minutes, 4 rendered images should appear in the gallery: 1 twitter_visual + 3 instagram_slide_*.
      5. Visually confirm brand palette is present: cream background (#F0ECE4), navy text (#0C1B32), gold accents (#D4AF37).
      EXPECTED: 4 images appear within 2 min, brand colors visibly correct.
      FAIL → Check scheduler logs for render_bundle_job errors; inspect bundle.rendered_images in DB.

    **Check 2 — R2 public URLs serve PNGs (CREV-07 / D-06)**
      1. Right-click any rendered image in the modal → "Copy image address".
      2. Paste into a new browser tab in incognito mode (no auth).
      3. The PNG should load with HTTP 200.
      EXPECTED: PNG loads publicly.
      FAIL → R2 bucket public access is likely not enabled; visit Cloudflare Dashboard → R2 → bucket → Settings → Public access.

    **Check 3 — Regenerate button (CREV-09 / D-15, D-17)**
      1. On the same modal, click "Regenerate images".
      2. Skeletons should appear immediately; button becomes disabled.
      3. Within ~2 minutes, a NEW set of 4 images should replace the old ones.
      4. Old R2 objects should still be reachable via their original URLs (D-07 — timestamp suffix preserves old renders).
      EXPECTED: New images replace old ones; button re-enables when done.
      FAIL → Check backend logs for asyncio.create_task exception; check bundle.rendered_images state in DB.

    **Check 4 — Silent fail on invalid credentials (D-18, CREV-10)**
      1. Temporarily in Railway → scheduler service → env vars, set GEMINI_API_KEY="invalid-test-key" and redeploy.
      2. Trigger Content Agent run (or wait for next cron).
      3. A new infographic bundle should commit; the DraftItem should appear in the dashboard queue normally.
      4. Open the modal: brief renders; gallery shows skeletons then hides after ~10 minutes (or immediately if the bundle is already stale); NO error banner in the modal.
      5. Confirm Railway scheduler logs show ERROR-level lines from image_render_agent but no crash.
      6. Confirm no WhatsApp alert was sent about the render failure (D-18).
      7. RESTORE the real GEMINI_API_KEY and redeploy.
      EXPECTED: Silent-fail works; operator UX degrades gracefully; agent pipeline unaffected.
      FAIL → Render failure propagated OR WhatsApp alert was sent — indicates D-18 / D-19 violation.

    **Check 5 — Quote bundle (CREV-07, 2 images)**
      1. Wait for (or manually trigger via a test story) a quote bundle commit.
      2. Open the modal; confirm QuotePreview renders + 2 rendered images (twitter_visual + instagram_slide_1).
      EXPECTED: 2 images, not 4. Attribution and source_url visible.
      FAIL → Check ROLES_BY_FORMAT["quote"] in image_render_agent.py.

    **Optional sanity — 10-min polling ceiling (D-14)**
      1. Find a pre-Phase-11 infographic bundle (no rendered_images and created >10 min ago).
      2. Open its modal. Gallery should NOT show skeletons; only the "Regenerate images" button. Clicking it should start a fresh render.
      EXPECTED: Old bundles don't poll indefinitely; regen is the only path to backfill (D-14 + D-20).

    If ALL five checks pass, respond with "approved" and any notes. If any check fails, describe the issue; Claude will open a quick task or Phase 11.1 ticket to address.
  </how-to-verify>
  <resume-signal>Type "approved" to finalize Phase 11, or describe issues to surface fixes</resume-signal>
</task>

<task type="auto" tdd="false">
  <name>Task 3: Finalize — mark Phase 11 complete in ROADMAP / STATE / REQUIREMENTS</name>
  <files>
    .planning/ROADMAP.md,
    .planning/STATE.md,
    .planning/REQUIREMENTS.md
  </files>
  <read_first>
    /Users/matthewnelson/seva-mining/.planning/ROADMAP.md,
    /Users/matthewnelson/seva-mining/.planning/STATE.md,
    /Users/matthewnelson/seva-mining/.planning/REQUIREMENTS.md
  </read_first>
  <action>
    After Task 2 returns "approved", make these updates.

    In .planning/ROADMAP.md:
      1. Change `- [ ] **Phase 11: Content Preview and Rendered Images**` to `- [x] **Phase 11: Content Preview and Rendered Images**`
      2. In the progress table at the bottom, update the Phase 11 row:
         | 11. Content Preview and Rendered Images | 7/7 | Complete | 2026-04-{DD} |
         (use the actual completion date)
      3. Update the milestone section if relevant — the v1.0.1 line can be annotated with the completion date

    In .planning/REQUIREMENTS.md:
      Change these traceability rows from "Pending" to "Complete":
        | CREV-06 | Phase 11 | Complete |
        | CREV-07 | Phase 11 | Complete |
        | CREV-08 | Phase 11 | Complete |
        | CREV-09 | Phase 11 | Complete |
        | CREV-10 | Phase 11 | Complete |
      Also check the checkboxes in the CREV section (change `- [ ]` to `- [x]` for CREV-06..CREV-10).

    In .planning/STATE.md:
      1. Update `status:` frontmatter to "v1.0.1 complete" (or the user's chosen marker)
      2. Update `stopped_at:` to "Completed Phase 11 — v1.0.1 milestone shipped"
      3. Update `last_updated:` to the current ISO timestamp
      4. Update `progress:`:
         - total_plans: increment by 7 (current_total + 7)
         - completed_plans: increment by 7
         - completed_phases: increment by 1
      5. In `## Current Position`:
         - Phase: 12 (or "v1.0.2 TBD" or whatever the user's convention is — match the file's existing formatting)
         - Plan: Not started
      6. Append any new decisions Plan 01-06 recorded to the `### Decisions` section (read the per-plan SUMMARYs for Phase 11 decisions worth logging — e.g. "sys.path shim for backend→scheduler imports").

    Final commit:
      git add .planning/ROADMAP.md .planning/STATE.md .planning/REQUIREMENTS.md
      git commit -m "docs(11): Phase 11 complete — v1.0.1 milestone shipped"
      (use HEREDOC if needed; follow project commit pattern)
  </action>
  <verify>
    <automated>grep -c "\[x\] \*\*Phase 11" /Users/matthewnelson/seva-mining/.planning/ROADMAP.md && grep -c "CREV-10 | Phase 11 | Complete" /Users/matthewnelson/seva-mining/.planning/REQUIREMENTS.md</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "\[x\] \*\*Phase 11" /Users/matthewnelson/seva-mining/.planning/ROADMAP.md` returns 1
    - `grep -c "11\. Content Preview and Rendered Images | 7/7 | Complete" /Users/matthewnelson/seva-mining/.planning/ROADMAP.md` returns 1
    - `grep -c "CREV-06 | Phase 11 | Complete\|CREV-07 | Phase 11 | Complete\|CREV-08 | Phase 11 | Complete\|CREV-09 | Phase 11 | Complete\|CREV-10 | Phase 11 | Complete" /Users/matthewnelson/seva-mining/.planning/REQUIREMENTS.md` returns 5
    - `grep -c "v1.0.1" /Users/matthewnelson/seva-mining/.planning/STATE.md` returns ≥ 1
    - git log -1 shows the finalization commit
  </acceptance_criteria>
  <done>
    All three planning docs reflect Phase 11 complete. v1.0.1 milestone shipped.
  </done>
</task>

</tasks>

<verification>
- All three automated verify commands from Task 1 pass
- Operator confirmed all five manual checks in Task 2
- ROADMAP, STATE, REQUIREMENTS all reflect Phase 11 complete
- git log shows the completion commit
</verification>

<success_criteria>
- Staging deploy is live and serving the new endpoints + modal
- Operator has personally confirmed: live Imagen render, R2 URL reachability, regen flow, silent-fail behavior, quote bundle rendering
- All planning documents updated; milestone v1.0.1 officially shipped
</success_criteria>

<output>
Create `.planning/phases/11-content-preview-and-rendered-images/11-07-SUMMARY.md` capturing:
- Pass/fail result of each of the 5 human checks + any notes
- Any issues that surfaced, and links to follow-up tickets (quick tasks or Phase 11.1 candidates)
- Final per-plan timing summary
- Known limitations to flag in the RETROSPECTIVE.md for the v1.0.1 milestone
- Update/create a phase-level SUMMARY rollup that future phases can reference
</output>
