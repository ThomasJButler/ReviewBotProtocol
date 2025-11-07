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
import { Badge } from '@/components/ui/badge'
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
  GitPullRequest,
  Sparkles,
  Zap,
  Clock,
  AlertTriangle,
  Shield,
  TrendingUp,
  Bot,
} from 'lucide-react'
import { cn } from '@/lib/utils'

interface ReviewInterfaceProps {
  className?: string
  onReviewComplete?: (results: ReviewResultsDisplay) => void
}

// Convert ServiceReviewResults to ReviewResultsDisplay
function convertToDisplayResults(
  serviceResults: ServiceReviewResults
): ReviewResultsDisplay {
  // Safely handle potentially missing arrays with fallbacks
  const security = serviceResults.security || []
  const performance = serviceResults.performance || []
  const quality = serviceResults.quality || []

  const allFindings: ReviewFinding[] = [
    ...security.map(f => ({
      ...f,
      category: 'security' as const,
    })),
    ...performance.map(f => ({
      ...f,
      category: 'performance' as const,
    })),
    ...quality.map(f => ({
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
    summary: serviceResults.summary || 'Analysis completed',
    overallScore: serviceResults.score || 0,
    findings: allFindings,
    metrics: {
      totalIssues: serviceResults.totalIssues || 0,
      criticalIssues,
      highIssues,
      mediumIssues,
      lowIssues,
      securityIssues: security.length,
      performanceIssues: performance.length,
      qualityIssues: quality.length,
      linesAnalyzed: serviceResults.linesAnalyzed || 0,
      filesAnalyzed: 1,
    },
    duration: 0,
    aiModel: 'GPT-4',
  }
}

export default function ReviewInterface({
  className,
  onReviewComplete,
}: ReviewInterfaceProps) {
  const [reviewResults, setReviewResults] =
    useState<ReviewResultsDisplay | null>(null)
  const [selectedPR, setSelectedPR] = useState<PullRequest | null>(null)

  // Service hooks
  const { analyzePR, isLoading: isReviewing, error } = useReviewService()
  const { isAuthenticated, signIn } = useGitHubService()

  const handleReview = useCallback(async () => {
    if (!selectedPR) {
      return
    }

    if (!isAuthenticated) {
      console.error('Not authenticated')
      return
    }

    try {
      const prResults = await analyzePR(
        selectedPR.number,
        selectedPR.repository
      )

      if (prResults) {
        console.log('PR Results received:', prResults)
        console.log('Has security array?', Array.isArray(prResults.security))
        console.log(
          'Has performance array?',
          Array.isArray(prResults.performance)
        )
        console.log('Has quality array?', Array.isArray(prResults.quality))

        const results = convertToDisplayResults(prResults)
        console.log('Converted results:', results)
        setReviewResults(results)
        onReviewComplete?.(results)
      }
    } catch (err) {
      console.error('Review error:', err)
    }
  }, [selectedPR, isAuthenticated, analyzePR, onReviewComplete])

  const canReview = () => {
    return selectedPR !== null && isAuthenticated
  }

  const getEstimatedTime = () => {
    return selectedPR ? Math.max(15, selectedPR.changedFiles * 3) : 15
  }

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
            <span>Review GitHub Pull Request</span>
            {canReview() && (
              <Badge variant="outline" className="flex items-center gap-1">
                <Clock className="h-3 w-3" />~{getEstimatedTime()}s
              </Badge>
            )}
          </CardTitle>
          <CardDescription>
            Connect your GitHub account and select a pull request for automated
            AI-powered review
          </CardDescription>
        </CardHeader>

        <CardContent>
          <div className="space-y-6">
            <div className="text-center mb-6">
              <h3 className="text-2xl font-semibold text-white mb-2">
                Review GitHub PR
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
          </div>

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
                  Start AI Review
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
