# 🎓 FREE Azure Deployment Guide - Git Review Assistant

**Deploy your Docker containers to Azure for FREE using student credits and free tiers!**

---

## 🎯 Cost: $0/month Strategy

This guide shows you how to deploy your Git Review Assistant to Azure **completely free** for learning purposes.

### The Free Stack

```
Frontend  → Vercel (Free Tier)           = $0/month
Backend   → Azure Container Apps (Free)  = $0/month
Redis     → UpStash (Free Tier)          = $0/month
Registry  → Docker Hub (Free Tier)       = $0/month
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TOTAL                                    = $0/month
```

---

## 📋 Table of Contents

1. [Get Azure for Students ($100 Credit)](#1-get-azure-for-students)
2. [Setup Azure CLI](#2-setup-azure-cli)
3. [Deploy Backend to Azure Container Apps](#3-deploy-backend)
4. [Deploy Frontend to Vercel](#4-deploy-frontend)
5. [Configure GitHub Webhooks](#5-configure-github-webhooks)
6. [Monitor Costs & Usage](#6-monitor-costs)
7. [Scale Up/Down as Needed](#7-manage-containers)
8. [Troubleshooting](#8-troubleshooting)

---

## 1. Get Azure for Students

### Option A: Azure for Students (BEST - No Credit Card!)

**Benefits:**

- ✅ $100 credit for 12 months
- ✅ Renewable annually until graduation
- ✅ NO credit card required
- ✅ Access to 25+ free services
- ✅ Free Azure Certification courses

**How to Sign Up:**

1. Visit: https://azure.microsoft.com/en-us/free/students

2. Click "Activate Now"

3. Sign in with your school email (.edu address)
   - If you don't have .edu email, use your student portal account

4. Verify your academic status
   - May require uploading proof (student ID, enrollment letter)
   - Usually approved within 24 hours

5. Start using immediately!
   - No credit card needed
   - $100 credit appears instantly

**Verification Methods:**

- School email domain (@university.edu)
- Student document upload (ID card, transcript)
- ISIC card (International Student Identity Card)
- GitHub Student Developer Pack verification

### Option B: GitHub Student Developer Pack

**Benefits:**

- ✅ $100 Azure credit (one-time)
- ✅ Plus other developer tools
- ✅ Access to GitHub Codespaces

**How to Get:**

1. Apply at: https://education.github.com/pack
2. Verify student status
3. Find Microsoft Azure in the pack
4. Activate your Azure credit

**Note:** Cannot be combined with Azure for Students (choose one)

### Option C: Azure Free Trial (Requires Credit Card)

**If you're not a student:**

- $200 credit for 30 days
- 12 months of free services
- Requires credit card (won't charge without consent)

---

## 2. Setup Azure CLI

### Install Azure CLI

**macOS:**

```bash
brew install azure-cli
```

**Linux:**

```bash
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
```

**Windows:**

```powershell
# Download and run installer from:
# https://aka.ms/installazurecliwindows
```

### Login to Azure

```bash
# Login with browser authentication
az login

# If you have multiple subscriptions, list them
az account list --output table

# Set your Azure for Students subscription (if multiple)
az account set --subscription "Azure for Students"

# Verify you're in the right subscription
az account show --output table
```

### Verify Free Credits

```bash
# Check your credit balance (if applicable)
# Go to: https://www.microsoftazuresponsorships.com/Balance
```

---

## 3. Deploy Backend

### Quick Deployment (Automated Script)

**Use the provided script for one-command deployment:**

```bash
# Make script executable
chmod +x deploy-azure-free.sh

# Run deployment
./deploy-azure-free.sh
```

The script will:

1. Create resource group
2. Create Container Apps environment
3. Build and push Docker image to Docker Hub
4. Deploy backend with scale-to-zero enabled
5. Setup cost alerts
6. Output your backend URL

**Expected time:** 5-10 minutes

---

### Manual Deployment (Step by Step)

If you prefer to understand each step:

#### Step 1: Set Variables

```bash
# Configuration
RESOURCE_GROUP="git-review-free-rg"
LOCATION="eastus"  # Cheapest region
CONTAINER_ENV="git-review-env"
BACKEND_APP="git-review-backend"
DOCKER_USERNAME="your-dockerhub-username"
DOCKER_IMAGE="$DOCKER_USERNAME/git-review-backend"
```

#### Step 2: Create Azure Resources

```bash
# Create resource group
az group create \
  --name $RESOURCE_GROUP \
  --location $LOCATION

echo "✅ Resource group created"

# Create Container Apps environment
# This enables running multiple container apps
az containerapp env create \
  --name $CONTAINER_ENV \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION

echo "✅ Container Apps environment created"
```

**Cost:** Free (included in subscription)

#### Step 3: Build and Push Docker Image

**Using Docker Hub (FREE):**

```bash
# Login to Docker Hub (create free account at hub.docker.com)
docker login

# Build backend image
cd backend
docker build -t $DOCKER_IMAGE:latest .
cd ..

# Push to Docker Hub
docker push $DOCKER_IMAGE:latest

echo "✅ Docker image pushed to Docker Hub"
```

**Alternative: Build directly in Azure (uses credits):**

```bash
# If you have Azure Container Registry (costs ~$5/month)
# Skip this if using Docker Hub!

ACR_NAME="gitreviewacr$RANDOM"
az acr create \
  --resource-group $RESOURCE_GROUP \
  --name $ACR_NAME \
  --sku Basic

az acr build \
  --registry $ACR_NAME \
  --image git-review-backend:latest \
  --file backend/Dockerfile \
  backend/
```

#### Step 4: Deploy Backend Container

```bash
# Deploy with scale-to-zero enabled
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
    openai-key=$OPENAI_API_KEY \
    github-secret=$GITHUB_WEBHOOK_SECRET \
    langchain-key=$LANGCHAIN_API_KEY \
    github-app-id=$GITHUB_APP_ID \
    github-client-id=$GITHUB_CLIENT_ID \
    github-client-secret=$GITHUB_CLIENT_SECRET \
    github-private-key="$GITHUB_PRIVATE_KEY" \
  --env-vars \
    OPENAI_API_KEY=secretref:openai-key \
    GITHUB_WEBHOOK_SECRET=secretref:github-secret \
    LANGCHAIN_API_KEY=secretref:langchain-key \
    GITHUB_APP_ID=secretref:github-app-id \
    GITHUB_CLIENT_ID=secretref:github-client-id \
    GITHUB_CLIENT_SECRET=secretref:github-client-secret \
    GITHUB_PRIVATE_KEY=secretref:github-private-key \
    ENVIRONMENT=production \
    USE_MOCK_REVIEWER=false

echo "✅ Backend deployed!"
```

**Key Configuration Explained:**

- `--min-replicas 0`: **Scale to zero** = no cost when idle!
- `--max-replicas 1`: Limit to 1 instance (keep costs low)
- `--cpu 0.5`: Half vCPU (plenty for webhooks, cheaper)
- `--memory 1.0Gi`: 1GB RAM
- `--ingress external`: Public endpoint for GitHub webhooks

#### Step 5: Get Backend URL

```bash
# Get your backend URL
BACKEND_URL=$(az containerapp show \
  --name $BACKEND_APP \
  --resource-group $RESOURCE_GROUP \
  --query properties.configuration.ingress.fqdn \
  --output tsv)

echo "🎉 Backend URL: https://$BACKEND_URL"
echo "🎉 Health Check: https://$BACKEND_URL/health"

# Test health endpoint
curl https://$BACKEND_URL/health
```

**Expected Response:**

```json
{ "status": "healthy" }
```

#### Step 6: Deploy Redis (Optional)

**Option A: Azure Container Apps (uses credits)**

```bash
az containerapp create \
  --name git-review-redis \
  --resource-group $RESOURCE_GROUP \
  --environment $CONTAINER_ENV \
  --image redis:7-alpine \
  --target-port 6379 \
  --ingress internal \
  --cpu 0.25 \
  --memory 0.5Gi \
  --min-replicas 0 \
  --max-replicas 1

# Get Redis URL
REDIS_URL=$(az containerapp show \
  --name git-review-redis \
  --resource-group $RESOURCE_GROUP \
  --query properties.configuration.ingress.fqdn \
  --output tsv)

echo "Redis URL: redis://$REDIS_URL:6379"
```

**Option B: UpStash (FREE, Recommended)**

1. Sign up at: https://upstash.com
2. Create Redis database (free tier: 10K commands/day)
3. Copy connection URL
4. Update backend environment:

```bash
az containerapp update \
  --name $BACKEND_APP \
  --resource-group $RESOURCE_GROUP \
  --set-env-vars REDIS_URL="redis://your-upstash-url:6379"
```

---

## 4. Deploy Frontend

### Deploy to Vercel (FREE)

```bash
# Install Vercel CLI
npm install -g vercel

# Navigate to project root
cd /Users/tombutler/Repos/Code-Review-Assistant

# Login to Vercel
vercel login

# Deploy
vercel

# Follow prompts:
# - Link to existing project? No
# - Project name? git-review-assistant
# - Directory? ./
# - Override settings? No
```

### Set Environment Variables

```bash
# Backend API URL (from Azure)
vercel env add NEXT_PUBLIC_API_URL
# Enter: https://your-backend.azurecontainerapps.io

# App URL (will be provided by Vercel)
vercel env add NEXT_PUBLIC_APP_URL
# Enter: https://your-app.vercel.app

# GitHub OAuth
vercel env add GITHUB_CLIENT_ID
vercel env add GITHUB_CLIENT_SECRET

# OpenAI (for frontend API routes)
vercel env add OPENAI_API_KEY
```

### Deploy to Production

```bash
vercel --prod
```

**Your frontend URL:** https://your-app.vercel.app

---

## 5. Configure GitHub Webhooks

### Create GitHub App

1. Go to: https://github.com/settings/apps

2. Click "New GitHub App"

3. Fill in details:

   ```
   GitHub App name: git-review-assistant-[your-name]
   Homepage URL: https://your-app.vercel.app
   Webhook URL: https://your-backend.azurecontainerapps.io/api/webhook/github
   Webhook secret: [generate random string]
   Callback URL: https://your-app.vercel.app/api/auth/github/callback
   ```

4. Set Permissions:
   - Repository permissions:
     - Pull requests: Read & Write
     - Contents: Read
     - Issues: Read & Write
   - Account permissions:
     - Email addresses: Read

5. Subscribe to events:
   - [x] Pull request
   - [x] Pull request review
   - [x] Pull request review comment
   - [x] Push

6. Create the app

7. Generate private key (download .pem file)

### Update Environment Variables

```bash
# Convert private key to base64
cat downloaded-key.pem | base64 > private-key-base64.txt

# Update Azure backend
az containerapp update \
  --name $BACKEND_APP \
  --resource-group $RESOURCE_GROUP \
  --set-env-vars \
    GITHUB_APP_ID="your-app-id" \
    GITHUB_WEBHOOK_SECRET="your-webhook-secret"

# Update Vercel frontend
vercel env add GITHUB_CLIENT_ID
vercel env add GITHUB_CLIENT_SECRET

# Redeploy
vercel --prod
```

### Test Webhook

1. Install your GitHub App on a test repository
2. Create a test PR
3. Check Azure logs:

```bash
az containerapp logs show \
  --name $BACKEND_APP \
  --resource-group $RESOURCE_GROUP \
  --follow
```

---

## 6. Monitor Costs

### Setup Cost Alerts

```bash
# Create budget alert at $5
az consumption budget create \
  --resource-group $RESOURCE_GROUP \
  --budget-name git-review-budget \
  --amount 5 \
  --time-period monthly \
  --threshold 80 \
  --notification enabled \
  --contact-emails your-email@example.com

echo "✅ Cost alert set at $5 (80% threshold = $4)"
```

### Check Current Spending

```bash
# Check usage and costs
az consumption usage list \
  --start-date $(date -d "7 days ago" +%Y-%m-%d) \
  --end-date $(date +%Y-%m-%d) \
  --output table

# Or visit Azure Portal:
# https://portal.azure.com → Cost Management + Billing
```

### Monitor Free Tier Usage

```bash
# Check container app metrics
az monitor metrics list \
  --resource $BACKEND_APP \
  --resource-group $RESOURCE_GROUP \
  --resource-type Microsoft.App/containerApps \
  --metric Requests \
  --output table
```

### Azure Portal Monitoring

1. Go to: https://portal.azure.com
2. Navigate to your resource group
3. Click "Cost analysis"
4. View daily breakdown
5. Set additional alerts as needed

---

## 7. Manage Containers

### Start Containers (For Demos)

```bash
# Scale up to 1 replica
az containerapp update \
  --name $BACKEND_APP \
  --resource-group $RESOURCE_GROUP \
  --min-replicas 1 \
  --max-replicas 1

echo "✅ Backend started"
```

### Stop Containers (Save Credits)

```bash
# Scale down to 0 replicas
az containerapp update \
  --name $BACKEND_APP \
  --resource-group $RESOURCE_GROUP \
  --min-replicas 0 \
  --max-replicas 1

echo "✅ Backend stopped (scale-to-zero)"
```

### Check Container Status

```bash
# Get container status
az containerapp show \
  --name $BACKEND_APP \
  --resource-group $RESOURCE_GROUP \
  --query properties.runningStatus \
  --output tsv

# Check replica count
az containerapp replica list \
  --name $BACKEND_APP \
  --resource-group $RESOURCE_GROUP \
  --output table
```

### View Container Logs

```bash
# Stream logs in real-time
az containerapp logs show \
  --name $BACKEND_APP \
  --resource-group $RESOURCE_GROUP \
  --follow

# Get recent logs
az containerapp logs show \
  --name $BACKEND_APP \
  --resource-group $RESOURCE_GROUP \
  --tail 100
```

### Update Container Image

```bash
# After pushing new image to Docker Hub
az containerapp update \
  --name $BACKEND_APP \
  --resource-group $RESOURCE_GROUP \
  --image $DOCKER_IMAGE:latest

echo "✅ Backend updated to latest image"
```

---

## 8. Troubleshooting

### Container Won't Start

**Check logs:**

```bash
az containerapp logs show \
  --name $BACKEND_APP \
  --resource-group $RESOURCE_GROUP \
  --tail 50
```

**Common Issues:**

- Missing environment variables
- Image not found (check Docker Hub)
- Port mismatch (should be 8000)
- Health check failing

**Fix:**

```bash
# Update environment variables
az containerapp update \
  --name $BACKEND_APP \
  --resource-group $RESOURCE_GROUP \
  --set-env-vars KEY=value

# Or recreate container
az containerapp delete --name $BACKEND_APP --resource-group $RESOURCE_GROUP --yes
# Then deploy again
```

### Webhook Not Received

**Check GitHub App:**

1. Go to GitHub App settings
2. Click "Advanced" → "Recent Deliveries"
3. Check response code

**Common Issues:**

- Webhook URL incorrect
- Webhook secret mismatch
- Container scaled to zero (first request may timeout)

**Fix:**

```bash
# Keep container warm (1 replica minimum)
az containerapp update \
  --name $BACKEND_APP \
  --resource-group $RESOURCE_GROUP \
  --min-replicas 1
```

### High Costs

**Check what's consuming credits:**

```bash
# View cost breakdown
az consumption usage list \
  --start-date $(date -d "30 days ago" +%Y-%m-%d) \
  --end-date $(date +%Y-%m-%d) \
  --query "[?contains(instanceName,'git-review')]" \
  --output table
```

**Optimize:**

```bash
# Reduce CPU/memory
az containerapp update \
  --name $BACKEND_APP \
  --resource-group $RESOURCE_GROUP \
  --cpu 0.25 \
  --memory 0.5Gi

# Or delete unused resources
az containerapp delete --name redis --resource-group $RESOURCE_GROUP --yes
```

### Container Keeps Restarting

**Check health probe:**

```bash
# Remove health probe temporarily
az containerapp update \
  --name $BACKEND_APP \
  --resource-group $RESOURCE_GROUP \
  --remove-health-probes

# Check logs to see actual error
az containerapp logs show \
  --name $BACKEND_APP \
  --resource-group $RESOURCE_GROUP \
  --follow
```

---

## 9. Cost Optimization Tips

### Keep Costs at $0

1. **Enable Scale-to-Zero** (already done in deployment)

   ```bash
   --min-replicas 0
   ```

2. **Use Docker Hub** instead of Azure Container Registry
   - ACR Basic: ~$5/month
   - Docker Hub Free: $0/month (1 private repo + unlimited public)

3. **Use UpStash** instead of Redis container
   - Redis container: ~$6/month (if always running)
   - UpStash Free: $0/month (10K commands/day)

4. **Use Vercel** for frontend
   - Azure Static Web Apps: Limited free tier
   - Vercel Free: Unlimited bandwidth

5. **Manual Start/Stop** for demos

   ```bash
   # Before demo
   ./manage-azure-containers.sh start

   # After demo
   ./manage-azure-containers.sh stop
   ```

### Monitor Free Tier Usage

**Azure Container Apps Free Tier:**

- 180,000 vCPU-seconds per month
- 360,000 GiB-seconds per month

**Your Configuration:**

- 0.5 vCPU + 1GB RAM = uses ~1.5 units/second
- 180,000 / 1.5 = 120,000 seconds = **33 hours free per month**

**Usage Scenarios:**

```
Webhook only (scale-to-zero):
  100 webhooks × 2 seconds = 200 seconds/month
  Cost: $0 (well within free tier)

Demo mode (2 hours/day):
  60 hours/month
  Cost: $0 (within free tier)

24/7 operation:
  720 hours/month (exceeds free tier)
  Cost: ~$35/month (use student credits)
```

---

## 10. Cleanup (When Done)

### Delete All Resources

```bash
# Delete entire resource group (removes everything)
az group delete \
  --name $RESOURCE_GROUP \
  --yes \
  --no-wait

echo "🗑️ All Azure resources deleted"
```

**This removes:**

- Container Apps environment
- All container apps
- All associated resources

**Does NOT affect:**

- Vercel deployment (separate)
- Docker Hub images (separate)
- GitHub App (separate)

### Delete Individual Resources

```bash
# Delete just the backend container
az containerapp delete \
  --name $BACKEND_APP \
  --resource-group $RESOURCE_GROUP \
  --yes

# Delete environment (after all apps removed)
az containerapp env delete \
  --name $CONTAINER_ENV \
  --resource-group $RESOURCE_GROUP \
  --yes
```

---

## 11. Summary

### What You've Deployed (For FREE!)

✅ **Backend API** - Azure Container Apps with scale-to-zero
✅ **Frontend** - Vercel with CDN
✅ **Docker Images** - Docker Hub registry
✅ **GitHub Integration** - Automated PR reviews
✅ **Cost Monitoring** - Alerts at $5

### Monthly Costs

```
Azure for Students Credit:      $100 (12 months)
Container Apps (scale-to-zero): $0/month
Frontend (Vercel):              $0/month
Docker Hub:                     $0/month
Redis (UpStash):                $0/month
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TOTAL:                          $0/month!
```

### Timeline

- **Month 1-12:** $100 credit covers any overages
- **After:** Free tier covers normal usage
- **Renewal:** Get another $100 credit (students)

### Expected Usage (For Learning)

```
Typical bootcamp usage:
- 10 test PRs per week
- 2 hours of demos per week
- 5 webhook events per day

Total monthly runtime: ~10 hours
Free tier limit: 33 hours
Status: ✅ Completely free!
```

---

## 12. Next Steps

1. ✅ Deploy backend to Azure Container Apps
2. ✅ Deploy frontend to Vercel
3. ✅ Configure GitHub webhooks
4. ✅ Set cost alerts
5. ✅ Test with sample PR
6. ✅ Create demo video
7. ✅ Submit for bootcamp grading

---

## 13. Quick Reference

### Useful Commands

```bash
# Check backend status
az containerapp show -n git-review-backend -g git-review-free-rg --query properties.runningStatus -o tsv

# View logs
az containerapp logs show -n git-review-backend -g git-review-free-rg --follow

# Update environment variable
az containerapp update -n git-review-backend -g git-review-free-rg --set-env-vars KEY=value

# Scale up
az containerapp update -n git-review-backend -g git-review-free-rg --min-replicas 1

# Scale down
az containerapp update -n git-review-backend -g git-review-free-rg --min-replicas 0

# Check costs
az consumption usage list --start-date $(date -d "7 days ago" +%Y-%m-%d) -o table
```

### Important URLs

- **Azure Portal:** https://portal.azure.com
- **Azure for Students:** https://azure.microsoft.com/en-us/free/students
- **Cost Management:** https://portal.azure.com/#blade/Microsoft_Azure_Billing/ModernBillingMenuBlade/Overview
- **Container Apps Docs:** https://learn.microsoft.com/en-us/azure/container-apps/
- **Docker Hub:** https://hub.docker.com
- **Vercel Dashboard:** https://vercel.com/dashboard
- **UpStash Console:** https://console.upstash.com

---

## Need Help?

- **Check logs first:** 90% of issues show in logs
- **Verify environment variables:** Common source of errors
- **Test locally:** Docker compose up to verify images work
- **Check cost alerts:** Make sure you're not getting charged
- **Use helper scripts:** `./manage-azure-containers.sh`

---

**Congratulations!** 🎉

You've deployed a production-grade AI code review system to Azure **completely free** using Docker containers!

This setup gives you:

- ✅ Real Azure experience for your resume
- ✅ Docker container deployment skills
- ✅ GitHub integration portfolio piece
- ✅ Zero monthly cost
- ✅ Bootcamp project completion

Now go create that demo video and ship it! 🚀
