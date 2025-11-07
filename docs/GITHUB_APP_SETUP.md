# GitHub App Setup Guide

## Overview

A GitHub App is **required** for the Git Review Assistant to function properly, especially for automated PR reviews with inline comments. This guide will walk you through creating and configuring your own GitHub App.

## Why You Need a GitHub App

GitHub Apps provide several critical features:

- **Webhook Events**: Automatically triggers reviews when PRs are created/updated
- **Inline PR Comments**: Posts AI-generated feedback directly on PR code lines
- **OAuth Authentication**: Secure user authentication without exposing personal tokens
- **Higher API Rate Limits**: 5,000 requests/hour vs 60 for unauthenticated requests
- **Fine-grained Permissions**: Control exactly what the app can access

## Step-by-Step Setup Guide

### Step 1: Create a New GitHub App

1. Navigate to GitHub Settings:
   - Go to [https://github.com/settings/apps](https://github.com/settings/apps)
   - Or: Click your profile → Settings → Developer settings → GitHub Apps

2. Click **"New GitHub App"**

3. Fill in the basic information:

#### Basic Information

```yaml
GitHub App name: ReviewBot Protocol
# Must be unique across all of GitHub

Homepage URL: http://localhost:3000
# For production: https://your-domain.com

Description: AI-powered code review assistant that provides intelligent feedback on pull requests
```

### Step 2: Configure Webhook Settings

#### Webhook Configuration

```yaml
Active: ✓ (checked)

Webhook URL: https://your-domain.com/api/webhook/github
# For local testing: Use ngrok (see "Local Development" section below)

Webhook secret: [Generate a strong random string]
# Save this! You'll need it for GITHUB_WEBHOOK_SECRET env variable
# Generate with: openssl rand -base64 32
```

### Step 3: Set Repository Permissions

Navigate to the **"Repository permissions"** section and set:

| Permission          | Access Level     | Purpose                               |
| ------------------- | ---------------- | ------------------------------------- |
| **Pull requests**   | Read & Write     | Read PR details, post review comments |
| **Contents**        | Read             | Access repository files for analysis  |
| **Issues**          | Write            | Create issue comments if needed       |
| **Metadata**        | Read             | Basic repository information          |
| **Actions**         | Read (optional)  | Check workflow status                 |
| **Checks**          | Write (optional) | Create check runs for PR status       |
| **Commit statuses** | Write (optional) | Update commit status indicators       |

### Step 4: Subscribe to Webhook Events

In the **"Subscribe to events"** section, check:

- ✓ **Pull request** - Triggers on PR open/close/sync
- ✓ **Pull request review** - Triggers on review submission
- ✓ **Pull request review comment** - Triggers on inline comments
- ✓ **Push** (optional) - Triggers on direct pushes

### Step 5: Configure OAuth & Permissions

#### User Permissions

```yaml
Account permissions:
  - Email addresses: Read
  - Profile: Read
```

#### OAuth Configuration

```yaml
Callback URL: http://localhost:3000/api/auth/github/callback
# For production: https://your-domain.com/api/auth/github/callback

Request user authorization (OAuth) during installation: ✓
```

### Step 6: Where Can This App Be Installed?

Choose based on your needs:

- **Only on this account**: For personal/private use
- **Any account**: For public/open-source projects

### Step 7: Create the App

Click **"Create GitHub App"** button

### Step 8: Generate and Download Private Key

After creation:

1. Scroll to **"Private keys"** section
2. Click **"Generate a private key"**
3. A `.pem` file will download automatically
4. **IMPORTANT**: Store this securely - you cannot regenerate the same key!

### Step 9: Note Your App Credentials

From the app settings page, copy these values:

```bash
App ID: 123456  # Found at the top of the page
Client ID: Iv1.a1b2c3d4e5f6  # In "OAuth Apps" section
Client Secret: [Click "Generate a new client secret"]
Webhook Secret: [The one you created in Step 2]
```

### Step 10: Install the App to Your Repository

1. Go to the **"Install App"** tab
2. Click **"Install"** next to your account
3. Choose repositories:
   - **All repositories**: For full access
   - **Selected repositories**: Choose specific repos

## Environment Variable Configuration

### Frontend (.env.local)

```bash
# GitHub App Configuration
GITHUB_APP_ID=123456
GITHUB_APP_NAME=reviewbot-protocol
GITHUB_CLIENT_ID=Iv1.a1b2c3d4e5f6
GITHUB_CLIENT_SECRET=abc123def456ghi789

# The private key - IMPORTANT: Use quotes and preserve line breaks
GITHUB_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA1234...
[full key content]
-----END RSA PRIVATE KEY-----"

# Webhook secret for signature verification
GITHUB_WEBHOOK_SECRET=your-webhook-secret-from-step-2
```

### Backend (backend/.env)

```bash
# GitHub App Configuration
GITHUB_APP_ID=123456
GITHUB_APP_NAME=reviewbot-protocol
GITHUB_TOKEN=ghp_... # Personal access token for API calls
GITHUB_WEBHOOK_SECRET=your-webhook-secret-from-step-2

# Private key path or content
GITHUB_PRIVATE_KEY_PATH=./github-app-key.pem
# OR
GITHUB_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----..."
```

## Local Development with Ngrok

For local webhook testing, you need a public URL. Use ngrok:

### Install Ngrok

```bash
# macOS
brew install ngrok

# Linux
snap install ngrok

# Or download from https://ngrok.com/download
```

### Start Ngrok Tunnel

```bash
# Start your backend first
cd backend && source .venv/bin/activate && uvicorn main:app --reload

# In another terminal, start ngrok
ngrok http 8000

# You'll see output like:
# Forwarding: https://abc123.ngrok.io -> http://localhost:8000
```

### Update Webhook URL

1. Go to your GitHub App settings
2. Update Webhook URL to: `https://abc123.ngrok.io/webhook/github`
3. Save changes

## Testing Your GitHub App

### 1. Test Webhook Delivery

1. Go to GitHub App settings → Advanced → Recent Deliveries
2. Create/update a PR in an installed repository
3. Check for webhook delivery and response

### 2. Test OAuth Flow

```bash
# Visit in browser
http://localhost:3000/api/auth/github

# Should redirect to GitHub OAuth, then back to your app
```

### 3. Test API Access

```python
# Test script (Python)
import requests
import jwt
import time

def generate_jwt(app_id, private_key):
    payload = {
        'iat': int(time.time()),
        'exp': int(time.time()) + 600,
        'iss': app_id
    }
    return jwt.encode(payload, private_key, algorithm='RS256')

# Make API call with app authentication
app_jwt = generate_jwt(GITHUB_APP_ID, GITHUB_PRIVATE_KEY)
response = requests.get(
    'https://api.github.com/app',
    headers={'Authorization': f'Bearer {app_jwt}'}
)
print(response.json())
```

### 4. Test PR Review

```bash
# Trigger a test review
curl -X POST http://localhost:8000/review/pr \
  -H "Content-Type: application/json" \
  -d '{
    "repository": "your-username/test-repo",
    "pr_number": 1,
    "force_refresh": false
  }'
```

## Common Issues & Solutions

### Issue: Webhook not receiving events

- **Solution**: Check ngrok is running and URL is updated in GitHub App settings
- Verify webhook secret matches in both GitHub and your `.env` files

### Issue: 401 Unauthorized errors

- **Solution**: Ensure private key is properly formatted with line breaks preserved
- Check App ID and Client ID are correct

### Issue: Cannot post PR comments

- **Solution**: Verify "Pull requests" permission is set to "Write"
- Ensure app is installed on the target repository

### Issue: Rate limiting

- **Solution**: Use app authentication instead of personal tokens
- Implement caching for frequently accessed data

## Security Best Practices

1. **Never commit secrets**: Add `.env*` to `.gitignore`
2. **Rotate keys regularly**: Generate new client secrets periodically
3. **Use environment variables**: Never hardcode credentials
4. **Validate webhooks**: Always verify webhook signatures
5. **Minimum permissions**: Only request necessary permissions
6. **Secure storage**: Use secret management services in production

## Production Deployment

For production deployment:

1. **Update URLs**: Change all `localhost` references to your domain
2. **SSL Required**: GitHub webhooks require HTTPS endpoints
3. **Secret Management**: Use services like AWS Secrets Manager or HashiCorp Vault
4. **Monitoring**: Set up webhook failure alerts
5. **Backup Keys**: Store private keys securely with backups

## Webhook Payload Examples

### Pull Request Opened

```json
{
  "action": "opened",
  "pull_request": {
    "id": 1,
    "number": 123,
    "title": "Add new feature",
    "user": {
      "login": "developer"
    },
    "base": {
      "ref": "main"
    },
    "head": {
      "ref": "feature-branch",
      "sha": "abc123"
    }
  },
  "repository": {
    "full_name": "owner/repo"
  }
}
```

### Automated Review Comment

```json
{
  "path": "src/components/Button.tsx",
  "line": 42,
  "side": "RIGHT",
  "body": "🔒 **Security Issue**: Potential XSS vulnerability..."
}
```

## Verification Checklist

Before considering your GitHub App setup complete:

- [ ] App created with unique name
- [ ] Webhook URL configured (ngrok for local, HTTPS for production)
- [ ] Webhook secret generated and saved
- [ ] Repository permissions configured (Pull requests: Write)
- [ ] Webhook events subscribed (pull_request, pull_request_review)
- [ ] OAuth callback URL set
- [ ] Private key generated and saved
- [ ] App installed on target repositories
- [ ] Environment variables configured in both frontend and backend
- [ ] Test webhook delivery successful
- [ ] Test OAuth flow working
- [ ] Test PR review endpoint functioning

## Resources

- [GitHub Apps Documentation](https://docs.github.com/en/developers/apps)
- [Webhook Events Reference](https://docs.github.com/en/developers/webhooks-and-events/webhooks/webhook-events-and-payloads)
- [GitHub API Rate Limiting](https://docs.github.com/en/rest/overview/resources-in-the-rest-api#rate-limiting)
- [Ngrok Documentation](https://ngrok.com/docs)
- [JWT.io - JWT Debugger](https://jwt.io/)

## Support

If you encounter issues:

1. Check GitHub App settings → Advanced → Recent Deliveries for webhook logs
2. Review backend logs for error messages
3. Verify all environment variables are set correctly
4. Test with the API test script: `./scripts/test-all-apis.sh`
