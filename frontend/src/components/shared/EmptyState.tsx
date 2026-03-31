import { CheckCircle } from 'lucide-react'

export function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="w-12 h-12 rounded-full bg-green-50 flex items-center justify-center mb-4">
        <CheckCircle className="w-6 h-6 text-green-500" />
      </div>
      <h3 className="text-base font-medium text-gray-900 mb-2">Queue is clear</h3>
      <p className="text-sm text-muted-foreground max-w-xs leading-relaxed">
        All items have been reviewed. Agents will deliver new content when it&apos;s available.
      </p>
    </div>
  )
}
