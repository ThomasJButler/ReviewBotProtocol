#!/bin/bash

# Git Review Assistant Backend Setup Script
# This script sets up the Python virtual environment and installs dependencies

set -e  # Exit on any error

echo "🚀 Setting up Git Review Assistant Backend..."

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed."
    echo "Please install Python 3.8 or later and try again."
    exit 1
fi

# Check Python version
PYTHON_VERSION=$(python3 -c "import sys; print('.'.join(map(str, sys.version_info[:2])))")
echo "📍 Found Python $PYTHON_VERSION"

# Check if we're in the backend directory
if [ ! -f "requirements.txt" ]; then
    echo "❌ requirements.txt not found. Please run this script from the backend directory."
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "📦 Creating Python virtual environment..."
    python3 -m venv .venv
else
    echo "✅ Virtual environment already exists"
fi

# Activate virtual environment
echo "🔄 Activating virtual environment..."
source .venv/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "📚 Installing dependencies..."
pip install -r requirements.txt

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "⚙️  Creating .env file from template..."
    cat > .env << 'EOF'
# Git Review Assistant Backend Configuration

# Application Settings
DEBUG=true
SECRET_KEY=your-secret-key-here-change-in-production
HOST=0.0.0.0
PORT=8000

# GitHub Configuration (Required)
GITHUB_APP_ID=your-github-app-id
GITHUB_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\nyour-github-private-key-here\n-----END RSA PRIVATE KEY-----"
GITHUB_WEBHOOK_SECRET=your-webhook-secret-here
GITHUB_CLIENT_ID=your-github-client-id
GITHUB_CLIENT_SECRET=your-github-client-secret

# OpenAI Configuration (Required)
OPENAI_API_KEY=sk-your-openai-api-key-here
OPENAI_MODEL=gpt-4-turbo-preview
OPENAI_MAX_TOKENS=4000

# LangChain Configuration (Optional but recommended)
LANGCHAIN_API_KEY=ls__your-langchain-api-key-here
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=git-review-assistant

# Database Configuration
DATABASE_URL=sqlite:///./git_review_assistant.db

# Redis Configuration (for background jobs)
REDIS_URL=redis://localhost:6379/0

# Monitoring (Optional)
SENTRY_DSN=https://your-sentry-dsn-here

# CORS Origins (adjust for your frontend)
ALLOWED_ORIGINS=["http://localhost:3000", "https://*.vercel.app"]
EOF
    echo "📝 Created .env file - please update with your actual credentials"
else
    echo "✅ .env file already exists"
fi

echo ""
echo "✨ Backend setup complete!"
echo ""
echo "📋 Next steps:"
echo "1. Update the .env file with your actual API keys and credentials"
echo "2. Start the development server with:"
echo "   source .venv/bin/activate"
echo "   python main.py"
echo ""
echo "🔗 The API will be available at: http://localhost:8000"
echo "📖 API documentation will be available at: http://localhost:8000/docs"
echo ""
echo "🛠️  For production deployment, see the README.md file"