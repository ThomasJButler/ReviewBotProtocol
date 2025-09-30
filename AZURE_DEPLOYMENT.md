# 🚀 Azure VM Deployment Guide - Git Review Assistant

Complete guide for deploying the Git Review Assistant to Azure as an **alternative to ngrok** for GitHub webhook integration.

---

## 📋 Table of Contents

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
