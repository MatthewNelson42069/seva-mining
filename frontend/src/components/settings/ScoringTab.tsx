import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { getConfig, updateConfig } from '@/api/settings'
import type { ConfigEntry } from '@/api/types'
import { Button } from '@/components/ui/button'

function toLabel(key: string): string {
  return key
    .split('_')
    .map(w => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')
}

function inputPropsForKey(key: string): { type: string; step: string; min: string; max: string } {
  if (key.includes('weight')) {
    return { type: 'number', step: '0.1', min: '0', max: '1' }
  }
  if (key.includes('threshold')) {
    return { type: 'number', step: '0.5', min: '0', max: '10' }
  }
  return { type: 'number', step: '0.1', min: '0', max: '100' }
}

interface SectionProps {
  title: string
  keys: ConfigEntry[]
  overrides: Record<string, string>
  onInputChange: (key: string, value: string) => void
  dirtyKeys: Set<string>
  onSave: (sectionKeys: string[]) => void
  isPending: boolean
}

function ScoringSection({ title, keys, overrides, onInputChange, dirtyKeys, onSave, isPending }: SectionProps) {
  const sectionDirty = keys.some(e => dirtyKeys.has(e.key))

  return (
    <div className="mb-6">
      <h3 className="text-sm font-semibold mb-3">{title}</h3>
      <div className="space-y-3">
        {keys.map(entry => {
          const inputProps = inputPropsForKey(entry.key)
          const displayValue = overrides[entry.key] !== undefined ? overrides[entry.key] : entry.value
          return (
            <div key={entry.key} className="flex items-center gap-4">
              <label className="w-56 text-sm text-muted-foreground">{toLabel(entry.key)}</label>
              <input
                {...inputProps}
                value={displayValue}
                onChange={e => onInputChange(entry.key, e.target.value)}
                className="border rounded-md px-2 py-1 text-sm w-28"
              />
            </div>
          )
        })}
      </div>
      <Button
        size="sm"
        className="mt-3"
        disabled={!sectionDirty || isPending}
        onClick={() => onSave(keys.map(e => e.key))}
      >
        Save Scoring Settings
      </Button>
    </div>
  )
}

export function ScoringTab() {
  const queryClient = useQueryClient()
  const { data: config = [] } = useQuery({ queryKey: ['config'], queryFn: getConfig })

  // Only track overrides (user edits) — don't copy entire config into state
  const [overrides, setOverrides] = useState<Record<string, string>>({})
  const [dirtyKeys, setDirtyKeys] = useState<Set<string>>(new Set())

  const { mutateAsync, isPending } = useMutation({
    mutationFn: ({ key, value }: { key: string; value: string }) => updateConfig(key, value),
  })

  function handleInputChange(key: string, value: string) {
    setOverrides(prev => ({ ...prev, [key]: value }))
    const original = config.find(e => e.key === key)?.value
    setDirtyKeys(prev => {
      const next = new Set(prev)
      if (value !== original) {
        next.add(key)
      } else {
        next.delete(key)
      }
      return next
    })
  }

  async function handleSave(sectionKeys: string[]) {
    const dirty = sectionKeys.filter(k => dirtyKeys.has(k))
    if (dirty.length === 0) return
    try {
      await Promise.all(dirty.map(k => mutateAsync({
        key: k,
        value: overrides[k] !== undefined ? overrides[k] : (config.find(e => e.key === k)?.value ?? ''),
      })))
      toast.success('Scoring settings saved')
      // Clear overrides for saved keys and remove from dirty set
      setOverrides(prev => {
        const next = { ...prev }
        dirty.forEach(k => delete next[k])
        return next
      })
      setDirtyKeys(prev => {
        const next = new Set(prev)
        dirty.forEach(k => next.delete(k))
        return next
      })
      queryClient.invalidateQueries({ queryKey: ['config'] })
    } catch {
      toast.error('Failed to save settings. Try again.')
    }
  }

  const contentKeys = config.filter(e => e.key.startsWith('content_'))
  const twitterScoringKeys = config.filter(
    e =>
      e.key.startsWith('twitter_') &&
      !e.key.includes('quota') &&
      !e.key.includes('monthly') &&
      !e.key.includes('schedule') &&
      !e.key.includes('interval'),
  )

  if (contentKeys.length === 0 && twitterScoringKeys.length === 0) {
    return <p className="text-sm text-muted-foreground p-4">No scoring config keys found.</p>
  }

  return (
    <div className="p-4">
      {contentKeys.length > 0 && (
        <ScoringSection
          title="Content Agent Scoring"
          keys={contentKeys}
          overrides={overrides}
          onInputChange={handleInputChange}
          dirtyKeys={dirtyKeys}
          onSave={handleSave}
          isPending={isPending}
        />
      )}
      {twitterScoringKeys.length > 0 && (
        <ScoringSection
          title="Twitter Agent Scoring"
          keys={twitterScoringKeys}
          overrides={overrides}
          onInputChange={handleInputChange}
          dirtyKeys={dirtyKeys}
          onSave={handleSave}
          isPending={isPending}
        />
      )}
    </div>
  )
}
