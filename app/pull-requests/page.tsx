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
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  GitPullRequest,
  Search,
  Filter,
  RefreshCw,
  ExternalLink,
  Clock,
  CheckCircle2,
  AlertCircle,
  GitMerge,
  Users,
  FileText,
  Plus,
  Minus,
  Eye,
  MessageSquare,
  GitBranch,
} from 'lucide-react'
import { formatTimeAgo, getStateIcon } from '@/lib/utils'

interface PullRequest {
  id: number
  number: number
  title: string
  description: string
  author: string
  state: 'open' | 'closed' | 'merged'
  draft: boolean
  repository: string
  branch: string
  baseBranch: string
  createdAt: string
  updatedAt: string
  labels: string[]
  reviewStatus: 'pending' | 'approved' | 'changes_requested'
  checksStatus: 'pending' | 'success' | 'failed'
  changedFiles: number
  additions: number
  deletions: number
  commits: number
  reviewers: string[]
  url: string
}

const mockPRs: PullRequest[] = [
  {
    id: 1,
    number: 42,
    title: 'Add user authentication system',
    description:
      'Implements JWT-based authentication with login, logout, and protected routes',
    author: 'john-doe',
    state: 'open',
    draft: false,
    repository: 'frontend-app',
    branch: 'feature/auth-system',
    baseBranch: 'main',
    createdAt: '2024-01-15T10:30:00Z',
    updatedAt: '2024-01-15T14:20:00Z',
    labels: ['enhancement', 'security'],
    reviewStatus: 'pending',
    checksStatus: 'success',
    changedFiles: 8,
    additions: 245,
    deletions: 12,
    commits: 6,
    reviewers: ['jane-smith', 'tech-lead'],
    url: 'https://github.com/example/frontend-app/pull/42',
  },
  {
    id: 2,
    number: 38,
    title: 'Fix memory leak in data processing',
    description:
      'Resolves memory leak issue causing performance degradation in large dataset processing',
    author: 'jane-smith',
    state: 'open',
    draft: false,
    repository: 'data-processor',
    branch: 'bugfix/memory-leak',
    baseBranch: 'main',
    createdAt: '2024-01-14T16:45:00Z',
    updatedAt: '2024-01-15T09:15:00Z',
    labels: ['bug', 'performance'],
    reviewStatus: 'approved',
    checksStatus: 'pending',
    changedFiles: 3,
    additions: 67,
    deletions: 45,
    commits: 4,
    reviewers: ['john-doe'],
    url: 'https://github.com/example/data-processor/pull/38',
  },
  {
    id: 3,
    number: 35,
    title: 'Implement dark mode toggle',
    description: 'Adds system-wide dark mode with user preference persistence',
    author: 'alex-dev',
    state: 'open',
    draft: true,
    repository: 'frontend-app',
    branch: 'feature/dark-mode',
    baseBranch: 'develop',
    createdAt: '2024-01-13T11:20:00Z',
    updatedAt: '2024-01-14T17:30:00Z',
    labels: ['enhancement', 'ui/ux'],
    reviewStatus: 'pending',
    checksStatus: 'failed',
    changedFiles: 12,
    additions: 189,
    deletions: 34,
    commits: 8,
    reviewers: [],
    url: 'https://github.com/example/frontend-app/pull/35',
  },
  {
    id: 4,
    number: 31,
    title: 'Update dependencies to latest versions',
    description:
      'Security update for vulnerable packages and general dependency maintenance',
    author: 'security-bot',
    state: 'merged',
    draft: false,
    repository: 'backend-api',
    branch: 'chore/update-deps',
    baseBranch: 'main',
    createdAt: '2024-01-12T08:00:00Z',
    updatedAt: '2024-01-12T08:00:00Z',
    labels: ['dependencies', 'security'],
    reviewStatus: 'approved',
    checksStatus: 'success',
    changedFiles: 2,
    additions: 0,
    deletions: 0,
    commits: 1,
    reviewers: ['john-doe', 'jane-smith'],
    url: 'https://github.com/example/backend-api/pull/31',
  },
]

export default function PullRequestsPage() {
  const [searchTerm, setSearchTerm] = useState('')
  const [stateFilter, setStateFilter] = useState('all')
  const [repoFilter, setRepoFilter] = useState('all')
  const [selectedPR, setSelectedPR] = useState<PullRequest | null>(null)

  const filteredPRs = mockPRs.filter(pr => {
    const matchesSearch =
      pr.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
      pr.description.toLowerCase().includes(searchTerm.toLowerCase()) ||
      pr.author.toLowerCase().includes(searchTerm.toLowerCase())

    const matchesState =
      stateFilter === 'all' ||
      (stateFilter === 'draft' && pr.draft) ||
      (stateFilter !== 'draft' && pr.state === stateFilter && !pr.draft)

    const matchesRepo = repoFilter === 'all' || pr.repository === repoFilter

    return matchesSearch && matchesState && matchesRepo
  })

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

  const getReviewStatusColor = (status: string) => {
    switch (status) {
      case 'approved':
        return 'text-green-500'
      case 'changes_requested':
        return 'text-red-500'
      default:
        return 'text-yellow-500'
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-deep-black via-gray-900 to-deep-black">
      <div className="container mx-auto px-4 py-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-white mb-2">Pull Requests</h1>
          <p className="text-gray-400">
            Manage and review pull requests across your repositories
          </p>
        </div>

        {/* Filters */}
        <Card className="glass-effect mb-6">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-white">
              <Filter className="h-5 w-5 text-matrix-green" />
              Filters
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                <Input
                  placeholder="Search pull requests..."
                  value={searchTerm}
                  onChange={e => setSearchTerm(e.target.value)}
                  className="pl-10"
                />
              </div>

              <Select value={stateFilter} onValueChange={setStateFilter}>
                <SelectTrigger>
                  <SelectValue placeholder="State" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All States</SelectItem>
                  <SelectItem value="open">Open</SelectItem>
                  <SelectItem value="closed">Closed</SelectItem>
                  <SelectItem value="merged">Merged</SelectItem>
                  <SelectItem value="draft">Draft</SelectItem>
                </SelectContent>
              </Select>

              <Select value={repoFilter} onValueChange={setRepoFilter}>
                <SelectTrigger>
                  <SelectValue placeholder="Repository" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Repositories</SelectItem>
                  <SelectItem value="frontend-app">frontend-app</SelectItem>
                  <SelectItem value="backend-api">backend-api</SelectItem>
                  <SelectItem value="data-processor">data-processor</SelectItem>
                </SelectContent>
              </Select>

              <Button variant="secondary" className="w-full">
                <RefreshCw className="h-4 w-4 mr-2" />
                Refresh
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* PR List */}
        <div className="space-y-4">
          {filteredPRs.map(pr => (
            <Card
              key={pr.id}
              className="glass-effect hover:border-matrix-green/30 transition-colors"
            >
              <CardContent className="p-6">
                <div className="flex items-start justify-between mb-4">
                  <div className="flex items-start gap-3 flex-1">
                    <GitPullRequest
                      className={`h-6 w-6 mt-1 ${
                        pr.state === 'merged'
                          ? 'text-purple-500'
                          : pr.state === 'closed'
                            ? 'text-red-500'
                            : pr.draft
                              ? 'text-gray-400'
                              : 'text-matrix-green'
                      }`}
                    />

                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        <h3 className="text-lg font-semibold text-white hover:text-matrix-green cursor-pointer">
                          {pr.title}
                        </h3>
                        <span className="text-gray-400">#{pr.number}</span>
                        {pr.draft && (
                          <Badge variant="outline" size="sm">
                            Draft
                          </Badge>
                        )}
                      </div>

                      <p className="text-gray-400 text-sm mb-3">
                        {pr.description}
                      </p>

                      <div className="flex items-center gap-4 text-sm text-gray-400">
                        <span className="flex items-center gap-1">
                          <Users className="h-4 w-4" />
                          {pr.author}
                        </span>
                        <span className="flex items-center gap-1">
                          <GitBranch className="h-4 w-4" />
                          {pr.branch} → {pr.baseBranch}
                        </span>
                        <span className="flex items-center gap-1">
                          <Clock className="h-4 w-4" />
                          {formatTimeAgo(pr.updatedAt)}
                        </span>
                        <span className="flex items-center gap-1">
                          <FileText className="h-4 w-4" />
                          {pr.changedFiles} files
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <Button variant="ghost" size="sm">
                      <Eye className="h-4 w-4" />
                    </Button>
                    <Button variant="ghost" size="sm">
                      <ExternalLink className="h-4 w-4" />
                    </Button>
                  </div>
                </div>

                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    {/* Labels */}
                    <div className="flex items-center gap-1">
                      {pr.labels.map(label => (
                        <Badge key={label} variant="outline" size="sm">
                          {label}
                        </Badge>
                      ))}
                    </div>

                    {/* Changes */}
                    <div className="flex items-center gap-2 text-sm">
                      <span className="flex items-center gap-1 text-green-500">
                        <Plus className="h-3 w-3" />
                        {pr.additions}
                      </span>
                      <span className="flex items-center gap-1 text-red-500">
                        <Minus className="h-3 w-3" />
                        {pr.deletions}
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center gap-4">
                    {/* Review Status */}
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-gray-400">Reviews:</span>
                      <span
                        className={`text-sm ${getReviewStatusColor(pr.reviewStatus)}`}
                      >
                        {pr.reviewStatus.replace('_', ' ')}
                      </span>
                    </div>

                    {/* Checks Status */}
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-gray-400">Checks:</span>
                      {getStatusIcon(pr.checksStatus)}
                    </div>

                    {/* Repository */}
                    <Badge variant="secondary" size="sm">
                      {pr.repository}
                    </Badge>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        {filteredPRs.length === 0 && (
          <Card className="glass-effect">
            <CardContent className="p-8 text-center">
              <GitPullRequest className="h-16 w-16 text-gray-400 mx-auto mb-4" />
              <h3 className="text-xl font-semibold text-white mb-2">
                No pull requests found
              </h3>
              <p className="text-gray-400">
                {searchTerm || stateFilter !== 'all' || repoFilter !== 'all'
                  ? 'Try adjusting your filters to see more results.'
                  : 'There are no pull requests to display.'}
              </p>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  )
}
