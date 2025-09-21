import { NextRequest, NextResponse } from 'next/server'

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000'

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url)
    const repository = searchParams.get('repository')
    const state = searchParams.get('state') || 'open'
    const search = searchParams.get('search')
    const page = searchParams.get('page') || '1'
    const per_page = searchParams.get('per_page') || '30'

    // If searching across all repositories
    if (!repository || repository === 'all') {
      const backendUrl = `${BACKEND_URL}/github/pulls/search`
      const backendParams = new URLSearchParams({
        query: search || '',
        state: state === 'all' ? 'open' : state,
        per_page: per_page,
      })

      const response = await fetch(`${backendUrl}?${backendParams}`, {
        headers: {
          'Content-Type': 'application/json',
        },
        // TODO: Add authentication headers when available
      })

      if (!response.ok) {
        throw new Error(`Backend responded with ${response.status}`)
      }

      const backendData = await response.json()

      return NextResponse.json({
        success: true,
        data: backendData.data || [],
        metadata: {
          total: backendData.data?.length || 0,
          filters: {
            repository,
            state,
            search,
          },
          ...backendData.metadata,
        },
      })
    } else {
      // Searching specific repository
      const backendUrl = `${BACKEND_URL}/github/repositories/${repository}/pulls`
      const backendParams = new URLSearchParams({
        state: state === 'all' ? 'open' : state,
        page: page,
        per_page: per_page,
      })

      const response = await fetch(`${backendUrl}?${backendParams}`, {
        headers: {
          'Content-Type': 'application/json',
        },
        // TODO: Add authentication headers when available
      })

      if (!response.ok) {
        throw new Error(`Backend responded with ${response.status}`)
      }

      const backendData = await response.json()

      // Filter by search term if provided
      let filteredData = backendData.data || []
      if (search) {
        const searchLower = search.toLowerCase()
        filteredData = filteredData.filter(
          (pr: any) =>
            pr.title.toLowerCase().includes(searchLower) ||
            pr.description.toLowerCase().includes(searchLower) ||
            pr.branch.toLowerCase().includes(searchLower)
        )
      }

      return NextResponse.json({
        success: true,
        data: filteredData,
        metadata: {
          total: filteredData.length,
          filters: {
            repository,
            state,
            search,
          },
          ...backendData.metadata,
        },
      })
    }
  } catch (error) {
    console.error('GitHub PR API error:', error)

    // Return fallback empty response
    return NextResponse.json({
      success: false,
      data: [],
      metadata: {
        total: 0,
        error: 'Failed to fetch pull requests from backend',
      },
    })
  }
}

// Get specific PR details
export async function POST(request: NextRequest) {
  try {
    const { prNumber, repository } = await request.json()

    if (!prNumber || !repository) {
      return NextResponse.json(
        { error: 'PR number and repository are required' },
        { status: 400 }
      )
    }

    // Call backend for detailed PR info
    const backendUrl = `${BACKEND_URL}/github/pulls/${repository}/${prNumber}`

    const response = await fetch(backendUrl, {
      headers: {
        'Content-Type': 'application/json',
      },
      // TODO: Add authentication headers when available
    })

    if (!response.ok) {
      if (response.status === 404) {
        return NextResponse.json(
          { error: 'Pull request not found' },
          { status: 404 }
        )
      }
      throw new Error(`Backend responded with ${response.status}`)
    }

    const backendData = await response.json()

    return NextResponse.json({
      success: true,
      data: backendData.data,
    })
  } catch (error) {
    console.error('GitHub PR detail API error:', error)
    return NextResponse.json(
      { error: 'Failed to fetch pull request details' },
      { status: 500 }
    )
  }
}
