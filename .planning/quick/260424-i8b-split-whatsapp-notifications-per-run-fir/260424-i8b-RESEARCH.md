# Research — 260424-i8b (Split WhatsApp notifications)

**Researched:** 2026-04-24
**Scope:** Phase A — Stream 1 firehose (breaking_news + threads) + Stream 2 retime (morning → midday digest)
**Confidence:** HIGH on Q1/Q2/Q3 (direct code read). MEDIUM on Q4 (tweepy + X API public docs, for Phase B readiness only)

---

## Q1 — APScheduler async dispatch

**Findings (HIGH, from direct code read):**

- `scheduler/worker.py:320-327` uses `AsyncIOScheduler` with `job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 1800}`. All jobs registered via `add_job(...)` are async coroutines (`async def job():` closures at lines 221, 241). APScheduler 3.x `AsyncIOScheduler` natively awaits coroutine job functions — no `asyncio.run_coroutine_threadsafe` or thread wrapper needed.
- The canonical call site is `senior_agent.py:281`: `sid = await send_whatsapp_message(digest_message)` inside `run_morning_digest` (an async method). The `send_whatsapp_message` function (`services/whatsapp.py:35`) is itself async and uses `asyncio.to_thread(_send_sync, message)` at line 85 to offload the blocking Twilio SDK call to a thread pool — keeping the event loop unblocked during the ~500ms-2s Twilio HTTP round-trip.
- Both sub-agents we care about (`breaking_news.run_draft_cycle`, `threads.run_draft_cycle`) route through `run_text_story_cycle` in `scheduler/agents/content/__init__.py:83` — also async.

**Recommended pattern (Stream 1 dispatch):**

Pattern **(A) — direct `await`**, NOT `asyncio.create_task` (fire-and-forget).

Justification:
- The hook sits inside an already-async coroutine, so `await` is syntactically free.
- `send_whatsapp_message` already does the non-blocking work via `asyncio.to_thread` — the caller never actually blocks the event loop, it just cooperatively yields.
- Fire-and-forget via `create_task` would orphan the task if the agent_run's outer `async with AsyncSessionLocal()` exits before the Twilio send completes. The session/connection could be closed mid-send, and `notes` writes (see Q3 below) would either race or be lost.
- We already `await` in `senior_agent.py:281` — matching the pattern keeps one mental model.

**Code reference:** `scheduler/agents/senior_agent.py:281` (canonical `await send_whatsapp_message(...)` inside a try/except that writes `whatsapp_status` to `run.notes`). Copy this shape verbatim.

---

## Q2 — Twilio WhatsApp segmentation

**Native segmentation (MEDIUM, public Twilio docs):**

- **No native auto-segmentation for WhatsApp.** `smart_encoded` is an SMS-only flag (reduces Unicode-induced GSM-7 fragmentation for 160-char SMS segments). WhatsApp messages are a different transport: each `messages.create()` call = one WhatsApp message. Payloads above the 1600-char hard cap are rejected with error 63032 / 21617 — Twilio does NOT silently split.
- Meta/WhatsApp also independently caps body at 4096 chars for free-form conversational messages, but Twilio's own cap (1600 for free-form session messages) is the binding constraint for us.
- Receiver UX: N sequential `messages.create()` calls from the same `whatsapp:+14155238886` sandbox sender to the same `whatsapp:+...` recipient arrive as N distinct bubbles in the same conversation thread (one thread per sender-recipient pair). No grouping UI; ordering is best-effort — Twilio sends serially in call order, and in practice WhatsApp preserves that order at ≥99% reliability for same-minute bursts. The `[threads 1/2]` / `[threads 2/2]` prefix is the right mitigation for the rare reorder case.
- Rate-limit risk: Twilio sandbox is quoted at 1 msg/sec outbound; paid WhatsApp sender numbers scale to tier-dependent higher rates. At our firehose volume (max ~12 runs/day × max ~5 chunks = 60 msgs/day, never more than ~5 back-to-back), we are nowhere near the limit. No pacing/sleep needed between chunks — serial `await` is sufficient natural pacing.

**Chunking pseudocode (defensive — applies to breaking_news too, not just threads):**

```text
INPUT:
  agent_name: str                 # "sub_breaking_news" or "sub_threads"
  items: list[str]                # each item is the tweet text already extracted from draft_content
                                  #   - breaking_news: draft_content["tweet"] (single string per item)
                                  #   - threads: "\n\n".join(draft_content["tweets"])  # thread collapsed to one block per item
  max_chunk_chars: int = 1500     # 100-char safety margin below Twilio's 1600

PROCEDURE build_chunks(agent_name, items):
  short_name = agent_name.removeprefix("sub_")         # "breaking_news" | "threads"
  n = len(items)
  header = f"[{short_name}] {n} approved:"             # always used on the FIRST chunk

  # Pre-render each numbered item block. Never split one item across chunks.
  blocks = [f"{i}. {text}" for i, text in enumerate(items, start=1)]

  # Greedy pack: add blocks to the current chunk until the next block would overflow.
  chunks = []
  current = header                                     # first chunk carries the header
  for block in blocks:
      # +2 accounts for the "\n\n" separator between header/blocks
      tentative = current + "\n\n" + block
      if len(tentative) <= max_chunk_chars:
          current = tentative
      else:
          chunks.append(current)
          current = block                              # new chunk starts with the block (no repeat header)
  chunks.append(current)

  # Single-chunk case: no continuation prefix (per CONTEXT decision — simpler for common case).
  if len(chunks) == 1:
      return chunks

  # Multi-chunk case: prefix each chunk (including the first) with "[short_name X/N]\n".
  total = len(chunks)
  return [f"[{short_name} {i}/{total}]\n{c}" for i, c in enumerate(chunks, start=1)]

EDGE CASES:
  - Empty items list: caller MUST NOT invoke the helper (firehose rule: 0 items => 0 WhatsApp).
  - Single item > 1500 chars: theoretically possible for a thread if all 5 tweets × 280 chars join + decorations > 1500.
    Current threads prompt caps each tweet at <=280 chars × 5 tweets + "\n\n" separators = max ~1408 chars → fits.
    If a single block ever does exceed 1500, log a warning and send that one block in its own oversized chunk —
    Twilio will reject >1600, which will surface as a TwilioRestException handled by the outer try/except
    (treated as whatsapp_per_run_failed). Do NOT split an individual tweet across chunks.
  - Chunk header cost: "[threads 1/2]\n" = 14 chars. The 100-char safety margin below 1600 covers this comfortably.
```

**Sequential dispatch:**

```text
PROCEDURE send_agent_run_notification(agent_name, items, run_id):
  if not items: return []                              # defensive — should never happen
  chunks = build_chunks(agent_name, items)
  sids = []
  for chunk in chunks:
      sid = await send_whatsapp_message(chunk)         # awaits sequentially; None if creds missing
      if sid is None:                                  # credentials missing — bail, don't send remaining chunks
          return sids
      sids.append(sid)
  return sids
```

No `asyncio.gather` — sequential is correct (preserves order on the receiver, and if chunk 1 fails on a TwilioRestException we want to stop, not paper over the gap with chunk 2).

---

## Q3 — Senior agent observer hook

**Critical finding (HIGH, from direct code read):**

CONTEXT.md specifies the hook lives in `senior_agent.py`, but the actual execution path for `sub_breaking_news` and `sub_threads` runs **does not pass through `senior_agent.py` at all**. Those sub-agents complete inside `run_text_story_cycle` in `scheduler/agents/content/__init__.py:83`, which writes `agent_run.status = "completed"` and `agent_run.notes = json.dumps({"candidates": ...})` directly at lines 372-373, commits at line 380, and returns `items_queued`.

`senior_agent.py:run_morning_digest` is the Stream 2 path — completely independent. It reads draft_items *after the fact* for the digest; it never observes sub-agent completion in real time, and it never writes to `agent_runs.notes` for sub-agent rows (only for the `morning_digest` row itself, line 294).

**Implication:** The Stream 1 hook must live in `run_text_story_cycle` (or in a callback it invokes), NOT in `senior_agent.py`. The CONTEXT.md rationale ("matches the existing senior_agent.py responsibility for writing `whatsapp_sent` notes") is based on a misread of where the `whatsapp_sent` note-writing currently happens — that pattern exists ONLY for the morning_digest job. For sub-agent runs, the `notes` field today is a structured JSON telemetry blob (`{"candidates": N}`), not a WhatsApp status string.

**Recommended insertion point:**

**File:** `scheduler/agents/content/__init__.py`
**Function:** `run_text_story_cycle`
**Line:** After `agent_run.status = "completed"` at **line 373**, BEFORE the `except Exception` at line 374.

**Minimal diff shape:**

```text
# ... existing code at line 358-373 (agent_run.items_queued assignment + notes write + status) ...
agent_run.status = "completed"

# ---- Stream 1 per-run firehose (quick-260424-i8b) ----
# Only for breaking_news + threads, and only when items_queued > 0.
# Firehose contract: silent on empty runs. Append whatsapp_* status to the existing
# JSON notes blob (don't overwrite the candidates telemetry).
if agent_name in {"sub_breaking_news", "sub_threads"} and items_queued > 0:
    # Collect the tweet text from the draft_items just persisted this run.
    # Scope: draft_items where agent_run_id == agent_run.id. See "items source" note below.
    items_text = await _collect_run_item_texts(session, agent_run.id, content_type)
    try:
        sids = await whatsapp.send_agent_run_notification(
            agent_name=agent_name,
            items=items_text,
            run_id=agent_run.id,
        )
        if not sids:
            whatsapp_status = "whatsapp_per_run_skipped: credentials missing"
        else:
            whatsapp_status = f"whatsapp_per_run_sent: sids={','.join(sids)}"
    except Exception as exc:  # noqa: BLE001
        logger.error("%s: per-run WhatsApp dispatch failed: %s", agent_name, exc)
        whatsapp_status = f"whatsapp_per_run_failed: {type(exc).__name__}: {exc}"

    # Merge into existing notes JSON (which is already set above at line 362 or 372).
    existing = json.loads(agent_run.notes) if agent_run.notes else {}
    existing["whatsapp"] = whatsapp_status
    agent_run.notes = json.dumps(existing)
# ---- end Stream 1 ----

except Exception as exc:
# ... existing failure path unchanged ...
```

**Items source (the text for the WhatsApp body):**

The `items_text` list must be a list of strings — one per approved tweet in this run. Two viable paths, pick one in the plan:

1. **Query-based (cleaner):** After the loop, `SELECT draft_content FROM draft_items WHERE agent_run_id = :run_id ORDER BY id` and extract the tweet text per content_type (for `breaking_news`: `draft_content["tweet"]`; for `thread`: `"\n\n".join(draft_content["tweets"])`). Requires confirming `draft_items.agent_run_id` is populated — check `content_agent.build_draft_item` FK wiring.
2. **Accumulator (simpler, no extra query):** Maintain a local `persisted_items: list[str] = []` inside the `for story in candidates` loop; after `items_queued += 1` at line 326, append the extracted tweet text. Pass this list directly to `send_agent_run_notification`. No DB round-trip. **Recommended** — less surface area, matches the "minimal diff" goal.

**For the accumulator path:** The tweet text is available inline at the point of persist — `draft_content` is already in scope inside the loop. Extract it right before or after the `items_queued += 1` line (line 326) using the same format logic already present in `content_agent.build_draft_item` (line 602-619):

```text
# Inside the loop, right after items_queued += 1:
if agent_name in {"sub_breaking_news", "sub_threads"}:
    if content_type == "breaking_news":
        persisted_items.append(draft_content.get("tweet", ""))
    elif content_type == "thread":
        tweets = draft_content.get("tweets", [])
        persisted_items.append("\n\n".join(str(t) for t in tweets if t))
```

Then at the post-loop hook, pass `persisted_items` as `items_text`. No DB query needed.

**Does senior_agent.py need any changes?** No. Leave `run_morning_digest` alone for the Stream 1 work. Stream 2 only requires retiming in `worker.py` (7→12 hour + "0"→"30" minute + timezone already set) and tweaking the digest message prefix + job id in `senior_agent.py:run_morning_digest` (`📊 Morning Digest` → `🕛 Midday Digest`) — scope already locked in CONTEXT.md.

---

## Q4 — Phase B preflight (read-only notes)

For Phase B (approve → auto-post to X) — do NOT implement in this task. Notes for next session:

- **`tweepy.Client.create_tweet`** (tweepy 4.x, Python 3.11-compatible — signature stable across 4.14+): `client.create_tweet(text=..., in_reply_to_tweet_id=..., media_ids=..., reply_settings=...)`. Returns `Response(data={"id": "...", "text": "..."}, includes={}, errors=[], meta={})`. Extract posted-tweet ID via `response.data["id"]`. **OAuth 1.0a User Context required** for writes — bearer tokens are read-only on v2. Env vars needed: `X_API_KEY` (consumer key), `X_API_SECRET` (consumer secret), `X_ACCESS_TOKEN`, `X_ACCESS_TOKEN_SECRET`. Existing project env has `x_api_bearer_token` + `x_api_key` + `x_api_secret` (verified in `scheduler/worker.py:461-465`) — the two access-token vars will need to be added.
- **Thread chains:** Post tweet 1, capture `response.data["id"]`, pass it as `in_reply_to_tweet_id` on tweet 2, capture that ID, pass to tweet 3, etc. Post sequentially with a small delay (0.5-1s) between calls to avoid tripping the per-endpoint burst limiter.
- **Rate limits (X API Basic, $100/mo):** 100 tweet creates per 24h per app-user pair (hard cap, documented). 17 tweets per 15-min window per user (soft, burst). Given firehose volume of max 12 approved breaking_news + ~2 threads × 5 tweets/thread/day = ~22 creates/day, we are well under the 24h cap.
- **Media uploads:** `media_ids` on `create_tweet` requires a prior upload via tweepy's v1.1 `API.media_upload()` (v2 native media upload is still in limited preview). Mixed v1.1/v2 client setup — two `Client` / `API` instances with shared OAuth1 session. We ship no images in breaking_news/threads today, so defer until needed.
- **Gotcha:** `create_tweet` silently truncates or 400s on >280-char bodies — the drafter prompts already enforce <=280 but add a defensive assert in the poster.

---

## Pitfalls

- **Hook location mismatch with CONTEXT.md:** CONTEXT.md says "senior_agent.py observer pattern" but `sub_breaking_news` / `sub_threads` completions never flow through `senior_agent.py`. Planner must acknowledge this and either (a) land the hook in `content/__init__.py:run_text_story_cycle` as proposed here, or (b) introduce a new observer callback param to `run_text_story_cycle` implemented by a function in `senior_agent.py`. Option (a) is less indirection; option (b) matches the CONTEXT.md spirit but adds one layer. Recommend (a) with a comment referencing CONTEXT.md's intent.
- **`agent_run.notes` is currently JSON, not a string:** `run_text_story_cycle` writes `notes = json.dumps({"candidates": N})` at line 362/372, while `senior_agent.run_morning_digest` writes a plain `whatsapp_status` string at line 294. Do NOT copy the string-concatenation pattern — merge into the JSON dict instead (shown in Q3 diff). Future readers will thank you.
- **Session scope for `await send_whatsapp_message`:** The dispatch happens INSIDE the `async with AsyncSessionLocal() as session:` block. A Twilio outage that takes ~5-10s per chunk × 3 chunks = 30s held open. The session has no pending writes at that point (we already set `status`, `notes`, `items_queued`) — but the DB connection is held. Mitigation options: (i) accept the held connection for now (volumes are tiny, Neon's pool size is ample); (ii) split the `finally: await session.commit()` to commit EARLIER, then send WhatsApp with the session already closed and open a short-lived session only for the `notes` update. Option (i) is simpler and sufficient for current scale. If Twilio timeouts become a pattern, revisit.
- **Empty-run silence guarantee:** The hook must check `items_queued > 0` BEFORE building chunks. A run that drafted but had every item compliance-blocked will have `drafted_count > 0` but `items_queued == 0` — that's still a silent-run case (nothing approved-for-drafting to show). Use `items_queued`, not `drafted_count`.
- **Twilio sandbox 24h session window:** Free-form WhatsApp messages from the sandbox only reach the recipient if the recipient has messaged the sandbox number within the last 24h. If the user goes quiet for >24h, the sandbox silently drops messages (Twilio returns `status=queued` but delivery fails). Not a Phase A blocker — same failure mode as the existing morning_digest — but worth remembering: if Stream 1 WhatsApps start disappearing without errors, check sandbox session state before debugging code.

---

## RESEARCH COMPLETE

**File:** `/Users/matthewnelson/seva-mining/.planning/quick/260424-i8b-split-whatsapp-notifications-per-run-fir/260424-i8b-RESEARCH.md`
