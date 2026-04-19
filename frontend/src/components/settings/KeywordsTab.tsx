import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog'
import {
  getKeywords,
  createKeyword,
  updateKeyword,
  deleteKeyword,
} from '@/api/settings'
import type { KeywordResponse } from '@/api/types'

export function KeywordsTab() {
  const queryClient = useQueryClient()
  const [showAddForm, setShowAddForm] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<KeywordResponse | null>(null)

  // Add form state
  const [addTerm, setAddTerm] = useState('')
  const [addPlatform, setAddPlatform] = useState('twitter')
  const [addWeight, setAddWeight] = useState(1.0)

  const { data: keywords = [], isLoading } = useQuery({
    queryKey: ['keywords'],
    queryFn: () => getKeywords(),
  })

  const createMutation = useMutation({
    mutationFn: createKeyword,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['keywords'] })
      setShowAddForm(false)
      setAddTerm('')
      setAddPlatform('twitter')
      setAddWeight(1.0)
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Parameters<typeof updateKeyword>[1] }) =>
      updateKeyword(id, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['keywords'] })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: deleteKeyword,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['keywords'] })
      setDeleteTarget(null)
    },
  })

  function handleAdd() {
    if (!addTerm.trim()) return
    createMutation.mutate({
      term: addTerm.trim(),
      platform: addPlatform,
      weight: addWeight,
      active: true,
    })
  }

  return (
    <div className="space-y-4 p-4">
      {/* Add button */}
      <div className="flex items-center justify-end">
        <Button size="sm" onClick={() => setShowAddForm(true)}>
          Add Keyword
        </Button>
      </div>

      {/* Table */}
      <div className="border rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-muted">
            <tr>
              <th className="px-4 py-3 text-left font-medium">Term</th>
              <th className="px-4 py-3 text-left font-medium">Platform</th>
              <th className="px-4 py-3 text-left font-medium">Weight</th>
              <th className="px-4 py-3 text-left font-medium">Active</th>
              <th className="px-4 py-3 text-left font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {/* Inline add form row */}
            {showAddForm && (
              <tr className="border-t bg-muted/30">
                <td className="px-4 py-2">
                  <input
                    className="border rounded px-2 py-1 text-sm w-full"
                    placeholder="keyword term"
                    value={addTerm}
                    onChange={e => setAddTerm(e.target.value)}
                  />
                </td>
                <td className="px-4 py-2">
                  <select
                    className="border rounded px-2 py-1 text-sm"
                    value={addPlatform}
                    onChange={e => setAddPlatform(e.target.value)}
                  >
                    <option value="twitter">twitter</option>
                    <option value="content">content</option>
                  </select>
                </td>
                <td className="px-4 py-2">
                  <input
                    className="border rounded px-2 py-1 text-sm w-20"
                    type="number"
                    min={0}
                    max={1}
                    step={0.1}
                    value={addWeight}
                    onChange={e => setAddWeight(parseFloat(e.target.value))}
                  />
                </td>
                <td className="px-4 py-2">—</td>
                <td className="px-4 py-2">
                  <div className="flex gap-1">
                    <Button
                      size="sm"
                      onClick={handleAdd}
                      disabled={createMutation.isPending}
                    >
                      Add
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => {
                        setShowAddForm(false)
                        setAddTerm('')
                        setAddPlatform('twitter')
                        setAddWeight(1.0)
                      }}
                    >
                      Cancel
                    </Button>
                  </div>
                </td>
              </tr>
            )}

            {/* Loading */}
            {isLoading && (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-muted-foreground">
                  Loading...
                </td>
              </tr>
            )}

            {/* Empty state */}
            {!isLoading && keywords.length === 0 && !showAddForm && (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-muted-foreground">
                  No keywords yet. Add keywords for the agent to monitor.
                </td>
              </tr>
            )}

            {/* Data rows */}
            {!isLoading && keywords.map(kw => (
              <tr key={kw.id} className="border-t">
                <td className="px-4 py-2">{kw.term}</td>
                <td className="px-4 py-2">{kw.platform ?? '—'}</td>
                <td className="px-4 py-2">
                  <input
                    type="number"
                    min={0}
                    max={1}
                    step={0.1}
                    defaultValue={kw.weight ?? 1.0}
                    className="border rounded px-2 py-1 text-sm w-20"
                    onBlur={e =>
                      updateMutation.mutate({
                        id: kw.id,
                        body: { weight: parseFloat(e.target.value) },
                      })
                    }
                  />
                </td>
                <td className="px-4 py-2">
                  <input
                    type="checkbox"
                    checked={kw.active}
                    className="accent-blue-600"
                    onChange={() =>
                      updateMutation.mutate({
                        id: kw.id,
                        body: { active: !kw.active },
                      })
                    }
                  />
                </td>
                <td className="px-4 py-2">
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => setDeleteTarget(kw)}
                  >
                    Delete
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Delete confirmation dialog */}
      <Dialog open={deleteTarget !== null} onOpenChange={open => { if (!open) setDeleteTarget(null) }}>
        <DialogContent showCloseButton={false}>
          <DialogHeader>
            <DialogTitle>Remove Keyword</DialogTitle>
            <DialogDescription>
              Remove &apos;{deleteTarget?.term}&apos; from {deleteTarget?.platform} keywords?
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>
              Keep Keyword
            </Button>
            <Button
              variant="destructive"
              onClick={() => deleteTarget && deleteMutation.mutate(deleteTarget.id)}
              disabled={deleteMutation.isPending}
            >
              Remove
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
