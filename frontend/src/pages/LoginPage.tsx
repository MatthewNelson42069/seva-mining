import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { login } from '@/api/auth'
import { useAppStore } from '@/stores'
import { Button } from '@/components/ui/button'

export function LoginPage() {
  const navigate = useNavigate()
  const isAuthenticated = useAppStore((s) => s.isAuthenticated)
  const setToken = useAppStore((s) => s.setToken)

  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (isAuthenticated) {
      navigate('/', { replace: true })
    }
  }, [isAuthenticated, navigate])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!password.trim()) return

    setLoading(true)
    setError('')

    try {
      const response = await login(password)
      setToken(response.access_token)
      navigate('/')
    } catch (err: unknown) {
      const status = (err as { status?: number })?.status
      if (status === 401 || status === 403) {
        setError('Incorrect password')
      } else {
        setError('Unable to connect. Please try again.')
      }
    } finally {
      setLoading(false)
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter') {
      handleSubmit(e as unknown as React.FormEvent)
    }
  }

  return (
    <div className="min-h-screen bg-white flex items-center justify-center">
      <div className="w-full max-w-sm px-8 py-10">
        {/* Logo / Title */}
        <div className="text-center mb-8">
          <h1 className="text-2xl font-semibold text-gray-900 tracking-tight">
            Seva Mining
          </h1>
          <p className="text-sm text-gray-500 mt-1">Approval Dashboard</p>
        </div>

        {/* Login Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Enter password"
              className="w-full h-9 rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-900 placeholder:text-gray-400 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-all"
              autoFocus
              autoComplete="current-password"
            />
          </div>

          <Button
            type="submit"
            className="w-full bg-blue-600 hover:bg-blue-700 text-white"
            disabled={loading || !password.trim()}
          >
            {loading ? 'Signing in...' : 'Sign in'}
          </Button>

          {error && (
            <p className="text-sm text-red-600 text-center">{error}</p>
          )}
        </form>
      </div>
    </div>
  )
}
