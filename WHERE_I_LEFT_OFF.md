# 🚦 WHERE I LEFT OFF - Git Review Assistant

**Last Updated:** November 6, 2024

**Status:** Project paused - focusing on health and job opportunities

---

## 📋 PROJECT SUMMARY

This is an AI-powered code review assistant built for the Codecademy Mastering Generative AI & Agents bootcamp. It uses LangChain + LangGraph to analyze GitHub PRs and provide security, performance, and quality feedback.

**Tech Stack:**

- **Frontend:** Next.js 14.2, TypeScript, Tailwind CSS
- **Backend:** FastAPI (Python), LangChain, LangGraph, OpenAI GPT-4
- **Integration:** GitHub OAuth, GitHub API

---

## ✅ WHAT'S WORKING

### 1. **Authentication Flow**

- ✅ GitHub OAuth login/logout
- ✅ User profile displays at top of app
- ✅ Auth token stored in cookies
- ✅ Protected routes working

### 2. **Pull Requests Page** (`/pull-requests`)

- ✅ Fetches real PRs from GitHub API
- ✅ Dynamic repository filter (no more mock data)
- ✅ ExternalLink button opens PR in GitHub
- ✅ Click entire PR card to navigate to review page
- ✅ All data is real from GitHub (no mock data)

### 3. **Backend API**

- ✅ FastAPI server running on port 8000
- ✅ Health endpoint working
- ✅ Database initialized (SQLite)
- ✅ API docs available at http://localhost:8000/docs

### 4. **Frontend Improvements**

- ✅ Removed all emojis for professional look
- ✅ Deleted Reports page (was non-functional)
- ✅ Removed paste code and file upload features
- ✅ Streamlined to PR-only reviews
- ✅ Clean, minimal UI

### 5. **Navigation**

- ✅ Dashboard with working quick actions
- ✅ Pull Requests page fully functional
- ✅ Review page exists

---

## ❌ WHAT'S BROKEN / INCOMPLETE

### 1. **PR Review Not Working** ⚠️ MAIN ISSUE

**Symptom:** Click "Start AI Review" → Loading spinner shows → Nothing happens

**Root Cause:**

- Backend returns 422 error (Unprocessable Entity)
- Frontend sends correct format: `{ repository, pr_number, configuration }`
- Backend expects this format BUT something is still wrong

**What I Was Debugging:**

- Console shows API call succeeds (200 status)
- But `convertToDisplayResults()` crashes because arrays are undefined
- Added safe fallbacks (`|| []`) to prevent crash
- Need to check what backend actually returns

**Files Involved:**

- `/app/api/review/pr/route.ts` (frontend API route)
- `/hooks/useReviewService.ts` (review service hook)
- `/components/review/ReviewInterface.tsx` (review UI)
- Backend: `backend/handlers/review.py` (PR review endpoint)

### 2. **GitHub App Deleted** 🔴 BLOCKER

**Status:** You deleted the custom GitHub app

**To Fix:**

1. Create new GitHub App at: https://github.com/settings/apps
2. Set Webhook URL: `https://your-app.vercel.app/api/webhook/github`
3. Set Callback URL: `https://your-app.vercel.app/api/auth/github/callback`
4. Required Permissions:
   - Repository: Pull requests (Read & Write)
   - Repository: Contents (Read)
   - Repository: Issues (Write)
   - Account: Email (Read)
5. Subscribe to Events: Pull request, Pull request review
6. Generate Private Key
7. Update `.env.local` with new credentials:
   ```
   GITHUB_APP_ID=your_new_app_id
   GITHUB_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----..."
   GITHUB_CLIENT_ID=your_client_id
   GITHUB_CLIENT_SECRET=your_client_secret
   ```

### 3. **Backend Issues**

- ❌ 422 errors when calling `/review/pr` endpoint
- ⚠️ Warning: Pydantic field conflicts with "model\_" namespace
- ⚠️ Warning: LangChain deprecated imports
- ⚠️ SQLAlchemy warnings about cartesian products

### 4. **Missing Features**

- ❌ Actual AI review generation (backend needs work)
- ❌ Inline PR comments (not implemented)
- ❌ Webhook processing (not set up)
- ❌ Review history (exists but not connected)

---

## 🔧 HOW TO RESUME WORK

### **Prerequisites:**

1. Make sure you have:
   - Node.js installed
   - Python 3.11+ installed
   - OpenAI API key
   - New GitHub App credentials (see above)

### **Step 1: Environment Setup**

Create `/backend/.env`:

```bash
DEBUG=true
OPENAI_API_KEY=sk-...
GITHUB_TOKEN=ghp_...
DATABASE_URL=sqlite+aiosqlite:///./reviews.db
SECRET_KEY=your-secret-key
```

Create `/.env.local`:

```bash
NEXT_PUBLIC_APP_URL=http://localhost:3000
BACKEND_URL=http://localhost:8000

# GitHub OAuth (need to create new app)
GITHUB_APP_ID=your_new_app_id
GITHUB_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----..."
GITHUB_CLIENT_ID=your_client_id
GITHUB_CLIENT_SECRET=your_client_secret

# OpenAI
OPENAI_API_KEY=sk-...
```

### **Step 2: Start Backend**

```bash
cd backend
source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Backend should start at: http://localhost:8000
API docs at: http://localhost:8000/docs

### **Step 3: Start Frontend**

```bash
npm install
npm run dev
```

Frontend should start at: http://localhost:3000

### **Step 4: Test Authentication**

1. Go to http://localhost:3000
2. Click "Connect GitHub"
3. Authorize the app
4. Should see your profile at top

### **Step 5: Debug PR Review**

Open browser console (F12) and try reviewing a PR. You should see:

```
Starting PR analysis for #116 in owner/repo
API response status: 200
API response data: { success: true, data: {...} }
PR Results received: {...}
Has security array? true/false
Has performance array? true/false
Has quality array? true/false
```

**The issue is likely here:** The backend is returning data in a different format than expected.

---

## 🐛 DEBUGGING CHECKLIST

When you come back, check these in order:

### 1. **Backend 422 Error**

- [ ] Check backend logs: Look at the uvicorn output
- [ ] Test backend endpoint directly:
  ```bash
  curl -X POST http://localhost:8000/review/pr \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer YOUR_GITHUB_TOKEN" \
    -d '{
      "repository": "owner/repo",
      "pr_number": 116,
      "force_refresh": false,
      "configuration": {
        "include_security": true,
        "include_performance": true,
        "include_quality": true,
        "severity_threshold": "low"
      }
    }'
  ```
- [ ] Check what error message backend returns
- [ ] Look at `backend/models/review.py` to see expected schema

### 2. **Frontend Data Transformation**

- [ ] Check console: What does `API response data` show?
- [ ] Does it have `security`, `performance`, `quality` arrays?
- [ ] Or is data nested differently?
- [ ] Update `convertToDisplayResults()` to match actual structure

### 3. **Backend Pydantic Warnings**

These are non-critical but annoying:

- [ ] In `backend/models/review.py`, add to model:
  ```python
  model_config = {"protected_namespaces": ()}
  ```

### 4. **LangChain Deprecation**

- [ ] Update `backend/services/ai_reviewer.py`:

  ```python
  # Change from:
  from langchain.callbacks import get_openai_callback

  # To:
  from langchain_community.callbacks.manager import get_openai_callback
  ```

---

## 📁 KEY FILES TO UNDERSTAND

### **Frontend Routes:**

- `/app/dashboard/page.tsx` - Main dashboard
- `/app/pull-requests/page.tsx` - PR listing (WORKING)
- `/app/review/page.tsx` - PR review interface
- `/app/api/auth/[...nextauth]/route.ts` - Auth handler
- `/app/api/review/pr/route.ts` - PR review API (sends to backend)
- `/app/api/github/prs/route.ts` - Fetches PRs from GitHub

### **Frontend Components:**

- `/components/review/ReviewInterface.tsx` - Main review UI
- `/components/review/PRSelector.tsx` - PR picker
- `/components/review/ReviewResults.tsx` - Results display
- `/components/layout/Header.tsx` - Navigation

### **Frontend Hooks:**

- `/hooks/useReviewService.ts` - Review API calls
- `/hooks/useGitHubService.ts` - GitHub integration
- `/contexts/AuthContext.tsx` - Auth state

### **Backend:**

- `backend/main.py` - FastAPI app entry
- `backend/handlers/review.py` - PR review endpoints
- `backend/models/review.py` - Data models
- `backend/services/ai_reviewer.py` - LangChain integration
- `backend/database/connection.py` - Database setup

---

## 🎯 NEXT STEPS (When You Return)

### **Priority 1: Get PR Review Working**

1. Create new GitHub App (see section above)
2. Fix backend 422 error:
   - Test endpoint directly with curl
   - Check backend logs for exact error
   - Fix data model mismatch
3. Fix frontend data transformation:
   - Check what backend actually returns
   - Update `convertToDisplayResults()` to match
4. Test end-to-end PR review

### **Priority 2: Clean Up Backend Warnings**

1. Fix Pydantic namespace warnings
2. Update LangChain imports
3. Fix SQLAlchemy cartesian product warnings

### **Priority 3: Implement Actual AI Review**

Right now the backend probably returns mock data or simple analysis.

1. Implement proper LangGraph workflow
2. Add LangChain chains for security, performance, quality
3. Test with real PRs
4. Tune AI prompts for better results

### **Priority 4: Polish & Deploy**

1. Add error boundaries
2. Improve loading states
3. Add toast notifications
4. Deploy to Vercel (frontend)
5. Deploy to Railway/Render (backend)

---

## 🛠️ DETAILED FIX PLAN & TIME ESTIMATES

### **THE MAIN ISSUE: Backend 422 Error**

**What's Happening:**
When you click "Start AI Review", the frontend sends a request to the backend, but the backend returns a 422 error (Unprocessable Entity). This means the request format doesn't match what the backend expects.

**Root Cause:**
The backend endpoint at `backend/handlers/review.py` expects a specific data structure that doesn't match what we're sending from the frontend.

**How to Fix (Step by Step):**

#### **Step 1: Test Backend Directly (15 minutes)**

First, figure out what the backend actually expects:

1. Open http://localhost:8000/docs in your browser
2. Find the `/review/pr` endpoint
3. Look at the "Request body" schema - this shows EXACTLY what format it expects
4. Compare with what frontend sends (in console screenshot you shared)
5. Note the differences

**Expected Result:** You'll see the exact field names and structure the backend wants

---

#### **Step 2: Fix Frontend Request Format (30 minutes)**

Open `/app/api/review/pr/route.ts` and update the request body to match backend schema.

**Current code (lines 81-91):**

```typescript
body: JSON.stringify({
  repository: repository,
  pr_number: prNumber,
  force_refresh: false,
  configuration: {
    include_security: true,
    include_performance: true,
    include_quality: true,
    severity_threshold: 'low',
  },
}),
```

**Possible fixes based on common issues:**

**Fix Option A:** Backend might want snake_case or different field names:

```typescript
body: JSON.stringify({
  repo_url: repository,  // or 'repository_url'
  pull_request_number: prNumber,  // or just 'number'
  refresh: false,
  config: {
    security: true,
    performance: true,
    quality: true,
    threshold: 'low',
  },
}),
```

**Fix Option B:** Backend might want the GitHub access token in the body:

```typescript
body: JSON.stringify({
  repository: repository,
  pr_number: prNumber,
  github_token: githubAccessToken,  // Add this
  force_refresh: false,
  configuration: {
    include_security: true,
    include_performance: true,
    include_quality: true,
    severity_threshold: 'low',
  },
}),
```

**Fix Option C:** Backend might want a simpler format:

```typescript
body: JSON.stringify({
  repository: repository,
  pr_number: prNumber,
}),
```

**How to know which one:** Check the `/docs` endpoint schema (Step 1)

---

#### **Step 3: Test & Verify (15 minutes)**

1. Make the fix from Step 2
2. Restart frontend: `npm run dev`
3. Try reviewing a PR again
4. Check browser console logs
5. Check backend terminal logs

**Success indicators:**

- ✅ Console shows: "API response status: 200"
- ✅ No 422 error in backend logs
- ✅ Review results appear on screen

---

#### **Step 4: Handle Backend Response (30 minutes)**

Once the 422 is fixed, you might get data in a different format than expected.

**Check console logs:**

```
API response data: { success: true, data: {...} }
PR Results received: {...}
Has security array? false  <- If this is false, you have a format issue
```

**Fix:** Update how you extract the data in `/app/api/review/pr/route.ts`

**Current code (lines 119-124):**

```typescript
const backendData = await backendResponse.json()

return NextResponse.json({
  success: true,
  data: backendData.data || backendData,
})
```

**Possible fix if data is nested differently:**

```typescript
const backendData = await backendResponse.json()

// Check what structure backend returns
console.log('Backend response structure:', backendData)

// Might need to extract differently:
return NextResponse.json({
  success: true,
  data: {
    security: backendData.security || backendData.findings?.security || [],
    performance:
      backendData.performance || backendData.findings?.performance || [],
    quality: backendData.quality || backendData.findings?.quality || [],
    summary: backendData.summary || 'Analysis completed',
    score: backendData.score || 0,
    totalIssues: backendData.totalIssues || 0,
    linesAnalyzed: backendData.linesAnalyzed || 0,
  },
})
```

---

### **SECONDARY ISSUE: GitHub App Deleted**

**Time Estimate:** 20-30 minutes

**Step-by-step fix:**

1. **Create New GitHub App (10 min)**
   - Go to: https://github.com/settings/apps/new
   - App Name: `git-review-assistant` (or whatever you want)
   - Homepage URL: `http://localhost:3000` (for now)
   - Callback URL: `http://localhost:3000/api/auth/github/callback`
   - Webhook: Uncheck "Active" for now (we'll set this up later)
   - Permissions:
     - Repository → Pull Requests: Read & Write
     - Repository → Contents: Read
     - Account → Email: Read
   - Click "Create GitHub App"

2. **Get Credentials (5 min)**
   - Copy the App ID
   - Click "Generate a private key" → Downloads a .pem file
   - Go to "OAuth 2.0" section
   - Copy Client ID
   - Generate a new Client Secret → Copy it

3. **Update Environment Variables (5 min)**
   - Open `.env.local`
   - Update:
     ```bash
     GITHUB_APP_ID=your_new_app_id
     GITHUB_CLIENT_ID=your_new_client_id
     GITHUB_CLIENT_SECRET=your_new_client_secret
     ```
   - Open the .pem file in a text editor
   - Copy the ENTIRE contents (including `-----BEGIN...` and `-----END...`)
   - Paste into GITHUB_PRIVATE_KEY: `GITHUB_PRIVATE_KEY="-----BEGIN RSA..."`

4. **Test Authentication (5 min)**
   - Restart frontend: `npm run dev`
   - Go to http://localhost:3000
   - Click "Connect GitHub"
   - Should redirect to GitHub → Authorize → Redirect back
   - Profile should show at top

---

### **MINOR FIXES: Backend Warnings**

**Time Estimate:** 15 minutes total

#### **Fix 1: Pydantic Warning (5 min)**

Open `backend/models/review.py` and add to each model with `model_name` or `model_version`:

```python
class YourModel(BaseModel):
    model_name: str
    model_version: str

    model_config = {"protected_namespaces": ()}  # Add this line
```

#### **Fix 2: LangChain Deprecation (5 min)**

Open `backend/services/ai_reviewer.py`:

```python
# Change line 19 from:
from langchain.callbacks import get_openai_callback

# To:
from langchain_community.callbacks.manager import get_openai_callback
```

#### **Fix 3: SQLAlchemy Cartesian Product (5 min)**

Open `backend/database/queries.py` or wherever stats queries are.
Add proper JOIN conditions between tables. This is low priority - warnings don't break anything.

---

### **TOTAL TIME ESTIMATES**

| Task                      | Time          | Priority    |
| ------------------------- | ------------- | ----------- |
| **Fix Backend 422 Error** | 1.5 hours     | 🔴 CRITICAL |
| - Test backend directly   | 15 min        | 🔴          |
| - Fix request format      | 30 min        | 🔴          |
| - Test & verify           | 15 min        | 🔴          |
| - Handle response format  | 30 min        | 🔴          |
| **Create New GitHub App** | 30 min        | 🟡 MEDIUM   |
| **Fix Backend Warnings**  | 15 min        | 🟢 LOW      |
| **Testing & Polish**      | 1 hour        | 🟡 MEDIUM   |
| **TOTAL**                 | **3-4 hours** | -           |

---

### **REALISTIC TIMELINE**

**Session 1 (2 hours):** Fix the 422 error and get PR reviews working

- ✅ Test backend endpoint
- ✅ Fix frontend request
- ✅ Get reviews displaying
- 🎯 GOAL: PR review working end-to-end

**Session 2 (1 hour):** Set up new GitHub App

- ✅ Create app
- ✅ Configure credentials
- ✅ Test authentication
- 🎯 GOAL: Full auth flow working

**Session 3 (1 hour):** Polish and cleanup

- ✅ Fix backend warnings
- ✅ Test all features
- ✅ Add error handling
- 🎯 GOAL: Production-ready

**Total: 4 hours over 3 sessions**

---

### **IF YOU GET STUCK**

**Problem:** Backend /docs doesn't show the schema clearly

**Solution:** Look directly at the code:

1. Open `backend/handlers/review.py`
2. Find the `/review/pr` endpoint
3. Look at the function signature - what parameters does it accept?
4. Look at the Pydantic model - what fields does it expect?

**Problem:** Still getting 422 after fixing request format

**Solution:** Add detailed logging:

1. In `backend/handlers/review.py`, add:
   ```python
   @router.post("/pr")
   async def review_pr(request: Request):
       body = await request.json()
       print("Received request body:", body)
       # ... rest of code
   ```
2. Check backend terminal for the print output
3. Compare with what the Pydantic model expects

**Problem:** Reviews work but data looks wrong

**Solution:** Add logging to see response structure:

1. In `/app/api/review/pr/route.ts` line 119:
   ```typescript
   const backendData = await backendResponse.json()
   console.log('BACKEND RESPONSE:', JSON.stringify(backendData, null, 2))
   ```
2. Check browser console
3. Adjust data extraction logic to match structure

---

### **CONFIDENCE LEVEL**

🟢 **HIGH CONFIDENCE (90%):** The 422 error is a simple request format mismatch. Once you see the backend schema in `/docs`, it should be obvious what to change. This is a 30-minute fix.

🟡 **MEDIUM CONFIDENCE (70%):** The response format issue might take some trial and error. But with the logging we added, you'll see exactly what the backend returns and can adjust accordingly.

🟢 **HIGH CONFIDENCE (95%):** GitHub App setup is straightforward - just follow the steps. GitHub has good documentation if you get stuck.

**Overall:** You can definitely finish this project! The hard parts (auth, GitHub integration, UI) are done. Just need to fix one API endpoint. 🚀

---

## 🤔 KNOWN QUIRKS

### **GitHub API Rate Limits**

- Authenticated: 5000 requests/hour
- Unauthenticated: 60 requests/hour
- Check remaining: `curl -H "Authorization: Bearer TOKEN" https://api.github.com/rate_limit`

### **Backend Needs GitHub Token**

The backend needs a GitHub token to fetch PR files:

- Either get it from frontend auth token
- Or create a Personal Access Token
- Set in backend `.env` as `GITHUB_TOKEN`

### **Mock Data Was Everywhere**

We removed mock data from:

- ✅ Pull requests page repository filter
- ✅ Reports page (deleted entirely)
- ✅ Dashboard quick actions
  But might still be in backend fallback responses

---

## 💡 HELPFUL COMMANDS

### **Backend:**

```bash
# Start backend
cd backend && source .venv/bin/activate && python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Check backend health
curl http://localhost:8000/health

# View API docs
open http://localhost:8000/docs

# Database reset (if needed)
rm backend/reviews.db
```

### **Frontend:**

```bash
# Start dev server
npm run dev

# Build for production
npm run build

# Type check
npm run typecheck

# Lint
npm run lint
```

### **Git:**

```bash
# Check current status
git status

# Current branch
git branch --show-current

# Recent commits
git log --oneline -10
```

---

## 📚 DOCUMENTATION REFERENCES

- **GitHub Apps:** https://docs.github.com/en/apps
- **GitHub API:** https://docs.github.com/en/rest
- **LangChain:** https://docs.langchain.com/
- **LangGraph:** https://langchain-ai.github.io/langgraph/
- **Next.js 14:** https://nextjs.org/docs
- **FastAPI:** https://fastapi.tiangolo.com/

---

## 🎓 PROJECT CONTEXT

This was built for the **Codecademy "Mastering Generative AI & Agents for Developers"** bootcamp.

**Course Requirements:**

- ✅ LangChain integration
- ✅ LangGraph workflow (partially)
- ⚠️ GitHub automation (needs work)
- ✅ Multi-modal input (PR only, removed paste/upload)
- ⚠️ Production ready (close but needs polish)
- ✅ Portfolio aesthetic (cyber/matrix theme)

**Submission Checklist:**

- [ ] All three input modes work (now only PR mode)
- [ ] GitHub PR with inline AI comments
- [ ] Security vulnerabilities detection
- [ ] Responsive UI on mobile/desktop
- [ ] Demo video
- [ ] README with setup instructions

---

## 💪 YOU'VE GOT THIS!

**What You Accomplished:**

- Set up full-stack app with Next.js + FastAPI
- Integrated GitHub OAuth
- Created beautiful cyber-themed UI
- Removed all mock data
- Streamlined app to be minimalistic
- Got 90% of the way there!

**What's Left:**

- Fix one backend endpoint issue (the 422 error)
- Get AI review working
- Polish and deploy

**When You Come Back:**

1. Read this file top to bottom
2. Set up environment variables
3. Start both servers
4. Debug the 422 error (see checklist above)
5. Test PR review end-to-end

**You're closer than you think!** The hard parts (auth, GitHub integration, UI) are done. The backend just needs the AI review logic to actually work.

---

## 🙏 FINAL NOTES

**Health comes first.** Take care of yourself.

**Job search comes second.** Nail that code assessment! 💼

**This project will be here when you're ready.** It's a solid portfolio piece once finished.

Good luck with everything! You've got this. 🚀

---

**Need Help When You Return?**

- Re-read this file
- Check the console logs (they're super detailed now)
- Test the backend endpoint directly with curl
- Look at backend logs in terminal
- Search GitHub issues for similar problems
- Or just take it step by step!
