# Phase 3: React Approval Dashboard - Context

**Gathered:** 2026-03-31
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the React approval dashboard — the operator's daily review interface. Tabbed queue with full-width approval cards, inline editing, one-click copy-to-clipboard, and direct links to original posts. Desktop-only, seeded with realistic gold sector mock data. The entire human review workflow is verified and polished before any agent produces real output.

</domain>

<decisions>
## Implementation Decisions

### Card Layout
- **D-01:** Full-width stack layout — one card per row, full width, everything visible without clicking. Linear issues / Notion database style.
- **D-02:** Draft alternatives displayed as tabs within each card (Draft A / Draft B / RT Quote). One visible at a time, click to switch. Keeps card height consistent.
- **D-03:** Urgency communicated by sort order only — most urgent cards at top. No color-coded borders, countdown badges, or background tints.
- **D-04:** Original post excerpt shows first 2 lines (~140 chars), click to expand for full text.
- **D-05:** Rationale collapsed by default — small "Why this post?" toggle. Expand when curious.
- **D-06:** Score displayed as numeric badge (8.7/10) in card header. Clean number, no color coding.
- **D-07:** Related cards (DASH-08) use a badge approach — "Also on Instagram" or "Also on Twitter" badge on the card. Clicking it navigates to the related card. Doesn't break urgency sorting.
- **D-08:** Content tab uses summary card + expand modal — headline, format choice, credibility score on the card. Click to open focused reading modal with full draft and all sources.

### Interaction Flow
- **D-09:** Approve/reject triggers fade-out animation (300ms) + toast confirmation ("Approved — copied to clipboard" or "Rejected"). Undo available for 5 seconds.
- **D-10:** Inline editing — click draft text to enter edit mode (textarea expands, border highlights). Read-only by default. "Edit + Approve" saves edit and approves in one action.
- **D-11:** Rejection UX — click Reject opens inline dropdown with 5 category radio buttons (off-topic, low-quality, bad-timing, tone-wrong, duplicate) + optional notes textarea + Confirm Reject button.

### Visual Identity
- **D-12:** Light mode only — clean white background, dark text. No dark mode toggle.
- **D-13:** Blue accent color (Linear-style) for buttons, active tabs, highlights. Classic SaaS blue, neutral, professional.
- **D-14:** Login page — Claude's discretion (simplest approach matching overall aesthetic, single password field, no username).

### Dashboard Chrome
- **D-15:** Top tabs + sidebar combo — platform tabs (Twitter/Instagram/Content with badge counts) at top for the queue, sidebar for other pages (Digest, Content Review, Settings).
- **D-16:** Empty state shows "Queue is clear" with agent last run time and next run countdown. Reassuring that the system is working.

### Mock Data
- **D-17:** Pre-seed the database with 10-15 realistic gold sector draft items across all platforms. Real-looking gold tweets, Instagram posts, and a content bundle so the full approval flow can be tested immediately before agents run.

### Claude's Discretion
- Login page design (D-14)
- Sidebar layout details and page routing
- Animation easing and timing details
- Typography scale and spacing
- Card border, shadow, and spacing within the Linear/Notion aesthetic
- Toast positioning and styling
- Modal design for content review

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Backend API (Phase 2 output)
- `backend/app/routers/queue.py` — Queue endpoints, state machine transitions, cursor pagination
- `backend/app/routers/auth.py` — Login endpoint, JWT flow
- `backend/app/schemas/draft_item.py` — DraftItem response/request schemas (the data shape for cards)
- `backend/app/schemas/content_bundle.py` — Content bundle schema
- `backend/app/schemas/watchlist.py` — Watchlist schema
- `backend/app/schemas/keyword.py` — Keyword schema
- `backend/app/routers/watchlists.py` — Watchlist CRUD endpoints
- `backend/app/routers/keywords.py` — Keyword CRUD endpoints
- `backend/app/routers/digests.py` — Digest endpoints
- `backend/app/routers/content.py` — Content today endpoint

### Prior Decisions
- `.planning/phases/02-fastapi-backend/02-CONTEXT.md` — API design decisions (D-02 cursor pagination, D-05 inline edit+approve, D-12 structured rejection)

### Stack References
- `CLAUDE.md` §Technology Stack — React 19, Vite 6, Tailwind v4, shadcn/ui (tailwind-v4 branch), TanStack Query v5, Zustand v5

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- No frontend exists yet — greenfield React setup required
- Backend API is fully built with 13 endpoints ready to consume
- Pydantic schemas in `backend/app/schemas/` define the exact data shapes the frontend will receive

### Established Patterns
- Backend uses FastAPI with JWT auth — frontend must send `Authorization: Bearer {token}` header
- Queue uses cursor-based pagination (base64 encoded `created_at:id` cursor)
- Approve endpoint accepts optional `edited_text` for inline edit+approve in one call
- Rejection requires structured JSON with `category` and optional `notes`

### Integration Points
- `POST /auth/login` — password-only login, returns JWT
- `GET /queue?platform=twitter&status=pending&cursor=...` — paginated queue
- `PATCH /items/{id}/approve` — approve (with optional edited_text)
- `PATCH /items/{id}/reject` — reject (with category + notes)
- `GET /digests/latest` — daily digest data
- `GET /content/today` — today's content bundle
- `GET /watchlists`, `GET /keywords` — settings data
- `GET /agent-runs` — agent run logs

</code_context>

<specifics>
## Specific Ideas

- Linear/Notion aesthetic: lots of white space, content-focused, minimal chrome
- The preview mockups shown during discussion represent the target density — card header with platform badge, account, score, then content area, then action buttons
- Tabbed alternatives within cards like browser tabs — small, unobtrusive, click to switch
- "Why this post?" as the rationale toggle text
- Toast should say "Approved — copied to clipboard" (approval auto-copies the selected draft)
- Empty state should feel reassuring, not empty — show system health

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 03-react-approval-dashboard*
*Context gathered: 2026-03-31*
