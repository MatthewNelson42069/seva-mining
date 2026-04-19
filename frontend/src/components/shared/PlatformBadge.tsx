import { MessageSquare, FileText } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import type { Platform } from '@/api/types'

const PLATFORM_CONFIG: Record<Platform, { label: string; icon: React.ElementType }> = {
  twitter: { label: 'Twitter', icon: MessageSquare },
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
