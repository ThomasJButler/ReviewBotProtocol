import { useState, useCallback } from 'react'
import { toast } from 'react-hot-toast'
import { useAuth } from '@/contexts/AuthContext'

export interface PullRequest {
  id: number
  number: number
  title: string
  description: string
  author: string
  state: 'open' | 'closed' | 'draft'
  draft: boolean
  repository: string
  branch: string
  baseBranch: string
  createdAt: string
  updatedAt: string
  labels: string[]
  reviewStatus: 'pending' | 'approved' | 'changes_requested'
  checksStatus: 'pending' | 'success' | 'failed'
  changedFiles: number
  additions: number
  deletions: number
  commits: number
  url: string
}

export interface PRFilters {
  repository?: string
  state?: string
  search?: string
  author?: string
}

export function useGitHubService() {
  const [pullRequests, setPullRequests] = useState<PullRequest[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [repositories, setRepositories] = useState<string[]>([])
  const [authors, setAuthors] = useState<string[]>([])

  // Use real authentication from AuthContext
  const { isAuthenticated, user, login, logout } = useAuth()

  const fetchPullRequests = useCallback(async (filters: PRFilters = {}) => {
    setIsLoading(true)
    setError(null)

    try {
      const params = new URLSearchParams()
      Object.entries(filters).forEach(([key, value]) => {
        if (value) params.append(key, value)
      })

      const response = await fetch(`/api/github/prs?${params.toString()}`)

      if (!response.ok) {
        if (response.status === 401) {
          throw new Error(
            'Authentication required. Please connect your GitHub account.'
          )
        }
        throw new Error('Failed to fetch pull requests')
      }

      const result = await response.json()

      if (!result.success) {
        throw new Error(
          result.metadata?.error ||
            result.error ||
            'Failed to load pull requests'
        )
      }

      setPullRequests(result.data)
      setRepositories(result.metadata.repositories || [])
      setAuthors(result.metadata.authors || [])
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'An unexpected error occurred'
      setError(errorMessage)
      toast.error(`Failed to load PRs: ${errorMessage}`)
    } finally {
      setIsLoading(false)
    }
  }, [])

  const getPRDetails = useCallback(
    async (prNumber: number, repository: string) => {
      setIsLoading(true)
      setError(null)

      try {
        const response = await fetch('/api/github/prs', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ prNumber, repository }),
        })

        if (!response.ok) {
          if (response.status === 401) {
            throw new Error('Authentication required')
          }
          throw new Error('Failed to fetch PR details')
        }

        const result = await response.json()

        if (!result.success) {
          throw new Error(result.error || 'Failed to load PR details')
        }

        return result.data
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : 'An unexpected error occurred'
        setError(errorMessage)
        toast.error(`Failed to load PR details: ${errorMessage}`)
        return null
      } finally {
        setIsLoading(false)
      }
    },
    []
  )

  const refreshPRs = useCallback(
    (filters: PRFilters = {}) => {
      return fetchPullRequests(filters)
    },
    [fetchPullRequests]
  )

  // Use real authentication from AuthContext
  const signIn = useCallback(() => {
    login() // Redirects to /api/auth/github
  }, [login])

  const signOut = useCallback(() => {
    logout()
    setPullRequests([])
  }, [logout])

  return {
    // Data
    pullRequests,
    repositories,
    authors,
    isAuthenticated,
    user: user
      ? { name: user.name || user.login, avatar: user.avatar_url }
      : null,

    // State
    isLoading,
    error,

    // Actions
    fetchPullRequests,
    getPRDetails,
    refreshPRs,
    signIn,
    signOut,
    clearError: () => setError(null),
  }
}
