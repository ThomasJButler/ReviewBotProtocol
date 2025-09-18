# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 🎯 Project Overview

**Git Review Assistant** - An AI-powered code review system with automated PR analysis, security scanning, and intelligent feedback generation using GitHub API integration.

**Course Project**: Part of "Codecademy Mastering Generative AI & Agents for Developers" bootcamp demonstrating advanced AI code review methodologies and practical application of AI in software development workflows.

### Course Requirements Compliance

- ✅ **LangChain Integration**: Core AI processing with chains and prompts
- ✅ **LangGraph Workflow**: Complex review logic with state management
- ✅ **GitHub Automation**: Webhook-driven PR reviews with inline comments
- ✅ **Multi-Modal Input**: Three review modes (Paste, Upload, GitHub PR)
- ✅ **Production Ready**: Deployable system with proper error handling
- ✅ **Portfolio Integration**: Follows signature cyber/matrix aesthetic

### Core Functionality

- **Three Review Modes**: Paste Code, Upload File, Review PR (GitHub Integration)
- **AI-Powered Analysis**: Using LangChain + GPT-4o for intelligent code reviews
- **Security Scanning**: OWASP Top 10 vulnerability detection and secret detection
- **GitHub Integration**: Automated webhook processing for PR reviews with inline comments
- **Real-time Feedback**: WebSocket connections for live review updates

## 🏗️ Architecture

### Tech Stack (Course Compliant)

- **Frontend**: Next.js 15 (App Router), TypeScript 5.6 (strict mode)
- **Styling**: Tailwind CSS with custom cyber/matrix theme (glass morphism, green accents)
- **UI Components**: Shadcn/ui + Radix UI primitives
- **AI Engine**: LangChain + LangGraph + OpenAI GPT-4o (Course Requirements)
- **Backend**: FastAPI for webhook processing
- **API Integration**: GitHub API v3/GraphQL, GitHub Webhooks for automated PR reviews
- **State Management**: React Context + Zustand for complex state
- **Real-time**: WebSockets for live updates
- **Testing**: Jest + React Testing Library, Cypress for E2E

### LangChain Architecture (Core Course Component)

- **Review Chains**: Security, Performance, Quality analysis chains
- **LangGraph Workflows**: Complex multi-step review processes with state
- **Prompt Engineering**: Specialized prompts for different review types
- **Memory Management**: Context retention across review sessions
- **Tool Integration**: GitHub API tools for automated commenting

### Project Structure

```
├── app/                    # Next.js 15 App Router
│   ├── api/               # API routes
│   │   ├── review/        # Review endpoints
│   │   ├── webhook/       # GitHub webhook handler
│   │   └── health/        # Health check endpoint
│   ├── (dashboard)/       # Dashboard routes
│   └── layout.tsx         # Root layout with theme
├── components/            # React components
│   ├── ui/               # Shadcn/ui components
│   ├── review/           # Review-specific components
│   └── layout/           # Layout components
├── lib/                   # Utilities
│   ├── ai/               # LangChain & LangGraph setup
│   │   ├── chains/       # Review processing chains
│   │   ├── prompts/      # Specialized review prompts
│   │   ├── tools/        # GitHub integration tools
│   │   └── workflows/    # LangGraph workflow definitions
│   ├── github/           # GitHub API client
│   └── utils/            # Helper functions
├── services/             # Business logic
│   ├── review-engine/    # Core review logic
│   ├── security/         # Security scanning
│   └── analysis/         # Code analysis
├── hooks/                # Custom React hooks
├── types/                # TypeScript definitions
└── backend/              # FastAPI webhook processor
    ├── main.py
    └── handlers/
```

## 🛠️ Development Commands

### Initial Setup

```bash
# Install dependencies
npm install

# Set up environment variables
cp .env.example .env.local

# Install Python dependencies for backend (includes LangChain/LangGraph)
cd backend && pip install -r requirements.txt

# Setup LangChain configuration
npm run setup:langchain

# Run database migrations (if using Supabase/Postgres)
npm run db:migrate
```

### Development

```bash
# Start development server (Next.js + FastAPI)
npm run dev

# Start only frontend
npm run dev:frontend

# Start only backend
npm run dev:backend

# Start with webhook tunnel (for GitHub webhook testing)
npm run dev:tunnel
```

### Testing

```bash
# Run all tests
npm run test

# Run unit tests
npm run test:unit

# Run integration tests
npm run test:integration

# Run E2E tests
npm run test:e2e

# Run security audit
npm run test:security

# Test GitHub webhook locally
npm run webhook:test

# Test LangChain workflows
npm run test:langchain

# Validate inline PR comments
npm run test:pr-comments
```

### Code Quality

```bash
# Run ESLint
npm run lint

# Run TypeScript type checking
npm run typecheck

# Run Prettier formatting
npm run format

# Run all checks (pre-commit)
npm run check
```

### Build & Deploy

```bash
# Build for production
npm run build

# Preview production build
npm run preview

# Deploy to Vercel
npm run deploy

# Deploy backend to Railway/Render
npm run deploy:backend
```

## 🔑 Environment Variables

```env
# Required - Frontend (.env.local)
NEXT_PUBLIC_APP_URL=http://localhost:3000
NEXT_PUBLIC_GITHUB_APP_NAME=git-review-assistant

# Required - API Keys
OPENAI_API_KEY=sk-...
GITHUB_APP_ID=123456
GITHUB_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----..."
GITHUB_WEBHOOK_SECRET=your-webhook-secret
GITHUB_CLIENT_ID=Iv1.abc123
GITHUB_CLIENT_SECRET=abc123def456

# LangChain Configuration (Course Required)
LANGCHAIN_API_KEY=ls__...      # LangSmith tracing & monitoring
LANGCHAIN_PROJECT=git-review-assistant
LANGCHAIN_TRACING_V2=true

# Optional - Enhanced Features
ANTHROPIC_API_KEY=sk-ant-...  # For Claude integration
SENTRY_DSN=https://...         # Error tracking
SUPABASE_URL=https://...       # Database
SUPABASE_ANON_KEY=eyJ...       # Database

# Backend (backend/.env)
WEBHOOK_ENDPOINT_SECRET=whsec_...
REDIS_URL=redis://localhost:6379
```

## 🔐 GitHub App Setup

1. **Create GitHub App**:
   - Go to Settings > Developer settings > GitHub Apps
   - Set Webhook URL: `https://your-app.vercel.app/api/webhook/github`
   - Set Callback URL: `https://your-app.vercel.app/api/auth/github/callback`

2. **Required Permissions**:
   - **Repository**: Pull requests (Read & Write), Contents (Read), Issues (Write)
   - **Account**: Email (Read)

3. **Subscribe to Events**:
   - Pull request
   - Pull request review
   - Pull request review comment
   - Push

4. **Generate Private Key** and add to environment variables

## 🎨 UI/UX Design System

### Color Palette (from STYLE_GUIDE.md)

```css
:root {
  --matrix-green: #00ff00;
  --matrix-cyan: #00ffff;
  --deep-black: #0a0a0a;
  --card-surface: #1a1a1a;
  --glass-bg: rgba(26, 26, 26, 0.6);
  --glass-border: rgba(255, 255, 255, 0.1);
}
```

### Component Patterns

- Glass morphism cards with backdrop blur
- Green accent colors for CTAs and active states
- Monospace font for code display
- Smooth transitions with cubic-bezier easing
- Dark theme by default (no light mode initially)

## 🤖 AI Review Engine (LangChain Based)

### LangChain Review Chains

```typescript
// Course-compliant LangChain implementation
const securityChain = new LLMChain({
  llm: chatModel,
  prompt: securityPrompt,
  outputKey: 'securityFindings',
})

const performanceChain = new LLMChain({
  llm: chatModel,
  prompt: performancePrompt,
  outputKey: 'performanceFindings',
})

const qualityChain = new LLMChain({
  llm: chatModel,
  prompt: qualityPrompt,
  outputKey: 'qualityFindings',
})

// LangGraph workflow for complex review orchestration
const reviewWorkflow = new StateGraph()
  .addNode('parse', parseCode)
  .addNode('security', securityChain)
  .addNode('performance', performanceChain)
  .addNode('quality', qualityChain)
  .addNode('synthesize', synthesizeFindings)
  .addEdge('parse', 'security')
  .addEdge('parse', 'performance')
  .addEdge('parse', 'quality')
  .addEdge(['security', 'performance', 'quality'], 'synthesize')
```

### Review Categories

1. **Security** (Critical, High, Medium, Low)
   - SQL injection, XSS, authentication bypass
   - Secret detection, dependency vulnerabilities
   - OWASP Top 10 compliance checking

2. **Performance** (High, Medium, Low)
   - Algorithm complexity analysis (O(n) calculations)
   - Memory usage optimization
   - Database query efficiency

3. **Code Quality** (Warning, Info)
   - Cyclomatic complexity analysis
   - Code smells, duplication detection
   - Best practices, style consistency

4. **Documentation & Testing** (Info)
   - Missing documentation gaps
   - Test coverage analysis
   - Code maintainability metrics

## 🚀 Key Features Implementation

### 1. Paste Code Review

- Monaco Editor for code input
- Language auto-detection
- Real-time syntax highlighting
- Instant AI analysis

### 2. File Upload Review

- Drag & drop interface
- Multiple file support
- Progress indicators
- Batch processing

### 3. GitHub PR Review

- OAuth authentication
- PR list with filters
- Inline comments
- Status checks integration

### 4. GitHub PR Review with Inline Comments (Course Focus)

- **Automated PR Detection**: Webhook triggers on PR open/update/sync
- **Inline Comment Generation**: AI-generated comments posted directly to PR lines
- **Status Checks**: Pass/fail status based on review score
- **CodeRabbit-style Integration**: Comments appear as code review suggestions
- **Review Summary**: Overall PR health and recommendation

### Inline Comment Example

```typescript
// Generated inline comment structure
{
  path: "src/components/Button.tsx",
  line: 42,
  body: "🔒 **Security Issue** (High)\n\nPotential XSS vulnerability detected. User input should be sanitized before rendering.\n\n**Suggestion**: Use `dangerouslySetInnerHTML` with a sanitization library like DOMPurify."
}
```

## 📊 Performance Targets (Course Grading Criteria)

- **Review Generation**: < 30 seconds per PR (LangChain optimization)
- **API Response**: < 2 seconds for manual reviews
- **Webhook Processing**: < 5 seconds (GitHub requirement)
- **False Positive Rate**: < 10% (acceptable for course demo)
- **Lighthouse Score**: > 90 (portfolio standard)
- **LangChain Response Time**: < 15 seconds for complex workflows
- **Inline Comment Accuracy**: > 85% relevant/actionable feedback

### Course Demo Requirements

- Must demonstrate all three input modes working
- Show actual GitHub PR with inline AI comments
- Display security vulnerabilities detection
- Demonstrate responsive UI on mobile/desktop

## 🧪 Testing Strategy

### Unit Tests

- Components: 90% coverage minimum
- Services: 95% coverage minimum
- Utilities: 100% coverage

### Integration Tests

- API endpoints
- GitHub webhook processing
- AI review pipeline

### E2E Tests

- Complete review flow
- GitHub authentication
- PR commenting

## 🔄 CI/CD Pipeline

### GitHub Actions Workflows

```yaml
# .github/workflows/ci.yml
- Lint and typecheck on every push
- Run tests on PR
- Security audit weekly
- Deploy to Vercel on main branch
```

## 📝 Important Notes

1. **Security First**: Never commit API keys or secrets
2. **Rate Limiting**: Respect GitHub API rate limits (5000 req/hour authenticated)
3. **Error Handling**: Implement comprehensive error boundaries and logging
4. **Accessibility**: Follow WCAG 2.1 AA standards
5. **Performance**: Lazy load heavy components, optimize bundle size

## 🔗 Related Resources

- [GitHub Apps Documentation](https://docs.github.com/en/developers/apps)
- [LangChain Documentation](https://docs.langchain.com/)
- [Next.js 15 Documentation](https://nextjs.org/docs)
- [Shadcn/ui Components](https://ui.shadcn.com/)
- Portfolio Style Guide: `STYLE_GUIDE.md`
- DevelopersOracle Integration: `DevelopersOracle/README.md`

## 🎯 Development Priorities

1. **Phase 1**: Basic UI with paste code functionality
2. **Phase 2**: GitHub OAuth and PR listing
3. **Phase 3**: AI review engine with LangChain
4. **Phase 4**: Webhook processing and inline comments
5. **Phase 5**: Advanced features (metrics, learning system)

## 💡 Tips for Development

- Use the DevelopersOracle code analysis utilities where applicable
- Follow the portfolio style guide for consistent UI
- Implement proper error boundaries for AI failures
- Add loading skeletons for better UX
- Cache GitHub API responses to reduce rate limit usage
- Use streaming for large PR reviews
- Implement WebSocket fallback to polling for older browsers
