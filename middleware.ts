import { NextResponse, type NextRequest } from 'next/server'

/**
 * The dashboard has no login. It is meant to be reached only from this
 * machine, so any request whose Host is not loopback is refused before a
 * page or a server action runs. This also defeats DNS rebinding, where a
 * hostile page resolves its own name to 127.0.0.1 to reach us.
 */
const ALLOWED_HOSTS = new Set(['localhost', '127.0.0.1', '[::1]'])

export function middleware(request: NextRequest) {
  const host = (request.headers.get('host') ?? '')
    .replace(/:\d+$/, '')
    .toLowerCase()
  if (!ALLOWED_HOSTS.has(host)) {
    return new NextResponse('This dashboard only answers to localhost.', {
      status: 421,
      headers: { 'content-type': 'text/plain; charset=utf-8' },
    })
  }
  return NextResponse.next()
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon).*)'],
}
