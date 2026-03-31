# Pitfalls Research

**Domain:** AI social media monitoring and engagement drafting system (gold sector)
**Researched:** 2026-03-30
**Confidence:** HIGH (critical pitfalls verified across multiple sources; integration-specific items HIGH from official docs)

---

## Critical Pitfalls

### Pitfall 1: X Basic API — 10,000 Tweet Monthly Cap Is Exhausted in Days

**What goes wrong:**
The X Basic tier ($100/mo) provides 10,000 tweet reads per month. A 2-hour monitoring cycle running across multiple keyword/cashtag/hashtag searches can consume this quota in 3-5 days if not carefully budgeted. The system then goes dark for the remainder of the month with no Twitter signal.

**Why it happens:**
Developers plan for "searches" without calculating actual tweet read volume. Each search result counts as individual tweet reads against the monthly cap. Monitoring a live market event (gold price spike, FOMC announcement) with event mode enabled at 8-10 posts can burn hundreds of reads in a single cycle.

**How to avoid:**
- Budget the cap explicitly before writing a single line: assume 2,000 tweets/week (rough ceiling), leaving headroom for event mode bursts.
- Implement a monthly quota tracker in the database. Track reads consumed and reads remaining via the `X-Rate-Limit-Remaining` response header.
- Hard-stop the Twitter Agent when monthly remaining falls below 500 — surface this as a dashboard alert and WhatsApp notification, not a silent failure.
- Deduplicate tweet IDs in the database so re-runs at the same cycle do not re-fetch already-seen tweets.
- During event mode (3x spike or gold price movement), cap the run at a configurable tweet fetch limit (e.g., 150 tweets per event run) to prevent burst exhaustion.

**Warning signs:**
- Twitter Agent returning empty queues more than one cycle without other error — likely 429 (Too Many Requests)
- Monthly cap exhaustion mid-month appearing in agent run logs
- Dashboard showing Twitter items drying up abruptly mid-month

**Phase to address:** Twitter Agent phase (early). The budget model must be built before any production monitoring begins. Cap tracking and dashboard alerting for quota status must ship with the Twitter Agent, not as a later addition.

---

### Pitfall 2: Instagram Apify Scraper Returns Partial or Empty Results Without Errors

**What goes wrong:**
Apify's Instagram scraper frequently returns partial datasets — fewer posts than requested, truncated hashtag results, or silently empty runs — without raising an error code. The system interprets this as "nothing relevant today" rather than "scraper was throttled or blocked." The Instagram Agent queue stays empty not because the gold conversation is quiet, but because Instagram's anti-bot system silently degraded the scrape.

**Why it happens:**
Instagram employs session-based tracking and behavioral analysis that reduces data returned to suspected bots gradually rather than hard-blocking them. The platform throttles aggressively after detecting patterns — frequent runs against the same hashtags, consistent proxy fingerprints, or unusual timing. Apify actors can return HTTP 200 with empty arrays when Instagram withholds data.

**How to avoid:**
- Implement a result-count sanity check: if an actor run returns 0 posts for a hashtag that historically returns 20+, flag it as a potential scraper health issue, not a silent success.
- Store baseline post counts per hashtag per run in the database. A drop to zero for two consecutive runs should trigger a WhatsApp alert.
- Stagger Instagram scraping runs — vary start times by ±15 minutes across cycles to avoid predictable timing fingerprints.
- Follow Apify's official guidance: use managed proxy pools (Apify residential proxies), not datacenter IPs. The Actor's README specifies the correct proxy configuration.
- Keep Apify Actor versions pinned and update deliberately — Instagram layout changes break specific Actor versions silently.
- Build retry logic with exponential backoff into the Instagram Agent: if a run returns 0 results, retry once at +2h before logging as empty.

**Warning signs:**
- Instagram Agent returns 0 items for multiple consecutive cycles without system errors
- Run logs show actor completing successfully but with empty `results` arrays
- Account watchlist items that previously produced consistent results suddenly go quiet

**Phase to address:** Instagram Agent phase. Scraper health monitoring must be designed in, not retrofitted. The retry logic and baseline-comparison alert belong in the initial build, not v2.

---

### Pitfall 3: Claude Drafts Violate the "No Financial Advice" and "No Seva Mention" Rules Despite Prompt Instructions

**What goes wrong:**
Claude generates drafts that subtly imply price direction ("this typically precedes a breakout"), reference the company indirectly ("accounts covering the gold space like ours"), or use soft buy/sell signals dressed as analysis ("gold bulls will be watching this level closely"). These drafts pass the agent's self-evaluation because the prompt constraints are stated but not enforced structurally. Over time, as prompts are iteratively modified, constraint language weakens or edge cases accumulate.

**Why it happens:**
Constraint violations in LLM outputs are probabilistic, not deterministic. Even well-crafted system prompts with explicit prohibitions will fail on some percentage of outputs — especially for nuanced constraints like "no implied financial advice" versus "no explicit buy/sell signals." Claude 3.x/4.x models take instructions literally; if constraints are in the system prompt but not re-stated in the scoring rubric with concrete examples, the model interprets borderline cases charitably.

**How to avoid:**
- Build a structured self-evaluation step that runs after draft generation — a second Claude call acting as a compliance checker against a concrete rubric (not the same prompt that generated the draft).
- Define the "no financial advice" constraint with explicit examples of violations: "examples of forbidden phrasing include: 'gold looks bullish here,' 'support at $X,' 'accumulation signal,' 'this could be a buying opportunity.'"
- Define the "no Seva mention" constraint with examples: "Seva Mining, @sevamining, 'our company,' 'we cover this space' — all forbidden."
- Track violations in the agent run log. If the compliance checker rejects more than 2 drafts in a single run, surface as an alert — it signals a prompt degradation or edge-case accumulation.
- Never modify the compliance checker prompt without a deliberate review. Treat it as a system constraint, not a tunable parameter.

**Warning signs:**
- Compliance checker rejection rate increasing over time in run logs
- Approved drafts accumulating in the dashboard that feel "investment-advice-adjacent" on review
- Self-evaluation quality score (7.0+ threshold) inflating — model learning to approve its own constraint violations

**Phase to address:** Content Agent and Twitter/Instagram Agent phases. The compliance checker must be built into the initial draft pipeline, not added after the first problematic draft surfaces. Scoring rubric with concrete examples belongs in the Phase 1 architecture.

---

### Pitfall 4: APScheduler in a Multi-Worker Environment Causes Duplicate Agent Runs

**What goes wrong:**
If the Railway backend ever runs with more than one process (Gunicorn workers, autoscaling replicas, or a deploy that briefly runs two instances during rollover), APScheduler runs in each process independently. The Twitter Agent fires twice simultaneously — two identical sets of API calls, two duplicate queues, two sets of drafts. The database receives duplicate items that the deduplication logic was not designed to handle because they arrive at the same millisecond.

**Why it happens:**
APScheduler has no interprocess synchronization. It does not know other processes exist. The project design correctly isolates the scheduler in a separate Railway worker process, which mitigates this — but Railway's deployment model can briefly run two overlapping instances during zero-downtime deploys. The scheduler process is already separated, but the risk exists in the scheduler process itself if it ever scales horizontally.

**How to avoid:**
- The separate scheduler worker (already in project design) is the correct mitigation — do not run APScheduler inside the FastAPI API process.
- Configure Railway to run the scheduler worker with exactly 1 replica and disable autoscaling for that service. Document this explicitly in deployment config.
- Add a database-level job lock: before any agent run, write a `job_running` row with a TTL. If the lock exists, skip the run and log "skipped: lock held." This is the final safety net for overlapping deploys.
- If the scheduler worker ever needs to be replaced by a more robust solution, ARQ (Redis-backed, async-native) is the right upgrade path — it was designed for this exact problem.

**Warning signs:**
- Duplicate items appearing in the approval queue with identical source URLs
- Agent run logs showing two overlapping runs at the same timestamp
- Railway deploy logs showing two scheduler worker instances simultaneously active

**Phase to address:** Infrastructure/scheduler phase. The job lock mechanism must be part of the initial scheduler design. The Railway replica constraint must be in the deploy configuration from day one.

---

### Pitfall 5: Content Quality Drift — The 7.0 Quality Threshold Becomes Meaningless Over Time

**What goes wrong:**
The self-evaluation rubric starts calibrated to produce content 4-5 days per week. Over weeks of operation, the scoring prompt subtly drifts: examples in the prompt age, gold sector context in the system prompt becomes stale, or iterative prompt tuning to "get more stories" lowers the effective bar without explicitly changing the 7.0 threshold. The dashboard fills with mediocre drafts that technically score 7.1 but wouldn't stop a senior gold analyst scrolling.

**Why it happens:**
LLM self-evaluation is not a static function — the same rubric produces different score distributions as the model encounters different input distributions, prompt modifications accumulate, or the surrounding system prompt changes. There is no objective anchor keeping "7.0" pegged to actual quality. The model can also learn to be lenient with itself when the user repeatedly approves borderline content.

**How to avoid:**
- Store the quality score and rationale for every draft in the database permanently (schema already plans for this).
- Build a weekly calibration check: what percentage of drafts scored above 7.0? What percentage were approved vs. rejected by the user? If approval rate drops below 50% on 7.0+ drafts, the rubric is inflated — surface this in the Settings page.
- Include 3-5 concrete "gold standard" example stories in the scoring prompt that cannot be modified without deliberate review. These serve as anchors.
- Add a "no story today" flag path that is frictionless to trigger — if producing a weak story is easier than flagging no story, the quality bar will erode from the path of least resistance.

**Warning signs:**
- Approval rate in the dashboard falling week-over-week while queue volume holds steady
- Stories that score 7.5+ on the rubric but feel thin, generic, or recycled on human review
- "No story today" flag never triggering across multiple weeks

**Phase to address:** Content Agent phase. The approval-rate tracking and calibration mechanism must ship with the Content Agent, not as a v2 analytics feature. The quality rubric anchor examples belong in the initial prompt design.

---

### Pitfall 6: Twilio WhatsApp — Sandbox Testing Masks Production Template Requirements

**What goes wrong:**
Development and testing proceed entirely in the Twilio Sandbox, where free-form messages work without restriction. The system is built, tested, and considered "done." On switch to production, Meta requires all business-initiated messages (morning digest, breaking alerts, expiring draft alerts) to use pre-approved message templates. Every notification type must be templated and approved by Meta before it can be sent, which takes days. The go-live is blocked.

**Why it happens:**
The Twilio Sandbox deliberately relaxes template requirements to speed up development. It uses a shared Twilio number, accepts free-form messages, and sends to any user who has joined the sandbox with a keyword. None of this reflects production behavior for business-initiated messages outside the 24-hour customer service window — which is the exact scenario for scheduled digests and alerts.

**How to avoid:**
- Design all three notification types (morning digest, breaking alert, expiring draft alert) as WhatsApp message templates from the start, even in development. Template structure constrains what dynamic content can be included — design the notification content around template constraints, not the reverse.
- Submit templates for Meta approval during the earliest infrastructure phase, not at the end. Approval takes 1-7 business days and cannot be expedited.
- In development, test the exact template format in the sandbox before submission — sandbox does accept templates and this catches formatting issues early.
- The single-user system (Seva Mining owner) has already opted in by design; document this opt-in proof per Meta's requirements at setup.

**Warning signs:**
- Notification system tested end-to-end only in Sandbox mode
- No Meta-approved message templates in the Twilio console before go-live
- Template variables (dynamic content like date, score, post title) not defined before approval submission

**Phase to address:** Infrastructure phase (alongside Twilio setup). Template design and Meta submission must happen in the first working sprint — not after the notification logic is built.

---

### Pitfall 7: Agent Handoff Context Loss — Senior Agent Deduplication Loses Cross-Platform Story Linking

**What goes wrong:**
The Senior Agent is responsible for deduplicating the same story across platforms (Twitter item and Instagram item about the same gold price event should be visually linked as "related" in the dashboard). This requires the Senior Agent to compare semantic similarity of items arriving from different agents on different cycles. Without explicit context passing and a stored story fingerprint, items arrive as isolated records. The "related" linking never works reliably and is silently dropped because it "mostly works."

**Why it happens:**
Multi-agent systems fail most often at handoff points. Each agent (Twitter, Instagram, Content) produces items with its own schema. The Senior Agent must normalize these into a comparable format, extract a story fingerprint (e.g., the core claim or event), and match against recently-queued items. This matching logic is subtle — a Twitter post about "gold hits $2,800" and an Instagram post about "gold price surge" should match. String matching won't work. Without a deliberate design for this, it gets implemented as fuzzy string similarity that fails on paraphrase.

**How to avoid:**
- The Senior Agent should extract a structured "story fingerprint" using Claude — a normalized event descriptor (e.g., `{event: "gold price", direction: "increase", level: "$2800"}`) for each incoming item. Store this in a JSONB column.
- Deduplication matching runs against fingerprints of items queued in the last 24h (Twitter) / 48h (Instagram), not against full text.
- Define "related" vs "duplicate" explicitly: same story, different platform = related (both cards shown, visually linked); same story, same platform within 2h = duplicate (second card dropped with log note).
- If Claude's fingerprint extraction fails or returns low-confidence output, fall back to queuing both items without the "related" link — never silently drop an item because deduplication was uncertain.

**Warning signs:**
- Related items appearing as completely unlinked cards on the dashboard
- Deduplication logic running but "related" field always empty in the database
- Senior Agent logs showing high drop rates due to "duplicate" classification that are actually different stories

**Phase to address:** Senior Agent / orchestration phase. Story fingerprint schema and extraction logic must be designed before building the queue management system — retrofitting this after the queue is built requires schema changes and logic rewrites.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Hardcoded scoring weights instead of Settings page | Faster initial build | Every threshold change requires a code deploy, not a settings change | Never — Settings page is a core requirement |
| Single monolithic Claude prompt per agent instead of chained generation + evaluation | Simpler code | Constraint violations (financial advice, Seva mention) catch rate degrades; no audit trail per step | Never for compliance-sensitive drafts |
| Skipping monthly quota tracking for X API | Saves a few DB columns | Twitter Agent silently goes dark mid-month; no alerting | Never — quota exhaustion is a primary failure mode |
| Storing only the approved draft alternative, not all alternatives | Smaller DB payload | Cannot analyze which alternative types get approved; learning loop has no data | Acceptable only if learning loop is explicitly deferred |
| Using APScheduler inside the FastAPI process instead of separate worker | Fewer Railway services | Crash coupling, duplicate execution risk | Never — already identified as architecture decision |
| Skipping Twilio WhatsApp template approval until launch | Faster development | Go-live blocked by Meta's approval queue (1-7 days) | Never — submit templates in Phase 1 infrastructure |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| X Basic API | Counting "searches" instead of "tweet reads" in quota planning | Count every tweet ID returned across all search results against the 10,000 monthly cap; budget by tweet reads not search calls |
| X Basic API | Not reading `X-Rate-Limit-Remaining` response headers | Parse headers on every response, persist remaining count to DB, alert at threshold |
| Apify Instagram | Treating 0-result run as valid empty signal | Baseline-compare results per hashtag/account; flag zero-result runs as scraper health events requiring investigation |
| Apify Instagram | Using Actor version pinning on the wrong version | Pin to the latest stable version at build time; review Apify changelog before updating — Instagram layout changes break specific versions |
| Claude API | Drafting and self-evaluating in the same prompt | Separate generation and evaluation into two distinct API calls with independent prompts; the evaluator must not see its own draft generation logic |
| SerpAPI | Not tracking hourly quota cap separately from monthly | SerpAPI enforces a 20% hourly cap on monthly quota; monitor both dimensions; batch Content Agent news searches to avoid hourly bursts |
| SerpAPI | Making duplicate search calls for overlapping keywords | Deduplicate keyword searches; cache results for 30 minutes before re-querying the same term |
| Twilio WhatsApp | Building notification logic around Sandbox free-form messages | Design all notifications as templates from day one; sandbox accepts templates too — test the template format before submission |
| Neon PostgreSQL | Assuming free-tier 512MB is ample if keeping all data forever | "Keep all data forever" with JSONB draft alternatives accumulates fast; monitor storage with a dashboard metric; budget the $19/mo Pro upgrade as an expected Phase 2 cost |
| Railway scheduler worker | Assuming Railway zero-downtime deploys prevent overlap | Configure scheduler worker replica count to exactly 1, disable autoscaling; add DB-level job lock as defense-in-depth |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Full-table scan for deduplication on every Senior Agent run | Senior Agent run time growing from 2s to 30s+ as queue grows | Index on `(source_url, platform, created_at)` and `(story_fingerprint_hash)`; query only last 24-48h window | After ~5,000 queue items (a few months of operation) |
| Fetching all pending items for the dashboard on every page load | Dashboard load time increasing as queue grows; React re-renders on every approval | Paginate approval queue; use database-side filtering for status; WebSocket or polling only for new item count badge | After ~500 pending items simultaneously |
| Claude API calls in a synchronous request-response loop on the scheduler | Agent run blocking until all Claude calls complete; scheduler timeout risks | Make Claude calls async; process items in parallel batches (not one-by-one); set per-call timeout with fallback | Immediately on event mode runs (8-10 posts = 8-10 sequential Claude calls) |
| Storing full post text + all alternatives as duplicated columns instead of JSONB array | Schema bloat, migration complexity if alternative count changes | Use JSONB array for alternatives (already in project design); do not add `alternative_1`, `alternative_2`, `alternative_3` columns | Schema becomes unmaintainable if alternative count varies by agent |
| Re-scraping Apify on every scheduler tick without caching seen post IDs | Redundant Apify runs burning monthly quota on already-processed posts | Store scraped post IDs with timestamp; skip on re-scrape if seen within the 8h window | Immediately — Apify charges per result, not per run |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Storing X API key, Apify key, Anthropic key, Twilio credentials, SerpAPI key in the repository or in plain environment variables without a secrets manager | Full API key exposure if repo is ever made public or Railway environment is misconfigured | Use Railway's environment variable secrets for all API keys; never commit `.env` files; document which vars are required without exposing values |
| Using the same password hash algorithm as a quick implementation (e.g., MD5, SHA-1) for single-user dashboard auth | Password compromise if the database is ever exposed | Use bcrypt for the single password hash; the simplicity of single-user auth doesn't justify weak hashing |
| Exposing raw Claude prompts (including quality rubric and scoring weights) via the Settings API | Prompt injection attacks; users could craft social media posts designed to manipulate the scoring rubric | Settings API should expose threshold numbers only, not prompt text; prompt text lives in server-side code only |
| Not rate-limiting the dashboard API | Brute-force attacks on the single-user password endpoint | Even for a single-user system, rate-limit `/auth/login` to 5 attempts per 15 minutes; log failed attempts |
| WhatsApp notification content including post excerpts with unescaped special characters | Message delivery failures; potential template rejection by Meta | Sanitize all dynamic content inserted into WhatsApp templates; test edge cases (quotes, unicode, long text) in sandbox before production |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Approval card inline editor opens in a modal that loses context of the original post | User has to close editor, re-read original post, reopen editor when making substantive edits | Side-by-side layout: original post stays visible while draft is editable in the same card |
| No visual distinction between "Twitter: reply" and "Twitter: retweet-with-comment" alternatives in the same card | User accidentally copies the reply text when intending to retweet, or vice versa | Explicit tab labels ("Reply" / "Retweet+Comment") within each card; tab state persists until card is acted on |
| Rejection reason field is optional | Over time, rejected items have no signal for what went wrong; learning loop has no data | Make rejection reason mandatory — a short dropdown (Off-brand / Low quality / Not relevant / Financial advice risk / Other) with optional free text |
| Dashboard shows score as a raw number (e.g., 7.4) without context | User cannot tell if 7.4 is good or if the rubric has inflated | Show score with its component breakdown (relevance, originality, tone, compliance) on hover/expand; show weekly average score in the header |
| Expiry countdown is not visible on cards approaching expiration | High-value draft expires while user is reviewing lower-priority items | Show a color-coded urgency indicator (green → yellow → red) on cards within 2h of expiry; sort expired-soon to the top of queue |
| WhatsApp digest arrives but links to the post require the user to open the dashboard to act | User reads the digest on mobile but cannot take action without switching to desktop | Morning digest should include direct platform URLs (Twitter/Instagram link) so user can at minimum read the source post on mobile; dashboard link is secondary |

---

## "Looks Done But Isn't" Checklist

- [ ] **Twitter quota tracking:** Agent can fetch tweets without hitting 429 — verify that monthly cap counter is being decremented correctly, not just that the API responds successfully
- [ ] **Instagram scraper health:** Apify runs show "completed" in logs — verify that result counts are being compared against baselines, not just that the actor finished without error
- [ ] **Claude compliance checks:** Draft quality scores above 7.0 — verify that the separate compliance checker (financial advice, Seva mention) is running as a second Claude call, not baked into the scoring prompt
- [ ] **WhatsApp production:** Notifications are received in sandbox — verify that Meta has approved message templates and production sender is configured, not just that sandbox messages arrive
- [ ] **Senior Agent deduplication:** Queue shows items from both Twitter and Instagram — verify that "related" linking is functioning with story fingerprints, not just that duplicates are being dropped
- [ ] **Rejection reason tracking:** Reject button works — verify that rejection reason is required and stored before the card is dismissed, not just that the state machine transitions correctly
- [ ] **APScheduler single-replica:** Scheduler worker starts and runs jobs — verify that Railway is configured with `replicas: 1` and autoscaling is disabled for that service
- [ ] **SerpAPI hourly cap:** Daily news searches complete — verify that the agent is not consuming more than 20% of monthly quota in a single hour across its scheduled runs
- [ ] **Expiry auto-archival:** Expired items are removed from the queue view — verify that the Senior Agent's expiry logic is running and marking items as `expired` status, not just hiding them client-side
- [ ] **Settings page writes:** Scoring weights can be changed in the UI — verify that changed weights are actually used in subsequent agent runs, not cached in-memory from startup

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| X API monthly quota exhausted mid-month | MEDIUM | Surface outage via dashboard banner and WhatsApp alert; switch to "news-only" mode (Content Agent continues, Twitter Agent pauses); resume at month reset; post-mortem to tighten query efficiency |
| Instagram scraper blocked / degraded for extended period | MEDIUM | Alert via dashboard; switch Instagram Agent to reduced frequency (once per 12h instead of 4h); open Apify support ticket; worst-case, gold sector Instagram monitoring is paused without total system failure |
| Claude compliance checker producing high rejection rates (prompt degradation) | LOW-MEDIUM | Roll back the evaluator prompt to last known-good version (keep prompt versions in code as named constants, not inline strings); re-run the failed batch manually |
| Twilio WhatsApp template rejected by Meta | LOW | Resubmit with revised template copy; notifications fall back to silence (system still operates, user just doesn't receive WhatsApp alerts); estimated re-approval: 1-3 days |
| APScheduler duplicate run causing duplicate queue items | LOW | Idempotency key on `(source_url, platform, created_at_hour)` allows cleanup with a single SQL deduplication query; implement DB job lock going forward |
| Neon free tier storage filled (512MB) | LOW | Upgrade to Neon Pro ($19/mo); no data loss; no architecture change; cost was pre-identified as expected |
| Quality rubric inflation (approval rate decline) | MEDIUM | Review last 30 days of rejection reasons; recalibrate rubric examples; this is a weekly calibration activity, not a crisis — only becomes HIGH cost if ignored for months |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| X API monthly quota exhaustion | Twitter Agent phase | Monthly cap counter exists in DB; dashboard shows remaining quota; hard-stop logic tested against mock 429 response |
| Instagram partial/silent scraper failure | Instagram Agent phase | Baseline-comparison alert fires on a simulated zero-result run; retry logic tested |
| Claude compliance violations (financial advice, Seva mention) | Content Agent phase + Twitter/Instagram Agent phase | Compliance checker runs as separate call in all three agents; tested with deliberately violating input |
| APScheduler duplicate execution | Infrastructure/scheduler phase | Railway config has replicas: 1 for scheduler service; DB job lock implemented and tested |
| Content quality threshold drift | Content Agent phase | Approval-rate tracking in DB; Settings page shows weekly approval rate; calibration path documented |
| Twilio WhatsApp template requirements | Infrastructure phase (Phase 1) | Meta template approval confirmed before notification logic build starts |
| Senior Agent story fingerprint / cross-platform deduplication | Senior Agent / orchestration phase | Related item linking tested with synthetic matching scenarios; fingerprint schema in DB |
| APScheduler inside API process (not separate worker) | Architecture decision (already decided correctly) | Verify Railway deploy config has two separate services: API and scheduler-worker |
| SerpAPI hourly quota burst | Content Agent phase | Hourly consumption logged per run; alert fires if single run exceeds 20% of monthly quota |
| Rejection reason not captured | Dashboard / approval workflow phase | Rejection action blocked at DB level if reason field is null |
| WhatsApp Sandbox masking production template requirements | Infrastructure phase | Template submitted to Meta before notification feature is considered "done" |

---

## Sources

- X API Basic tier limits and rate limiting: [Twitter API Limits Complete Guide 2025](https://www.gramfunnels.com/blog/twitter-api-limits) | [X API Pricing Tiers 2025](https://twitterapi.io/blog/twitter-api-pricing-2025)
- Instagram scraping pitfalls and Apify anti-detection: [Apify — How to scrape Instagram without getting blocked](https://blog.apify.com/scrape-instagram-python/) | [Apify Instagram Scraper official](https://apify.com/apify/instagram-scraper) | [Apify rate limiting docs](https://docs.apify.com/academy/anti-scraping/techniques/rate-limiting)
- APScheduler + FastAPI production pitfalls: [Common APScheduler mistakes in Python applications](https://sepgh.medium.com/common-mistakes-with-using-apscheduler-in-your-python-and-django-applications-100b289b812c) | [APScheduler FAQ — interprocess synchronization](https://apscheduler.readthedocs.io/en/3.x/faq.html) | [Building Resilient Task Queues in FastAPI with ARQ](https://davidmuraya.com/blog/fastapi-arq-retries/)
- Claude API prompt engineering pitfalls: [Anthropic Claude prompting best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices) | [Claude Prompt Engineering Best Practices 2026](https://promptbuilder.cc/blog/claude-prompt-engineering-best-practices-2026)
- AI agent hallucination and quality drift: [Ensuring Reliability in AI Agents: Preventing Drift and Hallucinations in Production](https://medium.com/@kamyashah2018/ensuring-reliability-in-ai-agents-preventing-drift-and-hallucinations-in-production-4b8f8600ec69) | [7 Common Pitfalls in AI Agent Deployment](https://www.getmaxim.ai/articles/7-common-pitfalls-in-ai-agent-deployment-and-how-to-avoid-them/)
- Multi-agent orchestration handoff failures: [AI Agent Orchestration Patterns — Azure Architecture Center](https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/ai-agent-design-patterns) | [Multi-Agent AI Systems Key Insights 2025](https://key-g.com/blog/multi-agent-ai-systems-in-2025-key-insights-examples-and-challenges/)
- Twilio WhatsApp sandbox vs. production: [Test WhatsApp messaging with the Sandbox — Twilio](https://www.twilio.com/docs/whatsapp/sandbox) | [Rules and Best Practices for WhatsApp Messaging on Twilio](https://support.twilio.com/hc/en-us/articles/360017773294-Rules-and-Best-Practices-for-WhatsApp-Messaging-on-Twilio) | [WhatsApp sender message limits and quality rating](https://support.twilio.com/hc/en-us/articles/360024008153-WhatsApp-Rate-Limiting)
- SerpAPI quota and hourly caps: [Overcome SerpAPI's hourly quota caps](https://blog.apify.com/best-serpapi-alternatives/) | [Mastering SERP API Limitations and Challenges](https://www.serphouse.com/blog/serp-api-limitations/)
- Financial content AI legal risk and compliance: [AI Governance in Financial Services — FINRA & SEC Guidance](https://www.smarsh.com/blog/thought-leadership/ai-governance-expectations-are-rising-even-without-rules) | [SEC Risk Alert: Investment Adviser Use of Social Media](https://www.sec.gov/about/offices/ocie/riskalert-socialmedia.pdf)

---
*Pitfalls research for: AI social media monitoring and engagement drafting system — gold sector*
*Researched: 2026-03-30*
