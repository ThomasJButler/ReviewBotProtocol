import { NextRequest, NextResponse } from 'next/server'
import { z } from 'zod'

// Request validation schema
const reviewRequestSchema = z.object({
  code: z.string().min(1, 'Code content is required'),
  language: z.string().optional().default('javascript'),
  mode: z.enum(['paste', 'upload', 'pr']).optional().default('paste'),
  filename: z.string().optional(),
})

// Mock AI review service
async function analyzeCode(code: string, language: string, filename?: string) {
  // Simulate API delay
  await new Promise(resolve => setTimeout(resolve, 2000))

  // Simple pattern-based analysis (replace with actual AI service)
  const findings: any[] = []

  // Security checks
  if (code.includes('eval(') || code.includes('innerHTML')) {
    findings.push({
      id: 'sec-1',
      title: 'Potential XSS vulnerability',
      description:
        'Use of eval() or innerHTML can lead to cross-site scripting attacks',
      severity: 'high',
      category: 'security',
      lineNumber:
        code
          .split('\n')
          .findIndex(
            line => line.includes('eval(') || line.includes('innerHTML')
          ) + 1,
      suggestion: 'Use safer alternatives like textContent or sanitize input',
    })
  }

  if (code.includes('SELECT * FROM') && !code.includes('?')) {
    findings.push({
      id: 'sec-2',
      title: 'SQL injection risk',
      description:
        'Direct string concatenation in SQL queries can lead to injection attacks',
      severity: 'critical',
      category: 'security',
      suggestion: 'Use parameterized queries or prepared statements',
    })
  }

  // Performance checks
  if (code.includes('for (') && code.includes('for (')) {
    findings.push({
      id: 'perf-1',
      title: 'Nested loops detected',
      description:
        'Nested loops can cause performance issues with large datasets',
      severity: 'medium',
      category: 'performance',
      suggestion:
        'Consider optimizing algorithm complexity or using more efficient data structures',
    })
  }

  // Code quality checks
  if (code.split('\n').some(line => line.length > 100)) {
    findings.push({
      id: 'qual-1',
      title: 'Long lines detected',
      description: 'Lines longer than 100 characters reduce readability',
      severity: 'low',
      category: 'quality',
      suggestion: 'Break long lines for better readability',
    })
  }

  if (!code.includes('//') && !code.includes('/*')) {
    findings.push({
      id: 'qual-2',
      title: 'Missing comments',
      description: 'Code lacks documentation comments',
      severity: 'info',
      category: 'quality',
      suggestion: 'Add comments to explain complex logic',
    })
  }

  // Calculate score
  const criticalCount = findings.filter(f => f.severity === 'critical').length
  const highCount = findings.filter(f => f.severity === 'high').length
  const mediumCount = findings.filter(f => f.severity === 'medium').length

  let score = 10 - criticalCount * 3 - highCount * 2 - mediumCount * 1
  score = Math.max(0, Math.min(10, score))

  return {
    security: findings.filter(f => f.category === 'security'),
    performance: findings.filter(f => f.category === 'performance'),
    quality: findings.filter(f => f.category === 'quality'),
    summary: generateSummary(findings, score),
    score,
    totalIssues: findings.length,
    analysisTime: '2.3s',
    linesAnalyzed: code.split('\n').length,
  }
}

function generateSummary(findings: any[], score: number): string {
  if (findings.length === 0) {
    return 'Excellent! No significant issues found. Your code follows security best practices and maintains good quality standards.'
  }

  const criticalCount = findings.filter(f => f.severity === 'critical').length
  const highCount = findings.filter(f => f.severity === 'high').length

  if (criticalCount > 0) {
    return `Critical security vulnerabilities detected. Immediate action required to fix ${criticalCount} critical and ${highCount} high severity issues.`
  }

  if (highCount > 0) {
    return `High priority issues found that should be addressed. Focus on the ${highCount} high severity findings first.`
  }

  if (score >= 7) {
    return 'Good code quality with minor improvements suggested. Address the identified issues to enhance security and maintainability.'
  }

  return 'Several areas for improvement identified. Review the findings to enhance code quality, security, and performance.'
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()

    // Validate request
    const result = reviewRequestSchema.safeParse(body)
    if (!result.success) {
      return NextResponse.json(
        { error: 'Invalid request', details: result.error.issues },
        { status: 400 }
      )
    }

    const { code, language, filename } = result.data

    // Perform code analysis
    const analysis = await analyzeCode(code, language, filename)

    return NextResponse.json({
      success: true,
      data: analysis,
      metadata: {
        timestamp: new Date().toISOString(),
        language,
        filename,
        codeLength: code.length,
      },
    })
  } catch (error) {
    console.error('Review API error:', error)
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}

export async function GET() {
  return NextResponse.json({
    status: 'OK',
    service: 'Code Review API',
    version: '1.0.0',
    endpoints: {
      review: 'POST /api/review',
      health: 'GET /api/health',
    },
  })
}
