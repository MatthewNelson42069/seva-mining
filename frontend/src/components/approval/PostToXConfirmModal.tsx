import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'

interface PostToXConfirmModalProps {
  isOpen: boolean
  onClose: () => void
  onConfirm: () => void
  isPending: boolean
  contentType: 'breaking_news' | 'thread'
  /** For breaking_news: a single string. For thread: a list of tweet strings. */
  preview: string | string[]
}

/**
 * Phase B (quick-260424-l0d): confirmation modal before user-initiated
 * approve→post-to-X. Shows the exact text/thread that will be posted, plus
 * an irreversibility warning per CONTEXT.md D6.
 *
 * The body preview is read-only — editing happens upstream in the draft
 * card's edit-on-approve flow (D9). This modal is the last safety gate before
 * the irreversible POST /items/{id}/post-to-x.
 */
export function PostToXConfirmModal({
  isOpen,
  onClose,
  onConfirm,
  isPending,
  contentType,
  preview,
}: PostToXConfirmModalProps) {
  const tweets = Array.isArray(preview) ? preview : null

  return (
    <Dialog open={isOpen} onOpenChange={(open) => { if (!open && !isPending) onClose() }}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Post to X?</DialogTitle>
          <DialogDescription>
            This will immediately post to your X account. You can&apos;t undo this.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          {contentType === 'thread' && tweets ? (
            <ol className="space-y-2 list-decimal pl-5">
              {tweets.map((t, i) => (
                <li key={i} className="text-sm leading-relaxed whitespace-pre-wrap">
                  {t}
                </li>
              ))}
            </ol>
          ) : (
            <div className="bg-muted/50 rounded-lg p-3 border border-border">
              <p className="text-sm leading-relaxed whitespace-pre-wrap">
                {typeof preview === 'string' ? preview : ''}
              </p>
            </div>
          )}
          <p className="text-xs text-muted-foreground">
            {contentType === 'thread'
              ? `${tweets?.length ?? 0}-tweet thread will be posted as one chain.`
              : 'A single tweet will be posted.'}
          </p>
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={onClose}
            disabled={isPending}
          >
            Cancel
          </Button>
          <Button
            onClick={onConfirm}
            disabled={isPending}
          >
            {isPending ? 'Posting…' : 'Post to X'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
