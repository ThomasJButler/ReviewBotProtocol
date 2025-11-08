# GitHub App Setup Guide

## Overview

A GitHub App is **required** for ReviewBot Protocol to function properly, especially for automated PR reviews with inline comments. This guide mirrors the exact GitHub App registration form to make setup straightforward.

## Why You Need a GitHub App

GitHub Apps provide several critical features:

- **Webhook Events**: Automatically triggers reviews when PRs are created/updated
- **Inline PR Comments**: Posts AI-generated feedback directly on PR code lines
- **OAuth Authentication**: Secure user authentication without exposing personal tokens
- **Higher API Rate Limits**: 5,000 requests/hour vs 60 for unauthenticated requests
- **Fine-grained Permissions**: Control exactly what the app can access

---

## Step-by-Step Setup Guide

### Step 1: Navigate to GitHub Apps

1. Go to [https://github.com/settings/apps](https://github.com/settings/apps)
2. Or: Click your profile → Settings → Developer settings → GitHub Apps
3. Click **"New GitHub App"**

---

### Step 2: Register New GitHub App

Follow each section of the registration form:

#### **GitHub App name**

```
ReviewBot Protocol
```

> **Note**: The name of your GitHub App. Must be unique across all of GitHub. This is displayed to users of your GitHub App.

#### **Homepage URL**

```
http://localhost:3000
```

For production deployment:
```
https://your-domain.com
```

> The full URL to your GitHub App's website.

---

### Step 3: Identifying and Authorizing Users

#### **Callback URL**

```
http://localhost:3000/api/auth/github/callback
```

For production:
```
https://your-domain.com/api/auth/github/callback
```

> The full URL to redirect to after a user authorizes an installation.

#### **User Authorization Options**

- ☐ **Expire user authorization tokens**
  _Optional: Provides a refresh_token which can be used to request an updated access token when this access token expires._

- ☑ **Request user authorization (OAuth) during installation**
  _Requests that the installing user grants access to their identity during installation of your App._

- ☐ **Enable Device Flow**
  _Optional: Allow this GitHub App to authorize users via the Device Flow._

> Read the [Identifying and authorizing users for GitHub Apps](https://docs.github.com/en/developers/apps/building-github-apps/identifying-and-authorizing-users-for-github-apps) documentation for more information.

---

### Step 4: Post Installation

#### **Setup URL (optional)**

```
(Leave blank for now)
```

> Users will be redirected to this URL after installing your GitHub App to complete additional setup.

- ☐ **Redirect on update**
  _Redirect users to the 'Setup URL' after installations are updated (e.g., repositories added/removed)._

---

### Step 5: Webhook Configuration

#### **Active**

- ☑ **Active**
  _We will deliver event details when this hook is triggered._

#### **Webhook URL**

**For local development (using ngrok):**
```
https://YOUR-NGROK-ID.ngrok.io/webhook/github
```

**For production:**
```
https://your-domain.com/api/webhook/github
```

> Events will POST to this URL. Read the [webhook documentation](https://docs.github.com/en/developers/webhooks-and-events) for more information.

#### **Webhook Secret**

Generate a strong secret:
```bash
openssl rand -base64 32
```

Example output:
```
8xK3nQ7mP2wV9cR5tY1uZ4sA6bN0jH8fE3gL7dM9
```

> **IMPORTANT**: Save this secret! You'll need it for `GITHUB_WEBHOOK_SECRET` environment variable.
> Read the [webhook secret documentation](https://docs.github.com/en/developers/webhooks-and-events/webhooks/securing-your-webhooks) for more information.

---

### Step 6: Permissions

User permissions are granted on an individual user basis as part of the User authorization flow. Read the [permissions documentation](https://docs.github.com/en/developers/apps/building-github-apps/setting-permissions-for-github-apps) for information about specific permissions.

#### **Repository Permissions**

Repository permissions permit access to repositories and related resources.

| Permission          | Access Level     | Purpose                                    |
| ------------------- | ---------------- | ------------------------------------------ |
| **Pull requests**   | Read and write   | Read PR details, post inline review comments |
| **Contents**        | Read-only        | Access repository files for code analysis  |
| **Issues**          | Read and write   | Create issue comments (optional)           |
| **Metadata**        | Read-only        | Basic repository information (automatic)   |
| **Commit statuses** | Read and write   | Update commit status indicators (optional) |
| **Checks**          | Read and write   | Create check runs for PR status (optional) |

#### **Organization Permissions**

_Leave all at "No access" unless you need organization-level features._

#### **Account Permissions**

These permissions are granted on an individual user basis as part of the User authorization flow.

| Permission              | Access Level | Purpose                     |
| ----------------------- | ------------ | --------------------------- |
| **Email addresses**     | Read-only    | Access user email for OAuth |
| **Profile information** | Read-only    | Access user profile data    |

---

### Step 7: Subscribe to Events

Based on the permissions you've selected, what events would you like to subscribe to?

**Required Events:**

- ☑ **Pull request**
  _Pull request opened, closed, reopened, synchronize, etc._

- ☑ **Pull request review**
  _Pull request review submitted, edited, or dismissed._

**Optional Events:**

- ☑ **Pull request review comment**
  _Pull request diff comment created, edited, or deleted._

- ☐ **Push**
  _Git push to a repository._

- ☐ **Installation target**
  _A GitHub App installation target is renamed._

- ☐ **Meta**
  _When this App is deleted and the associated hook is removed._

- ☐ **Security advisory**
  _Security advisory published, updated, or withdrawn._

---

### Step 8: Where Can This GitHub App Be Installed?

Choose based on your use case:

- ⦿ **Only on this account**
  _Only allow this GitHub App to be installed on your personal account._
  **Recommended for**: Personal projects, testing, course demos

- ○ **Any account**
  _Allow this GitHub App to be installed by any user or organization._
  **Recommended for**: Public/open-source projects, production apps

---

### Step 9: Create GitHub App

Click **"Create GitHub App"** button at the bottom of the page.

---

## Post-Creation Configuration

### Step 10: Generate Private Key

After creating the app:

1. Scroll to **"Private keys"** section on your app's settings page
2. Click **"Generate a private key"**
3. A `.pem` file will download automatically
4. **CRITICAL**: Store this file securely - you cannot regenerate the same key!

```bash
# Move the downloaded key to a secure location
mv ~/Downloads/reviewbot-protocol.*.private-key.pem ~/.ssh/github-app-key.pem
chmod 600 ~/.ssh/github-app-key.pem
```

### Step 11: Generate Client Secret

1. Scroll to **"Client secrets"** section
2. Click **"Generate a new client secret"**
3. Copy the secret immediately (it won't be shown again)
4. Save it for the `GITHUB_CLIENT_SECRET` environment variable

### Step 12: Note Your App Credentials

From the app settings page, gather these values:

```bash
App ID: 123456                    # Found at the top of the page
Client ID: Iv1.a1b2c3d4e5f6       # In "About" section
Client Secret: [from Step 11]     # Just generated
Webhook Secret: [from Step 5]     # The one you created earlier
Private Key: [from Step 10]       # Path to .pem file
```

### Step 13: Install the App

1. Click **"Install App"** in the left sidebar
2. Click **"Install"** next to your account
3. Choose repository access:
   - **All repositories**: For testing across multiple repos
   - **Only select repositories**: Choose specific repos (recommended)
4. Click **"Install"**

---

## Environment Configuration

### Frontend (.env.local)

Create or update `.env.local` in the project root:

```bash
# GitHub App Configuration
GITHUB_APP_ID=123456
GITHUB_APP_NAME=reviewbot-protocol
GITHUB_CLIENT_ID=Iv1.a1b2c3d4e5f6
GITHUB_CLIENT_SECRET=ghs_abc123def456ghi789

# Private key - IMPORTANT: Preserve line breaks, use quotes
GITHUB_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA1234567890...
[full key content - do not modify]
...xyz
-----END RSA PRIVATE KEY-----"

# Webhook secret for signature verification
GITHUB_WEBHOOK_SECRET=8xK3nQ7mP2wV9cR5tY1uZ4sA6bN0jH8fE3gL7dM9

# App URLs
NEXT_PUBLIC_APP_URL=http://localhost:3000
NEXT_PUBLIC_GITHUB_APP_NAME=reviewbot-protocol
```

### Backend (backend/.env)

Create or update `backend/.env`:

```bash
# GitHub App Configuration
GITHUB_APP_ID=123456
GITHUB_APP_NAME=reviewbot-protocol
GITHUB_WEBHOOK_SECRET=8xK3nQ7mP2wV9cR5tY1uZ4sA6bN0jH8fE3gL7dM9

# Private key - Either path OR content
GITHUB_PRIVATE_KEY_PATH=~/.ssh/github-app-key.pem
# OR embed the key content:
# GITHUB_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----..."

# OpenAI API Key (for AI reviews)
OPENAI_API_KEY=sk-proj-...

# LangChain Configuration
LANGCHAIN_API_KEY=lsv2_pt_...
LANGCHAIN_PROJECT=reviewbot-protocol
LANGCHAIN_TRACING_V2=true
```

---

## Local Development with Ngrok

For local webhook testing, you need a publicly accessible URL. GitHub cannot send webhooks to `localhost`.

### Install Ngrok

```bash
# macOS
brew install ngrok

# Linux
snap install ngrok

# Or download from https://ngrok.com/download
```

### Create Ngrok Account

1. Sign up at [https://ngrok.com](https://ngrok.com)
2. Get your auth token from the dashboard
3. Configure ngrok:

```bash
ngrok config add-authtoken YOUR_AUTH_TOKEN
```

### Start Development Environment

**Terminal 1 - Backend:**
```bash
cd backend
source .venv/bin/activate
uvicorn main:app --reload --port 8000
```

**Terminal 2 - Ngrok Tunnel:**
```bash
ngrok http 8000
```

You'll see output like:
```
Forwarding    https://abc123def456.ngrok.io -> http://localhost:8000
```

**Terminal 3 - Frontend:**
```bash
npm run dev
```

### Update Webhook URL in GitHub App

1. Copy the ngrok forwarding URL (e.g., `https://abc123def456.ngrok.io`)
2. Go to your GitHub App settings
3. Update **Webhook URL** to: `https://abc123def456.ngrok.io/webhook/github`
4. Click **"Save changes"**

> **Note**: Ngrok URLs change each time you restart ngrok (unless you have a paid plan). You'll need to update the webhook URL each time.

---

## Testing Your Setup

### 1. Test Webhook Delivery

1. Go to your GitHub App settings → **Advanced** → **Recent Deliveries**
2. Create or update a PR in a repository where the app is installed
3. Refresh the Recent Deliveries page
4. You should see a webhook delivery with a green checkmark ✓

**If you see a red X:**
- Check ngrok is running
- Verify the webhook URL is correct
- Check backend logs for errors

### 2. Test OAuth Flow

Visit in your browser:
```
http://localhost:3000/api/auth/github
```

You should be:
1. Redirected to GitHub OAuth page
2. Asked to authorize the app
3. Redirected back to your app

### 3. Test API Authentication

Create a test script `test_app_auth.py`:

```python
import requests
import jwt
import time
from pathlib import Path

# Your credentials
APP_ID = "123456"
PRIVATE_KEY_PATH = Path.home() / ".ssh" / "github-app-key.pem"

# Generate JWT
def generate_jwt(app_id, private_key_path):
    with open(private_key_path, 'r') as key_file:
        private_key = key_file.read()

    payload = {
        'iat': int(time.time()),
        'exp': int(time.time()) + 600,  # 10 minutes
        'iss': app_id
    }
    return jwt.encode(payload, private_key, algorithm='RS256')

# Test authentication
app_jwt = generate_jwt(APP_ID, PRIVATE_KEY_PATH)
response = requests.get(
    'https://api.github.com/app',
    headers={
        'Authorization': f'Bearer {app_jwt}',
        'Accept': 'application/vnd.github.v3+json'
    }
)

print("Status Code:", response.status_code)
print("App Info:", response.json())
```

Run it:
```bash
python test_app_auth.py
```

Expected output:
```json
{
  "id": 123456,
  "name": "ReviewBot Protocol",
  "owner": { ... },
  "created_at": "2024-...",
  ...
}
```

### 4. Test PR Review Flow

1. Create a test PR in a repository where the app is installed
2. Check backend logs for webhook receipt
3. Verify PR receives AI-generated inline comments
4. Check GitHub App settings → Recent Deliveries for webhook status

---

## Common Issues & Solutions

### Issue: Webhook not receiving events

**Symptoms:**
- No entries in GitHub App → Advanced → Recent Deliveries
- Backend not logging webhook receipts

**Solutions:**
- ✓ Verify ngrok is running (`ngrok http 8000`)
- ✓ Check webhook URL matches ngrok forwarding URL
- ✓ Ensure backend is running on correct port (8000)
- ✓ Verify webhook events are subscribed (pull_request, etc.)

### Issue: 401 Unauthorized errors

**Symptoms:**
- API calls return 401
- Cannot authenticate as GitHub App

**Solutions:**
- ✓ Ensure private key is properly formatted with line breaks
- ✓ Check `GITHUB_APP_ID` matches the App ID in settings
- ✓ Verify JWT generation is correct (not expired)
- ✓ Confirm private key file permissions (`chmod 600`)

### Issue: Cannot post PR comments

**Symptoms:**
- Review runs but no comments appear on PR
- API returns 403 Forbidden

**Solutions:**
- ✓ Verify "Pull requests" permission is "Read and write"
- ✓ Ensure app is installed on the target repository
- ✓ Check the app has access to the specific repository
- ✓ Verify installation ID is correct for the repository

### Issue: Webhook signature verification fails

**Symptoms:**
- Backend logs show "Invalid signature"
- Webhooks are rejected

**Solutions:**
- ✓ Ensure `GITHUB_WEBHOOK_SECRET` matches in both GitHub App settings and `.env`
- ✓ Check for trailing whitespace in webhook secret
- ✓ Verify signature validation code is using SHA-256
- ✓ Test with GitHub's webhook delivery "Redeliver" button

### Issue: Rate limiting

**Symptoms:**
- API returns 403 with rate limit message
- Headers show `X-RateLimit-Remaining: 0`

**Solutions:**
- ✓ Use GitHub App authentication (5,000 req/hour) instead of personal tokens (60 req/hour)
- ✓ Implement caching for frequently accessed data
- ✓ Add request throttling to avoid burst limits
- ✓ Check rate limit status: `curl https://api.github.com/rate_limit -H "Authorization: Bearer YOUR_JWT"`

---

## Security Best Practices

1. **Never commit secrets**
   ```bash
   # Ensure .gitignore includes:
   .env
   .env.local
   .env*.local
   *.pem
   *.key
   ```

2. **Rotate credentials regularly**
   - Regenerate client secrets every 90 days
   - Rotate webhook secrets periodically
   - Generate new private keys if compromised

3. **Use environment variables**
   - Never hardcode credentials in source code
   - Use different secrets for dev/staging/production

4. **Validate all webhooks**
   - Always verify webhook signatures
   - Reject webhooks with invalid signatures
   - Log suspicious webhook attempts

5. **Minimum permissions principle**
   - Only request permissions you actually need
   - Review permissions quarterly
   - Remove unused permissions

6. **Secure production deployment**
   - Use secret management services (AWS Secrets Manager, Vercel Environment Variables)
   - Enable webhook secret rotation
   - Monitor for unauthorized access attempts

---

## Production Deployment Checklist

Before deploying to production:

- [ ] Update all URLs from `localhost` to production domain
- [ ] Ensure HTTPS is enabled (GitHub requires SSL for webhooks)
- [ ] Configure secret management system
- [ ] Set up monitoring and alerting for webhook failures
- [ ] Backup private key securely (encrypted, off-site)
- [ ] Enable webhook signature verification
- [ ] Configure rate limiting and caching
- [ ] Set up error tracking (Sentry, etc.)
- [ ] Test OAuth flow with production URLs
- [ ] Test webhook delivery with production endpoint
- [ ] Document incident response procedures
- [ ] Set up log aggregation and monitoring

---

## Verification Checklist

Before considering your GitHub App setup complete:

- [ ] App created with unique name
- [ ] Homepage URL configured
- [ ] Callback URL set correctly
- [ ] "Request user authorization during installation" enabled
- [ ] Webhook URL configured (ngrok for local, HTTPS for production)
- [ ] Webhook marked as "Active"
- [ ] Webhook secret generated and saved
- [ ] Repository permissions set:
  - [ ] Pull requests: Read and write
  - [ ] Contents: Read-only
  - [ ] Metadata: Read-only (automatic)
- [ ] Account permissions set:
  - [ ] Email addresses: Read-only
  - [ ] Profile: Read-only
- [ ] Events subscribed:
  - [ ] Pull request
  - [ ] Pull request review
  - [ ] Pull request review comment (optional)
- [ ] Installation target selected (personal or any account)
- [ ] Private key generated and downloaded
- [ ] Private key stored securely with correct permissions
- [ ] Client secret generated and saved
- [ ] App installed on target repositories
- [ ] Environment variables configured:
  - [ ] Frontend `.env.local`
  - [ ] Backend `backend/.env`
- [ ] Ngrok tunnel running (for local dev)
- [ ] Test webhook delivery successful
- [ ] Test OAuth flow working
- [ ] Test PR review creating inline comments

---

## Resources

### Official Documentation
- [GitHub Apps Documentation](https://docs.github.com/en/developers/apps)
- [Webhook Events Reference](https://docs.github.com/en/developers/webhooks-and-events/webhooks/webhook-events-and-payloads)
- [GitHub API Rate Limiting](https://docs.github.com/en/rest/overview/resources-in-the-rest-api#rate-limiting)
- [Authenticating as a GitHub App](https://docs.github.com/en/developers/apps/building-github-apps/authenticating-with-github-apps)

### Tools
- [Ngrok Documentation](https://ngrok.com/docs)
- [JWT.io - JWT Debugger](https://jwt.io/)
- [GitHub Webhook Tester](https://webhook.site/)

### ReviewBot Protocol Specific
- [Main README](../README.md)
- [Backend README](../backend/README.md)
- [Testing Guide](../testing.md)

---

## Support

If you encounter issues not covered in this guide:

1. **Check Recent Deliveries**: GitHub App settings → Advanced → Recent Deliveries
2. **Review Backend Logs**: Check FastAPI console output for errors
3. **Verify Environment Variables**: Ensure all required vars are set correctly
4. **Test Individual Components**: Use the test scripts in this guide
5. **Check GitHub Status**: [https://www.githubstatus.com/](https://www.githubstatus.com/)

For ReviewBot Protocol-specific issues, run the test suite:
```bash
# Backend tests
cd backend && pytest -v

# Frontend tests
npm run test
```

---

**Last Updated**: 2024-11-08
**ReviewBot Protocol Version**: 1.04
