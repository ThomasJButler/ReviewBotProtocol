'use client'

import React, { useState, useCallback } from 'react'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Badge } from '@/components/ui/badge'
import { Textarea } from '@/components/ui/textarea'
import CodeEditor from './CodeEditor'
import FileUpload from './FileUpload'
import PRSelector from './PRSelector'
import ReviewResults, {
  type ReviewResultsDisplay,
  type ReviewFinding,
} from './ReviewResults'
import {
  useReviewService,
  type ReviewResults as ServiceReviewResults,
} from '@/hooks/useReviewService'
import { type PullRequest } from '@/hooks/useGitHubService'
import { useGitHubService } from '@/hooks/useGitHubService'
import {
  FileText,
  Upload,
  GitPullRequest,
  Sparkles,
  Zap,
  Clock,
  CheckCircle2,
  AlertTriangle,
  Shield,
  TrendingUp,
  Bot,
} from 'lucide-react'
import { cn } from '@/lib/utils'

interface UploadedFile extends File {
  id: string
  status: 'pending' | 'uploading' | 'success' | 'error'
  error?: string
  progress?: number
}

interface ReviewInterfaceProps {
  className?: string
  onReviewComplete?: (results: ReviewResultsDisplay) => void
  maxFiles?: number
  maxFileSize?: number
}

type ReviewMode = 'paste' | 'upload' | 'pr'

interface ReviewRequest {
  mode: ReviewMode
  content?: string
  files?: File[]
  pullRequest?: PullRequest
}

// Convert ServiceReviewResults to ReviewResultsDisplay
function convertToDisplayResults(
  serviceResults: ServiceReviewResults
): ReviewResultsDisplay {
  const allFindings: ReviewFinding[] = [
    ...serviceResults.security.map(f => ({
      ...f,
      category: 'security' as const,
    })),
    ...serviceResults.performance.map(f => ({
      ...f,
      category: 'performance' as const,
    })),
    ...serviceResults.quality.map(f => ({
      ...f,
      category: 'quality' as const,
    })),
  ]

  const criticalIssues = allFindings.filter(
    f => f.severity === 'critical'
  ).length
  const highIssues = allFindings.filter(f => f.severity === 'high').length
  const mediumIssues = allFindings.filter(f => f.severity === 'medium').length
  const lowIssues = allFindings.filter(f => f.severity === 'low').length

  return {
    id: `review-${Date.now()}`,
    timestamp: new Date().toISOString(),
    summary: serviceResults.summary,
    overallScore: serviceResults.score,
    findings: allFindings,
    metrics: {
      totalIssues: serviceResults.totalIssues,
      criticalIssues,
      highIssues,
      mediumIssues,
      lowIssues,
      securityIssues: serviceResults.security.length,
      performanceIssues: serviceResults.performance.length,
      qualityIssues: serviceResults.quality.length,
      linesAnalyzed: serviceResults.linesAnalyzed || 0,
      filesAnalyzed: 1,
    },
    duration: 0, // Not available from service
    aiModel: 'GPT-4',
  }
}

export default function ReviewInterface({
  className,
  onReviewComplete,
  maxFiles = 10,
  maxFileSize = 50,
}: ReviewInterfaceProps) {
  const [activeMode, setActiveMode] = useState<ReviewMode>('paste')
  const [reviewResults, setReviewResults] =
    useState<ReviewResultsDisplay | null>(null)

  // Paste mode state
  const [codeInput, setCodeInput] = useState('')
  const [codeLanguage, setCodeLanguage] = useState('javascript')

  // Upload mode state
  const [selectedFiles, setSelectedFiles] = useState<UploadedFile[]>([])

  // PR mode state
  const [selectedPR, setSelectedPR] = useState<PullRequest | null>(null)

  // Service hooks
  const {
    analyzeCode,
    analyzeFiles,
    analyzePR,
    isLoading: isReviewing,
    error,
  } = useReviewService()
  const { isAuthenticated, signIn } = useGitHubService()

  const handleReview = useCallback(async () => {
    let results: ReviewResultsDisplay | null = null

    try {
      // Call appropriate service method based on mode
      switch (activeMode) {
        case 'paste':
          if (!codeInput.trim()) {
            throw new Error('Please enter some code to review')
          }
          const codeResults = await analyzeCode({
            code: codeInput,
            language: codeLanguage,
            mode: 'paste',
          })
          results = codeResults ? convertToDisplayResults(codeResults) : null
          break

        case 'upload':
          if (selectedFiles.length === 0) {
            throw new Error('Please select at least one file to review')
          }
          const files = selectedFiles.filter(
            f => f.status === 'success'
          ) as File[]
          const fileResults = await analyzeFiles(files)
          results = fileResults ? convertToDisplayResults(fileResults) : null
          break

        case 'pr':
          if (!selectedPR) {
            throw new Error('Please select a pull request to review')
          }
          if (!isAuthenticated) {
            throw new Error('Please connect to GitHub first')
          }
          const prResults = await analyzePR(
            selectedPR.number,
            selectedPR.repository
          )
          results = prResults ? convertToDisplayResults(prResults) : null
          break

        default:
          throw new Error('Invalid review mode')
      }

      if (results) {
        setReviewResults(results)
        onReviewComplete?.(results)
      }
    } catch (err) {
      // Error handling is managed by the service hooks
      console.error('Review error:', err)
    }
  }, [
    activeMode,
    codeInput,
    codeLanguage,
    selectedFiles,
    selectedPR,
    isAuthenticated,
    analyzeCode,
    analyzeFiles,
    analyzePR,
    onReviewComplete,
  ])

  const canReview = () => {
    switch (activeMode) {
      case 'paste':
        return codeInput.trim().length > 0
      case 'upload':
        return selectedFiles.length > 0
      case 'pr':
        return selectedPR !== null && isAuthenticated
      default:
        return false
    }
  }

  const getEstimatedTime = () => {
    switch (activeMode) {
      case 'paste':
        const lines = codeInput.split('\n').length
        return Math.max(5, Math.ceil(lines / 20)) // Roughly 1 second per 20 lines, min 5 seconds
      case 'upload':
        return Math.max(10, selectedFiles.length * 5) // 5 seconds per file, min 10 seconds
      case 'pr':
        return selectedPR ? Math.max(15, selectedPR.changedFiles * 3) : 15 // 3 seconds per changed file
      default:
        return 10
    }
  }

  const handleFilesSelected = useCallback((files: File[]) => {
    const uploadedFiles: UploadedFile[] = files.map(file => ({
      ...file,
      id: `${file.name}-${Date.now()}-${Math.random()}`,
      status: 'pending',
    }))
    setSelectedFiles(prev => [...prev, ...uploadedFiles])
  }, [])

  const handleFileRemoved = useCallback((fileId: string) => {
    setSelectedFiles(prev => prev.filter(f => f.id !== fileId))
  }, [])

  return (
    <div className={cn('space-y-8', className)}>
      {/* Header */}
      <div className="text-center">
        <div className="flex items-center justify-center gap-3 mb-4">
          <div className="relative">
            <Bot className="h-12 w-12 text-matrix-green" />
            <Sparkles className="h-6 w-6 text-matrix-cyan absolute -top-1 -right-1 animate-pulse" />
          </div>
          <div>
            <h1 className="text-4xl font-bold text-white">AI Code Review</h1>
            <p className="text-gray-400">Powered by advanced AI analysis</p>
          </div>
        </div>
        <p className="text-lg text-gray-300 max-w-2xl mx-auto">
          Get intelligent code reviews with security scanning, performance
          analysis, and quality insights
        </p>
      </div>

      {/* Main Interface */}
      <Card className="max-w-6xl mx-auto">
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span>Select Review Method</span>
            {canReview() && (
              <Badge variant="outline" className="flex items-center gap-1">
                <Clock className="h-3 w-3" />~{getEstimatedTime()}s
              </Badge>
            )}
          </CardTitle>
          <CardDescription>
            Choose how you'd like to submit your code for AI-powered analysis
          </CardDescription>
        </CardHeader>

        <CardContent>
          <Tabs
            value={activeMode}
            onValueChange={value => setActiveMode(value as ReviewMode)}
          >
            <TabsList className="grid w-full grid-cols-3 mb-8">
              <TabsTrigger value="paste" className="flex items-center gap-2">
                <FileText className="h-4 w-4" />
                📝 Paste Code
              </TabsTrigger>
              <TabsTrigger value="upload" className="flex items-center gap-2">
                <Upload className="h-4 w-4" />
                📁 Upload Files
              </TabsTrigger>
              <TabsTrigger value="pr" className="flex items-center gap-2">
                <GitPullRequest className="h-4 w-4" />
                🔗 Review PR
              </TabsTrigger>
            </TabsList>

            {/* Paste Code Tab */}
            <TabsContent value="paste" className="space-y-6">
              <div className="text-center mb-6">
                <h3 className="text-2xl font-semibold text-white mb-2">
                  📝 Paste Your Code
                </h3>
                <p className="text-gray-400">
                  Paste your code here for instant AI analysis
                </p>
              </div>

              <CodeEditor
                value={codeInput}
                onChange={value => setCodeInput(value || '')}
                language={codeLanguage}
                onLanguageChange={setCodeLanguage}
                height={400}
                placeholder="Paste your code here for review..."
                showMetrics={true}
              />
            </TabsContent>

            {/* Upload Files Tab */}
            <TabsContent value="upload" className="space-y-6">
              <div className="text-center mb-6">
                <h3 className="text-2xl font-semibold text-white mb-2">
                  📁 Upload Code Files
                </h3>
                <p className="text-gray-400">
                  Upload multiple files for comprehensive analysis
                </p>
              </div>

              <FileUpload
                onFilesSelected={handleFilesSelected}
                selectedFiles={selectedFiles}
                onRemoveFile={handleFileRemoved}
                maxFiles={maxFiles}
                maxSize={maxFileSize}
                multiple={true}
              />
            </TabsContent>

            {/* Review PR Tab */}
            <TabsContent value="pr" className="space-y-6">
              <div className="text-center mb-6">
                <h3 className="text-2xl font-semibold text-white mb-2">
                  🔗 Review GitHub PR
                </h3>
                <p className="text-gray-400">
                  Select a GitHub pull request for automated review
                </p>
              </div>

              {!isAuthenticated ? (
                <Card>
                  <CardContent className="p-8 text-center">
                    <GitPullRequest className="h-16 w-16 text-gray-400 mx-auto mb-4" />
                    <h3 className="text-xl font-semibold text-white mb-2">
                      Connect to GitHub
                    </h3>
                    <p className="text-gray-400 mb-6">
                      Connect your GitHub account to access and review pull
                      requests
                    </p>
                    <Button onClick={signIn} disabled={isReviewing}>
                      <GitPullRequest className="h-4 w-4 mr-2" />
                      Connect GitHub Account
                    </Button>
                  </CardContent>
                </Card>
              ) : (
                <PRSelector
                  onPRSelected={setSelectedPR}
                  selectedPR={selectedPR}
                  maxResults={20}
                  showFilters={true}
                />
              )}
            </TabsContent>
          </Tabs>

          {/* Action Button */}
          <div className="mt-8 text-center">
            <Button
              onClick={handleReview}
              disabled={!canReview() || isReviewing}
              size="lg"
              className="px-12 py-4 text-lg font-semibold"
            >
              {isReviewing ? (
                <>
                  <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-current mr-3" />
                  Analyzing Code...
                </>
              ) : (
                <>
                  <Zap className="h-5 w-5 mr-3" />
                  🔍 Start AI Review
                </>
              )}
            </Button>

            <p className="mt-4 text-gray-400 text-sm">
              Press{' '}
              <kbd className="px-2 py-1 bg-gray-700 rounded text-xs">
                ⌘ + Enter
              </kbd>{' '}
              or{' '}
              <kbd className="px-2 py-1 bg-gray-700 rounded text-xs">
                Ctrl + Enter
              </kbd>{' '}
              to start review
            </p>
          </div>

          {/* Error Display */}
          {error && (
            <div className="mt-6 p-4 rounded-lg bg-red-500/10 border border-red-500/30">
              <div className="flex items-center gap-2 text-red-400">
                <AlertTriangle className="h-5 w-5" />
                <span className="font-medium">Error:</span>
                <span>{error}</span>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Review Results */}
      {(reviewResults || isReviewing) && (
        <ReviewResults
          results={reviewResults}
          isLoading={isReviewing}
          onExport={() => console.log('Export results')}
          onShare={() => console.log('Share results')}
        />
      )}

      {/* Quick Stats */}
      {reviewResults && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-4xl mx-auto">
          <Card>
            <CardContent className="p-4 text-center">
              <Shield className="h-8 w-8 text-red-500 mx-auto mb-2" />
              <div className="text-2xl font-bold text-white">
                {reviewResults.metrics.securityIssues}
              </div>
              <div className="text-sm text-gray-400">Security Issues</div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-4 text-center">
              <Zap className="h-8 w-8 text-yellow-500 mx-auto mb-2" />
              <div className="text-2xl font-bold text-white">
                {reviewResults.metrics.performanceIssues}
              </div>
              <div className="text-sm text-gray-400">Performance Issues</div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-4 text-center">
              <TrendingUp className="h-8 w-8 text-blue-500 mx-auto mb-2" />
              <div className="text-2xl font-bold text-white">
                {reviewResults.overallScore}%
              </div>
              <div className="text-sm text-gray-400">Overall Score</div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  )
}

// Keyboard shortcut handler
export function useReviewShortcut(onReview: () => void, enabled: boolean) {
  React.useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'Enter' && enabled) {
        e.preventDefault()
        onReview()
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [onReview, enabled])
}
