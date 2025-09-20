# Git Review Assistant

> **Portfolio Project**: A full-stack AI-powered code review system built to demonstrate modern development capabilities and understanding of AI systems from the ground up.

## What's This All About?

This is a **portfolio showcase project** designed to demonstrate full-stack development skills and deep understanding of how AI code review systems actually work under the hood. It's not trying to replace established tools like CodeRabbit (which is brilliant and probably what you should use day-to-day), but rather shows how you'd build something similar from scratch.

The project demonstrates expertise in:

- **Full-stack architecture** (Next.js 15 + FastAPI)
- **AI integration** (LangChain + LangGraph + OpenAI)
- **GitHub API integration** with automated PR reviews
- **Security scanning** and vulnerability detection
- **Modern UI/UX** with a cyber/matrix aesthetic
- **Production deployment** strategies

## Core Features

### Three Review Modes

1. **Paste Code**: Drop in code snippets for instant AI analysis
2. **File Upload**: Upload files for comprehensive review
3. **GitHub PR Review**: Automated PR analysis with inline comments (like CodeRabbit)

### AI-Powered Analysis

- **Security Scanning**: OWASP Top 10, secret detection, vulnerability analysis
- **Performance Review**: Algorithm complexity, memory usage, optimisation suggestions
- **Code Quality**: Style consistency, best practices, maintainability metrics
- **Documentation**: Missing docs, unclear naming, test coverage gaps

### GitHub Integration

- OAuth authentication and repository access
- Automated webhook processing for PR reviews
- Inline comments posted directly to pull requests
- Status checks integration (pass/fail based on review score)

## Tech Stack

**Frontend** (Next.js 15)

- TypeScript with strict mode
- Tailwind CSS with custom cyber theme
- Shadcn/ui components
- React Context + Zustand for state management

**Backend** (FastAPI)

- Python 3.11+ with async/await
- LangChain + LangGraph for AI workflows
- SQLAlchemy for database operations
- GitHub API v3/GraphQL integration

**AI Engine**

- OpenAI GPT-4o for code analysis
- Custom LangChain chains for different review types
- LangGraph workflows for complex multi-step processes
- Specialized prompts for security, performance, and quality analysis

## When Might This Actually Be Useful?

Look, CodeRabbit is ace and you should probably use that for most scenarios. But this custom approach could be valuable if you're dealing with:

**Privacy-First Environments**

- Financial services or healthcare where code can't leave your infrastructure
- Proprietary algorithms requiring extra security measures
- Compliance requirements for data sovereignty

**Cost Considerations**

- Large teams where per-seat pricing becomes expensive
- Multiple repositories where usage-based pricing adds up
- Long-term projects where one-time build cost beats ongoing subscriptions

**Hyper-Customisation**

- Specific coding standards or architectural patterns to enforce
- Domain-specific security requirements (e.g., crypto, fintech)
- Integration with internal tools and workflows
- Custom review criteria that generic tools don't support

**Learning & Control**

- Understanding exactly how your review system works
- Ability to debug and improve AI prompts
- Full control over the review logic and criteria

## Quick Start

### Prerequisites

- Node.js 18+ and npm
- Python 3.11+ and pip
- OpenAI API key
- GitHub App credentials (for GitHub integration)

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/git-review-assistant
cd git-review-assistant

# Install frontend dependencies
npm install

# Set up backend
cd backend
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env.local
# Edit .env.local with your API keys

# Run the development servers
npm run dev  # Starts both frontend and backend
```

### Environment Setup

```env
# Required
OPENAI_API_KEY=your-openai-api-key
GITHUB_APP_ID=your-github-app-id
GITHUB_PRIVATE_KEY=your-private-key
GITHUB_CLIENT_ID=your-client-id
GITHUB_CLIENT_SECRET=your-client-secret

# Optional
LANGCHAIN_API_KEY=your-langchain-key  # For tracing
DEMO_MODE=true  # For portfolio demo without real GitHub
```

## Architecture Overview

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Next.js 15    │    │    FastAPI       │    │   GitHub API    │
│   Frontend       │◄──►│   Backend        │◄──►│   Integration   │
│                 │    │                  │    │                 │
│ • React UI      │    │ • LangChain      │    │ • OAuth Flow    │
│ • TypeScript    │    │ • AI Processing  │    │ • Webhook       │
│ • Tailwind CSS  │    │ • Database       │    │ • PR Comments   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌──────────────────┐
                       │   OpenAI GPT-4   │
                       │   AI Engine      │
                       │                  │
                       │ • Code Analysis  │
                       │ • Security Scan  │
                       │ • Performance    │
                       └──────────────────┘
```

## Project Structure

```
├── app/                    # Next.js 15 App Router
│   ├── api/               # API routes
│   ├── (dashboard)/       # Dashboard pages
│   └── components/        # React components
├── backend/               # FastAPI backend
│   ├── main.py           # Application entry point
│   ├── routers/          # API route handlers
│   ├── services/         # Business logic
│   └── models/           # Database models
├── lib/                   # Shared utilities
│   ├── ai/               # LangChain setup
│   └── github/           # GitHub integration
└── docs/                 # Documentation
```

## Development Commands

```bash
# Development
npm run dev              # Start both frontend and backend
npm run dev:frontend     # Frontend only
npm run dev:backend      # Backend only

# Testing
npm run test            # Run all tests
npm run test:unit       # Unit tests
npm run test:e2e        # End-to-end tests

# Code Quality
npm run lint            # ESLint
npm run typecheck       # TypeScript checking
npm run format          # Prettier formatting

# Deployment
npm run build           # Production build
npm run deploy          # Deploy to Vercel/Render
```

## Deployment

### Portfolio Demo Mode

For showcasing without exposing real credentials:

```env
DEMO_MODE=true
GITHUB_INTEGRATION=false
```

### Full Functionality

Users can fork and deploy with their own credentials:

1. Fork this repository
2. Set up GitHub App following the guide in `/backend/RENDER_SETUP_GUIDE.md`
3. Deploy to Vercel (frontend) + Render (backend)
4. Configure environment variables

See detailed deployment guides:

- [Render Backend Setup](/backend/RENDER_SETUP_GUIDE.md)
- [Production Deployment Strategy](/backend/DEPLOYMENT_PLAN.md)

## Course Context

This project was built as part of the **"Codecademy Mastering Generative AI & Agents for Developers"** bootcamp, demonstrating:

- LangChain integration with custom chains and prompts
- LangGraph workflows for complex AI processing
- GitHub automation with webhook-driven reviews
- Multi-modal input handling (paste, upload, GitHub)
- Production-ready deployment with proper error handling

## Contributing

This is primarily a portfolio project, but if you'd like to contribute or use it as a starting point for your own AI code review system:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## Licence

MIT Licence - feel free to use this as a starting point for your own projects.

## Acknowledgements

- Built with [LangChain](https://langchain.com/) for AI orchestration
- UI components from [shadcn/ui](https://ui.shadcn.com/)
- Inspired by tools like CodeRabbit and GitHub Copilot
- Thanks to the open source community for making this possible

---

**Note**: This is a demonstration project built for portfolio purposes. For production code review needs, consider established tools like CodeRabbit, which offer more comprehensive features and professional support.
