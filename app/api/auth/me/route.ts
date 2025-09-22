import { NextRequest, NextResponse } from 'next/server'

export async function GET(request: NextRequest) {
  try {
    const authToken = request.cookies.get('auth_token')?.value

    if (!authToken) {
      return NextResponse.json({ error: 'Not authenticated' }, { status: 401 })
    }

    try {
      // Decode the simple base64 token (in production, use proper JWT verification)
      const userInfo = JSON.parse(Buffer.from(authToken, 'base64').toString())

      // Remove sensitive information before sending to client
      const { github_access_token, ...safeUserInfo } = userInfo

      return NextResponse.json(safeUserInfo)
    } catch (decodeError) {
      console.error('Token decode error:', decodeError)
      return NextResponse.json({ error: 'Invalid token' }, { status: 401 })
    }
  } catch (error) {
    console.error('Auth me error:', error)
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}
