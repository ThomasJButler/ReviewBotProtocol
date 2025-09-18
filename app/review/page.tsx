'use client'

import React from 'react'
import { ReviewInterface } from '@/components/review'
import ErrorBoundary from '@/components/error-boundary'

export default function ReviewPage() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-deep-black via-gray-900 to-deep-black">
      <div className="container mx-auto px-4 py-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-white mb-2">AI Code Review</h1>
          <p className="text-gray-400">
            Get instant AI-powered security, performance, and quality analysis
            for your code
          </p>
        </div>

        {/* Review Interface */}
        <ErrorBoundary>
          <ReviewInterface
            maxFiles={10}
            maxFileSize={50}
            onReviewComplete={results => {
              console.log('Review completed:', results)
            }}
          />
        </ErrorBoundary>
      </div>
    </div>
  )
}
