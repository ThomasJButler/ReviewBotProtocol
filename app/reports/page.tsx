'use client'

import React, { useState } from 'react'
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  BarChart3,
  TrendingUp,
  Shield,
  Zap,
  CheckCircle2,
  AlertTriangle,
  Download,
  Calendar,
  Filter,
  Users,
  GitPullRequest,
  Clock,
  Target,
  Award,
  FileText,
  PieChart,
  Activity,
  Github,
  ExternalLink,
} from 'lucide-react'
import { useAuth } from '@/contexts/AuthContext'

export default function ReportsPage() {
  const [timeRange, setTimeRange] = useState('30d')
  const [reportType, setReportType] = useState('overview')
  const { isAuthenticated, isLoading, login } = useAuth()

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-deep-black via-gray-900 to-deep-black">
        <div className="container mx-auto px-4 py-8">
          <div className="mb-8">
            <h1 className="text-3xl font-bold text-white mb-2">
              Analytics & Reports
            </h1>
            <p className="text-gray-400">
              Insights into your code review performance and security metrics
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

  const timeRangeOptions = [
    { value: '7d', label: 'Last 7 days' },
    { value: '30d', label: 'Last 30 days' },
    { value: '90d', label: 'Last 3 months' },
    { value: '1y', label: 'Last year' },
  ]

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-deep-black via-gray-900 to-deep-black">
        <div className="container mx-auto px-4 py-8">
          {/* Header */}
          <div className="mb-8">
            <h1 className="text-3xl font-bold text-white mb-2">
              Analytics & Reports
            </h1>
            <p className="text-gray-400">
              Insights into your code review performance and security metrics
            </p>
          </div>

          {/* Empty State - Not Authenticated */}
          <div className="flex items-center justify-center min-h-[60vh]">
            <Card className="glass-effect max-w-md w-full">
              <CardContent className="p-8 text-center">
                <div className="mb-6">
                  <BarChart3 className="h-16 w-16 text-gray-400 mx-auto mb-4" />
                  <h3 className="text-xl font-semibold text-white mb-2">
                    Connect Your GitHub Account
                  </h3>
                  <p className="text-gray-400 text-sm">
                    Connect your GitHub account to see your code review
                    analytics, repository statistics, and performance metrics.
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

  return (
    <div className="min-h-screen bg-gradient-to-br from-deep-black via-gray-900 to-deep-black">
      <div className="container mx-auto px-4 py-8">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-white mb-2">
                Analytics & Reports
              </h1>
              <p className="text-gray-400">
                Insights into your code review performance and security metrics
              </p>
            </div>
            <div className="flex items-center gap-3">
              <Select value={timeRange} onValueChange={setTimeRange}>
                <SelectTrigger className="w-40">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {timeRangeOptions.map(option => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button variant="secondary">
                <Download className="h-4 w-4 mr-2" />
                Export
              </Button>
            </div>
          </div>
        </div>

        <Tabs
          value={reportType}
          onValueChange={setReportType}
          className="space-y-6"
        >
          <TabsList className="grid w-full grid-cols-4">
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="security">Security</TabsTrigger>
            <TabsTrigger value="performance">Performance</TabsTrigger>
            <TabsTrigger value="team">Team</TabsTrigger>
          </TabsList>

          {/* Overview Tab */}
          <TabsContent value="overview" className="space-y-6">
            {/* Key Metrics */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
              <Card className="glass-effect">
                <CardContent className="p-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm text-gray-400">Total Reviews</p>
                      <p className="text-2xl font-bold text-white">--</p>
                      <p className="text-xs text-gray-500 flex items-center mt-1">
                        <TrendingUp className="h-3 w-3 mr-1" />
                        Loading...
                      </p>
                    </div>
                    <BarChart3 className="h-8 w-8 text-matrix-green" />
                  </div>
                </CardContent>
              </Card>

              <Card className="glass-effect">
                <CardContent className="p-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm text-gray-400">Avg Quality Score</p>
                      <p className="text-2xl font-bold text-white">--</p>
                      <p className="text-xs text-gray-500 flex items-center mt-1">
                        <Award className="h-3 w-3 mr-1" />
                        Loading...
                      </p>
                    </div>
                    <Target className="h-8 w-8 text-matrix-green" />
                  </div>
                </CardContent>
              </Card>

              <Card className="glass-effect">
                <CardContent className="p-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm text-gray-400">Security Issues</p>
                      <p className="text-2xl font-bold text-white">--</p>
                      <p className="text-xs text-gray-500 flex items-center mt-1">
                        <AlertTriangle className="h-3 w-3 mr-1" />
                        Loading...
                      </p>
                    </div>
                    <Shield className="h-8 w-8 text-red-400" />
                  </div>
                </CardContent>
              </Card>

              <Card className="glass-effect">
                <CardContent className="p-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm text-gray-400">Active Reviewers</p>
                      <p className="text-2xl font-bold text-white">--</p>
                      <p className="text-xs text-gray-500 flex items-center mt-1">
                        <Users className="h-3 w-3 mr-1" />
                        Loading...
                      </p>
                    </div>
                    <Users className="h-8 w-8 text-blue-400" />
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Trends */}
            <Card className="glass-effect">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-white">
                  <TrendingUp className="h-5 w-5 text-matrix-green" />
                  Performance Trends
                </CardTitle>
                <CardDescription>
                  Key metrics compared to previous period
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="text-center py-8">
                  <TrendingUp className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                  <p className="text-gray-400">No trend data available</p>
                  <p className="text-sm text-gray-500 mt-1">
                    Performance trends will appear after connecting GitHub
                  </p>
                </div>
              </CardContent>
            </Card>

            {/* Repository Performance */}
            <Card className="glass-effect">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-white">
                  <GitPullRequest className="h-5 w-5 text-matrix-green" />
                  Repository Performance
                </CardTitle>
                <CardDescription>
                  Review statistics by repository
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="text-center py-8">
                  <GitPullRequest className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                  <p className="text-gray-400">No repository data available</p>
                  <p className="text-sm text-gray-500 mt-1">
                    Repository performance will appear after connecting GitHub
                  </p>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Security Tab */}
          <TabsContent value="security" className="space-y-6">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <Card className="glass-effect">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-white">
                    <Shield className="h-5 w-5 text-red-400" />
                    Top Security Issues
                  </CardTitle>
                  <CardDescription>
                    Most frequent security vulnerabilities
                  </CardDescription>
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

              <Card className="glass-effect">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-white">
                    <PieChart className="h-5 w-5 text-matrix-green" />
                    Issue Distribution
                  </CardTitle>
                  <CardDescription>
                    Security issues by severity level
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="text-center py-6">
                    <PieChart className="h-10 w-10 text-gray-400 mx-auto mb-3" />
                    <p className="text-gray-400 text-sm">
                      No issue distribution data
                    </p>
                    <p className="text-xs text-gray-500 mt-1">
                      Issue distribution will appear after security scans
                    </p>
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          {/* Performance Tab */}
          <TabsContent value="performance" className="space-y-6">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <Card className="glass-effect">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-white">
                    <Zap className="h-5 w-5 text-yellow-400" />
                    Review Speed Metrics
                  </CardTitle>
                  <CardDescription>
                    How quickly reviews are completed
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="text-center py-6">
                    <Clock className="h-10 w-10 text-gray-400 mx-auto mb-3" />
                    <p className="text-gray-400 text-sm">No performance data</p>
                    <p className="text-xs text-gray-500 mt-1">
                      Performance metrics will appear after reviews
                    </p>
                  </div>
                </CardContent>
              </Card>

              <Card className="glass-effect">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-white">
                    <Activity className="h-5 w-5 text-matrix-green" />
                    Code Quality Trends
                  </CardTitle>
                  <CardDescription>
                    Quality score improvement over time
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="text-center py-6">
                    <Activity className="h-10 w-10 text-gray-400 mx-auto mb-3" />
                    <p className="text-gray-400 text-sm">No quality trends</p>
                    <p className="text-xs text-gray-500 mt-1">
                      Quality trends will appear after reviews
                    </p>
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          {/* Team Tab */}
          <TabsContent value="team" className="space-y-6">
            <Card className="glass-effect">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-white">
                  <Users className="h-5 w-5 text-blue-400" />
                  Top Reviewers
                </CardTitle>
                <CardDescription>
                  Most active and effective code reviewers
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="text-center py-8">
                  <Users className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                  <p className="text-gray-400">No team activity</p>
                  <p className="text-sm text-gray-500 mt-1">
                    Team collaboration will appear here
                  </p>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  )
}
