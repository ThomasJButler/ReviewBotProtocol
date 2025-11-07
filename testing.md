# Testing Guide - Git Review Assistant

## 📋 Overview

This guide covers how to test the Git Review Assistant locally and with Docker containers before deploying to Azure. The application is a **two-tier architecture** with separate frontend and backend services.

## 🏗️ Architecture & Docker Setup

### Why Two Dockerfiles?

This project requires **two separate Dockerfiles** because it's a two-tier application:

1. **Frontend Dockerfile** (`/Dockerfile`)
   - Next.js 14.2 application
   - Node.js 18 Alpine base image
   - Serves on port 3000
   - Handles UI, routing, and client-side logic

2. **Backend Dockerfile** (`/backend/Dockerfile`)
   - FastAPI application with Python 3.11
   - Handles AI processing, GitHub webhooks, API endpoints
   - LangChain + LangGraph integration
   - Serves on port 8000

**Both containers are required** for the application to function. Docker Compose orchestrates them together.

---

## 🧪 Testing Strategy

### Recommended Testing Order

1. **Backend locally** → Verify AI engine, API endpoints
2. **Frontend locally** → Test UI, routing, API integration
3. **Both together locally** → End-to-end local testing
4. **Docker containers** → Test containerized deployment
5. **Docker with webhooks** → Test GitHub integration (optional)
6. **Azure deployment** → Production testing

---

## 🖥️ Local Testing (Without Docker)

### Prerequisites

```bash
# Verify installations
node --version   # Should be 18+
python --version # Should be 3.11+
npm --version
```

### 1. Test Backend Locally

**Step 1: Activate Python environment**

```bash
cd backend
source .venv/bin/activate  # macOS/Linux
# OR
.venv\Scripts\activate     # Windows
```

**Step 2: Install dependencies** (if not already done)

```bash
pip install -r requirements.txt
```

**Step 3: Verify environment variables**

```bash
# backend/.env should contain:
# - OPENAI_API_KEY
# - LANGCHAIN_API_KEY
# - GITHUB_APP_ID
# - GITHUB_CLIENT_ID
# - GITHUB_CLIENT_SECRET
# - GITHUB_PRIVATE_KEY
# - GITHUB_WEBHOOK_SECRET
```

**Step 4: Start backend server**

```bash
uvicorn main:app --reload --port 8000
```

**Step 5: Test backend endpoints**

```bash
# Health check (should return 200 OK)
curl http://localhost:8000/health

# Expected response:
# {"status": "healthy", "timestamp": "2025-01-05T..."}

# API documentation (open in browser)
open http://localhost:8000/docs
```

**✅ Backend is working if:**

- Server starts without errors
- Health endpoint returns 200
- API docs are accessible
- No import errors in terminal

---

### 2. Test Frontend Locally

**Step 1: Install dependencies** (if not already done)

```bash
npm install
```

**Step 2: Verify environment variables**

```bash
# .env.local should contain:
# - NEXT_PUBLIC_API_URL=http://localhost:8000
# - OPENAI_API_KEY (same as backend)
# - GITHUB_APP_ID, CLIENT_ID, CLIENT_SECRET, etc.
```

**Step 3: Start frontend dev server**

```bash
npm run dev:frontend
# OR
npm run dev  # Starts both frontend and backend
```

**Step 4: Test frontend**

```bash
# Open browser
open http://localhost:3000
```

**✅ Frontend is working if:**

- No compilation errors
- Homepage loads
- Dashboard accessible at `/dashboard`
- No console errors in browser DevTools
- Can navigate between pages

---

### 3. Test Both Together (Full Integration)

**Step 1: Start both services**

```bash
# Terminal 1: Backend
cd backend
source .venv/bin/activate
uvicorn main:app --reload --port 8000

# Terminal 2: Frontend
npm run dev:frontend

# OR use single command (recommended):
npm run dev  # Starts both with concurrently
```

**Step 2: Test integration**

```bash
# 1. Open frontend
open http://localhost:3000

# 2. Navigate to dashboard
# 3. Try "Paste Code" review mode
# 4. Paste sample code and click "Review Code"
# 5. Verify AI review appears
```

**Test Cases:**

- ✅ Paste Code review works
- ✅ File Upload review works
- ✅ GitHub OAuth login works
- ✅ Dashboard displays review history
- ✅ API calls succeed (check Network tab)

---

## 🐳 Docker Testing

### Prerequisites

```bash
# Verify Docker is installed and running
docker --version
docker-compose --version

# Start Docker Desktop (macOS/Windows)
```

### 1. Build Docker Images

```bash
# Build both frontend and backend images
npm run docker:build

# OR manually:
docker-compose build

# Verify images were created
docker images | grep git-review
```

**Expected output:**

```
git-review-frontend    latest    ...
git-review-backend     latest    ...
```

---

### 2. Start Docker Containers

```bash
# Start all containers in detached mode
npm run docker:up

# OR manually:
docker-compose up -d

# Verify containers are running
docker ps
```

**Expected output:**

```
CONTAINER ID   IMAGE                    STATUS         PORTS
abc123         git-review-frontend      Up 10 seconds  0.0.0.0:3000->3000/tcp
def456         git-review-backend       Up 10 seconds  0.0.0.0:8000->8000/tcp
```

---

### 3. Test Docker Containers

**Backend Health Check:**

```bash
curl http://localhost:8000/health

# Expected: {"status": "healthy", ...}
```

**Frontend Check:**

```bash
# Open browser
open http://localhost:3000

# Should see homepage with no errors
```

**API Integration Test:**

```bash
# Test review endpoint
curl -X POST http://localhost:8000/api/review \
  -H "Content-Type: application/json" \
  -d '{"code": "console.log(\"test\")", "language": "javascript", "mode": "paste"}'

# Should return AI review JSON
```

---

### 4. View Container Logs

```bash
# View all logs
npm run docker:logs

# OR manually:
docker-compose logs -f

# View specific container logs
docker logs git-review-frontend -f
docker logs git-review-backend -f
```

**Look for:**

- ✅ Backend: "Uvicorn running on http://0.0.0.0:8000"
- ✅ Frontend: "Ready - started server on 0.0.0.0:3000"
- ❌ No error messages or stack traces

---

### 5. Stop Docker Containers

```bash
# Stop all containers
npm run docker:down

# OR manually:
docker-compose down

# Stop and remove volumes (full cleanup)
docker-compose down -v
```

---

## ✅ Testing Checklist

### Local Testing

- [ ] Backend starts without errors
- [ ] Backend health endpoint returns 200
- [ ] Backend API docs accessible at `/docs`
- [ ] Frontend compiles without errors
- [ ] Frontend homepage loads
- [ ] Dashboard accessible
- [ ] No console errors in browser
- [ ] Paste Code review works
- [ ] File Upload review works
- [ ] API integration working (Network tab shows 200 responses)

### Docker Testing

- [ ] Docker images build successfully
- [ ] Both containers start (frontend + backend)
- [ ] Backend health check returns 200
- [ ] Frontend loads at http://localhost:3000
- [ ] No errors in container logs
- [ ] Paste Code review works in Docker
- [ ] File Upload review works in Docker
- [ ] Containers stop cleanly

### Pre-Deployment Testing

- [ ] Environment variables configured for production
- [ ] All tests pass locally
- [ ] All tests pass in Docker
- [ ] No secrets in code or logs
- [ ] .env files not committed to git
- [ ] Docker images optimized (multi-stage builds)
- [ ] Health checks configured
- [ ] Error handling tested

---

## 🐛 Common Issues & Fixes

### Issue 1: Backend won't start - ModuleNotFoundError

**Symptom:**

```
ModuleNotFoundError: No module named 'fastapi'
```

**Fix:**

```bash
cd backend
source .venv/bin/activate
pip install -r requirements.txt
```

---

### Issue 2: Frontend build errors - Module not found

**Symptom:**

```
Module not found: Can't resolve '@/components/ui/...'
```

**Fix:**

```bash
# Reinstall dependencies
rm -rf node_modules package-lock.json
npm install

# Check tsconfig.json paths are correct
```

---

### Issue 3: Docker containers exit immediately

**Symptom:**

```
docker ps  # Shows no containers running
```

**Fix:**

```bash
# Check logs for errors
docker-compose logs

# Common fixes:
# 1. Missing environment variables
cp .env.example .env.local
# Edit .env.local with real values

# 2. Port already in use
lsof -i :3000
lsof -i :8000
# Kill processes or change ports in docker-compose.yml

# 3. Rebuild images
docker-compose down -v
docker-compose build --no-cache
docker-compose up
```

---

### Issue 4: API calls fail with CORS errors

**Symptom:**

```
Access to fetch at 'http://localhost:8000/api/review' has been blocked by CORS
```

**Fix:**

```bash
# Check backend/.env has correct ALLOWED_ORIGINS
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:3001

# Restart backend
```

---

### Issue 5: GitHub OAuth not working locally

**Symptom:**

```
Callback URL mismatch
```

**Fix:**

```bash
# Update GitHub App callback URL to:
http://localhost:3000/api/auth/github/callback

# Ensure .env.local has correct GitHub credentials
```

---

### Issue 6: AI reviews fail with OpenAI errors

**Symptom:**

```
openai.error.AuthenticationError: Invalid API key
```

**Fix:**

```bash
# Verify OpenAI API key in backend/.env and .env.local
echo $OPENAI_API_KEY

# Test API key directly
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"
```

---

## 🧪 Testing GitHub Webhooks (Optional)

### Using ngrok for Local Webhook Testing

**Step 1: Install ngrok**

```bash
# macOS
brew install ngrok

# Or download from https://ngrok.com
```

**Step 2: Start ngrok tunnel**

```bash
# Tunnel to backend port
ngrok http 8000

# Copy the HTTPS URL (e.g., https://abc123.ngrok-free.app)
```

**Step 3: Update GitHub App webhook URL**

```
GitHub App Settings > Webhook URL:
https://abc123.ngrok-free.app/api/webhook/github
```

**Step 4: Test webhook**

```bash
# Create a test PR in a repo where your GitHub App is installed
# Watch backend logs for webhook events

# Backend logs should show:
# "Received webhook event: pull_request"
# "Processing PR review..."
```

**Note:** ngrok URLs expire when the tunnel stops. You'll need to update the GitHub App webhook URL each time you restart ngrok.

---

## 🚀 Pre-Azure Deployment Testing

Before deploying to Azure, ensure:

1. **All local tests pass** ✅
2. **All Docker tests pass** ✅
3. **Environment variables ready** ✅
4. **GitHub App configured** ✅
5. **No secrets in code** ✅
6. **Docker images optimized** ✅

### Final Verification Checklist

```bash
# 1. Clean build test
npm run docker:down -v
npm run docker:build
npm run docker:up

# 2. Wait 30 seconds for startup
sleep 30

# 3. Test all endpoints
curl http://localhost:8000/health
curl http://localhost:3000

# 4. Test AI review
# Open browser, paste code, get review

# 5. Check logs for errors
npm run docker:logs

# ✅ If everything works, you're ready to deploy!
```

---

## 📚 Additional Resources

- **Docker Compose file**: `docker-compose.yml`
- **Frontend Dockerfile**: `/Dockerfile`
- **Backend Dockerfile**: `/backend/Dockerfile`
- **Deployment guide**: `FREE_AZURE_DEPLOYMENT.md`
- **Project docs**: `CLAUDE.md`

---

## 🎯 Quick Reference Commands

### Local Development

```bash
npm run dev                 # Start frontend + backend
npm run dev:frontend        # Frontend only
npm run dev:backend         # Backend only
```

### Docker

```bash
npm run docker:build        # Build images
npm run docker:up           # Start containers
npm run docker:down         # Stop containers
npm run docker:logs         # View logs
```

### Testing

```bash
curl http://localhost:8000/health    # Backend health
curl http://localhost:3000           # Frontend
docker ps                            # Check containers
docker logs <container_id>           # View logs
```

---

**Last updated:** 2025-01-05

**Status:** ✅ Ready for testing and deployment
