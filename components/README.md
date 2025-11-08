# ReviewBot Protocol - UI Components

This directory contains all the UI components for the ReviewBot Protocol, built with a cyber/matrix aesthetic and modern React patterns.

## 🎨 Design System

### Color Palette

- **Matrix Green**: `#00ff00` - Primary actions and accents
- **Matrix Cyan**: `#00ffff` - Secondary highlights
- **Deep Black**: `#0a0a0a` - Primary background
- **Card Surface**: `#1a1a1a` - Component backgrounds
- **Glass Border**: `rgba(255, 255, 255, 0.1)` - Subtle borders

### Effects

- **Glass Morphism**: Backdrop blur with transparency
- **Matrix Glow**: Green shadow effects for interactive elements
- **Smooth Transitions**: 200-300ms cubic-bezier animations
- **Hover Transforms**: Subtle scale and translate effects

## 📁 Component Structure

```
components/
├── ui/                     # Base UI components
│   ├── button.tsx         # Button with variants
│   ├── card.tsx           # Glass morphism cards
│   ├── input.tsx          # Form inputs
│   ├── textarea.tsx       # Text areas
│   ├── badge.tsx          # Status badges
│   ├── skeleton.tsx       # Loading states
│   ├── tabs.tsx           # Tab navigation
│   ├── dialog.tsx         # Modal dialogs
│   ├── select.tsx         # Dropdown selects
│   └── index.ts           # Exports
├── review/                # Review-specific components
│   ├── CodeEditor.tsx     # Monaco editor
│   ├── FileUpload.tsx     # Drag & drop upload
│   ├── PRSelector.tsx     # GitHub PR selection
│   ├── ReviewResults.tsx  # Results display
│   ├── ReviewInterface.tsx # Main interface
│   └── index.ts           # Exports
├── layout/                # Layout components
│   ├── Header.tsx         # Navigation header
│   ├── Footer.tsx         # Site footer
│   └── index.ts           # Exports
└── index.ts               # Main exports
```

## 🧩 Base UI Components

### Button

```tsx
import { Button } from '@/components/ui/button'

// Variants
<Button variant="primary">Primary Action</Button>
<Button variant="secondary">Secondary</Button>
<Button variant="ghost">Ghost</Button>
<Button variant="destructive">Delete</Button>
<Button variant="outline">Outline</Button>

// Sizes
<Button size="sm">Small</Button>
<Button size="md">Medium</Button>
<Button size="lg">Large</Button>
<Button size="icon"><Icon /></Button>

// States
<Button loading>Processing...</Button>
<Button disabled>Disabled</Button>
<Button icon={<Star />}>With Icon</Button>
```

### Card

```tsx
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'

<Card>
  <CardHeader>
    <CardTitle>Card Title</CardTitle>
    <CardDescription>Description</CardDescription>
  </CardHeader>
  <CardContent>
    Content goes here
  </CardContent>
</Card>

// Specialized variants
<MatrixCard>Matrix themed card</MatrixCard>
<GlowCard glowColor="matrix-green">Glowing card</GlowCard>
```

### Input

```tsx
import { Input, SearchInput, MatrixInput } from '@/components/ui/input'

<Input placeholder="Standard input" />
<Input icon={<Search />} placeholder="With icon" />
<Input error="Required field" />
<Input success />

<SearchInput placeholder="Search..." />
<MatrixInput variant="matrix" />
```

### Badge

```tsx
import { Badge, SecurityBadge, StatusBadge } from '@/components/ui/badge'

// Security badges
<SecurityBadge severity="critical" />
<SecurityBadge severity="high" />
<SecurityBadge severity="medium" />
<SecurityBadge severity="low" />

// Status badges
<StatusBadge status="success" />
<StatusBadge status="warning" />
<StatusBadge status="error" />

// Custom badges
<Badge variant="matrix">Matrix Theme</Badge>
<Badge variant="cyber">Cyber Theme</Badge>
```

## 🔧 Review Components

### CodeEditor

Monaco Editor with matrix theme and advanced features:

```tsx
import { CodeEditor } from '@/components/review'
;<CodeEditor
  value={code}
  onChange={setCode}
  language="typescript"
  height={400}
  showMetrics={true}
  readOnly={false}
  onLanguageChange={handleLanguageChange}
/>
```

**Features:**

- Matrix dark theme with green accents
- Syntax highlighting for 15+ languages
- Real-time metrics (lines, characters, complexity)
- Format code functionality
- Fullscreen mode
- Copy/download code
- Auto-detection of file types

### FileUpload

Drag & drop file upload with progress tracking:

```tsx
import { FileUpload } from '@/components/review'
;<FileUpload
  onFilesSelected={handleFiles}
  selectedFiles={files}
  onRemoveFile={removeFile}
  maxFiles={10}
  maxSize={50} // MB
  multiple={true}
  showPreview={true}
/>
```

**Features:**

- Drag & drop interface
- File type validation
- Progress indicators
- Preview for images
- Batch operations
- File size limits
- Multiple file support

### PRSelector

GitHub pull request selection interface:

```tsx
import { PRSelector } from '@/components/review'
;<PRSelector
  onPRSelected={handlePRSelection}
  selectedPR={currentPR}
  repositories={repoList}
  maxResults={20}
  showFilters={true}
/>
```

**Features:**

- Real-time PR loading
- Advanced filtering (repo, state, author)
- Search functionality
- Sort options
- Custom PR URL input
- Rich PR metadata display

### ReviewResults

Comprehensive results display with categorized findings:

```tsx
import { ReviewResults } from '@/components/review'
;<ReviewResults
  results={reviewData}
  isLoading={false}
  onExport={handleExport}
  onShare={handleShare}
/>
```

**Features:**

- Tabbed findings by category
- Expandable finding details
- Severity-based filtering
- Export/share functionality
- Code snippets with syntax highlighting
- Reference links
- Impact assessment

## 🏗️ Layout Components

### Header

Navigation header with GitHub integration:

```tsx
import { Header } from '@/components/layout'
;<Header user={currentUser} onSignIn={handleSignIn} onSignOut={handleSignOut} />
```

**Features:**

- Responsive navigation
- GitHub OAuth integration
- User profile menu
- Notification center
- Search functionality
- Mobile-friendly

### Footer

Comprehensive site footer:

```tsx
import { Footer } from '@/components/layout'

<Footer />           // Full footer
<Footer minimal />   // Minimal version
```

**Features:**

- Link organization
- Social media links
- Newsletter signup
- Status indicators
- Multi-language support

## 🎯 Main Interface

### ReviewInterface

Complete review interface combining all components:

```tsx
import { ReviewInterface } from '@/components/review'
;<ReviewInterface
  onReviewComplete={handleResults}
  maxFiles={10}
  maxFileSize={50}
/>
```

**Features:**

- Three-tab interface (Paste, Upload, PR)
- Real-time validation
- Keyboard shortcuts (⌘+Enter)
- Loading states
- Error handling
- Results integration

## 🛠️ Development Guidelines

### Component Creation

1. Use TypeScript with strict typing
2. Implement proper accessibility (ARIA)
3. Follow the design system colors
4. Add proper error boundaries
5. Include loading states
6. Support responsive design

### Styling Guidelines

1. Use Tailwind utility classes
2. Apply glass morphism effects with `backdrop-blur`
3. Use matrix green (`#00ff00`) for primary actions
4. Implement smooth transitions (200-300ms)
5. Add hover effects with subtle transforms
6. Maintain consistent spacing (4px scale)

### Performance Best Practices

1. Lazy load heavy components
2. Implement proper memoization
3. Use skeleton loaders
4. Optimize bundle size
5. Cache API responses
6. Implement virtual scrolling for large lists

## 🧪 Testing

### Component Testing

- Unit tests for all components
- Integration tests for complex interactions
- Accessibility testing with screen readers
- Visual regression testing
- Performance testing

### Testing Utils

```tsx
import { render, screen } from '@testing-library/react'
import { Button } from '@/components/ui/button'

test('button renders correctly', () => {
  render(<Button>Click me</Button>)
  expect(screen.getByRole('button')).toBeInTheDocument()
})
```

## 📱 Responsive Design

All components are built mobile-first with breakpoints:

- **Mobile**: `< 768px`
- **Tablet**: `768px - 1024px`
- **Desktop**: `> 1024px`

### Responsive Features

- Collapsible navigation
- Stack layouts on mobile
- Touch-friendly interactions
- Optimized typography scales
- Responsive spacing

## ♿ Accessibility

### WCAG 2.1 AA Compliance

- Proper ARIA labels and roles
- Keyboard navigation support
- Focus management
- Color contrast compliance
- Screen reader compatibility
- Reduced motion support

### Keyboard Shortcuts

- `Tab` / `Shift+Tab`: Navigate between elements
- `Space` / `Enter`: Activate buttons
- `Escape`: Close modals/menus
- `⌘+Enter` / `Ctrl+Enter`: Submit forms
- Arrow keys: Navigate tabs/lists

## 🚀 Usage Examples

### Quick Start

```tsx
import { Button, Card, Input } from '@/components/ui'
import { ReviewInterface } from '@/components/review'
import { Header, Footer } from '@/components/layout'

export default function App() {
  return (
    <div>
      <Header />
      <main>
        <ReviewInterface />
      </main>
      <Footer />
    </div>
  )
}
```

### Custom Styling

```tsx
// Extend component styles
<Button className="my-custom-class">
  Custom Button
</Button>

// Use design tokens
<div className="bg-deep-black text-matrix-green">
  Matrix themed content
</div>
```

## 🔧 Customization

### Theme Customization

Components use CSS custom properties and Tailwind config for theming:

```css
:root {
  --matrix-green: #00ff00;
  --matrix-cyan: #00ffff;
  --deep-black: #0a0a0a;
  --card-surface: #1a1a1a;
}
```

### Component Variants

Use `class-variance-authority` for component variants:

```tsx
const buttonVariants = cva('base-classes', {
  variants: {
    variant: {
      primary: 'primary-classes',
      secondary: 'secondary-classes',
    },
  },
})
```

## 📚 Resources

- [Tailwind CSS Documentation](https://tailwindcss.com/docs)
- [Radix UI Components](https://www.radix-ui.com/)
- [Lucide Icons](https://lucide.dev/)
- [Monaco Editor](https://microsoft.github.io/monaco-editor/)
- [React Dropzone](https://react-dropzone.js.org/)

## 🤝 Contributing

1. Follow the established patterns
2. Add proper TypeScript types
3. Include comprehensive tests
4. Update documentation
5. Follow the design system
6. Ensure accessibility compliance
