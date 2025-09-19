'use client'

import React from 'react'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Github,
  Twitter,
  Linkedin,
  Mail,
  ExternalLink,
  Zap,
  Shield,
  Bot,
  Sparkles,
  Heart,
  Code2,
  Globe,
  Book,
  MessageCircle,
  Coffee,
  Star,
} from 'lucide-react'
import { cn } from '@/lib/utils'

interface FooterProps {
  className?: string
  minimal?: boolean
}

export default function Footer({ className, minimal = false }: FooterProps) {
  const currentYear = new Date().getFullYear()

  const footerLinks = {
    product: [
      { name: 'Features', href: '/features' },
      { name: 'Pricing', href: '/pricing' },
      { name: 'Security', href: '/security' },
      { name: 'Integrations', href: '/integrations' },
      { name: 'API', href: '/api' },
    ],
    resources: [
      { name: 'Documentation', href: '/docs', icon: Book },
      { name: 'Tutorials', href: '/tutorials' },
      { name: 'Blog', href: '/blog' },
      { name: 'Changelog', href: '/changelog' },
      { name: 'Status', href: 'https://status.example.com', external: true },
    ],
    company: [
      { name: 'About', href: '/about' },
      { name: 'Careers', href: '/careers' },
      { name: 'Contact', href: '/contact', icon: Mail },
      { name: 'Support', href: '/support', icon: MessageCircle },
      { name: 'Privacy', href: '/privacy' },
      { name: 'Terms', href: '/terms' },
    ],
    developers: [
      {
        name: 'GitHub',
        href: 'https://github.com',
        icon: Github,
        external: true,
      },
      { name: 'API Docs', href: '/api-docs', icon: Code2 },
      { name: 'SDK', href: '/sdk' },
      { name: 'Webhooks', href: '/webhooks' },
      { name: 'Examples', href: '/examples' },
    ],
  }

  const socialLinks = [
    {
      name: 'GitHub',
      href: 'https://github.com',
      icon: Github,
      description: 'Star us on GitHub',
    },
    {
      name: 'Twitter',
      href: 'https://twitter.com',
      icon: Twitter,
      description: 'Follow for updates',
    },
    {
      name: 'LinkedIn',
      href: 'https://linkedin.com',
      icon: Linkedin,
      description: 'Connect with us',
    },
    {
      name: 'Email',
      href: 'mailto:hello@example.com',
      icon: Mail,
      description: 'Get in touch',
    },
  ]

  const stats = [
    { label: 'Reviews Generated', value: '10,000+', icon: Zap },
    { label: 'Security Issues Found', value: '5,000+', icon: Shield },
    { label: 'Developers Helped', value: '1,000+', icon: Bot },
    { label: 'Lines of Code Analyzed', value: '1M+', icon: Code2 },
  ]

  if (minimal) {
    return (
      <footer
        className={cn(
          'border-t border-border bg-deep-black/80 backdrop-blur-sm',
          className
        )}
      >
        <div className="container mx-auto px-4 py-6">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <Bot className="h-6 w-6 text-matrix-green" />
              <span className="text-gray-400 text-sm">
                © {currentYear} AI Code Review. Made with{' '}
                <Heart className="h-4 w-4 text-red-500 inline mx-1" />
                for developers.
              </span>
            </div>

            <div className="flex items-center gap-4">
              {socialLinks.slice(0, 2).map(social => {
                const Icon = social.icon
                return (
                  <a
                    key={social.name}
                    href={social.href}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-gray-400 hover:text-matrix-green transition-colors"
                  >
                    <Icon className="h-5 w-5" />
                  </a>
                )
              })}
            </div>
          </div>
        </div>
      </footer>
    )
  }

  return (
    <footer className={cn('border-t border-border bg-deep-black', className)}>
      {/* Main Footer Content */}
      <div className="container mx-auto px-4 py-12">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-6 gap-8">
          {/* Brand Section */}
          <div className="lg:col-span-2">
            <div className="flex items-center gap-3 mb-4">
              <div className="relative">
                <Bot className="h-8 w-8 text-matrix-green" />
                <Sparkles className="h-4 w-4 text-matrix-cyan absolute -top-1 -right-1" />
              </div>
              <div>
                <h3 className="text-xl font-bold text-white">AI Code Review</h3>
                <p className="text-xs text-gray-400">Powered by Advanced AI</p>
              </div>
            </div>

            <p className="text-gray-400 text-sm leading-relaxed mb-6 max-w-md">
              Revolutionizing code review with AI-powered analysis. Get instant
              security scans, performance insights, and quality improvements for
              your codebase.
            </p>

            {/* Social Links */}
            <div className="flex items-center gap-3">
              {socialLinks.map(social => {
                const Icon = social.icon
                return (
                  <a
                    key={social.name}
                    href={social.href}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="group relative"
                    title={social.description}
                  >
                    <div className="p-2 rounded-lg bg-card-surface/50 text-gray-400 hover:text-matrix-green hover:bg-matrix-green/10 transition-all duration-200 group-hover:scale-110">
                      <Icon className="h-5 w-5" />
                    </div>
                  </a>
                )
              })}
            </div>
          </div>

          {/* Product Links */}
          <div>
            <h4 className="font-semibold text-white mb-4">Product</h4>
            <ul className="space-y-3">
              {footerLinks.product.map(link => (
                <li key={link.name}>
                  <Link
                    href={link.href}
                    className="text-gray-400 hover:text-matrix-green transition-colors text-sm"
                  >
                    {link.name}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          {/* Resources */}
          <div>
            <h4 className="font-semibold text-white mb-4">Resources</h4>
            <ul className="space-y-3">
              {footerLinks.resources.map(link => {
                const Icon = link.icon
                return (
                  <li key={link.name}>
                    <Link
                      href={link.href}
                      className="flex items-center gap-2 text-gray-400 hover:text-matrix-green transition-colors text-sm group"
                      {...(link.external && {
                        target: '_blank',
                        rel: 'noopener noreferrer',
                      })}
                    >
                      {Icon && <Icon className="h-4 w-4" />}
                      {link.name}
                      {link.external && (
                        <ExternalLink className="h-3 w-3 opacity-0 group-hover:opacity-100 transition-opacity" />
                      )}
                    </Link>
                  </li>
                )
              })}
            </ul>
          </div>

          {/* Company */}
          <div>
            <h4 className="font-semibold text-white mb-4">Company</h4>
            <ul className="space-y-3">
              {footerLinks.company.map(link => {
                const Icon = link.icon
                return (
                  <li key={link.name}>
                    <Link
                      href={link.href}
                      className="flex items-center gap-2 text-gray-400 hover:text-matrix-green transition-colors text-sm"
                    >
                      {Icon && <Icon className="h-4 w-4" />}
                      {link.name}
                    </Link>
                  </li>
                )
              })}
            </ul>
          </div>

          {/* Developers */}
          <div>
            <h4 className="font-semibold text-white mb-4">Developers</h4>
            <ul className="space-y-3">
              {footerLinks.developers.map(link => {
                const Icon = link.icon
                return (
                  <li key={link.name}>
                    <Link
                      href={link.href}
                      className="flex items-center gap-2 text-gray-400 hover:text-matrix-green transition-colors text-sm group"
                      {...(link.external && {
                        target: '_blank',
                        rel: 'noopener noreferrer',
                      })}
                    >
                      {Icon && <Icon className="h-4 w-4" />}
                      {link.name}
                      {link.external && (
                        <ExternalLink className="h-3 w-3 opacity-0 group-hover:opacity-100 transition-opacity" />
                      )}
                    </Link>
                  </li>
                )
              })}
            </ul>
          </div>
        </div>

        {/* Stats Section */}
        <div className="border-t border-border mt-12 pt-8">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
            {stats.map(stat => {
              const Icon = stat.icon
              return (
                <div key={stat.label} className="text-center">
                  <div className="flex items-center justify-center mb-2">
                    <Icon className="h-6 w-6 text-matrix-green" />
                  </div>
                  <div className="text-2xl font-bold text-white mb-1">
                    {stat.value}
                  </div>
                  <div className="text-xs text-gray-400">{stat.label}</div>
                </div>
              )
            })}
          </div>
        </div>

        {/* Newsletter Section */}
        <div className="border-t border-border mt-12 pt-8">
          <div className="max-w-md mx-auto text-center">
            <h4 className="font-semibold text-white mb-2">Stay Updated</h4>
            <p className="text-gray-400 text-sm mb-4">
              Get the latest updates on new features and improvements
            </p>
            <div className="flex gap-2">
              <input
                type="email"
                placeholder="Enter your email"
                className="flex-1 px-3 py-2 bg-input border border-border rounded-lg text-white text-sm focus:border-matrix-green focus:outline-none"
              />
              <Button size="sm">Subscribe</Button>
            </div>
          </div>
        </div>
      </div>

      {/* Bottom Bar */}
      <div className="border-t border-border bg-card-surface/30">
        <div className="container mx-auto px-4 py-6">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-4 text-sm text-gray-400">
              <span>© {currentYear} AI Code Review. All rights reserved.</span>
              <span className="hidden sm:inline">•</span>
              <span className="flex items-center gap-1">
                Made with <Heart className="h-4 w-4 text-red-500" /> and{' '}
                <Coffee className="h-4 w-4 text-yellow-600" /> for developers
              </span>
            </div>

            <div className="flex items-center gap-4">
              {/* Status Badge */}
              <div className="flex items-center gap-2">
                <div className="h-2 w-2 bg-green-500 rounded-full animate-pulse"></div>
                <span className="text-xs text-gray-400">
                  All systems operational
                </span>
              </div>

              {/* Version */}
              <Badge variant="outline" size="sm">
                v1.0.3
              </Badge>

              {/* Language Selector */}
              <select className="bg-transparent text-gray-400 text-sm border-none focus:outline-none">
                <option value="en">🇺🇸 English</option>
                <option value="es">🇪🇸 Español</option>
                <option value="fr">🇫🇷 Français</option>
                <option value="de">🇩🇪 Deutsch</option>
              </select>
            </div>
          </div>
        </div>
      </div>
    </footer>
  )
}

// Feature Cards for Footer
interface FeatureCardProps {
  icon: React.ElementType
  title: string
  description: string
  href?: string
}

export function FeatureCard({
  icon: Icon,
  title,
  description,
  href,
}: FeatureCardProps) {
  const content = (
    <div className="p-4 rounded-lg bg-card-surface/50 border border-border hover:border-matrix-green/30 transition-all duration-200 group">
      <Icon className="h-8 w-8 text-matrix-green mb-3 group-hover:scale-110 transition-transform" />
      <h3 className="font-semibold text-white mb-2">{title}</h3>
      <p className="text-gray-400 text-sm">{description}</p>
      {href && (
        <div className="mt-3 flex items-center gap-1 text-matrix-green text-sm opacity-0 group-hover:opacity-100 transition-opacity">
          Learn more <ExternalLink className="h-3 w-3" />
        </div>
      )}
    </div>
  )

  if (href) {
    return (
      <Link href={href} className="block">
        {content}
      </Link>
    )
  }

  return content
}
