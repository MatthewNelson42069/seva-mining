import { Badge } from '@/components/ui/badge'
import type { Platform } from '@/api/types'

interface RelatedCardBadgeProps {
  relatedPlatform: Platform
  onSwitchPlatform?: (platform: Platform) => void
}

// Single-agent post quick-260420-sn9 — content only.
const PLATFORM_LABELS: Record<Platform, string> = {
  content: 'Content',
}

export function RelatedCardBadge({ relatedPlatform, onSwitchPlatform }: RelatedCardBadgeProps) {
  function handleClick() {
    onSwitchPlatform?.(relatedPlatform)
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      className="focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded"
    >
      <Badge
        variant="outline"
        className="cursor-pointer hover:bg-muted transition-colors text-xs"
      >
        Also on {PLATFORM_LABELS[relatedPlatform]}
      </Badge>
    </button>
  )
}
