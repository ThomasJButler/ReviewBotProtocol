import { NextRequest, NextResponse } from 'next/server'

/**
 * GitHub Webhook Proxy Route
 *
 * This route receives GitHub webhook events and forwards them to the FastAPI backend.
 * This is necessary because GitHub webhooks need a publicly accessible URL,
 * which ngrok can provide for the Next.js frontend.
 */
export async function POST(request: NextRequest) {
  try {
    // Get the backend URL from environment variables
    const backendUrl =
      process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'

    // Forward all headers from the original request
    const headers: Record<string, string> = {}
    request.headers.forEach((value, key) => {
      headers[key] = value
    })

    // Get the raw body to preserve webhook signature verification
    const body = await request.text()

    // Forward the webhook to the FastAPI backend
    const response = await fetch(`${backendUrl}/webhook/github`, {
      method: 'POST',
      headers: {
        ...headers,
        'Content-Type': 'application/json',
      },
      body: body,
    })

    // Forward the response from the backend
    const responseData = await response.text()

    return new NextResponse(responseData, {
      status: response.status,
      headers: {
        'Content-Type': 'application/json',
      },
    })
  } catch (error) {
    console.error('Webhook proxy error:', error)

    return NextResponse.json(
      {
        error: 'Webhook processing failed',
        message: error instanceof Error ? error.message : 'Unknown error',
      },
      { status: 500 }
    )
  }
}

// Also handle GET requests for webhook verification
export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url)
  const challenge = searchParams.get('hub.challenge')

  if (challenge) {
    // GitHub webhook verification challenge
    return new NextResponse(challenge, {
      status: 200,
      headers: {
        'Content-Type': 'text/plain',
      },
    })
  }

  return NextResponse.json(
    { message: 'GitHub webhook endpoint is active' },
    { status: 200 }
  )
}
