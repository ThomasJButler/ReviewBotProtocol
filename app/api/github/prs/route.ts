import { NextRequest, NextResponse } from 'next/server'

// Mock GitHub PR data
const mockPullRequests = [
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
    url: 'https://github.com/example/data-processor/pull/38',
  },
  {
    id: 3,
    number: 35,
    title: 'Implement dark mode toggle',
    description: 'Adds system-wide dark mode with user preference persistence',
    author: 'alex-dev',
    state: 'draft',
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
    url: 'https://github.com/example/frontend-app/pull/35',
  },
  {
    id: 4,
    number: 31,
    title: 'Update dependencies to latest versions',
    description:
      'Security update for vulnerable packages and general dependency maintenance',
    author: 'security-bot',
    state: 'open',
    draft: false,
    repository: 'backend-api',
    branch: 'chore/update-deps',
    baseBranch: 'main',
    createdAt: '2024-01-12T08:00:00Z',
    updatedAt: '2024-01-12T08:00:00Z',
    labels: ['dependencies', 'security'],
    reviewStatus: 'pending',
    checksStatus: 'success',
    changedFiles: 2,
    additions: 0,
    deletions: 0,
    commits: 1,
    url: 'https://github.com/example/backend-api/pull/31',
  },
  {
    id: 5,
    number: 28,
    title: 'Refactor API error handling',
    description:
      'Standardizes error responses and improves error handling across all endpoints',
    author: 'jane-smith',
    state: 'closed',
    draft: false,
    repository: 'backend-api',
    branch: 'refactor/error-handling',
    baseBranch: 'main',
    createdAt: '2024-01-10T14:15:00Z',
    updatedAt: '2024-01-11T16:45:00Z',
    labels: ['refactor', 'api'],
    reviewStatus: 'approved',
    checksStatus: 'success',
    changedFiles: 15,
    additions: 123,
    deletions: 89,
    commits: 7,
    url: 'https://github.com/example/backend-api/pull/28',
  },
]

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url)
    const repository = searchParams.get('repository')
    const state = searchParams.get('state') || 'all'
    const search = searchParams.get('search')
    const author = searchParams.get('author')

    // Simulate API delay
    await new Promise(resolve => setTimeout(resolve, 500))

    let filteredPRs = [...mockPullRequests]

    // Apply filters
    if (repository && repository !== 'all') {
      filteredPRs = filteredPRs.filter(pr => pr.repository === repository)
    }

    if (state !== 'all') {
      if (state === 'draft') {
        filteredPRs = filteredPRs.filter(pr => pr.draft)
      } else {
        filteredPRs = filteredPRs.filter(pr => pr.state === state && !pr.draft)
      }
    }

    if (search) {
      const searchLower = search.toLowerCase()
      filteredPRs = filteredPRs.filter(
        pr =>
          pr.title.toLowerCase().includes(searchLower) ||
          pr.description.toLowerCase().includes(searchLower) ||
          pr.branch.toLowerCase().includes(searchLower)
      )
    }

    if (author) {
      filteredPRs = filteredPRs.filter(pr => pr.author === author)
    }

    // Sort by updated date (newest first)
    filteredPRs.sort(
      (a, b) =>
        new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
    )

    return NextResponse.json({
      success: true,
      data: filteredPRs,
      metadata: {
        total: filteredPRs.length,
        filters: {
          repository,
          state,
          search,
          author,
        },
        repositories: ['frontend-app', 'backend-api', 'data-processor'],
        authors: ['john-doe', 'jane-smith', 'alex-dev', 'security-bot'],
      },
    })
  } catch (error) {
    console.error('GitHub PR API error:', error)
    return NextResponse.json(
      { error: 'Failed to fetch pull requests' },
      { status: 500 }
    )
  }
}

// Get specific PR details
export async function POST(request: NextRequest) {
  try {
    const { prNumber, repository } = await request.json()

    if (!prNumber) {
      return NextResponse.json(
        { error: 'PR number is required' },
        { status: 400 }
      )
    }

    // Find the PR
    const pr = mockPullRequests.find(p => p.number === prNumber)

    if (!pr) {
      return NextResponse.json(
        { error: 'Pull request not found' },
        { status: 404 }
      )
    }

    // Add detailed information for specific PR
    const detailedPR = {
      ...pr,
      files: [
        {
          filename: 'src/auth/AuthService.ts',
          additions: 89,
          deletions: 12,
          changes: 101,
          status: 'modified',
          patch:
            "@@ -1,5 +1,8 @@\n+import jwt from 'jsonwebtoken'\n import { User } from '../types'\n\n export class AuthService {\n+  private secretKey = process.env.JWT_SECRET\n+\n   async login(email: string, password: string) {",
        },
        {
          filename: 'src/components/LoginForm.tsx',
          additions: 67,
          deletions: 0,
          changes: 67,
          status: 'added',
          patch:
            "@@ -0,0 +1,67 @@\n+import React, { useState } from 'react'\n+import { Button } from '@/components/ui/button'\n+\n+export const LoginForm = () => {",
        },
      ],
      reviewComments: [
        {
          id: 1,
          author: 'security-reviewer',
          body: 'Consider adding rate limiting to prevent brute force attacks',
          path: 'src/auth/AuthService.ts',
          line: 23,
          createdAt: '2024-01-15T12:30:00Z',
        },
      ],
    }

    return NextResponse.json({
      success: true,
      data: detailedPR,
    })
  } catch (error) {
    console.error('GitHub PR detail API error:', error)
    return NextResponse.json(
      { error: 'Failed to fetch pull request details' },
      { status: 500 }
    )
  }
}
