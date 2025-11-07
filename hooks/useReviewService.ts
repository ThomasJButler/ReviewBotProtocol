import { useState, useCallback } from 'react'
import { toast } from 'react-hot-toast'

export interface ReviewFinding {
  id: string
  title: string
  description: string
  severity: 'critical' | 'high' | 'medium' | 'low' | 'info'
  category: 'security' | 'performance' | 'quality'
  lineNumber?: number
  code?: string
  suggestion?: string
}

export interface ReviewResults {
  security: ReviewFinding[]
  performance: ReviewFinding[]
  quality: ReviewFinding[]
  summary: string
  score: number
  totalIssues: number
  analysisTime?: string
  linesAnalyzed?: number
}

export function useReviewService() {
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const analyzePR = useCallback(
    async (
      prNumber: number,
      repository: string
    ): Promise<ReviewResults | null> => {
      setIsLoading(true)
      setError(null)

      try {
        console.log(`Starting PR analysis for #${prNumber} in ${repository}`)

        // Call the backend API to analyze the PR with timeout
        const controller = new AbortController()
        const timeoutId = setTimeout(() => controller.abort(), 120000) // 2 minute timeout

        const response = await fetch('/api/review/pr', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            prNumber,
            repository,
          }),
          signal: controller.signal,
        })

        clearTimeout(timeoutId)
        console.log(`API response status: ${response.status}`)

        if (!response.ok) {
          const errorData = await response.json()
          throw new Error(errorData.error || 'Failed to analyze PR')
        }

        const result = await response.json()
        console.log('API response data:', result)

        if (!result.success) {
          throw new Error(result.error || 'PR analysis failed')
        }

        console.log('PR analysis completed successfully!')
        toast.success('PR analysis completed successfully!')
        return result.data
      } catch (err) {
        console.error('PR analysis error:', err)

        let errorMessage = 'An unexpected error occurred'

        if (err instanceof Error) {
          if (err.name === 'AbortError') {
            errorMessage =
              'Request timed out after 2 minutes. Please try again.'
          } else {
            errorMessage = err.message
          }
        }

        setError(errorMessage)
        toast.error(`PR analysis failed: ${errorMessage}`)
        return null
      } finally {
        setIsLoading(false)
      }
    },
    []
  )

  return {
    analyzePR,
    isLoading,
    error,
    clearError: () => setError(null),
  }
}
