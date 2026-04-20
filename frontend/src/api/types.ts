export type DraftStatus = 'pending' | 'approved' | 'edited_approved' | 'rejected' | 'expired'
export type Platform = 'twitter' | 'content'

export interface DraftAlternative {
  text: string
  type: 'reply' | 'retweet' | 'comment' | 'thread' | 'long_post'
  label: string  // "Draft A", "Draft B", "RT Quote"
}

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

export interface RenderedImage {
  role: string
  url: string
  generated_at: string
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
  rendered_images?: RenderedImage[] | null
  created_at: string
}

export interface RerenderResponse {
  bundle_id: string
  render_job_id: string
  enqueued_at: string
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

export interface QuotaResponse {
  monthly_tweet_count: number
  quota_safety_margin: number
  monthly_cap: number
  reset_date?: string
}
