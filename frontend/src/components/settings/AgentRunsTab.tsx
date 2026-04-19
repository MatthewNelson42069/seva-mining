import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { format, parseISO } from 'date-fns'
import { getAgentRuns } from '@/api/settings'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { QuotaBar } from './QuotaBar'

const AGENT_OPTIONS = [
  { value: '', label: 'All agents' },
  { value: 'twitter_agent', label: 'twitter_agent' },
  { value: 'content_agent', label: 'content_agent' },
  { value: 'senior_agent', label: 'senior_agent' },
]

export function AgentRunsTab() {
  const [agentFilter, setAgentFilter] = useState('')
  const [viewingErrors, setViewingErrors] = useState<unknown>(null)

  const { data: runs = [], isLoading } = useQuery({
    queryKey: ['agentRuns', agentFilter || undefined, 7],
    queryFn: () => getAgentRuns(agentFilter || undefined, 7),
  })

  return (
    <div className="p-4">
      <QuotaBar />

      <div className="flex items-center gap-3 mb-4">
        <label className="text-sm text-muted-foreground">Filter:</label>
        <select
          value={agentFilter}
          onChange={e => setAgentFilter(e.target.value)}
          className="border rounded-md text-sm px-3 py-1.5"
        >
          {AGENT_OPTIONS.map(opt => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading...</p>
      ) : runs.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No agent runs yet. Runs will appear here once agents start executing.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-muted-foreground">
                <th className="pb-2 pr-4 font-medium">Agent</th>
                <th className="pb-2 pr-4 font-medium">Started</th>
                <th className="pb-2 pr-4 font-medium">Status</th>
                <th className="pb-2 pr-4 font-medium">Found</th>
                <th className="pb-2 pr-4 font-medium">Queued</th>
                <th className="pb-2 pr-4 font-medium">Filtered</th>
                <th className="pb-2 font-medium">Errors</th>
              </tr>
            </thead>
            <tbody>
              {runs.map(run => (
                <tr key={run.id} className="border-b last:border-0">
                  <td className="py-2 pr-4 font-mono text-xs">{run.agent_name}</td>
                  <td className="py-2 pr-4 text-muted-foreground">
                    {format(parseISO(run.started_at), 'MMM d, HH:mm')}
                  </td>
                  <td className="py-2 pr-4">
                    <Badge variant={run.status === 'success' ? 'default' : 'destructive'}>
                      {run.status}
                    </Badge>
                  </td>
                  <td className="py-2 pr-4">{run.items_found ?? '—'}</td>
                  <td className="py-2 pr-4">{run.items_queued ?? '—'}</td>
                  <td className="py-2 pr-4">{run.items_filtered ?? '—'}</td>
                  <td className="py-2">
                    {run.errors != null ? (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setViewingErrors(run.errors)}
                      >
                        View Errors
                      </Button>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Dialog open={!!viewingErrors} onOpenChange={open => { if (!open) setViewingErrors(null) }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Agent Run Errors</DialogTitle>
          </DialogHeader>
          <pre className="text-xs font-mono whitespace-pre-wrap overflow-auto max-h-96">
            {JSON.stringify(viewingErrors, null, 2)}
          </pre>
        </DialogContent>
      </Dialog>
    </div>
  )
}
