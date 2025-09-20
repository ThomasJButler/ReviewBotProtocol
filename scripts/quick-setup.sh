#!/bin/bash

# Git Review Assistant - Quick Setup Script
# This script helps you set up the environment quickly for testing

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Helper functions
log_header() {
    echo -e "\n${BOLD}${CYAN}=== $1 ===${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Check if running from project root
if [ ! -f "package.json" ]; then
    log_error "Please run this script from the project root directory"
    exit 1
fi

log_header "Git Review Assistant - Quick Setup"

# 1. Copy environment files
log_header "Setting up environment files"

if [ ! -f ".env.local" ]; then
    cp .env.example .env.local
    log_success "Created .env.local from template"
else
    log_warning ".env.local already exists - skipping"
fi

if [ ! -f "backend/.env" ]; then
    cp backend/.env.example backend/.env
    log_success "Created backend/.env from template"
else
    log_warning "backend/.env already exists - skipping"
fi

# 2. Generate random secrets
log_header "Generating secure random keys"

NEXTAUTH_SECRET=$(openssl rand -base64 32)
WEBHOOK_SECRET=$(openssl rand -base64 24)
BACKEND_SECRET=$(openssl rand -hex 32)

log_success "Generated NextAuth secret: ${NEXTAUTH_SECRET}"
log_success "Generated webhook secret: ${WEBHOOK_SECRET}"
log_success "Generated backend secret: ${BACKEND_SECRET}"

# 3. Update environment files with generated secrets
log_header "Updating environment files"

# Update .env.local
sed -i.bak "s/NEXTAUTH_SECRET=.*/NEXTAUTH_SECRET=${NEXTAUTH_SECRET}/" .env.local
sed -i.bak "s/GITHUB_WEBHOOK_SECRET=.*/GITHUB_WEBHOOK_SECRET=${WEBHOOK_SECRET}/" .env.local
log_success "Updated .env.local with generated secrets"

# Update backend/.env
sed -i.bak "s/SECRET_KEY=.*/SECRET_KEY=${BACKEND_SECRET}/" backend/.env
sed -i.bak "s/GITHUB_WEBHOOK_SECRET=.*/GITHUB_WEBHOOK_SECRET=${WEBHOOK_SECRET}/" backend/.env
log_success "Updated backend/.env with generated secrets"

# Clean up backup files
rm -f .env.local.bak backend/.env.bak

# 4. Install dependencies
log_header "Installing dependencies"

if command -v npm &> /dev/null; then
    log_info "Installing Node.js dependencies..."
    npm install
    log_success "Node.js dependencies installed"
else
    log_error "npm not found - please install Node.js"
    exit 1
fi

# Check for Python and install backend dependencies
if command -v python3 &> /dev/null; then
    log_info "Installing Python dependencies..."
    cd backend

    # Create virtual environment if it doesn't exist
    if [ ! -d ".venv" ]; then
        python3 -m venv .venv
        log_success "Created Python virtual environment"
    fi

    # Activate virtual environment and install dependencies
    source .venv/bin/activate
    pip install -r requirements.txt
    log_success "Python dependencies installed"
    cd ..
else
    log_warning "python3 not found - backend dependencies not installed"
fi

# 5. Show next steps
log_header "Setup Complete! Next Steps:"

echo -e "${YELLOW}🔑 You still need to configure these API keys:${NC}"
echo -e "   1. ${BOLD}OpenAI API Key${NC} - Get from: https://platform.openai.com/api-keys"
echo -e "   2. ${BOLD}GitHub App credentials${NC} - Create at: https://github.com/settings/apps"
echo -e ""
echo -e "${BLUE}📝 Edit these files with your real API keys:${NC}"
echo -e "   - ${BOLD}.env.local${NC} (frontend environment)"
echo -e "   - ${BOLD}backend/.env${NC} (backend environment)"
echo -e ""
echo -e "${GREEN}🚀 Test your setup:${NC}"
echo -e "   ${BOLD}node scripts/validate-env.js${NC}  # Validate configuration"
echo -e "   ${BOLD}npm run dev${NC}                   # Start development server"
echo -e ""
echo -e "${CYAN}📚 For GitHub App setup guide, see:${NC}"
echo -e "   ${BOLD}backend/DEPLOYMENT_PLAN.md${NC}"

log_success "Quick setup completed successfully!"