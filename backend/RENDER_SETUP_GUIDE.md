# Render Backend Deployment Guide

## 🚀 Deploy Your Git Review Assistant Backend to Render

This guide walks you through deploying the FastAPI backend to Render, a reliable platform for hosting Python applications.

## Prerequisites

- [ ] Render account (free tier available)
- [ ] GitHub repository with your forked code
- [ ] OpenAI API key
- [ ] GitHub App credentials (for full functionality)

## Step 1: Prepare Your Repository

### 1.1 Ensure Required Files Exist

Your backend should have these files:

```
backend/
├── main.py                 # FastAPI application entry point
├── requirements.txt        # Python dependencies
├── .env.example           # Environment template
└── render.yaml           # Render configuration (optional)
```

### 1.2 Create `render.yaml` (Optional but Recommended)

```yaml
# backend/render.yaml
services:
  - type: web
    name: git-review-assistant-backend
    env: python
    buildCommand: 'pip install -r requirements.txt'
    startCommand: 'uvicorn main:app --host 0.0.0.0 --port $PORT'
    envVars:
      - key: PYTHON_VERSION
        value: 3.11.0
      - key: DEBUG
        value: false
```

## Step 2: Create Render Web Service

### 2.1 Login to Render

1. Go to [render.com](https://render.com)
2. Sign up/login with GitHub
3. Grant access to your repository

### 2.2 Create New Web Service

1. Click **"New +"** → **"Web Service"**
2. Connect your GitHub repository
3. Select your repository: `your-username/Code-Review-Assistant-`
4. Configure the service:
   - **Name**: `git-review-assistant-backend`
   - **Region**: Choose closest to your users
   - **Branch**: `main` (or your default branch)
   - **Root Directory**: `backend`
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`

## Step 3: Configure Environment Variables

### 3.1 Add Required Environment Variables

In Render dashboard → your service → Environment:

```env
# Application Settings
DEBUG=false
SECRET_KEY=your-super-secure-random-secret-key-here
HOST=0.0.0.0
PORT=10000

# OpenAI Configuration (Required)
OPENAI_API_KEY=sk-your-real-openai-api-key-here
OPENAI_MODEL=gpt-4o
OPENAI_TEMPERATURE=0.1
OPENAI_MAX_TOKENS=4000

# Demo Mode (for portfolio showcase)
DEMO_MODE=true

# GitHub Configuration (for full functionality - optional for demo)
GITHUB_APP_ID=your-github-app-id
GITHUB_PRIVATE_KEY=-----BEGIN RSA PRIVATE KEY-----
your-private-key-content-here
-----END RSA PRIVATE KEY-----
GITHUB_WEBHOOK_SECRET=your-webhook-secret
GITHUB_CLIENT_ID=your-github-client-id
GITHUB_CLIENT_SECRET=your-github-client-secret

# LangChain Configuration (Optional but recommended)
LANGCHAIN_API_KEY=ls__your-langchain-api-key
LANGCHAIN_PROJECT=git-review-assistant
LANGCHAIN_TRACING_V2=true

# Database Configuration
DATABASE_URL=sqlite:///./reviews.db
DATABASE_ECHO=false

# CORS Origins (Important - replace with your frontend URL)
ALLOWED_ORIGINS=https://your-frontend-domain.vercel.app,http://localhost:3000

# Review Engine Settings
SECURITY_SCAN_ENABLED=true
PERFORMANCE_ANALYSIS_ENABLED=true
QUALITY_ANALYSIS_ENABLED=true
MAX_REVIEW_TIME=300
```

### 3.2 Important Notes on Environment Variables

**🔑 SECRET_KEY**: Generate a secure random key:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

**🔗 ALLOWED_ORIGINS**: Must include your frontend URL

- Replace `your-frontend-domain.vercel.app` with your actual Vercel URL
- Keep `http://localhost:3000` for local development

**🚀 DEMO_MODE**: Set to `true` for portfolio demo, `false` for full functionality

## Step 4: Deploy and Test

### 4.1 Initial Deployment

1. Click **"Create Web Service"**
2. Wait for initial build (5-10 minutes)
3. Check logs for any errors
4. Note your backend URL: `https://your-service-name.onrender.com`

### 4.2 Test Your Deployment

```bash
# Test health endpoint
curl https://your-service-name.onrender.com/health

# Expected response:
{
  "status": "healthy",
  "timestamp": "2025-01-20T10:30:00Z",
  "version": "1.0.0"
}
```

### 4.3 Test API Documentation

Visit: `https://your-service-name.onrender.com/docs`

- Should show interactive Swagger documentation
- Test basic endpoints like `/health` and `/`

## Step 5: Connect to Frontend

### 5.1 Update Frontend Environment Variables

In your frontend `.env.local`:

```env
NEXT_PUBLIC_API_URL=https://your-service-name.onrender.com
```

### 5.2 Update CORS Settings

Ensure your backend `ALLOWED_ORIGINS` includes your frontend URL:

```env
ALLOWED_ORIGINS=https://your-frontend.vercel.app,http://localhost:3000
```

## Step 6: Advanced Configuration

### 6.1 Custom Domain (Optional)

1. In Render dashboard → Settings → Custom Domains
2. Add your domain: `api.your-domain.com`
3. Configure DNS CNAME record
4. Update frontend to use custom domain

### 6.2 Health Checks

Render automatically monitors `/health` endpoint.
Configure custom health check:

1. Settings → Health Check Path: `/health`
2. Health Check Grace Period: 60 seconds

### 6.3 Auto-Deploy on Git Push

1. Settings → Auto-Deploy: `Yes`
2. Pushes to main branch will auto-deploy
3. Review deploy logs for issues

## Troubleshooting

### Common Issues

**Build Fails - Missing Dependencies**

```bash
# Solution: Check requirements.txt has all dependencies
pip freeze > requirements.txt
```

**App Won't Start - Port Issues**

```bash
# Ensure start command uses $PORT variable
uvicorn main:app --host 0.0.0.0 --port $PORT
```

**CORS Errors**

```bash
# Check ALLOWED_ORIGINS includes your frontend URL
# Check frontend API URL is correct
```

**Environment Variables Not Loading**

- Double-check variable names match exactly
- Ensure no trailing spaces in values
- For multiline values (like private keys), use quotes

### Debugging Commands

**View Logs**:

1. Render Dashboard → your service → Logs
2. Filter by "Build" or "Deploy" for specific issues

**Manual Health Check**:

```bash
curl -v https://your-service-name.onrender.com/health
```

**Test API Endpoint**:

```bash
curl -X POST https://your-service-name.onrender.com/api/review/paste \
  -H "Content-Type: application/json" \
  -d '{"code": "print(\"hello world\")", "language": "python"}'
```

## Performance Optimization

### 6.1 Free Tier Limitations

- Services sleep after 15 minutes of inactivity
- Cold start time: 30-60 seconds
- 512MB RAM, 0.1 CPU units

### 6.2 Paid Tier Benefits ($7/month)

- No sleeping
- Faster CPU and more RAM
- Custom domains included
- Priority support

### 6.3 Optimization Tips

```python
# Add to main.py for faster startup
@app.on_event("startup")
async def startup_event():
    # Pre-load AI models
    # Initialize database connections
    # Warm up critical services
```

## Security Best Practices

### 7.1 Environment Security

- Never commit real API keys to Git
- Use Render's encrypted environment variables
- Rotate secrets regularly

### 7.2 API Security

- Enable rate limiting in production
- Validate all input data
- Use HTTPS only (Render provides free SSL)

### 7.3 Monitoring

- Set up error alerts
- Monitor API usage patterns
- Track response times

## Cost Estimation

### Free Tier

- 1 free web service
- 750 hours/month (enough for personal projects)
- Automatic sleeping after 15 minutes

### Paid Plans

- **Starter ($7/month)**: 1 always-on service
- **Standard ($25/month)**: Multiple services, more resources
- **Pro ($85/month)**: Advanced features, priority support

## Next Steps

1. **Test thoroughly**: Verify all endpoints work
2. **Monitor logs**: Watch for errors or performance issues
3. **Set up alerts**: Get notified of deployment failures
4. **Document URLs**: Update frontend configuration
5. **Consider upgrades**: Move to paid tier for production use

## Support Resources

- [Render Documentation](https://render.com/docs)
- [FastAPI Deployment Guide](https://fastapi.tiangolo.com/deployment/)
- [Python on Render](https://render.com/docs/deploy-python)

---

## Quick Reference

**Your Backend URL**: `https://your-service-name.onrender.com`
**API Docs**: `https://your-service-name.onrender.com/docs`
**Health Check**: `https://your-service-name.onrender.com/health`

Need help? Check the troubleshooting section or Render's support documentation.
