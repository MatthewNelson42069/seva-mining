import { useQuery } from '@tanstack/react-query'
import { getQuota } from '@/api/settings'

export function QuotaBar() {
  const { data: quota } = useQuery({
    queryKey: ['quota'],
    queryFn: getQuota,
  })

  if (!quota) return null

  const pct = Math.min(100, Math.round((quota.monthly_tweet_count / quota.monthly_cap) * 100))
  const barColor = pct >= 80 ? 'bg-red-500' : pct >= 60 ? 'bg-yellow-500' : 'bg-green-500'

  return (
    <div className="border rounded-lg p-4 mb-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium">X API Monthly Quota</span>
        <span className="text-xs text-muted-foreground">
          {quota.monthly_tweet_count.toLocaleString()} / {quota.monthly_cap.toLocaleString()} reads
        </span>
      </div>
      <div className="w-full bg-gray-100 rounded-full h-2">
        <div
          className={`${barColor} h-2 rounded-full transition-all`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <p className="text-xs text-muted-foreground mt-1">
        Resets {quota.reset_date} · Safety margin: {quota.quota_safety_margin.toLocaleString()}
      </p>
    </div>
  )
}
