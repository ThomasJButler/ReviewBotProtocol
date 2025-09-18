import * as React from 'react'

import { cn } from '@/lib/utils'

const Card = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn(
      [
        'rounded-2xl border border-border bg-card text-card-foreground shadow-xl',
        'glass-effect backdrop-blur-md transition-all duration-300',
        'hover:border-matrix-green/30 hover:shadow-2xl hover:shadow-matrix-green/10',
        'hover:-translate-y-1 group',
      ],
      className
    )}
    {...props}
  />
))
Card.displayName = 'Card'

const CardHeader = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn(
      'flex flex-col space-y-1.5 p-6 pb-4 relative',
      'before:absolute before:bottom-0 before:left-6 before:right-6',
      'before:h-px before:bg-gradient-to-r before:from-transparent before:via-border before:to-transparent',
      'group-hover:before:via-matrix-green/30',
      className
    )}
    {...props}
  />
))
CardHeader.displayName = 'CardHeader'

const CardTitle = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLHeadingElement>
>(({ className, ...props }, ref) => (
  <h3
    ref={ref}
    className={cn(
      'text-2xl font-semibold leading-none tracking-tight text-white',
      'group-hover:text-matrix-green transition-colors duration-300',
      className
    )}
    {...props}
  />
))
CardTitle.displayName = 'CardTitle'

const CardDescription = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLParagraphElement>
>(({ className, ...props }, ref) => (
  <p
    ref={ref}
    className={cn('text-sm text-muted-foreground leading-relaxed', className)}
    {...props}
  />
))
CardDescription.displayName = 'CardDescription'

const CardContent = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div ref={ref} className={cn('p-6 pt-4', className)} {...props} />
))
CardContent.displayName = 'CardContent'

const CardFooter = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn(
      'flex items-center p-6 pt-0 relative',
      'before:absolute before:top-0 before:left-6 before:right-6',
      'before:h-px before:bg-gradient-to-r before:from-transparent before:via-border before:to-transparent',
      'group-hover:before:via-matrix-green/30',
      className
    )}
    {...props}
  />
))
CardFooter.displayName = 'CardFooter'

// Specialized card variants for specific use cases
const GlowCard = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement> & { glowColor?: string }
>(({ className, glowColor = 'matrix-green', ...props }, ref) => (
  <Card
    ref={ref}
    className={cn(
      'relative overflow-hidden',
      'before:absolute before:inset-0 before:rounded-2xl before:p-[1px]',
      `before:bg-gradient-to-br before:from-${glowColor}/50 before:to-transparent`,
      'before:mask-composite:exclude before:[mask:linear-gradient(#fff_0_0)_content-box,linear-gradient(#fff_0_0)]',
      className
    )}
    {...props}
  />
))
GlowCard.displayName = 'GlowCard'

const MatrixCard = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <Card
    ref={ref}
    className={cn(
      'relative border-matrix-green/20 bg-gradient-to-br from-card-surface/80 to-deep-black/90',
      'shadow-lg shadow-matrix-green/10',
      'hover:shadow-matrix-green/20 hover:border-matrix-green/40',
      'before:absolute before:inset-0 before:rounded-2xl before:bg-gradient-to-r',
      'before:from-matrix-green/5 before:via-transparent before:to-matrix-green/5',
      'before:opacity-0 hover:before:opacity-100 before:transition-opacity before:duration-500',
      className
    )}
    {...props}
  />
))
MatrixCard.displayName = 'MatrixCard'

export {
  Card,
  CardHeader,
  CardFooter,
  CardTitle,
  CardDescription,
  CardContent,
  GlowCard,
  MatrixCard,
}
