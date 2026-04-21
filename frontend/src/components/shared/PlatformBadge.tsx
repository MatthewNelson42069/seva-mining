import { FileText } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import type { Platform } from '@/api/types'

// Single-agent post quick-260420-sn9 — content only. Twitter/Instagram purged.
const PLATFORM_CONFIG: Record<Platform, { label: string; icon: React.ElementType }> = {
  content: { label: 'Content', icon: FileText },
}

interface PlatformBadgeProps {
  platform: Platform
}

export function PlatformBadge({ platform }: PlatformBadgeProps) {
  const config = PLATFORM_CONFIG[platform]
  const Icon = config.icon
  return (
    <Badge variant="secondary" className="gap-1 text-xs font-medium">
      <Icon className="size-3" />
      {config.label}
    </Badge>
  )
}
