export interface AuthSlice {
  token: string | null
  isAuthenticated: boolean
  setToken: (token: string) => void
  clearToken: () => void
}

export function createAuthSlice(
  set: (fn: (state: AuthSlice) => Partial<AuthSlice>, replace?: boolean) => void
): AuthSlice {
  return {
    token: localStorage.getItem('access_token'),
    isAuthenticated: !!localStorage.getItem('access_token'),

    setToken: (token) => {
      localStorage.setItem('access_token', token)
      set(() => ({ token, isAuthenticated: true }))
    },

    clearToken: () => {
      localStorage.removeItem('access_token')
      set(() => ({ token: null, isAuthenticated: false }))
    },
  }
}
