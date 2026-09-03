# Frontend plan: four screens, shadcn/ui

Status: drafted and built 2026-09-03. See "What was built" at the end for the differences from the draft; anything here is cheap to change after seeing it on screen.

## Purpose

The dashboard answers three questions for the owner: what got reviewed, what the bot said, and was it any good. It is a local, single-user tool. It talks only to the backend on the same machine, through the token-gated /api routes, from Next.js server code (the token never reaches the browser). It sends nothing anywhere else: no fonts from Google, no analytics, no CDN scripts.

## Screens

### 1. Reviews (/)

The landing page. A single table, newest first.

Columns: repository, PR (number and title, linking to GitHub), when, model, files reviewed / skipped, findings (with a small severity breakdown, e.g. "3: 1 high, 2 low"), duration, useful (a thumbs up/down summary or a dash), status (completed, failed, running).

Controls above the table: a repository filter (select, populated from the API), a refresh button, and a status chip showing queue depth and whether Ollama is reachable (pulled from /api/status, refreshed every 30 seconds while the tab is visible).

Row click opens the review detail. Keyboard: rows are links, Tab reaches each, Enter opens.

Empty state: one card saying no reviews yet, with the two things to check (App installed on the repo, webhook pointing at the backend) and a link to Setup.

### 2. Review detail (/reviews/[id])

Header: repository, PR link, head SHA (short), model, when, duration, tokens in and out, fork badge if applicable, status. On failure: the sanitised error message in a muted callout.

"Was this useful?" control: two buttons (Useful, Not useful) that POST feedback and show the recorded answer. Stored locally only.

Findings: a list grouped by file, each finding a card with severity badge, category, title, the quoted evidence in a code block, the recommendation, confidence. Sorted by severity then line. Filter chips for severity.

Posted review: the body as it was posted, rendered as markdown with the same restrictions as the sanitiser (no HTML), and the count of inline comments attached, with a link to the review on GitHub.

Not reviewed: the skipped files with reasons.

### 3. Status (/status)

Cards: Ollama (reachable, model configured, model present, loaded models with context length and VRAM), Queue (depth, current job), Database (ok), Limits (files per review, patch bytes, timeout, context window), Recent deliveries (last 20 webhook deliveries with status and the review they produced), Egress proof (a short paragraph pointing at the two commands, and the result of the last local run if the backend records one).

### 4. Setup (/setup)

A checklist rendered from static content, with copyable snippets:
1. Install Ollama and pull the model (command).
2. Create the GitHub App: name, webhook URL, secret, permissions (Pull requests read and write, Metadata read; nothing else), events (Pull request only), install on selected repositories.
3. Backend .env values (the three GitHub values, the local token).
4. Expose the backend webhook route (tunnel or reverse proxy), set ALLOWED_HOSTS.
5. Verify: send a ping from the App settings page and see it in Recent deliveries.

## Layout and look

- One narrow header: wordmark, four nav links, theme toggle. No sticky glass, no gradients, no glow.
- Content max width around 1100px, generous vertical rhythm, one h1 per page.
- Light and dark via next-themes with class strategy; system preference by default; toggle persisted in localStorage (the only browser storage used).
- shadcn/ui components: Button, Card, Table, Badge, Select, Tabs (detail page), Alert, Skeleton, Separator, Tooltip, Toggle group (feedback), Sheet not needed.
- Typography: system font stack. Code in the platform monospace.
- Colour: shadcn neutral palette. Severity badges use text plus colour, never colour alone (critical, high, medium, low, info are spelled out).
- Motion: none beyond focus transitions; prefers-reduced-motion respected.

## Accessibility commitments

- Every interactive element is a real button or link with a visible focus ring.
- Every icon-only control has an accessible name.
- Tables have caption and header scope; the reviews table is navigable by keyboard.
- Colour contrast meets AA in both themes (checked with the browser tooling before calling it done).
- Skip link to main content. aria-current on the active nav item. Live region for the queue status chip.

## Data flow

Next.js route handlers under /app/api/* are deleted. Pages are server components that call the backend with LOCAL_API_TOKEN from the server environment (BACKEND_URL and LOCAL_API_TOKEN in .env.local, never NEXT_PUBLIC). The feedback button and the status refresh use small server actions. No client-side fetch to the backend at all, so the token never leaves the server.

## Removed

app/api/**, app/demo, app/pull-requests, app/review, app/history (replaced), components/review/*, components/layout/Header and Footer, components/charts, contexts/AuthContext, hooks/*, lib/utils calculateComplexity, scripts/generate-*.js, vercel.json, the Google Fonts import, the matrix theme.
Packages dropped: @monaco-editor/react, recharts, react-dropzone, next-auth, @auth/prisma-adapter, @langchain/*, langchain, @octokit/*, axios, zustand, react-hook-form, @hookform/resolvers, react-hot-toast, date-fns, zod (unless a form needs it), puppeteer, sharp, @tailwindcss/forms, @tailwindcss/typography (a small prose style is written by hand).
Packages added: next 15.5 line, react 19, next-themes, tailwindcss 4 with @tailwindcss/postcss, shadcn (CLI, dev), the radix packages shadcn installs, lucide-react (kept).

## Verification

npm run lint, typecheck and build clean; a keyboard-only walk through all four screens; both themes checked for contrast; the browser network panel shows requests only to localhost:3000 (the backend is reached server-side).

## What was built (2026-09-03)

All four screens as described, verified in a browser against a seeded local backend and against a dead backend (every page renders an operator-facing alert rather than a 500). Lighthouse on the reviews and status pages: accessibility 100, best practices 100. The production build's HTML references no external host, font or script.

Differences from the draft:
- The reviews table shows the per-severity breakdown under the findings count; the backend list endpoint now returns `severity_counts` for that.
- No severity filter chips on the detail page; findings are grouped by file, sorted by severity then line, with a tally above.
- `/reviews/<unknown id>` renders the not-found page with HTTP 200, because the route streams behind a loading skeleton. Cosmetic.
- Versions: next 15.5, react 19, tailwindcss 4 with `@tailwindcss/postcss`, the unified `radix-ui` package the shadcn CLI now installs, eslint 9 with a flat config, `shadcn` as a runtime dependency because `app/globals.css` imports its Tailwind layer.
- The Nova preset the shadcn CLI applied tried to add a Google font import; it was removed and `--font-sans`/`--font-mono` are system stacks.
- The dashboard client (`lib/api.ts`) is marked `server-only`, so importing it from a client component is a build error rather than a token leak.
- The theme toggle offers Light, Dark and System; the preference is the only thing kept in browser storage.
