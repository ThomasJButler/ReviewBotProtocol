# ReviewBot Protocol

> **Portfolio Project**: AI-powered GitHub PR reviews with a custom dashboard.

## What Is This?

ReviewBot Protocol is a full-stack AI code review system that automatically analyses GitHub pull requests and provides intelligent feedback. Think of it as understanding how tools like CodeRabbit work by building one from scratch.

The system catches common issues before human reviewers need to look at the code, saving development time and improving code quality through automated analysis.

Built for the **Codecademy Generative AI & Agents** bootcamp, this project demonstrates:

- LangChain integration with custom chains and prompts
- LangGraph workflows for complex AI processing
- GitHub automation with webhook-driven reviews
- Production-ready error handling and logging
- Full-stack TypeScript/Python development

## Why This Is Useful

**Time Savings**: Automated reviews catch security vulnerabilities, performance issues, and code quality problems instantly, rather than waiting for manual review.

**Learning Through Building**: This project demonstrates how modern AI-powered developer tools actually work under the hood, from webhook integration to LangChain workflows.

**Real-World Application**: Shows integration of multiple complex systems (GitHub API, AI models, full-stack architecture) working together in a practical use case.

## Features

### Automated PR Reviews
- GitHub webhook integration triggers automatic analysis when PRs are opened or updated
- AI-generated inline comments posted directly to pull requests
- Review summary with security, performance, and quality scores

### Custom Dashboard
- Review history and analytics
- GitHub OAuth authentication
- Repository management interface

### AI-Powered Analysis
- **Security**: OWASP Top 10 vulnerabilities, secret detection, dependency analysis
- **Performance**: Algorithm complexity, memory usage, optimisation suggestions
- **Quality**: Code style, best practices, maintainability metrics
- **Documentation**: Missing docs, unclear naming, test coverage gaps

## Tech Stack

**Frontend**
- Next.js 15 with App Router
- TypeScript (strict mode)
- Tailwind CSS with custom cyber/matrix theme
- Shadcn/ui components

**Backend**
- FastAPI (Python 3.11+)
- LangChain + LangGraph for AI workflows
- SQLAlchemy for database operations
- PostgreSQL/SQLite support

**AI Integration**
- OpenAI GPT-4o for code analysis
- Custom LangChain chains for different review types
- LangGraph state machines for complex workflows
- Specialised prompts for security, performance, and quality

**GitHub Integration**
- GitHub API v3/GraphQL
- OAuth authentication flow
- Webhook event processing
- Automated PR commenting

## Licence

MIT Licence

**Note**: This is a portfolio demonstration project. For production code review needs, consider established tools like CodeRabbit, which offer more comprehensive features and professional support.
