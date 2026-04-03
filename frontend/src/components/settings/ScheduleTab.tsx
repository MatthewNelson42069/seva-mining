import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { getConfig, updateConfig } from '@/api/settings'
import { Button } from '@/components/ui/button'

function unitForKey(key: string): string {
  if (key.endsWith('_hour')) return 'hour'
  return 'hours'
}

function toLabel(key: string): string {
  return key
    .split('_')
    .map(w => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')
}

export function ScheduleTab() {
  const queryClient = useQueryClient()
  const { data: config = [] } = useQuery({ queryKey: ['config'], queryFn: getConfig })

  const [overrides, setOverrides] = useState<Record<string, string>>({})
  const [dirtyKeys, setDirtyKeys] = useState<Set<string>>(new Set())

  const { mutateAsync, isPending } = useMutation({
    mutationFn: ({ key, value }: { key: string; value: string }) => updateConfig(key, value),
  })

  const scheduleKeys = config.filter(
    e => e.key.includes('schedule') || e.key.includes('interval'),
  )

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

  async function handleSave() {
    const dirty = scheduleKeys.map(e => e.key).filter(k => dirtyKeys.has(k))
    if (dirty.length === 0) return
    try {
      await Promise.all(dirty.map(k => mutateAsync({
        key: k,
        value: overrides[k] !== undefined ? overrides[k] : (config.find(e => e.key === k)?.value ?? ''),
      })))
      toast.success('Schedule saved')
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

  return (
    <div className="p-4">
      <p className="text-sm text-muted-foreground mb-4">
        Schedule changes are saved to the database. They take effect on the next worker restart.
      </p>
      {scheduleKeys.length === 0 ? (
        <p className="text-sm text-muted-foreground">No schedule config keys found.</p>
      ) : (
        <>
          <div className="space-y-3 mb-4">
            {scheduleKeys.map(entry => {
              const displayValue = overrides[entry.key] !== undefined ? overrides[entry.key] : entry.value
              return (
                <div key={entry.key} className="flex items-center gap-4">
                  <label className="w-56 text-sm text-muted-foreground">{toLabel(entry.key)}</label>
                  <input
                    type="number"
                    min={1}
                    value={displayValue}
                    onChange={e => handleInputChange(entry.key, e.target.value)}
                    className="border rounded-md px-2 py-1 text-sm w-24"
                  />
                  <span className="text-sm text-muted-foreground">{unitForKey(entry.key)}</span>
                </div>
              )
            })}
          </div>
          <Button
            size="sm"
            disabled={dirtyKeys.size === 0 || isPending}
            onClick={handleSave}
          >
            Save Schedule
          </Button>
        </>
      )}
    </div>
  )
}
