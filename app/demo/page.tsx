'use client'

import React, { useState } from 'react'
import {
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Input,
  Textarea,
  Badge,
  Skeleton,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui'
import {
  CodeEditor,
  FileUpload,
  ReviewResults,
  PRSelector,
} from '@/components/review'
import { Header, Footer } from '@/components/layout'
import {
  Github,
  Shield,
  Zap,
  Code2,
  Upload,
  FileText,
  Star,
  Heart,
  Coffee,
} from 'lucide-react'

export default function DemoPage() {
  const [selectedFiles, setSelectedFiles] = useState<any[]>([])
  const [codeValue, setCodeValue] =
    useState(`// Sample TypeScript React Component
import React, { useState, useEffect } from 'react'

interface UserProps {
  id: string
  name: string
  email: string
}

export default function UserProfile({ id, name, email }: UserProps) {
  const [loading, setLoading] = useState(false)
  const [user, setUser] = useState<UserProps | null>(null)

  useEffect(() => {
    // This could have security issues - direct API call without validation
    fetchUser(id)
  }, [id])

  const fetchUser = async (userId: string) => {
    setLoading(true)
    try {
      // SQL injection vulnerability - user input not sanitized
      const response = await fetch(\`/api/users/\${userId}\`)
      const userData = await response.json()
      setUser(userData)
    } catch (error) {
      // Missing error handling
      console.log(error)
    }
    setLoading(false)
  }

  return (
    <div className="user-profile">
      {loading ? (
        <div>Loading...</div>
      ) : (
        <div>
          <h1>{user?.name}</h1>
          <p>{user?.email}</p>
        </div>
      )}
    </div>
  )
}`)

  const mockReviewResults = {
    id: 'demo-review',
    timestamp: new Date().toISOString(),
    summary:
      'Analysis complete! Found 3 issues including 1 critical security vulnerability that requires immediate attention. The code shows good structure but has some security and error handling concerns.',
    overallScore: 75,
    findings: [
      {
        id: '1',
        title: 'SQL Injection Vulnerability',
        description:
          'User input is directly interpolated into API endpoint without validation or sanitization.',
        severity: 'critical' as const,
        category: 'security' as const,
        lineNumber: 19,
        fileName: 'UserProfile.tsx',
        code: 'const response = await fetch(`/api/users/${userId}`)',
        suggestion:
          'Validate and sanitize user input before using in API calls. Use proper URL encoding.',
        impact:
          'Attackers could potentially access unauthorized data or perform injection attacks.',
        effort: 'medium' as const,
        references: [
          'https://owasp.org/www-community/attacks/SQL_Injection',
          'https://developer.mozilla.org/en-US/docs/Web/API/encodeURIComponent',
        ],
      },
      {
        id: '2',
        title: 'Inadequate Error Handling',
        description:
          'Errors are only logged to console without proper user feedback or error recovery.',
        severity: 'high' as const,
        category: 'quality' as const,
        lineNumber: 22,
        fileName: 'UserProfile.tsx',
        code: 'console.log(error)',
        suggestion:
          'Implement proper error handling with user feedback and error boundaries.',
        impact:
          'Poor user experience when errors occur, difficulty in debugging production issues.',
        effort: 'low' as const,
      },
      {
        id: '3',
        title: 'Missing Loading State Management',
        description:
          'Loading state is not properly reset if the fetch operation fails.',
        severity: 'medium' as const,
        category: 'quality' as const,
        lineNumber: 24,
        fileName: 'UserProfile.tsx',
        suggestion:
          'Ensure loading state is reset in finally block or handle errors properly.',
        impact:
          'UI might remain in loading state indefinitely if requests fail.',
        effort: 'low' as const,
      },
    ],
    metrics: {
      totalIssues: 3,
      criticalIssues: 1,
      highIssues: 1,
      mediumIssues: 1,
      lowIssues: 0,
      securityIssues: 1,
      performanceIssues: 0,
      qualityIssues: 2,
      linesAnalyzed: 35,
      filesAnalyzed: 1,
    },
    duration: 8500,
    aiModel: 'GPT-4o',
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-deep-black via-gray-900 to-deep-black">
      <Header
        user={{
          id: '1',
          login: 'demo-user',
          name: 'Demo User',
          email: 'demo@example.com',
          avatarUrl: 'https://github.com/identicons/demo.png',
          githubUrl: 'https://github.com/demo-user',
          isConnected: true,
        }}
      />

      <main className="container mx-auto px-4 py-12 space-y-12">
        {/* Hero Section */}
        <div className="text-center space-y-6">
          <h1 className="text-5xl font-bold text-white mb-4">
            🎨 Component Showcase
          </h1>
          <p className="text-xl text-gray-400 max-w-3xl mx-auto">
            A comprehensive showcase of all UI components built for the
            ReviewBot Protocol with cyber/matrix aesthetic
          </p>
        </div>

        {/* Buttons Section */}
        <Card>
          <CardHeader>
            <CardTitle>Button Components</CardTitle>
            <CardDescription>
              Various button styles with cyber/matrix theme
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="space-y-3">
                <h4 className="text-sm font-medium text-white">Primary</h4>
                <Button>Primary Button</Button>
                <Button loading>Loading...</Button>
                <Button icon={<Star className="h-4 w-4" />}>With Icon</Button>
              </div>
              <div className="space-y-3">
                <h4 className="text-sm font-medium text-white">Secondary</h4>
                <Button variant="secondary">Secondary</Button>
                <Button variant="secondary" disabled>
                  Disabled
                </Button>
                <Button variant="secondary" size="sm">
                  Small
                </Button>
              </div>
              <div className="space-y-3">
                <h4 className="text-sm font-medium text-white">Ghost</h4>
                <Button variant="ghost">Ghost Button</Button>
                <Button variant="ghost" size="lg">
                  Large Ghost
                </Button>
                <Button variant="ghost" size="icon">
                  <Heart className="h-4 w-4" />
                </Button>
              </div>
              <div className="space-y-3">
                <h4 className="text-sm font-medium text-white">Destructive</h4>
                <Button variant="destructive">Delete</Button>
                <Button variant="outline">Outline</Button>
                <Button variant="destructive" size="sm">
                  Small Delete
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Inputs Section */}
        <Card>
          <CardHeader>
            <CardTitle>Input Components</CardTitle>
            <CardDescription>
              Form inputs with matrix green focus states
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-4">
                <Input placeholder="Standard input" />
                <Input
                  placeholder="Search..."
                  icon={<Shield className="h-4 w-4" />}
                />
                <Input
                  placeholder="With error"
                  error="This field is required"
                />
                <Input placeholder="Success state" success />
              </div>
              <div className="space-y-4">
                <Textarea placeholder="Enter your comments..." />
                <Select>
                  <SelectTrigger>
                    <SelectValue placeholder="Select an option" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="option1">Option 1</SelectItem>
                    <SelectItem value="option2">Option 2</SelectItem>
                    <SelectItem value="option3">Option 3</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Badges Section */}
        <Card>
          <CardHeader>
            <CardTitle>Badge Components</CardTitle>
            <CardDescription>Status and severity indicators</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div>
                <h4 className="text-sm font-medium text-white mb-2">
                  Severity Badges
                </h4>
                <div className="flex gap-2 flex-wrap">
                  <Badge variant="critical">Critical</Badge>
                  <Badge variant="high">High</Badge>
                  <Badge variant="medium">Medium</Badge>
                  <Badge variant="low">Low</Badge>
                  <Badge variant="info">Info</Badge>
                </div>
              </div>
              <div>
                <h4 className="text-sm font-medium text-white mb-2">
                  Status Badges
                </h4>
                <div className="flex gap-2 flex-wrap">
                  <Badge variant="success">Success</Badge>
                  <Badge variant="warning">Warning</Badge>
                  <Badge variant="error">Error</Badge>
                  <Badge variant="matrix">Matrix Theme</Badge>
                  <Badge variant="cyber">Cyber Theme</Badge>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Code Editor Section */}
        <Card>
          <CardHeader>
            <CardTitle>Code Editor</CardTitle>
            <CardDescription>
              Monaco Editor with matrix theme and syntax highlighting
            </CardDescription>
          </CardHeader>
          <CardContent>
            <CodeEditor
              value={codeValue}
              onChange={(value: string | undefined) =>
                setCodeValue(value || '')
              }
              language="typescript"
              height={300}
              showMetrics={true}
            />
          </CardContent>
        </Card>

        {/* File Upload Section */}
        <Card>
          <CardHeader>
            <CardTitle>File Upload</CardTitle>
            <CardDescription>
              Drag & drop file upload with progress indicators
            </CardDescription>
          </CardHeader>
          <CardContent>
            <FileUpload
              onFilesSelected={files => setSelectedFiles(files)}
              selectedFiles={selectedFiles}
              onRemoveFile={id =>
                setSelectedFiles(files => files.filter(f => f.id !== id))
              }
              maxFiles={5}
              maxSize={10}
            />
          </CardContent>
        </Card>

        {/* Review Results Section */}
        <Card>
          <CardHeader>
            <CardTitle>Review Results</CardTitle>
            <CardDescription>
              AI code review results with detailed findings
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ReviewResults
              results={mockReviewResults}
              isLoading={false}
              onExport={() => console.log('Export')}
              onShare={() => console.log('Share')}
            />
          </CardContent>
        </Card>

        {/* Tabs Section */}
        <Card>
          <CardHeader>
            <CardTitle>Tab Components</CardTitle>
            <CardDescription>
              Tabbed interfaces with matrix styling
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Tabs defaultValue="tab1">
              <TabsList className="grid w-full grid-cols-3">
                <TabsTrigger value="tab1">Security</TabsTrigger>
                <TabsTrigger value="tab2">Performance</TabsTrigger>
                <TabsTrigger value="tab3">Quality</TabsTrigger>
              </TabsList>
              <TabsContent value="tab1" className="mt-4">
                <div className="p-4 rounded-lg bg-card-surface/30">
                  <Shield className="h-8 w-8 text-red-500 mb-2" />
                  <h3 className="text-lg font-semibold text-white mb-2">
                    Security Analysis
                  </h3>
                  <p className="text-gray-400">
                    Advanced security scanning with OWASP compliance checking.
                  </p>
                </div>
              </TabsContent>
              <TabsContent value="tab2" className="mt-4">
                <div className="p-4 rounded-lg bg-card-surface/30">
                  <Zap className="h-8 w-8 text-yellow-500 mb-2" />
                  <h3 className="text-lg font-semibold text-white mb-2">
                    Performance Insights
                  </h3>
                  <p className="text-gray-400">
                    Identify performance bottlenecks and optimization
                    opportunities.
                  </p>
                </div>
              </TabsContent>
              <TabsContent value="tab3" className="mt-4">
                <div className="p-4 rounded-lg bg-card-surface/30">
                  <Code2 className="h-8 w-8 text-blue-500 mb-2" />
                  <h3 className="text-lg font-semibold text-white mb-2">
                    Code Quality
                  </h3>
                  <p className="text-gray-400">
                    Best practices, maintainability, and code smell detection.
                  </p>
                </div>
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>

        {/* Dialog Section */}
        <Card>
          <CardHeader>
            <CardTitle>Dialog Components</CardTitle>
            <CardDescription>
              Modal dialogs with glass morphism effects
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex gap-4">
              <Dialog>
                <DialogTrigger asChild>
                  <Button variant="outline">Open Dialog</Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>ReviewBot Protocol Settings</DialogTitle>
                    <DialogDescription>
                      Configure your code review preferences and analysis
                      options.
                    </DialogDescription>
                  </DialogHeader>
                  <div className="space-y-4 py-4">
                    <div className="space-y-2">
                      <label className="text-sm font-medium text-white">
                        Analysis Depth
                      </label>
                      <Select>
                        <SelectTrigger>
                          <SelectValue placeholder="Select depth" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="basic">Basic Scan</SelectItem>
                          <SelectItem value="standard">
                            Standard Analysis
                          </SelectItem>
                          <SelectItem value="deep">Deep Analysis</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-medium text-white">
                        Notification Preferences
                      </label>
                      <div className="flex items-center space-x-2">
                        <input type="checkbox" className="rounded" />
                        <span className="text-sm text-gray-400">
                          Email notifications
                        </span>
                      </div>
                    </div>
                  </div>
                  <div className="flex justify-end gap-2">
                    <Button variant="outline">Cancel</Button>
                    <Button>Save Settings</Button>
                  </div>
                </DialogContent>
              </Dialog>
            </div>
          </CardContent>
        </Card>

        {/* Loading States */}
        <Card>
          <CardHeader>
            <CardTitle>Loading States</CardTitle>
            <CardDescription>
              Skeleton loaders and shimmer effects
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="space-y-2">
                <Skeleton className="h-4 w-[300px]" />
                <Skeleton className="h-4 w-[200px]" />
                <Skeleton className="h-4 w-[250px]" />
              </div>
              <div className="flex items-center space-x-4">
                <Skeleton className="h-12 w-12 rounded-full" />
                <div className="space-y-2">
                  <Skeleton className="h-4 w-[200px]" />
                  <Skeleton className="h-4 w-[150px]" />
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </main>

      <Footer />
    </div>
  )
}
