'use client'

import * as React from 'react'
import * as TabsPrimitive from '@radix-ui/react-tabs'

import { cn } from '@/lib/utils'

const Tabs = TabsPrimitive.Root

const TabsList = React.forwardRef<
  React.ElementRef<typeof TabsPrimitive.List>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.List>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.List
    ref={ref}
    className={cn(
      [
        'inline-flex h-12 items-center justify-center rounded-xl bg-card-surface/50 p-1',
        'text-muted-foreground backdrop-blur-sm border border-border',
        'hover:bg-card-surface/70 transition-all duration-200',
      ],
      className
    )}
    {...props}
  />
))
TabsList.displayName = TabsPrimitive.List.displayName

const TabsTrigger = React.forwardRef<
  React.ElementRef<typeof TabsPrimitive.Trigger>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.Trigger>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.Trigger
    ref={ref}
    className={cn(
      [
        'inline-flex items-center justify-center whitespace-nowrap rounded-lg px-4 py-2',
        'text-sm font-medium ring-offset-background transition-all duration-200',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
        'disabled:pointer-events-none disabled:opacity-50',
        'data-[state=active]:bg-matrix-green data-[state=active]:text-deep-black data-[state=active]:shadow-lg',
        'data-[state=active]:shadow-matrix-green/30 data-[state=active]:font-semibold',
        'hover:bg-white/5 hover:text-white data-[state=active]:hover:bg-matrix-green',
        'relative overflow-hidden group',
      ],
      className
    )}
    {...props}
  >
    {/* Active state glow effect */}
    <div className="absolute inset-0 bg-gradient-to-r from-matrix-green/20 via-matrix-green/30 to-matrix-green/20 opacity-0 group-data-[state=active]:opacity-100 transition-opacity duration-300" />
    <span className="relative z-10">{props.children}</span>
  </TabsPrimitive.Trigger>
))
TabsTrigger.displayName = TabsPrimitive.Trigger.displayName

const TabsContent = React.forwardRef<
  React.ElementRef<typeof TabsPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.Content>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.Content
    ref={ref}
    className={cn(
      [
        'mt-6 ring-offset-background',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
        'animate-fade-in',
      ],
      className
    )}
    {...props}
  />
))
TabsContent.displayName = TabsPrimitive.Content.displayName

// Specialized tab variants
const MatrixTabs = React.forwardRef<
  React.ElementRef<typeof TabsPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.Root>
>(({ className, ...props }, ref) => (
  <Tabs ref={ref} className={cn('w-full', className)} {...props} />
))
MatrixTabs.displayName = 'MatrixTabs'

const MatrixTabsList = React.forwardRef<
  React.ElementRef<typeof TabsPrimitive.List>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.List>
>(({ className, ...props }, ref) => (
  <TabsList
    ref={ref}
    className={cn(
      [
        'bg-gradient-to-r from-card-surface/60 to-card-surface/80',
        'border-matrix-green/20 shadow-lg shadow-matrix-green/10',
      ],
      className
    )}
    {...props}
  />
))
MatrixTabsList.displayName = 'MatrixTabsList'

const MatrixTabsTrigger = React.forwardRef<
  React.ElementRef<typeof TabsPrimitive.Trigger>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.Trigger>
>(({ className, ...props }, ref) => (
  <TabsTrigger
    ref={ref}
    className={cn(
      [
        'data-[state=active]:bg-gradient-to-r data-[state=active]:from-matrix-green data-[state=active]:to-green-600',
        'data-[state=active]:shadow-matrix-green/40',
      ],
      className
    )}
    {...props}
  />
))
MatrixTabsTrigger.displayName = 'MatrixTabsTrigger'

export {
  Tabs,
  TabsList,
  TabsTrigger,
  TabsContent,
  MatrixTabs,
  MatrixTabsList,
  MatrixTabsTrigger,
}
