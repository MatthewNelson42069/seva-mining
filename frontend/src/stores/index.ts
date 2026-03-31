import { create } from 'zustand'
import { createQueueUiSlice, type QueueUiSlice } from './slices/queueUiSlice'
import { createAuthSlice, type AuthSlice } from './slices/authSlice'

type AppStore = QueueUiSlice & AuthSlice

export const useAppStore = create<AppStore>()((set) => ({
  ...createQueueUiSlice(set as Parameters<typeof createQueueUiSlice>[0]),
  ...createAuthSlice(set as Parameters<typeof createAuthSlice>[0]),
}))
