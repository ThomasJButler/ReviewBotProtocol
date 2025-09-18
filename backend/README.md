# Git Review Assistant Backend

FastAPI backend for the Git Review Assistant - an AI-powered code review system with GitHub integration.

## Features

- **GitHub Integration**: Webhook-driven PR reviews with automated inline comments
- **AI-Powered Analysis**: LangChain + OpenAI GPT-4o for intelligent code reviews
- **Security Scanning**: OWASP Top 10 vulnerability detection
- **Performance Analysis**: Algorithm complexity and optimization suggestions
- **Quality Assessment**: Code maintainability and best practices
- **Background Processing**: Async queue system for handling multiple reviews
- **Rate Limiting**: GitHub API rate limiting and user quotas
- **Database Storage**: Review history and metrics tracking

## Architecture

```
backend/
├── main.py                  # FastAPI app entry point
├── config/                  # Configuration and logging
├── handlers/               # API route handlers
├── services/               # Business logic services
├── models/                 # Pydantic models
├── database/               # Database models and repositories
└── utils/                  # Utility functions
```

## Quick Start

### Prerequisites

- Python 3.11+
- Redis (for background processing)
- PostgreSQL (optional, defaults to SQLite)
- GitHub App credentials
- OpenAI API key

### Installation

1. **Clone and navigate to backend**:

   ```bash
   cd backend
   ```

2. **Run the automated setup script**:

   ```bash
   ./setup.sh
   ```

   Or manually create virtual environment:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # Linux/Mac
   # or
   .venv\Scripts\activate     # Windows
   ```

3. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**:

   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Run the application**:
   ```bash
   python main.py
   ```

The API will be available at `http://localhost:8000`

### Docker Setup

1. **Using Docker Compose** (recommended):

   ```bash
   docker-compose up -d
   ```

2. **Using Docker only**:
   ```bash
   docker build -t git-review-assistant-backend .
   docker run -p 8000:8000 --env-file .env git-review-assistant-backend
   ```

## Configuration

### Required Environment Variables

```bash
# GitHub App Configuration
GITHUB_APP_ID="your-app-id"
GITHUB_PRIVATE_KEY="your-private-key"
GITHUB_WEBHOOK_SECRET="your-webhook-secret"

# OpenAI Configuration
OPENAI_API_KEY="sk-your-api-key"

# LangChain Configuration (Course Requirements)
LANGCHAIN_API_KEY="ls__your-langsmith-key"
```

### Optional Configuration

```bash
# Database (defaults to SQLite)
DATABASE_URL="postgresql+asyncpg://user:pass@localhost/db"

# Redis (for background processing)
REDIS_URL="redis://localhost:6379"

# Security
SECRET_KEY="your-secret-key"
```

## API Endpoints

### Health & Status

- `GET /health` - Basic health check
- `GET /health/detailed` - Detailed health with dependency status
- `GET /metrics` - Application metrics

### Webhooks

- `POST /webhook/github` - GitHub webhook endpoint

### Reviews

- `POST /review/manual` - Manual code review
- `POST /review/files` - Multi-file review
- `POST /review/pr` - GitHub PR review
- `GET /review/{id}` - Get review results
- `GET /review/` - List reviews
- `GET /review/stats/overview` - Review statistics

### Authentication

- `GET /auth/github/login` - GitHub OAuth login URL
- `POST /auth/github/callback` - GitHub OAuth callback
- `POST /auth/token` - Create access token
- `GET /auth/me` - Current user info

## GitHub App Setup

1. **Create GitHub App**:
   - Go to GitHub Settings > Developer settings > GitHub Apps
   - Click "New GitHub App"

2. **Configure App**:

   ```
   App name: Git Review Assistant
   Homepage URL: https://your-app.com
   Webhook URL: https://your-api.com/webhook/github
   Webhook secret: [generate secure secret]
   ```

3. **Set Permissions**:
   - Repository permissions:
     - Pull requests: Read & Write
     - Contents: Read
     - Issues: Write
     - Metadata: Read

4. **Subscribe to Events**:
   - Pull request
   - Pull request review
   - Pull request review comment

5. **Generate and Download Private Key**

6. **Install App** on target repositories

## LangChain Integration

The backend uses LangChain for AI-powered code analysis:

```python
# Security Analysis Chain
security_chain = LLMChain(
    llm=ChatOpenAI(model="gpt-4o"),
    prompt=security_prompt,
    output_key="security_analysis"
)

# Performance Analysis Chain
performance_chain = LLMChain(
    llm=ChatOpenAI(model="gpt-4o"),
    prompt=performance_prompt,
    output_key="performance_analysis"
)
```

### LangSmith Monitoring

Set up LangSmith for tracing and monitoring:

```bash
LANGCHAIN_API_KEY="ls__your-key"
LANGCHAIN_PROJECT="git-review-assistant"
LANGCHAIN_TRACING_V2=true
```

## Background Processing

The system uses Redis for background job processing:

```python
# Add review to queue
await add_review_to_queue(
    review_request=analysis_request,
    installation_id=installation_id,
    priority="high"
)

# Start background workers
await queue_processor.start_workers(num_workers=2)
```

## Security Features

### Vulnerability Scanning

Built-in security scanner detects:

- SQL Injection vulnerabilities
- XSS vulnerabilities
- Command Injection
- Path Traversal
- Hardcoded secrets
- Weak cryptography
- And more...

### Authentication

- JWT-based authentication
- GitHub OAuth integration
- API key authentication
- Rate limiting per user

### Webhook Security

- GitHub webhook signature verification
- Request timeout handling
- Payload size limits

## Database Schema

### Reviews Table

```sql
CREATE TABLE reviews (
    id UUID PRIMARY KEY,
    type VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL,
    repository VARCHAR(255),
    pr_number INTEGER,
    overall_score FLOAT,
    total_issues INTEGER,
    created_at TIMESTAMP,
    completed_at TIMESTAMP,
    processing_time FLOAT
);
```

### Review Issues Table

```sql
CREATE TABLE review_issues (
    id UUID PRIMARY KEY,
    review_id UUID REFERENCES reviews(id),
    category VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    file_path VARCHAR(512),
    line_number INTEGER,
    suggestion TEXT
);
```

## Deployment

### Railway Deployment

1. **Connect Repository**:
   - Link GitHub repository to Railway
   - Set root directory to `/backend`

2. **Environment Variables**:

   ```bash
   GITHUB_APP_ID=your-app-id
   GITHUB_PRIVATE_KEY=your-private-key
   GITHUB_WEBHOOK_SECRET=your-webhook-secret
   OPENAI_API_KEY=sk-your-api-key
   SECRET_KEY=your-secret-key
   ```

3. **Add Database**:
   - Add PostgreSQL plugin
   - DATABASE_URL will be set automatically

4. **Add Redis**:
   - Add Redis plugin
   - REDIS_URL will be set automatically

### Render Deployment

1. **Create Web Service**:
   - Connect GitHub repository
   - Set build command: `pip install -r requirements.txt`
   - Set start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`

2. **Environment Variables**:
   - Add all required environment variables
   - Add database and Redis add-ons

## Development

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html
```

### Code Quality

```bash
# Format code
black .
isort .

# Lint code
flake8 .
mypy .

# Security audit
bandit -r .
safety check
```

### Database Migrations

```bash
# Create migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Downgrade
alembic downgrade -1
```

## Monitoring & Logging

### Structured Logging

```python
from config.logging import get_logger

logger = get_logger(__name__)
logger.info("Review started", repository="owner/repo", pr_number=123)
```

### Health Checks

- `/health` - Basic health check
- `/health/detailed` - Database, GitHub API, and AI service status
- `/metrics` - Prometheus-compatible metrics

### Sentry Integration

Set `SENTRY_DSN` for error tracking and performance monitoring.

## API Rate Limits

- GitHub API: 5,000 requests/hour (authenticated)
- OpenAI API: Based on your plan
- Review API: 100 requests/hour per user

## Contributing

1. Fork the repository
2. Create feature branch
3. Make changes with tests
4. Submit pull request

## License

See LICENSE file in the project root.

## Support

For issues and questions:

- GitHub Issues: [Repository Issues](https://github.com/your-username/git-review-assistant/issues)
- Documentation: [Project Wiki](https://github.com/your-username/git-review-assistant/wiki)
