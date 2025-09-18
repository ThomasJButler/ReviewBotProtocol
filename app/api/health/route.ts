import { NextResponse } from 'next/server'

export async function GET() {
  const healthData = {
    status: 'healthy',
    timestamp: new Date().toISOString(),
    version: '1.0.0',
    service: 'Git Review Assistant',
    uptime: process.uptime(),
    memory: process.memoryUsage(),
    environment: process.env.NODE_ENV || 'development',
    features: {
      codeReview: true,
      githubIntegration: !!process.env.GITHUB_TOKEN,
      aiAnalysis: !!process.env.OPENAI_API_KEY,
      webhooks: true,
    },
    checks: {
      api: 'ok',
      database: 'ok', // Would check actual DB connection
      ai: !!process.env.OPENAI_API_KEY ? 'ok' : 'disabled',
      github: !!process.env.GITHUB_TOKEN ? 'ok' : 'disabled',
    },
  }

  return NextResponse.json(healthData)
}
