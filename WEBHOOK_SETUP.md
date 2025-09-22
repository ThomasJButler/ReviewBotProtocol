# GitHub Webhook Setup Guide

This guide explains how to set up GitHub webhooks for automated PR reviews with the Git Review Assistant.

## Overview

The webhook system allows GitHub to automatically notify our application when pull requests are opened, updated, or synchronized. The AI will then analyze the code and post inline comments directly on the PR.

## Architecture

```
GitHub → ngrok tunnel → Next.js API route → FastAPI backend → AI Review → GitHub comments
```

## Prerequisites

1. **ngrok installed**: Download from [ngrok.com](https://ngrok.com) or install via:

   ```bash
   # macOS
   brew install ngrok

   # Windows (Chocolatey)
   choco install ngrok

   # Linux (Snap)
   snap install ngrok
   ```

2. **GitHub App created**: You should have a GitHub App with the necessary permissions.

## Step-by-Step Setup

### 1. Start the Application with Tunnel

```bash
# This starts both the Next.js frontend and creates an ngrok tunnel
npm run dev:tunnel
```

This command will:

- Start the Next.js development server on port 3000
- Start ngrok tunnel pointing to localhost:3000
- Display the public ngrok URL (e.g., `https://abc123.ngrok.io`)

### 2. Configure Environment Variables

Ensure your `.env.local` file has the required variables:

```env
# GitHub App Configuration
GITHUB_APP_ID=your_app_id
GITHUB_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----"
GITHUB_WEBHOOK_SECRET=your_webhook_secret
GITHUB_CLIENT_ID=your_client_id
GITHUB_CLIENT_SECRET=your_client_secret

# AI Configuration
OPENAI_API_KEY=sk-...

# Backend URL (for webhook forwarding)
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
```

### 3. Configure GitHub App Webhooks

1. Go to your GitHub App settings: `Settings > Developer settings > GitHub Apps > Your App`

2. **Update Webhook URL**:
   - Copy the ngrok URL from the terminal (e.g., `https://abc123.ngrok.io`)
   - Set Webhook URL to: `https://abc123.ngrok.io/api/webhook/github`

3. **Set Webhook Secret**:
   - Use the same secret you have in your `GITHUB_WEBHOOK_SECRET` environment variable

4. **Enable Required Events**:
   - ✅ Pull requests
   - ✅ Pull request reviews
   - ✅ Pull request review comments
   - ✅ Push (optional, for synchronize events)

5. **Verify Permissions**:
   - **Repository permissions**:
     - Pull requests: Read & Write
     - Contents: Read
     - Issues: Write (for comments)
     - Metadata: Read
   - **Account permissions**:
     - Email: Read

### 4. Install GitHub App on Repository

1. Go to your GitHub App settings
2. Click "Install App" or "Public page"
3. Install on the repositories where you want automated reviews
4. Grant the necessary permissions

### 5. Test the Webhook

#### Option A: Create a Test PR

1. Create a new branch in a repository where the app is installed
2. Make some code changes
3. Open a pull request
4. Check the terminal for webhook events and processing logs

#### Option B: Manual Webhook Test

```bash
# Test webhook endpoint directly
curl -X POST https://your-ngrok-url.ngrok.io/api/webhook/github \
  -H "Content-Type: application/json" \
  -d '{"test": "webhook"}'
```

### 6. Monitor Webhook Activity

#### Backend Logs

```bash
# In the backend directory
tail -f logs/webhook.log
```

#### GitHub Webhook Deliveries

1. Go to GitHub App settings
2. Click "Advanced" tab
3. View "Recent Deliveries" to see webhook status and responses

## Webhook Flow

### 1. PR Events Trigger Webhooks

- **opened**: New PR created
- **synchronize**: PR updated with new commits
- **reopened**: Closed PR reopened

### 2. Webhook Processing

1. GitHub sends webhook to ngrok URL
2. Next.js API route forwards to FastAPI backend
3. Backend verifies webhook signature
4. Backend extracts PR information
5. Backend queues review job

### 3. AI Review Process

1. Fetch PR files from GitHub API
2. Analyze code with OpenAI GPT-4
3. Generate review comments
4. Post inline comments to PR
5. Update PR status check

### 4. Review Results

- **Inline comments**: Posted directly on specific lines
- **Status check**: Pass/fail based on review score
- **PR description**: Summary comment with overall findings

## Troubleshooting

### Common Issues

#### 1. Webhook Not Received

- **Check ngrok URL**: Ensure it matches the GitHub webhook URL
- **Check ngrok status**: Run `ngrok status` to verify tunnel is active
- **Firewall issues**: Ensure ports 3000 and 8000 are accessible

#### 2. Signature Verification Fails

- **Check webhook secret**: Ensure `GITHUB_WEBHOOK_SECRET` matches GitHub App setting
- **Check headers**: Verify `X-Hub-Signature-256` header is present

#### 3. Backend Connection Issues

- **Check backend URL**: Ensure `NEXT_PUBLIC_BACKEND_URL` is correct
- **Backend running**: Verify FastAPI server is running on port 8000
- **CORS issues**: Check if CORS is properly configured

#### 4. GitHub API Errors

- **Check permissions**: Verify GitHub App has required permissions
- **Rate limiting**: Check if hitting GitHub API rate limits
- **Authentication**: Verify GitHub App JWT token generation

### Debugging Commands

```bash
# Check ngrok status and URLs
ngrok status

# Test backend health
curl http://localhost:8000/health

# Test webhook proxy
curl -X POST http://localhost:3000/api/webhook/github \
  -H "Content-Type: application/json" \
  -d '{"test": "proxy"}'

# Check backend logs
tail -f backend/logs/app.log

# Check GitHub App JWT generation
node -e "console.log(require('./lib/github/auth').generateJWT())"
```

## Production Deployment

For production, replace ngrok with a proper domain:

### Option 1: Vercel Deployment

```bash
# Deploy to Vercel
npm run deploy

# Update GitHub webhook URL to:
# https://your-app.vercel.app/api/webhook/github
```

### Option 2: Custom Domain

```bash
# Deploy backend to Railway/Render/Heroku
npm run deploy:backend

# Update GitHub webhook URL to:
# https://your-domain.com/api/webhook/github
```

### Environment Variables for Production

```env
# Production backend URL
NEXT_PUBLIC_BACKEND_URL=https://your-backend.railway.app

# Same GitHub App credentials
GITHUB_APP_ID=your_app_id
GITHUB_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----"
GITHUB_WEBHOOK_SECRET=your_webhook_secret
```

## Security Considerations

1. **Webhook Secret**: Always use a strong, random webhook secret
2. **Signature Verification**: Backend always verifies GitHub webhook signatures
3. **Rate Limiting**: Implement rate limiting for webhook endpoints
4. **Logging**: Log all webhook events for monitoring and debugging
5. **Error Handling**: Graceful error handling to prevent webhook failures

## Example Webhook Payload

```json
{
  "action": "opened",
  "number": 1,
  "pull_request": {
    "id": 123456789,
    "number": 1,
    "title": "Add new feature",
    "state": "open",
    "head": {
      "sha": "abc123...",
      "ref": "feature-branch"
    },
    "base": {
      "sha": "def456...",
      "ref": "main"
    }
  },
  "repository": {
    "id": 987654321,
    "name": "my-repo",
    "full_name": "user/my-repo"
  }
}
```

This payload triggers the AI review process, which analyzes the PR diff and posts intelligent comments.
