import * as React from 'react'
import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'

import { cn } from '@/lib/utils'

const buttonVariants = cva(
  'inline-flex items-center justify-center whitespace-nowrap rounded-lg text-sm font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-matrix-green focus-visible:ring-offset-2 focus-visible:ring-offset-deep-black disabled:pointer-events-none disabled:opacity-50 relative overflow-hidden group',
  {
    variants: {
      variant: {
        primary: [
          'bg-gradient-to-br from-matrix-green to-green-600 text-deep-black font-semibold',
          'hover:from-green-600 hover:to-green-700 hover:shadow-lg hover:shadow-matrix-green/30',
          'active:scale-[0.98] active:shadow-matrix-green/50',
          'before:absolute before:inset-0 before:bg-gradient-to-r before:from-transparent before:via-white/20 before:to-transparent',
          'before:translate-x-[-100%] hover:before:translate-x-[100%] before:transition-transform before:duration-700',
        ],
        secondary: [
          'border-2 border-matrix-green/60 text-matrix-green bg-transparent backdrop-blur-sm',
          'hover:bg-matrix-green/10 hover:border-matrix-green hover:text-matrix-green',
          'hover:shadow-md hover:shadow-matrix-green/20 hover:-translate-y-0.5',
          'active:translate-y-0 active:shadow-matrix-green/40',
        ],
        ghost: [
          'text-white/80 bg-transparent hover:bg-white/10',
          'hover:text-white hover:backdrop-blur-sm',
          'active:bg-white/20',
        ],
        destructive: [
          'bg-gradient-to-br from-red-500 to-red-600 text-white',
          'hover:from-red-600 hover:to-red-700 hover:shadow-lg hover:shadow-red-500/30',
          'active:scale-[0.98]',
        ],
        outline: [
          'border border-border bg-transparent text-white',
          'hover:bg-white/5 hover:border-white/20',
          'active:bg-white/10',
        ],
      },
      size: {
        sm: 'h-9 px-3 text-xs',
        md: 'h-11 px-6 text-sm',
        lg: 'h-13 px-8 text-base',
        xl: 'h-16 px-12 text-lg',
        icon: 'h-11 w-11',
      },
    },
    defaultVariants: {
      variant: 'primary',
      size: 'md',
    },
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
  loading?: boolean
  icon?: React.ReactNode
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className,
      variant,
      size,
      asChild = false,
      loading = false,
      icon,
      children,
      disabled,
      ...props
    },
    ref
  ) => {
    const Comp = asChild ? Slot : 'button'

    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        disabled={disabled || loading}
        {...props}
      >
        {loading && (
          <div className="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
        )}
        {icon && !loading && <span className="mr-2">{icon}</span>}
        {children}
      </Comp>
    )
  }
)
Button.displayName = 'Button'

export { Button, buttonVariants }
