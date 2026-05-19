import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { createQueueUiSlice, type QueueUiSlice } from './slices/queueUiSlice'
import { createAuthSlice, type AuthSlice } from './slices/authSlice'
import { createCompanySlice, type CompanySlice } from './slices/companySlice'

type AppStore = QueueUiSlice & AuthSlice & CompanySlice

/**
 * v3.0 Phase 9 (TENANT-07, D-08) — Zustand app store wrapped with `persist`
 * middleware. ONLY `lastVisitedCompany` is persisted via partialize; auth
 * already manages its own localStorage write inside authSlice (no
 * double-write) and queueUi state stays in-memory only.
 *
 * Persist key `seva-mining-app-state-v3` per CONTEXT.md Claude's-discretion.
 */
export const useAppStore = create<AppStore>()(
  persist(
    (set) => ({
      ...createQueueUiSlice(set as Parameters<typeof createQueueUiSlice>[0]),
      ...createAuthSlice(set as Parameters<typeof createAuthSlice>[0]),
      ...createCompanySlice(set as Parameters<typeof createCompanySlice>[0]),
    }),
    {
      name: 'seva-mining-app-state-v3',
      // Only persist the lastVisitedCompany slot — queue UI + auth stay
      // in memory (auth has its own localStorage write inside authSlice;
      // no double-write).
      partialize: (state) => ({
        lastVisitedCompany: state.lastVisitedCompany,
      }),
    },
  ),
)
