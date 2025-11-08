# ReviewBot Protocol

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

## Core Feature

1. **GitHub PR Review**: Automated Custom PR analysis with inline comments (like CodeRabbit)

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
- Specialised prompts for security, performance, and quality analysis

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

## Course Context

This project was built as part of the **"Codecademy Mastering Generative AI & Agents for Developers"** bootcamp, demonstrating:

- LangChain integration with custom chains and prompts
- LangGraph workflows for complex AI processing
- GitHub automation with webhook-driven reviews
- Multi-modal input handling (paste, upload, GitHub)
- Production-ready deployment with proper error handling

## Licence

MIT Licence - feel free to use this as a starting point for your own projects.

**Note**: This is a demonstration project built for portfolio purposes. For production code review needs, consider established tools like CodeRabbit, which offer more comprehensive features and professional support.
