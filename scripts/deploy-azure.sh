#!/bin/bash

# ============================================
# Git Review Assistant - Azure Deployment Script
# ============================================
# Automates deployment to Azure VM
# Usage: ./scripts/deploy-azure.sh <vm-ip-or-hostname> [branch]
# Example: ./scripts/deploy-azure.sh 20.185.123.45 main
# ============================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
VM_USER="${AZURE_VM_USER:-azureuser}"
DEPLOY_DIR="/home/${VM_USER}/Code-Review-Assistant-"
BRANCH="${2:-main}"

# Function to print colored messages
print_info() {
    echo -e "${BLUE}ℹ ${1}${NC}"
}

print_success() {
    echo -e "${GREEN}✓ ${1}${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ ${1}${NC}"
}

print_error() {
    echo -e "${RED}✗ ${1}${NC}"
}

# Check if VM address provided
if [ -z "$1" ]; then
    print_error "Usage: $0 <vm-ip-or-hostname> [branch]"
    print_info "Example: $0 20.185.123.45 main"
    exit 1
fi

VM_ADDRESS="$1"

# Header
echo ""
echo "╔════════════════════════════════════════════╗"
echo "║   Git Review Assistant - Azure Deploy      ║"
echo "╚════════════════════════════════════════════╝"
echo ""
print_info "Target: ${VM_USER}@${VM_ADDRESS}"
print_info "Branch: ${BRANCH}"
print_info "Deploy Directory: ${DEPLOY_DIR}"
echo ""

# Test SSH connection
print_info "Testing SSH connection..."
if ssh -o ConnectTimeout=5 "${VM_USER}@${VM_ADDRESS}" "echo 'SSH connection successful'" > /dev/null 2>&1; then
    print_success "SSH connection established"
else
    print_error "Cannot connect to VM. Check your SSH key and VM address."
    exit 1
fi

# Confirm deployment
read -p "$(echo -e ${YELLOW}Continue with deployment? [y/N]:${NC} )" -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    print_warning "Deployment cancelled"
    exit 0
fi

# Step 1: Update code from Git
print_info "Step 1/8: Pulling latest code from Git..."
ssh "${VM_USER}@${VM_ADDRESS}" << 'ENDSSH'
    cd /home/azureuser/Code-Review-Assistant-
    git fetch --all
    git checkout ${BRANCH}
    git pull origin ${BRANCH}
ENDSSH
print_success "Code updated"

# Step 2: Update backend dependencies
print_info "Step 2/8: Updating backend dependencies..."
ssh "${VM_USER}@${VM_ADDRESS}" << 'ENDSSH'
    cd /home/azureuser/Code-Review-Assistant-/backend
    source .venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
ENDSSH
print_success "Backend dependencies updated"

# Step 3: Update frontend dependencies
print_info "Step 3/8: Updating frontend dependencies..."
ssh "${VM_USER}@${VM_ADDRESS}" << 'ENDSSH'
    cd /home/azureuser/Code-Review-Assistant-
    npm install
ENDSSH
print_success "Frontend dependencies updated"

# Step 4: Build frontend
print_info "Step 4/8: Building frontend (this may take a few minutes)..."
ssh "${VM_USER}@${VM_ADDRESS}" << 'ENDSSH'
    cd /home/azureuser/Code-Review-Assistant-
    npm run build
ENDSSH
print_success "Frontend built successfully"

# Step 5: Restart backend
print_info "Step 5/8: Restarting backend service..."
ssh "${VM_USER}@${VM_ADDRESS}" << 'ENDSSH'
    pm2 restart git-review-backend
ENDSSH
print_success "Backend restarted"

# Step 6: Restart frontend
print_info "Step 6/8: Restarting frontend service..."
ssh "${VM_USER}@${VM_ADDRESS}" << 'ENDSSH'
    pm2 restart git-review-frontend
ENDSSH
print_success "Frontend restarted"

# Step 7: Check PM2 status
print_info "Step 7/8: Checking application status..."
ssh "${VM_USER}@${VM_ADDRESS}" << 'ENDSSH'
    pm2 list
ENDSSH

# Step 8: Test health endpoints
print_info "Step 8/8: Testing application health..."

# Get the domain from VM
DOMAIN=$(ssh "${VM_USER}@${VM_ADDRESS}" "grep NEXT_PUBLIC_APP_URL .env.local | cut -d'=' -f2")

if [ -z "$DOMAIN" ]; then
    print_warning "Could not determine domain. Using VM IP for health check."
    DOMAIN="http://${VM_ADDRESS}"
fi

sleep 5  # Wait for services to fully start

# Test backend health
print_info "Testing backend health..."
if curl -s -f "${DOMAIN}/api/health" > /dev/null 2>&1; then
    print_success "Backend is healthy"
else
    print_warning "Backend health check failed (may be starting up)"
fi

# Test frontend
print_info "Testing frontend..."
if curl -s -f "${DOMAIN}/" > /dev/null 2>&1; then
    print_success "Frontend is accessible"
else
    print_warning "Frontend check failed (may be starting up)"
fi

# Summary
echo ""
echo "╔════════════════════════════════════════════╗"
echo "║        Deployment Complete! 🎉             ║"
echo "╚════════════════════════════════════════════╝"
echo ""
print_success "Application deployed to: ${DOMAIN}"
print_info "Monitor logs with: ssh ${VM_USER}@${VM_ADDRESS} 'pm2 logs'"
print_info "Check status with: ssh ${VM_USER}@${VM_ADDRESS} 'pm2 status'"
echo ""

# Optional: Show recent logs
read -p "$(echo -e ${YELLOW}Show recent logs? [y/N]:${NC} )" -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    print_info "Recent backend logs:"
    ssh "${VM_USER}@${VM_ADDRESS}" "pm2 logs git-review-backend --lines 20 --nostream"
    echo ""
    print_info "Recent frontend logs:"
    ssh "${VM_USER}@${VM_ADDRESS}" "pm2 logs git-review-frontend --lines 20 --nostream"
fi

echo ""
print_success "Deployment script finished!"
echo ""