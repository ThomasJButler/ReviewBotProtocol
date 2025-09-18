import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'

import { cn } from '@/lib/utils'

const inputVariants = cva(
  [
    'flex w-full rounded-lg border bg-input px-3 py-2 text-sm text-white',
    'file:border-0 file:bg-transparent file:text-sm file:font-medium',
    'placeholder:text-muted-foreground/60',
    'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
    'focus-visible:ring-offset-deep-black',
    'disabled:cursor-not-allowed disabled:opacity-50',
    'transition-all duration-200 backdrop-blur-sm',
    'hover:border-matrix-green/40',
  ],
  {
    variants: {
      variant: {
        default: [
          'border-border bg-input/80',
          'focus-visible:border-matrix-green focus-visible:bg-input',
          'focus-visible:shadow-lg focus-visible:shadow-matrix-green/20',
        ],
        matrix: [
          'border-matrix-green/30 bg-deep-black/50',
          'focus-visible:border-matrix-green focus-visible:bg-deep-black/80',
          'focus-visible:shadow-lg focus-visible:shadow-matrix-green/30',
          'focus-visible:ring-matrix-green',
        ],
        ghost: [
          'border-transparent bg-transparent',
          'hover:bg-white/5 focus-visible:bg-white/10',
          'focus-visible:border-white/20',
        ],
        search: [
          'border-border bg-card-surface/50 pl-10',
          'focus-visible:border-matrix-green focus-visible:bg-card-surface/80',
        ],
      },
      inputSize: {
        sm: 'h-9 px-3 text-xs',
        md: 'h-11 px-3 text-sm',
        lg: 'h-13 px-4 text-base',
      },
    },
    defaultVariants: {
      variant: 'default',
      inputSize: 'md',
    },
  }
)

export interface InputProps
  extends React.InputHTMLAttributes<HTMLInputElement>,
    VariantProps<typeof inputVariants> {
  icon?: React.ReactNode
  rightIcon?: React.ReactNode
  error?: string
  success?: boolean
}

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  (
    {
      className,
      variant,
      inputSize,
      type,
      icon,
      rightIcon,
      error,
      success,
      ...props
    },
    ref
  ) => {
    const hasIcon = icon || rightIcon

    return (
      <div className="relative group">
        {icon && (
          <div className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground group-focus-within:text-matrix-green transition-colors z-10">
            {icon}
          </div>
        )}

        <input
          type={type}
          className={cn(
            inputVariants({ variant, inputSize }),
            {
              'pl-10': icon,
              'pr-10': rightIcon,
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

        {rightIcon && (
          <div className="absolute right-3 top-1/2 transform -translate-y-1/2 text-muted-foreground group-focus-within:text-matrix-green transition-colors">
            {rightIcon}
          </div>
        )}

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
Input.displayName = 'Input'

// Specialized input components
const SearchInput = React.forwardRef<
  HTMLInputElement,
  Omit<InputProps, 'variant'>
>(({ className, ...props }, ref) => (
  <Input ref={ref} variant="search" className={className} {...props} />
))
SearchInput.displayName = 'SearchInput'

const MatrixInput = React.forwardRef<
  HTMLInputElement,
  Omit<InputProps, 'variant'>
>(({ className, ...props }, ref) => (
  <Input ref={ref} variant="matrix" className={className} {...props} />
))
MatrixInput.displayName = 'MatrixInput'

export { Input, SearchInput, MatrixInput, inputVariants }
