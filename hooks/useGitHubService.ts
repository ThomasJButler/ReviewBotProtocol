import { useState, useCallback } from 'react'
import { toast } from 'react-hot-toast'

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
        throw new Error('Failed to fetch pull requests')
      }

      const result = await response.json()

      if (!result.success) {
        throw new Error(result.error || 'Failed to load pull requests')
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

  // Mock authentication status
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [user, setUser] = useState<{ name: string; avatar?: string } | null>(
    null
  )

  const signIn = useCallback(async () => {
    setIsLoading(true)
    try {
      // Simulate OAuth flow
      await new Promise(resolve => setTimeout(resolve, 1000))

      setIsAuthenticated(true)
      setUser({ name: 'Demo User', avatar: 'https://github.com/github.png' })
      toast.success('Successfully connected to GitHub!')

      // Auto-fetch PRs after authentication
      await fetchPullRequests()
    } catch (err) {
      toast.error('Failed to connect to GitHub')
    } finally {
      setIsLoading(false)
    }
  }, [fetchPullRequests])

  const signOut = useCallback(() => {
    setIsAuthenticated(false)
    setUser(null)
    setPullRequests([])
    toast.success('Disconnected from GitHub')
  }, [])

  return {
    // Data
    pullRequests,
    repositories,
    authors,
    isAuthenticated,
    user,

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
