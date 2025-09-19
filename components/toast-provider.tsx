'use client'

import { Toaster } from 'react-hot-toast'

export function ToastProvider() {
  return (
    <Toaster
      position="top-right"
      reverseOrder={false}
      gutter={8}
      containerClassName=""
      containerStyle={{}}
      toastOptions={{
        // Default options
        duration: 4000,
        style: {
          background: '#1a1a1a',
          color: '#ffffff',
          border: '1px solid rgba(255, 255, 255, 0.1)',
          borderRadius: '12px',
          boxShadow:
            '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
          backdropFilter: 'blur(16px)',
        },

        // Success toasts
        success: {
          duration: 3000,
          style: {
            background: 'rgba(16, 185, 129, 0.1)',
            border: '1px solid rgba(16, 185, 129, 0.3)',
            color: '#10B981',
          },
          iconTheme: {
            primary: '#10B981',
            secondary: '#1a1a1a',
          },
        },

        // Error toasts
        error: {
          duration: 5000,
          style: {
            background: 'rgba(239, 68, 68, 0.1)',
            border: '1px solid rgba(239, 68, 68, 0.3)',
            color: '#EF4444',
          },
          iconTheme: {
            primary: '#EF4444',
            secondary: '#1a1a1a',
          },
        },

        // Loading toasts
        loading: {
          style: {
            background: 'rgba(59, 130, 246, 0.1)',
            border: '1px solid rgba(59, 130, 246, 0.3)',
            color: '#3B82F6',
          },
          iconTheme: {
            primary: '#3B82F6',
            secondary: '#1a1a1a',
          },
        },
      }}
    />
  )
}
