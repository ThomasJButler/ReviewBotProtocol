#!/bin/bash
# Azure Container Instances Deployment Script
# Git Review Assistant
#
# This script automates the deployment of the Git Review Assistant to Azure Container Instances
#
# Prerequisites:
# 1. Azure CLI installed and logged in (az login)
# 2. Docker installed
# 3. Environment variables set or .env file present
#
# Usage:
#   ./deploy-azure.sh

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
RESOURCE_GROUP="git-review-assistant-rg"
LOCATION="eastus"
ACR_NAME="gitreviewassistant"
BACKEND_IMAGE="${ACR_NAME}.azurecr.io/backend:latest"
FRONTEND_IMAGE="${ACR_NAME}.azurecr.io/frontend:latest"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Git Review Assistant - Azure Deployment${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

if ! command -v az &> /dev/null; then
    echo -e "${RED}Error: Azure CLI not found. Please install it first.${NC}"
    exit 1
fi

if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker not found. Please install it first.${NC}"
    exit 1
fi

# Check if logged in to Azure
if ! az account show &> /dev/null; then
    echo -e "${RED}Error: Not logged in to Azure. Run 'az login' first.${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Prerequisites check passed${NC}"
echo ""

# Create resource group
echo -e "${YELLOW}Creating resource group: ${RESOURCE_GROUP}${NC}"
az group create \
  --name ${RESOURCE_GROUP} \
  --location ${LOCATION} \
  --output none

echo -e "${GREEN}✓ Resource group created${NC}"
echo ""

# Create Azure Container Registry
echo -e "${YELLOW}Creating Azure Container Registry: ${ACR_NAME}${NC}"
az acr create \
  --resource-group ${RESOURCE_GROUP} \
  --name ${ACR_NAME} \
  --sku Basic \
  --admin-enabled true \
  --output none

echo -e "${GREEN}✓ Container registry created${NC}"
echo ""

# Get ACR credentials
echo -e "${YELLOW}Retrieving ACR credentials...${NC}"
ACR_USERNAME=$(az acr credential show --name ${ACR_NAME} --query username --output tsv)
ACR_PASSWORD=$(az acr credential show --name ${ACR_NAME} --query passwords[0].value --output tsv)

echo -e "${GREEN}✓ ACR credentials retrieved${NC}"
echo ""

# Login to ACR
echo -e "${YELLOW}Logging in to ACR...${NC}"
echo ${ACR_PASSWORD} | docker login ${ACR_NAME}.azurecr.io --username ${ACR_USERNAME} --password-stdin

echo -e "${GREEN}✓ Logged in to ACR${NC}"
echo ""

# Build and push backend image
echo -e "${YELLOW}Building backend Docker image...${NC}"
cd backend
docker build -t ${BACKEND_IMAGE} .
cd ..

echo -e "${GREEN}✓ Backend image built${NC}"
echo ""

echo -e "${YELLOW}Pushing backend image to ACR...${NC}"
docker push ${BACKEND_IMAGE}

echo -e "${GREEN}✓ Backend image pushed${NC}"
echo ""

# Build and push frontend image
echo -e "${YELLOW}Building frontend Docker image...${NC}"
docker build -t ${FRONTEND_IMAGE} .

echo -e "${GREEN}✓ Frontend image built${NC}"
echo ""

echo -e "${YELLOW}Pushing frontend image to ACR...${NC}"
docker push ${FRONTEND_IMAGE}

echo -e "${GREEN}✓ Frontend image pushed${NC}"
echo ""

# Load environment variables
echo -e "${YELLOW}Loading environment variables...${NC}"

if [ -f .env ]; then
    export $(cat .env | grep -v '#' | awk '/=/ {print $1}')
    echo -e "${GREEN}✓ Environment variables loaded from .env${NC}"
else
    echo -e "${YELLOW}⚠ No .env file found. Using environment variables.${NC}"
fi

# Verify required environment variables
REQUIRED_VARS="OPENAI_API_KEY LANGCHAIN_API_KEY GITHUB_APP_ID GITHUB_CLIENT_ID GITHUB_CLIENT_SECRET GITHUB_PRIVATE_KEY GITHUB_WEBHOOK_SECRET"

for VAR in $REQUIRED_VARS; do
    if [ -z "${!VAR}" ]; then
        echo -e "${RED}Error: Required environment variable ${VAR} is not set${NC}"
        exit 1
    fi
done

echo -e "${GREEN}✓ All required environment variables present${NC}"
echo ""

# Deploy backend container
echo -e "${YELLOW}Deploying backend container...${NC}"

az container create \
  --resource-group ${RESOURCE_GROUP} \
  --name git-review-backend \
  --image ${BACKEND_IMAGE} \
  --registry-login-server ${ACR_NAME}.azurecr.io \
  --registry-username ${ACR_USERNAME} \
  --registry-password ${ACR_PASSWORD} \
  --dns-name-label git-review-backend-$(date +%s) \
  --ports 8000 \
  --cpu 1 \
  --memory 2 \
  --environment-variables \
    OPENAI_API_KEY=${OPENAI_API_KEY} \
    LANGCHAIN_API_KEY=${LANGCHAIN_API_KEY} \
    LANGCHAIN_PROJECT=git-review-assistant \
    LANGCHAIN_TRACING_V2=true \
    GITHUB_APP_ID=${GITHUB_APP_ID} \
    GITHUB_CLIENT_ID=${GITHUB_CLIENT_ID} \
    GITHUB_CLIENT_SECRET=${GITHUB_CLIENT_SECRET} \
    GITHUB_PRIVATE_KEY="${GITHUB_PRIVATE_KEY}" \
    GITHUB_WEBHOOK_SECRET=${GITHUB_WEBHOOK_SECRET} \
    ENVIRONMENT=production \
    USE_MOCK_REVIEWER=false \
  --output none

BACKEND_FQDN=$(az container show \
  --resource-group ${RESOURCE_GROUP} \
  --name git-review-backend \
  --query ipAddress.fqdn \
  --output tsv)

echo -e "${GREEN}✓ Backend deployed at: https://${BACKEND_FQDN}:8000${NC}"
echo ""

# Deploy frontend container
echo -e "${YELLOW}Deploying frontend container...${NC}"

az container create \
  --resource-group ${RESOURCE_GROUP} \
  --name git-review-frontend \
  --image ${FRONTEND_IMAGE} \
  --registry-login-server ${ACR_NAME}.azurecr.io \
  --registry-username ${ACR_USERNAME} \
  --registry-password ${ACR_PASSWORD} \
  --dns-name-label git-review-frontend-$(date +%s) \
  --ports 3000 \
  --cpu 0.5 \
  --memory 1 \
  --environment-variables \
    NEXT_PUBLIC_APP_URL=https://${FRONTEND_FQDN} \
    NEXT_PUBLIC_API_URL=https://${BACKEND_FQDN}:8000 \
    GITHUB_CLIENT_ID=${GITHUB_CLIENT_ID} \
    GITHUB_CLIENT_SECRET=${GITHUB_CLIENT_SECRET} \
    OPENAI_API_KEY=${OPENAI_API_KEY} \
  --output none

FRONTEND_FQDN=$(az container show \
  --resource-group ${RESOURCE_GROUP} \
  --name git-review-frontend \
  --query ipAddress.fqdn \
  --output tsv)

echo -e "${GREEN}✓ Frontend deployed at: https://${FRONTEND_FQDN}:3000${NC}"
echo ""

# Summary
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Deployment Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${GREEN}Backend URL:${NC}  https://${BACKEND_FQDN}:8000"
echo -e "${GREEN}Frontend URL:${NC} https://${FRONTEND_FQDN}:3000"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "1. Update your GitHub App webhook URL to: https://${BACKEND_FQDN}:8000/api/webhook/github"
echo "2. Update your GitHub App callback URL to: https://${FRONTEND_FQDN}:3000/api/auth/github/callback"
echo "3. Test the deployment by visiting the frontend URL"
echo "4. Create a test PR to verify webhook integration"
echo ""
echo -e "${YELLOW}Cleanup:${NC}"
echo "To delete all resources, run:"
echo "  az group delete --name ${RESOURCE_GROUP} --yes --no-wait"
echo ""
