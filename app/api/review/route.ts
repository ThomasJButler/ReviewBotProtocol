import { NextRequest, NextResponse } from 'next/server'
import { z } from 'zod'

// Request validation schema
const reviewRequestSchema = z.object({
  code: z.string().min(1, 'Code content is required'),
  language: z.string().optional().default('javascript'),
  mode: z.enum(['paste', 'upload', 'pr']).optional().default('paste'),
  filename: z.string().optional(),
})

// Enhanced AI review service - connects to Python FastAPI backend
async function analyzeCode(code: string, language: string, filename?: string) {
  try {
    // Call the Python FastAPI backend
    const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000'

    const response = await fetch(`${backendUrl}/review/code`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        files: [
          {
            filename: filename || `code.${getFileExtension(language)}`,
            content: code,
            language: language,
            status: 'modified',
            changes: code.split('\n').length,
            patch: code,
          },
        ],
      }),
      // Add timeout for long-running AI analysis
      signal: AbortSignal.timeout(120000), // 2 minutes timeout
    })

    if (!response.ok) {
      throw new Error(`Backend responded with status: ${response.status}`)
    }

    const backendResult = await response.json()

    // Transform backend result to frontend format
    return transformBackendResult(backendResult, code)
  } catch (error) {
    console.error('AI backend error:', error)

    // Fallback to basic analysis if backend is unavailable
    return await fallbackAnalysis(code, language, filename)
  }
}

function getFileExtension(language: string): string {
  const extensions: Record<string, string> = {
    javascript: 'js',
    typescript: 'ts',
    python: 'py',
    java: 'java',
    csharp: 'cs',
    php: 'php',
    ruby: 'rb',
    go: 'go',
    rust: 'rs',
    cpp: 'cpp',
    c: 'c',
    html: 'html',
    css: 'css',
    sql: 'sql',
    json: 'json',
  }
  return extensions[language] || 'txt'
}

function transformBackendResult(backendResult: any, code: string) {
  // Extract findings from different categories
  const allFindings = [
    ...(backendResult.security_issues || []),
    ...(backendResult.performance_issues || []),
    ...(backendResult.quality_issues || []),
    ...(backendResult.documentation_issues || []),
    ...(backendResult.testing_issues || []),
    ...(backendResult.architecture_issues || []),
  ]

  // Map backend findings to frontend format
  const mappedFindings = allFindings.map((finding: any, index: number) => ({
    id: `ai-${index + 1}`,
    title: finding.type || finding.title || 'Issue detected',
    description: finding.description,
    severity: finding.severity || 'medium',
    category: getCategoryFromType(finding.type || 'quality'),
    lineNumber: finding.line_number || null,
    suggestion:
      finding.recommendation ||
      finding.suggestion ||
      'Review and fix this issue',
    impact: finding.impact,
    complexity_before: finding.complexity_before,
    complexity_after: finding.complexity_after,
  }))

  return {
    security: mappedFindings.filter(f => f.category === 'security'),
    performance: mappedFindings.filter(f => f.category === 'performance'),
    quality: mappedFindings.filter(f => f.category === 'quality'),
    documentation: mappedFindings.filter(f => f.category === 'documentation'),
    testing: mappedFindings.filter(f => f.category === 'testing'),
    architecture: mappedFindings.filter(f => f.category === 'architecture'),
    summary: backendResult.summary || generateEnhancedSummary(backendResult),
    score: backendResult.overall_score || 8.5,
    letterGrade: backendResult.letter_grade || 'B+',
    scoringBreakdown: backendResult.scoring_breakdown || {},
    codeSuggestions: backendResult.code_suggestions || [],
    priorityFixes: backendResult.priority_fixes || [],
    quickWins: backendResult.quick_wins || [],
    totalIssues: mappedFindings.length,
    analysisTime: backendResult.analysis_time || '15.2s',
    linesAnalyzed: code.split('\n').length,
    aiMetrics: backendResult.ai_metrics || {},
  }
}

function getCategoryFromType(type: string): string {
  if (
    type.toLowerCase().includes('security') ||
    type.toLowerCase().includes('vulnerability')
  ) {
    return 'security'
  }
  if (
    type.toLowerCase().includes('performance') ||
    type.toLowerCase().includes('complexity')
  ) {
    return 'performance'
  }
  if (
    type.toLowerCase().includes('documentation') ||
    type.toLowerCase().includes('comment')
  ) {
    return 'documentation'
  }
  if (
    type.toLowerCase().includes('test') ||
    type.toLowerCase().includes('coverage')
  ) {
    return 'testing'
  }
  if (
    type.toLowerCase().includes('architecture') ||
    type.toLowerCase().includes('design')
  ) {
    return 'architecture'
  }
  return 'quality'
}

function generateEnhancedSummary(result: any): string {
  const grade = result.letter_grade || 'B'
  const score = result.overall_score || 85

  let summary = `Code Review Complete\n\nAnalyzed ${result.files_reviewed?.length || 1} files in ${result.analysis_time || '15s'}\n\nGrade: ${grade}`

  if (score >= 90) {
    summary += '\n\nExcellent code quality with minimal issues.'
  } else if (score >= 80) {
    summary += '\n\nGood code quality with minor improvements suggested.'
  } else if (score >= 70) {
    summary += '\n\nAcceptable code quality with several areas for improvement.'
  } else if (score >= 60) {
    summary += '\n\nCode needs improvement to meet quality standards.'
  } else {
    summary += '\n\nCode requires significant improvements before deployment.'
  }

  if (result.priority_fixes?.length > 0) {
    summary += `\n\nPriority fixes needed: ${result.priority_fixes.length}`
  }

  return summary
}

// Fallback analysis when backend is unavailable
async function fallbackAnalysis(
  code: string,
  language: string,
  filename?: string
) {
  const findings: any[] = []

  // Basic security check
  if (!code.includes('//') && !code.includes('/*')) {
    findings.push({
      id: 'fallback-1',
      title: 'Missing comments',
      description: 'Code lacks documentation comments',
      severity: 'info',
      category: 'quality',
      suggestion: 'Add comments to explain complex logic',
    })
  }

  return {
    security: [],
    performance: [],
    quality: findings,
    documentation: [],
    testing: [],
    architecture: [],
    summary:
      'Basic analysis completed (AI backend unavailable)\n\nGrade: C\n\nLimited analysis performed due to backend connectivity issues.',
    score: 7.0,
    letterGrade: 'C',
    scoringBreakdown: { overall_score: 70, letter_grade: 'C' },
    codeSuggestions: [],
    priorityFixes: [],
    quickWins: [],
    totalIssues: findings.length,
    analysisTime: '0.1s',
    linesAnalyzed: code.split('\n').length,
    aiMetrics: {},
  }
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
