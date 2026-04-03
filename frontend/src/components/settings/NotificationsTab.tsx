import { useState, useEffect } from 'react'
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

interface NotificationSectionProps {
  title: string
  keys: ConfigEntry[]
  formState: Record<string, string>
  onInputChange: (key: string, value: string) => void
  dirtyKeys: Set<string>
  onSave: (sectionKeys: string[]) => void
  isPending: boolean
}

function NotificationSection({ title, keys, formState, onInputChange, dirtyKeys, onSave, isPending }: NotificationSectionProps) {
  const sectionDirty = keys.some(e => dirtyKeys.has(e.key))

  return (
    <div className="mb-6">
      <h3 className="text-sm font-semibold mb-3">{title}</h3>
      <div className="space-y-3">
        {keys.map(entry => (
          <div key={entry.key} className="flex items-center gap-4">
            <label className="w-56 text-sm text-muted-foreground">{toLabel(entry.key)}</label>
            <input
              type="text"
              value={formState[entry.key] ?? entry.value}
              onChange={e => onInputChange(entry.key, e.target.value)}
              className="border rounded-md px-2 py-1 text-sm w-64"
            />
          </div>
        ))}
      </div>
      <Button
        size="sm"
        className="mt-3"
        disabled={!sectionDirty || isPending}
        onClick={() => onSave(keys.map(e => e.key))}
      >
        Save Notification Settings
      </Button>
    </div>
  )
}

export function NotificationsTab() {
  const queryClient = useQueryClient()
  const { data: config = [] } = useQuery({ queryKey: ['config'], queryFn: getConfig })

  const [formState, setFormState] = useState<Record<string, string>>({})
  const [dirtyKeys, setDirtyKeys] = useState<Set<string>>(new Set())

  useEffect(() => {
    const initial: Record<string, string> = {}
    config.forEach(e => { initial[e.key] = e.value })
    setFormState(initial)
    setDirtyKeys(new Set())
  }, [config])

  const { mutateAsync, isPending } = useMutation({
    mutationFn: ({ key, value }: { key: string; value: string }) => updateConfig(key, value),
  })

  function handleInputChange(key: string, value: string) {
    setFormState(prev => ({ ...prev, [key]: value }))
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
      await Promise.all(dirty.map(k => mutateAsync({ key: k, value: formState[k] })))
      toast.success('Notification settings saved')
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

  const notifKeys = config.filter(
    e =>
      e.key.includes('whatsapp') ||
      e.key.includes('alert') ||
      e.key.includes('notification') ||
      e.key.includes('digest_time'),
  )

  if (notifKeys.length === 0) {
    return <p className="text-sm text-muted-foreground p-4">No notification config keys found.</p>
  }

  return (
    <div className="p-4">
      <NotificationSection
        title="Notification Settings"
        keys={notifKeys}
        formState={formState}
        onInputChange={handleInputChange}
        dirtyKeys={dirtyKeys}
        onSave={handleSave}
        isPending={isPending}
      />
    </div>
  )
}
