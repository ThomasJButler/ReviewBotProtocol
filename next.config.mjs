import { dirname } from 'path'
import { fileURLToPath } from 'url'

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // This repository holds the backend too, so pin the tracing root here rather
  // than letting Next guess from whichever lockfile it finds first.
  outputFileTracingRoot: dirname(fileURLToPath(import.meta.url)),
}

export default nextConfig
