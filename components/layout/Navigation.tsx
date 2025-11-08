'use client'

import React from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { Button } from '@/components/ui/button'
import {
  Bot,
  BarChart3,
  Code2,
  GitPullRequest,
  FileText,
  Github,
  User,
  Settings,
  LogOut,
  Clock,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useAuth } from '@/contexts/AuthContext'

const navigation = [
  {
    name: 'Dashboard',
    href: '/dashboard',
    icon: BarChart3,
    description: 'Overview and analytics',
  },
  {
    name: 'Review Code',
    href: '/review',
    icon: Code2,
    description: 'AI-powered code analysis',
  },
  {
    name: 'History',
    href: '/history',
    icon: Clock,
    description: 'Review history',
  },
  {
    name: 'Pull Requests',
    href: '/pull-requests',
    icon: GitPullRequest,
    description: 'GitHub PR management',
  },
]

export default function Navigation() {
  const pathname = usePathname()
  const { user, isAuthenticated, login, logout } = useAuth()

  return (
    <header className="sticky top-0 z-50 bg-deep-black/80 backdrop-blur-lg border-b border-gray-800">
      <div className="container mx-auto px-4">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <Link
            href="/"
            className="flex items-center gap-3 hover:opacity-80 transition-opacity"
          >
            <div className="relative">
              <Bot className="h-8 w-8 text-matrix-green" />
              <div className="absolute -top-1 -right-1 h-3 w-3 bg-matrix-green rounded-full animate-pulse"></div>
            </div>
            <div>
              <h1 className="text-xl font-bold text-white">
                ReviewBot Protocol
              </h1>
              <p className="text-xs text-gray-400">AI-Powered Code Analysis</p>
            </div>
          </Link>

          {/* Navigation */}
          <nav className="hidden md:flex items-center gap-2">
            {navigation.map(item => {
              const isActive = pathname === item.href
              const Icon = item.icon

              return (
                <Link key={item.name} href={item.href}>
                  <Button
                    variant={isActive ? 'secondary' : 'ghost'}
                    className={cn(
                      'flex items-center gap-2 px-4 py-2 rounded-lg transition-all duration-200',
                      isActive
                        ? 'bg-matrix-green/20 text-matrix-green border border-matrix-green/30 shadow-lg shadow-matrix-green/20'
                        : 'text-gray-300 hover:text-white hover:bg-white/5'
                    )}
                  >
                    <Icon className="h-4 w-4" />
                    {item.name}
                  </Button>
                </Link>
              )
            })}
          </nav>

          {/* User Actions */}
          <div className="flex items-center gap-3">
            {isAuthenticated ? (
              <>
                <div className="flex items-center gap-2 px-3 py-1 rounded-lg bg-matrix-green/10 border border-matrix-green/20">
                  <img
                    src={user?.avatar_url}
                    alt={user?.name || user?.login}
                    className="h-6 w-6 rounded-full"
                  />
                  <span className="text-sm text-white">
                    {user?.name || user?.login}
                  </span>
                </div>

                <Button
                  variant="ghost"
                  size="icon"
                  className="text-gray-400 hover:text-white"
                >
                  <Settings className="h-4 w-4" />
                </Button>

                <Button
                  variant="ghost"
                  size="icon"
                  onClick={logout}
                  className="text-gray-400 hover:text-red-400"
                >
                  <LogOut className="h-4 w-4" />
                </Button>
              </>
            ) : (
              <Button
                variant="ghost"
                size="sm"
                onClick={login}
                className="text-gray-400 hover:text-white"
              >
                <Github className="h-4 w-4 mr-2" />
                Connect GitHub
              </Button>
            )}
          </div>
        </div>

        {/* Mobile Navigation */}
        <div className="md:hidden py-4 border-t border-gray-800">
          <div className="grid grid-cols-2 gap-2">
            {navigation.map(item => {
              const isActive = pathname === item.href
              const Icon = item.icon

              return (
                <Link key={item.name} href={item.href}>
                  <Button
                    variant={isActive ? 'secondary' : 'ghost'}
                    className={cn(
                      'w-full flex items-center gap-2 justify-start px-3 py-2 rounded-lg',
                      isActive
                        ? 'bg-matrix-green/20 text-matrix-green border border-matrix-green/30'
                        : 'text-gray-300 hover:text-white hover:bg-white/5'
                    )}
                  >
                    <Icon className="h-4 w-4" />
                    {item.name}
                  </Button>
                </Link>
              )
            })}
          </div>
        </div>
      </div>
    </header>
  )
}
