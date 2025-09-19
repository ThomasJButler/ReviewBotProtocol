'use client'

import React, { useState, useEffect } from 'react'
import Link from 'next/link'
import { useRouter, usePathname } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import {
  Github,
  Bot,
  Zap,
  Shield,
  Settings,
  User,
  LogOut,
  Menu,
  X,
  Bell,
  Search,
  ChevronDown,
  ExternalLink,
  Sparkles,
  Code2,
  FileText,
  Activity,
} from 'lucide-react'
import { cn } from '@/lib/utils'

interface User {
  id: string
  login: string
  name: string
  email: string
  avatarUrl: string
  githubUrl: string
  isConnected: boolean
}

interface HeaderProps {
  user?: User | null
  onSignIn?: () => void
  onSignOut?: () => void
  className?: string
}

export default function Header({
  user,
  onSignIn,
  onSignOut,
  className,
}: HeaderProps) {
  const [isMenuOpen, setIsMenuOpen] = useState(false)
  const [isUserMenuOpen, setIsUserMenuOpen] = useState(false)
  const [notifications, setNotifications] = useState(3) // Mock notification count
  const pathname = usePathname()
  const router = useRouter()

  // Navigation items
  const navigation = [
    { name: 'Dashboard', href: '/', icon: Activity, current: pathname === '/' },
    {
      name: 'Review Code',
      href: '/review',
      icon: Code2,
      current: pathname === '/review',
    },
    {
      name: 'Pull Requests',
      href: '/pull-requests',
      icon: Github,
      current: pathname === '/pull-requests',
    },
    {
      name: 'Reports',
      href: '/reports',
      icon: FileText,
      current: pathname === '/reports',
    },
  ]

  // Close mobile menu when route changes
  useEffect(() => {
    setIsMenuOpen(false)
  }, [pathname])

  const handleGitHubConnect = () => {
    if (user?.isConnected) {
      // Already connected, show user menu or go to settings
      setIsUserMenuOpen(!isUserMenuOpen)
    } else {
      // Trigger GitHub OAuth
      onSignIn?.()
    }
  }

  return (
    <>
      <header
        className={cn(
          'sticky top-0 z-50 w-full border-b border-border bg-deep-black/90 backdrop-blur-lg supports-[backdrop-filter]:bg-deep-black/60',
          className
        )}
      >
        <div className="container mx-auto flex h-16 items-center justify-between px-4">
          {/* Logo */}
          <div className="flex items-center gap-4">
            <Link href="/" className="flex items-center gap-3 group">
              <div className="relative">
                <Bot className="h-8 w-8 text-matrix-green transition-transform group-hover:scale-110" />
                <div className="absolute -top-1 -right-1 h-3 w-3 bg-matrix-green rounded-full animate-pulse"></div>
              </div>
              <div className="hidden sm:block">
                <h1 className="text-xl font-bold text-white group-hover:text-matrix-green transition-colors">
                  AI Code Review
                </h1>
                <p className="text-xs text-gray-400 -mt-1">Powered by AI</p>
              </div>
            </Link>

            {/* Desktop Navigation */}
            <nav className="hidden lg:flex items-center gap-1 ml-8">
              {navigation.map(item => {
                const Icon = item.icon
                return (
                  <Link
                    key={item.name}
                    href={item.href}
                    className={cn(
                      'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200',
                      item.current
                        ? 'bg-matrix-green/10 text-matrix-green border border-matrix-green/30'
                        : 'text-gray-300 hover:text-white hover:bg-white/5'
                    )}
                  >
                    <Icon className="h-4 w-4" />
                    {item.name}
                  </Link>
                )
              })}
            </nav>
          </div>

          {/* Right side */}
          <div className="flex items-center gap-3">
            {/* Search - Desktop only */}
            <Button variant="ghost" size="sm" className="hidden md:flex">
              <Search className="h-4 w-4 mr-2" />
              Search
              <Badge variant="outline" size="sm" className="ml-2">
                ⌘K
              </Badge>
            </Button>

            {/* Notifications */}
            <div className="relative">
              <Button variant="ghost" size="sm">
                <Bell className="h-4 w-4" />
                {notifications > 0 && (
                  <Badge
                    variant="destructive"
                    size="sm"
                    className="absolute -top-1 -right-1 h-5 w-5 p-0 flex items-center justify-center text-xs"
                  >
                    {notifications}
                  </Badge>
                )}
              </Button>
            </div>

            {/* GitHub Connection / User Menu */}
            {user?.isConnected ? (
              <div className="relative">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setIsUserMenuOpen(!isUserMenuOpen)}
                  className="flex items-center gap-2"
                >
                  <img
                    src={user.avatarUrl}
                    alt={user.login}
                    className="h-6 w-6 rounded-full"
                  />
                  <span className="hidden sm:inline text-white">
                    {user.login}
                  </span>
                  <ChevronDown className="h-4 w-4" />
                </Button>

                {/* User Dropdown Menu */}
                {isUserMenuOpen && (
                  <div className="absolute right-0 top-full mt-2 w-64 bg-card-surface border border-border rounded-lg shadow-2xl z-50 animate-fade-in">
                    <div className="p-4 border-b border-border">
                      <div className="flex items-center gap-3">
                        <img
                          src={user.avatarUrl}
                          alt={user.login}
                          className="h-10 w-10 rounded-full"
                        />
                        <div>
                          <p className="font-medium text-white">
                            {user.name || user.login}
                          </p>
                          <p className="text-sm text-gray-400">{user.email}</p>
                        </div>
                      </div>
                    </div>

                    <div className="p-2">
                      <Link
                        href="/settings"
                        className="flex items-center gap-2 px-3 py-2 rounded-md text-sm text-gray-300 hover:text-white hover:bg-white/5 transition-colors"
                        onClick={() => setIsUserMenuOpen(false)}
                      >
                        <Settings className="h-4 w-4" />
                        Settings
                      </Link>

                      <a
                        href={user.githubUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-2 px-3 py-2 rounded-md text-sm text-gray-300 hover:text-white hover:bg-white/5 transition-colors"
                      >
                        <Github className="h-4 w-4" />
                        GitHub Profile
                        <ExternalLink className="h-3 w-3 ml-auto" />
                      </a>

                      <div className="border-t border-border my-2"></div>

                      <button
                        onClick={() => {
                          setIsUserMenuOpen(false)
                          onSignOut?.()
                        }}
                        className="flex items-center gap-2 px-3 py-2 rounded-md text-sm text-red-400 hover:text-red-300 hover:bg-red-500/10 transition-colors w-full text-left"
                      >
                        <LogOut className="h-4 w-4" />
                        Sign Out
                      </button>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <Button
                onClick={handleGitHubConnect}
                className="flex items-center gap-2"
              >
                <Github className="h-4 w-4" />
                <span className="hidden sm:inline">Connect GitHub</span>
              </Button>
            )}

            {/* Mobile menu button */}
            <Button
              variant="ghost"
              size="sm"
              className="lg:hidden"
              onClick={() => setIsMenuOpen(!isMenuOpen)}
            >
              {isMenuOpen ? (
                <X className="h-5 w-5" />
              ) : (
                <Menu className="h-5 w-5" />
              )}
            </Button>
          </div>
        </div>

        {/* Mobile Navigation */}
        {isMenuOpen && (
          <div className="lg:hidden border-t border-border bg-deep-black/95 backdrop-blur-lg animate-fade-in">
            <div className="container mx-auto px-4 py-4">
              <nav className="flex flex-col gap-2">
                {navigation.map(item => {
                  const Icon = item.icon
                  return (
                    <Link
                      key={item.name}
                      href={item.href}
                      className={cn(
                        'flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-all duration-200',
                        item.current
                          ? 'bg-matrix-green/10 text-matrix-green border border-matrix-green/30'
                          : 'text-gray-300 hover:text-white hover:bg-white/5'
                      )}
                      onClick={() => setIsMenuOpen(false)}
                    >
                      <Icon className="h-5 w-5" />
                      {item.name}
                    </Link>
                  )
                })}

                {/* Mobile-only items */}
                <div className="border-t border-border mt-4 pt-4">
                  <Link
                    href="/search"
                    className="flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium text-gray-300 hover:text-white hover:bg-white/5 transition-all duration-200"
                    onClick={() => setIsMenuOpen(false)}
                  >
                    <Search className="h-5 w-5" />
                    Search
                  </Link>
                </div>
              </nav>
            </div>
          </div>
        )}
      </header>

      {/* Click outside to close user menu */}
      {isUserMenuOpen && (
        <div
          className="fixed inset-0 z-40"
          onClick={() => setIsUserMenuOpen(false)}
        />
      )}
    </>
  )
}

// Status Indicator Component
interface StatusIndicatorProps {
  online?: boolean
  analyzing?: boolean
}

export function StatusIndicator({
  online = true,
  analyzing = false,
}: StatusIndicatorProps) {
  return (
    <div className="flex items-center gap-2">
      <div
        className={cn(
          'h-2 w-2 rounded-full',
          analyzing
            ? 'bg-yellow-500 animate-pulse'
            : online
              ? 'bg-green-500'
              : 'bg-red-500'
        )}
      />
      <span className="text-xs text-gray-400">
        {analyzing ? 'Analyzing...' : online ? 'Online' : 'Offline'}
      </span>
    </div>
  )
}

// Quick Stats Component for Header
interface QuickStatsProps {
  stats: {
    reviewsToday: number
    issuesFound: number
    codeQuality: number
  }
}

export function QuickStats({ stats }: QuickStatsProps) {
  return (
    <div className="hidden xl:flex items-center gap-6 text-sm">
      <div className="flex items-center gap-2">
        <Zap className="h-4 w-4 text-yellow-500" />
        <span className="text-gray-400">
          {stats.reviewsToday} reviews today
        </span>
      </div>
      <div className="flex items-center gap-2">
        <Shield className="h-4 w-4 text-red-500" />
        <span className="text-gray-400">{stats.issuesFound} issues found</span>
      </div>
      <div className="flex items-center gap-2">
        <Sparkles className="h-4 w-4 text-matrix-green" />
        <span className="text-gray-400">
          {stats.codeQuality}% quality score
        </span>
      </div>
    </div>
  )
}
