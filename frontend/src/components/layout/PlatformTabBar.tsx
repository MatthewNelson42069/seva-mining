import type { Platform } from '@/api/types'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'

interface PlatformTabBarProps {
  activeTab: Platform
  onTabChange: (tab: Platform) => void
  counts: Record<Platform, number>
}

const PLATFORMS: { value: Platform; label: string }[] = [
  { value: 'twitter', label: 'Twitter' },
  { value: 'instagram', label: 'Instagram' },
  { value: 'content', label: 'Content' },
]

export function PlatformTabBar({ activeTab, onTabChange, counts }: PlatformTabBarProps) {
  return (
    <Tabs
      value={activeTab}
      onValueChange={(val) => onTabChange(val as Platform)}
    >
      <TabsList variant="line" className="border-b border-border w-full rounded-none px-6 pb-0 h-auto bg-card">
        {PLATFORMS.map(({ value, label }) => (
          <TabsTrigger
            key={value}
            value={value}
            className="pb-3 pt-1 data-active:text-amber-600 data-active:border-b-2 data-active:border-amber-500"
          >
            {label}
            {counts[value] > 0 && (
              <span className="ml-1.5 inline-flex items-center justify-center min-w-[18px] h-[18px] rounded-full bg-amber-100 text-amber-700 text-xs font-medium px-1">
                {counts[value]}
              </span>
            )}
          </TabsTrigger>
        ))}
      </TabsList>
    </Tabs>
  )
}
