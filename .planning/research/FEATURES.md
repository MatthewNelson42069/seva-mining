# Feature Research

**Domain:** AI social media monitoring and engagement drafting system (single-operator, niche industry)
**Researched:** 2026-03-30
**Confidence:** HIGH (core features), MEDIUM (differentiators specific to niche sector)

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features the operator will assume exist from day one. Missing these makes the system feel broken or unusable.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Keyword / hashtag / cashtag monitoring | Core premise of the product — no monitoring = no system | MEDIUM | X Basic API + Apify handle this; query design matters more than implementation |
| Engagement threshold filtering | Without signal/noise filtering the queue floods with irrelevant posts | MEDIUM | Hard numeric gates (500+ likes, 200+ IG likes) are standard; configurable post-launch |
| AI-drafted response alternatives per post | Single draft is too limiting; user expects choice | MEDIUM | 2-3 alternatives per post is the accepted convention in HITL workflows |
| Approval queue with approve / reject actions | Human-in-loop is the whole model; no queue = no product | MEDIUM | State machine: pending → approved / rejected / expired |
| Inline editing on draft before approval | Drafts are always imperfect; edit-then-approve is the standard workflow pattern | LOW | Rich text editing on card; saves edited version alongside original |
| One-click copy to clipboard | User manually posts; friction here is felt every single session | LOW | Copy final draft to clipboard with toast confirmation |
| Direct link to original post | Cannot engage without seeing the source | LOW | URL stored at ingest; opens in new tab |
| Platform badge on each queue card | Without at-a-glance platform identification the queue is confusing | LOW | X vs Instagram visual distinction |
| Account info on each queue card | Authority context informs whether to engage | LOW | Handle, follower count, platform |
| Automatic expiry of stale items | Stale drafts clog the queue and erode trust in the system | LOW | Twitter: 6h, Instagram: 12h; Senior Agent handles sweep |
| Configurable watchlist (bypass engagement gate) | Tier-1 accounts always matter regardless of engagement volume | LOW | DB-stored list, editable from Settings |
| Settings page for thresholds and keywords | Operators always want to tune signal/noise after first use | MEDIUM | Scoring weights, decay curves, keyword lists, watchlist management |
| Run logs per agent | Operators need to verify the system is running and diagnose failures | LOW | Timestamp, items found/queued/filtered/errors per execution |
| Simple authentication | Single-user dashboard still needs a password | LOW | Bcrypt hashed password, JWT session token |
| Mobile-appropriate notification delivery | Operator reviews on desktop but gets alerted on phone | LOW | WhatsApp via Twilio is purpose-built for this; email is the obvious fallback |

---

### Differentiators (Competitive Advantage)

Features that set this system apart from generic social listening tools like Hootsuite or Sprout Social. These align with the project's core value: every drafted response must be genuinely valuable to the gold conversation.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Niche-domain scoring (gold sector relevance) | Generic tools score by raw engagement; this system scores by topic relevance to gold/mining, making a 600-like post about gold price more valuable than a 5,000-like post about crypto | HIGH | Requires prompt-based relevance classification layered on top of engagement scoring |
| Recency decay curve | A 4-hour-old post is worth half a fresh post; without decay the queue surfaces stale opportunities | MEDIUM | Full score at 1h, 50% at 4h, expired at 6h; configurable decay function |
| Dual-format drafting (reply + retweet-with-comment) | Generic tools draft one response type; giving the operator both options per post doubles decision speed | MEDIUM | Two distinct drafts per X post with format labeling |
| Event mode (engagement spike + price movement trigger) | Gold price movement is a defined, high-value signal that generic tools don't model; event mode scales output 8-10x during these windows | HIGH | Requires gold price feed integration OR engagement spike detection (3x baseline); this is novel in the monitoring space |
| Agent self-evaluation quality gate | Content Agent scores its own output before queuing (relevance, originality, tone match, no company mention, no financial advice); items below 7.0/10 don't exist | MEDIUM | Rubric is defined and consistent; reduces human review burden by surfacing only quality-cleared items |
| Senior Agent deduplication with visual linking | Same story appearing across platforms is presented as related cards, not duplicate noise; rare in monitoring tools which treat platforms in isolation | MEDIUM | Story fingerprinting via semantic similarity; "related" label and visual grouping in dashboard |
| Performance-driven learning loop | Senior Agent tracks which content types get engagement online and adjusts scoring weights accordingly; most tools require manual tuning | HIGH | Requires logging of posted content and feedback mechanism; Phase 2 or later |
| Infographic brief generation | Moving beyond text replies to structured visual content briefs is uncommon in monitoring tools; relevant for Instagram | HIGH | HTML templates for data-heavy pieces; AI image generation for editorial pieces |
| Content Agent with deep research pass | Most monitoring tools draft from surface-level post context; this agent corroborates claims and connects to broader sector trends before drafting | HIGH | Multi-step: RSS ingest → SerpAPI search → web research → format decision → draft |
| "No story today" flag | Most tools always produce output to justify their existence; explicitly flagging when nothing clears the quality bar is honest signal and builds operator trust | LOW | 7.0/10 threshold produces this naturally; surface clearly in dashboard |
| WhatsApp morning digest + breaking news alerts | Operators of single-company monitoring systems don't live in dashboards; push notification to their primary communication channel is meaningful | LOW | Twilio integration; morning digest + threshold-triggered breaking alerts + expiry warnings |
| Queue hard cap with priority scoring | Prevents dashboard overwhelm; 15-item cap forces the system to surface only the highest-value opportunities | LOW | Senior Agent enforces cap with priority score tiebreaking |

---

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem like obvious additions but create serious problems for this specific product.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Auto-posting to platforms | "Why review manually if the AI is good enough?" | Brand risk: a single bad auto-post in the gold/finance space (implying buy/sell, misattributing data, mentioning Seva Mining) cannot be recalled and causes credibility damage that takes months to repair. The product's value is the human judgment layer. | Copy-to-clipboard + direct link; operator posts manually in under 10 seconds |
| Two-way WhatsApp approval (approve via chat reply) | "I should be able to approve from WhatsApp without opening the dashboard" | Adds significant backend complexity (Twilio webhook handling, session state, security surface). The dashboard is already mobile-accessible. The time savings are marginal. | WhatsApp notifications link directly to dashboard; single click to open the relevant card |
| LinkedIn agent | Covers more surface area | LinkedIn's API is restrictive and expensive at scale. Gold sector conversation on LinkedIn is lower-signal than X. Engineering cost is disproportionate. | X + Instagram covers the highest-value conversations; add LinkedIn only if signal quality proves insufficient |
| Reddit monitoring | More comprehensive signal | Reddit API restrictions post-2023 make reliable monitoring expensive. Scraping risks TOS violations. RSS + SerpAPI already captures Reddit-sourced stories when they reach mainstream coverage. | SerpAPI news search surfaces Reddit-originated stories once they have traction |
| Multi-tenancy / multi-client architecture | "Build it right from the start" | Premature optimization. Multi-tenancy requires tenant isolation, separate config scopes, billing, and onboarding flows. None of that creates value for a single-operator system. | Refactor when second client actually exists; schema design should not block this but should not over-engineer for it |
| Analytics dashboard | "I want to see my performance over time" | Requires defining what to measure, building data collection, designing meaningful visualizations — a separate product essentially. Zero value until enough content has been posted to generate meaningful trends. | Defer to v2; all data is retained in DB so analytics can be added later without migration |
| Mobile-responsive dashboard | "I might want to review from my phone" | Single-user desktop workflow; mobile responsiveness adds CSS complexity and testing surface for zero stated need. WhatsApp notifications handle mobile touchpoints. | Desktop-only v1; WhatsApp covers mobile alerts |
| Real-time streaming monitoring | "Shouldn't monitoring be instantaneous?" | X Basic API does not support streaming; polling every 2h is the constraint. Instagram via Apify is inherently polling-based. Streaming would require X Enterprise tier ($5,000+/mo). Polling at 2h/4h intervals is appropriate for a 1-person review workflow anyway — faster would just produce more items faster than they can be reviewed. | Scheduled polling at defined intervals; event mode handles true urgency windows |
| Sentiment analytics on monitored posts | "Knowing whether a post is positive/negative about gold would be useful" | Adds classification step to every monitored post; for a niche domain (gold sector), generic sentiment models are unreliable. The engagement score + topic relevance score already proxy for this. | Topic relevance scoring captures most of the signal; add sentiment only if a clear decision depends on it |

---

## Feature Dependencies

```
[WhatsApp Notifications]
    └──requires──> [Senior Agent: queue management]
                       └──requires──> [Twitter Agent: monitoring + scoring]
                       └──requires──> [Instagram Agent: monitoring + scoring]
                       └──requires──> [Content Agent: story pipeline]

[Approval Dashboard]
    └──requires──> [Senior Agent: queue management]
    └──requires──> [State machine: pending/approved/rejected/expired]

[Inline Editing]
    └──requires──> [Approval Dashboard]
    └──requires──> [Draft storage (JSONB alternatives array)]

[Deduplication / Related Cards]
    └──requires──> [Senior Agent]
    └──requires──> [Both Twitter Agent AND Instagram Agent running]

[Event Mode]
    └──requires──> [Twitter Agent: baseline engagement tracking]
    └──enhances──> [Senior Agent: queue cap management] (cap may need to flex during event mode)

[Infographic Generation]
    └──requires──> [Content Agent: story pipeline]
    └──requires──> [Format decision logic]

[Performance-Driven Learning Loop]
    └──requires──> [Run logs]
    └──requires──> [Approval state tracking (what got approved vs rejected)]
    └──requires──> [External engagement tracking (what performed online)]
    (Defer to v2 — dependency chain is longest, value requires historical data)

[Settings Page: Scoring Parameters]
    └──enhances──> [Twitter Agent scoring]
    └──enhances──> [Instagram Agent scoring]
    └──enhances──> [Content Agent quality threshold]

[Agent Self-Evaluation]
    └──requires──> [Quality rubric definition]
    └──requires──> [Claude API integration]
    └──feeds into──> [Senior Agent queue management] (only quality-cleared items reach queue)

[Event Mode] ──conflicts-with──> [Queue Hard Cap 15]
    (Resolution: event mode temporarily expands cap to handle 8-10 posts during spike windows)
```

### Dependency Notes

- **Approval Dashboard requires Senior Agent:** The dashboard is a read layer on top of what Senior Agent has queued and scored. Senior Agent must exist before dashboard has anything to show.
- **WhatsApp requires queue management:** Morning digest and breaking alerts are derived from queue state. No queue, no meaningful notifications.
- **Performance-driven learning loop requires approval tracking + external data:** This is fundamentally a v2 feature. The feedback loop cannot close until there is historical data on what got approved and what performed well after posting.
- **Event mode conflicts with hard cap:** The 15-item cap must yield during event mode (engagement spike / price movement), or the event will crowd out normal monitoring. Design the cap as "soft" during event windows.
- **Deduplication requires both agents running:** Cross-platform story linking only becomes valuable once both X and Instagram agents are operational. In practice, this means it is a Phase 2 refinement, not a Phase 1 blocker.

---

## MVP Definition

### Launch With (v1)

Minimum viable product — what is needed for the operator to actually use the system daily.

- [ ] Twitter Agent: monitoring, scoring, engagement gate, watchlist bypass, draft alternatives (reply + RT-with-comment), recency decay
- [ ] Instagram Agent: monitoring, scoring, engagement gate, draft alternatives (comment only, no hashtags)
- [ ] Content Agent: RSS ingest, SerpAPI search, deep research pass, format decision, quality threshold (7.0/10), thread + single-post dual format
- [ ] Senior Agent: queue management, deduplication, expiry, hard cap 15, priority scoring
- [ ] Approval Dashboard: feed/timeline layout, approval cards with full context, approve/edit+approve/reject, inline editing, copy-to-clipboard, direct link
- [ ] WhatsApp notifications: morning digest, breaking news alert, expiry alert
- [ ] Agent self-evaluation quality gate
- [ ] Settings page: watchlist, keywords, scoring parameters, run logs, notification prefs, agent schedule
- [ ] Simple password authentication
- [ ] Run logging per agent execution

### Add After Validation (v1.x)

Features to add once core workflow is proven useful.

- [ ] Event mode (engagement spike + price movement) — add once baseline engagement data exists to define "3x normal"
- [ ] Infographic generation — add once Content Agent story pipeline is calibrated and producing consistent quality
- [ ] Performance-driven learning loop — requires several weeks of approval data before the feedback signal is meaningful
- [ ] Deduplication visual linking — implement after both agents have been running for several cycles; the pattern will be obvious from real data

### Future Consideration (v2+)

Features to defer until product-market fit is established.

- [ ] Analytics dashboard — requires enough historical data for trends to be meaningful; all data is retained so this is purely a build decision
- [ ] Multi-client platform (multi-tenancy) — refactor only when a second client exists
- [ ] LinkedIn agent — only if X + Instagram prove insufficient signal
- [ ] Two-way WhatsApp approval — reconsider if operator friction on approval workflow proves to be the primary bottleneck

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Twitter Agent monitoring + scoring + drafting | HIGH | MEDIUM | P1 |
| Instagram Agent monitoring + scoring + drafting | HIGH | MEDIUM | P1 |
| Content Agent story pipeline | HIGH | HIGH | P1 |
| Approval Dashboard (cards, state machine, inline edit) | HIGH | MEDIUM | P1 |
| Senior Agent (queue, dedup, expiry, cap) | HIGH | MEDIUM | P1 |
| Agent self-evaluation quality gate | HIGH | LOW | P1 |
| WhatsApp notifications | HIGH | LOW | P1 |
| Settings page (watchlist, keywords, thresholds) | HIGH | MEDIUM | P1 |
| Simple authentication | HIGH | LOW | P1 |
| Run logging | MEDIUM | LOW | P1 |
| Event mode | HIGH | HIGH | P2 |
| Infographic generation | MEDIUM | HIGH | P2 |
| Performance-driven learning loop | HIGH | HIGH | P2 |
| Deduplication visual linking | MEDIUM | MEDIUM | P2 |
| Analytics dashboard | MEDIUM | HIGH | P3 |
| Multi-tenancy | LOW | HIGH | P3 |
| LinkedIn agent | LOW | MEDIUM | P3 |

**Priority key:**
- P1: Must have for launch
- P2: Should have, add when possible
- P3: Nice to have, future consideration

---

## Competitor Feature Analysis

This system is a custom-built, single-operator product. The relevant comparators are the general-purpose tools the operator would otherwise use.

| Feature | Sprout Social | Hootsuite | This System |
|---------|--------------|-----------|-------------|
| Multi-platform monitoring | Yes (30+ platforms) | Yes (30+ networks) | X + Instagram (niche focus) |
| Engagement scoring | Basic (raw engagement metrics) | Basic (raw engagement metrics) | Custom-weighted: engagement x decay x topic relevance |
| Industry-specific relevance scoring | No | No | Yes — gold sector relevance layer on every post |
| Approval workflow | Yes (multi-step, team-based) | Yes (lighter, enterprise tier only) | Yes (single-operator, inline edit, copy-to-clipboard) |
| AI draft alternatives | 1 suggestion (Sprout AI helper) | 1 suggestion (OwlyWriter AI) | 2-3 alternatives per post, dual format (reply + RT) |
| Content Agent (proactive story creation) | No | No | Yes — RSS + SerpAPI + deep research + format decision |
| Recency decay on queue items | No | No | Yes — configurable decay curve |
| Hard queue cap | No | No | Yes — 15 items, priority-ranked |
| WhatsApp notifications | No (email/Slack) | No (email/Slack) | Yes — Twilio WhatsApp |
| Event mode (price spike response) | No | No | Yes — 3x engagement spike OR gold price movement |
| "No story today" quality gate | No (always produces output) | No | Yes — 7.0/10 threshold with explicit flag |
| Auto-posting | Yes (core feature) | Yes (core feature) | Deliberately excluded |
| Multi-platform publishing | Yes | Yes | Out of scope (operator posts manually) |
| Team collaboration | Yes | Yes | Out of scope (single operator) |
| Analytics | Yes (deep) | Yes (moderate) | Deferred to v2 |
| Pricing | $249/mo+ | $99/mo+ | ~$255-275/mo (operating costs, no license fee) |

---

## Sources

- [12 Best AI Agents for Social Media Management in 2026 — ema.ai](https://www.ema.ai/additional-blogs/addition-blogs/best-social-media-ai-agents)
- [Best AI Social Media Automation Tools in 2026 — Enrich Labs](https://www.enrichlabs.ai/blog/best-ai-social-media-automation-tools)
- [Top 10 Social Listening Platforms for 2026 — Pulsar Platform](https://www.pulsarplatform.com/blog/2025/best-social-listening-tools-2026)
- [13 Best Social Media Listening Tools for 2026 — Nextiva](https://www.nextiva.com/blog/social-media-listening-software.html)
- [Content Approval Workflows Guide 2026 — InfluenceFlow](https://influenceflow.io/resources/content-approval-workflows-a-complete-guide-for-2026-1/)
- [Building Human-In-The-Loop Agentic Workflows — Towards Data Science](https://towardsdatascience.com/building-human-in-the-loop-agentic-workflows/)
- [Hootsuite vs Sprout Social 2026 — Planable](https://planable.io/blog/hootsuite-vs-sprout-social/)
- [Sprout Social Review 2026 — Copywriters Now](https://copywritersnow.com/sprout-social-review/)
- [The Social Media Metrics to Track in 2026 — Sprout Social](https://sproutsocial.com/insights/social-media-metrics/)
- [Social Media Engagement in 2025: An Expanded Overview — Global Banking and Finance](https://www.globalbankingandfinance.com/social-media-engagement-in-2025-an-expanded-overview/)
- [Social Media Mistakes to Avoid in 2025 — Metricool](https://metricool.com/biggest-social-media-mistakes/)
- [Top 5 Social Media Pitfalls to Avoid in 2025 — Vista Social](https://vistasocial.com/insights/5-social-media-pitfalls-to-avoid-in-2025/)
- [Brand Safety on Social Media in 2025 — eMarketer](https://www.emarketer.com/content/brand-safety-on-social-media-2025)
- [2026 State of Content Workflows — Averi AI](https://www.averi.ai/guides/2026-state-content-workflows)
- [AI in Social Media: Everything You Need to Know for 2026 — Metricool](https://metricool.com/ai-social-media-marketing/)

---

*Feature research for: AI social media monitoring and engagement drafting system (gold sector)*
*Researched: 2026-03-30*
