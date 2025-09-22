'use client'

import React, { useState, useEffect, useCallback } from 'react'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Calendar,
  Clock,
  Code2,
  Filter,
  Search,
  Download,
  Eye,
  TrendingUp,
  TrendingDown,
  Minus,
  GitPullRequest,
  FileText,
  Shield,
  Zap,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  ChevronLeft,
  ChevronRight,
  RefreshCw,
  ExternalLink,
  ArrowUpDown,
} from 'lucide-react'
import { useAuth } from '@/contexts/AuthContext'
import { format } from 'date-fns'
import { cn } from '@/lib/utils'

interface ReviewHistoryItem {
  id: string
  timestamp: string
  repository?: string
  pullRequest?: {
    number: number
    title: string
    url: string
  }
  type: 'paste' | 'upload' | 'pr'
  score: number
  letterGrade: string
  totalIssues: number
  criticalIssues: number
  securityIssues: number
  performanceIssues: number
  qualityIssues: number
  linesAnalyzed: number
  filesAnalyzed: number
  status: 'completed' | 'in_progress' | 'failed'
}

interface FilterOptions {
  search: string
  dateRange: 'today' | 'week' | 'month' | 'all'
  minScore: string
  maxScore: string
  type: 'all' | 'paste' | 'upload' | 'pr'
  status: 'all' | 'completed' | 'in_progress' | 'failed'
  sortBy: 'date' | 'score' | 'issues'
  sortOrder: 'asc' | 'desc'
}

const initialFilters: FilterOptions = {
  search: '',
  dateRange: 'all',
  minScore: '',
  maxScore: '',
  type: 'all',
  status: 'all',
  sortBy: 'date',
  sortOrder: 'desc',
}

export default function HistoryPage() {
  const { user, isAuthenticated, isLoading } = useAuth()
  const [reviews, setReviews] = useState<ReviewHistoryItem[]>([])
  const [filteredReviews, setFilteredReviews] = useState<ReviewHistoryItem[]>(
    []
  )
  const [filters, setFilters] = useState<FilterOptions>(initialFilters)
  const [isLoadingReviews, setIsLoadingReviews] = useState(false)
  const [currentPage, setCurrentPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [selectedReview, setSelectedReview] = useState<string | null>(null)
  const itemsPerPage = 10

  const fetchReviewHistory = useCallback(async () => {
    setIsLoadingReviews(true)
    try {
      const backendUrl =
        process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'
      const params = new URLSearchParams({
        user_id: user?.id || '',
        limit: '100',
        offset: '0',
      })

      const response = await fetch(`${backendUrl}/review/history?${params}`)
      if (response.ok) {
        const data = await response.json()
        const transformedReviews = transformReviews(data.reviews || [])
        setReviews(transformedReviews)
        setFilteredReviews(transformedReviews)
      }
    } catch (error) {
      console.error('Failed to fetch review history:', error)
    } finally {
      setIsLoadingReviews(false)
    }
  }, [user])

  // Fetch review history
  useEffect(() => {
    if (isAuthenticated && user) {
      fetchReviewHistory()
    }
  }, [isAuthenticated, user, fetchReviewHistory])

  const transformReviews = (backendReviews: any[]): ReviewHistoryItem[] => {
    return backendReviews.map(review => ({
      id: review.id,
      timestamp: review.created_at || review.completed_at,
      repository: review.repository,
      pullRequest: review.pull_request
        ? {
            number: review.pull_request.number,
            title: review.pull_request.title,
            url: review.pull_request.url,
          }
        : undefined,
      type: review.type === 'github_pr' ? 'pr' : review.type || 'paste',
      score: review.results?.overall_score || 0,
      letterGrade: review.results?.letter_grade || 'N/A',
      totalIssues: review.results?.total_issues || 0,
      criticalIssues: review.results?.critical_issues || 0,
      securityIssues: review.results?.security_issues?.length || 0,
      performanceIssues: review.results?.performance_issues?.length || 0,
      qualityIssues: review.results?.quality_issues?.length || 0,
      linesAnalyzed: review.results?.lines_analyzed || 0,
      filesAnalyzed: review.results?.files_analyzed || 1,
      status: review.status || 'completed',
    }))
  }

  // Apply filters
  useEffect(() => {
    let filtered = [...reviews]

    // Search filter
    if (filters.search) {
      const searchLower = filters.search.toLowerCase()
      filtered = filtered.filter(
        review =>
          review.repository?.toLowerCase().includes(searchLower) ||
          review.pullRequest?.title.toLowerCase().includes(searchLower) ||
          review.id.toLowerCase().includes(searchLower)
      )
    }

    // Date range filter
    const now = new Date()
    if (filters.dateRange !== 'all') {
      const cutoffDate = new Date()
      if (filters.dateRange === 'today') {
        cutoffDate.setHours(0, 0, 0, 0)
      } else if (filters.dateRange === 'week') {
        cutoffDate.setDate(now.getDate() - 7)
      } else if (filters.dateRange === 'month') {
        cutoffDate.setMonth(now.getMonth() - 1)
      }
      filtered = filtered.filter(
        review => new Date(review.timestamp) >= cutoffDate
      )
    }

    // Score filter
    if (filters.minScore) {
      filtered = filtered.filter(
        review => review.score >= parseFloat(filters.minScore)
      )
    }
    if (filters.maxScore) {
      filtered = filtered.filter(
        review => review.score <= parseFloat(filters.maxScore)
      )
    }

    // Type filter
    if (filters.type !== 'all') {
      filtered = filtered.filter(review => review.type === filters.type)
    }

    // Status filter
    if (filters.status !== 'all') {
      filtered = filtered.filter(review => review.status === filters.status)
    }

    // Sorting
    filtered.sort((a, b) => {
      let comparison = 0
      if (filters.sortBy === 'date') {
        comparison =
          new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
      } else if (filters.sortBy === 'score') {
        comparison = b.score - a.score
      } else if (filters.sortBy === 'issues') {
        comparison = b.totalIssues - a.totalIssues
      }
      return filters.sortOrder === 'asc' ? -comparison : comparison
    })

    setFilteredReviews(filtered)
    setTotalPages(Math.ceil(filtered.length / itemsPerPage))
    setCurrentPage(1)
  }, [filters, reviews])

  const handleFilterChange = (key: keyof FilterOptions, value: string) => {
    setFilters(prev => ({ ...prev, [key]: value }))
  }

  const resetFilters = () => {
    setFilters(initialFilters)
  }

  const exportReviews = () => {
    const csv = [
      [
        'ID',
        'Date',
        'Repository',
        'Type',
        'Score',
        'Grade',
        'Total Issues',
        'Security',
        'Performance',
        'Quality',
        'Lines',
        'Files',
        'Status',
      ],
      ...filteredReviews.map(r => [
        r.id,
        format(new Date(r.timestamp), 'yyyy-MM-dd HH:mm'),
        r.repository || 'N/A',
        r.type,
        r.score.toString(),
        r.letterGrade,
        r.totalIssues.toString(),
        r.securityIssues.toString(),
        r.performanceIssues.toString(),
        r.qualityIssues.toString(),
        r.linesAnalyzed.toString(),
        r.filesAnalyzed.toString(),
        r.status,
      ]),
    ]
      .map(row => row.join(','))
      .join('\n')

    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `review-history-${format(new Date(), 'yyyy-MM-dd')}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  const getScoreBadgeVariant = (score: number) => {
    if (score >= 90) return 'success'
    if (score >= 80) return 'warning'
    if (score >= 70) return 'secondary'
    return 'destructive'
  }

  const getGradeBadgeClass = (grade: string) => {
    const gradeClasses: Record<string, string> = {
      A: 'bg-green-500/20 text-green-400 border-green-500/50',
      B: 'bg-blue-500/20 text-blue-400 border-blue-500/50',
      C: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/50',
      D: 'bg-orange-500/20 text-orange-400 border-orange-500/50',
      F: 'bg-red-500/20 text-red-400 border-red-500/50',
    }
    return (
      gradeClasses[grade] || 'bg-gray-500/20 text-gray-400 border-gray-500/50'
    )
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle2 className="h-4 w-4 text-green-400" />
      case 'in_progress':
        return <RefreshCw className="h-4 w-4 text-yellow-400 animate-spin" />
      case 'failed':
        return <XCircle className="h-4 w-4 text-red-400" />
      default:
        return <Minus className="h-4 w-4 text-gray-400" />
    }
  }

  const paginatedReviews = filteredReviews.slice(
    (currentPage - 1) * itemsPerPage,
    currentPage * itemsPerPage
  )

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-deep-black via-gray-900 to-deep-black">
        <div className="container mx-auto px-4 py-8">
          <div className="flex items-center justify-center min-h-[60vh]">
            <div className="animate-spin rounded-full h-16 w-16 border-b-2 border-matrix-green"></div>
          </div>
        </div>
      </div>
    )
  }

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-deep-black via-gray-900 to-deep-black">
        <div className="container mx-auto px-4 py-8">
          <Card className="max-w-md mx-auto">
            <CardContent className="p-8 text-center">
              <h3 className="text-xl font-semibold text-white mb-2">
                Authentication Required
              </h3>
              <p className="text-gray-400">
                Please sign in to view your review history
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-deep-black via-gray-900 to-deep-black">
      <div className="container mx-auto px-4 py-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-white mb-2">Review History</h1>
          <p className="text-gray-400">
            Browse and analyze your past code reviews
          </p>
        </div>

        {/* Stats Overview */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <Card className="glass-effect">
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-400">Total Reviews</p>
                  <p className="text-2xl font-bold text-white">
                    {reviews.length}
                  </p>
                </div>
                <Code2 className="h-8 w-8 text-matrix-green" />
              </div>
            </CardContent>
          </Card>

          <Card className="glass-effect">
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-400">Avg Score</p>
                  <p className="text-2xl font-bold text-white">
                    {reviews.length > 0
                      ? (
                          reviews.reduce((acc, r) => acc + r.score, 0) /
                          reviews.length
                        ).toFixed(1)
                      : 'N/A'}
                  </p>
                </div>
                <TrendingUp className="h-8 w-8 text-blue-400" />
              </div>
            </CardContent>
          </Card>

          <Card className="glass-effect">
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-400">Total Issues</p>
                  <p className="text-2xl font-bold text-white">
                    {reviews.reduce((acc, r) => acc + r.totalIssues, 0)}
                  </p>
                </div>
                <AlertTriangle className="h-8 w-8 text-yellow-400" />
              </div>
            </CardContent>
          </Card>

          <Card className="glass-effect">
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-400">Lines Analyzed</p>
                  <p className="text-2xl font-bold text-white">
                    {reviews
                      .reduce((acc, r) => acc + r.linesAnalyzed, 0)
                      .toLocaleString()}
                  </p>
                </div>
                <FileText className="h-8 w-8 text-purple-400" />
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Filters */}
        <Card className="glass-effect mb-6">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-white">
              <Filter className="h-5 w-5" />
              Filters
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-4">
              <div>
                <label className="text-sm text-gray-400 mb-1 block">
                  Search
                </label>
                <div className="relative">
                  <Search className="absolute left-2 top-2.5 h-4 w-4 text-gray-400" />
                  <Input
                    placeholder="Search..."
                    value={filters.search}
                    onChange={e => handleFilterChange('search', e.target.value)}
                    className="pl-8"
                  />
                </div>
              </div>

              <div>
                <label className="text-sm text-gray-400 mb-1 block">
                  Date Range
                </label>
                <Select
                  value={filters.dateRange}
                  onValueChange={value =>
                    handleFilterChange('dateRange', value)
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="today">Today</SelectItem>
                    <SelectItem value="week">Last 7 Days</SelectItem>
                    <SelectItem value="month">Last 30 Days</SelectItem>
                    <SelectItem value="all">All Time</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <label className="text-sm text-gray-400 mb-1 block">Type</label>
                <Select
                  value={filters.type}
                  onValueChange={value => handleFilterChange('type', value)}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Types</SelectItem>
                    <SelectItem value="paste">Paste</SelectItem>
                    <SelectItem value="upload">Upload</SelectItem>
                    <SelectItem value="pr">Pull Request</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <label className="text-sm text-gray-400 mb-1 block">
                  Status
                </label>
                <Select
                  value={filters.status}
                  onValueChange={value => handleFilterChange('status', value)}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Status</SelectItem>
                    <SelectItem value="completed">Completed</SelectItem>
                    <SelectItem value="in_progress">In Progress</SelectItem>
                    <SelectItem value="failed">Failed</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <label className="text-sm text-gray-400 mb-1 block">
                  Sort By
                </label>
                <Select
                  value={filters.sortBy}
                  onValueChange={value => handleFilterChange('sortBy', value)}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="date">Date</SelectItem>
                    <SelectItem value="score">Score</SelectItem>
                    <SelectItem value="issues">Issues</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="flex items-end gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() =>
                    handleFilterChange(
                      'sortOrder',
                      filters.sortOrder === 'asc' ? 'desc' : 'asc'
                    )
                  }
                >
                  <ArrowUpDown className="h-4 w-4" />
                </Button>
                <Button variant="outline" size="sm" onClick={resetFilters}>
                  Reset
                </Button>
                <Button size="sm" onClick={exportReviews}>
                  <Download className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Reviews Table */}
        <Card className="glass-effect">
          <CardContent className="p-0">
            {isLoadingReviews ? (
              <div className="p-8 text-center">
                <RefreshCw className="h-8 w-8 text-matrix-green animate-spin mx-auto mb-4" />
                <p className="text-gray-400">Loading review history...</p>
              </div>
            ) : filteredReviews.length === 0 ? (
              <div className="p-8 text-center">
                <FileText className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                <p className="text-gray-400">No reviews found</p>
                <p className="text-sm text-gray-500 mt-2">
                  {filters.search ||
                  filters.dateRange !== 'all' ||
                  filters.type !== 'all'
                    ? 'Try adjusting your filters'
                    : 'Start reviewing code to see your history here'}
                </p>
              </div>
            ) : (
              <>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Date</TableHead>
                      <TableHead>Repository / File</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>Score</TableHead>
                      <TableHead>Issues</TableHead>
                      <TableHead>Lines</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {paginatedReviews.map(review => (
                      <TableRow
                        key={review.id}
                        className={cn(
                          'hover:bg-white/5 cursor-pointer transition-colors',
                          selectedReview === review.id && 'bg-white/10'
                        )}
                        onClick={() => setSelectedReview(review.id)}
                      >
                        <TableCell className="text-gray-400">
                          <div className="flex items-center gap-2">
                            <Clock className="h-3 w-3" />
                            {format(new Date(review.timestamp), 'MMM d, HH:mm')}
                          </div>
                        </TableCell>
                        <TableCell className="text-white">
                          <div className="flex flex-col gap-1">
                            <span className="font-medium">
                              {review.repository || 'Direct Review'}
                            </span>
                            {review.pullRequest && (
                              <span className="text-xs text-gray-400">
                                PR #{review.pullRequest.number}
                              </span>
                            )}
                          </div>
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline" className="text-xs">
                            {review.type === 'pr' && (
                              <GitPullRequest className="h-3 w-3 mr-1" />
                            )}
                            {review.type === 'upload' && (
                              <FileText className="h-3 w-3 mr-1" />
                            )}
                            {review.type === 'paste' && (
                              <Code2 className="h-3 w-3 mr-1" />
                            )}
                            {review.type.toUpperCase()}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <Badge
                              variant={
                                getScoreBadgeVariant(review.score) as any
                              }
                              className="min-w-[50px] justify-center"
                            >
                              {review.score.toFixed(1)}
                            </Badge>
                            <Badge
                              variant="outline"
                              className={cn(
                                'min-w-[30px] justify-center',
                                getGradeBadgeClass(review.letterGrade)
                              )}
                            >
                              {review.letterGrade}
                            </Badge>
                          </div>
                        </TableCell>
                        <TableCell>
                          <div className="flex flex-col gap-1 text-xs">
                            {review.criticalIssues > 0 && (
                              <span className="text-red-400">
                                {review.criticalIssues} critical
                              </span>
                            )}
                            {review.securityIssues > 0 && (
                              <span className="text-orange-400 flex items-center gap-1">
                                <Shield className="h-3 w-3" />
                                {review.securityIssues}
                              </span>
                            )}
                            {review.performanceIssues > 0 && (
                              <span className="text-yellow-400 flex items-center gap-1">
                                <Zap className="h-3 w-3" />
                                {review.performanceIssues}
                              </span>
                            )}
                            <span className="text-gray-400">
                              Total: {review.totalIssues}
                            </span>
                          </div>
                        </TableCell>
                        <TableCell className="text-gray-400">
                          {review.linesAnalyzed.toLocaleString()}
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            {getStatusIcon(review.status)}
                            <span className="text-xs text-gray-400">
                              {review.status}
                            </span>
                          </div>
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={e => {
                                e.stopPropagation()
                                window.open(`/review/${review.id}`, '_blank')
                              }}
                            >
                              <Eye className="h-4 w-4" />
                            </Button>
                            {review.pullRequest && (
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={e => {
                                  e.stopPropagation()
                                  window.open(review.pullRequest!.url, '_blank')
                                }}
                              >
                                <ExternalLink className="h-4 w-4" />
                              </Button>
                            )}
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>

                {/* Pagination */}
                {totalPages > 1 && (
                  <div className="flex items-center justify-between p-4 border-t border-gray-800">
                    <p className="text-sm text-gray-400">
                      Showing {(currentPage - 1) * itemsPerPage + 1} to{' '}
                      {Math.min(
                        currentPage * itemsPerPage,
                        filteredReviews.length
                      )}{' '}
                      of {filteredReviews.length} reviews
                    </p>
                    <div className="flex items-center gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                        disabled={currentPage === 1}
                      >
                        <ChevronLeft className="h-4 w-4" />
                      </Button>
                      <span className="text-sm text-gray-400">
                        Page {currentPage} of {totalPages}
                      </span>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() =>
                          setCurrentPage(p => Math.min(totalPages, p + 1))
                        }
                        disabled={currentPage === totalPages}
                      >
                        <ChevronRight className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                )}
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
