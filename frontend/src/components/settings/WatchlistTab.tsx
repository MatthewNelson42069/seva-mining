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
  getWatchlists,
  createWatchlist,
  updateWatchlist,
  deleteWatchlist,
} from '@/api/settings'
import type { WatchlistResponse } from '@/api/types'

export function WatchlistTab() {
  const queryClient = useQueryClient()
  const [platform, setPlatform] = useState<'twitter' | 'instagram'>('twitter')
  const [showAddForm, setShowAddForm] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<WatchlistResponse | null>(null)

  // Add form state
  const [addHandle, setAddHandle] = useState('')
  const [addRelValue, setAddRelValue] = useState(5)
  const [addNotes, setAddNotes] = useState('')

  // Edit form state
  const [editRelValue, setEditRelValue] = useState(5)
  const [editNotes, setEditNotes] = useState('')

  const { data: watchlists = [], isLoading } = useQuery({
    queryKey: ['watchlists', platform],
    queryFn: () => getWatchlists(platform),
  })

  const createMutation = useMutation({
    mutationFn: createWatchlist,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['watchlists', platform] })
      setShowAddForm(false)
      setAddHandle('')
      setAddRelValue(5)
      setAddNotes('')
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Parameters<typeof updateWatchlist>[1] }) =>
      updateWatchlist(id, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['watchlists', platform] })
      setEditingId(null)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: deleteWatchlist,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['watchlists', platform] })
      setDeleteTarget(null)
    },
  })

  function handleStartEdit(entry: WatchlistResponse) {
    setEditingId(entry.id)
    setEditRelValue(entry.relationship_value ?? 5)
    setEditNotes(entry.notes ?? '')
  }

  function handleSaveEdit(id: string) {
    updateMutation.mutate({ id, body: { relationship_value: editRelValue, notes: editNotes } })
  }

  function handleAdd() {
    if (!addHandle.trim()) return
    createMutation.mutate({
      platform,
      account_handle: addHandle.trim(),
      relationship_value: addRelValue,
      notes: addNotes,
      active: true,
    })
  }

  return (
    <div className="space-y-4 p-4">
      {/* Platform filter + Add button */}
      <div className="flex items-center justify-between">
        <div className="flex gap-2">
          <Button
            size="sm"
            variant={platform === 'twitter' ? 'default' : 'outline'}
            onClick={() => setPlatform('twitter')}
          >
            Twitter
          </Button>
          <Button
            size="sm"
            variant={platform === 'instagram' ? 'default' : 'outline'}
            onClick={() => setPlatform('instagram')}
          >
            Instagram
          </Button>
        </div>
        <Button size="sm" onClick={() => setShowAddForm(true)}>
          Add Account
        </Button>
      </div>

      {/* Table */}
      <div className="border rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-muted">
            <tr>
              <th className="px-4 py-3 text-left font-medium">Account Handle</th>
              <th className="px-4 py-3 text-left font-medium">Platform</th>
              <th className="px-4 py-3 text-left font-medium">Relationship Value</th>
              <th className="px-4 py-3 text-left font-medium">Notes</th>
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
                    placeholder="@handle"
                    value={addHandle}
                    onChange={e => setAddHandle(e.target.value)}
                  />
                </td>
                <td className="px-4 py-2 text-muted-foreground">{platform}</td>
                <td className="px-4 py-2">
                  <input
                    className="border rounded px-2 py-1 text-sm w-20"
                    type="number"
                    min={1}
                    max={5}
                    value={addRelValue}
                    onChange={e => setAddRelValue(Number(e.target.value))}
                  />
                </td>
                <td className="px-4 py-2">
                  <textarea
                    className="border rounded px-2 py-1 text-sm w-full"
                    rows={1}
                    value={addNotes}
                    onChange={e => setAddNotes(e.target.value)}
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
                      Save
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => {
                        setShowAddForm(false)
                        setAddHandle('')
                        setAddRelValue(5)
                        setAddNotes('')
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
                <td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">
                  Loading...
                </td>
              </tr>
            )}

            {/* Empty state */}
            {!isLoading && watchlists.length === 0 && !showAddForm && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">
                  No {platform} watchlist entries yet. Add accounts for the agent to monitor.
                </td>
              </tr>
            )}

            {/* Data rows */}
            {!isLoading && watchlists.map(entry => (
              <tr key={entry.id} className="border-t">
                {editingId === entry.id ? (
                  <>
                    <td className="px-4 py-2">{entry.account_handle}</td>
                    <td className="px-4 py-2">{entry.platform}</td>
                    <td className="px-4 py-2">
                      <input
                        className="border rounded px-2 py-1 text-sm w-20"
                        type="number"
                        min={1}
                        max={5}
                        value={editRelValue}
                        onChange={e => setEditRelValue(Number(e.target.value))}
                      />
                    </td>
                    <td className="px-4 py-2">
                      <textarea
                        className="border rounded px-2 py-1 text-sm w-full"
                        rows={1}
                        value={editNotes}
                        onChange={e => setEditNotes(e.target.value)}
                      />
                    </td>
                    <td className="px-4 py-2">{entry.active ? 'Yes' : 'No'}</td>
                    <td className="px-4 py-2">
                      <div className="flex gap-1">
                        <Button
                          size="sm"
                          onClick={() => handleSaveEdit(entry.id)}
                          disabled={updateMutation.isPending}
                        >
                          Save
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => setEditingId(null)}
                        >
                          Cancel
                        </Button>
                      </div>
                    </td>
                  </>
                ) : (
                  <>
                    <td className="px-4 py-2">{entry.account_handle}</td>
                    <td className="px-4 py-2">{entry.platform}</td>
                    <td className="px-4 py-2">{entry.relationship_value ?? '—'}</td>
                    <td className="px-4 py-2 text-muted-foreground">{entry.notes ?? '—'}</td>
                    <td className="px-4 py-2">{entry.active ? 'Yes' : 'No'}</td>
                    <td className="px-4 py-2">
                      <div className="flex gap-1">
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => handleStartEdit(entry)}
                        >
                          Edit
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => setDeleteTarget(entry)}
                        >
                          Delete
                        </Button>
                      </div>
                    </td>
                  </>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Delete confirmation dialog */}
      <Dialog open={deleteTarget !== null} onOpenChange={open => { if (!open) setDeleteTarget(null) }}>
        <DialogContent showCloseButton={false}>
          <DialogHeader>
            <DialogTitle>Remove Account</DialogTitle>
            <DialogDescription>
              Remove {deleteTarget?.account_handle} from the {deleteTarget?.platform} watchlist? This will stop the agent from tracking this account.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>
              Keep Account
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
