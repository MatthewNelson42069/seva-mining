import { Badge } from '@/components/ui/badge'
import type { Platform } from '@/api/types'

interface RelatedCardBadgeProps {
  relatedId: string
  relatedPlatform: Platform
  onSwitchPlatform?: (platform: Platform) => void
}

const PLATFORM_LABELS: Record<Platform, string> = {
  twitter: 'Twitter',
  instagram: 'Instagram',
  content: 'Content',
}

export function RelatedCardBadge({ relatedId: _relatedId, relatedPlatform, onSwitchPlatform }: RelatedCardBadgeProps) {
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
