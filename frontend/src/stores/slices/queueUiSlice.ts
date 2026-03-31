export interface QueueUiSlice {
  editingCardId: string | null
  rejectionPanelCardId: string | null
  activeDraftTab: Record<string, number>  // cardId -> tab index
  fadingCardIds: Set<string>
  pendingTimeouts: Map<string, ReturnType<typeof setTimeout>>
  setEditingCard: (id: string | null) => void
  setRejectionPanel: (id: string | null) => void
  setActiveDraftTab: (cardId: string, tabIndex: number) => void
  startFadeOut: (cardId: string, timeoutId: ReturnType<typeof setTimeout>) => void
  cancelFadeOut: (cardId: string) => void
  clearAllPending: () => void
}

export function createQueueUiSlice(
  set: (
    fn: (state: QueueUiSlice) => Partial<QueueUiSlice>,
    replace?: boolean
  ) => void
): QueueUiSlice {
  return {
    editingCardId: null,
    rejectionPanelCardId: null,
    activeDraftTab: {},
    fadingCardIds: new Set<string>(),
    pendingTimeouts: new Map<string, ReturnType<typeof setTimeout>>(),

    setEditingCard: (id) =>
      set(() => ({ editingCardId: id })),

    setRejectionPanel: (id) =>
      set(() => ({ rejectionPanelCardId: id })),

    setActiveDraftTab: (cardId, tabIndex) =>
      set((state) => ({
        activeDraftTab: { ...state.activeDraftTab, [cardId]: tabIndex },
      })),

    startFadeOut: (cardId, timeoutId) =>
      set((state) => {
        const newFading = new Set(state.fadingCardIds)
        newFading.add(cardId)
        const newTimeouts = new Map(state.pendingTimeouts)
        newTimeouts.set(cardId, timeoutId)
        return { fadingCardIds: newFading, pendingTimeouts: newTimeouts }
      }),

    cancelFadeOut: (cardId) =>
      set((state) => {
        const timeout = state.pendingTimeouts.get(cardId)
        if (timeout !== undefined) clearTimeout(timeout)
        const newFading = new Set(state.fadingCardIds)
        newFading.delete(cardId)
        const newTimeouts = new Map(state.pendingTimeouts)
        newTimeouts.delete(cardId)
        return { fadingCardIds: newFading, pendingTimeouts: newTimeouts }
      }),

    clearAllPending: () =>
      set((state) => {
        state.pendingTimeouts.forEach((timeout) => clearTimeout(timeout))
        return {
          fadingCardIds: new Set<string>(),
          pendingTimeouts: new Map<string, ReturnType<typeof setTimeout>>(),
        }
      }),
  }
}
