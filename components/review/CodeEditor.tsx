'use client'

import React, { useRef, useEffect, useState } from 'react'
import { Editor } from '@monaco-editor/react'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Copy,
  Download,
  Maximize2,
  Minimize2,
  RotateCcw,
  FileText,
  Code2,
  Zap,
} from 'lucide-react'
import { cn } from '@/lib/utils'

interface CodeEditorProps {
  value: string
  onChange?: (value: string | undefined) => void
  language?: string
  height?: string | number
  readOnly?: boolean
  showLineNumbers?: boolean
  showMinimap?: boolean
  className?: string
  placeholder?: string
  onLanguageChange?: (language: string) => void
  showMetrics?: boolean
}

interface CodeMetrics {
  lines: number
  characters: number
  words: number
  complexity: number
}

const SUPPORTED_LANGUAGES = [
  { value: 'javascript', label: 'JavaScript', icon: '🟨' },
  { value: 'typescript', label: 'TypeScript', icon: '🟦' },
  { value: 'python', label: 'Python', icon: '🐍' },
  { value: 'java', label: 'Java', icon: '☕' },
  { value: 'csharp', label: 'C#', icon: '💜' },
  { value: 'php', label: 'PHP', icon: '🟣' },
  { value: 'ruby', label: 'Ruby', icon: '💎' },
  { value: 'go', label: 'Go', icon: '🔷' },
  { value: 'rust', label: 'Rust', icon: '🦀' },
  { value: 'cpp', label: 'C++', icon: '⚡' },
  { value: 'json', label: 'JSON', icon: '📋' },
  { value: 'html', label: 'HTML', icon: '🌐' },
  { value: 'css', label: 'CSS', icon: '🎨' },
  { value: 'sql', label: 'SQL', icon: '🗄️' },
]

export default function CodeEditor({
  value,
  onChange,
  language = 'javascript',
  height = 400,
  readOnly = false,
  showLineNumbers = true,
  showMinimap = false,
  className,
  placeholder = 'Enter your code here...',
  onLanguageChange,
  showMetrics = true,
}: CodeEditorProps) {
  const editorRef = useRef<any>(null)
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [editorLanguage, setEditorLanguage] = useState(language)
  const [metrics, setMetrics] = useState<CodeMetrics>({
    lines: 0,
    characters: 0,
    words: 0,
    complexity: 0,
  })

  // Calculate code metrics
  useEffect(() => {
    if (value) {
      const lines = value.split('\n').length
      const characters = value.length
      const words = value.split(/\s+/).filter(word => word.length > 0).length

      // Simple complexity calculation (count of control structures)
      const complexityPatterns = [
        /\bif\b/g,
        /\belse\b/g,
        /\bfor\b/g,
        /\bwhile\b/g,
        /\bswitch\b/g,
        /\bcatch\b/g,
        /\btry\b/g,
        /\bdo\b/g,
      ]
      const complexity = complexityPatterns.reduce((acc, pattern) => {
        const matches = value.match(pattern)
        return acc + (matches ? matches.length : 0)
      }, 0)

      setMetrics({ lines, characters, words, complexity })
    } else {
      setMetrics({ lines: 0, characters: 0, words: 0, complexity: 0 })
    }
  }, [value])

  const handleEditorDidMount = (editor: any, monaco: any) => {
    editorRef.current = editor
    console.log('Monaco Editor mounted successfully')

    // Ensure editor is focusable and editable
    if (!readOnly) {
      editor.focus()
      // Force the editor to be interactive
      editor.updateOptions({ readOnly: false })
    }

    // Configure editor theme
    monaco.editor.defineTheme('matrix-dark', {
      base: 'vs-dark',
      inherit: true,
      rules: [
        { token: 'comment', foreground: '#6A9955', fontStyle: 'italic' },
        { token: 'keyword', foreground: '#00FF00', fontStyle: 'bold' },
        { token: 'string', foreground: '#00FFFF' },
        { token: 'number', foreground: '#FFFF00' },
        { token: 'regexp', foreground: '#FF6B6B' },
        { token: 'type', foreground: '#4ECDC4' },
        { token: 'class', foreground: '#45B7D1' },
        { token: 'function', foreground: '#96CEB4' },
        { token: 'variable', foreground: '#FFEAA7' },
      ],
      colors: {
        'editor.background': '#0a0a0a',
        'editor.foreground': '#ffffff',
        'editor.lineHighlightBackground': '#1a1a1a',
        'editor.selectionBackground': '#00ff0020',
        'editorCursor.foreground': '#00ff00',
        'editorLineNumber.foreground': '#666666',
        'editorLineNumber.activeForeground': '#00ff00',
        'editor.selectionHighlightBackground': '#00ff0010',
        'editor.wordHighlightBackground': '#00ffff10',
        'editor.findMatchBackground': '#00ff0030',
        'editor.findMatchHighlightBackground': '#00ff0015',
        'editorBracketMatch.background': '#00ff0020',
        'editorBracketMatch.border': '#00ff00',
      },
    })

    monaco.editor.setTheme('matrix-dark')
  }

  const handleLanguageChange = (newLanguage: string) => {
    setEditorLanguage(newLanguage)
    onLanguageChange?.(newLanguage)
  }

  const handleCopyCode = async () => {
    if (value) {
      await navigator.clipboard.writeText(value)
      // You could add a toast notification here
    }
  }

  const handleDownloadCode = () => {
    if (value) {
      const extension =
        SUPPORTED_LANGUAGES.find(lang => lang.value === editorLanguage)
          ?.value || 'txt'
      const blob = new Blob([value], { type: 'text/plain' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `code.${extension}`
      a.click()
      URL.revokeObjectURL(url)
    }
  }

  const handleFormatCode = () => {
    if (editorRef.current) {
      editorRef.current.getAction('editor.action.formatDocument').run()
    }
  }

  const toggleFullscreen = () => {
    setIsFullscreen(!isFullscreen)
  }

  const getComplexityColor = (complexity: number) => {
    if (complexity < 5) return 'success'
    if (complexity < 10) return 'warning'
    return 'error'
  }

  return (
    <div
      className={cn(
        'relative',
        isFullscreen && 'fixed inset-0 z-50 bg-deep-black p-4',
        className
      )}
    >
      <Card className={cn('overflow-hidden', isFullscreen && 'h-full')}>
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-border bg-card-surface/30">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <Code2 className="h-5 w-5 text-matrix-green" />
              <h3 className="font-semibold text-white">Code Editor</h3>
            </div>

            {/* Language Selector */}
            <select
              value={editorLanguage}
              onChange={e => handleLanguageChange(e.target.value)}
              className="bg-input border border-border rounded-lg px-3 py-1 text-sm text-white focus:border-matrix-green focus:outline-none"
            >
              {SUPPORTED_LANGUAGES.map(lang => (
                <option key={lang.value} value={lang.value}>
                  {lang.icon} {lang.label}
                </option>
              ))}
            </select>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={handleFormatCode}
              disabled={readOnly}
            >
              <Zap className="h-4 w-4 mr-2" />
              Format
            </Button>

            <Button
              variant="ghost"
              size="sm"
              onClick={handleCopyCode}
              disabled={!value}
            >
              <Copy className="h-4 w-4" />
            </Button>

            <Button
              variant="ghost"
              size="sm"
              onClick={handleDownloadCode}
              disabled={!value}
            >
              <Download className="h-4 w-4" />
            </Button>

            <Button variant="ghost" size="sm" onClick={toggleFullscreen}>
              {isFullscreen ? (
                <Minimize2 className="h-4 w-4" />
              ) : (
                <Maximize2 className="h-4 w-4" />
              )}
            </Button>
          </div>
        </div>

        {/* Editor */}
        <div
          className="relative bg-card-surface rounded-lg border border-border overflow-hidden"
          onClick={() => {
            // Focus the editor when the container is clicked
            if (editorRef.current && !readOnly) {
              editorRef.current.focus()
            }
          }}
        >
          <Editor
            height={isFullscreen ? 'calc(100vh - 200px)' : height}
            value={value}
            language={editorLanguage}
            onChange={value => {
              console.log('Monaco Editor onChange:', value)
              onChange?.(value)
            }}
            onMount={handleEditorDidMount}
            options={{
              readOnly: readOnly || false,
              lineNumbers: showLineNumbers ? 'on' : 'off',
              minimap: { enabled: showMinimap },
              fontSize: 14,
              fontFamily: 'JetBrains Mono, Fira Code, monospace',
              wordWrap: 'on',
              automaticLayout: true,
              scrollBeyondLastLine: false,
              smoothScrolling: true,
              cursorBlinking: 'smooth',
              renderLineHighlight: 'all',
              bracketPairColorization: { enabled: true },
              selectOnLineNumbers: true,
              roundedSelection: false,
              scrollbar: {
                vertical: 'visible',
                horizontal: 'visible',
              },
              guides: {
                bracketPairs: true,
                indentation: true,
              },
              suggest: {
                showMethods: !readOnly,
                showFunctions: !readOnly,
                showConstructors: !readOnly,
                showDeprecated: true,
                showFields: !readOnly,
                showVariables: !readOnly,
                showClasses: !readOnly,
                showStructs: !readOnly,
                showInterfaces: !readOnly,
                showModules: !readOnly,
                showProperties: !readOnly,
                showEvents: !readOnly,
                showOperators: !readOnly,
                showUnits: !readOnly,
                showValues: !readOnly,
                showConstants: !readOnly,
                showEnums: !readOnly,
                showEnumMembers: !readOnly,
                showKeywords: !readOnly,
                showWords: !readOnly,
                showColors: !readOnly,
                showFiles: !readOnly,
                showReferences: !readOnly,
                showFolders: !readOnly,
                showTypeParameters: !readOnly,
                showSnippets: !readOnly,
              },
              quickSuggestions: !readOnly,
              parameterHints: { enabled: !readOnly },
              hover: { enabled: true },
              lightbulb: { enabled: !readOnly ? 'on' : ('off' as any) },
            }}
            loading={
              <div className="flex items-center justify-center h-full">
                <div className="flex items-center gap-2 text-matrix-green">
                  <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-matrix-green"></div>
                  <span>Loading editor...</span>
                </div>
              </div>
            }
          />
        </div>

        {/* Metrics Footer */}
        {showMetrics && value && (
          <div className="flex items-center justify-between p-4 border-t border-border bg-card-surface/30">
            <div className="flex items-center gap-4 text-sm text-gray-400">
              <span>{metrics.lines} lines</span>
              <span>{metrics.characters} characters</span>
              <span>{metrics.words} words</span>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-400">Complexity:</span>
              <Badge variant={getComplexityColor(metrics.complexity) as any}>
                {metrics.complexity}
              </Badge>
            </div>
          </div>
        )}
      </Card>
    </div>
  )
}
