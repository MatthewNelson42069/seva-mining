import { useMutation, useQueryClient } from '@tanstack/react-query'
import { approveItem } from '@/api/queue'
import { toast } from 'sonner'

export function useApprove(platform: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, editedText }: { id: string; editedText?: string }) =>
      approveItem(id, editedText),
    onSuccess: (data, variables) => {
      // Per D-06 + D-09: copy approved text to clipboard
      const textToCopy = variables.editedText ?? data.alternatives?.[0]?.text ?? ''
      navigator.clipboard.writeText(textToCopy)
      toast.success('Approved — copied to clipboard')
      // Invalidate queue to remove approved card
      queryClient.invalidateQueries({ queryKey: ['queue', platform] })
    },
  })
}
