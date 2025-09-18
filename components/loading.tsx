'use client'

import React from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

interface LoadingSpinnerProps {
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

export function LoadingSpinner({
  size = 'md',
  className,
}: LoadingSpinnerProps) {
  const sizeClasses = {
    sm: 'h-4 w-4',
    md: 'h-8 w-8',
    lg: 'h-12 w-12',
  }

  return (
    <div
      className={cn(
        'animate-spin rounded-full border-2 border-matrix-green border-t-transparent',
        sizeClasses[size],
        className
      )}
    />
  )
}

interface LoadingCardProps {
  title?: string
  description?: string
  className?: string
}

export function LoadingCard({
  title = 'Loading...',
  description,
  className,
}: LoadingCardProps) {
  return (
    <Card className={className}>
      <CardContent className="p-8">
        <div className="flex flex-col items-center justify-center space-y-4">
          <div className="relative">
            <LoadingSpinner size="lg" />
            <div className="absolute inset-0 rounded-full border-2 border-matrix-green/20"></div>
          </div>
          <div className="text-center">
            <p className="text-white font-medium">{title}</p>
            {description && (
              <p className="text-gray-400 text-sm mt-1">{description}</p>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

interface PageLoadingProps {
  message?: string
}

export function PageLoading({ message = 'Loading...' }: PageLoadingProps) {
  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-center space-y-4">
        <LoadingSpinner size="lg" />
        <p className="text-white text-lg">{message}</p>
      </div>
    </div>
  )
}

interface CodeAnalysisLoadingProps {
  stage?: string
  progress?: number
}

export function CodeAnalysisLoading({
  stage = 'Analyzing code...',
  progress,
}: CodeAnalysisLoadingProps) {
  return (
    <Card>
      <CardContent className="p-8">
        <div className="flex flex-col items-center justify-center space-y-6">
          <div className="relative">
            <LoadingSpinner size="lg" />
            <div className="absolute inset-0 rounded-full border-2 border-matrix-green/20"></div>
          </div>

          <div className="text-center space-y-2">
            <p className="text-white font-medium text-lg">{stage}</p>
            <p className="text-gray-400 text-sm">This may take a few moments</p>
          </div>

          {progress !== undefined && (
            <div className="w-full max-w-xs">
              <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-matrix-green to-green-600 transition-all duration-300"
                  style={{ width: `${progress}%` }}
                />
              </div>
              <p className="text-xs text-gray-400 mt-2 text-center">
                {progress}% complete
              </p>
            </div>
          )}

          <div className="flex items-center gap-4 text-xs text-gray-400">
            <div className="flex items-center gap-1">
              <div className="h-2 w-2 bg-matrix-green rounded-full animate-pulse"></div>
              Security Analysis
            </div>
            <div className="flex items-center gap-1">
              <div className="h-2 w-2 bg-yellow-500 rounded-full animate-pulse"></div>
              Performance Review
            </div>
            <div className="flex items-center gap-1">
              <div className="h-2 w-2 bg-blue-500 rounded-full animate-pulse"></div>
              Code Quality
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

interface ContentLoadingProps {
  lines?: number
  showAvatar?: boolean
  className?: string
}

export function ContentLoading({
  lines = 3,
  showAvatar = false,
  className,
}: ContentLoadingProps) {
  return (
    <div className={cn('space-y-3', className)}>
      {showAvatar && (
        <div className="flex items-start gap-3">
          <Skeleton className="h-10 w-10 rounded-full" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-4 w-32" />
            <Skeleton className="h-3 w-24" />
          </div>
        </div>
      )}

      {Array.from({ length: lines }).map((_, i) => (
        <div key={i} className="space-y-2">
          <Skeleton className="h-4 w-full" />
          {i === lines - 1 && <Skeleton className="h-4 w-3/4" />}
        </div>
      ))}
    </div>
  )
}

interface ListLoadingProps {
  items?: number
  className?: string
}

export function ListLoading({ items = 3, className }: ListLoadingProps) {
  return (
    <div className={cn('space-y-4', className)}>
      {Array.from({ length: items }).map((_, i) => (
        <Card key={i}>
          <CardContent className="p-4">
            <div className="flex items-start gap-3">
              <Skeleton className="h-10 w-10 rounded-lg" />
              <div className="flex-1 space-y-2">
                <Skeleton className="h-5 w-3/4" />
                <Skeleton className="h-4 w-1/2" />
                <div className="flex gap-2 mt-3">
                  <Skeleton className="h-6 w-16" />
                  <Skeleton className="h-6 w-20" />
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}

export default LoadingSpinner
