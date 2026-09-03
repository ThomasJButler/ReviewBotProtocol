import { dirname } from 'path'
import { fileURLToPath } from 'url'

/** @type {import('next').NextConfig} */
const isProduction = process.env.NODE_ENV === 'production'

// A strict policy in production; the dev server needs eval for its overlay.
const csp = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${isProduction ? '' : " 'unsafe-eval'"}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data:",
  "font-src 'self'",
  "connect-src 'self'",
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
].join('; ')

const nextConfig = {
  poweredByHeader: false,
  async headers() {
    return [
      {
        source: '/(.*)',
        headers: [
          { key: 'Content-Security-Policy', value: csp },
          { key: 'Referrer-Policy', value: 'no-referrer' },
          { key: 'X-Content-Type-Options', value: 'nosniff' },
          { key: 'X-Frame-Options', value: 'DENY' },
        ],
      },
    ]
  },
  reactStrictMode: true,
  // This repository holds the backend too, so pin the tracing root here rather
  // than letting Next guess from whichever lockfile it finds first.
  outputFileTracingRoot: dirname(fileURLToPath(import.meta.url)),
}

export default nextConfig
