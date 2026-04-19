import { useState } from 'react'
import { Textarea } from '@/components/ui/textarea'

interface InlineEditorProps {
  text: string
  isEditing: boolean
  onStartEdit: () => void
  onSave: (text: string) => void
  onCancel: () => void
  /** Called on every keystroke in edit mode so parent can track current value */
  onEditChange?: (text: string) => void
}

export function InlineEditor({
  text,
  isEditing,
  onStartEdit,
  onSave,
  onCancel,
  onEditChange,
}: InlineEditorProps) {
  // "Storing information from previous renders" pattern from react.dev:
  // track the previous `text` prop in state and, when it changes while the user
  // is NOT editing, reset `editValue` during render (no effect, no ref). This is
  // the officially-recommended alternative to "Syncing state to props with useEffect".
  const [editValue, setEditValue] = useState(text)
  const [prevText, setPrevText] = useState(text)
  if (!isEditing && prevText !== text) {
    setPrevText(text)
    setEditValue(text)
  }

  function handleChange(value: string) {
    setEditValue(value)
    onEditChange?.(value)
  }

  if (isEditing) {
    return (
      <div className="space-y-2">
        <Textarea
          value={editValue}
          onChange={(e) => handleChange(e.target.value)}
          className="border-ring ring-2 ring-ring/30 text-sm"
          autoFocus
        />
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => onSave(editValue)}
            className="text-xs font-medium text-primary hover:underline"
          >
            Save
          </button>
          <button
            type="button"
            onClick={onCancel}
            className="text-xs text-muted-foreground hover:text-foreground"
          >
            Cancel
          </button>
        </div>
      </div>
    )
  }

  return (
    <p
      role="button"
      tabIndex={0}
      onClick={onStartEdit}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') onStartEdit()
      }}
      className="cursor-pointer rounded text-sm leading-relaxed hover:bg-muted/50 p-1 -m-1 transition-colors"
      title="Click to edit"
    >
      {text}
    </p>
  )
}
