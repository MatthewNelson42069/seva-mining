import { useMutation, useQueryClient } from '@tanstack/react-query'
import { rejectItem } from '@/api/queue'
import type { RejectionCategory } from '@/api/types'
import { toast } from 'sonner'

export function useReject(platform: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, category, notes }: { id: string; category: RejectionCategory; notes?: string }) =>
      rejectItem(id, category, notes),
    onSuccess: () => {
      toast.success('Rejected')
      queryClient.invalidateQueries({ queryKey: ['queue', platform] })
    },
  })
}
