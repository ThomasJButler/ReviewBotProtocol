'use client'

import React, { useCallback, useState, useRef } from 'react'
import { useDropzone } from 'react-dropzone'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { formatFileSize, getFileInfo } from '@/lib/utils'
import {
  Upload,
  FileCode,
  X,
  File,
  FolderOpen,
  AlertCircle,
  CheckCircle2,
  FileText,
  Image,
  Archive,
  HardDrive,
  Eye,
  Trash2,
  Download,
} from 'lucide-react'
import { cn } from '@/lib/utils'

interface UploadedFile extends File {
  id: string
  preview?: string
  status: 'pending' | 'uploading' | 'success' | 'error'
  error?: string
  progress?: number
}

interface FileUploadProps {
  onFilesSelected: (files: File[]) => void
  selectedFiles: UploadedFile[]
  onRemoveFile: (fileId: string) => void
  maxFiles?: number
  maxSize?: number // in MB
  acceptedTypes?: string[]
  multiple?: boolean
  disabled?: boolean
  className?: string
  showPreview?: boolean
  onFilesUploaded?: (files: UploadedFile[]) => void
}

const SUPPORTED_FILE_TYPES = {
  // Code files
  '.js': { icon: FileCode, color: 'text-yellow-500', label: 'JavaScript' },
  '.jsx': { icon: FileCode, color: 'text-blue-500', label: 'React JSX' },
  '.ts': { icon: FileCode, color: 'text-blue-600', label: 'TypeScript' },
  '.tsx': { icon: FileCode, color: 'text-blue-600', label: 'React TSX' },
  '.py': { icon: FileCode, color: 'text-green-500', label: 'Python' },
  '.java': { icon: FileCode, color: 'text-orange-600', label: 'Java' },
  '.cs': { icon: FileCode, color: 'text-purple-500', label: 'C#' },
  '.php': { icon: FileCode, color: 'text-purple-600', label: 'PHP' },
  '.rb': { icon: FileCode, color: 'text-red-500', label: 'Ruby' },
  '.go': { icon: FileCode, color: 'text-cyan-500', label: 'Go' },
  '.rs': { icon: FileCode, color: 'text-orange-500', label: 'Rust' },
  '.cpp': { icon: FileCode, color: 'text-blue-400', label: 'C++' },
  '.c': { icon: FileCode, color: 'text-gray-500', label: 'C' },
  '.swift': { icon: FileCode, color: 'text-orange-400', label: 'Swift' },
  '.kt': { icon: FileCode, color: 'text-purple-400', label: 'Kotlin' },
  '.dart': { icon: FileCode, color: 'text-blue-300', label: 'Dart' },

  // Markup and config
  '.html': { icon: FileText, color: 'text-orange-500', label: 'HTML' },
  '.css': { icon: FileText, color: 'text-blue-500', label: 'CSS' },
  '.scss': { icon: FileText, color: 'text-pink-500', label: 'SCSS' },
  '.less': { icon: FileText, color: 'text-blue-400', label: 'LESS' },
  '.json': { icon: FileText, color: 'text-yellow-600', label: 'JSON' },
  '.xml': { icon: FileText, color: 'text-green-600', label: 'XML' },
  '.yaml': { icon: FileText, color: 'text-purple-500', label: 'YAML' },
  '.yml': { icon: FileText, color: 'text-purple-500', label: 'YAML' },
  '.toml': { icon: FileText, color: 'text-gray-600', label: 'TOML' },
  '.md': { icon: FileText, color: 'text-gray-400', label: 'Markdown' },

  // Archives
  '.zip': { icon: Archive, color: 'text-gray-500', label: 'ZIP Archive' },
  '.tar': { icon: Archive, color: 'text-gray-500', label: 'TAR Archive' },
  '.gz': { icon: Archive, color: 'text-gray-500', label: 'GZIP Archive' },

  // Default
  default: { icon: File, color: 'text-gray-400', label: 'File' },
}

export default function FileUpload({
  onFilesSelected,
  selectedFiles = [],
  onRemoveFile,
  maxFiles = 10,
  maxSize = 50, // 50MB default
  acceptedTypes,
  multiple = true,
  disabled = false,
  className,
  showPreview = true,
  onFilesUploaded,
}: FileUploadProps) {
  const [dragActive, setDragActive] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const validateFile = (file: File): { valid: boolean; error?: string } => {
    // Check file size
    if (file.size > maxSize * 1024 * 1024) {
      return { valid: false, error: `File size exceeds ${maxSize}MB limit` }
    }

    // Check file type if specified
    if (acceptedTypes && acceptedTypes.length > 0) {
      const fileExtension = '.' + file.name.split('.').pop()?.toLowerCase()
      if (!acceptedTypes.includes(fileExtension)) {
        return { valid: false, error: 'File type not supported' }
      }
    }

    // Check if we're at max files
    if (selectedFiles.length >= maxFiles) {
      return { valid: false, error: `Maximum ${maxFiles} files allowed` }
    }

    return { valid: true }
  }

  const processFiles = useCallback(
    (files: File[]) => {
      const validFiles: UploadedFile[] = []
      const invalidFiles: { file: File; error: string }[] = []

      files.forEach(file => {
        const validation = validateFile(file)
        if (validation.valid) {
          const uploadedFile: UploadedFile = {
            ...file,
            id: `${file.name}-${Date.now()}-${Math.random()}`,
            status: 'pending',
          }

          // Create preview for image files
          if (file.type.startsWith('image/') && showPreview) {
            const reader = new FileReader()
            reader.onload = () => {
              uploadedFile.preview = reader.result as string
            }
            reader.readAsDataURL(file)
          }

          validFiles.push(uploadedFile)
        } else {
          invalidFiles.push({ file, error: validation.error! })
        }
      })

      if (validFiles.length > 0) {
        onFilesSelected(validFiles)
      }

      // Handle invalid files (you could show a toast notification here)
      if (invalidFiles.length > 0) {
        console.warn('Invalid files:', invalidFiles)
      }
    },
    [
      onFilesSelected,
      selectedFiles.length,
      maxFiles,
      maxSize,
      acceptedTypes,
      showPreview,
    ]
  )

  const onDrop = useCallback(
    (acceptedFiles: File[]) => {
      setDragActive(false)
      processFiles(acceptedFiles)
    },
    [processFiles]
  )

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    onDragEnter: () => setDragActive(true),
    onDragLeave: () => setDragActive(false),
    multiple,
    disabled,
    maxFiles,
    maxSize: maxSize * 1024 * 1024,
    accept: acceptedTypes
      ? acceptedTypes.reduce((acc, type) => ({ ...acc, [type]: [] }), {})
      : undefined,
  })

  const handleFileInputClick = () => {
    fileInputRef.current?.click()
  }

  const handleFileInputChange = (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    const files = Array.from(event.target.files || [])
    processFiles(files)
  }

  const downloadFile = (file: UploadedFile) => {
    const url = URL.createObjectURL(file)
    const a = document.createElement('a')
    a.href = url
    a.download = file.name
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className={cn('space-y-6', className)}>
      {/* Drop Zone */}
      <Card
        {...getRootProps()}
        className={cn(
          'border-2 border-dashed cursor-pointer transition-all duration-300',
          isDragActive || dragActive
            ? 'border-matrix-green bg-matrix-green/5 scale-[1.02]'
            : 'border-border hover:border-matrix-green/50 hover:bg-matrix-green/5',
          disabled && 'opacity-50 cursor-not-allowed'
        )}
      >
        <input {...getInputProps()} />
        <input
          ref={fileInputRef}
          type="file"
          multiple={multiple}
          onChange={handleFileInputChange}
          className="hidden"
          accept={acceptedTypes?.join(',')}
        />

        <CardContent className="py-12">
          <div className="text-center">
            <div className="relative">
              <Upload
                className={cn(
                  'h-16 w-16 mx-auto mb-4 transition-all duration-300',
                  isDragActive || dragActive
                    ? 'text-matrix-green scale-110'
                    : 'text-gray-400'
                )}
              />
              {isDragActive && (
                <div className="absolute inset-0 animate-ping">
                  <Upload className="h-16 w-16 mx-auto text-matrix-green/50" />
                </div>
              )}
            </div>

            {isDragActive ? (
              <div>
                <p className="text-xl font-semibold text-matrix-green mb-2">
                  Drop files here!
                </p>
                <p className="text-gray-400">Release to upload your files</p>
              </div>
            ) : (
              <div>
                <p className="text-xl font-semibold text-white mb-2">
                  {selectedFiles.length > 0
                    ? 'Add more files'
                    : 'Upload your code files'}
                </p>
                <p className="text-gray-400 mb-4">
                  Drag & drop files here, or{' '}
                  <button
                    type="button"
                    onClick={handleFileInputClick}
                    className="text-matrix-green hover:text-matrix-cyan underline"
                  >
                    browse files
                  </button>
                </p>

                <div className="flex flex-wrap items-center justify-center gap-2 text-xs text-gray-500">
                  <span>
                    Supports: JS, TS, Python, Java, C#, PHP, Ruby, Go, Rust, and
                    more
                  </span>
                  <span>•</span>
                  <span>Max {maxFiles} files</span>
                  <span>•</span>
                  <span>Up to {maxSize}MB each</span>
                </div>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Selected Files */}
      {selectedFiles.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FolderOpen className="h-5 w-5 text-matrix-green" />
              Selected Files ({selectedFiles.length}/{maxFiles})
            </CardTitle>
          </CardHeader>

          <CardContent>
            <div className="space-y-3">
              {selectedFiles.map(file => (
                <FileItem
                  key={file.id}
                  file={file}
                  onRemove={() => onRemoveFile(file.id)}
                  onDownload={() => downloadFile(file)}
                  showPreview={showPreview}
                />
              ))}
            </div>

            {selectedFiles.length > 0 && (
              <div className="mt-6 pt-4 border-t border-border">
                <div className="flex items-center justify-between text-sm text-gray-400">
                  <span>
                    Total: {selectedFiles.length} files (
                    {formatFileSize(
                      selectedFiles.reduce((sum, file) => sum + file.size, 0)
                    )}
                    )
                  </span>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() =>
                        selectedFiles.forEach(file => onRemoveFile(file.id))
                      }
                    >
                      <Trash2 className="h-4 w-4 mr-2" />
                      Clear All
                    </Button>
                  </div>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  )
}

// Individual File Item Component
interface FileItemProps {
  file: UploadedFile
  onRemove: () => void
  onDownload: () => void
  showPreview: boolean
}

function FileItem({ file, onRemove, onDownload, showPreview }: FileItemProps) {
  const fileInfo = getFileInfo(file)

  const getStatusIcon = () => {
    switch (file.status) {
      case 'success':
        return <CheckCircle2 className="h-4 w-4 text-green-500" />
      case 'error':
        return <AlertCircle className="h-4 w-4 text-red-500" />
      case 'uploading':
        return (
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-matrix-green border-t-transparent" />
        )
      default:
        return <FileText className={cn('h-4 w-4', fileInfo.color)} />
    }
  }

  return (
    <div className="flex items-center gap-3 p-3 rounded-lg bg-card-surface/30 border border-border hover:border-matrix-green/30 transition-all duration-200 group">
      {/* File Preview/Icon */}
      <div className="flex-shrink-0">
        {showPreview && file.preview ? (
          <img
            src={file.preview}
            alt={file.name}
            className="h-10 w-10 rounded object-cover"
          />
        ) : (
          <div className="h-10 w-10 rounded bg-card-surface flex items-center justify-center">
            {getStatusIcon()}
          </div>
        )}
      </div>

      {/* File Info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <p className="text-sm font-medium text-white truncate">{file.name}</p>
          <Badge variant="outline" size="sm">
            {fileInfo.label}
          </Badge>
        </div>

        <div className="flex items-center gap-4 text-xs text-gray-400">
          <span>{formatFileSize(file.size)}</span>
          {file.status === 'error' && file.error && (
            <span className="text-red-400">{file.error}</span>
          )}
        </div>

        {/* Progress bar for uploading files */}
        {file.status === 'uploading' && file.progress !== undefined && (
          <div className="mt-2">
            <div className="h-1 bg-gray-700 rounded-full overflow-hidden">
              <div
                className="h-full bg-matrix-green transition-all duration-300"
                style={{ width: `${file.progress}%` }}
              />
            </div>
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
        <Button variant="ghost" size="sm" onClick={onDownload}>
          <Download className="h-4 w-4" />
        </Button>
        <Button variant="ghost" size="sm" onClick={onRemove}>
          <X className="h-4 w-4" />
        </Button>
      </div>
    </div>
  )
}
