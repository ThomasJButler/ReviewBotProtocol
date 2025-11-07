import { NextResponse } from 'next/server'

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000'

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url)
    const days = searchParams.get('days') || '30'

    // Forward request to backend
    const response = await fetch(
      `${BACKEND_URL}/review/stats/overview?days=${days}`,
      {
        headers: {
          'Content-Type': 'application/json',
        },
      }
    )

    if (!response.ok) {
      console.error('Backend stats request failed:', response.statusText)

      // Return mock data as fallback
      return NextResponse.json({
        success: true,
        data: {
          totalReviews: 0,
          averageScore: 0,
          criticalIssues: 0,
          highIssues: 0,
          mediumIssues: 0,
          lowIssues: 0,
          topRepositories: [],
          recentActivity: [],
        },
      })
    }

    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error('Error fetching GitHub stats:', error)

    // Return mock data on error
    return NextResponse.json({
      success: true,
      data: {
        totalReviews: 0,
        averageScore: 0,
        criticalIssues: 0,
        highIssues: 0,
        mediumIssues: 0,
        lowIssues: 0,
        topRepositories: [],
        recentActivity: [],
      },
    })
  }
}
