export type DraftStatus = 'pending' | 'approved' | 'edited_approved' | 'rejected' | 'expired'
export type Platform = 'twitter' | 'instagram' | 'content'

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
  format_type?: string
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
