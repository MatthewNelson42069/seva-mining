export type DraftStatus = 'pending' | 'approved' | 'edited_approved' | 'rejected' | 'expired'
// Platform narrowed to 'content' only in quick-260420-sn9 (Twitter agent purged;
// Instagram agent was purged in quick-260419-lvy). Backend column stays permissive String(20).
export type Platform = 'content'

export interface DraftAlternative {
  text: string
  type: 'reply' | 'retweet' | 'comment' | 'thread' | 'long_post'
  label: string  // "Draft A", "Draft B" (retweet/RT Quote types are legacy — no longer produced)
}

// Phase B (quick-260424-l0d): X post-state, orthogonal to DraftStatus.
// Stored on draft_items.approval_state. See backend ApprovalState enum.
export type ApprovalState =
  | 'pending'
  | 'posted'
  | 'failed'
  | 'discarded'
  | 'posted_partial'

export interface DraftItemResponse {
  id: string
  platform: Platform
  status: DraftStatus
  source_url?: string
  source_text?: string
  source_account?: string
  follower_count?: number
  score?: number
  quality_score?: number
  alternatives: DraftAlternative[]
  rationale?: string
  urgency?: string
  related_id?: string
  rejection_reason?: string
  edit_delta?: string
  expires_at?: string
  decided_at?: string
  created_at: string
  updated_at?: string
  engagement_snapshot?: Record<string, unknown>
  // Phase B (quick-260424-l0d): X post-state surfaced to dashboard
  approval_state?: ApprovalState
  posted_tweet_id?: string
  posted_tweet_ids?: string[]
  posted_at?: string
  post_error?: string
}

// Phase B (quick-260424-l0d): response from POST /items/{id}/post-to-x.
// Mirrors the post-state columns plus an `already_posted` flag for idempotent
// re-calls.
export interface PostToXResponse {
  approval_state: ApprovalState
  posted_tweet_id?: string
  posted_tweet_ids?: string[]
  posted_at?: string
  post_error?: string
  already_posted: boolean
}

export interface QueueListResponse {
  items: DraftItemResponse[]
  next_cursor?: string
}

export interface ContentBundleResponse {
  id: string
  story_headline: string
  story_url?: string
  source_name?: string
  content_type?: string
  score?: number
  quality_score?: number
  no_story_flag: boolean
  deep_research?: unknown
  draft_content?: unknown
  compliance_passed?: boolean
  created_at: string
}

export interface ContentBundleDetailResponse {
  id: string
  story_headline: string
  story_url?: string
  source_name?: string
  content_type?: string
  score?: number
  quality_score?: number
  no_story_flag: boolean
  deep_research?: unknown
  draft_content?: unknown
  compliance_passed?: boolean
  created_at: string
}

export const REJECTION_CATEGORIES = [
  'off-topic', 'low-quality', 'bad-timing', 'tone-wrong', 'duplicate'
] as const
export type RejectionCategory = typeof REJECTION_CATEGORIES[number]

export interface LoginRequest { password: string }
export interface TokenResponse { access_token: string; token_type: string }

export interface DailyDigestResponse {
  id: string
  digest_date: string
  top_stories: unknown
  queue_snapshot: unknown
  yesterday_approved: unknown
  yesterday_rejected: unknown
  yesterday_expired: unknown
  priority_alert: unknown
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
  term: string          // CRITICAL: "term" not "keyword" — matches backend schema
  platform?: string
  weight?: number
  active?: boolean
}
export interface KeywordUpdate {
  weight?: number
  active?: boolean
}
export interface KeywordResponse {
  id: string
  term: string          // CRITICAL: "term" not "keyword"
  platform?: string
  weight?: number
  active: boolean
  created_at: string
  updated_at?: string
}

export interface ConfigEntry {
  key: string
  value: string
}

