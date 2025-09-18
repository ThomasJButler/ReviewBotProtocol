'use client'

import React, { useState } from 'react'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  MatrixCard,
} from '@/components/ui/card'
import { Badge, SecurityBadge, StatusBadge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ReviewSkeleton } from '@/components/ui/skeleton'
import {
  Shield,
  Zap,
  CheckCircle2,
  AlertTriangle,
  Bug,
  Clock,
  TrendingUp,
  FileText,
  Download,
  Share,
  ChevronDown,
  ChevronRight,
  ExternalLink,
  Copy,
  Eye,
  EyeOff,
} from 'lucide-react'
import { cn } from '@/lib/utils'

export interface ReviewFinding {
  id: string
  title: string
  description: string
  severity: 'critical' | 'high' | 'medium' | 'low' | 'info'
  category: 'security' | 'performance' | 'quality' | 'documentation'
  lineNumber?: number
  columnNumber?: number
  fileName?: string
  code?: string
  suggestion?: string
  references?: string[]
  impact?: string
  effort?: 'low' | 'medium' | 'high'
}

export interface ReviewResultsDisplay {
  id: string
  timestamp: string
  summary: string
  overallScore: number
  findings: ReviewFinding[]
  metrics: {
    totalIssues: number
    criticalIssues: number
    highIssues: number
    mediumIssues: number
    lowIssues: number
    securityIssues: number
    performanceIssues: number
    qualityIssues: number
    linesAnalyzed: number
    filesAnalyzed: number
  }
  duration: number
  aiModel: string
}

interface ReviewResultsProps {
  results: ReviewResultsDisplay | null
  isLoading: boolean
  onExport?: () => void
  onShare?: () => void
  className?: string
}

export default function ReviewResults({
  results,
  isLoading,
  onExport,
  onShare,
  className,
}: ReviewResultsProps) {
  const [expandedFindings, setExpandedFindings] = useState<Set<string>>(
    new Set()
  )
  const [activeTab, setActiveTab] = useState('overview')
  const [showOnlyCritical, setShowOnlyCritical] = useState(false)

  const toggleFinding = (findingId: string) => {
    const newExpanded = new Set(expandedFindings)
    if (newExpanded.has(findingId)) {
      newExpanded.delete(findingId)
    } else {
      newExpanded.add(findingId)
    }
    setExpandedFindings(newExpanded)
  }

  const getScoreColor = (score: number) => {
    if (score >= 80) return 'text-green-500'
    if (score >= 60) return 'text-yellow-500'
    if (score >= 40) return 'text-orange-500'
    return 'text-red-500'
  }

  const getScoreGrade = (score: number) => {
    if (score >= 90) return 'A+'
    if (score >= 80) return 'A'
    if (score >= 70) return 'B'
    if (score >= 60) return 'C'
    if (score >= 50) return 'D'
    return 'F'
  }

  const filterFindings = (findings: ReviewFinding[]) => {
    if (showOnlyCritical) {
      return findings.filter(
        f => f.severity === 'critical' || f.severity === 'high'
      )
    }
    return findings
  }

  const getFindingsByCategory = (category: string) => {
    if (!results) return []
    return filterFindings(results.findings.filter(f => f.category === category))
  }

  const copyFindingToClipboard = async (finding: ReviewFinding) => {
    const text = `${finding.title}\n\nDescription: ${finding.description}\nSeverity: ${finding.severity}\nCategory: ${finding.category}${finding.suggestion ? `\n\nSuggestion: ${finding.suggestion}` : ''}`
    await navigator.clipboard.writeText(text)
  }

  if (isLoading) {
    return (
      <div className={cn('space-y-6', className)}>
        <ReviewSkeleton />
      </div>
    )
  }

  if (!results) {
    return (
      <div className={cn('text-center py-12', className)}>
        <FileText className="h-16 w-16 text-gray-400 mx-auto mb-4" />
        <h3 className="text-xl font-semibold text-white mb-2">
          No Review Results
        </h3>
        <p className="text-gray-400">
          Start a code review to see the results here
        </p>
      </div>
    )
  }

  return (
    <div className={cn('space-y-6', className)}>
      {/* Overview Summary */}
      <MatrixCard>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <CheckCircle2 className="h-6 w-6 text-matrix-green" />
                Code Review Complete
              </CardTitle>
              <CardDescription>
                Analyzed {results.metrics.linesAnalyzed} lines across{' '}
                {results.metrics.filesAnalyzed} files in{' '}
                {(results.duration / 1000).toFixed(1)}s
              </CardDescription>
            </div>

            <div className="flex items-center gap-3">
              <div className="text-right">
                <div
                  className={cn(
                    'text-3xl font-bold',
                    getScoreColor(results.overallScore)
                  )}
                >
                  {results.overallScore}
                </div>
                <div className="text-sm text-gray-400">
                  Grade: {getScoreGrade(results.overallScore)}
                </div>
              </div>

              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={onExport}>
                  <Download className="h-4 w-4 mr-2" />
                  Export
                </Button>
                <Button variant="outline" size="sm" onClick={onShare}>
                  <Share className="h-4 w-4 mr-2" />
                  Share
                </Button>
              </div>
            </div>
          </div>
        </CardHeader>

        <CardContent>
          <p className="text-gray-300 leading-relaxed mb-6">
            {results.summary}
          </p>

          {/* Metrics Grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="text-center p-4 rounded-lg bg-red-500/10 border border-red-500/20">
              <div className="text-2xl font-bold text-red-400">
                {results.metrics.criticalIssues}
              </div>
              <div className="text-sm text-gray-400">Critical</div>
            </div>
            <div className="text-center p-4 rounded-lg bg-orange-500/10 border border-orange-500/20">
              <div className="text-2xl font-bold text-orange-400">
                {results.metrics.highIssues}
              </div>
              <div className="text-sm text-gray-400">High</div>
            </div>
            <div className="text-center p-4 rounded-lg bg-yellow-500/10 border border-yellow-500/20">
              <div className="text-2xl font-bold text-yellow-400">
                {results.metrics.mediumIssues}
              </div>
              <div className="text-sm text-gray-400">Medium</div>
            </div>
            <div className="text-center p-4 rounded-lg bg-blue-500/10 border border-blue-500/20">
              <div className="text-2xl font-bold text-blue-400">
                {results.metrics.lowIssues}
              </div>
              <div className="text-sm text-gray-400">Low</div>
            </div>
          </div>
        </CardContent>
      </MatrixCard>

      {/* Findings Tabs */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <Bug className="h-5 w-5 text-yellow-500" />
              Detailed Findings ({results.findings.length})
            </CardTitle>

            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowOnlyCritical(!showOnlyCritical)}
            >
              {showOnlyCritical ? (
                <Eye className="h-4 w-4 mr-2" />
              ) : (
                <EyeOff className="h-4 w-4 mr-2" />
              )}
              {showOnlyCritical ? 'Show All' : 'Critical Only'}
            </Button>
          </div>
        </CardHeader>

        <CardContent>
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList className="grid w-full grid-cols-4">
              <TabsTrigger value="overview">
                All ({filterFindings(results.findings).length})
              </TabsTrigger>
              <TabsTrigger value="security" className="text-red-400">
                <Shield className="h-4 w-4 mr-1" />
                Security ({getFindingsByCategory('security').length})
              </TabsTrigger>
              <TabsTrigger value="performance" className="text-yellow-400">
                <Zap className="h-4 w-4 mr-1" />
                Performance ({getFindingsByCategory('performance').length})
              </TabsTrigger>
              <TabsTrigger value="quality" className="text-blue-400">
                <TrendingUp className="h-4 w-4 mr-1" />
                Quality ({getFindingsByCategory('quality').length})
              </TabsTrigger>
            </TabsList>

            <TabsContent value="overview" className="mt-6">
              <FindingsList
                findings={filterFindings(results.findings)}
                expandedFindings={expandedFindings}
                onToggleFinding={toggleFinding}
                onCopyFinding={copyFindingToClipboard}
              />
            </TabsContent>

            <TabsContent value="security" className="mt-6">
              <FindingsList
                findings={getFindingsByCategory('security')}
                expandedFindings={expandedFindings}
                onToggleFinding={toggleFinding}
                onCopyFinding={copyFindingToClipboard}
              />
            </TabsContent>

            <TabsContent value="performance" className="mt-6">
              <FindingsList
                findings={getFindingsByCategory('performance')}
                expandedFindings={expandedFindings}
                onToggleFinding={toggleFinding}
                onCopyFinding={copyFindingToClipboard}
              />
            </TabsContent>

            <TabsContent value="quality" className="mt-6">
              <FindingsList
                findings={getFindingsByCategory('quality')}
                expandedFindings={expandedFindings}
                onToggleFinding={toggleFinding}
                onCopyFinding={copyFindingToClipboard}
              />
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
    </div>
  )
}

// Findings List Component
interface FindingsListProps {
  findings: ReviewFinding[]
  expandedFindings: Set<string>
  onToggleFinding: (id: string) => void
  onCopyFinding: (finding: ReviewFinding) => void
}

function FindingsList({
  findings,
  expandedFindings,
  onToggleFinding,
  onCopyFinding,
}: FindingsListProps) {
  if (findings.length === 0) {
    return (
      <div className="text-center py-8">
        <CheckCircle2 className="h-12 w-12 text-green-500 mx-auto mb-4" />
        <p className="text-lg font-medium text-white mb-2">No issues found!</p>
        <p className="text-gray-400">This category looks clean.</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {findings.map(finding => (
        <FindingCard
          key={finding.id}
          finding={finding}
          expanded={expandedFindings.has(finding.id)}
          onToggle={() => onToggleFinding(finding.id)}
          onCopy={() => onCopyFinding(finding)}
        />
      ))}
    </div>
  )
}

// Individual Finding Card
interface FindingCardProps {
  finding: ReviewFinding
  expanded: boolean
  onToggle: () => void
  onCopy: () => void
}

function FindingCard({
  finding,
  expanded,
  onToggle,
  onCopy,
}: FindingCardProps) {
  const getCategoryIcon = (category: string) => {
    switch (category) {
      case 'security':
        return <Shield className="h-4 w-4" />
      case 'performance':
        return <Zap className="h-4 w-4" />
      case 'quality':
        return <TrendingUp className="h-4 w-4" />
      case 'documentation':
        return <FileText className="h-4 w-4" />
      default:
        return <Bug className="h-4 w-4" />
    }
  }

  return (
    <Card className="transition-all duration-200 hover:border-matrix-green/30">
      <CardContent className="p-4">
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-start gap-3 flex-1">
            <div className="mt-0.5">{getCategoryIcon(finding.category)}</div>

            <div className="flex-1">
              <div className="flex items-center gap-2 mb-2">
                <SecurityBadge severity={finding.severity} />
                <h4 className="font-medium text-white">{finding.title}</h4>
                {finding.lineNumber && (
                  <Badge variant="outline" size="sm">
                    Line {finding.lineNumber}
                  </Badge>
                )}
              </div>

              <p className="text-gray-400 text-sm leading-relaxed">
                {finding.description}
              </p>

              {finding.fileName && (
                <div className="flex items-center gap-1 mt-2 text-xs text-gray-500">
                  <FileText className="h-3 w-3" />
                  {finding.fileName}
                </div>
              )}
            </div>
          </div>

          <div className="flex items-center gap-1 ml-4">
            <Button variant="ghost" size="sm" onClick={onCopy}>
              <Copy className="h-4 w-4" />
            </Button>
            <Button variant="ghost" size="sm" onClick={onToggle}>
              {expanded ? (
                <ChevronDown className="h-4 w-4" />
              ) : (
                <ChevronRight className="h-4 w-4" />
              )}
            </Button>
          </div>
        </div>

        {expanded && (
          <div className="border-t border-border pt-4 mt-4 space-y-4 animate-fade-in">
            {finding.code && (
              <div>
                <h5 className="text-sm font-medium text-white mb-2">Code:</h5>
                <pre className="bg-deep-black/50 rounded-lg p-3 text-sm overflow-x-auto">
                  <code className="text-gray-300">{finding.code}</code>
                </pre>
              </div>
            )}

            {finding.suggestion && (
              <div>
                <h5 className="text-sm font-medium text-white mb-2">
                  Suggestion:
                </h5>
                <div className="bg-matrix-green/10 border border-matrix-green/30 rounded-lg p-3">
                  <p className="text-matrix-green text-sm">
                    {finding.suggestion}
                  </p>
                </div>
              </div>
            )}

            {finding.impact && (
              <div>
                <h5 className="text-sm font-medium text-white mb-2">Impact:</h5>
                <p className="text-gray-400 text-sm">{finding.impact}</p>
              </div>
            )}

            {finding.effort && (
              <div className="flex items-center gap-2">
                <span className="text-sm text-gray-400">Effort to fix:</span>
                <Badge
                  variant={
                    finding.effort === 'low'
                      ? 'success'
                      : finding.effort === 'medium'
                        ? 'warning'
                        : 'error'
                  }
                >
                  {finding.effort}
                </Badge>
              </div>
            )}

            {finding.references && finding.references.length > 0 && (
              <div>
                <h5 className="text-sm font-medium text-white mb-2">
                  References:
                </h5>
                <div className="space-y-1">
                  {finding.references.map((ref, idx) => (
                    <a
                      key={idx}
                      href={ref}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1 text-sm text-matrix-green hover:text-matrix-cyan transition-colors"
                    >
                      <ExternalLink className="h-3 w-3" />
                      {ref}
                    </a>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
