import { NextRequest, NextResponse } from 'next/server'

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url)
    const code = searchParams.get('code')
    const state = searchParams.get('state')
    const error = searchParams.get('error')

    // Check for OAuth errors
    if (error) {
      console.error('GitHub OAuth error:', error)
      return NextResponse.redirect(
        'http://localhost:3000/dashboard?error=oauth_error'
      )
    }

    if (!code) {
      return NextResponse.redirect(
        'http://localhost:3000/dashboard?error=no_code'
      )
    }

    // Verify state parameter (CSRF protection)
    const storedState = request.cookies.get('oauth_state')?.value
    if (!storedState || state !== storedState) {
      return NextResponse.redirect(
        'http://localhost:3000/dashboard?error=invalid_state'
      )
    }

    // Exchange code for access token
    const tokenResponse = await fetch(
      'https://github.com/login/oauth/access_token',
      {
        method: 'POST',
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          client_id: process.env.GITHUB_CLIENT_ID,
          client_secret: process.env.GITHUB_CLIENT_SECRET,
          code,
        }),
      }
    )

    const tokenData = await tokenResponse.json()

    if (tokenData.error) {
      console.error('GitHub token exchange error:', tokenData.error)
      return NextResponse.redirect(
        'http://localhost:3000/dashboard?error=token_exchange'
      )
    }

    const accessToken = tokenData.access_token

    // Get user information from GitHub
    const userResponse = await fetch('https://api.github.com/user', {
      headers: {
        Authorization: `Bearer ${accessToken}`,
        Accept: 'application/vnd.github.v3+json',
      },
    })

    if (!userResponse.ok) {
      console.error('Failed to fetch GitHub user info')
      return NextResponse.redirect(
        'http://localhost:3000/dashboard?error=user_fetch'
      )
    }

    const userData = await userResponse.json()

    // Get user email (might be private)
    const emailResponse = await fetch('https://api.github.com/user/emails', {
      headers: {
        Authorization: `Bearer ${accessToken}`,
        Accept: 'application/vnd.github.v3+json',
      },
    })

    let primaryEmail = userData.email
    if (emailResponse.ok) {
      const emails = await emailResponse.json()
      const primaryEmailObj = emails.find((email: any) => email.primary)
      if (primaryEmailObj) {
        primaryEmail = primaryEmailObj.email
      }
    }

    // Create user session/JWT token
    const userInfo = {
      id: userData.id.toString(),
      login: userData.login,
      name: userData.name || userData.login,
      email: primaryEmail,
      avatar_url: userData.avatar_url,
      github_access_token: accessToken, // Store for GitHub API calls
    }

    // Create a simple JWT token (in production, use a proper JWT library)
    const token = Buffer.from(JSON.stringify(userInfo)).toString('base64')

    // Set authentication cookie
    const response = NextResponse.redirect('http://localhost:3000/dashboard')

    response.cookies.set('auth_token', token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      maxAge: 86400 * 7, // 7 days
      path: '/',
    })

    // Clear the state cookie
    response.cookies.set('oauth_state', '', {
      httpOnly: true,
      maxAge: 0,
    })

    return response
  } catch (error) {
    console.error('GitHub OAuth callback error:', error)
    return NextResponse.redirect(
      'http://localhost:3000/dashboard?error=callback_error'
    )
  }
}
