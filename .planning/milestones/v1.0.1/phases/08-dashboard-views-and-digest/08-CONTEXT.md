---
phase: 8
slug: dashboard-views-and-digest
created: 2026-04-02
discuss_complete: true
---

# Phase 8 — Implementation Context

> Decisions and constraints that guide researcher and planner. All choices here are final — no re-asking downstream.

---

## Phase Goal

Build out the three stub-only frontend pages (DigestPage, ContentPage, SettingsPage) so the operator has a working daily digest view, a content review + approve flow for today's ContentBundle, and a full Settings page wired to live DB configuration.

---

## What Already Exists (Do Not Rebuild)

### Backend endpoints — all complete, no new endpoints needed except config CRUD:

| Endpoint | Purpose |
|----------|---------|
| `GET /digests/latest` | Latest DailyDigest record |
| `GET /digests/{date}` | DailyDigest by `YYYY-MM-DD` |
| `GET /content/today` | Today's ContentBundle (most recent `created_at` for today) |
| `GET /queue?platform=content&status=pending` | Content DraftItem for today |
| `PATCH /items/{id}/approve` | Approve a DraftItem (already used by Twitter/Instagram) |
| `PATCH /items/{id}/reject` | Reject a DraftItem |
| `GET /agent-runs?agent_name=X&days=7` | Agent run log |
| `GET /watchlists?platform=twitter\|instagram` | List watchlist entries |
| `POST /watchlists` | Create watchlist entry |
| `PATCH /watchlists/{id}` | Update watchlist entry |
| `DELETE /watchlists/{id}` | Delete watchlist entry |
| `GET /keywords?platform=X&active=true` | List keywords |
| `POST /keywords` | Create keyword |
| `PATCH /keywords/{id}` | Update keyword |
| `DELETE /keywords/{id}` | Delete keyword |
| `GET /config/quota` | Twitter API quota data |

### New backend endpoints required for Phase 8:

| Endpoint | Purpose |
|----------|---------|
| `GET /config` | List all config keys as `[{key, value}]` — used by Scoring, Notifications, Schedule tabs |
| `PATCH /config/{key}` | Update a single config key by name — used by Scoring, Notifications, Schedule tabs |

These belong in `backend/app/routers/config.py` alongside the existing `/config/quota` route. The Config model (`backend/app/models/config.py`) already exists.

### Frontend stub pages (all 3 fully empty — just a `<p>Coming in Phase 8</p>`):
- `frontend/src/pages/DigestPage.tsx`
- `frontend/src/pages/ContentPage.tsx`
- `frontend/src/pages/SettingsPage.tsx`

### Existing reusable frontend assets:
- `Badge`, `Button`, `Tabs`, `Separator`, `Textarea`, `Dialog` — already installed shadcn components
- `EmptyState`, `ScoreBadge`, `PlatformBadge` — shared components
- `useApprove(platform)`, `useReject(platform)` hooks — use these for ContentPage approval
- `ApprovalCard`, `ContentSummaryCard`, `ContentDetailModal` — reference for design patterns
- TanStack Query + Zustand — established data-fetching pattern

---

## Decision: Infographic Preview Rendering

**Chosen:** Stat cards layout

The `draft_content` JSONB for infographic format has this shape:
```json
{
  "format": "infographic",
  "headline": "...",
  "key_stats": [{"stat": "...", "source": "...", "source_url": "..."}],
  "visual_structure": "bar chart" | "timeline" | "comparison table" | "stat callouts" | "map",
  "caption_text": "..."
}
```

**Render as:**
1. Section header: "INFOGRAPHIC BRIEF" label + `visual_structure` as a Badge (e.g. "Bar Chart") + Copy button (copies `caption_text` to clipboard)
2. Headline: `draft_content.headline` in a larger font weight
3. Key stats list: each item as a bullet row — bold `stat` text + `source` as a clickable link to `source_url` below it
4. Caption block: `draft_content.caption_text` in a text area or styled paragraph

No chart rendering, no SVG approximation. The stat cards layout gives the operator all the information needed to review the brief at a glance.

---

## Decision: Settings Page Layout

**Chosen:** Tabbed sections using existing `tabs.tsx` shadcn component

5 tabs:
1. **Watchlists** — X and Instagram sub-tables (filter by platform), add/edit/delete rows
2. **Keywords** — table with platform column, active toggle, weight field, delete; add-row form
3. **Scoring** — form fields for all weight/threshold config keys (content_relevance_weight, content_recency_weight, content_credibility_weight, content_quality_threshold, plus Twitter/Instagram equivalents as they exist in DB). Save button per section.
4. **Notifications** — WhatsApp timing and alert threshold config keys. Editable fields + save.
5. **Agent Runs** — table of last 7 days runs, agent filter dropdown, columns: agent_name, started_at, status, items_found, items_queued, items_filtered, errors

SETT-08 (X API quota): add a quota widget at the bottom of the **Agent Runs** tab (or as a small card at the top of that tab). `GET /config/quota` response: `{monthly_tweet_count, quota_safety_margin, monthly_cap, reset_date}`. Render as a progress bar: `monthly_tweet_count / monthly_cap`.

Agent schedule config (SETT-07): Shown in a 6th tab **Schedule** or within the Agent Runs tab. Display current schedule intervals (from config keys like `content_agent_schedule_hour`, etc.) as editable number inputs. Save writes to DB. Show a note: "Changes take effect on next worker restart." This is display + DB write only in Phase 8 — Phase 9 wires the scheduler to actually read these values.

---

## Decision: Digest History Navigation

**Chosen:** Previous / Next arrow buttons + date shown in header

- On mount: fetch `GET /digests/latest` → set `currentDate = digest.digest_date`
- "←" button: decrement date by 1 day, fetch `GET /digests/{date}`, show 404 as "No digest for this date"
- "→" button: increment date by 1 day, fetch `GET /digests/{date}`. Disable "→" when `currentDate === latestDate`
- Show `currentDate` formatted as "Monday, April 7, 2026" in the page header beside the arrows
- No date picker, no dropdown. Simple and matches the one-record-per-day pattern.

---

## Decision: Content Approve Flow

**Chosen:** Same `useApprove` hook as Twitter/Instagram

The Content Agent creates a `DraftItem(platform="content", status="pending")` with `engagement_snapshot={"content_bundle_id": "<uuid>"}`.

ContentPage flow:
1. Fetch `GET /content/today` → `ContentBundle`
2. If `no_story_flag=True` → show `EmptyState` with "No strong story found today" + bundle score
3. If `no_story_flag=False` → fetch `GET /queue?platform=content&status=pending` → find the matching `DraftItem`
4. If DraftItem found → render the content review UI with Approve / Reject buttons
5. If DraftItem not found (already approved/rejected) → show the bundle's info as read-only with status badge

**Approve behavior:**
- Calls `approveItem(draftItem.id)` (existing hook) — same endpoint as Twitter/Instagram
- Clipboard text is determined by `format_type` from the ContentBundle:
  - `"infographic"` → `draft_content.caption_text`
  - `"long_form"` → `draft_content.post`
  - `"thread"` → all tweets joined with `"\n\n"` (the `tweets` array)
- Toast: "Approved — copied to clipboard" (existing behavior)

---

## New Frontend API Modules

Add these files to `frontend/src/api/`:

### `digests.ts`
```typescript
getLatestDigest(): Promise<DailyDigestResponse>
getDigestByDate(date: string): Promise<DailyDigestResponse>  // date = "YYYY-MM-DD"
```

### `content.ts`
```typescript
getTodayContent(): Promise<ContentBundleResponse>
```

### `settings.ts`
```typescript
getWatchlists(platform?: string): Promise<WatchlistResponse[]>
createWatchlist(body: WatchlistCreate): Promise<WatchlistResponse>
updateWatchlist(id: string, body: WatchlistUpdate): Promise<WatchlistResponse>
deleteWatchlist(id: string): Promise<void>

getKeywords(platform?: string, active?: boolean): Promise<KeywordResponse[]>
createKeyword(body: KeywordCreate): Promise<KeywordResponse>
updateKeyword(id: string, body: KeywordUpdate): Promise<KeywordResponse>
deleteKeyword(id: string): Promise<void>

getAgentRuns(agentName?: string, days?: number): Promise<AgentRunResponse[]>

getQuota(): Promise<QuotaResponse>

getConfig(): Promise<ConfigEntry[]>
updateConfig(key: string, value: string): Promise<ConfigEntry>
```

---

## New TypeScript Types (add to `frontend/src/api/types.ts`)

```typescript
export interface DailyDigestResponse {
  id: string
  digest_date: string          // "YYYY-MM-DD"
  top_stories: unknown         // JSONB — array of story objects
  queue_snapshot: unknown      // JSONB — counts per platform
  yesterday_approved: unknown
  yesterday_rejected: unknown
  yesterday_expired: unknown
  priority_alert: unknown      // null or alert object
  whatsapp_sent_at?: string
  created_at: string
}

export interface AgentRunResponse {
  id: string
  agent_name: string
  started_at: string
  ended_at?: string
  items_found?: number
  items_queued?: number
  items_filtered?: number
  errors?: unknown
  status?: string
  notes?: string
  created_at: string
}

export interface WatchlistCreate {
  platform: string
  account_handle: string
  relationship_value?: number
  follower_threshold?: number
  notes?: string
  active?: boolean
}
export interface WatchlistUpdate {
  relationship_value?: number
  follower_threshold?: number
  notes?: string
  active?: boolean
}
export interface WatchlistResponse extends WatchlistCreate {
  id: string
  platform_user_id?: string
  active: boolean
  created_at: string
  updated_at?: string
}

export interface KeywordCreate {
  keyword: string
  platform: string
  weight?: number
  active?: boolean
}
export interface KeywordUpdate {
  weight?: number
  active?: boolean
}
export interface KeywordResponse extends KeywordCreate {
  id: string
  created_at: string
  updated_at?: string
}

export interface ConfigEntry {
  key: string
  value: string
}

export interface QuotaResponse {
  monthly_tweet_count: number
  quota_safety_margin: number
  monthly_cap: number
  reset_date?: string
}
```

---

## Phase Scope Boundaries

### In Phase 8:
- All 3 stub pages fully built and wired to live endpoints
- New backend `GET /config` + `PATCH /config/{key}` endpoints
- Scoring/notification/schedule settings write to DB
- Infographic stat cards rendering
- Content approve flow (same hook as Twitter/Instagram)

### Out of Phase 8 (Phase 9):
- Agents actually reading scoring weights from DB at runtime (not hardcoded)
- Scheduler reading schedule intervals from DB to reschedule jobs dynamically
- Agent crash isolation and graceful failure handling

### Explicitly deferred:
- Dark mode toggle
- Mobile/responsive layout optimization
- Bulk approve/reject across multiple items
- Export/download of agent run logs

---

## TanStack Query Keys

| Feature | Query Key |
|---------|-----------|
| Latest digest | `['digest', 'latest']` |
| Digest by date | `['digest', date]` |
| Today's content | `['content', 'today']` |
| Agent runs | `['agentRuns', agentName, days]` |
| Watchlists | `['watchlists', platform]` |
| Keywords | `['keywords', platform]` |
| Config | `['config']` |
| Quota | `['quota']` |

---

## Implementation Notes

1. **DigestPage `top_stories` field**: JSONB — render as an ordered list of story cards. Each story likely has `headline`, `source`, `url`, `score` fields. Render defensively (check field existence before accessing).

2. **DigestPage `queue_snapshot` field**: JSONB — likely `{twitter: N, instagram: N, content: N}`. Render as 3 stat cards.

3. **DigestPage `priority_alert` field**: JSONB or null. If non-null, render prominently at the top as an alert banner. If null, show nothing.

4. **ContentPage DraftItem lookup**: `GET /queue?platform=content&status=pending` returns all pending content items. Since there's at most 1 per day, take `items[0]`. The `engagement_snapshot.content_bundle_id` links it to the ContentBundle.

5. **Settings Scoring tab config keys**: The seeded keys from `scheduler/seed_content_data.py` are: `content_relevance_weight`, `content_recency_weight`, `content_credibility_weight`, `content_quality_threshold`. Twitter agent seeds its own keys. Show all `content_*` and `twitter_*` scoring keys in their respective sections.

6. **Config PATCH backend**: The `Config` model has `key` (String, unique) and `value` (Text). `PATCH /config/{key}` does an upsert: update if exists, create if not. Return `{key, value}`.

7. **Keyword schema**: Check `backend/app/schemas/keyword.py` for exact field names before writing TypeScript types. The `KeywordResponse` likely has a `weight` field (Numeric) and `active` (Boolean).
