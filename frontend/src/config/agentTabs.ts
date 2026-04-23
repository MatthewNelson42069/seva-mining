/**
 * Single source of truth for the 6 content sub-agent tabs.
 *
 * Introduced in quick-260421-eoe when the monolithic Content Agent was
 * split into sub-agents (see scheduler/agents/content/). Sidebar,
 * Router, PerAgentQueuePage, and useQueueCounts all read from this
 * array — adding a sub-agent is a single-line change here.
 * quick-260423-k8n: sub_long_form removed, reducing from 7 to 6 sub-agents.
 *
 *  - `slug`          — URL slug used in /agents/:slug
 *  - `contentType`   — DB-native value on content_bundles.content_type
 *                      (this is what the backend /queue?content_type= filter
 *                      expects — do NOT send the slug here)
 *  - `label`         — Human-facing label (Sidebar + page H1 + AgentRunsTab)
 *  - `priority`      — Render order in Sidebar (1 = top)
 *  - `agentName`     — Value written to agent_runs.agent_name by the
 *                      sub-agent module (used by the AgentRunsTab filter)
 */
export interface AgentTab {
  slug: string
  contentType: string
  label: string
  priority: number
  agentName: string
}

export const CONTENT_AGENT_TABS: AgentTab[] = [
  { slug: 'breaking-news', contentType: 'breaking_news', label: 'Breaking News', priority: 1, agentName: 'sub_breaking_news' },
  { slug: 'threads',       contentType: 'thread',        label: 'Threads',       priority: 2, agentName: 'sub_threads' },
  { slug: 'quotes',        contentType: 'quote',         label: 'Quotes',        priority: 4, agentName: 'sub_quotes' },
  { slug: 'infographics',  contentType: 'infographic',   label: 'Infographics',  priority: 5, agentName: 'sub_infographics' },
  { slug: 'gold-media',    contentType: 'gold_media',    label: 'Gold Media',    priority: 6, agentName: 'sub_gold_media' },
  { slug: 'gold-history',  contentType: 'gold_history',  label: 'Gold History',  priority: 7, agentName: 'sub_gold_history' },
]

export function findTabBySlug(slug: string | undefined): AgentTab | undefined {
  if (!slug) return undefined
  return CONTENT_AGENT_TABS.find((t) => t.slug === slug)
}
