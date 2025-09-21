import { NextRequest, NextResponse } from 'next/server'

export async function GET(request: NextRequest) {
  try {
    const clientId = process.env.GITHUB_CLIENT_ID
    const redirectUri = 'http://localhost:3000/api/auth/github/callback'

    if (!clientId) {
      return NextResponse.json(
        { error: 'GitHub OAuth not configured' },
        { status: 500 }
      )
    }

    // Generate a random state parameter for security
    const state = crypto.randomUUID()

    // Store state in a cookie for verification (in a real app, you might use a more secure method)
    const response = NextResponse.redirect(
      `https://github.com/login/oauth/authorize?client_id=${clientId}&scope=user:email,read:user&state=${state}&redirect_uri=${encodeURIComponent(redirectUri)}`
    )

    response.cookies.set('oauth_state', state, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      maxAge: 600, // 10 minutes
    })

    return response
  } catch (error) {
    console.error('GitHub OAuth initiation error:', error)
    return NextResponse.json(
      { error: 'Failed to initiate GitHub OAuth' },
      { status: 500 }
    )
  }
}
