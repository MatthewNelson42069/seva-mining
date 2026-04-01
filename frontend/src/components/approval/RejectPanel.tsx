import { useState } from 'react'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Textarea } from '@/components/ui/textarea'
import { Button } from '@/components/ui/button'
import { REJECTION_CATEGORIES, type RejectionCategory } from '@/api/types'

const CATEGORY_LABELS: Record<RejectionCategory, string> = {
  'off-topic': 'Off-topic',
  'low-quality': 'Low quality',
  'bad-timing': 'Bad timing',
  'tone-wrong': 'Tone wrong',
  'duplicate': 'Duplicate',
}

interface RejectPanelProps {
  isOpen: boolean
  onConfirm: (category: RejectionCategory, notes?: string) => void
  onCancel: () => void
}

export function RejectPanel({ isOpen, onConfirm, onCancel }: RejectPanelProps) {
  const [selectedCategory, setSelectedCategory] = useState<string>('')
  const [notes, setNotes] = useState('')

  if (!isOpen) return null

  const handleConfirm = () => {
    if (!selectedCategory) return
    onConfirm(selectedCategory as RejectionCategory, notes.trim() || undefined)
    setSelectedCategory('')
    setNotes('')
  }

  return (
    <div className="mt-3 rounded-lg border bg-muted/30 p-3 space-y-3">
      <RadioGroup
        value={selectedCategory}
        onValueChange={(val) => setSelectedCategory(val as RejectionCategory)}
      >
        {REJECTION_CATEGORIES.map((cat) => (
          <div key={cat} className="flex items-center gap-2">
            <RadioGroupItem value={cat} id={`reject-${cat}`} />
            <label htmlFor={`reject-${cat}`} className="text-sm cursor-pointer select-none">
              {CATEGORY_LABELS[cat]}
            </label>
          </div>
        ))}
      </RadioGroup>

      <Textarea
        placeholder="Optional notes..."
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        className="text-sm min-h-[60px]"
      />

      <div className="flex gap-2">
        <Button
          size="sm"
          variant="destructive"
          onClick={handleConfirm}
          disabled={!selectedCategory}
        >
          Confirm Reject
        </Button>
        <Button
          size="sm"
          variant="ghost"
          onClick={onCancel}
        >
          Cancel
        </Button>
      </div>
    </div>
  )
}
