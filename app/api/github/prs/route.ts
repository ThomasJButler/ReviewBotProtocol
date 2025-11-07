import { NextRequest, NextResponse } from 'next/server'
import { cookies } from 'next/headers'

export async function GET(request: NextRequest) {
  try {
    // Extract GitHub access token from auth cookie
    const cookieStore = cookies()
    const authToken = cookieStore.get('auth_token')?.value

    if (!authToken) {
      return NextResponse.json(
        {
          success: false,
          data: [],
          metadata: {
            total: 0,
            error:
              'Authentication required. Please connect your GitHub account.',
          },
        },
        { status: 401 }
      )
    }

    // Decode the auth token to get GitHub access token
    let githubAccessToken: string
    try {
      const decoded = JSON.parse(Buffer.from(authToken, 'base64').toString())
      githubAccessToken = decoded.github_access_token

      if (!githubAccessToken) {
        throw new Error('GitHub access token not found in session')
      }
    } catch (error) {
      console.error('Failed to decode auth token:', error)
      return NextResponse.json(
        {
          success: false,
          data: [],
          metadata: {
            total: 0,
            error: 'Invalid authentication session. Please sign in again.',
          },
        },
        { status: 401 }
      )
    }

    const { searchParams } = new URL(request.url)
    const repository = searchParams.get('repository')
    const state = searchParams.get('state') || 'open'
    const search = searchParams.get('search')
    const page = parseInt(searchParams.get('page') || '1')
    const per_page = parseInt(searchParams.get('per_page') || '30')

    // Call GitHub API directly
    let githubApiUrl: string
    let githubParams: URLSearchParams

    if (!repository || repository === 'all') {
      // Search across all user's PRs
      const query = `is:pr author:@me state:${state === 'all' ? 'open' : state}${search ? ` ${search}` : ''}`
      githubApiUrl = 'https://api.github.com/search/issues'
      githubParams = new URLSearchParams({
        q: query,
        sort: 'updated',
        order: 'desc',
        per_page: per_page.toString(),
        page: page.toString(),
      })
    } else {
      // Get PRs for specific repository
      githubApiUrl = `https://api.github.com/repos/${repository}/pulls`
      githubParams = new URLSearchParams({
        state: state === 'all' ? 'all' : state,
        sort: 'updated',
        direction: 'desc',
        per_page: per_page.toString(),
        page: page.toString(),
      })
    }

    const response = await fetch(`${githubApiUrl}?${githubParams}`, {
      headers: {
        Authorization: `Bearer ${githubAccessToken}`,
        Accept: 'application/vnd.github.v3+json',
        'User-Agent': 'Git-Review-Assistant',
      },
    })

    if (!response.ok) {
      console.error(`GitHub API responded with ${response.status}`)
      const errorData = await response.json().catch(() => ({}))
      return NextResponse.json(
        {
          success: false,
          data: [],
          metadata: {
            total: 0,
            error: `GitHub API error: ${errorData.message || response.statusText}`,
          },
        },
        { status: response.status }
      )
    }

    const githubData = await response.json()

    // Transform GitHub API response to our format
    let pullRequests: any[]

    if (!repository || repository === 'all') {
      // Search API returns items array
      pullRequests = (githubData.items || []).map((item: any) => ({
        id: item.id.toString(),
        number: item.number,
        title: item.title,
        description: item.body || 'No description provided',
        state: item.state,
        draft: item.draft || false,
        author: item.user.login,
        authorAvatar: item.user.avatar_url,
        repository: item.repository_url.split('/').slice(-2).join('/'),
        branch: item.head?.ref || 'unknown',
        baseBranch: item.base?.ref || 'main',
        url: item.html_url,
        createdAt: item.created_at,
        updatedAt: item.updated_at,
        changedFiles: 0, // Not available in search API
        additions: 0,
        deletions: 0,
        comments: item.comments || 0,
        labels: item.labels?.map((l: any) => l.name) || [],
        reviewStatus: 'pending' as const,
        checksStatus: 'pending' as const,
        commits: 0,
      }))
    } else {
      // Repository pulls API returns array directly
      pullRequests = (githubData || []).map((pr: any) => ({
        id: pr.id.toString(),
        number: pr.number,
        title: pr.title,
        description: pr.body || 'No description provided',
        state: pr.state,
        draft: pr.draft || false,
        author: pr.user.login,
        authorAvatar: pr.user.avatar_url,
        repository: repository,
        branch: pr.head.ref,
        baseBranch: pr.base.ref,
        url: pr.html_url,
        createdAt: pr.created_at,
        updatedAt: pr.updated_at,
        changedFiles: pr.changed_files || 0,
        additions: pr.additions || 0,
        deletions: pr.deletions || 0,
        comments: pr.comments || 0,
        labels: pr.labels?.map((l: any) => l.name) || [],
        reviewStatus: 'pending' as const,
        checksStatus: 'pending' as const,
        commits: pr.commits || 0,
      }))
    }

    // Filter by search term if provided
    if (search && repository && repository !== 'all') {
      const searchLower = search.toLowerCase()
      pullRequests = pullRequests.filter(
        (pr: any) =>
          pr.title.toLowerCase().includes(searchLower) ||
          pr.description.toLowerCase().includes(searchLower) ||
          pr.branch.toLowerCase().includes(searchLower)
      )
    }

    return NextResponse.json({
      success: true,
      data: pullRequests,
      metadata: {
        total: pullRequests.length,
        filters: {
          repository,
          state,
          search,
        },
      },
    })
  } catch (error) {
    console.error('GitHub PR API error:', error)

    return NextResponse.json(
      {
        success: false,
        data: [],
        metadata: {
          total: 0,
          error:
            error instanceof Error
              ? error.message
              : 'Failed to fetch pull requests',
        },
      },
      { status: 500 }
    )
  }
}

// Get specific PR details
export async function POST(request: NextRequest) {
  try {
    // Extract GitHub access token from auth cookie
    const cookieStore = cookies()
    const authToken = cookieStore.get('auth_token')?.value

    if (!authToken) {
      return NextResponse.json(
        { error: 'Authentication required' },
        { status: 401 }
      )
    }

    let githubAccessToken: string
    try {
      const decoded = JSON.parse(Buffer.from(authToken, 'base64').toString())
      githubAccessToken = decoded.github_access_token

      if (!githubAccessToken) {
        throw new Error('GitHub access token not found')
      }
    } catch (error) {
      return NextResponse.json(
        { error: 'Invalid authentication session' },
        { status: 401 }
      )
    }

    const { prNumber, repository } = await request.json()

    if (!prNumber || !repository) {
      return NextResponse.json(
        { error: 'PR number and repository are required' },
        { status: 400 }
      )
    }

    // Call GitHub API for detailed PR info
    const githubApiUrl = `https://api.github.com/repos/${repository}/pulls/${prNumber}`

    const response = await fetch(githubApiUrl, {
      headers: {
        Authorization: `Bearer ${githubAccessToken}`,
        Accept: 'application/vnd.github.v3+json',
        'User-Agent': 'Git-Review-Assistant',
      },
    })

    if (!response.ok) {
      if (response.status === 404) {
        return NextResponse.json(
          { error: 'Pull request not found' },
          { status: 404 }
        )
      }
      const errorData = await response.json().catch(() => ({}))
      return NextResponse.json(
        { error: errorData.message || 'Failed to fetch PR details' },
        { status: response.status }
      )
    }

    const pr = await response.json()

    // Transform to our format
    const prData = {
      id: pr.id.toString(),
      number: pr.number,
      title: pr.title,
      description: pr.body || 'No description provided',
      state: pr.state,
      draft: pr.draft || false,
      author: pr.user.login,
      authorAvatar: pr.user.avatar_url,
      repository: repository,
      branch: pr.head.ref,
      baseBranch: pr.base.ref,
      url: pr.html_url,
      createdAt: pr.created_at,
      updatedAt: pr.updated_at,
      mergedAt: pr.merged_at,
      changedFiles: pr.changed_files || 0,
      additions: pr.additions || 0,
      deletions: pr.deletions || 0,
      comments: pr.comments || 0,
      commits: pr.commits || 0,
      mergeable: pr.mergeable,
      merged: pr.merged,
    }

    return NextResponse.json({
      success: true,
      data: prData,
    })
  } catch (error) {
    console.error('GitHub PR detail API error:', error)
    return NextResponse.json(
      {
        error:
          error instanceof Error
            ? error.message
            : 'Failed to fetch pull request details',
      },
      { status: 500 }
    )
  }
}
