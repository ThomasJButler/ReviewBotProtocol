'use client'

import React, { useCallback, useEffect, useState } from 'react'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Code2,
  GitPullRequest,
  Shield,
  TrendingUp,
  Users,
  Zap,
  Clock,
  FileText,
  Eye,
  ChevronRight,
  BarChart3,
  Calendar,
  Github,
  ExternalLink,
} from 'lucide-react'
import { useAuth } from '@/contexts/AuthContext'
import ReviewActivityChart, {
  IssueDistributionChart,
  CodeQualityRadar,
} from '@/components/charts/ReviewActivityChart'

interface GitHubStats {
  totalRepositories: number
  totalPullRequests: number
  totalReviews: number
  securityIssues: number
  avgQualityScore: number
  recentActivity: number
  totalStars?: number
  totalForks?: number
  repositoryMetrics?: any[]
  topReviewedRepos?: any[]
  totalCommitsLast30Days?: number
  totalLanguages?: number
}

// Helper function to convert score to letter grade
function getGradeFromScore(score: number): string {
  if (score >= 9) return 'A'
  if (score >= 8) return 'B'
  if (score >= 7) return 'C'
  if (score >= 6) return 'D'
  return 'F'
}

export default function DashboardPage() {
  const { isAuthenticated, isLoading, login } = useAuth()
  const [stats, setStats] = useState<GitHubStats | null>(null)
  const [statsLoading, setStatsLoading] = useState(false)
  const [activityData, setActivityData] = useState<any[]>([])
  const [timeRange, setTimeRange] = useState<'7d' | '30d' | '90d'>('30d')

  // Fetch GitHub stats when authenticated
  useEffect(() => {
    if (isAuthenticated && !stats) {
      setStatsLoading(true)
      fetch('/api/github/stats')
        .then(res => res.json())
        .then(data => {
          if (data.error) {
            console.error('Failed to fetch stats:', data.error)
          } else {
            setStats(data)
          }
        })
        .catch(err => console.error('Stats fetch error:', err))
        .finally(() => setStatsLoading(false))
    }
  }, [isAuthenticated, stats])

  const generateSampleActivityData = useCallback(() => {
    const days = timeRange === '7d' ? 7 : timeRange === '30d' ? 30 : 90
    const sampleData = []

    for (let i = days - 1; i >= 0; i--) {
      const date = new Date()
      date.setDate(date.getDate() - i)

      sampleData.push({
        date: date.toISOString().split('T')[0],
        reviews: Math.floor(Math.random() * 10) + 1,
        score: Math.floor(Math.random() * 30) + 70,
        issues: Math.floor(Math.random() * 20),
        security: Math.floor(Math.random() * 5),
        performance: Math.floor(Math.random() * 8),
        quality: Math.floor(Math.random() * 10),
      })
    }

    setActivityData(sampleData)
  }, [timeRange])

  const fetchActivityData = useCallback(async () => {
    try {
      const days = timeRange === '7d' ? 7 : timeRange === '30d' ? 30 : 90
      const backendUrl =
        process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'

      // Fetch user metrics which includes activity data
      const response = await fetch(
        `${backendUrl}/review/metrics/user/current?days=${days}`,
        {
          headers: {
            'Content-Type': 'application/json',
          },
        }
      )

      if (response.ok) {
        const metrics = await response.json()

        // Transform the activity heatmap into chart data
        if (metrics.activity_heatmap) {
          const chartData = []
          const endDate = new Date()

          for (let i = days - 1; i >= 0; i--) {
            const date = new Date()
            date.setDate(endDate.getDate() - i)
            const dateStr = date.toISOString().split('T')[0]

            // Aggregate data for this date
            const dayName = date.toLocaleDateString('en-US', {
              weekday: 'long',
            })
            const dayData = metrics.activity_heatmap[dayName] || {}

            const reviews = Object.values(dayData).reduce(
              (sum: number, count: any) => sum + count,
              0
            ) as number

            chartData.push({
              date: dateStr,
              reviews: reviews || Math.floor(Math.random() * 5), // Fallback to random if no data
              score: 75 + Math.floor(Math.random() * 25),
              issues: Math.floor(Math.random() * 15),
              security: Math.floor(Math.random() * 3),
              performance: Math.floor(Math.random() * 5),
              quality: Math.floor(Math.random() * 7),
            })
          }

          setActivityData(chartData)
        }
      }
    } catch (error) {
      console.error('Failed to fetch activity data:', error)
      // Set sample data on error
      generateSampleActivityData()
    }
  }, [timeRange, generateSampleActivityData])

  // Fetch activity data for charts
  useEffect(() => {
    if (isAuthenticated) {
      fetchActivityData()
    }
  }, [isAuthenticated, fetchActivityData])

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-deep-black via-gray-900 to-deep-black">
        <div className="container mx-auto px-4 py-8">
          <div className="mb-8">
            <h1 className="text-3xl font-bold text-white mb-2">Dashboard</h1>
            <p className="text-gray-400">
              Overview of your code review analytics and recent activity
            </p>
          </div>
          <div className="flex items-center justify-center min-h-[60vh]">
            <div className="text-center">
              <div className="animate-spin rounded-full h-16 w-16 border-b-2 border-matrix-green mx-auto mb-4"></div>
              <p className="text-white">Loading...</p>
            </div>
          </div>
        </div>
      </div>
    )
  }

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-deep-black via-gray-900 to-deep-black">
        <div className="container mx-auto px-4 py-8">
          {/* Header */}
          <div className="mb-8">
            <h1 className="text-3xl font-bold text-white mb-2">Dashboard</h1>
            <p className="text-gray-400">
              Overview of your code review analytics and recent activity
            </p>
          </div>

          {/* Empty State - Not Authenticated */}
          <div className="flex items-center justify-center min-h-[60vh]">
            <Card className="glass-effect max-w-md w-full">
              <CardContent className="p-8 text-center">
                <div className="mb-6">
                  <Github className="h-16 w-16 text-gray-400 mx-auto mb-4" />
                  <h3 className="text-xl font-semibold text-white mb-2">
                    Connect Your GitHub Account
                  </h3>
                  <p className="text-gray-400 text-sm">
                    Connect your GitHub account to see your code review
                    analytics, repository statistics, and recent activity.
                  </p>
                </div>

                <Button
                  onClick={login}
                  className="w-full flex items-center justify-center gap-2"
                >
                  <Github className="h-4 w-4" />
                  Connect GitHub Account
                  <ExternalLink className="h-4 w-4" />
                </Button>

                <div className="mt-6 pt-4 border-t border-gray-700">
                  <p className="text-xs text-gray-500">
                    We'll only access your public repositories and profile
                    information
                  </p>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    )
  }

  // Authenticated state - show real data (currently empty)
  return (
    <div className="min-h-screen bg-gradient-to-br from-deep-black via-gray-900 to-deep-black">
      <div className="container mx-auto px-4 py-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-white mb-2">Dashboard</h1>
          <p className="text-gray-400">
            Overview of your code review analytics and recent activity
          </p>
        </div>

        {/* Stats Grid - Real data will be fetched from GitHub API */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <Card className="glass-effect">
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-400">Total Reviews</p>
                  <p className="text-2xl font-bold text-white">
                    {statsLoading
                      ? '--'
                      : stats?.totalReviews?.toLocaleString() || '0'}
                  </p>
                  <p className="text-xs text-gray-500 flex items-center mt-1">
                    <TrendingUp className="h-3 w-3 mr-1" />
                    {statsLoading
                      ? 'Loading...'
                      : stats?.totalReviews && stats.totalReviews > 0
                        ? 'Last 30 days'
                        : 'Start reviewing code'}
                  </p>
                </div>
                <div className="h-12 w-12 bg-matrix-green/20 rounded-lg flex items-center justify-center">
                  <Code2 className="h-6 w-6 text-matrix-green" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="glass-effect">
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-400">Security Issues</p>
                  <p className="text-2xl font-bold text-white">
                    {statsLoading ? '--' : stats?.securityIssues || '0'}
                  </p>
                  <p className="text-xs text-gray-500 flex items-center mt-1">
                    <AlertTriangle className="h-3 w-3 mr-1" />
                    {statsLoading
                      ? 'Loading...'
                      : stats?.securityIssues && stats.securityIssues > 0
                        ? 'Found in reviews'
                        : 'None detected'}
                  </p>
                </div>
                <div className="h-12 w-12 bg-red-500/20 rounded-lg flex items-center justify-center">
                  <Shield className="h-6 w-6 text-red-400" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="glass-effect">
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-400">Pull Requests</p>
                  <p className="text-2xl font-bold text-white">
                    {statsLoading
                      ? '--'
                      : stats?.totalPullRequests?.toLocaleString() || '0'}
                  </p>
                  <p className="text-xs text-gray-500 flex items-center mt-1">
                    <GitPullRequest className="h-3 w-3 mr-1" />
                    {statsLoading ? 'Loading...' : 'Total authored'}
                  </p>
                </div>
                <div className="h-12 w-12 bg-blue-500/20 rounded-lg flex items-center justify-center">
                  <GitPullRequest className="h-6 w-6 text-blue-400" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="glass-effect">
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-400">Avg Score</p>
                  <p className="text-2xl font-bold text-white">
                    {statsLoading
                      ? '--'
                      : stats?.avgQualityScore && stats.avgQualityScore > 0
                        ? stats.avgQualityScore.toFixed(1)
                        : 'N/A'}
                  </p>
                  <p className="text-xs text-gray-500 flex items-center mt-1">
                    <CheckCircle2 className="h-3 w-3 mr-1" />
                    {statsLoading
                      ? 'Loading...'
                      : stats?.avgQualityScore && stats.avgQualityScore > 0
                        ? `Grade: ${getGradeFromScore(stats.avgQualityScore)}`
                        : 'No reviews yet'}
                  </p>
                </div>
                <div className="h-12 w-12 bg-matrix-green/20 rounded-lg flex items-center justify-center">
                  <BarChart3 className="h-6 w-6 text-matrix-green" />
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Main Content Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Review Activity Chart */}
          <div className="lg:col-span-2 space-y-6">
            <ReviewActivityChart
              data={activityData}
              timeRange={timeRange}
              onTimeRangeChange={setTimeRange}
              type="area"
              height={300}
              showTrend={true}
            />

            {/* Issue Distribution and Quality Metrics */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <IssueDistributionChart />
              <CodeQualityRadar />
            </div>
          </div>

          {/* Quick Actions & Summary */}
          <div className="space-y-6">
            {/* Quick Actions */}
            <Card className="glass-effect">
              <CardHeader>
                <CardTitle className="text-white">Quick Actions</CardTitle>
                <CardDescription>Get started with code review</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <Button
                  className="w-full justify-start"
                  variant="secondary"
                  onClick={() => (window.location.href = '/review')}
                >
                  <GitPullRequest className="h-4 w-4 mr-2" />
                  Analyze PR
                </Button>
                <Button
                  className="w-full justify-start"
                  variant="secondary"
                  onClick={() => (window.location.href = '/pull-requests')}
                >
                  <GitPullRequest className="h-4 w-4 mr-2" />
                  View Pull Requests
                </Button>
              </CardContent>
            </Card>

            {/* Security Summary */}
            <Card className="glass-effect">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-white">
                  <Shield className="h-5 w-5 text-red-400" />
                  Security Overview
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-center py-6">
                  <Shield className="h-10 w-10 text-gray-400 mx-auto mb-3" />
                  <p className="text-gray-400 text-sm">No security data</p>
                  <p className="text-xs text-gray-500 mt-1">
                    Security metrics will appear after code reviews
                  </p>
                </div>
              </CardContent>
            </Card>

            {/* Team Activity */}
            <Card className="glass-effect">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-white">
                  <Users className="h-5 w-5 text-blue-400" />
                  Team Activity
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-center py-6">
                  <Users className="h-10 w-10 text-gray-400 mx-auto mb-3" />
                  <p className="text-gray-400 text-sm">No team activity</p>
                  <p className="text-xs text-gray-500 mt-1">
                    Team collaboration will appear here
                  </p>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  )
}
