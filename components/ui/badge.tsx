import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'

import { cn } from '@/lib/utils'

const badgeVariants = cva(
  'inline-flex items-center rounded-md border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2',
  {
    variants: {
      variant: {
        default:
          'border-transparent bg-primary text-primary-foreground shadow hover:bg-primary/80',
        secondary:
          'border-transparent bg-secondary text-secondary-foreground hover:bg-secondary/80',
        destructive:
          'border-transparent bg-destructive text-destructive-foreground shadow hover:bg-destructive/80',
        outline: 'text-foreground',
        // Security severity badges
        critical: [
          'border-transparent bg-gradient-to-r from-red-600 to-red-700 text-white',
          'shadow-lg shadow-red-500/30 animate-pulse',
        ],
        high: [
          'border-transparent bg-gradient-to-r from-red-500 to-red-600 text-white',
          'shadow-md shadow-red-500/20',
        ],
        medium: [
          'border-transparent bg-gradient-to-r from-yellow-500 to-orange-500 text-white',
          'shadow-md shadow-yellow-500/20',
        ],
        low: [
          'border-transparent bg-gradient-to-r from-blue-500 to-blue-600 text-white',
          'shadow-md shadow-blue-500/20',
        ],
        info: [
          'border-transparent bg-gradient-to-r from-gray-600 to-gray-700 text-white',
          'shadow-md shadow-gray-500/20',
        ],
        // Matrix theme badges
        matrix: [
          'border-matrix-green/50 bg-matrix-green/10 text-matrix-green',
          'hover:bg-matrix-green/20 hover:border-matrix-green',
          'shadow-sm shadow-matrix-green/10',
        ],
        cyber: [
          'border-matrix-cyan/50 bg-matrix-cyan/10 text-matrix-cyan',
          'hover:bg-matrix-cyan/20 hover:border-matrix-cyan',
          'shadow-sm shadow-matrix-cyan/10',
        ],
        // Status badges
        success: [
          'border-transparent bg-gradient-to-r from-green-500 to-green-600 text-white',
          'shadow-md shadow-green-500/20',
        ],
        warning: [
          'border-transparent bg-gradient-to-r from-yellow-500 to-yellow-600 text-white',
          'shadow-md shadow-yellow-500/20',
        ],
        error: [
          'border-transparent bg-gradient-to-r from-red-500 to-red-600 text-white',
          'shadow-md shadow-red-500/20',
        ],
      },
      size: {
        sm: 'px-2 py-0.5 text-xs',
        md: 'px-2.5 py-0.5 text-xs',
        lg: 'px-3 py-1 text-sm',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'md',
    },
  }
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {
  icon?: React.ReactNode
  pulse?: boolean
}

function Badge({
  className,
  variant,
  size,
  icon,
  pulse,
  children,
  ...props
}: BadgeProps) {
  return (
    <div
      className={cn(
        badgeVariants({ variant, size }),
        pulse && 'animate-pulse',
        className
      )}
      {...props}
    >
      {icon && <span className="mr-1">{icon}</span>}
      {children}
    </div>
  )
}

// Specialized badge components for security findings
const SecurityBadge = ({
  severity,
  ...props
}: Omit<BadgeProps, 'variant'> & {
  severity: 'critical' | 'high' | 'medium' | 'low' | 'info'
}) => <Badge variant={severity} {...props} />

const StatusBadge = ({
  status,
  ...props
}: Omit<BadgeProps, 'variant'> & {
  status: 'success' | 'warning' | 'error' | 'info'
}) => <Badge variant={status} {...props} />

export { Badge, SecurityBadge, StatusBadge, badgeVariants }
