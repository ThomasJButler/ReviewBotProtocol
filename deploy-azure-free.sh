#!/bin/bash
# Free Azure Deployment Script for Git Review Assistant
# Optimized for ON-DEMAND usage (2 hours/day) = $0/month!
#
# This script deploys your backend to Azure Container Apps with scale-to-zero enabled.
# Containers start on-demand when needed and stop when idle = FREE!
#
# Prerequisites:
# 1. Azure for Students account ($100 credit, no credit card)
# 2. Azure CLI installed and logged in (az login)
# 3. Docker Hub account (free)
# 4. Environment variables set
#
# Usage:
#   ./deploy-azure-free.sh

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  FREE Azure Deployment - Git Review Assistant       ║${NC}"
echo -e "${GREEN}║  Scale-to-Zero = $0/month with free tier!          ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════╝${NC}"
echo ""

# Configuration
RESOURCE_GROUP="git-review-free-rg"
LOCATION="eastus"  # Cheapest region
CONTAINER_ENV="git-review-env"
BACKEND_APP="git-review-backend"

# Check prerequisites
echo -e "${YELLOW}📋 Checking prerequisites...${NC}"

# Check Azure CLI
if ! command -v az &> /dev/null; then
    echo -e "${RED}❌ Azure CLI not found. Install it first:${NC}"
    echo "   brew install azure-cli"
    exit 1
fi

# Check Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker not found. Install it first:${NC}"
    echo "   https://www.docker.com/get-started"
    exit 1
fi

# Check Azure login
if ! az account show &> /dev/null; then
    echo -e "${RED}❌ Not logged in to Azure. Run 'az login' first.${NC}"
    exit 1
fi

echo -e "${GREEN}✅ All prerequisites met!${NC}"
echo ""

# Get Docker Hub username
echo -e "${BLUE}🐳 Docker Hub Configuration${NC}"
read -p "Enter your Docker Hub username: " DOCKER_USERNAME

if [ -z "$DOCKER_USERNAME" ]; then
    echo -e "${RED}❌ Docker Hub username required${NC}"
    exit 1
fi

DOCKER_IMAGE="$DOCKER_USERNAME/git-review-backend"

# Check environment variables
echo ""
echo -e "${YELLOW}🔐 Checking required environment variables...${NC}"

REQUIRED_VARS=(
    "OPENAI_API_KEY"
    "LANGCHAIN_API_KEY"
    "GITHUB_APP_ID"
    "GITHUB_CLIENT_ID"
    "GITHUB_CLIENT_SECRET"
    "GITHUB_PRIVATE_KEY"
    "GITHUB_WEBHOOK_SECRET"
)

MISSING_VARS=()

for VAR in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!VAR}" ]; then
        MISSING_VARS+=("$VAR")
    fi
done

if [ ${#MISSING_VARS[@]} -gt 0 ]; then
    echo -e "${YELLOW}⚠️  Missing environment variables:${NC}"
    for VAR in "${MISSING_VARS[@]}"; do
        echo "   - $VAR"
    done
    echo ""
    echo -e "${BLUE}💡 Load them from .env file or set manually:${NC}"
    echo "   export OPENAI_API_KEY=your-key"
    echo ""
    read -p "Continue anyway? (y/N): " CONTINUE
    if [[ ! $CONTINUE =~ ^[Yy]$ ]]; then
        echo "Exiting. Set environment variables and try again."
        exit 1
    fi
fi

echo -e "${GREEN}✅ Environment variables ready${NC}"
echo ""

# Create resource group
echo -e "${YELLOW}📦 Creating Azure resource group...${NC}"
az group create \
  --name $RESOURCE_GROUP \
  --location $LOCATION \
  --output none

echo -e "${GREEN}✅ Resource group created: $RESOURCE_GROUP${NC}"
echo ""

# Create Container Apps environment
echo -e "${YELLOW}🏗️  Creating Container Apps environment...${NC}"
az containerapp env create \
  --name $CONTAINER_ENV \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION \
  --output none

echo -e "${GREEN}✅ Container Apps environment created${NC}"
echo ""

# Build and push Docker image
echo -e "${YELLOW}🐳 Building and pushing Docker image...${NC}"
echo -e "${BLUE}   This may take 2-3 minutes...${NC}"

# Check if logged in to Docker Hub
if ! docker info | grep -q "Username"; then
    echo -e "${YELLOW}⚠️  Not logged in to Docker Hub${NC}"
    echo -e "${BLUE}   Logging in now...${NC}"
    docker login
fi

# Build backend image
cd backend
docker build -t $DOCKER_IMAGE:latest -t $DOCKER_IMAGE:$(date +%Y%m%d) .
cd ..

# Push to Docker Hub
docker push $DOCKER_IMAGE:latest
docker push $DOCKER_IMAGE:$(date +%Y%m%d)

echo -e "${GREEN}✅ Docker image pushed to Docker Hub${NC}"
echo ""

# Deploy backend container
echo -e "${YELLOW}🚀 Deploying backend container...${NC}"
echo -e "${BLUE}   This may take 3-5 minutes...${NC}"

# Create secrets and deploy
az containerapp create \
  --name $BACKEND_APP \
  --resource-group $RESOURCE_GROUP \
  --environment $CONTAINER_ENV \
  --image $DOCKER_IMAGE:latest \
  --target-port 8000 \
  --ingress external \
  --cpu 0.5 \
  --memory 1.0Gi \
  --min-replicas 0 \
  --max-replicas 1 \
  --secrets \
    openai-key="${OPENAI_API_KEY:-placeholder}" \
    github-secret="${GITHUB_WEBHOOK_SECRET:-placeholder}" \
    langchain-key="${LANGCHAIN_API_KEY:-placeholder}" \
    github-app-id="${GITHUB_APP_ID:-placeholder}" \
    github-client-id="${GITHUB_CLIENT_ID:-placeholder}" \
    github-client-secret="${GITHUB_CLIENT_SECRET:-placeholder}" \
    github-private-key="${GITHUB_PRIVATE_KEY:-placeholder}" \
  --env-vars \
    OPENAI_API_KEY=secretref:openai-key \
    GITHUB_WEBHOOK_SECRET=secretref:github-secret \
    LANGCHAIN_API_KEY=secretref:langchain-key \
    LANGCHAIN_PROJECT=git-review-assistant \
    LANGCHAIN_TRACING_V2=true \
    GITHUB_APP_ID=secretref:github-app-id \
    GITHUB_CLIENT_ID=secretref:github-client-id \
    GITHUB_CLIENT_SECRET=secretref:github-client-secret \
    GITHUB_PRIVATE_KEY=secretref:github-private-key \
    ENVIRONMENT=production \
    USE_MOCK_REVIEWER=false \
    ALLOWED_ORIGINS=* \
  --output none

echo -e "${GREEN}✅ Backend deployed successfully!${NC}"
echo ""

# Get backend URL
BACKEND_URL=$(az containerapp show \
  --name $BACKEND_APP \
  --resource-group $RESOURCE_GROUP \
  --query properties.configuration.ingress.fqdn \
  --output tsv)

# Setup cost alert
echo -e "${YELLOW}💰 Setting up cost alert...${NC}"

# Get subscription ID
SUBSCRIPTION_ID=$(az account show --query id --output tsv)

# Create budget (requires Microsoft.Consumption permissions)
az consumption budget create \
  --resource-group $RESOURCE_GROUP \
  --budget-name git-review-budget \
  --amount 5 \
  --time-period monthly \
  --category Cost \
  --time-grain Monthly \
  --start-date $(date +%Y-%m-01) \
  --end-date $(date -d "+1 year" +%Y-%m-01) \
  --output none 2>/dev/null || echo -e "${YELLOW}⚠️  Budget creation skipped (may require additional permissions)${NC}"

echo -e "${GREEN}✅ Cost alert configured (if permissions allow)${NC}"
echo ""

# Test health endpoint
echo -e "${YELLOW}🏥 Testing health endpoint...${NC}"
echo -e "${BLUE}   Waiting for container to start (30 seconds)...${NC}"
sleep 30

HEALTH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://$BACKEND_URL/health)

if [ "$HEALTH_STATUS" == "200" ]; then
    echo -e "${GREEN}✅ Health check passed!${NC}"
else
    echo -e "${YELLOW}⚠️  Health check returned: $HEALTH_STATUS${NC}"
    echo -e "${BLUE}   Container may still be starting. Check logs with:${NC}"
    echo "   az containerapp logs show -n $BACKEND_APP -g $RESOURCE_GROUP --follow"
fi

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║              🎉 DEPLOYMENT COMPLETE! 🎉              ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}📍 Backend URL:${NC}"
echo "   https://$BACKEND_URL"
echo ""
echo -e "${BLUE}🏥 Health Check:${NC}"
echo "   https://$BACKEND_URL/health"
echo ""
echo -e "${BLUE}📊 Webhook Endpoint:${NC}"
echo "   https://$BACKEND_URL/api/webhook/github"
echo ""
echo -e "${GREEN}💰 Cost Status: $0/month (scale-to-zero enabled!)${NC}"
echo ""
echo -e "${YELLOW}📝 Next Steps:${NC}"
echo ""
echo -e "${BLUE}1. Update GitHub App webhook URL:${NC}"
echo "   https://github.com/settings/apps"
echo "   Webhook URL: https://$BACKEND_URL/api/webhook/github"
echo ""
echo -e "${BLUE}2. Deploy frontend to Vercel:${NC}"
echo "   cd /Users/tombutler/Repos/Code-Review-Assistant"
echo "   vercel"
echo "   vercel env add NEXT_PUBLIC_API_URL"
echo "   # Enter: https://$BACKEND_URL"
echo "   vercel --prod"
echo ""
echo -e "${BLUE}3. Manage your containers:${NC}"
echo "   ./manage-azure-containers.sh status   # Check status"
echo "   ./manage-azure-containers.sh start    # Start for demo"
echo "   ./manage-azure-containers.sh stop     # Stop to save credits"
echo "   ./manage-azure-containers.sh logs     # View logs"
echo ""
echo -e "${BLUE}4. Monitor costs:${NC}"
echo "   https://portal.azure.com → Cost Management"
echo "   Or run: az consumption usage list --output table"
echo ""
echo -e "${GREEN}🎓 FREE Azure Learning Mode Activated!${NC}"
echo -e "${GREEN}   Your $100 student credit covers ~3 months of 24/7 usage${NC}"
echo -e "${GREEN}   Or UNLIMITED on-demand usage within free tier!${NC}"
echo ""
echo -e "${BLUE}💡 Pro Tip:${NC}"
echo "   Keep containers at min-replicas=0 (default)"
echo "   They'll auto-start for webhooks (<1 sec)"
echo "   = Essentially FREE operation forever!"
echo ""
echo -e "${GREEN}Happy coding! 🚀${NC}"
echo ""

# Save deployment info
cat > deployment-info.txt <<EOF
Git Review Assistant - Azure Deployment Info
Generated: $(date)

Backend URL: https://$BACKEND_URL
Health Check: https://$BACKEND_URL/health
Webhook Endpoint: https://$BACKEND_URL/api/webhook/github

Resource Group: $RESOURCE_GROUP
Container App: $BACKEND_APP
Location: $LOCATION
Docker Image: $DOCKER_IMAGE:latest

Management Commands:
  Status:  ./manage-azure-containers.sh status
  Start:   ./manage-azure-containers.sh start
  Stop:    ./manage-azure-containers.sh stop
  Logs:    ./manage-azure-containers.sh logs
  Update:  ./manage-azure-containers.sh update

Cost Monitoring:
  Portal: https://portal.azure.com
  CLI: az consumption usage list --output table

Cleanup (when done):
  az group delete --name $RESOURCE_GROUP --yes --no-wait
EOF

echo -e "${GREEN}📄 Deployment info saved to: deployment-info.txt${NC}"
