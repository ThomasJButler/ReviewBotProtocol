'use client'

import React from 'react'
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
} from 'lucide-react'

export default function DashboardPage() {
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

        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <Card className="glass-effect">
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-400">Total Reviews</p>
                  <p className="text-2xl font-bold text-white">1,247</p>
                  <p className="text-xs text-matrix-green flex items-center mt-1">
                    <TrendingUp className="h-3 w-3 mr-1" />
                    +12% from last month
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
                  <p className="text-2xl font-bold text-white">23</p>
                  <p className="text-xs text-red-400 flex items-center mt-1">
                    <AlertTriangle className="h-3 w-3 mr-1" />5 critical
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
                  <p className="text-2xl font-bold text-white">156</p>
                  <p className="text-xs text-blue-400 flex items-center mt-1">
                    <GitPullRequest className="h-3 w-3 mr-1" />
                    18 pending
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
                  <p className="text-2xl font-bold text-white">8.4/10</p>
                  <p className="text-xs text-matrix-green flex items-center mt-1">
                    <CheckCircle2 className="h-3 w-3 mr-1" />
                    Excellent
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
          {/* Recent Activity */}
          <div className="lg:col-span-2">
            <Card className="glass-effect">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-white">
                  <Activity className="h-5 w-5 text-matrix-green" />
                  Recent Activity
                </CardTitle>
                <CardDescription>
                  Latest code reviews and security findings
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {[
                    {
                      id: 1,
                      type: 'review',
                      title: 'Authentication middleware review completed',
                      description: 'Found 2 security issues in JWT validation',
                      time: '2 minutes ago',
                      severity: 'high',
                      icon: Shield,
                      color: 'text-red-400',
                    },
                    {
                      id: 2,
                      type: 'pr',
                      title: 'Pull request #123 analyzed',
                      description: 'Memory leak fix - 8.7/10 quality score',
                      time: '15 minutes ago',
                      severity: 'medium',
                      icon: GitPullRequest,
                      color: 'text-blue-400',
                    },
                    {
                      id: 3,
                      type: 'review',
                      title: 'Performance optimization review',
                      description: 'Algorithm complexity improved to O(log n)',
                      time: '1 hour ago',
                      severity: 'low',
                      icon: Zap,
                      color: 'text-yellow-400',
                    },
                    {
                      id: 4,
                      type: 'review',
                      title: 'API endpoint security scan',
                      description: 'No vulnerabilities detected - Clean',
                      time: '3 hours ago',
                      severity: 'info',
                      icon: CheckCircle2,
                      color: 'text-matrix-green',
                    },
                  ].map(activity => {
                    const IconComponent = activity.icon
                    return (
                      <div
                        key={activity.id}
                        className="flex items-start gap-3 p-3 rounded-lg hover:bg-white/5 transition-colors"
                      >
                        <div
                          className={`h-8 w-8 rounded-full bg-${activity.color.split('-')[1]}-500/20 flex items-center justify-center flex-shrink-0`}
                        >
                          <IconComponent
                            className={`h-4 w-4 ${activity.color}`}
                          />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-white font-medium">
                            {activity.title}
                          </p>
                          <p className="text-gray-400 text-sm">
                            {activity.description}
                          </p>
                          <div className="flex items-center gap-2 mt-1">
                            <span className="text-xs text-gray-500">
                              {activity.time}
                            </span>
                            <Badge
                              variant={
                                activity.severity === 'high'
                                  ? 'destructive'
                                  : activity.severity === 'medium'
                                    ? 'secondary'
                                    : 'outline'
                              }
                              size="sm"
                            >
                              {activity.severity}
                            </Badge>
                          </div>
                        </div>
                        <ChevronRight className="h-4 w-4 text-gray-500" />
                      </div>
                    )
                  })}
                </div>
                <div className="mt-4 pt-4 border-t border-border">
                  <Button
                    variant="ghost"
                    className="w-full text-matrix-green hover:text-matrix-green"
                  >
                    View All Activity
                    <ChevronRight className="h-4 w-4 ml-1" />
                  </Button>
                </div>
              </CardContent>
            </Card>
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
                <Button className="w-full justify-start" variant="secondary">
                  <Code2 className="h-4 w-4 mr-2" />
                  Review Code
                </Button>
                <Button className="w-full justify-start" variant="secondary">
                  <GitPullRequest className="h-4 w-4 mr-2" />
                  Analyze PR
                </Button>
                <Button className="w-full justify-start" variant="secondary">
                  <FileText className="h-4 w-4 mr-2" />
                  Upload Files
                </Button>
                <Button className="w-full justify-start" variant="secondary">
                  <BarChart3 className="h-4 w-4 mr-2" />
                  View Reports
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
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-400">Critical</span>
                    <Badge variant="destructive">5</Badge>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-400">High</span>
                    <Badge variant="secondary">12</Badge>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-400">Medium</span>
                    <Badge variant="outline">6</Badge>
                  </div>
                  <div className="pt-3 border-t border-border">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="w-full text-red-400 hover:text-red-300"
                    >
                      <AlertTriangle className="h-4 w-4 mr-2" />
                      View All Issues
                    </Button>
                  </div>
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
                <div className="space-y-3">
                  {[
                    {
                      name: 'John Doe',
                      action: 'completed review',
                      time: '5m ago',
                      avatar: 'JD',
                    },
                    {
                      name: 'Jane Smith',
                      action: 'merged PR #124',
                      time: '12m ago',
                      avatar: 'JS',
                    },
                    {
                      name: 'Alex Chen',
                      action: 'fixed security issue',
                      time: '1h ago',
                      avatar: 'AC',
                    },
                  ].map((member, index) => (
                    <div key={index} className="flex items-center gap-3">
                      <div className="h-8 w-8 rounded-full bg-matrix-green/20 flex items-center justify-center text-xs font-medium text-matrix-green">
                        {member.avatar}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm text-white">{member.name}</p>
                        <p className="text-xs text-gray-400">{member.action}</p>
                      </div>
                      <span className="text-xs text-gray-500">
                        {member.time}
                      </span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  )
}
