import * as React from 'react'

import { cn } from '@/lib/utils'

export interface TextareaProps
  extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  error?: string
  success?: boolean
  resizable?: boolean
}

const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, error, success, resizable = true, ...props }, ref) => {
    return (
      <div className="relative group">
        <textarea
          className={cn(
            [
              'flex min-h-[120px] w-full rounded-lg border border-border bg-input/80 px-3 py-2',
              'text-sm text-white placeholder:text-muted-foreground/60',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-matrix-green',
              'focus-visible:ring-offset-2 focus-visible:ring-offset-deep-black',
              'focus-visible:border-matrix-green focus-visible:bg-input',
              'focus-visible:shadow-lg focus-visible:shadow-matrix-green/20',
              'disabled:cursor-not-allowed disabled:opacity-50',
              'transition-all duration-200 backdrop-blur-sm',
              'hover:border-matrix-green/40',
              !resizable && 'resize-none',
            ],
            {
              'border-red-500 focus-visible:border-red-500 focus-visible:ring-red-500':
                error,
              'border-green-500 focus-visible:border-green-500 focus-visible:ring-green-500':
                success,
            },
            className
          )}
          ref={ref}
          {...props}
        />

        {/* Error message */}
        {error && (
          <p className="mt-1 text-xs text-red-400 animate-fade-in">{error}</p>
        )}

        {/* Focus glow effect */}
        <div className="absolute inset-0 rounded-lg bg-matrix-green/5 opacity-0 group-focus-within:opacity-100 transition-opacity duration-200 pointer-events-none" />
      </div>
    )
  }
)
Textarea.displayName = 'Textarea'

// Code textarea variant for code input
const CodeTextarea = React.forwardRef<
  HTMLTextAreaElement,
  Omit<TextareaProps, 'className'>
>(({ ...props }, ref) => (
  <Textarea
    ref={ref}
    className="font-mono text-sm bg-deep-black/80 border-matrix-green/30 focus-visible:bg-deep-black/90"
    {...props}
  />
))
CodeTextarea.displayName = 'CodeTextarea'

export { Textarea, CodeTextarea }
