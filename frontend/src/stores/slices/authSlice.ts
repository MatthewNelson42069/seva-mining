export interface AuthSlice {
  token: string | null
  isAuthenticated: boolean
  setToken: (token: string) => void
  clearToken: () => void
}

function getStoredToken(): string | null {
  try {
    return typeof localStorage !== 'undefined' ? localStorage.getItem('access_token') : null
  } catch {
    return null
  }
}

export function createAuthSlice(
  set: (fn: (state: AuthSlice) => Partial<AuthSlice>, replace?: boolean) => void
): AuthSlice {
  const storedToken = getStoredToken()
  return {
    token: storedToken,
    isAuthenticated: !!storedToken,

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
