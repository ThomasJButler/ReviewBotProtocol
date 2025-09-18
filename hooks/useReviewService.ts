import { useState, useCallback } from 'react'
import { toast } from 'react-hot-toast'

export interface ReviewRequest {
  code: string
  language?: string
  filename?: string
  mode?: 'paste' | 'upload' | 'pr'
}

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

  const analyzeCode = useCallback(
    async (request: ReviewRequest): Promise<ReviewResults | null> => {
      setIsLoading(true)
      setError(null)

      try {
        const response = await fetch('/api/review', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(request),
        })

        if (!response.ok) {
          const errorData = await response.json()
          throw new Error(errorData.error || 'Failed to analyze code')
        }

        const result = await response.json()

        if (!result.success) {
          throw new Error(result.error || 'Analysis failed')
        }

        toast.success('Code analysis completed successfully!')
        return result.data
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : 'An unexpected error occurred'
        setError(errorMessage)
        toast.error(`Analysis failed: ${errorMessage}`)
        return null
      } finally {
        setIsLoading(false)
      }
    },
    []
  )

  const analyzeFiles = useCallback(
    async (files: File[]): Promise<ReviewResults | null> => {
      if (files.length === 0) {
        setError('No files provided')
        return null
      }

      // For demo, we'll analyze the first file
      const file = files[0]
      const code = await file.text()

      return analyzeCode({
        code,
        filename: file.name,
        language: detectLanguage(file.name),
        mode: 'upload',
      })
    },
    [analyzeCode]
  )

  const analyzePR = useCallback(
    async (
      prNumber: number,
      repository: string
    ): Promise<ReviewResults | null> => {
      setIsLoading(true)
      setError(null)

      try {
        // Get PR details first
        const prResponse = await fetch('/api/github/prs', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ prNumber, repository }),
        })

        if (!prResponse.ok) {
          throw new Error('Failed to fetch PR details')
        }

        const prData = await prResponse.json()

        if (!prData.success) {
          throw new Error('Failed to get PR data')
        }

        // Simulate analyzing PR files
        const mockCode = `
        // Simulated PR code analysis
        const userInput = req.body.input;
        const query = "SELECT * FROM users WHERE email = '" + userInput + "'";

        function processData(data) {
          for (let i = 0; i < data.length; i++) {
            for (let j = 0; j < data[i].items.length; j++) {
              // Nested processing
              console.log(data[i].items[j]);
            }
          }
        }
      `

        return analyzeCode({
          code: mockCode,
          language: 'javascript',
          mode: 'pr',
        })
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : 'An unexpected error occurred'
        setError(errorMessage)
        toast.error(`PR analysis failed: ${errorMessage}`)
        return null
      } finally {
        setIsLoading(false)
      }
    },
    [analyzeCode]
  )

  return {
    analyzeCode,
    analyzeFiles,
    analyzePR,
    isLoading,
    error,
    clearError: () => setError(null),
  }
}

function detectLanguage(filename: string): string {
  const extension = filename.split('.').pop()?.toLowerCase()

  const languageMap: Record<string, string> = {
    js: 'javascript',
    jsx: 'javascript',
    ts: 'typescript',
    tsx: 'typescript',
    py: 'python',
    java: 'java',
    cs: 'csharp',
    cpp: 'cpp',
    c: 'c',
    go: 'go',
    rs: 'rust',
    php: 'php',
    rb: 'ruby',
    swift: 'swift',
    kt: 'kotlin',
    scala: 'scala',
    html: 'html',
    css: 'css',
    scss: 'scss',
    sass: 'sass',
    json: 'json',
    xml: 'xml',
    yaml: 'yaml',
    yml: 'yaml',
    md: 'markdown',
    sql: 'sql',
    sh: 'shell',
    bash: 'shell',
  }

  return languageMap[extension || ''] || 'javascript'
}
