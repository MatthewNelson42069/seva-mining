import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import type { DraftAlternative } from '@/api/types'

interface DraftTabBarProps {
  alternatives: DraftAlternative[]
  activeIndex: number
  onTabChange: (index: number) => void
}

export function DraftTabBar({ alternatives, activeIndex, onTabChange }: DraftTabBarProps) {
  if (alternatives.length <= 1) return null

  return (
    <Tabs
      value={String(activeIndex)}
      onValueChange={(val) => onTabChange(Number(val))}
    >
      <TabsList className="h-7 p-0.5">
        {alternatives.map((alt, idx) => (
          <TabsTrigger
            key={idx}
            value={String(idx)}
            className="h-6 px-2 text-xs"
          >
            {alt.label}
          </TabsTrigger>
        ))}
      </TabsList>
    </Tabs>
  )
}
