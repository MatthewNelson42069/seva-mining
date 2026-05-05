# Phase 2: FastAPI Backend - Context

**Gathered:** 2026-03-31
**Status:** Ready for planning

<domain>
## Phase Boundary

Build all REST API endpoints for the Seva Mining approval dashboard: authentication (login/JWT), the full approval queue CRUD with state machine enforcement, content bundle review, watchlist and keyword management, agent run logs, daily digest retrieval, and a Twilio WhatsApp notification service. Nothing is posted to any platform — this phase gives the React dashboard (Phase 3) a complete API to work against.

</domain>

<decisions>
## Implementation Decisions

### API Endpoint Design
- **D-01:** Response shape — Claude's discretion per endpoint (envelope vs direct payload)
- **D-02:** Cursor-based pagination for the approval queue using `created_at` cursor. Queue is capped at 15 but pagination supports filtering by platform/status
- **D-03:** Error format — Claude's discretion (pick what's cleanest for the React frontend)
- **D-04:** URL versioning — Claude's discretion
- **D-05:** Inline edit + approve in one API call — `PATCH /items/{id}/approve` accepts optional `edited_text` in body. Single call, not two-step edit-then-approve
- **D-06:** Bulk operations for watchlists/keywords — Claude's discretion

### Authentication
- **D-07:** Simple password login — single bcrypt hash stored in `DASHBOARD_PASSWORD` env var, compared on login, returns JWT
- **D-08:** JWT expiry: 7 days
- **D-09:** Token expiry behavior — Claude's discretion (silent redirect to login or refresh token — pick the simpler approach for single-user)
- **D-10:** JWT secret stored in `JWT_SECRET` env var (already in config.py)

### Draft State Machine
- **D-11:** Valid transitions: `pending → approved`, `pending → edited_approved` (with edit_delta preserved), `pending → rejected` (reason required), `pending → expired` (auto, by expiry processor). No other transitions allowed — API returns error on invalid transition
- **D-12:** Rejection reasons: category tag (off-topic, low-quality, bad-timing, tone-wrong, duplicate) + optional free-text notes. Both stored in `rejection_reason` field as structured JSON
- **D-13:** Expired items visible in an 'Expired' tab — soft state, not deleted, queryable via `GET /queue?status=expired`
- **D-14:** Edit history preserved — when `edited_approved`, store the original draft text in `edit_delta` field so the learning loop can compare original vs edited

### WhatsApp Notifications
- **D-15:** Three WhatsApp trigger types: (1) daily morning digest at 8am, (2) breaking news alert when content scores 9.0+, (3) high-urgency draft about to expire
- **D-16:** Twilio failure handling — Claude's discretion (log + retry once, or log only)
- **D-17:** Use pre-registered Meta-approved templates: `seva_morning_digest` (HX930c2171b211acdea4d5fa0a12d6c0e0), `seva_breaking_news` (HXc5bcef9a42a18e9071acd1d6fb0fac39), `seva_expiry_alert` (HX45fd40f45d91e2ea54abd2298dd8bc41)

### Claude's Discretion
- Response envelope vs direct payload (D-01)
- Error format (D-03)
- URL versioning (D-04)
- Bulk operations (D-06)
- Token expiry handling (D-09)
- Twilio failure strategy (D-16)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Backend Code (Phase 1 output)
- `backend/app/config.py` — All env vars including jwt_secret, dashboard_password
- `backend/app/models/draft_item.py` — DraftItem model with DraftStatus enum, edit_delta, alternatives JSONB
- `backend/app/models/content_bundle.py` — ContentBundle model
- `backend/app/models/watchlist.py` — Watchlist model
- `backend/app/models/keyword.py` — Keyword model
- `backend/app/models/agent_run.py` — AgentRun model
- `backend/app/models/daily_digest.py` — DailyDigest model
- `backend/app/database.py` — Async engine with Neon pool config
- `backend/app/main.py` — FastAPI app skeleton with /health endpoint
- `backend/alembic/versions/0001_initial_schema.py` — Full schema reference

### Project Requirements
- `.planning/REQUIREMENTS.md` — AUTH-01, AUTH-02, AUTH-03, EXEC-01 definitions

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/app/config.py` — Settings class already has jwt_secret, dashboard_password, twilio_* fields
- `backend/app/database.py` — AsyncSessionLocal ready for dependency injection
- `backend/app/models/` — All 6 models with proper JSONB fields and DraftStatus enum
- `backend/app/main.py` — FastAPI app with lifespan pattern, /health already working

### Established Patterns
- Pydantic v2 with `model_config = ConfigDict(from_attributes=True)` for ORM serialization
- Async everything — `create_async_engine`, `AsyncSession`, all handlers must be `async def`
- UUID primary keys on all models

### Integration Points
- New routes register on `backend/app/main.py`'s `app` instance
- Database sessions via `AsyncSessionLocal` dependency
- Alembic handles any schema additions (though Phase 2 likely needs none — schema is complete)

</code_context>

<specifics>
## Specific Ideas

- Rejection reason categories: off-topic, low-quality, bad-timing, tone-wrong, duplicate — stored as structured JSON in rejection_reason field
- The 13 API endpoints from the blueprint are the contract: /queue, /items/{id}/approve, /items/{id}/reject, /items/{id}/edit, /digests/latest, /content/today, /watchlists (CRUD), /keywords (CRUD+patch), /agent-runs
- WhatsApp template SIDs are known and should be constants in the notification service

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 02-fastapi-backend*
*Context gathered: 2026-03-31*
