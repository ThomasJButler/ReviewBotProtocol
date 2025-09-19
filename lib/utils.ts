import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatDate(date: string | Date) {
  return new Intl.DateTimeFormat('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  }).format(new Date(date))
}

export function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 Bytes'

  const k = 1024
  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))

  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

export function formatTimeAgo(date: string | Date): string {
  const now = new Date()
  const past = new Date(date)
  const diffInSeconds = Math.floor((now.getTime() - past.getTime()) / 1000)

  if (diffInSeconds < 60) {
    return `${diffInSeconds} seconds ago`
  }

  const diffInMinutes = Math.floor(diffInSeconds / 60)
  if (diffInMinutes < 60) {
    return `${diffInMinutes} minute${diffInMinutes > 1 ? 's' : ''} ago`
  }

  const diffInHours = Math.floor(diffInMinutes / 60)
  if (diffInHours < 24) {
    return `${diffInHours} hour${diffInHours > 1 ? 's' : ''} ago`
  }

  const diffInDays = Math.floor(diffInHours / 24)
  if (diffInDays < 30) {
    return `${diffInDays} day${diffInDays > 1 ? 's' : ''} ago`
  }

  const diffInMonths = Math.floor(diffInDays / 30)
  if (diffInMonths < 12) {
    return `${diffInMonths} month${diffInMonths > 1 ? 's' : ''} ago`
  }

  const diffInYears = Math.floor(diffInMonths / 12)
  return `${diffInYears} year${diffInYears > 1 ? 's' : ''} ago`
}

export function getStateIcon(state: string) {
  switch (state.toLowerCase()) {
    case 'open':
      return '🟢'
    case 'closed':
      return '🔴'
    case 'merged':
      return '🟣'
    case 'draft':
      return '⚪'
    default:
      return '⚫'
  }
}

export function getFileInfo(file: File) {
  const extension = file.name.split('.').pop()?.toLowerCase() || ''

  const fileTypes: Record<
    string,
    { icon: string; color: string; label: string }
  > = {
    // JavaScript & TypeScript
    js: { icon: '📄', color: 'text-yellow-400', label: 'JavaScript' },
    jsx: { icon: '⚛️', color: 'text-blue-400', label: 'React JSX' },
    ts: { icon: '📘', color: 'text-blue-600', label: 'TypeScript' },
    tsx: { icon: '⚛️', color: 'text-blue-600', label: 'React TSX' },

    // Web Technologies
    html: { icon: '🌐', color: 'text-orange-500', label: 'HTML' },
    css: { icon: '🎨', color: 'text-blue-500', label: 'CSS' },
    scss: { icon: '🎨', color: 'text-pink-500', label: 'SCSS' },
    sass: { icon: '🎨', color: 'text-pink-500', label: 'Sass' },
    less: { icon: '🎨', color: 'text-blue-600', label: 'Less' },

    // Backend Languages
    py: { icon: '🐍', color: 'text-green-500', label: 'Python' },
    java: { icon: '☕', color: 'text-red-600', label: 'Java' },
    cs: { icon: '🔷', color: 'text-purple-600', label: 'C#' },
    cpp: { icon: '⚙️', color: 'text-blue-700', label: 'C++' },
    c: { icon: '⚙️', color: 'text-blue-600', label: 'C' },
    go: { icon: '🐹', color: 'text-cyan-500', label: 'Go' },
    rs: { icon: '🦀', color: 'text-orange-600', label: 'Rust' },
    php: { icon: '🐘', color: 'text-purple-500', label: 'PHP' },
    rb: { icon: '💎', color: 'text-red-500', label: 'Ruby' },
    swift: { icon: '🍎', color: 'text-orange-500', label: 'Swift' },
    kt: { icon: '🎯', color: 'text-purple-700', label: 'Kotlin' },
    scala: { icon: '⚡', color: 'text-red-700', label: 'Scala' },

    // Data & Config
    json: { icon: '📋', color: 'text-yellow-600', label: 'JSON' },
    xml: { icon: '📄', color: 'text-orange-600', label: 'XML' },
    yaml: { icon: '📝', color: 'text-purple-400', label: 'YAML' },
    yml: { icon: '📝', color: 'text-purple-400', label: 'YAML' },
    toml: { icon: '⚙️', color: 'text-gray-600', label: 'TOML' },
    ini: { icon: '⚙️', color: 'text-gray-500', label: 'INI' },

    // Documentation
    md: { icon: '📖', color: 'text-blue-300', label: 'Markdown' },
    txt: { icon: '📄', color: 'text-gray-400', label: 'Text' },

    // Database
    sql: { icon: '🗃️', color: 'text-blue-800', label: 'SQL' },

    // Shell Scripts
    sh: { icon: '💻', color: 'text-green-400', label: 'Shell Script' },
    bash: { icon: '💻', color: 'text-green-500', label: 'Bash Script' },
    ps1: { icon: '💻', color: 'text-blue-400', label: 'PowerShell' },

    // Default
    default: { icon: '📄', color: 'text-gray-400', label: 'File' },
  }

  return fileTypes[extension] || fileTypes.default
}

export function calculateComplexity(code: string): number {
  // Simple cyclomatic complexity calculation
  const complexityKeywords = [
    'if',
    'else',
    'elif',
    'while',
    'for',
    'switch',
    'case',
    'catch',
    'finally',
    '&&',
    '||',
    '?',
    ':',
    'try',
  ]

  let complexity = 1 // Base complexity

  for (const keyword of complexityKeywords) {
    const regex = new RegExp(`\\b${keyword}\\b`, 'gi')
    const matches = code.match(regex)
    if (matches) {
      complexity += matches.length
    }
  }

  return complexity
}

export function truncateText(text: string, maxLength: number) {
  if (text.length <= maxLength) return text
  return text.slice(0, maxLength) + '...'
}

export function debounce<T extends (...args: any[]) => any>(
  func: T,
  delay: number
): (...args: Parameters<T>) => void {
  let timeoutId: NodeJS.Timeout
  return (...args: Parameters<T>) => {
    clearTimeout(timeoutId)
    timeoutId = setTimeout(() => func(...args), delay)
  }
}

export function generateId(): string {
  return Math.random().toString(36).substr(2, 9)
}
