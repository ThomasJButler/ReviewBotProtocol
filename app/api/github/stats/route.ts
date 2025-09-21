import { NextRequest, NextResponse } from 'next/server'

// Helper functions to fetch review metrics from backend
async function fetchReviewCount(userId: string): Promise<number> {
  try {
    const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000'
    const response = await fetch(
      `${backendUrl}/review/stats/user?user_id=${userId}&days=30`
    )

    if (response.ok) {
      const data = await response.json()
      return data.total_reviews || 0
    }
    return 0
  } catch (error) {
    console.error('Failed to fetch review count:', error)
    return 0
  }
}

async function fetchSecurityIssueCount(userId: string): Promise<number> {
  try {
    const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000'
    const response = await fetch(
      `${backendUrl}/review/stats/user?user_id=${userId}&days=30`
    )

    if (response.ok) {
      const data = await response.json()
      const issues = data.top_issues || []
      const securityIssue = issues.find((i: any) => i.category === 'security')
      return securityIssue?.count || 0
    }
    return 0
  } catch (error) {
    console.error('Failed to fetch security issues:', error)
    return 0
  }
}

async function fetchAverageQualityScore(userId: string): Promise<number> {
  try {
    const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000'
    const response = await fetch(
      `${backendUrl}/review/stats/user?user_id=${userId}&days=30`
    )

    if (response.ok) {
      const data = await response.json()
      return data.average_score || 0
    }
    return 0
  } catch (error) {
    console.error('Failed to fetch average quality score:', error)
    return 0
  }
}

// Also fetch repository-specific review metrics
async function fetchRepositoryReviewMetrics(repositories: any[]): Promise<any> {
  try {
    const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000'

    // Get metrics for top repositories
    const topRepos = repositories.slice(0, 5).map(r => r.full_name)
    const metricsPromises = topRepos.map(async (repoName: string) => {
      try {
        const response = await fetch(
          `${backendUrl}/review/stats/overview?repository=${repoName}&days=30`
        )
        if (response.ok) {
          const data = await response.json()
          return {
            repository: repoName,
            totalReviews: data.total_reviews || 0,
            avgScore: data.avg_score || 0,
          }
        }
      } catch {
        return null
      }
    })

    const metrics = await Promise.all(metricsPromises)
    return metrics.filter(m => m !== null)
  } catch (error) {
    console.error('Failed to fetch repository metrics:', error)
    return []
  }
}

export async function GET(request: NextRequest) {
  try {
    const authToken = request.cookies.get('auth_token')?.value

    if (!authToken) {
      return NextResponse.json({ error: 'Not authenticated' }, { status: 401 })
    }

    // Decode the auth token to get GitHub access token
    const userInfo = JSON.parse(Buffer.from(authToken, 'base64').toString())
    const githubToken = userInfo.github_access_token

    if (!githubToken) {
      return NextResponse.json(
        { error: 'GitHub token not found' },
        { status: 401 }
      )
    }

    // Fetch user's repositories
    const reposResponse = await fetch(
      'https://api.github.com/user/repos?per_page=100&sort=updated',
      {
        headers: {
          Authorization: `Bearer ${githubToken}`,
          Accept: 'application/vnd.github.v3+json',
        },
      }
    )

    if (!reposResponse.ok) {
      throw new Error('Failed to fetch repositories')
    }

    const repos = await reposResponse.json()

    // Fetch user's pull requests (from all repos)
    const user = userInfo.login
    const pullsQuery = `author:${user} is:pr`

    const pullsResponse = await fetch(
      `https://api.github.com/search/issues?q=${encodeURIComponent(pullsQuery)}&sort=updated&per_page=100`,
      {
        headers: {
          Authorization: `Bearer ${githubToken}`,
          Accept: 'application/vnd.github.v3+json',
        },
      }
    )

    let totalPulls = 0
    let openPulls = 0
    let mergedPulls = 0

    if (pullsResponse.ok) {
      const pullsData = await pullsResponse.json()
      totalPulls = pullsData.total_count

      // Count open vs closed/merged PRs
      openPulls = pullsData.items.filter(
        (pr: any) => pr.state === 'open'
      ).length
      mergedPulls = pullsData.items.filter(
        (pr: any) => pr.state === 'closed'
      ).length
    }

    // Get real commit activity for more accurate review estimation
    const commitActivity = await Promise.all(
      repos.slice(0, 10).map(async (repo: any) => {
        try {
          const commitsResponse = await fetch(
            `https://api.github.com/repos/${repo.full_name}/commits?since=${new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString()}&per_page=100`,
            {
              headers: {
                Authorization: `Bearer ${githubToken}`,
                Accept: 'application/vnd.github.v3+json',
              },
            }
          )
          if (commitsResponse.ok) {
            const commits = await commitsResponse.json()
            return commits.length
          }
          return 0
        } catch {
          return 0
        }
      })
    )

    const totalCommitsLast30Days = commitActivity.reduce(
      (sum, count) => sum + count,
      0
    )

    // Calculate real stats based on actual GitHub data
    // Fetch repository-specific review metrics
    const repositoryMetrics = await fetchRepositoryReviewMetrics(repos)

    const stats = {
      totalRepositories: repos.length,
      publicRepositories: repos.filter((repo: any) => !repo.private).length,
      privateRepositories: repos.filter((repo: any) => repo.private).length,
      totalStars: repos.reduce(
        (sum: number, repo: any) => sum + repo.stargazers_count,
        0
      ),
      totalForks: repos.reduce(
        (sum: number, repo: any) => sum + repo.forks_count,
        0
      ),
      totalPullRequests: totalPulls,
      openPullRequests: openPulls,
      mergedPullRequests: mergedPulls,
      totalIssues: repos.reduce(
        (sum: number, repo: any) => sum + repo.open_issues_count,
        0
      ),
      totalCommitsLast30Days,

      // Fetch real review metrics from backend
      totalReviews: await fetchReviewCount(userInfo.login),
      securityIssues: await fetchSecurityIssueCount(userInfo.login),
      avgQualityScore: await fetchAverageQualityScore(userInfo.login),

      // Recent activity (last 7 days) based on actual repo updates
      recentActivity: repos.filter((repo: any) => {
        const lastUpdate = new Date(repo.updated_at)
        const sevenDaysAgo = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000)
        return lastUpdate > sevenDaysAgo
      }).length,

      // Additional real metrics
      avgStarsPerRepo:
        repos.length > 0
          ? Math.round(
              repos.reduce(
                (sum: number, repo: any) => sum + repo.stargazers_count,
                0
              ) / repos.length
            )
          : 0,
      totalLanguages: [
        ...new Set(
          repos
            .filter((repo: any) => repo.language)
            .map((repo: any) => repo.language)
        ),
      ].length,
      hasActiveRepos: repos.some((repo: any) => {
        const lastUpdate = new Date(repo.updated_at)
        const thirtyDaysAgo = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000)
        return lastUpdate > thirtyDaysAgo
      }),

      // Repository-specific review metrics
      repositoryMetrics: repositoryMetrics,

      // Top reviewed repositories
      topReviewedRepos: repositoryMetrics
        .sort((a: any, b: any) => b.totalReviews - a.totalReviews)
        .slice(0, 3),
    }

    return NextResponse.json(stats)
  } catch (error) {
    console.error('GitHub stats error:', error)
    return NextResponse.json(
      { error: 'Failed to fetch GitHub stats' },
      { status: 500 }
    )
  }
}
