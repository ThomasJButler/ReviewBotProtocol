# 🚀 Azure Deployment Guide - Git Review Assistant

Complete guide for deploying the Git Review Assistant to Azure with **multiple deployment options**.

---

## 🎯 Deployment Options

This guide covers **three Azure deployment approaches**:

### 1. 🐳 Azure Container Instances (Recommended)

- **Simplest and fastest** - Deploy pre-built Docker containers
- **Cost:** ~$15-30/month
- **Time:** 30-60 minutes
- **Best for:** Quick deployment, testing, cost optimization
- **See:** [Docker Container Deployment](#docker-container-deployment)

### 2. 🖥️ Azure VM (Traditional)

- **Full control** - Manual VM setup with Nginx, PM2
- **Cost:** ~$30-70/month
- **Time:** 2-3 hours
- **Best for:** Learning infrastructure, custom configuration
- **See:** [VM Deployment Guide](#vm-deployment-guide) (original guide below)

### 3. ☁️ Azure App Service

- **Managed platform** - PaaS deployment, no server management
- **Cost:** ~$13+/month
- **Time:** 1-2 hours
- **Best for:** Enterprise scenarios, auto-scaling needs
- **See:** [App Service Deployment](#app-service-deployment)

---

## 🐳 Docker Container Deployment

### Quick Start with Azure CLI

**Prerequisites:**

- Azure CLI installed
- Docker installed locally
- GitHub repository with Dockerfiles

#### Step 1: Automated Deployment Script

Use the provided deployment script for one-command deployment:

```bash
# Clone repository
git clone https://github.com/yourusername/Code-Review-Assistant.git
cd Code-Review-Assistant

# Set environment variables
cp .env.example .env
# Edit .env with your API keys

# Run deployment script
./deploy-azure.sh
```

The script will:

1. Create Azure Resource Group
2. Create Azure Container Registry
3. Build and push Docker images
4. Deploy backend container
5. Deploy frontend container
6. Output URLs for your deployed services

#### Step 2: Manual Container Deployment

If you prefer manual control:

```bash
# Login to Azure
az login

# Create resource group
az group create \
  --name git-review-assistant-rg \
  --location eastus

# Create container registry
az acr create \
  --resource-group git-review-assistant-rg \
  --name gitreviewassistant \
  --sku Basic \
  --admin-enabled true

# Get ACR credentials
az acr credential show --name gitreviewassistant

# Build and push images
cd backend
docker build -t gitreviewassistant.azurecr.io/backend:latest .

cd ..
docker build -t gitreviewassistant.azurecr.io/frontend:latest .

# Login to ACR
az acr login --name gitreviewassistant

# Push images
docker push gitreviewassistant.azurecr.io/backend:latest
docker push gitreviewassistant.azurecr.io/frontend:latest

# Deploy backend container
az container create \
  --resource-group git-review-assistant-rg \
  --name git-review-backend \
  --image gitreviewassistant.azurecr.io/backend:latest \
  --registry-login-server gitreviewassistant.azurecr.io \
  --registry-username [ACR_USERNAME] \
  --registry-password [ACR_PASSWORD] \
  --dns-name-label git-review-backend \
  --ports 8000 \
  --cpu 1 \
  --memory 2 \
  --environment-variables \
    OPENAI_API_KEY=$OPENAI_API_KEY \
    LANGCHAIN_API_KEY=$LANGCHAIN_API_KEY \
    GITHUB_APP_ID=$GITHUB_APP_ID

# Deploy frontend container
az container create \
  --resource-group git-review-assistant-rg \
  --name git-review-frontend \
  --image gitreviewassistant.azurecr.io/frontend:latest \
  --registry-login-server gitreviewassistant.azurecr.io \
  --registry-username [ACR_USERNAME] \
  --registry-password [ACR_PASSWORD] \
  --dns-name-label git-review-frontend \
  --ports 3000 \
  --cpu 0.5 \
  --memory 1 \
  --environment-variables \
    NEXT_PUBLIC_API_URL=http://git-review-backend.eastus.azurecontainer.io:8000

# Get URLs
az container show \
  --resource-group git-review-assistant-rg \
  --name git-review-backend \
  --query ipAddress.fqdn

az container show \
  --resource-group git-review-assistant-rg \
  --name git-review-frontend \
  --query ipAddress.fqdn
```

#### Step 3: GitHub Actions Automation

The repository includes a GitHub Actions workflow for automated deployment:

```yaml
# .github/workflows/deploy-azure.yml
# Triggers on push to main branch
# Automatically builds and deploys containers
```

**Setup GitHub Actions:**

1. Create Azure service principal:

```bash
az ad sp create-for-rbac --name "git-review-assistant" \
  --role contributor \
  --scopes /subscriptions/YOUR_SUBSCRIPTION_ID/resourceGroups/git-review-assistant-rg \
  --sdk-auth
```

2. Add secrets to GitHub repository:
   - `AZURE_CREDENTIALS` - Output from above command
   - `OPENAI_API_KEY`
   - `LANGCHAIN_API_KEY`
   - `GITHUB_APP_ID`
   - `GH_CLIENT_ID`
   - `GH_CLIENT_SECRET`
   - `GITHUB_PRIVATE_KEY`
   - `GITHUB_WEBHOOK_SECRET`

3. Push to main branch - automatic deployment!

### Docker Deployment Resources

- **Deployment Script:** `deploy-azure.sh`
- **Container Template:** `azure-container-instances.yaml`
- **GitHub Workflow:** `.github/workflows/deploy-azure.yml`
- **Parameters File:** `azure-parameters.json`

### Docker Deployment Benefits

- ✅ **Fast deployment** - Minutes vs hours
- ✅ **Consistent environment** - Same as local development
- ✅ **Easy updates** - Rebuild and redeploy
- ✅ **Cost effective** - Pay only for container runtime
- ✅ **No server management** - Azure handles infrastructure
- ✅ **Auto-restart** - Containers restart on failure
- ✅ **Health checks** - Built-in monitoring

### Docker Deployment Costs

**Azure Container Instances Pricing (East US):**

- Backend (1 vCPU, 2 GB RAM): ~$36/month (730 hours)
- Frontend (0.5 vCPU, 1 GB RAM): ~$14/month (730 hours)
- **Total: ~$50/month**

**Additional Costs:**

- Azure Container Registry (Basic): $5/month
- Bandwidth: ~$2-5/month
- **Grand Total: ~$57-60/month**

Compare to VM deployment: ~$30-70/month + setup time

---

## 📋 Table of Contents

### Docker Deployment (Recommended)

- [Docker Container Deployment](#docker-container-deployment)
- [Container Quick Start](#quick-start-with-azure-cli)
- [GitHub Actions Automation](#github-actions-automation)

### VM Deployment (Traditional)

1. [Prerequisites](#prerequisites)
2. [Phase 1: Create Azure VM](#phase-1-create-azure-vm)
3. [Phase 2: Install Dependencies](#phase-2-install-dependencies)
4. [Phase 3: Deploy Application](#phase-3-deploy-application)
5. [Phase 4: Configure Nginx Reverse Proxy](#phase-4-configure-nginx-reverse-proxy)
6. [Phase 5: Setup SSL with Let's Encrypt](#phase-5-setup-ssl-with-lets-encrypt)
7. [Phase 6: Configure GitHub Webhooks](#phase-6-configure-github-webhooks)
8. [Phase 7: Process Management with PM2](#phase-7-process-management-with-pm2)
9. [Troubleshooting](#troubleshooting)
10. [Cost Optimization](#cost-optimization)

---

# VM Deployment Guide

The following sections cover traditional Azure VM deployment. For Docker deployment (recommended), see above.

---

## Prerequisites

- Azure account with active subscription
- GitHub account with repository access
- OpenAI API key
- Domain name (optional but recommended)
- SSH client (Terminal, PuTTY, etc.)

---

## Phase 1: Create Azure VM

### 1.1 Create VM via Azure Portal

1. Go to [Azure Portal](https://portal.azure.com)
2. Click **"Create a resource"** → **"Virtual Machine"**
3. Configure:

```yaml
Basics:
  Resource Group: git-review-assistant-rg
  VM Name: git-review-vm
  Region: East US (or closest to you)
  Image: Ubuntu 22.04 LTS
  Size: Standard B2s (2 vCPUs, 4 GB RAM) - Minimum
    Standard D2s_v3 (2 vCPUs, 8 GB RAM) - Recommended

Authentication:
  Type: SSH public key
  Username: azureuser
  SSH Public Key: [Paste your ~/.ssh/id_rsa.pub]

Networking:
  Public IP: Yes
  Inbound Port Rules:
    - SSH (22)
    - HTTP (80)
    - HTTPS (443)

Management:
  Auto-shutdown: Enabled (save costs)
```

### 1.2 Connect to VM

```bash
# SSH into your VM
ssh azureuser@<your-vm-public-ip>

# Update system packages
sudo apt update && sudo apt upgrade -y
```

---

## Phase 2: Install Dependencies

### 2.1 Install Node.js 18

```bash
# Install Node.js 18 LTS
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs

# Verify installation
node --version  # Should show v18.x.x
npm --version
```

### 2.2 Install Python 3.11

```bash
# Install Python 3.11 and pip
sudo apt install -y python3.11 python3.11-venv python3.11-dev python3-pip

# Make Python 3.11 default (optional)
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1

# Verify installation
python3 --version  # Should show Python 3.11.x
```

### 2.3 Install System Tools

```bash
# Install Git, Nginx, and other essentials
sudo apt install -y git curl wget nginx certbot python3-certbot-nginx

# Install PM2 for process management
sudo npm install -g pm2

# Verify installations
git --version
nginx -v
pm2 --version
```

---

## Phase 3: Deploy Application

### 3.1 Clone Repository

```bash
# Navigate to home directory
cd /home/azureuser

# Clone your repository
git clone https://github.com/YOUR_USERNAME/Code-Review-Assistant-.git
cd Code-Review-Assistant-

# Or upload from local machine
# scp -r ./Code-Review-Assistant- azureuser@<your-vm-ip>:/home/azureuser/
```

### 3.2 Setup Backend

```bash
# Navigate to backend directory
cd /home/azureuser/Code-Review-Assistant-/backend

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Test backend imports
python3 -c "from main import app; print('✅ Backend imports successful')"
```

### 3.3 Setup Frontend

```bash
# Navigate to frontend (root) directory
cd /home/azureuser/Code-Review-Assistant-

# Install Node.js dependencies
npm install

# Build production version
npm run build

# The .next folder contains the built application
ls -la .next/
```

### 3.4 Environment Configuration

```bash
# Create .env.local file in root
cd /home/azureuser/Code-Review-Assistant-
cat > .env.local << 'EOF'
# Application
NEXT_PUBLIC_APP_URL=https://your-domain.com
NEXT_PUBLIC_APP_NAME=Git Review Assistant

# Backend
BACKEND_URL=http://localhost:8000

# GitHub OAuth
GITHUB_CLIENT_ID=your_github_client_id
GITHUB_CLIENT_SECRET=your_github_client_secret

# AI Services
OPENAI_API_KEY=sk-your-openai-key
LANGCHAIN_API_KEY=ls-your-langchain-key

# NextAuth
NEXTAUTH_URL=https://your-domain.com
NEXTAUTH_SECRET=your-nextauth-secret-here
EOF

# Set proper permissions
chmod 600 .env.local
```

```bash
# Create backend/.env file
cd /home/azureuser/Code-Review-Assistant-/backend
cat > .env << 'EOF'
# AI Services
OPENAI_API_KEY=sk-your-openai-key
LANGCHAIN_API_KEY=ls-your-langchain-key

# GitHub Integration
GITHUB_APP_ID=your_app_id
GITHUB_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----
your-private-key-here
-----END RSA PRIVATE KEY-----"
GITHUB_CLIENT_ID=your_client_id
GITHUB_CLIENT_SECRET=your_client_secret
GITHUB_WEBHOOK_SECRET=your_webhook_secret

# Server
HOST=0.0.0.0
PORT=8000
DEBUG=false
LOG_LEVEL=INFO

# Database (optional)
DATABASE_URL=sqlite:///./reviews.db
EOF

# Set proper permissions
chmod 600 .env
```

---

## Phase 4: Configure Nginx Reverse Proxy

### 4.1 Create Nginx Configuration

```bash
# Create Nginx config file
sudo nano /etc/nginx/sites-available/git-review-assistant
```

Paste this configuration:

```nginx
# Git Review Assistant - Nginx Configuration

# Redirect HTTP to HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name your-domain.com www.your-domain.com;

    # Let's Encrypt ACME challenge
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    # Redirect all other traffic to HTTPS
    location / {
        return 301 https://$server_name$request_uri;
    }
}

# HTTPS Configuration
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name your-domain.com www.your-domain.com;

    # SSL Certificates (will be added by Certbot)
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    # SSL Security
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    # Security Headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Frontend - Next.js (Port 3000)
    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Backend API - FastAPI (Port 8000)
    location /api/ {
        proxy_pass http://localhost:8000/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # GitHub Webhook specific
        proxy_buffering off;
        proxy_request_buffering off;

        # Longer timeout for AI processing
        proxy_connect_timeout 120s;
        proxy_send_timeout 120s;
        proxy_read_timeout 120s;
    }

    # GitHub Webhook (direct path)
    location /webhook/ {
        proxy_pass http://localhost:8000/webhook/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Hub-Signature-256 $http_x_hub_signature_256;
        proxy_set_header X-GitHub-Event $http_x_github_event;
        proxy_set_header X-GitHub-Delivery $http_x_github_delivery;

        # Critical for webhooks
        proxy_buffering off;
        proxy_request_buffering off;
    }

    # Static files caching
    location ~* \.(jpg|jpeg|png|gif|ico|css|js|svg|woff|woff2)$ {
        proxy_pass http://localhost:3000;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

### 4.2 Enable Site and Test

```bash
# Enable the site
sudo ln -s /etc/nginx/sites-available/git-review-assistant /etc/nginx/sites-enabled/

# Remove default site (optional)
sudo rm /etc/nginx/sites-enabled/default

# Test Nginx configuration
sudo nginx -t

# Reload Nginx
sudo systemctl reload nginx

# Enable Nginx on boot
sudo systemctl enable nginx
```

---

## Phase 5: Setup SSL with Let's Encrypt

### 5.1 Configure DNS

Before running Certbot, ensure your domain points to the VM:

```bash
# Check your VM's public IP
curl ifconfig.me

# Add an A record in your DNS provider:
# Type: A
# Name: @ (or your-subdomain)
# Value: <your-vm-public-ip>
# TTL: 300 (5 minutes)

# Wait for DNS propagation (5-30 minutes)
# Test with:
nslookup your-domain.com
```

### 5.2 Obtain SSL Certificate

```bash
# Run Certbot
sudo certbot --nginx -d your-domain.com -d www.your-domain.com

# Follow the prompts:
# - Enter email address
# - Agree to terms of service
# - Choose redirect option (option 2)

# Test SSL
curl https://your-domain.com

# Check certificate auto-renewal
sudo certbot renew --dry-run
```

### 5.3 Setup Auto-Renewal

```bash
# Certbot automatically creates a systemd timer
# Verify it's active:
sudo systemctl status certbot.timer

# Manual renewal test
sudo certbot renew --dry-run
```

---

## Phase 6: Configure GitHub Webhooks

### 6.1 Update GitHub App Settings

1. Go to your GitHub App settings
2. Update **Webhook URL**:
   ```
   https://your-domain.com/webhook/github
   ```
3. Update **Callback URL**:
   ```
   https://your-domain.com/api/auth/github/callback
   ```
4. Ensure **Webhook Secret** matches your `.env` file
5. Click **Save changes**

### 6.2 Test Webhook

```bash
# Monitor backend logs
pm2 logs backend

# Create a test PR in your GitHub repo
# Check logs for webhook reception
```

---

## Phase 7: Process Management with PM2

### 7.1 Create PM2 Ecosystem File

```bash
cd /home/azureuser/Code-Review-Assistant-
nano ecosystem.config.js
```

Paste this configuration:

```javascript
// PM2 Ecosystem Configuration for Git Review Assistant

module.exports = {
  apps: [
    {
      name: 'git-review-frontend',
      script: 'node_modules/.bin/next',
      args: 'start',
      cwd: '/home/azureuser/Code-Review-Assistant-',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '1G',
      env: {
        NODE_ENV: 'production',
        PORT: 3000,
      },
      error_file: '/home/azureuser/.pm2/logs/frontend-error.log',
      out_file: '/home/azureuser/.pm2/logs/frontend-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
    },
    {
      name: 'git-review-backend',
      script:
        '/home/azureuser/Code-Review-Assistant-/backend/.venv/bin/uvicorn',
      args: 'main:app --host 0.0.0.0 --port 8000 --workers 2',
      cwd: '/home/azureuser/Code-Review-Assistant-/backend',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '1G',
      env: {
        PYTHONPATH: '/home/azureuser/Code-Review-Assistant-/backend',
      },
      error_file: '/home/azureuser/.pm2/logs/backend-error.log',
      out_file: '/home/azureuser/.pm2/logs/backend-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
    },
  ],
}
```

### 7.2 Start Applications with PM2

```bash
# Start both applications
pm2 start ecosystem.config.js

# Save PM2 process list
pm2 save

# Setup PM2 to start on system boot
pm2 startup
# Run the command it outputs (usually with sudo)

# Monitor applications
pm2 monit

# View logs
pm2 logs

# Restart applications
pm2 restart all

# Stop applications
pm2 stop all
```

### 7.3 PM2 Useful Commands

```bash
# List all processes
pm2 list

# Show detailed info
pm2 show git-review-backend

# Monitor resources
pm2 monit

# View logs
pm2 logs
pm2 logs git-review-backend
pm2 logs git-review-frontend

# Restart specific app
pm2 restart git-review-backend

# Delete app from PM2
pm2 delete git-review-backend

# Clear logs
pm2 flush
```

---

## Troubleshooting

### Issue: Backend won't start

```bash
# Check Python dependencies
cd /home/azureuser/Code-Review-Assistant-/backend
source .venv/bin/activate
pip install -r requirements.txt

# Test manually
uvicorn main:app --host 0.0.0.0 --port 8000

# Check logs
pm2 logs git-review-backend --lines 100
```

### Issue: Frontend build fails

```bash
# Clear Next.js cache
cd /home/azureuser/Code-Review-Assistant-
rm -rf .next node_modules
npm install
npm run build

# Check Node.js version
node --version  # Should be v18.x
```

### Issue: Webhook not receiving events

```bash
# Check Nginx logs
sudo tail -f /var/log/nginx/error.log

# Check backend logs
pm2 logs git-review-backend

# Test webhook endpoint
curl -X POST https://your-domain.com/webhook/github/test

# Verify firewall
sudo ufw status
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
```

### Issue: SSL certificate errors

```bash
# Renew certificate
sudo certbot renew --force-renewal

# Check certificate
sudo certbot certificates

# Test SSL
curl -vI https://your-domain.com
```

---

## Cost Optimization

### VM Size Recommendations

| VM Size | vCPUs | RAM   | Monthly Cost | Use Case           |
| ------- | ----- | ----- | ------------ | ------------------ |
| B1s     | 1     | 1 GB  | ~$8          | Testing only       |
| B2s     | 2     | 4 GB  | ~$30         | Minimum production |
| D2s_v3  | 2     | 8 GB  | ~$70         | Recommended        |
| D4s_v3  | 4     | 16 GB | ~$140        | High traffic       |

### Cost-Saving Tips

1. **Auto-shutdown**: Configure VM to shut down during off-hours
2. **Reserved instances**: Save 30-40% with 1-year commitment
3. **Use spot instances**: Save up to 90% for non-critical workloads
4. **Monitor usage**: Use Azure Cost Management

```bash
# Setup auto-shutdown via Azure CLI
az vm auto-shutdown -g git-review-assistant-rg -n git-review-vm --time 2200
```

---

## Updating the Application

```bash
# SSH into VM
ssh azureuser@your-vm-ip

# Navigate to project
cd /home/azureuser/Code-Review-Assistant-

# Pull latest changes
git pull origin main

# Update frontend
npm install
npm run build
pm2 restart git-review-frontend

# Update backend
cd backend
source .venv/bin/activate
pip install -r requirements.txt
cd ..
pm2 restart git-review-backend

# Check status
pm2 status
```

---

## Security Checklist

- [ ] SSH key-only authentication (disable password auth)
- [ ] Firewall configured (only ports 22, 80, 443 open)
- [ ] SSL certificate active and auto-renewing
- [ ] Environment variables secured (chmod 600 on .env files)
- [ ] GitHub webhook secret configured
- [ ] Regular system updates scheduled
- [ ] PM2 logs rotated
- [ ] Nginx rate limiting configured (optional)

---

## Resources

- [Azure VM Pricing](https://azure.microsoft.com/en-us/pricing/details/virtual-machines/)
- [Let's Encrypt Documentation](https://letsencrypt.org/docs/)
- [PM2 Documentation](https://pm2.keymetrics.io/docs/)
- [Nginx Documentation](https://nginx.org/en/docs/)
- [GitHub Webhooks Guide](https://docs.github.com/en/webhooks)

---

## Support

For issues specific to this deployment:

1. Check PM2 logs: `pm2 logs`
2. Check Nginx logs: `sudo tail -f /var/log/nginx/error.log`
3. Check application health: `curl https://your-domain.com/health`
4. Open an issue on GitHub

---

**🎉 Congratulations!** Your Git Review Assistant is now deployed on Azure with webhook support!
