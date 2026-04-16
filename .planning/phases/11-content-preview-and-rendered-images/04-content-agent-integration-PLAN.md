---
phase: 11-content-preview-and-rendered-images
plan: 04
type: execute
wave: 2
depends_on: [11-02]
files_modified:
  - scheduler/agents/content_agent.py
  - scheduler/tests/test_content_agent.py
autonomous: true
requirements: [CREV-07, CREV-10]

must_haves:
  truths:
    - "After ContentAgent commits an infographic or quote bundle with compliance_passed=True, a one-off DateTrigger job is registered on the module-level scheduler to run render_bundle_job(bundle_id) immediately"
    - "The enqueue happens AFTER session.commit() and AFTER compliance check passes — never before"
    - "Enqueue failures are caught and logged — they do NOT propagate and do NOT mark the bundle as failed (D-19)"
    - "Thread, long_form, breaking_news, video_clip, gold_history bundles do NOT trigger enqueue"
    - "The integration test asserts scheduler.add_job was called with id matching f'render_{bundle.id}' and replace_existing=True"
  artifacts:
    - path: "scheduler/agents/content_agent.py"
      provides: "ContentAgent with post-commit render enqueue for eligible bundles"
      contains: "render_bundle_job"
  key_links:
    - from: "scheduler/agents/content_agent.py"
      to: "scheduler.worker.get_scheduler"
      via: "late import inside enqueue helper"
      pattern: "from worker import get_scheduler"
    - from: "scheduler/agents/content_agent.py"
      to: "scheduler.agents.image_render_agent.render_bundle_job"
      via: "APScheduler DateTrigger job target"
      pattern: "render_bundle_job"
---

<objective>
Wire the ContentAgent to enqueue a background render job every time it commits an infographic or quote bundle that passed compliance. Never block the agent on render success/failure. Never enqueue for non-visual formats.

Purpose: Delivers CREV-07 (auto-rendering of infographic + quote) and CREV-10 (background execution independent of cron — agent returns fast, render runs separately).

Output: A single enqueue helper, three call sites in content_agent.py after the three bundle-commit locations (infographic path, quote path, video_clip path — but enqueue only fires for infographic/quote per D-04), plus integration tests covering all branches.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/phases/11-content-preview-and-rendered-images/11-CONTEXT.md
@.planning/phases/11-content-preview-and-rendered-images/11-RESEARCH.md
@.planning/phases/11-content-preview-and-rendered-images/11-02-SUMMARY.md
@.planning/phases/07-content-agent/07-CONTEXT.md
@CLAUDE.md

<interfaces>
<!-- render_bundle_job — Plan 02 -->
```python
# scheduler/agents/image_render_agent.py
async def render_bundle_job(bundle_id: str) -> None: ...
```

<!-- scheduler worker accessor — Plan 01 -->
```python
# scheduler/worker.py
def get_scheduler() -> AsyncIOScheduler: ...
```

<!-- content_agent.py commit sites (from current code) -->
```
Line ~1351–1395: infographic / standard format commit + build_draft_item
Line ~1430–1436: no_story / current_data fallback
Line ~1493–1507: video_clip bundle commit
Line ~1553–...: quote bundle commit
```

<!-- APScheduler DateTrigger pattern -->
```python
from datetime import datetime, timezone
from apscheduler.triggers.date import DateTrigger

scheduler.add_job(
    render_bundle_job,
    trigger=DateTrigger(run_date=datetime.now(timezone.utc)),
    args=[str(bundle.id)],
    id=f"render_{bundle.id}",
    name=f"Image render — bundle {bundle.id}",
    replace_existing=True,
)
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add _enqueue_render helper + wire all three commit sites</name>
  <files>
    scheduler/agents/content_agent.py,
    scheduler/tests/test_content_agent.py
  </files>
  <read_first>
    /Users/matthewnelson/seva-mining/scheduler/agents/content_agent.py (focus: lines 1340-1570 where bundles are committed),
    /Users/matthewnelson/seva-mining/scheduler/tests/test_content_agent.py,
    /Users/matthewnelson/seva-mining/scheduler/agents/image_render_agent.py,
    /Users/matthewnelson/seva-mining/scheduler/worker.py (get_scheduler function),
    /Users/matthewnelson/seva-mining/.planning/phases/11-content-preview-and-rendered-images/11-RESEARCH.md (§Pattern 1, §Pitfall 6)
  </read_first>
  <behavior>
    - Test 1 (test_commit_infographic_enqueues_render): When ContentAgent commits a bundle with content_type="infographic" and compliance_passed=True, scheduler.add_job is called once with id=f"render_{bundle.id}", args=[str(bundle.id)], and replace_existing=True.
    - Test 2 (test_commit_quote_enqueues_render): Same as above for content_type="quote".
    - Test 3 (test_commit_thread_does_not_enqueue): Bundle with content_type="thread" → scheduler.add_job NOT called.
    - Test 4 (test_commit_long_form_does_not_enqueue): Same for "long_form".
    - Test 5 (test_commit_breaking_news_does_not_enqueue): Same for "breaking_news".
    - Test 6 (test_commit_video_clip_does_not_enqueue): Same for "video_clip" (text-only per D-04).
    - Test 7 (test_commit_without_compliance_does_not_enqueue): Bundle with content_type="infographic" but compliance_passed=False → scheduler.add_job NOT called.
    - Test 8 (test_enqueue_failure_does_not_crash_agent): When get_scheduler() raises RuntimeError (e.g. scheduler not started in tests), ContentAgent completes its run without propagating the exception.
    - Test 9 (test_enqueue_uses_replace_existing_true): Asserts the replace_existing=True kwarg is passed, so a second rerender-triggered enqueue with the same job id doesn't raise ConflictingIdError (Pitfall 6).
  </behavior>
  <action>
    Add a single helper near the top of scheduler/agents/content_agent.py (after the existing imports — before the class definitions):

      _RENDER_FORMATS = {"infographic", "quote"}


      def _enqueue_render_job_if_eligible(bundle) -> None:
          """Fire-and-forget: schedule an immediate DateTrigger render job for eligible bundles.

          Eligible = compliance_passed=True AND content_type in {"infographic", "quote"} (D-04).
          Enqueue failures are swallowed — rendering is best-effort per D-19.
          """
          if not bundle.compliance_passed:
              return
          if (bundle.content_type or "").lower() not in _RENDER_FORMATS:
              return
          try:
              from datetime import datetime, timezone  # noqa: PLC0415
              from apscheduler.triggers.date import DateTrigger  # noqa: PLC0415
              from worker import get_scheduler  # noqa: PLC0415
              from agents.image_render_agent import render_bundle_job  # noqa: PLC0415
              scheduler = get_scheduler()
              scheduler.add_job(
                  render_bundle_job,
                  trigger=DateTrigger(run_date=datetime.now(timezone.utc)),
                  args=[str(bundle.id)],
                  id=f"render_{bundle.id}",
                  name=f"Image render — bundle {bundle.id}",
                  replace_existing=True,
              )
          except Exception as exc:  # never block the agent on render plumbing (D-19)
              import logging  # noqa: PLC0415
              logging.getLogger(__name__).warning(
                  "Failed to enqueue render job for bundle %s: %s", bundle.id, exc,
              )

    Now call this helper at EVERY location where a ContentBundle gets committed AFTER compliance is set. Use grep to locate every `session.add(bundle)` + subsequent `await session.commit()`/`await session.flush()` pair in content_agent.py (the canonical refs call out lines ~1351, ~1370, ~1380, ~1493, ~1553 — read the code to be sure).

    Specifically insert `_enqueue_render_job_if_eligible(bundle)` (or `_enqueue_render_job_if_eligible(vc_bundle)` / `_enqueue_render_job_if_eligible(q_bundle)` etc. matching the local variable name) AFTER the commit that persists each bundle AND after compliance_passed has been set on that bundle. If there is a single commit at end of a try-block that persists multiple bundles, call the helper for each bundle in the list.

    Do NOT insert the helper for the `build_no_story_bundle` path — those never have compliance_passed=True and never get rendered.

    In scheduler/tests/test_content_agent.py: Read existing tests to see mock patterns. Add 9 new tests implementing behaviors 1–9 above. For each test:
      - Patch `worker.get_scheduler` to return a MagicMock with an `.add_job` AsyncMock/MagicMock
      - Patch `agents.image_render_agent.render_bundle_job` to an AsyncMock (so the callable reference exists but never runs)
      - Call `_enqueue_render_job_if_eligible(mock_bundle)` directly with a lightweight bundle mock (don't spin up the full ContentAgent) — these are unit tests on the helper
      - Assert add_job call_count and kwargs

    Exception: Test 8 (enqueue failure) uses patch(get_scheduler, side_effect=RuntimeError("not started")) and asserts the helper returns None and does NOT raise.
  </action>
  <verify>
    <automated>cd /Users/matthewnelson/seva-mining/scheduler && uv run pytest tests/test_content_agent.py -v -k "enqueue or render"</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "_enqueue_render_job_if_eligible" /Users/matthewnelson/seva-mining/scheduler/agents/content_agent.py` returns ≥ 4 (definition + ≥ 3 call sites)
    - `grep -c "from worker import get_scheduler" /Users/matthewnelson/seva-mining/scheduler/agents/content_agent.py` returns 1 (inside helper, late import)
    - `grep -c "replace_existing=True" /Users/matthewnelson/seva-mining/scheduler/agents/content_agent.py` returns 1
    - `grep -c "_RENDER_FORMATS" /Users/matthewnelson/seva-mining/scheduler/agents/content_agent.py` returns ≥ 2
    - pytest reports 9 new tests PASSED (enqueue tests)
    - Full content_agent suite still passes: `cd scheduler && uv run pytest tests/test_content_agent.py -v` — no regressions on existing tests
  </acceptance_criteria>
  <done>
    _enqueue_render_job_if_eligible is defined and called at every bundle-commit site. Infographic and quote bundles enqueue; thread/long_form/breaking_news/video_clip do not. Enqueue failures are logged, not raised. Content agent tests stay green.
  </done>
</task>

</tasks>

<verification>
- `cd scheduler && uv run pytest -v` — full suite green
- Manual sanity: `grep -n "_enqueue_render_job_if_eligible" scheduler/agents/content_agent.py` should show the helper definition plus call sites at each bundle-commit location
- No import of `worker` at module top-level of content_agent.py (must be late-imported inside the helper to avoid circularity)
</verification>

<success_criteria>
- Eligible bundles (infographic, quote) always enqueue after commit
- Ineligible bundles never enqueue
- Compliance-failed bundles never enqueue
- Render enqueue failures never crash the agent
- All 9 new tests pass; existing content_agent tests remain green
</success_criteria>

<output>
Create `.planning/phases/11-content-preview-and-rendered-images/11-04-SUMMARY.md` noting:
- Exact call sites where _enqueue_render_job_if_eligible was inserted (line numbers)
- Any bundle-commit site NOT wired (and why — e.g. no_story_flag path)
- Test coverage: how many ContentAgent tests now exercise the enqueue path
- Any circular-import gotchas encountered (late-import is the fix)
</output>
