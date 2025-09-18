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
} from 'lucide-react'

export default function ReportsPage() {
  const [timeRange, setTimeRange] = useState('30d')
  const [reportType, setReportType] = useState('overview')

  const stats = {
    totalReviews: 1247,
    averageScore: 8.4,
    securityIssues: 23,
    criticalIssues: 5,
    resolvedIssues: 89,
    activeReviewers: 12,
  }

  const timeRangeOptions = [
    { value: '7d', label: 'Last 7 days' },
    { value: '30d', label: 'Last 30 days' },
    { value: '90d', label: 'Last 3 months' },
    { value: '1y', label: 'Last year' },
  ]

  const trends = [
    {
      metric: 'Code Quality Score',
      current: 8.4,
      previous: 7.9,
      change: +6.3,
      trend: 'up',
    },
    {
      metric: 'Security Issues',
      current: 23,
      previous: 31,
      change: -25.8,
      trend: 'down',
    },
    {
      metric: 'Review Speed',
      current: '2.3h',
      previous: '3.1h',
      change: -25.8,
      trend: 'down',
    },
    {
      metric: 'PR Success Rate',
      current: 94.2,
      previous: 91.8,
      change: +2.6,
      trend: 'up',
    },
  ]

  const repositories = [
    {
      name: 'frontend-app',
      reviews: 456,
      score: 8.7,
      issues: 8,
      status: 'healthy',
    },
    {
      name: 'backend-api',
      reviews: 389,
      score: 8.1,
      issues: 12,
      status: 'warning',
    },
    {
      name: 'data-processor',
      reviews: 234,
      score: 7.9,
      issues: 3,
      status: 'healthy',
    },
    {
      name: 'mobile-app',
      reviews: 168,
      score: 8.9,
      issues: 0,
      status: 'excellent',
    },
  ]

  const topIssues = [
    { type: 'SQL Injection', count: 12, severity: 'critical', trend: -2 },
    { type: 'XSS Vulnerability', count: 8, severity: 'high', trend: +1 },
    { type: 'Memory Leak', count: 15, severity: 'medium', trend: -5 },
    { type: 'Unused Variables', count: 43, severity: 'low', trend: +8 },
  ]

  const reviewers = [
    { name: 'John Doe', reviews: 89, avgScore: 8.9, speciality: 'Security' },
    {
      name: 'Jane Smith',
      reviews: 76,
      avgScore: 8.7,
      speciality: 'Performance',
    },
    {
      name: 'Alex Chen',
      reviews: 65,
      avgScore: 9.1,
      speciality: 'Architecture',
    },
    {
      name: 'Sarah Wilson',
      reviews: 54,
      avgScore: 8.4,
      speciality: 'Frontend',
    },
  ]

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
                      <p className="text-2xl font-bold text-white">
                        {stats.totalReviews.toLocaleString()}
                      </p>
                      <p className="text-xs text-matrix-green flex items-center mt-1">
                        <TrendingUp className="h-3 w-3 mr-1" />
                        +12% vs last period
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
                      <p className="text-2xl font-bold text-white">
                        {stats.averageScore}/10
                      </p>
                      <p className="text-xs text-matrix-green flex items-center mt-1">
                        <Award className="h-3 w-3 mr-1" />
                        Excellent
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
                      <p className="text-2xl font-bold text-white">
                        {stats.securityIssues}
                      </p>
                      <p className="text-xs text-red-400 flex items-center mt-1">
                        <AlertTriangle className="h-3 w-3 mr-1" />
                        {stats.criticalIssues} critical
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
                      <p className="text-2xl font-bold text-white">
                        {stats.activeReviewers}
                      </p>
                      <p className="text-xs text-blue-400 flex items-center mt-1">
                        <Users className="h-3 w-3 mr-1" />
                        +2 this month
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
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                  {trends.map((trend, index) => (
                    <div
                      key={index}
                      className="p-4 rounded-lg border border-border"
                    >
                      <p className="text-sm text-gray-400 mb-1">
                        {trend.metric}
                      </p>
                      <p className="text-xl font-bold text-white mb-2">
                        {trend.current}
                      </p>
                      <div
                        className={`flex items-center text-sm ${
                          trend.trend === 'up'
                            ? 'text-matrix-green'
                            : 'text-red-400'
                        }`}
                      >
                        <TrendingUp
                          className={`h-3 w-3 mr-1 ${
                            trend.trend === 'down' ? 'rotate-180' : ''
                          }`}
                        />
                        {Math.abs(trend.change)}%
                      </div>
                    </div>
                  ))}
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
                <div className="space-y-4">
                  {repositories.map((repo, index) => (
                    <div
                      key={index}
                      className="flex items-center justify-between p-4 rounded-lg border border-border"
                    >
                      <div className="flex items-center gap-4">
                        <div
                          className={`h-3 w-3 rounded-full ${
                            repo.status === 'excellent'
                              ? 'bg-matrix-green'
                              : repo.status === 'healthy'
                                ? 'bg-blue-500'
                                : repo.status === 'warning'
                                  ? 'bg-yellow-500'
                                  : 'bg-red-500'
                          }`}
                        />
                        <div>
                          <p className="font-medium text-white">{repo.name}</p>
                          <p className="text-sm text-gray-400">
                            {repo.reviews} reviews
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-6">
                        <div className="text-right">
                          <p className="text-sm text-gray-400">Quality Score</p>
                          <p className="font-medium text-white">
                            {repo.score}/10
                          </p>
                        </div>
                        <div className="text-right">
                          <p className="text-sm text-gray-400">Issues</p>
                          <p
                            className={`font-medium ${repo.issues === 0 ? 'text-matrix-green' : 'text-yellow-400'}`}
                          >
                            {repo.issues}
                          </p>
                        </div>
                        <Badge
                          variant={
                            repo.status === 'excellent'
                              ? 'default'
                              : repo.status === 'healthy'
                                ? 'secondary'
                                : repo.status === 'warning'
                                  ? 'destructive'
                                  : 'outline'
                          }
                        >
                          {repo.status}
                        </Badge>
                      </div>
                    </div>
                  ))}
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
                  <div className="space-y-4">
                    {topIssues.map((issue, index) => (
                      <div
                        key={index}
                        className="flex items-center justify-between p-3 rounded-lg border border-border"
                      >
                        <div>
                          <p className="font-medium text-white">{issue.type}</p>
                          <p className="text-sm text-gray-400">
                            {issue.count} occurrences
                          </p>
                        </div>
                        <div className="flex items-center gap-3">
                          <Badge
                            variant={
                              issue.severity === 'critical'
                                ? 'destructive'
                                : issue.severity === 'high'
                                  ? 'secondary'
                                  : 'outline'
                            }
                          >
                            {issue.severity}
                          </Badge>
                          <span
                            className={`text-sm ${issue.trend > 0 ? 'text-red-400' : 'text-matrix-green'}`}
                          >
                            {issue.trend > 0 ? '+' : ''}
                            {issue.trend}
                          </span>
                        </div>
                      </div>
                    ))}
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
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <span className="text-white">Critical</span>
                      <div className="flex items-center gap-2">
                        <div className="w-32 h-2 bg-gray-700 rounded-full overflow-hidden">
                          <div className="h-full w-1/5 bg-red-600 rounded-full"></div>
                        </div>
                        <span className="text-red-400">5</span>
                      </div>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-white">High</span>
                      <div className="flex items-center gap-2">
                        <div className="w-32 h-2 bg-gray-700 rounded-full overflow-hidden">
                          <div className="h-full w-2/5 bg-red-500 rounded-full"></div>
                        </div>
                        <span className="text-red-500">12</span>
                      </div>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-white">Medium</span>
                      <div className="flex items-center gap-2">
                        <div className="w-32 h-2 bg-gray-700 rounded-full overflow-hidden">
                          <div className="h-full w-1/4 bg-yellow-500 rounded-full"></div>
                        </div>
                        <span className="text-yellow-500">6</span>
                      </div>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-white">Low</span>
                      <div className="flex items-center gap-2">
                        <div className="w-32 h-2 bg-gray-700 rounded-full overflow-hidden">
                          <div className="h-full w-full bg-blue-500 rounded-full"></div>
                        </div>
                        <span className="text-blue-500">43</span>
                      </div>
                    </div>
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
                  <div className="space-y-4">
                    <div className="p-4 rounded-lg border border-border">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-white">Average Review Time</span>
                        <span className="text-matrix-green font-bold">
                          2.3 hours
                        </span>
                      </div>
                      <div className="w-full h-2 bg-gray-700 rounded-full overflow-hidden">
                        <div className="h-full w-3/4 bg-matrix-green rounded-full"></div>
                      </div>
                    </div>
                    <div className="p-4 rounded-lg border border-border">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-white">First Response Time</span>
                        <span className="text-blue-400 font-bold">
                          45 minutes
                        </span>
                      </div>
                      <div className="w-full h-2 bg-gray-700 rounded-full overflow-hidden">
                        <div className="h-full w-4/5 bg-blue-500 rounded-full"></div>
                      </div>
                    </div>
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
                  <div className="space-y-4">
                    <div className="text-center">
                      <p className="text-3xl font-bold text-matrix-green">
                        8.4
                      </p>
                      <p className="text-gray-400">Current Quality Score</p>
                    </div>
                    <div className="grid grid-cols-3 gap-4 text-center">
                      <div>
                        <p className="text-lg font-bold text-white">7.9</p>
                        <p className="text-xs text-gray-400">Last Month</p>
                      </div>
                      <div>
                        <p className="text-lg font-bold text-white">7.6</p>
                        <p className="text-xs text-gray-400">3 Months Ago</p>
                      </div>
                      <div>
                        <p className="text-lg font-bold text-white">7.2</p>
                        <p className="text-xs text-gray-400">6 Months Ago</p>
                      </div>
                    </div>
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
                <div className="space-y-4">
                  {reviewers.map((reviewer, index) => (
                    <div
                      key={index}
                      className="flex items-center justify-between p-4 rounded-lg border border-border"
                    >
                      <div className="flex items-center gap-3">
                        <div className="h-10 w-10 rounded-full bg-matrix-green/20 flex items-center justify-center font-medium text-matrix-green">
                          {reviewer.name
                            .split(' ')
                            .map(n => n[0])
                            .join('')}
                        </div>
                        <div>
                          <p className="font-medium text-white">
                            {reviewer.name}
                          </p>
                          <p className="text-sm text-gray-400">
                            {reviewer.speciality} Specialist
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-6">
                        <div className="text-right">
                          <p className="text-sm text-gray-400">Reviews</p>
                          <p className="font-medium text-white">
                            {reviewer.reviews}
                          </p>
                        </div>
                        <div className="text-right">
                          <p className="text-sm text-gray-400">Avg Score</p>
                          <p className="font-medium text-matrix-green">
                            {reviewer.avgScore}/10
                          </p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  )
}
