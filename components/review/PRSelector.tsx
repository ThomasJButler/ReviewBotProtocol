'use client'

import React, { useState, useEffect } from 'react'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { formatTimeAgo, getStateIcon } from '@/lib/utils'
import { useGitHubService, type PullRequest } from '@/hooks/useGitHubService'
import {
  GitPullRequest,
  Search,
  ExternalLink,
  GitBranch,
  Calendar,
  User,
  MessageSquare,
  CheckCircle2,
  Clock,
  AlertCircle,
  Github,
  Loader2,
  RefreshCw,
  Filter,
} from 'lucide-react'
import { cn } from '@/lib/utils'

interface PRSelectorProps {
  onPRSelected: (pr: PullRequest) => void
  selectedPR?: PullRequest | null
  repositories?: string[]
  className?: string
  maxResults?: number
  autoRefresh?: boolean
  showFilters?: boolean
}

export default function PRSelector({
  onPRSelected,
  selectedPR,
  className,
  maxResults = 20,
  autoRefresh = false,
  showFilters = true,
}: PRSelectorProps) {
  const [searchTerm, setSearchTerm] = useState('')
  const [repoFilter, setRepoFilter] = useState<string>('all')
  const [stateFilter, setStateFilter] = useState<string>('open')
  const [authorFilter, setAuthorFilter] = useState<string>('all')

  const {
    pullRequests,
    isLoading,
    error,
    repositories,
    authors,
    fetchPullRequests,
  } = useGitHubService()

  // Fetch PRs on component mount and when filters change
  useEffect(() => {
    const filters = {
      repository: repoFilter !== 'all' ? repoFilter : undefined,
      state: stateFilter !== 'all' ? stateFilter : undefined,
      search: searchTerm || undefined,
      author: authorFilter !== 'all' ? authorFilter : undefined,
    }
    fetchPullRequests(filters)
  }, [fetchPullRequests, repoFilter, stateFilter, searchTerm, authorFilter])

  // Auto-refresh functionality
  useEffect(() => {
    if (!autoRefresh) return

    const interval = setInterval(() => {
      const filters = {
        repository: repoFilter !== 'all' ? repoFilter : undefined,
        state: stateFilter !== 'all' ? stateFilter : undefined,
        search: searchTerm || undefined,
        author: authorFilter !== 'all' ? authorFilter : undefined,
      }
      fetchPullRequests(filters)
    }, 30000) // Refresh every 30 seconds

    return () => clearInterval(interval)
  }, [
    autoRefresh,
    fetchPullRequests,
    repoFilter,
    stateFilter,
    searchTerm,
    authorFilter,
  ])

  const handleRefresh = () => {
    const filters = {
      repository: repoFilter !== 'all' ? repoFilter : undefined,
      state: stateFilter !== 'all' ? stateFilter : undefined,
      search: searchTerm || undefined,
      author: authorFilter !== 'all' ? authorFilter : undefined,
    }
    fetchPullRequests(filters)
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'success':
        return <CheckCircle2 className="h-4 w-4 text-green-500" />
      case 'pending':
        return <Clock className="h-4 w-4 text-yellow-500" />
      case 'failed':
        return <AlertCircle className="h-4 w-4 text-red-500" />
      default:
        return <Clock className="h-4 w-4 text-gray-400" />
    }
  }

  const filteredPRs = pullRequests.slice(0, maxResults)

  if (error) {
    return (
      <Card className={cn('glass-effect', className)}>
        <CardContent className="p-6">
          <div className="text-center">
            <AlertCircle className="h-12 w-12 text-red-500 mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-white mb-2">
              Error Loading Pull Requests
            </h3>
            <p className="text-gray-400 mb-4">{error}</p>
            <Button onClick={handleRefresh} variant="secondary">
              <RefreshCw className="h-4 w-4 mr-2" />
              Try Again
            </Button>
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className={cn('glass-effect', className)}>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2 text-white">
              <GitPullRequest className="h-5 w-5 text-matrix-green" />
              Select Pull Request
            </CardTitle>
            <CardDescription>Choose a pull request to analyze</CardDescription>
          </div>
          <Button
            onClick={handleRefresh}
            variant="ghost"
            size="sm"
            disabled={isLoading}
          >
            <RefreshCw className={cn('h-4 w-4', isLoading && 'animate-spin')} />
          </Button>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {showFilters && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
              <Input
                placeholder="Search PRs..."
                value={searchTerm}
                onChange={e => setSearchTerm(e.target.value)}
                className="pl-10"
              />
            </div>

            <Select value={repoFilter} onValueChange={setRepoFilter}>
              <SelectTrigger>
                <SelectValue placeholder="Repository" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Repositories</SelectItem>
                {repositories.map(repo => (
                  <SelectItem key={repo} value={repo}>
                    {repo}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select value={stateFilter} onValueChange={setStateFilter}>
              <SelectTrigger>
                <SelectValue placeholder="State" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All States</SelectItem>
                <SelectItem value="open">Open</SelectItem>
                <SelectItem value="closed">Closed</SelectItem>
                <SelectItem value="draft">Draft</SelectItem>
              </SelectContent>
            </Select>

            <Select value={authorFilter} onValueChange={setAuthorFilter}>
              <SelectTrigger>
                <SelectValue placeholder="Author" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Authors</SelectItem>
                {authors.map(author => (
                  <SelectItem key={author} value={author}>
                    {author}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}

        <div className="space-y-3">
          {isLoading ? (
            Array.from({ length: 3 }).map((_, index) => (
              <div key={index} className="space-y-2">
                <Skeleton className="h-4 w-3/4" />
                <Skeleton className="h-3 w-1/2" />
              </div>
            ))
          ) : filteredPRs.length === 0 ? (
            <div className="text-center py-8">
              <GitPullRequest className="h-16 w-16 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-semibold text-white mb-2">
                No Pull Requests Found
              </h3>
              <p className="text-gray-400">
                {searchTerm ||
                repoFilter !== 'all' ||
                stateFilter !== 'all' ||
                authorFilter !== 'all'
                  ? 'Try adjusting your filters to see more results.'
                  : 'No pull requests available.'}
              </p>
            </div>
          ) : (
            filteredPRs.map(pr => (
              <div
                key={pr.id}
                className={cn(
                  'border border-gray-700 rounded-lg p-4 cursor-pointer transition-all duration-200 hover:border-matrix-green/50',
                  selectedPR?.id === pr.id &&
                    'border-matrix-green bg-matrix-green/5'
                )}
                onClick={() => onPRSelected(pr)}
              >
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <GitPullRequest
                      className={cn(
                        'h-4 w-4',
                        pr.state === 'open' && !pr.draft
                          ? 'text-matrix-green'
                          : pr.state === 'closed'
                            ? 'text-red-500'
                            : pr.draft
                              ? 'text-gray-400'
                              : 'text-matrix-green'
                      )}
                    />
                    <h4 className="font-medium text-white text-sm line-clamp-1">
                      {pr.title}
                    </h4>
                    <span className="text-xs text-gray-400">#{pr.number}</span>
                  </div>
                  <ExternalLink
                    className="h-4 w-4 text-gray-400 hover:text-white flex-shrink-0"
                    onClick={e => {
                      e.stopPropagation()
                      window.open(pr.url, '_blank')
                    }}
                  />
                </div>

                <p className="text-xs text-gray-400 mb-3 line-clamp-2">
                  {pr.description}
                </p>

                <div className="flex items-center justify-between text-xs text-gray-400">
                  <div className="flex items-center gap-3">
                    <span className="flex items-center gap-1">
                      <User className="h-3 w-3" />
                      {pr.author}
                    </span>
                    <span className="flex items-center gap-1">
                      <GitBranch className="h-3 w-3" />
                      {pr.branch}
                    </span>
                    <span className="flex items-center gap-1">
                      <Calendar className="h-3 w-3" />
                      {formatTimeAgo(pr.updatedAt)}
                    </span>
                  </div>

                  <div className="flex items-center gap-2">
                    {pr.labels.slice(0, 2).map((label, index) => (
                      <Badge key={index} variant="outline" className="text-xs">
                        {label}
                      </Badge>
                    ))}
                    {getStatusIcon(pr.checksStatus)}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </CardContent>
    </Card>
  )
}
