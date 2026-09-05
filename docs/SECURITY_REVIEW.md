# ReviewBot Protocol security review

Date: 2026-09-03. Branch: v1.1-Local-AI at commit 8ee88ea. Reviewer: Claude (Fable 5.1 orchestrating), commissioned by Tom Butler.

This document is the record of the Phase 0 investigation. It is severity-ranked, it names what an attacker actually achieves, and it says how hard each attack is. It also lists what was checked and found fine, so the reader knows what was looked at. Findings are numbered SR-01 onwards. The Status column is updated as fixes land; until then every item is Open.

## How this review was done

Every backend file and every Next.js API route was read in full. Seven independent read-only investigators each took one lens (webhook authentication, the model pipeline, endpoint authorisation, data and logging, denial of service, dependencies and git history, and "what everyone else will miss"). Their findings were merged, then every merged finding was attacked by two or three adversarial verifiers whose instruction was to refute it with repository evidence; critical and high findings needed three verifiers to survive. A completeness critic then named six gaps, each of which was investigated and verified the same way. Upstream library behaviour was checked against the pinned versions on GitHub and PyPI, not from memory. Nothing was installed or executed against the project during the review, so runtime claims are derived from source and are marked as such where it matters.

Tally: 86 raw findings, 61 after merge, 58 confirmed, 3 refuted, 41 more confirmed from the gap round, 118 checked-fine items. After removing overlaps between the main and gap rounds, 91 findings are listed below.

## Threat model

ReviewBot accepts arbitrary input from anyone on the internet (a webhook, and today several unauthenticated API routes), feeds that input to a language model, and then acts on the result with a credential that can write to GitHub repositories. Each step is dangerous and they compound: a forged or replayed webhook triggers work and spend; a crafted diff can steer the model; the model output is posted under the App identity and can set commit statuses that branch protection may trust; anything the diff contains, including secrets committed by accident, travels through logs, prompts, storage and comments.

The intended end state is a tool that runs entirely on the owner's machine, where the only network peer is api.github.com, and where every one of those steps has a guard: signature verification and replay rejection at the door, size and concurrency limits, redaction before the model, a data-only prompt frame, schema-constrained output, sanitised and bounded comments, no status decisions from model output, and logs that never contain code.

## Summary

Status at 2026-09-03 after the backend rewrite, the frontend rebuild and the docs pass: 89 fixed, 1 mitigated, 1 informational.

| Severity | Count |
| -------- | ----- |
| critical | 1     |
| high     | 21    |
| medium   | 34    |
| low      | 24    |
| info     | 11    |

The four findings that matter most are not classic vulnerabilities but total failures of the product path, in execution order: the GitHub client cannot mint a token (SR-08), the LangGraph result shape crashes its consumers (SR-04), the prompts never contain the code (SR-03), and the status logic is inverted (SR-14, SR-09). Each masks the next, which is why the two highest-impact security findings (inline execution in the webhook request, and unauthenticated paid endpoints) were downgraded from critical to high by the verifiers: today they cannot fully fire. They become critical the moment the pipeline is repaired, so they are fixed in the same change.

## Critical findings

### SR-01: backend/requirements.txt is unresolvable on every Python version: langchain-community==0.3.27 contradicts the pinned langchain==0.3.13 and langchain-core==0.3.28

- Severity: critical
- Where: backend/requirements.txt:24
- Difficulty for an attacker: trivial
- Category: dependency-resolution / build-blocker
- Status: Fixed 2026-09-03. backend/requirements.txt now pins langchain 0.3.27, langchain-core 0.3.86 and langsmith 0.3.45, the set that resolves with langchain-community 0.3.27; verified with pip install --dry-run on Python 3.13. The full move to the LangChain 1.x line happens in Phase 4.

What it is.

Three exact pins in the same file contradict each other. backend/requirements.txt:21 pins langchain==0.3.13, :23 pins langchain-core==0.3.28, :24 pins langchain-community==0.3.27. The published metadata for langchain-community 0.3.27 declares requires_dist entries 'langchain<1.0.0,>=0.3.26' and 'langchain-core<1.0.0,>=0.3.66'. Under PEP 440, 0.3.13 < 0.3.26 and 0.3.28 < 0.3.66, so both pins violate it. pip's resolver has no candidate set and terminates with ResolutionImpossible. This is not host-specific: it fails on 3.11, 3.12, 3.13 and 3.14 alike, and it fails before any wheel is downloaded. langchain-community cannot simply be deleted from the file either, because it is needed at runtime: backend/services/ai_reviewer.py:19 does 'from langchain.callbacks import get_openai_callback', and in langchain 0.3.13 that name is only a lazy re-export of langchain_community.callbacks.manager.get_openai_callback (see the create_importer / TYPE_CHECKING block in libs/langchain/langchain/callbacks/**init**.py at tag langchain==0.3.13), and it is actually called at ai_reviewer.py:1085 and :1260.

What an attacker achieves.

Murphy achieves total unavailability of the backend. The first documented setup command (backend/README.md:65, scripts/quick-setup.sh:115) aborts with a resolver error, so nobody, including the owner, can install or run the FastAPI service, run the webhook end to end, or perform the egress capture. It has been broken in the default branch since 8 Nov 2025 and no CI exists to surface it.

Evidence.

backend/requirements.txt:21 'langchain==0.3.13'; :23 'langchain-core==0.3.28'; :24 'langchain-community==0.3.27'. PyPI JSON https://pypi.org/pypi/langchain-community/0.3.27/json info.requires_dist contains verbatim 'langchain-core<1.0.0,>=0.3.66' and 'langchain<1.0.0,>=0.3.26' (confirmed on two separate fetches). backend/services/ai_reviewer.py:19 'from langchain.callbacks import get_openai_callback'; :1085 and :1260 'with get_openai_callback() as cb:'.

Fix.

Move forwards, not backwards. Set backend/requirements.txt:21 to 'langchain>=0.3.26,<0.4.0' and :23 to 'langchain-core>=0.3.66,<0.4.0' (or pick concrete 0.3.x releases that satisfy those bounds) so langchain-community==0.3.27 resolves. Do not revert langchain-community to 0.3.13: OSV reports GHSA-pc6w-59fv-rh23 / PYSEC-2026-1515 (XXE) against that version. Bumping langchain-core past 0.3.28 also clears six GHSAs currently open against 0.3.28 (GHSA-2g6r-c272-w58r, GHSA-6qv9-48xg-fc7f, GHSA-926x-3r5x-gfhw, GHSA-c67j-w6g6-q2cm, GHSA-pjwx-r37v-7724, GHSA-qh6h-p6c9-ff54). Verify the change with 'pip install --dry-run -r backend/requirements.txt' in a throwaway venv, and add a minimal GitHub Actions job that does exactly that so the next dependabot PR cannot merge broken.

Verification: 1 adversarial verifier, 0 refuted.

## High findings

### SR-02: Queue never started: every webhook review runs inline inside the HTTP request (re-run up to 4 times on failure, unbounded concurrency), every delivery exceeds GitHub's 10 s limit, and the 'pending' status is posted after the final status so commits stay pending forever

- Severity: high (reported as critical, adjusted by verification)
- Where: backend/services/queue_processor.py:149
- Difficulty for an attacker: trivial
- Category: dos-limits
- Status: Fixed in the backend rewrite (2026-09-03): single-worker queue in services/review_queue.py, the webhook returns 202 (tests: test_webhook, test_queue).

What it is.

QueueProcessor.connect() and start_workers() are never called anywhere (grep: only get_queue_stats() and is_running at backend/handlers/review.py:883-886); main.py lifespan (backend/main.py:40-54) only calls init_db/close_db. redis_client therefore stays None (queue_processor.py:106) and add_task takes the fallback (:149-152) to _process_task_immediate (:465-468) to _process_task (:274-341), which runs the GitHub fetches, all LLM calls and comment POSTs while github_webhook is still awaiting add_review_to_queue (backend/handlers/webhook.py:244-249). BackgroundTasks is accepted at webhook.py:79 but background_tasks.add_task is never called. On any exception _process_task sleeps 2**retry_count (2, 4, 8 s) and calls add_task again (:317-327), recursing into immediate processing, so a failing review runs 4 times end to end (max_retries=3, :64) with 14 s of sleeps inside one request. The processing_semaphore (:110) is only acquired in _worker_loop (:228), which never runs.

What an attacker achieves.

Any collaborator on an installed repo (every push) ties up the single uvicorn process for the full review duration, times 4 on failure, with no worker, concurrency bound or wall-clock cap. Every real delivery shows as failed in GitHub, inviting Redeliver clicks that start a second concurrent full review with duplicate comments and double OpenAI cost. If the context is a required check no PR can merge; otherwise every commit carries a permanent yellow dot hiding the real result.

Evidence.

backend/services/queue_processor.py:64, :106, :110, :149-152, :228, :274-341, :306-330, :317-327, :431-440, :465-468; backend/handlers/webhook.py:79, :244-249, :251-267, :260-265, :387-403, :412-419; backend/main.py:40-54; grep -rn 'connect()|start_workers|background_tasks.add_task|is_disconnected' backend to no call sites; app/api/webhook/github/route.ts:26-33 no signal; vercel.json:88-91 maxDuration 60; backend/config/settings.py:61, :74; GitHub docs: deliveries over 10 s are recorded as failures and not auto-redelivered.

Fix.

Post the pending status first, persist the delivery, enqueue and return 202 within milliseconds; call queue_processor.connect()/start_workers() from the lifespan (and stop/disconnect on shutdown) and fail loudly if Redis is unavailable, or replace Redis with an in-process asyncio.Queue plus a single worker, or at minimum use background_tasks.add_task. Remove the recursive add_task retry from _process_task and never retry deterministic errors; wrap each review in asyncio.wait_for(settings.MAX_REVIEW_TIME); make _process_task return a bool that add_task surfaces and only append 'posted_status_check' when it succeeded; add an AbortSignal.timeout to the proxy fetch; ignore duplicate delivery ids.

Verification: 3 adversarial verifiers, 1 refuted.

### SR-03: Every prompt is a literal message list, so {filename}/{language}/{code_diff} are never substituted and the model never sees the diff: all reviews are blind

- Severity: high (reported as critical, adjusted by verification)
- Where: backend/services/ai_reviewer.py:292
- Difficulty for an attacker: trivial
- Category: llm-pipeline
- Status: Fixed in the backend rewrite (2026-09-03): prompts are real templates; test_review_generation asserts the diff, file name and language are in the human message.

What it is.

All ten prompts in _setup_prompts are ChatPromptTemplate.from_messages([SystemMessage(content=...), HumanMessage(content=...)]) (ai_reviewer.py:292-349 security, 352-426 performance, 429-516 quality, 519-549 line_by_line, 552-588 refactoring, 591-620 assessment, 623-676 documentation, 679-727 testing, 730-782 architecture, 785-846 enhanced_scoring). In langchain-core 0.3.28 (pinned, requirements.txt:23) a BaseMessage instance is kept verbatim (prompts/chat.py:1464-1465), input_variables is collected only from template types (chat.py:1012-1022, 1081-1083) and format_messages passes instances through (chat.py:1222-1224). LLMChain selects only declared variables (langchain 0.3.13 chains/llm.py:108, 222-223) and _validate_inputs checks only missing keys (chains/base.py:288-290), so arun(**chain_input) at ai_reviewer.py:1166, 1175, 1184, 1193, 1202, 1211, 1262 succeeds silently and the model receives the literal text 'File: {filename}\nLanguage: {language}\nCode to analyze:\n{code_diff}' (ai_reviewer.py:337-340). chain_input built at :1078-1082 is never interpolated.

What an attacker achieves.

No attacker needed. Every finding, score and commit status ever produced is hallucinated from a prompt containing no code: the model returns [] or prose (parsed to [] at :1237-1240), every file scores clean, pr_score stays 100 (review_workflow.py:796-821) and the status reads 'Review passed' (review_workflow.py:573-574), while full gpt-4o cost (4 to 6 calls per file) is still incurred.

Evidence.

backend/services/ai_reviewer.py:15-16 imports (re-exports of langchain_core), :292-349, :337-348, :1078-1082, :1166-1262; upstream langchain-core 0.3.28 libs/core/langchain_core/prompts/chat.py:1012-1022, 1081-1083, 1222-1224, 1464-1465; langchain 0.3.13 chains/llm.py:108, 222-223, chains/base.py:288-290, 686-691, prompts/**init**.py:38-43, schema/**init**.py:9-15. No local runtime repro possible (no Python with langchain installed).

Fix.

Build message templates, not messages: ChatPromptTemplate.from_messages([('system', text), ('human', text)]) or SystemMessagePromptTemplate/HumanMessagePromptTemplate.from_template; escape every literal brace as {{ }} in all prompts (security, performance and quality currently use single braces); add a startup assertion and unit test that sorted(prompt.input_variables) == ['code_diff', 'filename', 'language'] and that the diff appears in the rendered human message; replace deprecated LLMChain.arun with prompt | llm runnables so missing variables raise.

Reproduced 2026-09-03 (backend/tests/test_review_generation.py, RecordingChatModel). The human message the security chain sends, verbatim, begins "File: {filename}\nLanguage: {language}\nCode to analyze:\n{code_diff}" and the prompt's input_variables list is empty. The diff sentinel was not present. The test is a strict expected failure until Phase 4 step 3.

Verification: 3 adversarial verifiers, 0 refuted.

### SR-04: LangGraph result shape is incompatible with every consumer: files_reviewed is a list of filenames, consumers index it as dicts, so each review crashes after the full LLM spend and the webhook path re-runs it four times, ending FAILED with the status stuck on pending

- Severity: high (reported as critical, adjusted by verification)
- Where: backend/services/queue_processor.py:378
- Difficulty for an attacker: trivial
- Category: llm-pipeline
- Status: Fixed in the backend rewrite (2026-09-03): results are FileReviewResult objects consumed by the renderer and runner (tests: test_workflow, test_runner).

What it is.

review_workflow.py:210 fills files_to_review with filenames, :469 appends the current filename string to files_reviewed, and _format_review_results returns it unchanged at :946; AIReviewer defaults to use_langgraph=True and returns workflow_results directly (ai_reviewer.py:199, :953). queue_processor._process_pr_review_task does 'for file_result in review_results["files_reviewed"]: filename = file_result["filename"]' (:377-378), raising TypeError on the first entry; _process_task (:306-330) retries three times with 2, 4, 8 s sleeps and re-runs the whole review via add_task to _process_task_immediate (:318-327, :149-151, :465-468), then marks FAILED (:329-330); create_status_check at :434 is never reached and webhook.py:387-403 leaves 'pending'.

What an attacker achieves.

No inline comment, PR summary or final status check has ever been produced by the LangGraph path; every PR event burns 4x OpenAI and GitHub API calls (a 2-file PR is roughly 48 gpt-4o calls, about $0.85, for zero output) and leaves the status permanently pending; anyone submitting a PR to an installed repo or hitting /review/code with a real filename triggers this, and the UI shows a misleading 'AI backend unavailable' fallback.

Evidence.

backend/services/review_workflow.py:210, :469, :946, :957, :540-563, :601, :628-642, :844-867; backend/services/ai_reviewer.py:199, :953, :955-957; backend/services/queue_processor.py:149-151, :306-330, :318-327, :377-378, :431, :434, :465-468; backend/handlers/review.py:762, :820-821, :862-876, :978, :1014; backend/handlers/webhook.py:387-403; backend/main.py:40-54; app/api/review/route.ts:26, :47-51, :185-224; git log -S'"files_reviewed": state["files_reviewed"]' to cd3749e.

Fix.

Make _format_review_results emit per-file dicts from state['file_analyses'] (filename, language, security_issues, performance_issues, quality_issues, documentation_issues, testing_issues, architecture_issues, ai_metrics) so all consumers work, or have queue_processor consume review_results['github_comments'] via GitHubClient.post_pr_review and use status_check.result; never retry deterministic TypeError/AttributeError/KeyError and never re-run the LLM stage on retry (persist the result first); add a test running _process_pr_review_task and review_pr_files against a stubbed LLM asserting a comment and status check are produced.

Verification: 3 adversarial verifiers, 0 refuted.

### SR-05: Unauthenticated POST /review/code and POST /review/manual drive the paid gpt-4o pipeline with no auth, no file-count, size or rate cap, and per-request instantiation: arbitrary spend, event-loop saturation and DB fill by anyone

- Severity: high (reported as critical, adjusted by verification)
- Where: backend/handlers/review.py:719
- Difficulty for an attacker: trivial
- Category: dos-limits
- Status: Fixed in the backend rewrite (2026-09-03): those endpoints no longer exist; the dashboard API is token-gated (test_api).

What it is.

review_code_direct takes 'request: Dict[str, Any]' with only a db_session dependency (backend/handlers/review.py:719-723), loops over every entry in request['files'] (:734, :768-787) with no count cap, constructs a new AIReviewer (:762, building a ChatOpenAI client and compiling a LangGraph per request, ai_reviewer.py:207-236) and awaits review_pr_files (:791). create_manual_review (:30-35) has no auth, ManualReviewRequest.code is an unbounded str (backend/models/review.py:177-182), and process_manual_review is pushed to BackgroundTasks (:60-66, :965-1055) so 200 returns before any cost is incurred; with the default 'code.txt' the LangGraph path skips it (review_workflow.py:631), throws IndexError at :601 and the basic path reviews it as 'text' (helpers.py:87) with 6 calls; with a .py name it runs 6 calls then dies at review.py:1014.

What an attacker achieves.

Any internet user (port 8000 or the CORS-open Vercel /api/review proxy, vercel.json:14-35) burns the operator's OpenAI budget at a rate bounded only by OpenAI's limits: 1 to 2 files of 100 KB give 12 calls of about 25k input tokens each; 1,000 small .py files trip the recursion limit, fall back and cost roughly 6,000 gpt-4o calls (tens to hundreds of dollars) from one 10 MB request; /review/manual lets a script queue thousands of 6-call jobs per second without waiting.

Evidence.

backend/handlers/review.py:30-35, :60-66, :719-723, :734, :759, :762, :768-787, :781, :791, :816-849, :965-1055, :978, :1014; backend/models/review.py:177-182; backend/models/github.py:126-132; backend/services/ai_reviewer.py:207-236, :1088-1129, :1166-1211, :1262, :1399-1402; backend/services/review_workflow.py:174-181, :282-443, :370, :430, :601, :631, :639; backend/config/settings.py:35-37, :57-74; backend/handlers/auth.py:374-388 '# For now, always return True (no rate limiting)'; backend/main.py:322-331; app/api/review/route.ts:16-37, :226-253; vercel.json:14-35; grep for MAX_FILES_PER_PR|MAX_FILE_SIZE|MAX_REVIEW_TIME|REVIEW_RATE_LIMIT to settings.py only.

Fix.

Require a real session (backend JWT or the frontend cookie validated server-side) on every /review/* mutation and on /api/review; replace Dict[str, Any] with a Pydantic model using conlist(max_length=MAX_FILES_PER_PR) and constr(max_length=...) on content/code; reject bodies over a few hundred KB via Content-Length middleware or a reverse proxy; compute changes server-side from the patch; enforce per-user/IP rate and token budgets and REVIEW_RATE_LIMIT; reuse one AIReviewer; wrap review_pr_files in asyncio.wait_for(MAX_REVIEW_TIME); route manual work through the queue with a concurrency cap; lower OPENAI_MAX_TOKENS for JSON prompts; remove /api/review if unused.

Verification: 3 adversarial verifiers, 0 refuted.

### SR-06: Review results including model-quoted code snippets and error strings are persisted to SQLite and can be read, enumerated or deleted without authentication

- Severity: high (reported as medium, adjusted by verification)
- Where: backend/handlers/review.py:195
- Difficulty for an attacker: easy
- Category: authz-endpoints
- Status: Fixed in the backend rewrite (2026-09-03): every /api route requires LOCAL_API_TOKEN; there is no delete route (test_api).

What it is.

GET /review/{review_id} (backend/handlers/review.py:195-264) returns every issue with code_snippet, suggestion and file_path (:221-235) and 'Review failed: {error_message}' (:242) to anyone; DELETE /review/{review_id} (:697-716) deletes any review; GET /review/stats/overview, /review/stats/user, /review/metrics/user/{id}, /review/metrics/repository, /review/metrics/trending and /review/compare/{a}/{b} (:340, :496, :895, :912, :929, :593) are open; GET /review/ (:267-337) and /review/history (:388-493, returning code_suggestions and priority_fixes at :467-468) enumerate every id. No route in review.py has an auth dependency. /review/code writes model output into review_issues.message, suggestion, code_snippet and reviews.metrics.code_suggestions with current_code/suggested_code (review.py:807-846; ai_reviewer.py:830-839; database/models.py:78, 88, 103, 130, 138, 139) and str(e) into error_message (:868-872, :1062-1066).

What an attacker achieves.

Anyone reaching the backend port (0.0.0.0 default, settings.py:21) can read model findings, suggestions and code snippets derived from other users' submissions plus raw error strings, delete arbitrary reviews, and learn which repositories the operator reviews; bulk dump is blocked only by bugs, not design.

Evidence.

backend/handlers/review.py:43, :94, :142, :195-199, :221-235, :231, :242, :267-337, :340, :388-493, :467-468, :496, :593, :697-701, :743, :807-813, :835-846, :852, :868-872, :895, :912, :929, :1062-1066; backend/database/models.py:35, :78, :88, :103, :130, :138-139; backend/services/ai_reviewer.py:830-839; backend/config/settings.py:21, :48; .gitignore:112-114; backend/services/queue_processor.py:343-457.

Fix.

Add an auth dependency and ownership check (created_by == current user) to every /review route and scope listings; store only what the UI needs (drop or truncate code_snippet and current_code) and a generic error category instead of str(e); return 404 for malformed ids; set an explicit DATABASE_URL outside the repo.

Verification: 2 adversarial verifiers, 0 refuted.

### SR-07: No cross-request concurrency control: N webhooks or API calls mean N interleaved reviews on one event loop, with a blocking PyGithub call per review and no cost telemetry

- Severity: high (reported as medium, adjusted by verification)
- Where: backend/services/ai_reviewer.py:979
- Difficulty for an attacker: easy
- Category: dos-limits
- Status: Fixed in the backend rewrite (2026-09-03): one review at a time, by construction of the queue.

What it is.

The only semaphore in the review path is asyncio.Semaphore(3) created per call in review_pr_files (:979), basic-chain branch only; the LangGraph branch is unlimited across requests; processing_semaphore (queue_processor.py:110) is acquired only in _worker_loop (:228); uvicorn runs without --limit-concurrency (main.py:322-331) and WORKERS=1 (settings.py:23). Each review creates a fresh GitHubClient (queue_processor.py:353; webhook.py:395) and _get_access_token calls synchronous PyGithub installation.get_access_token() inside an async function (github_client.py:91-92), blocking the loop; with the retry loop that is five token mints per failed webhook. get_openai_callback cost tracking is wired only to the basic path and LangGraph results carry no ai_metrics, so ai_tokens_used/ai_cost are 0 (review.py:805-806).

What an attacker achieves.

Ten simultaneous webhooks or curl calls produce ten interleaved reviews with no queueing, backpressure or budget, OpenAI 429s add client retries, and the operator has no cost telemetry.

Evidence.

backend/services/ai_reviewer.py:979; backend/services/queue_processor.py:110, :228, :353; backend/services/github_client.py:91-92; backend/main.py:323-331; backend/config/settings.py:23; backend/handlers/webhook.py:395; backend/handlers/review.py:805-806.

Fix.

One global semaphore or the queue worker count around every review entry point; run PyGithub via asyncio.to_thread; cache installation tokens per installation_id; carry token/cost metrics out of the LangGraph path and log them per review.

Verification: 2 adversarial verifiers, 0 refuted.

### SR-08: GitHub App client can never mint an installation token: wrong PyGithub API, so nothing is ever read from or posted to GitHub while the webhook still reports success

- Severity: high
- Where: backend/services/github_client.py:91
- Difficulty for an attacker: trivial
- Category: gaps-critic-prep
- Status: Fixed in the backend rewrite (2026-09-03): services/github_app_auth.py mints installation tokens with an RS256 App JWT over httpx (test_github_client).

What it is.

_get_access_token calls self._github_integration.get_installation(self.installation_id) then installation.get_access_token() (backend/services/github_client.py:91-95). In pinned PyGithub 1.59.1 (requirements.txt:14) GithubIntegration.get_installation is deprecated and takes (owner, repo) (upstream GithubIntegration.py:197-207) and Installation has no get_access_token (it lives on GithubIntegration), so the call raises TypeError every time, also on 2.x. Every GitHubClient method goes through _get_access_token (:115, :124), so get_pr_info, get_pr_files, post_review_comment and create_status_check all fail; _process_pr_review_task fails at queue_processor.py:357, is retried with 2+4+8 s inline sleeps (:318-327), post_initial_status_check returns False (webhook.py:412-419) yet 'posted_status_check' is appended (:265) and 200 'review queued' is returned.

What an attacker achieves.

Nothing for an attacker; the core feature has never worked while responses and logs claim success, and it masks the LangGraph shape, status-scale and fork-PR findings that surface once fixed.

Evidence.

backend/services/github_client.py:91-95, :115, :124; upstream PyGithub v1.59.1 'def get_installation(self, owner, repo)' @deprecated and 'def get_access_token(self, installation_id, permissions=None)' on GithubIntegration; backend/services/queue_processor.py:318-327, :357; backend/handlers/webhook.py:260-265, :412-419.

Fix.

auth = self._github_integration.get_access_token(self.installation_id); store auth.token and auth.expires_at; only append 'posted_status_check' when the call returns True; add an integration test against a recorded fixture.

Verification: 3 adversarial verifiers, 0 refuted.

### SR-09: Model-derived commit status uses the wrong scale (0-100 compared against 7.0) and ignores the workflow's own verdict, so almost every PR gets 'success'

- Severity: high (reported as medium, adjusted by verification)
- Where: backend/services/queue_processor.py:431
- Difficulty for an attacker: trivial
- Category: gaps-critic-prep
- Status: Fixed in the backend rewrite (2026-09-03): commit statuses removed entirely, with the permission.

What it is.

queue_processor.py:431-432 sets 'success' when overall_score >= 7.0 and prints '{score:.1f}/10'; the LangGraph path returns pr_score on 0-100 (review_workflow.py:796-821, :957) while the basic path returns 0-10 (ai_reviewer.py:1323), and review.py:240 also prints '/10'. A PR with six critical findings (score 10.0) still passes with a description like 'AI Review: 93.0/10'. The workflow's status_check_result (failure/neutral/success, review_workflow.py:565-574) is discarded.

What an attacker achieves.

A contributor can rely on a green git-review-assistant/review status regardless of content; a required check becomes a rubber stamp (and, with the templating bug, bears no relation to the code at all).

Evidence.

backend/services/queue_processor.py:431-432; backend/services/review_workflow.py:565-574, :796-821, :957; backend/services/ai_reviewer.py:1323; backend/handlers/review.py:240.

Fix.

Use review_results['status_check']['result'] and ['message'] when present; normalise scores to one scale in one place; document that the context must not be a required check until the pipeline is proven.

Verification: 2 adversarial verifiers, 0 refuted.

### SR-10: OPENAI_API_KEY is a required setting with no default, so the process cannot boot for a fully-local deployment, and no base_url exists at either ChatOpenAI construction site

- Severity: high
- Where: backend/config/settings.py:34
- Difficulty for an attacker: trivial
- Category: local-inference-migration/requirements-gap
- Status: Fixed in the backend rewrite (2026-09-03): no cloud settings exist; STRICT_LOCAL refuses to boot if a cloud key is present (test_settings).

What it is.

The branch is v1.1-Local-AI and the stated goal is fully local, but there is zero implementation and the current shape actively blocks it. settings.py:34 declares `OPENAI_API_KEY: str` with no default, and settings.py:151 instantiates `settings = Settings()` at import time, so a missing key raises pydantic ValidationError before FastAPI ever starts, even if no OpenAI call is ever made. Both ChatOpenAI construction sites (ai_reviewer.py:207-213 in AIReviewer.**init**, and ai_reviewer.py:1417-1422 in get_ai_health) pass model_name/temperature/max_tokens/openai_api_key and no base_url or openai_api_base. requirements.txt has no ollama or langchain-ollama package, backend/.env.example:22-25 has no OPENAI_BASE_URL, and a repo-wide grep for ollama, base_url, 11434, api_base across backend/ returns only DATABASE_URL matches.

What an attacker achieves.

No attacker. The owner's headline requirement has no code path, no config surface, no dependency and no assessment, so the migration has never been costed and the boot-time hard dependency on a cloud key is unnoticed.

Evidence.

backend/config/settings.py:34 `    OPENAI_API_KEY: str` (no default), :151 `settings = Settings()`. backend/services/ai_reviewer.py:207-213 `self.llm = ChatOpenAI(model_name=..., temperature=..., max_tokens=..., openai_api_key=settings.OPENAI_API_KEY, streaming=False)`. backend/services/ai_reviewer.py:1417-1422 same shape with max_tokens=10. backend/requirements.txt:22 `langchain-openai==0.2.14`, no ollama package anywhere in the file. `grep -rniE 'ollama|base_url|11434|openai_api_base|api_base' backend/` to only DATABASE_URL lines. langchain 0.2.14 base.py: `openai_api_base: Optional[str] = Field(default=..., alias="base_url")` and client_params includes `"base_url": self.openai_api_base`.

Fix.

Add `OPENAI_BASE_URL: Optional[str] = None` to settings.py, give OPENAI_API_KEY a default of 'ollama' (or make it Optional and pass 'ollama' when a base_url is set) so the app boots without a cloud key, and pass `base_url=settings.OPENAI_BASE_URL` at BOTH ai_reviewer.py:207 and ai_reviewer.py:1417. Set OPENAI_BASE_URL=http://localhost:11434/v1 and OPENAI_MODEL=qwen3.5:9b in .env.example alongside the existing gpt-4o line. Do not add langchain-ollama: the OpenAI-compat shim is the smaller change and keeps LLMChain/LangGraph untouched.

Verification: 1 adversarial verifier, 0 refuted.

### SR-11: Six strictly sequential LLM calls per file run inline inside the webhook request with no deadline; the Semaphore(3) everyone points at is dead code on the live path

- Severity: high
- Where: backend/services/review_workflow.py:150
- Difficulty for an attacker: trivial
- Category: local-inference-migration/throughput
- Status: Fixed in the backend rewrite (2026-09-03): one structured call per file, run by the worker under REVIEW_TIMEOUT_SECONDS.

What it is.

The throughput question has been mis-scoped. `asyncio.Semaphore(3)` at ai_reviewer.py:979 is in the basic-chains fallback, which review_pr_files (ai_reviewer.py:929-953) returns before reaching whenever LangGraph succeeds. The live path is the LangGraph state machine, whose edges (review_workflow.py:150-181) chain security to performance to quality to documentation to testing to architecture to synthesize, then loop back to security for the next file. That is 6 strictly serial LLM calls per reviewable file with zero concurrency, and _generate_ai_summary (review_workflow.py:748-769) is a hardcoded template not an LLM call, so there is no 7th. The whole thing runs inside the HTTP request: main.py:41-54 lifespan never calls queue_processor.connect() or start_workers(), so redis_client stays None, queue_processor.py:149-151 falls through to `await self._process_task_immediate(task)`, and webhook.py:244 awaits add_review_to_queue.

What an attacker achieves.

Every review times out. GitHub's webhook delivery deadline is 10 seconds. Order-of-magnitude sizing for the local model, stated as an estimate that needs a measured benchmark: an M1 Max has ~400 GB/s memory bandwidth and the model is 6.6 GB of Q4_K_M weights, so memory-bound decode tops out around 60 tok/s and realistically lands near 30-45 tok/s. With max_tokens=4000 and thinking enabled, each chain call plausibly emits 800-4000 tokens, i.e. roughly 20-130 s per call, so 2-13 minutes per file and 10-65 minutes for a 5-file PR.

Evidence.

backend/services/review_workflow.py:150-181 sequential add_edge chain performancetoqualitytodocumentationtotestingtoarchitecturetosynthesize_file_results, and :171-179 conditional edge 'next_file' to 'security_analysis'. backend/services/review_workflow.py:748-769 `_generate_ai_summary` returns an f-string, no chain call. backend/services/ai_reviewer.py:979 `semaphore = asyncio.Semaphore(3)` sits after the `return workflow_results` at :953. backend/main.py:41-54 lifespan body is init_db / yield / close_db only. backend/services/queue_processor.py:149-151 `if not self.redis_client: await self._process_task_immediate(task); return True`.

Fix.

The answer to 'must the semaphore drop to 1' is that it is already effectively 1 and is not the lever. The required change is to stop running inference inside the webhook: have the handler verify, enqueue and return 202 within a second, and do the review in a worker. Either wire the existing queue (call queue_processor.connect() and start_workers() in main.py's lifespan) or, as a smaller step, hand the task to FastAPI's BackgroundTasks, which is already imported at webhook.py:3 and passed into every handler but never used.

Verification: 1 adversarial verifier, 0 refuted.

### SR-12: Monkeypatching httpx or the openai client proves only that the patched client stayed quiet: five independent HTTP stacks live in one process, one of them a background thread

- Severity: high
- Where: backend/services/github_client.py:9
- Difficulty for an attacker: easy
- Category: test-design
- Status: Fixed in the backend rewrite (2026-09-03): the proof is a socket-level guard below every HTTP stack (test_runner wraps whole reviews in it with respx answering GitHub in-process; test_no_egress wraps a real-model review in it, opt-in) plus docker run --network none (scripts/prove-local.sh).

What it is.

The backend process loads at least five mutually independent HTTP client stacks, so any in-process patch covers a subset. Verified: (a) httpx.AsyncClient used directly (github_client.py:7 `import httpx`, :134, :590); (b) requests.Session inside PyGithub, confirmed from upstream v1.59.1 source where github/Requester.py does `import requests` / `import requests.adapters` and `class HTTPSRequestsConnectionClass: self.session = requests.Session()` (pinned at backend/requirements.txt:14 PyGithub==1.59.1); (c) the openai SDK's own internal httpx.Client instance, constructed inside ChatOpenAI and not the same object a test would patch (requirements.txt:26 openai==1.58.1); (d) sentry-sdk's urllib3 transport, which runs on a BACKGROUND WORKER THREAD and flushes on its own timer, so an assertion made at the end of a test body can pass while the flush happens afterwards (requirements.txt:50, main.py:29); (e) langsmith's requests session, confirmed from upstream v0.2.7 python/langsmith/client.py which does `import requests` / `from requests import adapters as requests_adapters` and defaults to h [...]

What an attacker achieves.

A green test that certifies nothing. The reviewer patches httpx.AsyncClient.request, sees zero calls, and declares the system local, while PyGithub ships the PR diff to api.github.com through requests and Sentry ships exception context out of a thread the assertion never observed.

Evidence.

backend/services/github_client.py:7 `import httpx` and :9 `from github import Github, GithubIntegration`; upstream PyGithub v1.59.1 github/Requester.py: `import requests`, `import requests.adapters`, `class HTTPSRequestsConnectionClass ... self.session = requests.Session()`; upstream langsmith v0.2.7 python/langsmith/client.py: `import requests`, default endpoint `https://api.smith.langchain.com`; backend/requirements.txt:9 httpx==0.25.2, :10 requests==2.32.4, :14 PyGithub==1.59.1, :26 openai==1.58.1, :30 langsmith==0.2.7, :50 sentry-sdk[fastapi]==1.38.0; backend/main.py:29 `sentry_sdk.init(`.

Fix.

Do not assert at the library layer. Assert below every stack, at the socket layer, and state the blind spot explicitly in the test docstring. Cheapest honest in-process guard: a conftest autouse fixture that wraps `socket.socket.connect`/`connect_ex` and `socket.getaddrinfo`, allowing only loopback and raising on anything else. That catches all five stacks because they all bottom out in the socket module, but it still does NOT catch a subprocess, a C extension using its own resolver, or anything after the interpreter exits. Pair it with an out-of-process capture (below) for the real proof, and never present the socket fixture alone as the proof.

Verification: 1 adversarial verifier, 0 refuted.

### SR-13: GitHub App manifest in the README omits Commit statuses: Read & Write, so every status POST 403s

- Severity: high
- Where: backend/README.md:169
- Difficulty for an attacker: trivial
- Category: permissions-manifest-mismatch
- Status: Fixed in the backend rewrite (2026-09-03): statuses removed; backend/README.md lists the two permissions actually needed.

What it is.

The documented manifest (backend/README.md:169-174) tells the operator to grant only 'Pull requests: Read & Write, Contents: Read, Issues: Write, Metadata: Read'. The only write endpoint the review pipeline needs beyond pull requests is POST /repos/{repo}/statuses/{sha} at backend/services/github_client.py:333, which GitHub maps to the separate 'Commit statuses' repository permission at write level. That permission is never mentioned, so an operator who follows the README exactly builds an installation whose token cannot post any status. Both call sites are affected: the initial pending status (backend/handlers/webhook.py:397-403) and the terminal verdict (backend/services/queue_processor.py:434-440).

What an attacker achieves.

Not an attacker, this is Murphy. Reviews run, burn GPT-4o tokens and post inline comments, and then the status POST returns 403 'Resource not accessible by integration'. The operator sees comments appear but no check on the PR, with the only trace a log line at backend/services/github_client.py:355-362. If the context is wired into branch protection the PR is never mergeable and the reason is invisible in the GitHub UI.

Evidence.

backend/README.md:169-174 lists exactly four permissions and no commit statuses entry: '- Pull requests: Read & Write / - Contents: Read / - Issues: Write / - Metadata: Read'. backend/services/github_client.py:333: `url = f"/repos/{repo_full_name}/statuses/{commit_sha}"` then :343 `response = await self._make_request("POST", url, json=data)`. Callers: backend/handlers/webhook.py:397-403 and backend/services/queue_processor.py:434-440.

Fix.

Change backend/README.md:169-174 to the minimum manifest: Metadata: Read (mandatory), Pull requests: Read & Write, Commit statuses: Read & Write. Drop 'Issues: Write' and 'Contents: Read' (see the separate findings). Add a line telling the operator that an existing installation must be re-authorised after adding a permission, because GitHub does not apply new permissions to an installed App until the owner accepts the request.

Verification: 1 adversarial verifier, 0 refuted.

### SR-14: Pending status is posted after the final verdict, so the required check is stuck on 'pending' forever

- Severity: high
- Where: backend/handlers/webhook.py:244
- Difficulty for an attacker: trivial
- Category: merge-gating
- Status: Fixed in the backend rewrite (2026-09-03): statuses removed.

What it is.

backend/handlers/webhook.py:244 awaits add_review_to_queue, which reaches QueueProcessor.add_task; with self.redis_client None (backend/services/queue_processor.py:149-152) it runs _process_task_immediate inline, and that runs the whole review to completion including the terminal status POST at backend/services/queue_processor.py:434-440 with context 'git-review-assistant/review'. Only after that returns does backend/handlers/webhook.py:260-264 post the 'pending' status on the same context. GitHub keeps the most recent status per context as the current state, so the last write wins and the check settles on pending with description 'ReviewBot Protocol analysis in progress...' permanently, regardless of the review outcome.

What an attacker achieves.

Every PR shows a check that never resolves. If 'git-review-assistant/review' is added to branch protection as a required status check, no PR in the repository can ever be merged, and there is no error anywhere because both API calls returned 201. A contributor cannot distinguish 'the bot is still thinking' from 'the bot finished ten minutes ago'.

Evidence.

backend/handlers/webhook.py:244 `queue_result = await add_review_to_queue(` ... :260 `await post_initial_status_check(` (sequential awaits inside handle_pull_request_event, itself awaited inline at backend/handlers/webhook.py:134). backend/services/queue_processor.py:149-152: `if not self.redis_client: / await self._process_task_immediate(task) / return True`. backend/services/queue_processor.py:434-440 posts the terminal state with context 'git-review-assistant/review'; backend/handlers/webhook.py:402 posts 'pending' with the identical context.

Fix.

Post the pending status before queueing, not after: move the post_initial_status_check call above the add_review_to_queue call at backend/handlers/webhook.py:244, and add the same pending post to the READY_FOR_REVIEW branch at :281. Until the queue is genuinely asynchronous this ordering is the only thing that keeps the terminal status last.

Verification: 1 adversarial verifier, 0 refuted.

### SR-15: A 403 on the status POST re-runs the entire review three more times and duplicates every inline comment

- Severity: high (reported as medium, adjusted by verification)
- Where: backend/services/queue_processor.py:317
- Difficulty for an attacker: trivial
- Category: retry-amplification
- Status: Fixed in the backend rewrite (2026-09-03): no whole-review retries; the client retries one request once on 401 or a short Retry-After.

What it is.

The terminal status POST at backend/services/queue_processor.py:434 is the last statement of _process_pr_review_task, after all inline comments have already been posted (:392 and :417). When it raises (which it will, given the missing Commit statuses permission), the exception propagates to _process_task, which retries the whole task up to max_retries=3 (backend/services/queue_processor.py:62, :317-327) by calling add_task again, which with redis_client None recurses straight back into _process_task_immediate and replays the entire review from the top: fresh get_pr_info, fresh get_pr_files, a fresh full LangGraph pass over every file, and a fresh set of inline comments.

What an attacker achieves.

Four complete GPT-4o passes over the diff for one webhook delivery, and four copies of every security and performance comment on the PR (the comment POSTs succeed, only the status POST fails). Cost is 4x, the PR is spammed, and the exponential backoff sleeps at :323-324 (2s + 4s + 8s) run inside the webhook HTTP request because the whole chain is awaited from backend/handlers/webhook.py:134.

Evidence.

backend/services/queue_processor.py:62 `self.max_retries = 3`. :306-327 `except Exception as e: ... if task.retry_count < task.max_retries: task.retry_count += 1 ... delay = 2 ** task.retry_count ... await asyncio.sleep(delay) ... await self.add_task(task)`. add_task at :146-152 with no redis_client calls _process_task_immediate, which calls _process_task at :468. The comment loops that get replayed are at :381-403 and :406-428; the failing call is at :434-440.

Fix.

Wrap the terminal create_status_check in its own try/except inside _process_pr_review_task so a status failure is logged but does not fail the task, and make the retry path idempotent (skip files whose comments were already posted) before it is allowed to replay a review that has side effects on the PR.

Verification: 1 adversarial verifier, 0 refuted.

### SR-16: Documented setup builds the venv with bare python3, which is 3.14.6 on this host, where three pinned compiled deps have no wheel and no pure-Python fallback

- Severity: high
- Where: scripts/quick-setup.sh:109
- Difficulty for an attacker: trivial
- Category: environment-reproducibility
- Status: Fixed in the backend rewrite (2026-09-03): backend/README.md names Python 3.13; scripts/quick-setup.sh removed.

What it is.

Both documented install paths invoke the unqualified interpreter: scripts/quick-setup.sh:103 gates on 'command -v python3', :109 runs 'python3 -m venv .venv', :115 runs 'pip install -r requirements.txt'; backend/README.md:56 gives the same 'python3 -m venv .venv' and :65 the same pip line. On this machine 'python3' resolves to /usr/local/bin/python3, which is 3.14.6, so the venv is 3.14 and pip computes cp314 tags. Three pinned compiled dependencies publish no cp314 wheel and, unlike SQLAlchemy, no py3-none-any fallback, so pip must build each from sdist: (a) pydantic-core 2.23.4, pinned exactly by pydantic==2.9.2 at backend/requirements.txt:4 (pydantic v2.9.2 pyproject.toml:53 reads 'pydantic-core==2.23.4', so pip cannot substitute a newer core), whose wheels stop at cp313 and whose build needs Rust plus pyo3 0.22.2 (pydantic-core v2.23.4 Cargo.toml:31), a PyO3 release whose build config only knows abi3 up to minor 12 (pyo3-build-config/src/impl_.rs:42 'pub(crate) const ABI3_MAX_MINOR: u8 = 12;') and which predates CPython 3.14 entirely; (b) greenlet==3.1.1 at :37, wheels cp38 to cp [...]

What an attacker achieves.

Murphy achieves a second, independent install failure that survives fixing the langchain conflict. Even with the resolver conflict repaired, the first 'pip install -r requirements.txt' on this host drops into three Rust and C source builds against a Python the toolchains do not support. Nothing tells the owner which interpreter is expected, and the one artefact that did (python:3.11-slim) was deleted, so the failure looks like a mystery rather than a version mismatch.

Evidence.

python3 -VV to 'Python 3.14.6 (main, Jun 10 2026, 10:03:53)'; which -a python3 to /usr/local/bin/python3 first. scripts/quick-setup.sh:109 'python3 -m venv .venv'; :115 'pip install -r requirements.txt'. backend/README.md:56 'python3 -m venv .venv'; :65 'pip install -r requirements.txt'. backend/requirements.txt:4 'pydantic==2.9.2'; :27 'tiktoken==0.8.0'; :37 'greenlet==3.1.1 # Required for SQLAlchemy async support'. curl raw.githubusercontent.com/pydantic/pydantic/v2.9.2/pyproject.toml line 53: 'pydantic-core==2.23.4'.

Fix.

Pin the interpreter rather than raising the dependency floor. Add backend/.python-version containing '3.11' (the host already has 3.11.15 at /opt/homebrew/bin/python3.11 and 3.13.7 at /usr/local/bin/python3.13, either of which has wheels for every pin), change scripts/quick-setup.sh:109 and backend/README.md:56 to 'python3.11 -m venv .venv', and restore a backend/Dockerfile pinned to python:3.11-slim so the pin is reproducible off this laptop. Have quick-setup.sh fail loudly if the chosen interpreter is missing instead of silently falling through to bare python3.

Verification: 1 adversarial verifier, 0 refuted.

### SR-17: Raw PR diff is carried verbatim into LangChain chain inputs, which are shipped to LangSmith by the tracer even though the prompt bug stops it reaching OpenAI

- Severity: high
- Where: backend/services/review_workflow.py:278
- Difficulty for an attacker: trivial
- Category: data-exposure
- Status: Fixed in the backend rewrite (2026-09-03): startup refuses LangSmith tracing variables; patches are redacted before they enter chain inputs.

What it is.

file.patch is placed into the chain input dict unmodified and handed to LLMChain.arun(). LangChain's Chain.acall passes that entire input dict to on_chain_start BEFORE any template substitution, so the LangSmith tracer serialises the raw patch as the run's inputs. This leg does not depend on the ChatPromptTemplate defect at ai_reviewer.py:292: the placeholder is never substituted, so nothing reaches api.openai.com, but the callback payload still carries the full patch off the machine. LANGCHAIN_TRACING_V2 defaults to True in settings and backend/.env.example instructs the operator to set it plus a LangSmith key. Activation requires the two values to be real process environment variables (pydantic-settings reads .env without exporting to os.environ, and LangChain's tracer reads os.environ), which is exactly how Railway/Render/Heroku inject config, and TrustedHostMiddleware names those three platforms as the deploy targets.

What an attacker achieves.

Every secret present in any reviewed diff (API keys, private keys, DB URLs with inline passwords) is transmitted to smith.langchain.com and retained in a third-party trace store, with no redaction and no operator-visible indication. No attacker action is needed; any contributor who opens a PR touching a credential file triggers it.

Evidence.

backend/services/review_workflow.py:215 `code_diff=file.patch or ""`; :278 `chain_input = {..., "code_diff": file_state["code_diff"]}` (repeated at :317, :346, :379, :407, :439); backend/services/ai_reviewer.py:1166 `result = await self.security_chain.arun(**chain_input)`. langchain==0.3.13 libs/langchain/langchain/chains/base.py acall: `inputs = await self.aprep_inputs(input)` then `run_manager = await callback_manager.on_chain_start(None, inputs, run_id, name=run_name)` BEFORE `self._validate_inputs(inputs)` at :210 - the untemplated dict, code_diff included, is what the tracer sees.

Fix.

Redact the patch before it is ever placed in a dict that a chain or runnable receives, i.e. at review_workflow.py:215 and ai_reviewer.py:1081, not inside the prompt. Independently, do not default LANGCHAIN_TRACING_V2 to True (settings.py:45) - tracing that ships full code diffs to a third party should be opt-in, and .env.example should say what it sends.

Verification: 1 adversarial verifier, 0 refuted.

### SR-18: No redactor anywhere between get_pr_files and the prompt, so fixing the ChatPromptTemplate defect converts a silent no-op into a live secret exfil to api.openai.com

- Severity: high
- Where: backend/services/ai_reviewer.py:1081
- Difficulty for an attacker: trivial
- Category: data-exposure
- Status: Fixed in the backend rewrite (2026-09-03): services/redaction.py runs on the patch before the prompt, the comment and the database, and on model output before it is logged or stored (test_redaction, test_runner).

What it is.

The patch travels GitHub API to PRFile.patch to FileAnalysisState.code_diff to chain_input['code_diff'] with exactly one transformation applied: a 100KB length truncation. There is no filename denylist, no secret pattern scrub, no entropy filter and no hunk filter on that path. The only masking code in the repository, SecurityScanner._mask_secret, is never reachable (SecurityScanner is defined and never imported). The reason no key has reached OpenAI yet is accidental: all ten prompts are built with raw SystemMessage/HumanMessage instances rather than message templates, so ChatPromptTemplate infers zero input_variables and '{code_diff}' is sent to the model as a literal string, while Chain._validate_inputs silently discards the extra kwargs. The moment someone fixes that prompt bug, the unredacted patch starts flowing to api.openai.com on every PR.

What an attacker achieves.

A single one-line fix to the prompt construction (converting SystemMessage/HumanMessage to the template forms) simultaneously and silently arms full-diff exfiltration to OpenAI. Anyone who opens a PR adding a credential file has that credential sent to a third-party inference API and, per OpenAI retention, held for up to 30 days.

Evidence.

backend/services/github_client.py:194 `patch = file_data.get("patch")` to :209 `patch=patch`; backend/models/github.py:128-131 the only transformation is `if v and len(v) > 100000: return v[:100000] + "\n... (truncated)"`; backend/services/ai_reviewer.py:1078-1081 `chain_input = {"filename": ..., "language": ..., "code_diff": file.patch}`. Proof the placeholder is currently inert: langchain-core 0.3.28 prompts/chat.py `_convert_to_message` returns a BaseMessage unchanged (`elif isinstance(message, BaseMessage): _message = message`), and ChatPromptTemplate.**init** only does `input_vars.update(_message.input_variables)` for BaseChatPromptTemplate/BaseMessagePromptTemplate, so input_variables [...]

Fix.

Treat the prompt fix and the redactor as one change. Add a scrub_patch(patch) to patch step called at review_workflow.py:215 and ai_reviewer.py:1081 that replaces matched secrets with a fixed token such as [REDACTED:openai_key] before the text can enter any chain input, and make it fail closed (drop the file) when a match is found in a file whose name is on a credential denylist.

Verification: 1 adversarial verifier, 0 refuted.

### SR-19: Model-authored text is inserted into a public PR comment with no output filter, and the prompt explicitly teaches the model to quote the offending line verbatim

- Severity: high
- Where: backend/utils/helpers.py:286
- Difficulty for an attacker: easy
- Category: data-exposure
- Status: Fixed in the backend rewrite (2026-09-03): services/comment_renderer.sanitise on every model string; evidence is redacted before the model sees it.

What it is.

format_review_comment concatenates the model's description and recommendation strings into the comment body with no filtering, escaping or length cap, and queue_processor posts that body straight to the GitHub review-comments API. Nothing on this path inspects the model text for secrets. The prompts actively encourage the echo: the enhanced scoring prompt's worked example at ai_reviewer.py:834 shows the model returning `"current_code": "password = request.args.get('pwd')"`, and the security prompt at ai_reviewer.py:296-302 lists `API_KEY = "sk-..."` as a pattern to report, so a model told to report a hardcoded key will naturally include the key in its description. Going local (Ollama) removes the api.openai.com hop but leaves this leg completely untouched - a local model quoting the key into a public comment leaks it just as thoroughly.

What an attacker achieves.

The bot republishes the secret it just found into a PR comment. That is strictly worse than the original leak: the comment is a separate object from the diff, so rewriting or force-pushing the branch removes the secret from the code but not from the comment; the comment survives branch deletion, is emitted verbatim in email notifications to every repository watcher, and is served by the public issue-comments API. On a public repository the key is broadcast to anyone watching. The bot converts a contained mistake into a published one.

Evidence.

backend/utils/helpers.py:280 `comment = f"{emoji} **{comment_type.title()} Issue** ({severity_text})\n\n"`; :286 `comment += message`; :288-289 `if suggestion: comment += f"\n\n**Suggestion:** {suggestion}"` - message and suggestion are the raw model strings. backend/services/queue_processor.py:384-390 passes `issue.get("description", ...)` and `issue.get("recommendation")` into it, then :392-399 `await github_client.post_review_comment(repo_full_name, pr_number, comment_body, head_sha, filename, issue["line_number"])`; the same pair again at :409-423. backend/services/github_client.py:243-250 sends `"body": body` unmodified.

Fix.

Add a post-flight filter between _parse_json_result and format_review_comment that runs the secret patterns over every model-authored string (description, recommendation, code_snippet, current_code) and either redacts the match or, better, suppresses the whole finding and replaces it with a fixed no-detail message such as 'A possible hardcoded credential was detected on this line. Rotate it and move it to a secret store.' A finding about a secret should never carry the secret.

Verification: 1 adversarial verifier, 0 refuted.

### SR-20: The /api/github/stats proxy returns a shape the dashboard cannot read on either branch, so all three stat tiles are permanently blank

- Severity: high
- Where: app/api/github/stats/route.ts:39
- Difficulty for an attacker: trivial
- Category: correctness
- Status: Fixed in the backend rewrite (2026-09-03): the stats proxy and its backend endpoint are gone; the dashboard reads /api/reviews and /api/status.

What it is.

The proxy has two exit paths and neither produces the object the caller consumes. Happy path (route.ts:39-40) passes the backend body through verbatim: FastAPI pins it to ReviewStatsResponse, whose fields are total_reviews, completed_reviews, failed_reviews, avg_processing_time, avg_score, common_issues, reviews_by_repository, reviews_by_date (backend/models/review.py:227-236, constructed at backend/handlers/review.py:369-381). Error path (route.ts:24-36 and :45-57) returns {success:true, data:{totalReviews, averageScore, criticalIssues, highIssues, mediumIssues, lowIssues, topRepositories, recentActivity}}, nested one level under data. The dashboard does setStats(data) (app/dashboard/page.tsx:79) against interface GitHubStats {totalRepositories, totalPullRequests, totalReviews, securityIssues, avgQualityScore, recentActivity, ...} (app/dashboard/page.tsx:38-51) and reads stats.totalReviews (:276), stats.securityIssues (:300) and stats.avgQualityScore (:342, :343, :350, :351).

What an attacker achieves.

No attacker needed. Every dashboard load shows empty or zero stat tiles regardless of whether the backend is up, and the failure is silent because both branches return HTTP 200 with success:true.

Evidence.

app/api/github/stats/route.ts:39-40 `const data = await response.json()` / `return NextResponse.json(data)`; app/api/github/stats/route.ts:24-36 fallback `return NextResponse.json({ success: true, data: { totalReviews: 0, averageScore: 0, criticalIssues: 0, ... } })`; backend/models/review.py:229-236 `total_reviews: int` / `avg_score: float` / `common_issues` / `reviews_by_repository` / `reviews_by_date`; backend/handlers/review.py:369-381 ReviewStatsResponse(...); app/dashboard/page.tsx:38-51 `interface GitHubStats { totalReviews: number; securityIssues: number; avgQualityScore: number; ...

Fix.

Delete the route. Move the stats query into a server component or a single route that owns the mapping, and make the mapping explicit and typed rather than a pass-through. If the route is kept, the two branches must return the same shape and that shape must be GitHubStats.

Verification: 1 adversarial verifier, 0 refuted.

### SR-21: POST /review/pr returns a job receipt, not findings, so the PR review UI can never render a result

- Severity: high
- Where: app/api/review/pr/route.ts:122
- Difficulty for an attacker: trivial
- Category: correctness
- Status: Fixed in the backend rewrite (2026-09-03): the /review/pr endpoint is gone; reviews are triggered by webhooks only.

What it is.

The backend endpoint the proxy calls is declared response_model=ReviewResponse (backend/handlers/review.py:129) and returns ReviewResponse(review_id=..., status="pending", message="PR review queued for ...", created_at=...) at backend/handlers/review.py:183-188. ReviewResponse is {review_id, status, message, created_at, estimated_completion} (backend/models/review.py:201-207), and because it is a declared response_model FastAPI strips anything else. The proxy then does `data: backendData.data || backendData` (app/api/review/pr/route.ts:126) and hands that to the caller as result.data. hooks/useReviewService.ts:74 returns result.data typed as ReviewResults = {security, performance, quality, summary, score, totalIssues, analysisTime?, linesAnalyzed?} (hooks/useReviewService.ts:15-24). Not one of those keys is present. The real work happens in a BackgroundTask (backend/handlers/review.py:177-181) whose output is never fetched, because nothing in the frontend ever polls GET /review/{review_id}.

What an attacker achieves.

No attacker needed. The headline feature reachable from the UI reports success and shows nothing, every time. A full gpt-4o review is paid for in the background and then discarded.

Evidence.

backend/handlers/review.py:129 `@review_router.post("/pr", response_model=ReviewResponse)`; backend/handlers/review.py:183-188 `return ReviewResponse(review_id=review_id, status="pending", message=f"PR review queued for {request.repository}#{request.pr_number}", created_at=review.created_at)`; backend/models/review.py:201-207 class ReviewResponse fields; app/api/review/pr/route.ts:124-127 `return NextResponse.json({ success: true, data: backendData.data || backendData })`; hooks/useReviewService.ts:15-24 `export interface ReviewResults { security: ReviewFinding[]; ... }`; hooks/useReviewService.ts:73-74 `toast.success('PR analysis completed successfully!'); return result.data`.

Fix.

Pick one contract. Either make the backend endpoint synchronous and return the review results (as POST /review/code already does at backend/handlers/review.py:719-858), or keep it async and have the frontend poll GET /review/{review_id}. Do not keep a proxy whose only job is to relabel a receipt as a result.

Verification: 1 adversarial verifier, 0 refuted.

### SR-22: GET /review/history is shadowed by GET /review/{review_id}, so the history page is permanently empty

- Severity: high
- Where: backend/handlers/review.py:195
- Difficulty for an attacker: trivial
- Category: correctness
- Status: Fixed in the backend rewrite (2026-09-03): the shadowed route is gone; /api/reviews lists reviews.

What it is.

FastAPI matches routes in registration order. `@review_router.get("/{review_id}")` is registered at backend/handlers/review.py:195, and `@review_router.get("/history")` at backend/handlers/review.py:388. The single-segment path /review/history therefore matches the parameterised route first with review_id="history", falls through repo.get_review_by_id("history") returning None, and raises HTTPException(404, "Review not found") (backend/handlers/review.py:203-206). app/history/page.tsx:125 fetches `${backendUrl}/review/history?${params}` and then guards `if (response.ok)` at :126, so the 404 is swallowed with no error state and reviews stays []. This is one of only two places where the browser talks to the Python backend directly, bypassing the Next.js layer entirely, which is why no proxy-level test or fallback catches it. Note the other single-segment routes are safe: /stats/overview, /stats/user, /queue/status and /metrics/* are all two or more segments.

What an attacker achieves.

No attacker needed. The history page renders an empty list forever, and the failure is invisible because the response.ok guard has no else branch.

Evidence.

backend/handlers/review.py:195 `@review_router.get("/{review_id}", response_model=ReviewResultResponse)`; backend/handlers/review.py:388 `@review_router.get("/history", response_model=ReviewHistoryResponse)`; backend/handlers/review.py:205-206 `if not review: raise HTTPException(status_code=404, detail="Review not found")`; backend/main.py:290-292 include_router with prefix="/review"; app/history/page.tsx:125-131 `const response = await fetch(`${backendUrl}/review/history?${params}`)` then `if (response.ok) { ... }` with no else.

Fix.

Move the /{review_id} and /{review_id} DELETE declarations below every literal path in backend/handlers/review.py, or prefix the collection routes (for example /reviews/{review_id}). Add the else branch in app/history/page.tsx so a non-ok response surfaces instead of being silently discarded.

Verification: 1 adversarial verifier, 0 refuted.

## Medium findings

### SR-23: Whole webhook body is buffered before the signature check with no size limit at any layer (unauthenticated memory DoS)

- Severity: medium
- Where: backend/handlers/webhook.py:54
- Difficulty for an attacker: trivial
- Category: webhook-auth
- Status: Fixed in the backend rewrite (2026-09-03): read_body_capped rejects over MAX_WEBHOOK_BODY_BYTES with 413 before the HMAC check (test_webhook).

What it is.

verify_webhook_signature() reads the entire body into memory (backend/handlers/webhook.py:54) before verify_github_signature() at :62; the only earlier checks are header presence (:37-51), satisfiable with dummy values. uvicorn 0.24.0 has no body-size option, FastAPI/Starlette request.body() accumulates all chunks, and main.py adds only CORS, TrustedHost and logging middleware (backend/main.py:69-129). The Next.js proxy buffers the same body again as a JS string (app/api/webhook/github/route.ts:23).

What an attacker achieves.

Any unauthenticated client forces the backend and proxy to allocate hundreds of MB per request by POSTing a large body with two dummy headers; a few concurrent requests exhaust the 1024 MB Vercel function (vercel.json app/api/webhook/**/* memory 1024) or the backend host. The secret gives no protection because it is checked after allocation.

Fix.

Reject on Content-Length before reading (413 above ~1 MB) and stream-read with a hard cap in the backend (small ASGI middleware or request.stream() with a byte count); apply the same cap in the proxy before request.text(); add per-source inbound rate limiting on /webhook/github; consider binding HOST to 127.0.0.1 when the proxy is the entry point.

Verification: 2 adversarial verifiers, 0 refuted.

### SR-24: No replay or idempotency protection: X-GitHub-Delivery is logged but never stored or checked, and the HMAC carries no timestamp, so one captured delivery re-triggers a full paid review indefinitely

- Severity: medium
- Where: backend/handlers/webhook.py:104
- Difficulty for an attacker: moderate
- Category: webhook-auth
- Status: Fixed in the backend rewrite (2026-09-03): delivery ids are stored in webhook_deliveries; a repeat answers 200 duplicate and does nothing (test_webhook).

What it is.

The delivery GUID is read at backend/handlers/webhook.py:104 only for logging and the response. A pydantic WebhookDelivery is built at :122-128 with id f'{delivery_id}_{int(time.time())}' (so replays get distinct ids) and only its id is copied into the task payload (backend/services/queue_processor.py:570). Nothing persists it: WebhookRepository (backend/database/repositories/webhook_repository.py:14) has zero callers and the webhook_deliveries table (backend/database/models.py:160-193) is never written; webhook.py imports (:10-20) include no repository.

What an attacker achieves.

Anyone holding one valid delivery (ngrok's inspector at 127.0.0.1:4040, GitHub's webhook UI for repo admins, any intermediary log, a compromised intermediate) can resend it forever without the secret: repeated OpenAI spend, duplicate review comments and repeated status-check flips on the same head SHA.

Fix.

Persist the delivery GUID via the existing webhook_deliveries table and WebhookRepository.create_webhook_delivery with a unique constraint, insert before processing and return 200 'already processed' on conflict; add a timestamp/age check; dedupe review work by (repository, pr_number, head_sha) and refuse to re-review an unchanged head; move execution to a worker and return 202; rotate the secret if the ngrok inspector or logs may have been expos [...]

Verification: 2 adversarial verifiers, 0 refuted.

### SR-25: Hard-coded TrustedHost allowlist bound to DEBUG=false rejects most real hostnames (and the webhook proxy forwards the public Host header), pushing operators to run production with DEBUG=true

- Severity: medium
- Where: backend/main.py:69
- Difficulty for an attacker: trivial
- Category: authz-endpoints
- Status: Fixed in the backend rewrite (2026-09-03): ALLOWED_HOSTS setting; the proxy is deleted in Phase 5 (test_webhook covers a configured public host).

What it is.

is_production is simply 'not DEBUG' (backend/config/settings.py:15 DEBUG False by default, :118-120), so TrustedHostMiddleware is on by default with allowed_hosts *.railway.app, *.render.com, *.herokuapp.com, localhost (backend/main.py:69-73). Starlette 0.27.0 strips the port and suffix-matches, returning 400 'Invalid host header'; Render's real domain *.onrender.com, 127.0.0.1, ngrok hosts, Docker service names, *.vercel.app and any custom domain are rejected before the webhook handler runs.

What an attacker achieves.

No direct compromise; the middleware is a denial of service against the operator's own deployment and the indirect result is a production instance with DEBUG=true and every dev-only endpoint and detailed error body exposed.

Fix.

Make ALLOWED_HOSTS a setting (default the real domain, or '*' behind a reverse proxy) and decouple is_production from DEBUG via an ENVIRONMENT setting; have the proxy forward only X-GitHub-Event, X-GitHub-Delivery, X-Hub-Signature-256, Content-Type and User-Agent and let fetch set Host and Content-Length.

Verification: 2 adversarial verifiers, 0 refuted.

### SR-26: Every synchronize re-runs a full multi-pass review of the whole PR with no head-SHA dedupe, in-flight guard, cancellation or comment cleanup; drafts are reviewed under DEBUG

- Severity: medium (reported as high, adjusted by verification)
- Where: backend/handlers/webhook.py:223
- Difficulty for an attacker: trivial
- Category: dos-limits
- Status: Fixed in the backend rewrite (2026-09-03): dedupe by head SHA, supersede pending, cancel in flight (test_queue).

What it is.

opened, synchronize and reopened all queue a PRAnalysisRequest with include_security/performance/quality True (backend/handlers/webhook.py:223-249) and ready_for_review does the same (:274-291). synchronize fires on every push and base update; the review fetches every PR file (backend/services/queue_processor.py:361; github_client.py:185-189), not the delta, and posts a fresh inline comment per issue (queue_processor.py:377-428, :392-399, :417-424) with no listing or deletion of earlier bot comments.

What an attacker achieves.

A contributor pushing N fixup commits (or anyone who can open PRs on a public installed repo) triggers N concurrent full gpt-4o reviews (6 calls per file, times the retry and fallback multipliers) and N stacks of near-duplicate bot comments, with no rate limit or spend cap.

Fix.

Key reviews by (repo, pr_number, head_sha) and skip when already reviewed or in flight; cancel the superseded asyncio.Task when a newer SHA arrives; debounce synchronize by 30-60 s; review only files changed since the last reviewed SHA; list and update or delete existing app comments, or post one PR review via the existing post_pr_review (github_client.py:281); add per-repository and per-author budgets; keep draft handling independent of DEBUG.

Verification: 3 adversarial verifiers, 0 refuted.

### SR-27: LangGraph workflow aborts for normal PRs (default recursion limit 25 trips at roughly 3+ files) and for empty file sets (unguarded router index), and every abort falls back to a second full basic-chain pass that also reviews markdown/JSON/YAML

- Severity: medium (reported as high, adjusted by verification)
- Where: backend/services/review_workflow.py:920
- Difficulty for an attacker: trivial
- Category: dos-limits
- Status: Fixed in the backend rewrite (2026-09-03): recursion_limit set from the file count; empty file sets route straight to synthesis (test_workflow, 40 files).

What it is.

The graph runs 2 setup nodes, 7 per file (8 via risk_assessment), and 3 closing nodes: 5 + 7N steps. run_review calls compiled_workflow.ainvoke with a RunnableConfig setting only callbacks and tags (:920-926) and nothing sets recursion_limit (grep); langchain-core 0.3.28 DEFAULT_RECURSION_LIMIT = 25 and langgraph 0.2.59 loop.py allows about 26 steps, so 4 files (33) always fails and 3 (26) is borderline with GraphRecursionError.

What an attacker achieves.

Every mid-sized PR costs roughly (6N + 1) + 15 LLM calls instead of 6N and the LangGraph path silently never completes; docs-only PRs cost as much as code PRs and still hit the comment-posting crash; any LangGraph exception doubles spend, all inline in the webhook request.

Fix.

Pass recursion_limit = 10 + 8 * len(files) (or loop over files inside one node); guard the router when current_file_index >= len(files_to_review) and add an all_complete edge from prioritize_files for empty lists; do not fall back to a second full LLM pass on failure, surface the error or reuse partial state; share one _should_review_file that skips non-code languages in both paths.

Verification: 3 adversarial verifiers, 0 refuted.

### SR-28: Backend authentication is a mock that is live outside DEBUG: any 'code' mints a 24 h JWT for testuser, /auth/token accepts any password via query string, OAuth state is a constant, admin allowlist is hard-coded and SECRET_KEY defaults to a known string

- Severity: medium
- Where: backend/handlers/auth.py:112
- Difficulty for an attacker: trivial
- Category: authz-endpoints
- Status: Fixed in the backend rewrite (2026-09-03): the mock auth endpoints are deleted; the only credential is LOCAL_API_TOKEN, compared in constant time.

What it is.

POST /auth/github/callback (backend/handlers/auth.py:112-173) never contacts GitHub; for any code it upserts a fixed 'testuser' (:134-147, avatar identicons/testuser.png at :144) and returns a 24 h JWT (:157); unlike /auth/dev/create-user (:342) it is not gated on settings.DEBUG. POST /auth/token (:176-229) accepts any password when username == 'testuser' (:200-207); username and password are bare parameters (:177-179) so FastAPI binds them as query parameters, which main.py:95-101 and :107-114 log via str(request.url).

What an attacker achieves.

Any caller obtains a 'testuser' session on a non-debug deployment and, with the default SECRET_KEY, forges tokens for any user id; worthless today because nothing valuable sits behind require_auth, but it is the foothold once routes are protected, and any real password later sent to /auth/token lands in logs and Sentry breadcrumbs.

Fix.

Delete the mock callback, /auth/github/login and /auth/token (or gate them on DEBUG like /auth/dev/create-user); take credentials from a request body and redact query strings in log_requests; fail startup when SECRET_KEY is the default and DEBUG is false; remove require_admin or back it with User.is_admin (database/models.py:212); attach require_auth to the review and github routers.

Verification: 2 adversarial verifiers, 0 refuted.

### SR-29: Unauthenticated health and status endpoints make a live gpt-4o completion and an unauthenticated GitHub API call per request and leak configuration

- Severity: medium
- Where: backend/main.py:173
- Difficulty for an attacker: trivial
- Category: dos-limits
- Status: Fixed in the backend rewrite (2026-09-03): /health returns status and version only; /api/status is gated and never runs a generation.

What it is.

GET /health/detailed (backend/main.py:173-235, no Depends) calls get_ai_health, which instantiates ChatOpenAI and runs agenerate with max_tokens=10 on the real key (backend/services/ai_reviewer.py:1413-1425), and get_github_health, which GETs api.github.com/rate_limit unauthenticated (github_client.py:586-595, subject to the 60/hour per-IP limit), plus a DB round trip, with no auth, cache or throttle, and returns raw exception strings on failure (:221-224).

What an attacker achieves.

Cheap remote consumption of OpenAI request quota (429s starving real reviews) and the server IP's GitHub quota, an oracle for key validity and model name, and a fingerprint of ports, debug state and configuration.

Fix.

Restrict /health/detailed to an internal network or admin token, cache results for 60 s, replace the live completion with a models.list call or a last-review-succeeded flag, and trim /status and /api/health to a bare status string.

Verification: 2 adversarial verifiers, 0 refuted.

### SR-30: Request middleware and uvicorn access log record full URLs including query-string credentials (password, OAuth code, installation_id, user_id)

- Severity: medium
- Where: backend/main.py:98
- Difficulty for an attacker: trivial
- Category: data-logging
- Status: Fixed in the backend rewrite (2026-09-03): the request log records method, path and status only.

What it is.

log_requests logs url=str(request.url) at INFO twice per request (backend/main.py:95-101, :107-114) and on failure (:121-128), including the query string. Secrets in query strings: POST /auth/token username and password (backend/handlers/auth.py:176-180), POST /auth/github/callback code and state (:113-115), installation_id on every /github/* route (backend/handlers/github.py:19), user_id on /review/history and /review/stats/user (review.py:390, :498). Uvicorn's access log is also on (package.json:8; main.py:330 access_log=True) and uvicorn 0.24.0 appends scope['query_string'] to the line.

What an attacker achieves.

Anyone reading stdout, terminal scrollback, a platform log viewer or the Sentry project obtains passwords (any value works today), OAuth codes and installation_id values that act as bearer credentials for /github/*; a future real password check would persist plaintext passwords in logs.

Fix.

Log request.url.path or a redacted URL; move /auth/token to OAuth2PasswordRequestForm or a JSON body; take installation_id from the session; run uvicorn with --no-access-log or a formatter that drops the query string.

Verification: 2 adversarial verifiers, 0 refuted.

### SR-31: With SENTRY_DSN set, code submitted to /review/code and local variables holding diffs are shipped to Sentry on errors

- Severity: medium
- Where: backend/handlers/review.py:876
- Difficulty for an attacker: easy
- Category: data-logging
- Status: Fixed in the backend rewrite (2026-09-03): sentry-sdk removed; STRICT_LOCAL refuses SENTRY_DSN.

What it is.

sentry_sdk.init runs whenever SENTRY_DSN is set (backend/main.py:28-37) with FastApiIntegration and 1.38.0 defaults: max_request_body_size 'medium' (bodies up to 10,000 bytes attached), include_local_variables True, max_value_length 1024, LoggingIntegration on. review_code_direct wraps failures in HTTPException 500 (review.py:862-876), which the Starlette integration captures with the JSON body (files[].content and files[].patch, the code twice, app/api/review/route.ts:23-34) and frame locals such as request, files_data, content, pr_files (review.py:734-787).

What an attacker achieves.

Code under review, including credentials the tool is meant to flag, is stored at sentry.io in error events readable by anyone with project access; an unintended data flow rather than a direct external exploit.

Fix.

Pass max_request_body_size='never' and include_local_variables=False, add a before_send hook dropping request.data and frame vars for /review/* and /webhook/*, set LoggingIntegration(event_level=None), and keep SENTRY_DSN unset locally.

Verification: 2 adversarial verifiers, 0 refuted.

### SR-32: get_pr_files does not paginate: only the first 30 files of a PR are reviewed and the status check still reports success

- Severity: medium
- Where: backend/services/github_client.py:189
- Difficulty for an attacker: easy
- Category: dos-limits
- Status: Fixed in the backend rewrite (2026-09-03): list_pull_files follows Link headers at 100 per page (test_github_client).

What it is.

_make_request is called with no per_page/page parameters and no Link handling (backend/services/github_client.py:188-189, iterated at :191-212); GitHub returns 30 files per page by default (max 100, 3000 per PR), so files beyond 30 are silently ignored and create_status_check posts success/failure from the subset (queue_processor.py:431-440). MAX_FILES_PER_PR (settings.py:63) is unused.

What an attacker achieves.

A change can be hidden from the reviewer by placing it after the first 30 files (alphabetical by path) and large PRs get a green status for code never examined.

Fix.

Paginate with per_page=100 following Link until empty or MAX_FILES_PER_PR; post a neutral/error status saying the review was partial when the cap is exceeded.

Verification: 2 adversarial verifiers, 0 refuted.

### SR-33: GitHub client retry semantics: 403 handler sleeps Retry-After inline then re-raises, the rate limiter is inert because header lookups are case-sensitive, and retry_async is dead code

- Severity: medium
- Where: backend/services/github_client.py:169
- Difficulty for an attacker: easy
- Category: dos-limits
- Status: Fixed in the backend rewrite (2026-09-03): one bounded retry per request; the inert rate limiter is gone.

What it is.

On a 403 _make_request sleeps Retry-After inline (:169-173) then re-raises (:175), so the caller fails and _process_task retries the whole review up to 4 times, each sleeping again. update_rate_limit receives dict(response.headers) (:147) whose keys httpx 0.25.2 lowercases, so headers.get('X-RateLimit-Remaining'/'X-RateLimit-Reset') (:44-45) always return 0: wait_if_needed (:28-39) never sleeps and a spurious 'rate limit low' warning logs on every request (:50-56). utils.helpers.retry_async (helpers.py:322-357) is imported (github_client.py:16; queue_processor.py:22) but never called.

What an attacker achieves.

A secondary rate limit (one POST per issue per file makes this easy) becomes 4 x (full review + 60 s sleep) inside one request, and false warnings mask a real limit.

Fix.

Use response.headers directly (case-insensitive); on 403/429 retry the single request with bounded retry_async or raise immediately without sleeping; never sleep inline in a handler; batch inline comments into one POST /pulls/{n}/reviews.

Verification: 2 adversarial verifiers, 0 refuted.

### SR-34: next 14.2.33 ships 23 open advisories into the running app; only two have a 14.x backport, the rest need Next 15.5.21+/16

- Severity: medium (reported as high, adjusted by verification)
- Where: package.json:45
- Difficulty for an attacker: easy
- Category: deps-history-scripts
- Status: Fixed in the frontend rebuild (2026-09-03): next 15.5.25, react 19, eslint 9; npm audit runs in CI at the high level.

What it is.

package.json:45 pins next 14.2.33 (package-lock.json:8931-8934). npm audit lists RSC DoS GHSA-mwv6-3258-q52c (fixed 14.2.34) and GHSA-5j59-xgg2-r9c4 (14.2.35), then issues fixed only in 15.0.8/15.5.x/15.5.21: GHSA-h25m-26qc-wcjf RSC deserialization DoS 7.5, GHSA-q4gf-8mx6-v5v3, GHSA-8h8q-6873-q5fj, GHSA-c4j6-fc7j-m34r SSRF via WebSocket upgrade 8.6, GHSA-wfc6-r584-vfw7 cache poisoning, GHSA-h64f-5h5j-jqjh image optimiser DoS, GHSA-m99w-x7hq-7vfj Server Actions DoS, GHSA-p9j2-gv94-2wf4 rewrites SSRF, GHSA-955p-x3mx-jcvp; fixAvailable only next 16.3.4 (major).

What an attacker achieves.

Unauthenticated remote DoS via crafted RSC/server-function requests (CVSS 7.5 class) and, self-hosted, image-optimiser exhaustion and cache poisoning; Vercel absorbs some DoS classes but next start (package.json:9) and standalone output (next.config.mjs:4) remain vulnerable.

Fix.

Short term bump to 14.2.35; then migrate to Next 15.5.21+ or 16.x, bump eslint-config-next to match, remove the dead experimental.serverActions block, and correct README.md:52.

Verification: 3 adversarial verifiers, 0 refuted.

### SR-35: Session JWTs use python-jose 3.3.0 (CRITICAL algorithm-confusion CVE and two JWE-bomb CVEs) although the current HS256 shared-secret usage is not exploitable and PyJWT is already installed

- Severity: medium
- Where: backend/requirements.txt:39
- Difficulty for an attacker: hard
- Category: deps-history-scripts
- Status: Fixed in the backend rewrite (2026-09-03): python-jose removed; no JWT auth remains apart from the GitHub App JWT signed with PyJWT.

What it is.

backend/requirements.txt:39 pins python-jose[cryptography]==3.3.0: CVE-2024-33663 GHSA-6c5p-j8vq-pqhj (algorithm confusion, CRITICAL, fixed 3.4.0), CVE-2024-33664 GHSA-cjwg-qfpm-7377 and CVE-2024-29370 PYSEC-2025-185 (JWE decompression bombs). Used at backend/utils/crypto.py:119-126 (jwt.encode HS256 with SECRET_KEY) and :142-146 (jwt.decode with algorithms=['HS256']); no asymmetric key and no jwe.decrypt, so not exploitable now. PyJWT is already a direct dependency (requirements.txt:14; github_client.py:8).

What an attacker achieves.

Nothing today; if a future change passes a public key or widens algorithms, CVE-2024-33663 becomes token forgery (full auth bypass). The default SECRET_KEY (settings.py:16) is the larger auth issue, covered separately.

Fix.

Replace the two python-jose calls with PyJWT (encode/decode with algorithms=['HS256']), drop python-jose and its ecdsa/rsa tree, bump PyJWT to >=2.13.0; if jose must stay, pin >=3.4.0.

Verification: 2 adversarial verifiers, 0 refuted.

### SR-36: LangChain stack is 8+ months behind with 19 open advisories including a CRITICAL serialization CVE; the Dependabot branch was never merged and is itself below the patched version

- Severity: medium
- Where: backend/requirements.txt:22
- Difficulty for an attacker: hard
- Category: deps-history-scripts
- Status: Fixed in the backend rewrite (2026-09-03): langchain 1.3.18, langchain-core 1.6.1, langgraph 1.2.11.

What it is.

backend/requirements.txt:20-27 pins langchain 0.3.13, langchain-openai 0.2.14, langchain-core 0.3.28, langchain-community 0.3.27, langgraph 0.2.59, langsmith 0.2.7. langchain-core 0.3.28: 12 advisories incl. CVE-2025-68664 GHSA-c67j-w6g6-q2cm (dumps/loads serialization injection leaking secrets, CRITICAL, fixed 0.3.81), CVE-2025-65106 GHSA-6qv9-48xg-fc7f, CVE-2026-44843 GHSA-pjwx-r37v-7724 (fixed 0.3.85), CVE-2026-40087 GHSA-926x-3r5x-gfhw, CVE-2026-34070 GHSA-qh6h-p6c9-ff54; langchain 0.3.13: GHSA-3644-q5cj-c5c7, GHSA-gr75-jv2w-4656; langsmith 0.2.7: GHSA-f4xh-w4cj-qxq8 (TracingMiddleware fil [...]

What an attacker achieves.

Nothing direct now; once tracing is exported or any run-data deserialisation is added, PR content containing '{"lc": ...}' structures could be revived as objects extracting secrets such as OPENAI_API_KEY (CVSS 9.x).

Fix.

Bump the family together: langchain-core >=0.3.85, langchain >=0.3.30, langsmith >=0.8.18, compatible langgraph and langchain-openai; drop langchain-community (not imported); close the stale Dependabot PR; default LANGCHAIN_TRACING_V2 to False.

Verification: 2 adversarial verifiers, 0 refuted.

### SR-37: Thirteen runtime npm dependencies are never imported; they contribute 4 of the 7 critical advisories and roughly two thirds of the audit list

- Severity: medium
- Where: package.json:33
- Difficulty for an attacker: hard
- Category: deps-history-scripts
- Status: Fixed in the frontend rebuild (2026-09-03): every unused package removed; the runtime set is next, react, react-dom, next-themes, radix-ui, lucide-react and five small utilities (class-variance-authority, clsx, server-only, tailwind-merge, tw-animate-css); the shadcn CSS layer is vendored rather than depended on.

What it is.

No source file under app/, components/, lib/, hooks/, contexts/ or scripts/ imports next-auth, @auth/prisma-adapter, axios, langchain, @langchain/community, @langchain/openai, @octokit/auth-app, @octokit/rest, @octokit/webhooks, zustand, react-dropzone, react-hook-form or @hookform/resolvers, yet all sit in dependencies (package.json:33-66).

What an attacker achieves.

No runtime exploit; a much wider supply-chain surface (1,000+ extra packages incl. a gRPC/protobuf stack and an FTP client) on every npm install and CI build, plus dev-tool exposure for whoever runs the scripts.

Fix.

Remove the 13 unused packages and regenerate the lockfile (removes 4 of 7 criticals and most highs); move puppeteer and sharp to one-off tooling or bump to 25.x/0.35.x; npm audit fix the pure-transitive bumps; what remains should be next and the eslint-config-next chain.

Verification: 2 adversarial verifiers, 0 refuted.

### SR-38: 'datetime' is never imported in handlers/review.py, so list_reviews and get_review_history raise NameError (500) whenever a review exists

- Severity: medium
- Where: backend/handlers/review.py:300
- Difficulty for an attacker: trivial
- Category: gaps-critic-prep
- Status: Fixed in the backend rewrite (2026-09-03): the handler no longer exists.

What it is.

Lines 300, 301, 304, 316 and 447 use isinstance(..., datetime), datetime.fromisoformat and datetime.utcnow(), but the module imports only uuid and time at the top (:1-24) and 'from datetime import timedelta' inside three functions (:348, :404, :504). The NameError is caught by the blanket except and returned as HTTP 500 with the exception text, so GET /review/ fails for any non-empty result set.

What an attacker achieves.

No attacker; listing reviews is broken and leaks a Python error string in 'detail'.

Fix.

Add 'from datetime import datetime, timedelta' at module level, drop the function-local imports, and stop returning str(e).

Verification: 2 adversarial verifiers, 0 refuted.

### SR-39: LANGCHAIN_TRACING_V2 defaults to true and .env.example instructs the operator to set it, which ships every code diff off-box and contradicts the fully-local goal

- Severity: medium
- Where: backend/config/settings.py:45
- Difficulty for an attacker: trivial
- Category: local-inference-migration/data-egress
- Status: Fixed in the backend rewrite (2026-09-03): the setting no longer exists; a tracing variable set to true stops startup (test_settings).

What it is.

settings.py:45 declares `LANGCHAIN_TRACING_V2: bool = True` and .env.example:30 sets `LANGCHAIN_TRACING_V2=true` next to a LANGCHAIN_API_KEY placeholder at :28. When active, LangSmith tracing uploads full prompt and completion payloads, which here are the customer's private PR diffs, to api.smith.langchain.com. That is the exact data the fully-local goal exists to keep on the machine, and moving inference to Ollama does nothing about it.

What an attacker achieves.

No attacker. A latent, one-shell-command-away egress of private source diffs to a third party, in a branch whose entire premise is that nothing leaves the machine. The same applies to sentry_sdk.init at main.py:29-37, which is gated on SENTRY_DSN and runs with traces_sample_rate 1.0 outside production.

Fix.

Flip the default to `LANGCHAIN_TRACING_V2: bool = False` at settings.py:45 and set it to false in .env.example:30, removing the LANGCHAIN_API_KEY placeholder or commenting it out with a note that enabling it sends diffs off-box. If tracing is genuinely wanted for the course requirement, point it at a self-hosted LangSmith and say so explicitly in the .env.example comment. Make the same call consciously for SENTRY_DSN.

Verification: 1 adversarial verifier, 0 refuted.

### SR-40: .gitignore:118 silently untracks test_*.py outside backend/tests/, so the natural first move produces a file git refuses to add

- Severity: medium
- Where: .gitignore:118
- Difficulty for an attacker: trivial
- Category: tooling-trap
- Status: Fixed 2026-09-03 (commit 92460dc): .gitignore ignores only root-level scratch files.

What it is.

.gitignore:118 is `test_*.py` with negations at :119 `!backend/tests/test_*.py` and :120 `!backend/tests/**/test_*.py`. Verified by `git check-ignore` (without -v, which prints only genuinely ignored paths): IGNORED are backend/test_no_egress.py, tests/test_egress.py, test_egress.py and scripts/test_egress.py. IMPORTANT CORRECTION to the briefing: the negations DO work. backend/tests/test_no_egress.py and backend/tests/network/test_egress.py are both TRACKABLE, and `git check-ignore -v backend/tests` exits 1, so the parent directory is not excluded and re-inclusion is legal.

What an attacker achieves.

The owner writes backend/test_no_egress.py or a root tests/test_egress.py, runs it locally, sees it pass, commits, and the file is never added. The proof of localness exists only on one laptop, is absent from the repo and from any future CI, and its absence is invisible because git add reports nothing.

Fix.

Put every Python test under backend/tests/ (create backend/tests/**init**.py and backend/tests/conftest.py, both confirmed trackable) and do not create a root tests/ directory. Confirmed trackable by `git check-ignore` returning nothing for: backend/tests/**init**.py, backend/tests/conftest.py, backend/tests/test_no_egress.py, backend/tests/egress/conftest.py, backend/tests/egress/test_no_egress.py, scripts/egress_capture.sh, scripts/egress-allow [...]

Verification: 1 adversarial verifier, 0 refuted.

### SR-41: No test runner exists on either side and no CI: pytest is pinned but unconfigured, and `npm test` invokes a jest that is not a dependency

- Severity: medium
- Where: package.json:17
- Difficulty for an attacker: easy
- Category: test-infrastructure
- Status: Fixed in the backend rewrite (2026-09-03): pytest suite in backend/tests and .github/workflows/ci.yml with no continue-on-error; the frontend jobs land with Phase 5.

What it is.

There is nothing to hang the test on. A find for test_*.py, *_test.py, _.test.ts_, _.spec.ts_, conftest.py, pytest.ini and tox.ini across the repo excluding node_modules returns zero results, and .github does not exist, so there is no CI to keep the test honest. On the Python side pytest==7.4.3, pytest-asyncio==0.21.1 and pytest-cov==4.1.0 are pinned at backend/requirements.txt:56-58, but no pyproject.toml, setup.cfg or pytest.ini exists at the repo root or under backend/, so pytest-asyncio 0.21.1 runs in its default strict mode and every async test silently needs an explicit @pytest.mark.asyn [...]

What an attacker achieves.

An async egress test written without the marker is collected, skipped, and reported as a pass, so it certifies localness while never having executed a single request. On the JS side there is no route at all to test the frontend legs.

Fix.

Add backend/pytest.ini (or a [tool.pytest.ini_options] block) setting `asyncio_mode = auto`, `testpaths = tests` and a `no_egress` marker, so async tests cannot silently skip. Add backend/tests/**init**.py and backend/tests/conftest.py. Add .github/workflows/egress.yml running the pytest suite (all paths confirmed trackable).

Verification: 1 adversarial verifier, 0 refuted.

### SR-42: The proposed network-namespace capture does not exist on this host: macOS has no netns, and the Docker fallback has no Dockerfile to build

- Severity: medium
- Where: package.json:35
- Difficulty for an attacker: moderate
- Category: test-design
- Status: Fixed in the backend rewrite (2026-09-03): socket-level guard around the whole-review tests and Dockerfile.local with --network none.

What it is.

The suggested capture mechanism of 'an interposed proxy in a network namespace' is not available. The host is Darwin 25.6.0 arm64, which has no Linux network namespaces; `command -v unshare` returns absent, as do podman and colima. Available instead: /sbin/pfctl (present, but a deny-all anchor needs sudo and will not be runnable from CI or an unattended test), /usr/local/bin/docker (present, daemon state unverified).

What an attacker achieves.

The egress test design stalls, or falls back to the in-process patch it was meant to replace, because every out-of-process option named in the plan needs infrastructure that is not in the repo. Alternatively someone runs `npm run docker:up`, gets a bare 'no configuration file' error, and concludes the containerisation exists but is broken.

Fix.

Pick a two-tier mechanism and be explicit about what each tier proves. Tier 1 (runs everywhere, including CI, proves 'the interpreter opened no non-loopback socket'): the conftest autouse socket.connect/getaddrinfo guard described above.

Verification: 1 adversarial verifier, 0 refuted.

### SR-43: Issues: Write is granted in the documented manifest but no code path touches the Issues API

- Severity: medium
- Where: backend/README.md:173
- Difficulty for an attacker: moderate
- Category: excess-permission
- Status: Fixed in the backend rewrite (2026-09-03): backend/README.md lists Pull requests and Metadata only.

What it is.

backend/README.md:173 instructs the operator to grant 'Issues: Write'. Nothing in the backend creates an issue or an issue comment: the only path containing the string 'issues' is the read-only search at backend/services/github_client.py:541 (GET /search/issues), and inline review comments go to the pull request comments endpoint at :242, which is covered by Pull requests: write. Contents: Read at backend/README.md:172 is similarly unearned, since the only consumer, get_file_content at backend/services/github_client.py:387-411, has no caller anywhere in the repository.

What an attacker achieves.

Widens the blast radius of the App's private key and of any leaked installation token. With Issues: Write on every installed repository, an attacker who obtains the key (or who reaches the unauthenticated review endpoints and pivots) can open and edit issues and issue comments across the whole installation, which is a plausible route to phishing re [...]

Fix.

Remove 'Issues: Write' and 'Contents: Read' from backend/README.md:172-173. Reinstate Contents: Read only if and when get_file_content gains a caller.

Verification: 1 adversarial verifier, 0 refuted.

### SR-44: Installation access token is used against user-only endpoints, so /github/repositories and /github/pulls/search always fail

- Severity: medium
- Where: backend/services/github_client.py:434
- Difficulty for an attacker: trivial
- Category: app-vs-pat
- Status: Fixed in the backend rewrite (2026-09-03): those routes no longer exist.

What it is.

GitHubClient always authenticates as a GitHub App installation: the constructor takes an installation_id (backend/services/github_client.py:65-78) and _get_access_token mints an installation access token (:80-107) that _make_request sends as `Authorization: token ...` (:126). But get_user_repositories at :434-438 calls `github.get_user()` then `user.get_repos()`, that is GET /user and GET /user/repos, and search_user_pulls at :530-532 calls `github.get_user()` to read `user.login`. Installation tokens cannot call user endpoints. The App-correct call is GET /installation/repositories.

What an attacker achieves.

Two documented API routes are dead on arrival for every caller: GET /github/repositories (backend/handlers/github.py:87) and GET /github/pulls/search (backend/handlers/github.py:175) will 403 with 'Resource not accessible by integration', which the handlers swallow into a generic 500 'Failed to fetch repositories' (backend/handlers/github.py:102-10 [...]

Fix.

Replace get_user_repositories with GET /installation/repositories through _make_request, and drop or rewrite search_user_pulls so it does not need a login name from GET /user (search per installed repository, or take the login from the caller).

Verification: 1 adversarial verifier, 0 refuted.

### SR-45: Frontend OAuth requests only user:email,read:user, yet the same token is used to read repository and PR data

- Severity: medium
- Where: app/api/auth/github/route.ts:20
- Difficulty for an attacker: trivial
- Category: token-scope
- Status: Fixed in the frontend rebuild (2026-09-03): no GitHub OAuth in the dashboard; it reads only the local backend with LOCAL_API_TOKEN from the server environment.

What it is.

The OAuth authorise URL requests `scope=user:email,read:user`, which grants no repository access at all. The token that comes back is stored in the auth_token cookie and then used verbatim as a bearer token against repository endpoints: GET /repos/{repository}/pulls at app/api/github/prs/route.ts:73, GET /repos/{repository}/pulls/{prNumber} at app/api/github/prs/route.ts:248 and at app/api/review/pr/route.ts:57, plus the author search at app/api/github/prs/route.ts:63.

What an attacker achieves.

Every private repository is invisible and unreviewable through the frontend. GitHub answers 404 (not 403) for a private repo read with an unscoped token, so app/api/review/pr/route.ts:65-67 throws `Failed to fetch PR details: Not Found` and the user is shown a generic failure, while app/api/github/prs/route.ts:88-101 surfaces 'GitHub API error: Not [...]

Fix.

Decide one identity model and document it. Either keep read:user for identity and fetch all PR data server-side through the GitHub App installation token (preferred, since the App is already the thing with Commit statuses write), or, if the frontend must read repositories directly, request the narrowest repository scope that works and say so in the README.

Verification: 1 adversarial verifier, 0 refuted.

### SR-46: backend/README.md tells the reader to run ./setup.sh as install step 2, but that file was deleted and does not exist

- Severity: medium
- Where: backend/README.md:47
- Difficulty for an attacker: trivial
- Category: documentation / broken-setup-path
- Status: Fixed in the backend rewrite (2026-09-03): backend/README.md rewritten.

What it is.

backend/README.md:47-51 presents the primary install route as '2. Run the automated setup script: `bash ./setup.sh `', with the manual venv steps offered only as an alternative ('Or manually create virtual environment', :53). backend/setup.sh does not exist anywhere in the working tree, and a repo-wide find for any setup.sh returns nothing. It was deleted by commit 0579209 in the same 'portfolio presentation' cleanup that removed the Dockerfiles and the test suite. A reader following the README in order hits 'no such file or directory' on the very first command they are told to run.

What an attacker achieves.

Murphy achieves an immediate dead end for anyone, the owner included, following the documented backend setup, compounding the two install failures above. The reader has to notice the fallback branch at :53 before they can even reach the pip step that then fails for the two reasons already listed.

Fix.

Delete the ./setup.sh step from backend/README.md:47-51 and promote the manual venv block to step 2, with the interpreter spelled out ('python3.11 -m venv .venv'). Also correct backend/README.md:33 and README.md:58, which both claim 'Python 3.11+': the pinned set does not install on 3.14, so the accurate statement is a bounded range such as 'Python 3.11 to 3.13'.

Verification: 1 adversarial verifier, 0 refuted.

### SR-47: No CI, no lockfile and no dependabot config, so an automated dependency bump broke the install and nothing noticed for ten months

- Severity: medium
- Where: backend/requirements.txt:1
- Difficulty for an attacker: trivial
- Category: supply-chain / process
- Status: Fixed in the backend rewrite (2026-09-03): .github/workflows/ci.yml and .github/dependabot.yml added; exact pins in requirements.txt.

What it is.

The repository has no .github directory at all, so there is no workflow that installs the Python dependencies, and no .github/dependabot.yml, meaning the bump in 223268d came from GitHub's default security-update behaviour rather than a configured, grouped update the owner reviewed. There is no lockfile of any kind (no requirements.lock, no poetry.lock, no uv.lock, no pyproject.toml) so the loose transitive deps float: uvicorn[standard]==0.24.0 at requirements.txt:3 pulls uvloop, httptools, watchfiles and websockets with no upper bound, and aiopg==1.4.0 at :35 pulls psycopg2-binary>=2.9.5 with [...]

What an attacker achieves.

Murphy achieves a repository where dependency state is only validated by a human running an install by hand, which has evidently not happened since the bump. Any future dependabot PR can land the same class of break, and the floating transitive set means two installs on different days can produce different runtime versions with no record of which o [...]

Fix.

Add a single GitHub Actions workflow that runs 'pip install -r backend/requirements.txt' (or at minimum 'pip install --dry-run -r backend/requirements.txt') on the pinned interpreter for every push and PR, so a resolver conflict blocks the merge. Add .github/dependabot.yml so pip updates are grouped and land as reviewable PRs.

Verification: 1 adversarial verifier, 0 refuted.

### SR-48: The default LangGraph file filter admits .env, id_rsa, .pem, .tfvars and .npmrc into the review; the fallback filter admits credentials.json and Kubernetes secret YAML

- Severity: medium
- Where: backend/services/review_workflow.py:628
- Difficulty for an attacker: trivial
- Category: data-exposure
- Status: Fixed in the backend rewrite (2026-09-03): services/redaction.is_excluded_path skips secret-bearing files, and the review says so (test_redaction, test_runner).

What it is.

There are two different _should_review_file implementations and neither is a secret filter. The LangGraph one (the default, since AIReviewer is constructed with use_langgraph=True) excludes only .md/.txt/.json/.yml/.yaml, removed files and diffs over 1000 changes, so every credential file without one of those five extensions passes.

What an attacker achieves.

A PR that adds or edits .env, .env.local, id_rsa, deploy_key.pem, terraform.tfvars or .npmrc is reviewed on the default path with its full contents in the chain input. If the LangGraph workflow throws for any reason, the fallback path picks up credentials.json (a GCP service-account key) and k8s/secret.yaml instead.

Fix.

Replace both filters with one shared function that carries an explicit credential denylist matched on the full path and basename, not on Path.suffix: .env*, *.pem, *.key, _.p12, *.pfx, id_rsa*, id_ed25519_, .npmrc, .netrc, *.tfvars, _credentials_, _service-account_.json, *.jks. Files on that list should be reported as 'a credential file was changed' without their contents ever entering a prompt.

Verification: 1 adversarial verifier, 0 refuted.

### SR-49: Wiring the dead SecurityScanner in as-is would add a third echo path rather than close one: _scan_line reports the matched text and the raw source line unmasked

- Severity: medium
- Where: backend/services/security_scanner.py:340
- Difficulty for an attacker: easy
- Category: data-exposure
- Status: Fixed in the backend rewrite (2026-09-03): the scanner is replaced by redaction that never echoes the match.

What it is.

The dead scanner has two output paths and only one of them masks. _scan_secrets (:354-388) builds its code_snippet through _mask_secret, but _scan_line (:317-351) sets `message=f"{rule.description}\n\nDetected pattern: {match.group(0)}"` and `code_snippet=line_content.strip()` with no masking at all, and the hardcoded_secret_1 rule it runs matches the generic assignment form `(password|pwd|secret|key|token) = "..."`. Those ReviewIssue fields feed the same comment and database sinks as the model output.

What an attacker achieves.

An operator who reads this code as the ready-made fix for the redaction gap enables it and creates a new, deterministic leak: every generic secret assignment in a diff is quoted verbatim into a public PR comment by the rule path, with no dependency on model behaviour.

Fix.

Do not reuse SecurityScanner as the redactor. Extract only the pattern table into a standalone redact(text) helper that returns text with every match replaced by a type label, then use that helper on both the pre-flight (patch to prompt) and post-flight (model text to comment/database) legs. If SecurityScanner is ever enabled as a detector, mask at :340 and :343 first.

Verification: 1 adversarial verifier, 0 refuted.

### SR-50: app/api/review/route.ts is 273 lines of unreachable code that still ships as a live, unauthenticated endpoint driving gpt-4o on arbitrary input

- Severity: medium
- Where: app/api/review/route.ts:226
- Difficulty for an attacker: easy
- Category: dead-code-attack-surface
- Status: Fixed in the frontend rebuild (2026-09-03): app/api/** deleted.

What it is.

Nothing in the application calls POST /api/review. A grep for 'api/review' across ts, tsx, js, py, md and json outside node_modules returns exactly three hits: vercel.json:84 (a functions memory config), app/api/review/route.ts:269 (the route's own self-describing GET), and hooks/useReviewService.ts:45 which targets the sibling /api/review/pr. app/review/page.tsx is 35 lines and contains no fetch at all. The route nonetheless exists as a file under app/api, so Next.js deploys it.

What an attacker achieves.

Anyone who can reach the tunnel gets an unmetered gpt-4o completion service billed to the project's OPENAI_API_KEY, plus one database row per request, by POSTing {"code":"..."} to /api/review. No credential required.

Fix.

Delete app/api/review/route.ts. If the paste-a-snippet feature is ever built out, rebuild it against the single surviving contract rather than reviving this one, and give it an auth check and a body size cap.

Verification: 1 adversarial verifier, 0 refuted.

### SR-51: Six of the fourteen fields transformBackendResult reads do not exist on the default LangGraph response, so the transform silently emits placeholder data

- Severity: medium
- Where: app/api/review/route.ts:113
- Difficulty for an attacker: trivial
- Category: contract-drift
- Status: Fixed in the frontend rebuild (2026-09-03): deleted with the route.

What it is.

app/api/review/route.ts:104-122 builds its result from backendResult.letter_grade, .scoring_breakdown, .code_suggestions, .priority_fixes, .quick_wins and .ai_metrics. AIReviewer is constructed with use_langgraph=True by default, so review_pr_files returns workflow_results straight from ReviewWorkflow._format_review_results (backend/services/ai_reviewer.py:929-953). That function enumerates its output exhaustively at backend/services/review_workflow.py:943-975 and emits none of those six keys; grep counts each of the six strings zero times anywhere in review_workflow.py.

What an attacker achieves.

No attacker needed. Any consumer of this route is fed a fabricated grade of B+ and empty suggestion lists that look like genuine 'no issues found' results, which is worse than an error because it is indistinguishable from a clean review.

Fix.

Delete the transform along with the route (see the dead-code finding). If any transform survives, define the backend response as a single Pydantic model used by both the LangGraph and basic-chain paths, generate the TypeScript type from it, and drop every `|| <placeholder>` so a missing field is a visible failure rather than an invented grade.

Verification: 1 adversarial verifier, 0 refuted.

### SR-52: The webhook proxy exists solely to keep the ngrok tunnel on port 3000, which publishes the entire cookie-auth frontend to receive a webhook

- Severity: medium
- Where: app/api/webhook/github/route.ts:3
- Difficulty for an attacker: moderate
- Category: architecture
- Status: Fixed in the frontend rebuild (2026-09-03): the proxy is gone; the tunnel or reverse proxy points at the backend's webhook route.

What it is.

The route's own docstring states the rationale: GitHub needs a public URL, ngrok provides one for the Next.js frontend (app/api/webhook/github/route.ts:3-9), and package.json:9 confirms the tunnel is `ngrok http 3000`. Everything the proxy does between receiving and forwarding is a no-op: copy every header into a plain object (route.ts:17-20), read the body as text (route.ts:23), POST both to the backend (route.ts:26-33), and return the backend body verbatim (route.ts:36-43). The signature is verified downstream against the raw bytes, so the hop adds no security.

What an attacker achieves.

Anyone who discovers the ngrok URL reaches the full frontend API surface rather than only the signature-verified webhook receiver. The proxy is what forces that choice of port.

Fix.

Delete app/api/webhook/github/route.ts, change dev:tunnel to `ngrok http 8000`, and set the GitHub App webhook URL to the tunnel host plus /webhook/github. Nothing else references the route.

Verification: 1 adversarial verifier, 0 refuted.

### SR-53: The webhook proxy reads NEXT_PUBLIC_BACKEND_URL, which .env.example never documents and which the three sibling proxies do not use

- Severity: medium
- Where: app/api/webhook/github/route.ts:14
- Difficulty for an attacker: easy
- Category: config
- Status: Fixed in the frontend rebuild (2026-09-03): deleted with the proxy; the root .env.example holds only BACKEND_URL and LOCAL_API_TOKEN.

What it is.

Four Next.js routes reach the Python backend and they do not agree on how to find it. app/api/github/stats/route.ts:3, app/api/review/route.ts:16 and app/api/review/pr/route.ts:4 all read process.env.BACKEND_URL, which .env.example documents at line 45. app/api/webhook/github/route.ts:14 alone reads process.env.NEXT_PUBLIC_BACKEND_URL, which appears nowhere in .env.example. Anyone who follows the documented setup gets a webhook proxy hard-wired to http://localhost:8000 with no warning.

What an attacker achieves.

A misconfigured or silently defaulted backend URL sends webhooks nowhere on any host where the backend is not on localhost:8000, and a correctly configured one leaks the backend's address into the public client bundle.

Fix.

Delete the webhook proxy, which removes the only server-side use. Keep a single documented NEXT_PUBLIC_BACKEND_URL for the two client components and add it to .env.example, or better, route the dashboard and history fetches through the server so no backend address reaches the browser at all and only BACKEND_URL survives.

Verification: 1 adversarial verifier, 0 refuted.

### SR-54: backend/handlers/auth.py and backend/handlers/github.py are unreachable from the shipped UI, so the auth duplication has already been decided in Next's favour

- Severity: medium
- Where: backend/handlers/auth.py:112
- Difficulty for an attacker: easy
- Category: dead-code
- Status: Fixed in the backend rewrite (2026-09-03): handlers/auth.py and handlers/github.py deleted.

What it is.

The Next.js layer implements OAuth itself (app/api/auth/github/route.ts, app/api/auth/github/callback/route.ts) and calls api.github.com directly for PR data (app/api/github/prs/route.ts:83, :250). It never calls the backend's equivalents. The only backend paths any frontend code touches are /review/stats/overview (app/api/github/stats/route.ts:12), /review/pr (app/api/review/pr/route.ts:75), /review/code (app/api/review/route.ts:18), /review/history (app/history/page.tsx:125) and /review/metrics/user/current (app/dashboard/page.tsx:117).

What an attacker achieves.

Thirteen unreferenced HTTP endpoints stay mounted and reachable on the backend, among them credential-issuing routes that no reviewer has reason to look at because no product feature depends on them.

Fix.

Delete backend/handlers/auth.py and backend/handlers/github.py and their include_router calls at backend/main.py:296-305. Keep the Next.js OAuth flow as the single auth implementation. If the backend later needs to know who is calling, add one dependency that verifies the Next-issued session rather than reviving a second login system.

Verification: 1 adversarial verifier, 0 refuted.

### SR-55: scripts/validate-env.js demands the GitHub App private key and the OpenAI key in the frontend .env.local, where no frontend code reads them

- Severity: medium
- Where: scripts/validate-env.js:186
- Difficulty for an attacker: easy
- Category: config
- Status: Fixed in the backend rewrite (2026-09-03): scripts/validate-env.js removed.

What it is.

The validator loads .env.local from the repo root as frontendEnv (scripts/validate-env.js:141, :166) and marks OPENAI_API_KEY, GITHUB_APP_ID, GITHUB_PRIVATE_KEY and GITHUB_WEBHOOK_SECRET as required=true in that file (:186-216), then separately checks the same secrets in backend/.env (:242-251). A grep for GITHUB_APP_ID, GITHUB_PRIVATE_KEY and GITHUB_WEBHOOK_SECRET across app, components, hooks, lib and contexts returns nothing: the only GitHub env vars the frontend reads are GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET (app/api/auth/github/route.ts:5, app/api/auth/github/callback/route.ts:42-43) [...]

What an attacker achieves.

A second copy of the GitHub App private key and the OpenAI key sits in a file that nothing reads, so it will never be noticed as stale and never rotated with the one that matters.

Fix.

Once the layer is collapsed to one host, keep one .env. Reduce the frontend requirements in validate-env.js to GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET and the app URL, and leave GITHUB_APP_ID, GITHUB_PRIVATE_KEY, GITHUB_WEBHOOK_SECRET and OPENAI_API_KEY as backend-only.

Verification: 1 adversarial verifier, 0 refuted.

### SR-56: The auth_token cookie is an unsigned base64 envelope wrapping a live GitHub OAuth token, so it must be kept but cannot stay in this form

- Severity: medium
- Where: app/api/auth/github/callback/route.ts:105
- Difficulty for an attacker: moderate
- Category: auth
- Status: Fixed in the frontend rebuild (2026-09-03): no cookie session; nothing about the user is stored in the browser except the theme choice.

What it is.

Answering whether the cookie can be dropped on a single local host: no. It is the only real credential in the system, because it carries the user's GitHub OAuth access token (callback/route.ts:101) which three routes use to call api.github.com on the user's behalf (app/api/github/prs/route.ts:85 and :252, app/api/review/pr/route.ts:60). httpOnly is therefore mandatory and correct. But the encoding is not a token: it is Buffer.from(JSON.stringify(userInfo)).toString('base64') with no signature, no MAC and no expiry claim inside it (callback/route.ts:105).

What an attacker achieves.

Anyone who can set a cookie on the origin, including via any XSS or a shared browser profile, can mint an arbitrary identity by base64-encoding their own JSON; the identity fields shown by /api/auth/me are entirely attacker-chosen.

Fix.

Keep the OAuth flow and the httpOnly cookie, they are the parts that work. Replace the base64 envelope with either a signed session (iron-session or a real JWT signed with a secret) or, better on a single local host, a server-side session store keyed by an opaque random cookie so the GitHub token never leaves the server's memory or disk. Add an expiry claim the server checks on every decode.

Verification: 1 adversarial verifier, 0 refuted.

## Low and informational findings

Full evidence for these is in the review transcript; each is stated here with its impact and fix.

### SR-57: Webhook handler converts every failure into HTTP 200 echoing str(e); ping, unlisted events and unlisted PR actions raise before dispatch (and a non-ASCII signature header reaches the same path unauthenticated)

- Severity: low
- Where: backend/handlers/webhook.py:178
- Difficulty for an attacker: trivial
- Category: webhook-auth
- Status: Fixed in the backend rewrite (2026-09-03): missing headers 400, bad signature 401, bad JSON 400, schema mismatch 400, ping 200, unknown event 200 ignored, and unhandled errors are a generic 500 (test_webhook).

What it is.

github_webhook's blanket 'except Exception' (backend/handlers/webhook.py:178-193) returns WebhookResponse with default 200 and message f'Webhook processing failed: {str(e)}' (:189). Paths into it: GitHubEventType(event_type) at :124 raises ValueError for any event outside the six-member enum (backend/models/github.py:9-16), including GitHub's ping, installation, check_suite, so the 'Unhandled event type' branch (:149-154) is only reachable for issues/issue_comment; PRWebhookPayload (models/github.py:103-110) requires action: PRAction (:19-27, seven values) and installation (:109), so labeled, [...]

What an attacker achieves.

An unauthenticated sender fingerprints a Python service using hmac string comparison and sees exact exception text; a signed or replayed sender sees pydantic, GitHub client, OpenAI and database error strings. Operationally, misconfigured hooks (ping errors, unsupported actions) look successful and real failures never surface as failed deliveries.

Fix.

In verify_github_signature validate with ^sha256=[0-9a-f]{64}$ and compare bytes via bytes.fromhex/hmac digest, returning False on parse failure. Handle ping explicitly (200 with zen), dispatch on the raw event string and return 200/202 'ignored' for unknown events without constructing the enum, make PRWebhookPayload.action a plain str or extend PRAction and ignore actions outside the trigger set, return 400 for ValidationError and 500/422 for un [...]

Verification: 1 adversarial verifier, 0 refuted.

### SR-58: Expected HMAC prefix (40 bits) for an attacker-chosen body is written to logs on every failed webhook signature verification

- Severity: low
- Where: backend/utils/crypto.py:54
- Difficulty for an attacker: moderate
- Category: webhook-auth
- Status: Fixed in the backend rewrite (2026-09-03): the failure log records the event name and body size only.

What it is.

On mismatch verify_github_signature logs the first 10 hex characters of HMAC-SHA256(GITHUB_WEBHOOK_SECRET, submitted body) plus the first 10 of the supplied value at WARNING (backend/utils/crypto.py:50-55). The endpoint accepts unauthenticated POSTs (backend/handlers/webhook.py:37-71, :76-91), so the body is attacker-chosen. Logs are stdout JSON in production (backend/config/logging.py:35-36), shipped to the platform, and become Sentry breadcrumbs when SENTRY_DSN is set (backend/main.py:28-37).

What an attacker achieves.

A log reader (platform dashboard, Sentry, a teammate, shared aggregation) can verify guessed secrets offline against a known body with 2^-40 false-positive rate; real forgery still needs 216 more bits, so impact is limited to weak, dictionary or placeholder secrets such as 'your-webhook-secret' in backend/.env.example, after which they can forge we [...]

Fix.

Remove expected_signature (and the provided value, or log only its length) from the log line; log a boolean outcome, delivery id and payload size. Keep the constant-time compare.

Verification: 1 adversarial verifier, 0 refuted.

### SR-59: Prompt injection posture (latent until templating is fixed): raw diff and filename enter the prompt with no delimiting or data-only instruction, and model text goes verbatim into GitHub comments and status decisions with no validation or limits

- Severity: low (reported as high, adjusted by verification)
- Where: backend/services/ai_reviewer.py:337
- Difficulty for an attacker: easy
- Category: llm-pipeline
- Status: Fixed in the backend rewrite (2026-09-03): PR content enters only inside the data block with delimiters defanged, output is schema-constrained, findings are checked against the diff, and the renderer sanitises (test_review_generation).

What it is.

The intended prompt shape 'File: {filename}\nLanguage: {language}\nCode to analyze:\n{code_diff}' (ai_reviewer.py:337-340, 404-407, 496-499, 661-664, 712-715, 767-770) has no fence, boundary or untrusted-data instruction; chain_input comes from file.filename and file.patch (ai_reviewer.py:1078-1082; review_workflow.py:275-279, 314-318, 343-347, 376-380, 404-408, 436-440), both PR-author controlled. PR title/body are fetched (queue_processor.py:371-372) and stored (review_workflow.py:60-61, 886-887) but unused; head ref only reaches helpers.py:165.

What an attacker achieves.

Once templating works, a PR author (or anyone with /review/code access) can put instructions in a diff comment or string literal that make the bot post attacker-authored markdown (phishing links, images, @mentions) as inline comments from the app account, suppress real findings for a passing status, or inflate severity to fail others' PRs.

Fix.

Wrap the diff in a labelled fenced block with a random delimiter and a system instruction that its contents are data that may contain adversarial instructions; validate output against the existing Pydantic finding models (severity enum, positive int line_number, description/recommendation caps around 1,000 chars) and drop failures; strip or neutralise links, images, raw HTML and @mentions before posting and cap comments per file; never let model [...]

Verification: 3 adversarial verifiers, 0 refuted.

### SR-60: _parse_json_result and downstream code never validate model output shape: non-JSON becomes a clean review, scalar JSON crashes the task or workflow, severity casing and string line numbers are mishandled

- Severity: low (reported as medium, adjusted by verification)
- Where: backend/services/ai_reviewer.py:1217
- Difficulty for an attacker: easy
- Category: llm-pipeline
- Status: Fixed in the backend rewrite (2026-09-03): parse_file_review is lenient and validated; scalars and prose yield no findings (test_review_generation).

What it is.

_parse_json_result (ai_reviewer.py:1217-1243) strips only a leading '`json' and trailing '`' (:1222-1225); any other fence or prose raises JSONDecodeError and returns [] (:1237-1240), indistinguishable from 'no issues'; a scalar is wrapped as [scalar] (:1232-1233). queue_processor.py:382 'if issue.get("line_number")' sits outside the try starting at :383, so a non-dict finding raises AttributeError into the 4x retry loop (:318-327); review_workflow.py:730 has no try, so the synthesize node raises, LangGraph aborts and ai_reviewer.py:955-957 falls back to re-running 6 calls per file plus sc [...]

What an attacker achieves.

Any formatting drift becomes a silent all-clear or a task failure that re-runs the whole review; upper-case severities bypass the critical gate. An attacker steering output (see prompt injection) can emit a non-dict to crash the review or 'CRITICAL' to avoid the failure status while looking severe.

Fix.

Parse with a tolerant fence stripper (regex for ```[a-z]*), validate each finding with the existing Pydantic models with severity normalised to lower case and line_number coerced to Optional[int] > 0, discard invalid entries and count them; distinguish 'parse failed' from 'no findings' so a failed parse cannot yield a green status; map diff-relative lines to new-file lines using hunk headers (helpers.parse_git_diff / security_scanner.scan_diff al [...]

Verification: 2 adversarial verifiers, 0 refuted.

### SR-61: Dead and misleading code in the summary/scoring path: file 'content' never exists, PR-level lists are never aggregated, the 'AI summary' is a template, and LangGraph metadata and footer overstate what ran

- Severity: low
- Where: backend/services/ai_reviewer.py:1256
- Difficulty for an attacker: trivial
- Category: llm-pipeline
- Status: Fixed in the backend rewrite (2026-09-03): the code is gone; the summary is a template and the footer says the findings are model output.

What it is.

_generate_overall_summary builds code_diff from file.get('content', '')[:1000] (ai_reviewer.py:1256-1257) but file_result dicts never carry 'content' (:1059-1074); it serialises documentation/testing/architecture lists (:1253-1255) that the basic path never aggregates at PR level (:1002-1004). review_workflow._generate_ai_summary (:748-769) is an f-string with a comment 'This would call an AI model'; the footer claims LangGraph orchestration (:863) and workflow_metadata lists nodes that do not exist (:968-973 versus :133-145).

What an attacker achieves.

Operators and users are shown a fabricated AI summary, processing time and node list; maintainers reason about behaviour that does not exist.

Fix.

Delete unused chains and pattern tables or wire them in; make _generate_ai_summary a real model call or label it a template; derive workflow_metadata from the graph; add start_time to the state schema; pass real per-file diffs (or drop code_diff) in the scoring prompt.

Verification: 1 adversarial verifier, 0 refuted.

### SR-62: OpenAPI schema is served at /openapi.json even though /docs and /redoc are DEBUG-gated

- Severity: low
- Where: backend/main.py:64
- Difficulty for an attacker: trivial
- Category: authz-endpoints
- Status: Fixed in the backend rewrite (2026-09-03): openapi_url follows DEBUG (test_api).

What it is.

main.py:58-66 sets docs_url and redoc_url to None when DEBUG is False but leaves openapi_url at FastAPI 0.104.1's default '/openapi.json' (requirements.txt:2); setup() registers that route whenever openapi_url is truthy. The schema lists every route including DEBUG-only POST /auth/dev/create-user and POST /webhook/github/test, query parameter names (installation_id, username, password) and response models.

What an attacker achieves.

A machine-readable map of the whole backend attack surface, including dev-only endpoints to try if DEBUG is ever enabled.

Fix.

Pass openapi_url='/openapi.json' if settings.DEBUG else None.

Verification: 1 adversarial verifier, 0 refuted.

### SR-63: Internal exception text is returned to unauthenticated clients from 16 review handlers, the auth handler, health endpoints and /status regardless of DEBUG

- Severity: low
- Where: backend/handlers/review.py:78
- Difficulty for an attacker: trivial
- Category: data-logging
- Status: Fixed in the backend rewrite (2026-09-03): handlers return fixed messages; the global handler returns a generic body.

What it is.

The global handler hides exception text unless DEBUG (backend/main.py:144-159) but review.py raises HTTPException(status_code=500, detail=str(e)) at :78, 126, 192, 264, 337, 385, 493, 590, 694, 716, 892, 909, 926, 943, 960 and f'Review failed: {str(e)}' at :876, and auth.py:368 does the same. GET /health/detailed returns str(e) for database, GitHub and AI checks (main.py:195-198, 208-211, 221-224) after a live OpenAI call, get_ai_health returns error=str(e) plus model name (ai_reviewer.py:1427-1440), and GET /status exposes HOST:PORT, model and credential presence (main.py:263-273).

What an attacker achieves.

An unauthenticated caller learns schema and SQL fragments, dialect, filesystem layout, model and provider details and which upstream keys are valid, guiding further attacks.

Fix.

Log the exception server side and return a fixed message plus a correlation id; let the global handler mask details; gate /health/detailed and /status behind auth or a network allow-list and drop the live OpenAI call from the health check.

Verification: 1 adversarial verifier, 0 refuted.

### SR-64: OAuth authorisation code prefix is written to logs by the mock callback

- Severity: low
- Where: backend/handlers/auth.py:132
- Difficulty for an attacker: hard
- Category: data-logging
- Status: Fixed in the backend rewrite (2026-09-03): the mock callback is gone.

What it is.

github_oauth_callback logs code=code[:10] + '...' at INFO (backend/handlers/auth.py:132); GitHub codes are 20 hex characters so half is logged, and the full code is already in the URL logger (main.py:98) because code is a query parameter (:113-115). The endpoint is a mock that never exchanges the code (:124-147).

What an attacker achieves.

Log readers see partial or full OAuth codes; no practical gain with the current mock, but a live single-use code would leak if the real exchange were implemented here.

Fix.

Do not log any part of the code; log only that a callback arrived and a hash of the state.

Verification: 1 adversarial verifier, 0 refuted.

### SR-65: fastapi 0.104.1 hard-pins starlette 0.27.0, a line with 7 open advisories that cannot be fixed without bumping FastAPI

- Severity: low (reported as medium, adjusted by verification)
- Where: backend/requirements.txt:2
- Difficulty for an attacker: moderate
- Category: deps-history-scripts
- Status: Fixed in the backend rewrite (2026-09-03): fastapi 0.141.1 with starlette 1.6.

What it is.

backend/requirements.txt:2 pins fastapi==0.104.1 (Nov 2023), which requires starlette<0.28.0,>=0.27.0. OSV for starlette 0.27.0: CVE-2024-47874 GHSA-f96h-pmfr-66vw multipart DoS HIGH (fixed 0.40.0), CVE-2025-54121 GHSA-2c2j-9gv5-cj73, CVE-2026-54283 GHSA-82w8-qh3p-5jfq HIGH, CVE-2026-48710 GHSA-86qp-5c8j-p5mr Host header poisons request.url.path, CVE-2026-54282 GHSA-jp82-jpqv-5vv3, CVE-2026-48818 GHSA-wqp7-x3pw-xc5r HIGH, CVE-2026-48817 GHSA-x746-7m8f-x49c. fastapi's own PYSEC-2024-38 / CVE-2024-24762 is mitigated by python-multipart 0.0.18 (requirements.txt:6).

What an attacker achieves.

Nothing today; any future form, upload or static route gets an unauthenticated memory/CPU DoS (CVSS 7.5 class) immediately, and the Host poisoning applies when DEBUG=true.

Fix.

Bump fastapi to a current 0.11x release (starlette >=0.40, ideally 1.x), re-pin pydantic/pydantic-settings compatibly, add a lock (pip-compile or uv), and keep form parsing out of the backend until then.

Verification: 2 adversarial verifiers, 0 refuted.

### SR-66: scripts/quick-setup.sh echoes freshly generated secrets to the terminal and its sed substitution breaks on base64 slashes, aborting half way with placeholders left in place

- Severity: low
- Where: scripts/quick-setup.sh:70
- Difficulty for an attacker: moderate
- Category: deps-history-scripts
- Status: Fixed in the backend rewrite (2026-09-03): scripts/quick-setup.sh removed.

What it is.

quick-setup.sh generates secrets with openssl rand -base64 (:66-67) and prints all three in clear (:70-72), then substitutes them with sed using '/' as delimiter (:78-79, :83-84); base64 contains '/', so roughly half of runs fail with 'unknown option to s' and, under set -e (:6), abort before backend/.env is updated, the .bak cleanup (:88) and npm/pip installs (:90-120).

What an attacker achieves.

Secrets in terminal history and CI logs for anyone with access; developers left with half-configured environments containing template placeholders such as 'dev-secret-key-change-in-production' (settings.py:16).

Fix.

Use openssl rand -hex (no sed metacharacters) or a different sed delimiter with escaping; never echo values; set LANGCHAIN_TRACING_V2=false in the template; drop NEXTAUTH_SECRET unless next-auth is adopted; fix the dangling doc reference.

Verification: 1 adversarial verifier, 0 refuted.

### SR-67: Other stale backend pins carry advisories that no current call site reaches (python-multipart, cryptography, PyJWT, sentry-sdk, python-dotenv, click, requests)

- Severity: low
- Where: backend/requirements.txt:6
- Difficulty for an attacker: hard
- Category: deps-history-scripts
- Status: Fixed in the backend rewrite (2026-09-03): those packages are removed or current.

What it is.

OSV: python-multipart 0.0.18 (:6) 14 advisories (GHSA-wp53-j4wj-2cfg, GHSA-pp6c-gr5w-3c5g HIGH, GHSA-5rvq-cxj2-64vf HIGH, others; fixes up to 0.0.31), not imported and no form routes; cryptography 44.0.1 (:12) 10 advisories (GHSA-537c-gmf6-5ccf HIGH fixed 48.0.1, GHSA-r6ph-v2qm-q3c2, GHSA-g6cj-pr64-35w5, GHSA-jwv3-5hgf-82ww, GHSA-m959-cc7f-wv43), used only for RS256 App JWT signing (github_client.py:75-78, :639); PyJWT 2.8.0 (:14) 11 advisories (GHSA-752w-5fwx-jx9f, GHSA-xgmm-8j9v-c9wx, GHSA-w7vc-732c-9m39; fix 2.13.0), only encode() used; sentry-sdk 1.38.0 (:46) CVE-2024-40647 GHSA-g92j-qhmh- [...]

What an attacker achieves.

Nothing on the current surface; each becomes live when the matching feature is added (uploads, PyJWT decode, subprocess with scrubbed env, dotenv set_key).

Fix.

Bump in one pass: python-multipart >=0.0.31 (or remove), cryptography >=48.0.1, PyJWT >=2.13.0, sentry-sdk >=2.x, python-dotenv >=1.2.2, requests >=2.33.0 or drop, click unpinned; add pip-audit to CI.

Verification: 1 adversarial verifier, 0 refuted.

### SR-68: requirements.txt carries 14 packages nothing imports plus dev tools, with no lock, so every install resolves a different transitive set

- Severity: low
- Where: backend/requirements.txt:29
- Difficulty for an attacker: hard
- Category: deps-history-scripts
- Status: Fixed in the backend rewrite (2026-09-03): 14 exact runtime pins; dev tools in requirements-dev.txt. Transitive versions are not locked.

What it is.

Import grep across the 33 backend .py files shows celery (:35), kombu (:37), aiopg (:32, pulls psycopg2-binary), alembic (:31), aiofiles (:10), requests (:9), python-dateutil (:60), click (:61), python-multipart (:6), python-dotenv (:49), langchain-community (:24, largest transitive tree) and explicit transitive pins openai (:26), tiktoken (:27), langsmith (:30) are never imported; pytest/pytest-asyncio/pytest-cov (:53-55) and black/isort/mypy (:58-60) share the runtime file while no tests exist (backend/tests deleted in 0579209; .gitignore:118-120).

What an attacker achieves.

Larger install-time supply-chain surface with no functional benefit, and non-reproducible builds.

Fix.

Split runtime and dev requirements, delete the unused packages, generate a lock with pip-compile or uv, and run pip-audit against it in CI.

Verification: 1 adversarial verifier, 0 refuted.

### SR-69: package.json scripts point at infrastructure deleted from the repo, and the CI that ran npm audit and pip-audit was deleted with it

- Severity: low
- Where: package.json:22
- Difficulty for an attacker: hard
- Category: deps-history-scripts
- Status: Fixed in the frontend rebuild (2026-09-03): package.json scripts are dev, build, start, lint, typecheck, format and check; the docker and jest scripts are gone.

What it is.

Eleven docker:* scripts (package.json:22-32) invoke docker-compose but no compose or Dockerfile exists (deleted in cf58336 and 0579209); dev:backend (:7) sources a missing backend/.venv; test scripts (:14-16) run jest, which is not installed and has no tests; .github/workflows/ci.yml (deleted in 80903be) ran npm audit and pip-audit and deploy-azure.yml used secrets.AZURE_CREDENTIALS, so nothing audits dependencies now. dev:tunnel (:8) exposes every Next route via ngrok. prepare: husky (:20) and .husky/pre-commit:1 run local lint-staged only.

What an attacker achieves.

No direct exploit; documented workflows fail and advisories accumulate unseen, which is how 45 npm and about 70 PyPI advisories built up.

Fix.

Delete the docker:* and jest scripts or restore what they need; restore a minimal CI running npm audit --audit-level=high, pip-audit, lint and typecheck; merge or close the Dependabot branches.

Verification: 1 adversarial verifier, 0 refuted.

### SR-70: README version claims do not match the pins: Next.js 15 versus 14.2.33, and 'Python 3.11+' although the pinned wheels stop at CPython 3.13

- Severity: low
- Where: README.md:52
- Difficulty for an attacker: hard
- Category: deps-history-scripts
- Status: Fixed in the docs pass (2026-09-03): README.md and backend/README.md rewritten; versions stated are the pinned ones.

What it is.

README.md:52 says Next.js 15 while package.json:45 and package-lock.json:8931-8932 pin 14.2.33; README.md:58 and backend/README.md:33 say Python 3.11+ but pydantic 2.9.2 (pydantic-core 2.23.4) and greenlet 3.1.1 ship wheels only to cp313, so on this host's 3.14.6 pip install needs a Rust toolchain or fails; effective range is 3.11 to 3.13. Historic hints disagree (deleted CI 3.11, deleted setup.sh 3.8, deleted main-simple.py 3.13, commit 6d79b5f). eslint-config-next 14.2.14 (package.json:76) lags next.

What an attacker achieves.

Nothing security-relevant; reviewers misjudge which Next advisories apply and new contributors on 3.14 cannot install the backend.

Fix.

Correct README.md:52 (or upgrade Next), state Python 3.11 to 3.13 or bump pydantic/greenlet, and add .python-version or requires-python.

Verification: 1 adversarial verifier, 0 refuted.

### SR-71: Response models reject what the app stores: GET /review/{id} fails validation for 'direct' reviews and for 'warning'/'architecture' issues

- Severity: low
- Where: backend/handlers/review.py:254
- Difficulty for an attacker: trivial
- Category: gaps-critic-prep
- Status: Fixed in the backend rewrite (2026-09-03): the endpoint and models are gone.

What it is.

get_review_result builds ReviewResultResponse(review=review_dict) (:254) where CodeReview.type is ReviewType (manual, pr_webhook, scheduled; models/review.py:19-23, :99) but review_code_direct stores type='direct' (:748); ReviewIssue requires severity in SeverityLevel (no 'warning', which the quality prompt mandates at ai_reviewer.py:510) and category in IssueCategory (no 'architecture', stored at :830). Pydantic raises inside the handler, caught as a generic 500; ReviewListResponse has the same problem once the datetime bug is fixed.

What an attacker achieves.

No attacker; reading back any review created through the web UI fails.

Fix.

Add DIRECT, WARNING and ARCHITECTURE to the enums (coercing unknown values) or return a permissive response schema for stored rows.

Verification: 1 adversarial verifier, 0 refuted.

### SR-72: Naive and aware datetimes are mixed: /review/stats/user throws on the default SQLite database, the metrics service throws on PostgreSQL, and a PyGithub bump breaks the token cache

- Severity: low
- Where: backend/handlers/review.py:583
- Difficulty for an attacker: trivial
- Category: gaps-critic-prep
- Status: Fixed in the backend rewrite (2026-09-03): the code is gone; all timestamps are timezone-aware.

What it is.

get_user_statistics computes (end_date - r.created_at).days (:583-584) with an aware end_date (utils/helpers.py:362) while SQLite (settings.py:48 default) returns naive values for DateTime(timezone=True) columns (database/models.py:91), raising TypeError to 500. metrics_service.py:96-98 compares DB values with naive datetime.utcnow(), which raises on PostgreSQL (swallowed at :199-205).

What an attacker achieves.

No attacker; statistics endpoints fail depending on the backend and a routine dependency bump breaks GitHub token caching.

Fix.

Replace datetime.utcnow() with datetime.now(timezone.utc) everywhere; normalise DB values with .replace(tzinfo=timezone.utc) when tzinfo is None; store token expiry as an aware datetime.

Verification: 1 adversarial verifier, 0 refuted.

### SR-73: MetricsService reads attributes that do not exist, so every /review/metrics/* endpoint returns an error dict with HTTP 200, and the dashboard fabricates activity with Math.random()

- Severity: low
- Where: backend/services/metrics_service.py:60
- Difficulty for an attacker: trivial
- Category: gaps-critic-prep
- Status: Fixed in the backend rewrite (2026-09-03): metrics_service.py deleted.

What it is.

metrics_service.py:60-89, :104-109, :126-130, :234-250, :297-310, :379-395, :447-449, :464-469 read review.results, absent from the Review model (database/models.py:64-114); get_comparison_metrics calls self.review_repo.get_by_id (:289), which does not exist (get_review_by_id); review_types (:148-152) test values never stored. Every AttributeError is returned as {'error': ...} with 200 (:199-205, :275-280, :351-353).

What an attacker achieves.

No attacker; the analytics surface displays invented numbers as real data.

Fix.

Read from real Review columns (overall_score, total_issues, *_issues_count, metrics JSON); rename to get_review_by_id; return 4xx/5xx on failure; remove random fallbacks and render an empty state.

Verification: 1 adversarial verifier, 0 refuted.

### SR-74: Frontend does not type-check: app/demo imports a FileUpload component that does not exist and app/review passes unknown props, so next build fails

- Severity: low
- Where: app/demo/page.tsx:31
- Difficulty for an attacker: trivial
- Category: gaps-critic-prep
- Status: Fixed in the frontend rebuild (2026-09-03): the demo page and its imports are gone; npm run typecheck and next build pass in CI.

What it is.

app/demo/page.tsx:31-36 imports FileUpload from '@/components/review' but components/review/index.ts:2-5 exports only CodeEditor, PRSelector, ReviewResults and ReviewInterface and no FileUpload exists; app/review/page.tsx:24-30 passes maxFiles and maxFileSize to ReviewInterface whose props are className and onReviewComplete (components/review/ReviewInterface.tsx:36-39). tsconfig.json:6 strict is on and next.config.mjs does not ignore build errors, so next build and 'npm run check' (package.json:20) fail. tsc could not be run (node_modules absent).

What an attacker achieves.

No attacker; the frontend cannot be built or deployed as committed.

Fix.

Remove the FileUpload import and section (or add the component), drop the unknown props, and wire npm run check into CI.

Verification: 1 adversarial verifier, 0 refuted.

### SR-75: Status context default disagrees with the context actually posted, in four places

- Severity: low
- Where: backend/services/github_client.py:328
- Difficulty for an attacker: easy
- Category: config-drift
- Status: Fixed in the backend rewrite (2026-09-03): statuses removed.

What it is.

create_status_check defaults `context: str = "git-review-assistant"` while both real callers pass 'git-review-assistant/review'. The same wrong value is baked into three more places that describe the check to the rest of the system: backend/models/github.py:171, backend/models/review.py:128 and the database column default at backend/database/models.py:107. Branch protection matches required checks by exact context string, so the two names are two different checks.

What an attacker achieves.

An operator who reads the model or the schema to find the context string to require in branch protection will require 'git-review-assistant', a context nothing ever posts, and the branch will block on a check that never appears. Any future caller that omits the context argument silently creates a second, parallel check on the commit.

Fix.

Define the context once as a settings constant and reference it from backend/services/github_client.py:328, backend/handlers/webhook.py:402, backend/services/queue_processor.py:439 and the two model defaults, then document the exact string in backend/README.md next to the branch protection guidance.

Verification: 1 adversarial verifier, 0 refuted.

### SR-76: README tells the operator to install the App on target repositories without recommending selected repositories

- Severity: low
- Where: backend/README.md:183
- Difficulty for an attacker: moderate
- Category: install-scope
- Status: Fixed in the backend rewrite (2026-09-03): backend/README.md says selected repositories, never all.

What it is.

Step 6 of the App setup reads only '6. **Install App** on target repositories', with no instruction to choose 'Only select repositories' over 'All repositories' at install time. Given that the corrected manifest carries Pull requests: Read & Write and Commit statuses: Read & Write, and given that the review endpoints in backend/handlers/review.py carry no auth dependency and backend/handlers/auth.py issues JWTs for any code, an all-repositories installation makes every repository in the account reachable from one under-protected backend.

What an attacker achieves.

Anyone who reaches the backend (or obtains the App private key, which the same README asks the operator to paste into Railway environment variables at backend/README.md:301-309) gets pull request write and commit status write across every repository in the account rather than the one or two the demo actually needs.

Fix.

Change step 6 to 'Install the App on **Only select repositories**, and pick just the repositories you want reviewed', and add a warning that this App can write commit statuses, so it should not be installed account-wide while the backend review endpoints are unauthenticated.

Verification: 1 adversarial verifier, 0 refuted.

### SR-77: aiopg==1.4.0 is pinned and pulls psycopg2-binary but is never imported anywhere in the backend

- Severity: low
- Where: backend/requirements.txt:35
- Difficulty for an attacker: trivial
- Category: unused-dependency
- Status: Fixed in the backend rewrite (2026-09-03): aiopg removed.

What it is.

backend/requirements.txt:35 pins aiopg==1.4.0. A grep for aiopg across every .py file in the repo returns no hits. aiopg's own base requirement is psycopg2-binary>=2.9.5, so the pin drags a compiled PostgreSQL driver into every install for nothing. The configured default database is SQLite (backend/config/settings.py:48 DATABASE_URL defaults to 'sqlite:///./reviews.db') and backend/database/connection.py:31 and :115 rewrite that URL to 'sqlite+aiosqlite:///', so the async driver actually used is aiosqlite (pinned separately at requirements.txt:36), not aiopg.

What an attacker achieves.

Murphy achieves a wider install surface than the code needs: an extra compiled dependency to build or fetch, extra CVE exposure to track, and extra install time, on a project whose install is already the bottleneck.

Fix.

Drop aiopg==1.4.0 from backend/requirements.txt:35. If PostgreSQL support is intended for later, add asyncpg (the driver SQLAlchemy 2.x async actually uses for postgres) at that point rather than aiopg, which is capped at SQLAlchemy 1.4 for its own ORM extra. While there, drop the redundant explicit tiktoken pin at :27 and let langchain-openai select it, which also removes one of the cp314 wheel gaps from finding 2.

Verification: 1 adversarial verifier, 0 refuted.

### SR-78: The secret pattern set misses sk-proj-, github_pat_, OPENSSH/ENCRYPTED PEM headers, inline DB-URL passwords and generic assignments, and _mask_secret leaves most of a fine-grained PAT visible

- Severity: low (reported as medium, adjusted by verification)
- Where: backend/services/security_scanner.py:231
- Difficulty for an attacker: moderate
- Category: insufficient-validation
- Status: Fixed in the backend rewrite (2026-09-03): redaction covers sk-proj-, github_pat_, OPENSSH and ENCRYPTED PEM, URL passwords and generic assignments (test_redaction).

What it is.

Measured against real key shapes, the table at :231-250 covers AKIA, ghp_/gho_/ghu_/ghs_, legacy 48-char sk-, RSA/EC/DSA PEM headers and Stripe. It misses the current OpenAI project-key format sk-proj-_, GitHub fine-grained tokens github_pat__, -----BEGIN OPENSSH PRIVATE KEY----- and -----BEGIN ENCRYPTED PRIVATE KEY-----, postgres://user:pass@host URLs, and generic high-entropy assignments entirely.

What an attacker achieves.

A redactor built naively on this table would pass a sk-proj- OpenAI key, a github_pat_ token, an OpenSSH private key header and a database URL with an inline password straight through to the model, the comment and the database, while producing a false positive on every commit SHA.

Fix.

Rebuild the table from a maintained source (gitleaks rules or GitHub's published token formats) rather than extending this one. Add sk-proj-[A-Za-z0-9_-]{20,}, github_pat_[A-Za-z0-9_]{20,}, -----BEGIN [A-Z ]_PRIVATE KEY-----, [a-z]+://[^:@/\s]+:[^@/\s]+@ for URL credentials, and a generic (?i)(secret|token|passwd|password|api[\_-]?key)\s_[=:]\s*\S{8,}. Drop the bare 40-char catch-all.

Verification: 1 adversarial verifier, 0 refuted.

### SR-79: vercel.json is 93 lines of inert configuration for a deployment the README says does not exist, including the wildcard-with-credentials CORS block and a rewrite nothing references

- Severity: low (reported as medium, adjusted by verification)
- Where: vercel.json:18
- Difficulty for an attacker: moderate
- Category: dead-config
- Status: Fixed in the frontend rebuild (2026-09-03): vercel.json deleted.

What it is.

README.md:21 states 'No live deployment, due to the sensitive nature of project.' Nothing in the repo deploys to Vercel: there is no CI workflow, and next.config.mjs has no headers() function, so none of the vercel.json headers apply under next dev or next start. Every clause is therefore dead: the CORS block granting Access-Control-Allow-Origin * together with Access-Control-Allow-Credentials true on /api/(._) (:18-25), the rewrite /api/backend/:path_ to /api/:path* whose source string appears nowhere else in the repo, the three env aliases (:69-73) referencing Vercel secrets, and the functio [...]

What an attacker achieves.

Nothing today, since the file is never read. If anyone ever does deploy to Vercel, any website becomes able to preflight and POST to /api/review and read the response, because the header block allows POST and Content-Type from origin *.

Fix.

Delete vercel.json. Move the genuinely wanted security headers (X-Content-Type-Options, X-Frame-Options, Referrer-Policy, Permissions-Policy from vercel.json:36-59) into a headers() function in next.config.mjs, where they will actually be applied, and do not carry the CORS block across.

Verification: 1 adversarial verifier, 0 refuted.

### SR-80: app/api/health/route.ts always reports healthy and always reports GitHub and AI disabled, and has no caller

- Severity: low
- Where: app/api/health/route.ts:14
- Difficulty for an attacker: trivial
- Category: correctness
- Status: Fixed in the frontend rebuild (2026-09-03): deleted.

What it is.

The route reports checks.database as the hardcoded string 'ok' with a comment conceding it does not check anything (:20), so status is 'healthy' unconditionally. It gates githubIntegration and checks.github on process.env.GITHUB_TOKEN (:14, :22), a variable that appears nowhere in .env.example and nowhere else in the repository, so both are permanently false and 'disabled'. It gates aiAnalysis and checks.ai on OPENAI_API_KEY (:15, :21), which in the intended split lives in backend/.env rather than the frontend env, so those are false too in a correct configuration.

What an attacker achieves.

Anyone reaching the tunnel gets Node heap and RSS figures and process uptime for free. More practically, a monitor pointed at this endpoint would report green while the backend, the database and the AI path are all down.

Fix.

Delete it, or make it real: proxy the backend's own health endpoint and drop the memory and uptime fields. Do not keep a health check whose only possible answer is 'healthy'.

Verification: 1 adversarial verifier, 0 refuted.

### SR-81: Signature verification was commented out on main for six weeks ('for testing') with no test to catch a repeat

- Severity: info
- Where: backend/handlers/webhook.py:62
- Difficulty for an attacker: hard
- Category: webhook-auth
- Status: Mitigated 2026-09-03: test_webhook and test_signature pin the check and CI runs them on every push.

What it is.

Commit d18240a (2025-09-22) commented out the verify_github_signature check and the return in verify_webhook_signature; cd3749e (2025-11-02) restored both; both are on main and this branch. In the disabled state the function returned None so the unpack at webhook.py:91 raised TypeError into the 200-with-error path, so the window was probably never exercised, but the intent was to bypass authentication on main. No tests exist (.gitignore ignores test_*.py outside backend/tests and backend/tests is empty). Current code has verification enabled.

What an attacker achieves.

Nothing today; a one-line comment silently removes the only authentication on the endpoint and the 200-on-exception behaviour makes the outage look like success to GitHub.

Fix.

Add backend/tests/test_webhook_signature.py that posts unsigned, wrongly signed and correctly signed pull_request payloads with TestClient asserting 400, 401 and 200; gate any bypass behind an explicit setting refused when is_production is true.

Verification: 1 adversarial verifier, 0 refuted.

### SR-82: GET webhook handler answers a hub.challenge query (Meta/WebSub pattern) that GitHub never sends and fingerprints the route

- Severity: info
- Where: app/api/webhook/github/route.ts:60
- Difficulty for an attacker: trivial
- Category: webhook-auth
- Status: Fixed in the frontend rebuild (2026-09-03): the proxy is gone.

What it is.

The GET export reads hub.challenge and echoes it as text/plain, commented as 'GitHub webhook verification challenge' (app/api/webhook/github/route.ts:57-70); GitHub verifies by POSTing a ping event and never issues a GET. The route also answers {message: 'GitHub webhook endpoint is active'} to any GET.

What an attacker achieves.

A small fingerprint only; the reflection is text/plain so no script execution.

Fix.

Remove the GET handler (or return 405) and handle the POST ping event in the backend.

Verification: 1 adversarial verifier, 0 refuted.

### SR-83: No working no-network path: MockAIReviewer and SecurityScanner are never imported, DEMO_MODE is only a status flag, and OPENAI_API_KEY is mandatory

- Severity: info
- Where: backend/services/mock_reviewer.py:19
- Difficulty for an attacker: trivial
- Category: llm-pipeline
- Status: Fixed in the backend rewrite (2026-09-03): the whole pipeline is local; test_runner proves a review completes with every non-loopback socket blocked (GitHub answered in-process by respx, the model a fake; the real-model variant is the opt-in e2e test).

What it is.

Repo-wide grep for MockAIReviewer, mock_reviewer, get_mock_ai_health, SecurityScanner, security_scanner and DEMO_MODE finds only the definitions (mock_reviewer.py:19, :303; security_scanner.py:30) and one read of DEMO_MODE in main.py:272 for GET /status. MockAIReviewer.review_pr_files(self, files) (mock_reviewer.py:25) lacks the pr_number/pr_title/pr_description kwargs passed at queue_processor.py:368-373.

What an attacker achieves.

Nothing directly; there is no offline or local-model path despite the branch name, and the only deterministic analyser is unused.

Fix.

Make OPENAI_API_KEY optional and select the reviewer (Ollama/local, OpenAI, Mock) by settings behind one interface with the same review_pr_files signature; run SecurityScanner.scan_diff as a deterministic first pass and merge its results into security_findings.

Verification: 1 adversarial verifier, 0 refuted.

### SR-84: CORS: backend configuration is correct; vercel.json wildcard plus credentials and next.config allowedOrigins are inert

- Severity: info
- Where: vercel.json:18
- Difficulty for an attacker: hard
- Category: authz-endpoints
- Status: Fixed in the backend rewrite (2026-09-03): backend CORS allows no credentials and an explicit method and header list; vercel.json goes in Phase 5.

What it is.

Backend CORSMiddleware uses an explicit origin list with allow_credentials=True (backend/main.py:76-82; settings.py:17, :77-81) and sets no cookies. vercel.json:16-35 combines Access-Control-Allow-Origin '_' with Allow-Credentials 'true' on /api/_, which browsers refuse to honour, so cross-site reads only reach already-unauthenticated endpoints. next.config.mjs:6-10 serverActions.allowedOrigins is inert because there is no 'use server'. The real risk is 'fixing' the wildcard by reflecting Origin with credentials true, which would expose /api/auth/me and /api/github/prs.

What an attacker achieves.

Nothing beyond what an unauthenticated direct request already gives.

Fix.

Drop the Access-Control-* headers from vercel.json (same-origin app) or list the exact frontend origin without the credentials flag.

Verification: 1 adversarial verifier, 0 refuted.

### SR-85: Raw model output logged at DEBUG; traceback logging inconsistent between DEBUG and JSON modes

- Severity: info
- Where: backend/services/ai_reviewer.py:1239
- Difficulty for an attacker: hard
- Category: data-logging
- Status: Fixed in the backend rewrite (2026-09-03): prompts and model output are logged only under LOG_PROMPTS=true, both after redaction (the output side was only fixed in the third round).

What it is.

_parse_json_result logs the full raw completion when parsing fails (ai_reviewer.py:1237-1240); LOG_LEVEL defaults to INFO (settings.py:66; .env.example:52; logging.py:16-20) so it is silent unless raised, at which point completions quoting reviewed code hit stdout and any shipper. review_workflow.py:938 passes exc_info=True but the structlog chain (logging.py:23-42) lacks format_exc_info, so JSON mode drops tracebacks while console mode prints them.

What an attacker achieves.

Nothing by default; an operator raising LOG_LEVEL to DEBUG starts writing reviewed code to logs.

Fix.

Log only the length, a hash or the first 200 characters of the raw result; add structlog.processors.format_exc_info.

Verification: 1 adversarial verifier, 0 refuted.

### SR-86: Browser console receives full editor contents on every keystroke and full review results

- Severity: info
- Where: components/review/CodeEditor.tsx:285
- Difficulty for an attacker: hard
- Category: data-logging
- Status: Fixed in the frontend rebuild (2026-09-03): the code editor is gone; no console logging of content.

What it is.

The Monaco onChange handler logs the whole editor value on every change (components/review/CodeEditor.tsx:284-287); hooks/useReviewService.ts:66, components/review/ReviewInterface.tsx:124-133 and app/review/page.tsx:28 log full results. These run client-side only; server route handlers log only errors and status codes (app/api/auth/github/callback/route.ts:52; app/api/review/pr/route.ts:31, 95, 129; app/api/github/prs/route.ts:35, 92, 190).

What an attacker achieves.

Minimal; code and results are visible in the same user's devtools and to extensions or screen recordings.

Fix.

Remove the console.log calls or guard them behind process.env.NODE_ENV !== 'production'.

Verification: 1 adversarial verifier, 0 refuted.

### SR-87: Runtime Google Fonts import phones home for every visitor and duplicates the self-hosted next/font Inter

- Severity: info
- Where: app/globals.css:5
- Difficulty for an attacker: hard
- Category: data-logging
- Status: Fixed in the frontend rebuild (2026-09-03): no font is loaded from a network; the production HTML references no external host.

What it is.

app/globals.css:5-6 @imports Inter and JetBrains Mono from fonts.googleapis.com at runtime while app/layout.tsx:2,9 already self-hosts Inter via next/font/google. NEXT_TELEMETRY_DISABLED=1 is only set in vercel.json:76. scripts/validate-env.js:118 posts the OPENAI_API_KEY to api.openai.com (expected); the social-image scripts only print an opengraph.xyz URL; puppeteer (package.json:100) downloads Chromium on install. No analytics or Sentry browser SDK imports exist.

What an attacker achieves.

Google receives per-visitor IP, user agent and referrer; no attacker gain.

Fix.

Delete the two @import lines and load JetBrains Mono via next/font/google; add NEXT_TELEMETRY_DISABLED=1 to .env.example if telemetry is unwanted.

Verification: 1 adversarial verifier, 0 refuted.

### SR-88: Git history contains no real credentials; the only non-placeholder artefacts are an 'example' webhook secret in deleted docs and an expired ngrok hostname

- Severity: info
- Where: docs/GITHUB_APP_SETUP.md:131
- Difficulty for an attacker: hard
- Category: deps-history-scripts
- Status: No action needed: informational.

What it is.

All 27 'BEGIN RSA PRIVATE KEY' hits in git log --all -p are placeholders or the validate-env.js format check (:306); no 64-character base64 PEM body lines and no token-format matches (sk-, ghp_, ghs_, github_pat_, lsv2_, AKIA, xox*, Sentry DSN, whsec_) exist; no .env, .db, .sqlite or .log was ever added.

What an attacker achieves.

Nothing from the repository alone; if the example string was ever the real secret of a still-existing App, signatures could be forged (WHERE_I_LEFT_OFF.md records the original App was deleted).

Fix.

No history rewrite needed; rotate GITHUB_WEBHOOK_SECRET if that example value was ever used; add gitleaks to CI.

Verification: 1 adversarial verifier, 0 refuted.

### SR-89: Deleted working notes in history contradict the README's 'working' narrative and document the mock auth, missing review pipeline and removed test suite

- Severity: info
- Where: WHERE_I_LEFT_OFF.md:1
- Difficulty for an attacker: hard
- Category: deps-history-scripts
- Status: Fixed in the docs pass (2026-09-03): README.md says what works, what is deliberately absent, and that one person has run it end to end.

What it is.

Files removed in cf58336/0579209 remain readable: WHERE_I_LEFT_OFF.md ('PR Review Not Working MAIN ISSUE', 'GitHub App Deleted BLOCKER', 'Webhook processing (not set up)'), claudetodo.txt ('fully functional' with a live ngrok URL), backend/api-test-report-20251107-220316.md (17/21 passing, /review/manual in 0.049 s), FIXES_SUMMARY_NOV7.md, backend/seed_test_user.py ('any password works for testuser in DEBUG mode'), CLAUDE.md describing scripts and a lib/ai tree that never existed, and the only test suite (backend/tests/*, test_langgraph.py, test_webhook_signature.py, pytest.ini, run_tests.py); [...]

What an attacker achieves.

Reconnaissance only: the mock-auth username, the shape of unauthenticated review endpoints, and confirmation that no tests or CI guard the code.

Fix.

Restore or rewrite the backend test suite from 0579209^:backend/tests/, remove the test_*.py ignore rule, and make README claims match reality.

Verification: 1 adversarial verifier, 0 refuted.

### SR-90: Image-generation scripts are dev-only and offline, but generate-social-images.js is broken on the pinned Puppeteer and disables the Chromium sandbox

- Severity: info
- Where: scripts/generate-social-images.js:21
- Difficulty for an attacker: hard
- Category: deps-history-scripts
- Status: Fixed in the frontend rebuild (2026-09-03): the image scripts and puppeteer are gone.

What it is.

generate-social-images.js launches Puppeteer with --no-sandbox/--disable-setuid-sandbox (:19-22) and calls page.waitForTimeout (:42, :47, :58), removed in Puppeteer 22, so with puppeteer ^24.29.1 (package.json:81) it throws before any screenshot; it only loads a local file:// template (:28-32) and writes to public/. generate-favicons.js and generate-simple-social-images.js use sharp on local SVGs (generate-favicons.js:14-29; generate-simple-social-images.js:14, :99-107). Puppeteer and sharp account for 8 high/critical transitive audit entries and the generated assets are already committed.

What an attacker achieves.

Nothing remotely; a sandbox-less browser run against a malicious template would gain the developer's privileges, but the template is repo-controlled.

Fix.

Delete the generator scripts and drop puppeteer/sharp from devDependencies, or fix waitForTimeout, drop --no-sandbox and bump puppeteer to 25.x and sharp to 0.35.x.

Verification: 1 adversarial verifier, 0 refuted.

### SR-91: Name drift in text posted to GitHub, sent as User-Agent and shown in health output ('ReviewBot Protocol' versus 'Git Review Assistant')

- Severity: info
- Where: backend/services/review_workflow.py:863
- Difficulty for an attacker: trivial
- Category: gaps-critic-prep
- Status: Fixed in the backend rewrite (2026-09-03): one name everywhere; the User-Agent is ReviewBot-Protocol.

What it is.

The PR comment header says 'ReviewBot Protocol Results' (review_workflow.py:847) while its footer says 'Generated by Git Review Assistant' (:863); the status context is 'git-review-assistant/review' with description 'ReviewBot Protocol analysis in progress...' (webhook.py:401-402; queue_processor.py:439); defaults 'git-review-assistant' at models/github.py:171, models/review.py:128, database/models.py:107, github_client.py:328; User-Agent 'Git-Review-Assistant' (app/api/review/pr/route.ts:62; app/api/github/prs/route.ts:87, :254); /api/health reports 'Git Review Assistant' (app/api/health/rout [...]

What an attacker achieves.

None; two product names in one comment and a mismatched status context confuse required-check configuration.

Fix.

Introduce a single APP_DISPLAY_NAME / STATUS_CONTEXT constant (settings.APP_NAME exists) and use it in comments, statuses, User-Agent and docs; fix the README support links.

Verification: 1 adversarial verifier, 0 refuted.

## Second round: review of the rewrite

The rewritten backend was itself put through the same adversarial process on 2026-09-03 (four Opus reviewers with distinct lenses: security, correctness, GitHub API contract against the official docs, and test gaps; then verifiers per finding). 64 raw findings, 56 after merge, all 56 confirmed, none refuted. Every one was fixed the same day and the suite grew from 111 to 208 tests. The ones worth knowing about:

- The delimiter defence had a hole: a four-bracket `<<<<DIFF_DATA_END>>>` collapsed into the exact delimiter after the single-pass replace, so a PR author could forge the end of the untrusted block. Now the delimiters carry a per-request random nonce, anything in PR content that resembles a marker (any bracket run, any suffix) is rewritten to a bracket-free token, and the rendered prompt is checked for exactly one begin and one end before the model is called; a failed check skips the file and says so. Tests cover four-bracket, five-bracket, spaced and nonce-suffixed forgeries in both filenames and diffs.
- The private-key redaction could swallow the rest of a patch when no END marker followed, and collapsed lines so comment line numbers drifted. Redaction is now line-preserving throughout and bounded per block.
- Redaction now also catches unquoted assignments, npm and Slack app tokens, Azure account keys and passwords containing `@`, and no longer skips a real secret just because it contains the word `example`. Model output is redacted as well as PR content.
- The sanitiser no longer has a 200-character tag limit to pad past; it also neutralises `www.` and e-mail autolinks, reference-style link definitions and every `@` mention, and quoted evidence goes inside a code span so it keeps its angle brackets.
- The GitHub client only sends the installation token to the configured API host (a hostile Link header is refused), treats redirects as errors (the production client was still following them until the third round), merges `per_page` into every page, reports truncation, backs off using the rate-limit reset header, and only folds inline comments into the body when GitHub's 422 is actually about a comment line.
- The queue survives any exception a worker raises, sets aside a worker that ignores cancellation after a grace period and waits for it before the next job, refuses jobs while shutting down, reports whether its loop is alive, and rows left running by a crash are marked interrupted at the next start so GitHub's redelivery is accepted.
- The runner abandons a job when the PR head moved (before and after the model calls), counts files the model failed on separately and says so in the posted review, and picks the riskiest files before applying the file cap.
- Fork detection fails closed when the source repository has been deleted; repository names are validated against a pattern before they reach an API path; a non-ASCII dashboard token is a 401 rather than a 500; every `/api` route is gated at the router, and a test walks the routes to prove it.

The verified findings and votes of both rounds are kept in the session transcript; the durable record is this file and the tests named above.

## Third round: the whole branch, after the fixes

On 2026-09-03 the branch was reviewed a third time, this time everything that changed since main: the backend in its post-fix state, the new dashboard, the supply chain (lockfiles, CI, the container proof), the documentation against the code, and the tests themselves. Five Opus reviewers with distinct lenses, then Sonnet merged their findings and two or three Opus verifiers per finding tried to refute each one. 91 raw findings, 68 after merge, 67 confirmed, 1 refuted (three queue tests alleged to be timing races; the verifier ran them 50 times each and they held). Every confirmed finding was fixed the same day. The ones that mattered:

- The dashboard bound to every network interface and has no login (high). Next's CLI defaults to 0.0.0.0, and nothing in the app checked who was asking, so anyone on the same network could read every stored review, including quoted lines of private code. Now `next dev` and `next start` bind to 127.0.0.1, a middleware refuses any request whose Host is not loopback (which also defeats DNS rebinding), responses carry a Content-Security-Policy, `Referrer-Policy: no-referrer`, `X-Frame-Options: DENY` and `X-Content-Type-Options: nosniff`, the framework header is off, and the README says plainly that the dashboard has no login and must stay on loopback.
- An unterminated HTML comment in a model summary hid the rest of the review (high). A summary ending `<!--` is a CommonMark HTML block, so GitHub swallowed everything after it: remaining findings, the list of skipped secret-bearing files and the footer. The sanitiser now replaces every remaining `<` after the tag pass, text spliced into a single body line is collapsed to one line, and the body is assembled with the parts an author cannot influence (not attached, not reviewed) before the model-written summaries, so the 6000-character cap cuts summaries first and says so.
- A hard-coded bearer token in a dict literal, `"Authorization": "Bearer ..."`, was not redacted (high) because the pattern required the separator to follow the word directly. It now allows a closing quote or bracket.
- `backend/.env.example` put a comment after an empty webhook secret, which python-dotenv reads as the value (high): an operator who filled in only the App id and key would have been verifying signatures against a public string. Comments are on their own lines now, and settings refuse a webhook secret or dashboard token shorter than 16 characters or starting with `#`.
- The production GitHub client followed redirects, including cross-host ones, so a redirect from api.github.com could have sent the installation token elsewhere; the second-round summary claimed it did not. It no longer follows any redirect, and a test builds the client without an injected transport to prove it.
- A review cancelled by shutdown was recorded as superseded, which blocks GitHub's redelivery. The queue now tells the worker why it was cancelled (superseded, timeout or shutdown) and the runner records interrupted, timed out or superseded accordingly. A stuck worker is set aside and waited for before the next job starts, so two reviews never run at once; a second backend instance against the same database refuses to start; a head that was already reviewed to completion is not reviewed again after a restart.
- Secret-bearing file names were matched case-sensitively, so `.ENV` or `ID_RSA` would have been reviewed and posted. Fixed.
- Model output was logged unredacted under `LOG_PROMPTS=true`, while the review claimed otherwise. Fixed, and the claim corrected.
- Bidi and zero-width characters were stripped from the prompt but survived into the posted review and dashboard. Stripped everywhere now.
- The frontend `npm audit --audit-level=high` gate in CI would have failed on the committed lockfile (a vulnerable postcss under Next); the workflow had never run. The override is in place (npm 11, which fixed an override bug in npm 10), the audit is clean, CI pins its actions by commit SHA and grants `contents: read` only, Dependabot watches the container base image, the backend installs from a hashed lock with `--require-hashes`, and `.gitignore` and `.dockerignore` exclude private keys and every `.env` variant.
- Two assertions in the prompt-injection tests could not fail (`or True`, and an operator-precedence slip). Replaced with assertions that can. Added: the post-model head-move check, every rate-limit branch, the WAL pragma, a fuzz test that redaction never changes a line count, the boundary check's fail-closed branch with the defences in front of it disabled, and 15 vitest unit tests for the dashboard's link allowlist and API guards.
- Documentation drift: the headline egress claim named a test that did not use the socket guard (the guard is now applied to every whole-review test, and the wording says exactly what each proof covers), the ping-verification step could never have succeeded (every signed delivery is recorded now, so it does), `OLLAMA_NO_CLOUD` was described as something it is not, `MAX_PATCH_BYTES` disagreed across four files, and a handful of design statements in LOCAL_MIGRATION.md did not match the code. All corrected.

Not changed, deliberately: the dashboard has no authentication of its own. It is single-user and loopback-only by construction; adding a login would add a credential to protect without changing who can reach it. The threat model says so.

### Second round (2026-09-03): the 56 findings

Each line: id, severity after verification (original in brackets where it changed), where, the finding. Status for every one: fixed on 2026-09-03 unless a note says otherwise.

- R2-01 [high (was critical)] backend/services/ai_reviewer.py:33: Delimiter reconstitution lets PR content forge the untrusted-data block boundary
- R2-02 [high] backend/services/redaction.py:15: Unterminated private-key marker deletes the rest of the file's patch (review evasion)
- R2-03 [high] backend/services/redaction.py:15: Multi-line private-key redaction collapses diff lines, so inline comment 'line' values point at the wrong code
- R2-04 [medium (was high)] backend/services/redaction.py:30: Redaction misses the most common real-world secret form: unquoted key=value assignments
- R2-05 [medium] backend/services/comment_renderer.py:18: HTML stripper is bypassed by padding the tag past 200 characters
- R2-06 [medium] backend/services/comment_renderer.py:20: GFM www. and email autolinks pass the link filter unchanged
- R2-07 [medium] backend/services/comment_renderer.py:87: Failed/unparseable file reviews are counted identically to successful ones in both the posted comment and the persisted review
- R2-08 [medium] backend/services/comment_renderer.py:21: @mention neutralisation is skipped after any backtick, including an unmatched one
- R2-09 [medium] backend/services/github_client.py:50: Paginated Link-header URL is followed with the installation token attached and no host/scheme check
- R2-10 [medium (was low)] backend/services/redaction.py:61: Redaction is skipped whenever the captured secret contains a placeholder hint substring
- R2-11 [medium (was high)] backend/services/review_queue.py:101: A BaseException or stray CancelledError from the worker kills the review loop permanently and silently
- R2-12 [medium (was high)] backend/services/diff.py:66: Findings whose evidence quotes the diff line with its leading '+' are silently dropped
- R2-13 [medium] backend/services/review_queue.py:95: The review deadline is not hard: a worker hanging while unwinding blocks the single-worker queue forever
- R2-14 [medium] backend/services/review_runner.py:93: Reviews left in status 'running' after a crash are never reconciled at startup
- R2-15 [medium] backend/services/review_queue.py:128: Jobs pending in the queue at shutdown are dropped and can never be redelivered
- R2-16 [medium] backend/services/review_runner.py:67: The file cap is applied in GitHub's raw order before risk prioritisation, so the riskiest files can be cut, and neither the composition nor the output-schema strength is tested
- R2-17 [medium] backend/services/github_client.py:62: 3xx responses are treated as success and never followed; a redirected repo turns a review into an AttributeError
- R2-18 [medium] backend/services/github_client.py:98: The 422 fallback re-POSTs the review immediately, including when the 422 means the endpoint has been spammed
- R2-19 [medium] backend/services/github_client.py:57: Rate-limit handling ignores x-ratelimit-reset and does not back off at all when retry-after is absent
- R2-20 [medium] backend/handlers/webhook.py:31: The webhook body cap's streaming branch is untested; only the content-length branch is covered
- R2-21 [medium] backend/handlers/review.py:79: GET /api/deliveries has no test at all, and the feedback route's auth is never tested negatively
- R2-22 [medium] backend/handlers/review.py:55: No test enforces the invariant 'every route except /health and /webhook/github requires LOCAL_API_TOKEN'
- R2-23 [medium] backend/tests/conftest.py:40: Security-relevant settings defaults are masked by conftest's process environment, so the defaults are not actually pinned
- R2-24 [medium] backend/config/settings.py:62: LOG_PROMPTS has no test whatsoever: neither the default nor the fact that nothing logs diffs when it is off
- R2-25 [medium] backend/tests/test_review_generation.py:71: test_pr_title_and_body_never_reach_the_model cannot fail: the title is never passed in
- R2-26 [medium] backend/tests/test_runner.py:43: The egress guard cannot fire in the test named after it, and langsmith is missing from the cloud-SDK denylist
- R2-27 [medium] backend/tests/conftest.py:35: Tests share one SQLite file and module-level engine globals; test_runner identifies 'the' failed review by global ordering
- R2-28 [low (was high)] backend/services/comment_renderer.py:95: Model-authored text is never redacted before posting or persisting, and the test claiming to prove otherwise can't fail
- R2-29 [low] backend/services/github_client.py:102: The 422 fallback posts the raw, unsanitised filename into the comment body
- R2-30 [low] backend/services/ai_reviewer.py:39: _meta leaves Unicode line separators and bidi controls in the filename
- R2-31 [low] backend/handlers/review.py:26: Non-ASCII dashboard token header crashes require_local_token into a 500 instead of a 401, and this is untested unlike the identical webhook-path hazard
- R2-32 [low] backend/services/redaction.py:16: openai-key pattern false-positives on ordinary sk- prefixed identifiers
- R2-33 [low] backend/models/github.py:84: A PR from a deleted fork (head.repo null) is classified as not-a-fork
- R2-34 [low (was medium)] backend/services/review_queue.py:63: submit() after stop() accepts jobs that will never run
- R2-35 [low] backend/services/review_runner.py:145: Superseded and timed-out reviews are recorded as 'failed' with error_message 'CancelledError'
- R2-36 [low] backend/services/review_runner.py:105: The review is posted against the API's head sha, not the job's, so the same content can be reviewed twice
- R2-37 [low] backend/main.py:71: The 500 response carries no CORS headers, so the dashboard sees an opaque failure
- R2-38 [low] backend/main.py:59: TrustedHostMiddleware is the innermost middleware, and its default allowed hosts cannot receive a real webhook
- R2-39 [low] backend/services/diff.py:68: Short evidence strings relocate a finding onto an unrelated line
- R2-40 [low] backend/config/settings.py:53: MAX_PATCH_BYTES is not budgeted against OLLAMA_NUM_CTX, and Ollama truncates silently
- R2-41 [low] backend/database/connection.py:28: SQLite runs in rollback-journal mode with a 15-connection pool and two concurrent writers
- R2-42 [low] backend/config/settings.py:64: The default SQLite path is relative, so the database follows the working directory
- R2-43 [low] backend/services/github_client.py:14: File pagination silently truncates and its 3000-file cap depends on GitHub echoing per_page into the Link header
- R2-44 [low] backend/services/review_runner.py:104: commit_id is read before the file list, so a push between the two calls can invalidate every inline comment
- R2-45 [low] backend/services/review_runner.py:57: Rename-only, copied and unchanged files are reported to the PR author as binary or too large
- R2-46 [low (was high)] backend/main.py:36: main.py lifespan wiring (real queue + run_review worker) is never exercised by any test
- R2-47 [low (was high)] backend/services/llm.py:17: Nothing pins that the production model client is local; build_chat_model is only reached by the skipped e2e test
- R2-48 [low] backend/main.py:71: The generic 500 handler is never tested, so a change that leaks exception detail would go unnoticed
- R2-49 [low] backend/main.py:67: Request and rejection logging content is unpinned: nothing stops query strings, bodies or signatures being logged
- R2-50 [low] backend/services/review_runner.py:65: .env.example is deliberately allowed past the secret-file exclusion but then silently dropped as 'not code'
- R2-51 [low] backend/handlers/webhook.py:80: Webhook delivery bookkeeping has no test for the failure and supersede paths
- R2-52 [info] backend/services/github_client.py:71: Repository full_name is interpolated into API paths without validation
- R2-53 [info] backend/services/review_queue.py:124: drain() polls forever with no liveness check or timeout
- R2-54 [info] backend/services/review_workflow.py:77: recursion_limit is correct but roughly three times larger than the graph needs
- R2-55 [info] backend/services/review_workflow.py:62: results is copied on every analyse_file step (quadratic in file count)
- R2-56 [info] backend/tests/test_webhook.py:76: Two assertions in the suite are structurally incapable of failing

### Third round (2026-09-03): the 67 findings

Each line: id, severity after verification (original in brackets where it changed), where, the finding. Status for every one: fixed on 2026-09-03 unless a note says otherwise.

- R3-01 [high] package.json:6: Dashboard has no authentication and binds to every network interface by default
- R3-02 [high (was medium)] backend/services/comment_renderer.py:50: Unterminated HTML comment in model output hides the footer, overflow findings and Not-reviewed list
- R3-03 [high (was medium)] backend/services/redaction.py:34: Hard-coded bearer token in a headers dict , the commonest form , is not redacted
- R3-04 [high] backend/.env.example:7: .env.example's webhook secret line is parsed with the trailing comment as its value, defaulting the signature check to a public constant
- R3-05 [medium] backend/services/redaction.py:140: Secret-bearing filename exclusion is case-sensitive
- R3-06 [medium (was high)] backend/services/review_runner.py:199: A review killed by backend shutdown is recorded as "superseded", permanently blocking GitHub's redelivery
- R3-07 [medium (was high)] backend/services/github_client.py:40: Production GitHub client follows redirects, including cross-host, contradicting the documented "treats redirects as errors" claim , and the only test covering it uses a differently-configured client
- R3-08 [medium (was high)] .github/workflows/ci.yml:45: CI's frontend npm audit --audit-level=high gate fails on the committed lockfile, and the workflow has apparently never actually run
- R3-09 [medium] backend/services/comment_renderer.py:136: 6000-character body cap truncates from the tail, dropping the findings overflow and Not-reviewed sections first
- R3-10 [medium (was high)] README.md:37: README's headline egress claim names a test that never uses the socket-level guard; the one test that does is skipped by default and never runs in CI
- R3-11 [medium] scripts/prove_local/run_proof.py:4: Container proof docstring claims it fails on a disobeyed prompt injection; the exit code never checks that, and the secret check it does run is a weak 14-character prefix match on posted output only
- R3-12 [medium] backend/services/review_queue.py:133: After the grace period the queue abandons a stuck worker and starts the next job, so two reviews can run concurrently
- R3-13 [medium] lib/api.ts:85: A dead review queue is invisible on the dashboard
- R3-14 [medium] package.json:27: shadcn , a 318-package codegen CLI , sits in production dependencies for the sake of one 16KB CSS import
- R3-15 [medium (was high)] app/actions.ts:20: Server actions run for any unauthenticated caller; Next's Origin check stops browsers but not scripts, and there is no Host allowlist against DNS rebinding
- R3-16 [medium (was high)] .gitignore:87: .gitignore has no _.pem/_.key rule, while the documented setup path puts the GitHub App private key inside the repository working tree
- R3-17 [medium (was high)] .dockerignore:1: .dockerignore does not exclude private keys or logs, so the local proof image can bake in the GitHub App private key
- R3-18 [medium] backend/requirements.txt:2: No lockfile or hashes for the Python runtime: 14 pins carry ~46 floating transitives, including the langsmith client the local-only claim depends on excluding
- R3-19 [medium (was high)] backend/README.md:43: The documented "send a ping and see it in Recent deliveries" verification step cannot ever succeed
- R3-20 [medium] docs/SECURITY_REVIEW.md:1987: "Prompts and model output are logged only after redaction" is false: model output is logged unredacted
- R3-21 [medium] README.md:31: OLLAMA_NO_CLOUD is described as doing something it does not do, and a cloud-tagged model would relay prompts off the machine with no guard detecting it
- R3-22 [medium] docs/LOCAL_MIGRATION.md:165: LOCAL_MIGRATION's egress-proof list describes a test and a supporting document that do not exist in the form claimed
- R3-23 [medium] backend/services/review_runner.py:166: The post-model head-SHA supersede check is never exercised: the fake GitHub server returns the same head to both get_pull calls in every test
- R3-24 [medium] backend/tests/test_review_generation.py:76: Two assertions in the hostile-filename prompt-injection test are unconditionally true
- R3-25 [low (was medium)] backend/tests/test_review_generation.py:189: Sanitiser reference-link-definition test is short-circuited by operator precedence and passes vacuously
- R3-26 [low] backend/services/comment_renderer.py:48: Bidi and zero-width Unicode control characters are stripped for the model prompt but survive into the posted GitHub review and dashboard
- R3-27 [low (was medium)] backend/README.md:73: MAX_PATCH_BYTES disagrees across code default, .env.example, and documentation, and the documented 40000 value is unreachable at the shipped context size
- R3-28 [low] backend/requirements.txt:12: langchain meta-package is pinned as a runtime dependency but never imported
- R3-29 [low (was medium)] .github/workflows/ci.yml:1: CI workflow declares no permissions block, pins actions by mutable tag, and Dependabot has no docker ecosystem so the mutable Ollama base image is never updated
- R3-30 [low (was high)] components/severity-badge.tsx:41: Dashboard cannot render three of the five backend review statuses and hides the error message for all non-happy-path outcomes
- R3-31 [low] backend/services/review_runner.py:212: A head-move supersede is reported to the queue as a successful review
- R3-32 [low] backend/services/review_queue.py:120: Any worker that ends self-cancelled is reported as SupersededError regardless of the actual cause
- R3-33 [low] backend/services/review_runner.py:172: A cancel between the GitHub POST and the database write loses the posted review's URL or leaves an inconsistent row
- R3-34 [low] backend/services/review_queue.py:98: submit() cancels the in-flight review for a new head and then reports the delivery as "duplicate"
- R3-35 [low] components/ui/dropdown-menu.tsx:144: Dropdown menu's keyboard-focus indicator is a 1.09:1 background tint, well under WCAG contrast
- R3-36 [low] components/ui/toggle.tsx:10: Feedback toggle's selected state is a 1.09:1 background tint, so which answer is recorded is not visibly distinguishable
- R3-37 [low] package.json:37: eslint 9 is end-of-life, so the lint gate runs on an unmaintained major version
- R3-38 [low] next.config.mjs:5: No CSP, frame-ancestors, or other security response headers; X-Powered-By is advertised
- R3-39 [low] components/posted-body.tsx:11: Hand-written markdown renderer is quadratic on runs of '[', bounded only by a backend constant the frontend doesn't know about
- R3-40 [low] app/reviews/[id]/page.tsx:114: Two hrefs render backend-supplied strings with no local scheme/shape validation
- R3-41 [low] lib/api.ts:125: BACKEND_URL is unvalidated, so a misconfigured value ships LOCAL_API_TOKEN off the machine
- R3-42 [low] docs/FRONTEND_PLAN.md:50: docs/FRONTEND_PLAN.md makes four claims about the built dashboard that the shipped code contradicts
- R3-43 [low (was medium)] lib/api.ts:222: recordFeedback validates nothing, and encodeURIComponent leaves dot-segments unescaped, letting an unauthenticated caller steer a token-authenticated backend request
- R3-44 [low] Dockerfile.local:13: Container proof is not reproducible: model, OS packages and Python transitives are all resolved fresh from the network at build time with no digests
- R3-45 [low] scripts/prove_local/entrypoint.sh:11: Entrypoint's "no route out" check cannot distinguish a missing route from a DNS or upstream failure
- R3-46 [low] scripts/prove_local/entrypoint.sh:7: Proof entrypoint starts the fake GitHub server in the background and never waits for it to accept connections
- R3-47 [low] docs/SECURITY_REVIEW.md:2360: Second adversarial round's '56 findings, all fixed' claim has no corresponding per-finding record anywhere in the document it points to
- R3-48 [low] backend/README.md:8: "The same head SHA is never reviewed twice" holds only while a job is queued or in flight, not after it completes
- R3-49 [low] docs/LOCAL_MIGRATION.md:190: Implementation notes still describe the delimiter-softening defence that the second review round replaced
- R3-50 [low] docs/LOCAL_MIGRATION.md:47: Four design-section statements in LOCAL_MIGRATION are contradicted by the code and are not listed as differences
- R3-51 [low] backend/README.md:53: Model speed figures mix a labelled estimate with an unlabelled one, and none is reproducible from the repository
- R3-52 [low] README.md:39: "Last run: 2026-09-03, passed" for the container proof is unverifiable and has no mechanism to stay true
- R3-53 [low] docs/SECURITY_REVIEW.md:927: SR-37's status line miscounts the runtime dependency set
- R3-54 [low (was medium)] backend/services/redaction.py:15: Redaction's line-count invariant is a hard-coded docstring promise with no property test covering the pattern table
- R3-55 [low (was medium)] backend/database/repositories/review_repository.py:64: Startup reconciliation marks every 'running'/'queued' row interrupted with no owner check, so a second concurrent instance can hijack an in-flight review
- R3-56 [low (was medium)] backend/database/models.py:62: created_at/received_at timestamps are stored timezone-naive and rendered an hour wrong under British Summer Time
- R3-57 [low (was medium)] lib/api.ts:129: Frontend has zero tests and no test runner, despite several pure functions worth covering
- R3-58 [low] backend/services/ai_reviewer.py:155: Prompt boundary check cannot fail under current input, so its fail-closed branch has never executed and no test reaches it
- R3-59 [low] backend/services/github_client.py:87: Only one of three rate-limit back-off branches is tested, leaving the wait cap and retry budget unverified
- R3-60 [low] backend/database/connection.py:45: WAL journal mode and busy_timeout pragmas , the setting that keeps the dashboard from colliding with a running review , have no test at all
- R3-61 [low] backend/tests/test_review_generation.py:196: A single test assertion accounts for 62% of the suite's runtime because sanitise()'s email regex is quadratic on input with no '@'
- R3-62 [info] app/loading.tsx:5: Loading screens put aria-label and aria-busy on a plain div, where neither is announced
- R3-63 [info] app/page.tsx:24: searchParams.repository is typed as a string but Next supplies an array when the query parameter repeats
- R3-64 [info (was low)] package.json:47: Pre-commit hook silently rewrites staged source with eslint --fix and re-stages it before the author reviews the result
- R3-65 [info] docs/SECURITY_REVIEW.md:2313: Absolute home path committed in the security review discloses the maintainer's local username
- R3-66 [info] docs/SECURITY_REVIEW.md:2340: SECURITY_REVIEW's App-permissions section still lists Commit statuses, write, contradicting every other permission list in the repository
- R3-67 [info] README.md:29: Two omissions in the privacy documentation: findings store quoted diff lines, and tunnelling the whole port exposes the dashboard API behind only one shared token

Refuted in this round:

- Three queue tests are timing races by construction, and one grace-period assertion is weakened by an or-clause

## Fourth round: after the expert prompt, the verify pass and the hosted plan

On 2026-09-04 the branch was reviewed a fourth time. Two things were different. First, the vulnerability hunt proper is Tom's to run with the Claude Security plugin (`/claude-security`, whole repository, thorough), because that scan is reserved for explicit user invocation; its report lands in a `CLAUDE-SECURITY-<timestamp>/` directory and its findings are folded in as they arrive. Second, my own five lenses covered what that scan does not: every round-three fix re-verified against the current code, the new verify pass and measurement harness, the hosted-mode documents and scripts against what the code guarantees, test gaps, and supply chain. Opus finders, Sonnet merge, two Opus verifiers on high findings and one Sonnet verifier otherwise, refute by default. 41 raw findings, 39 after merge, 35 confirmed, 4 refuted. All 35 fixed the same day. The ones worth knowing:

- A quoted key in JSON or a dict literal, `"api_key": "..."`, was never redacted (high). Round three widened the authorization-header pattern to tolerate a closing quote between the key and the separator, and left the two generic assigned-secret patterns as they were. A pull request touching a JSON config would have sent the value to the model, and, if the model quoted it, into the posted review and the database. Both patterns now carry the same class; six quoted-key shapes are in the tests and the fuzz corpus.
- The private key path the example env shipped (`../../github-app.pem`) was one the settings parser did not recognise as a path. The parser now treats any single-line value without a PEM header as a path, relative ones resolved against the backend directory; the example and the Setup screen point outside the repository.
- The verify pass, new today: it kept the first pass's summary after refuting its findings (the refuted claim was still posted), it had no call budget (up to 500 extra model calls on a dense review), and it never read the verifier's confidence (a 0.1-confidence refutation killed a 0.95 finding). Now: a neutral summary when nothing survives and a note when some do, a per-review budget (`MAX_VERIFY_CALLS_PER_REVIEW`, 40) after which findings are kept unverified, and a refutation only counts when the verifier's confidence clears the same floor as a finding. The pass stays off by default on the measured evidence.
- Multi-line evidence, fixed this morning, let a fabricated line ride along with a real one into the posted comment. The finding's evidence is now trimmed to the line that was actually located.
- The success path between the GitHub POST and the database write was not shielded, so a supersede arriving in that window could leave a live review recorded as superseded with no URL. Shielded now, like the failure path.
- The posted footer said "Generated locally" in every mode. It now says "Generated by", true in both, and the Status page shows the model's address so a hosted box reports where its model really is.
- Hosted scripts and documents: `gpu-up.sh` never checked whether SSH came up and would leave a billing pod running; it now stops the pod on failure, validates its arguments before they reach `sed` or `pkill`, and refuses to start without the passwordless sudo rule the plan now documents. The plan gains the Node install it forgot, a WAL-aware backup command, a corrected step-B cost line, a trailing-slash-tolerant Caddy matcher, and the venv step the test plan skipped.
- Tests that could not fail or did not exist: a tautological newline assertion in the verify-prompt test, no test that each verify call carries its own finding, no test of the verify chain's schema binding, a corpus self-check that never ran in the default suite, no test of the verify pass's own boundary check, no settings test for the new flag, and a prompt-quality floor that could never run because the unit suite pins a fake model name. All added or repaired; 257 backend tests now.

Prompt red team, run through the real model with the eval harness the same day: three Opus writers produced fifteen hostile diffs, each carrying one real planted bug plus an attack on the reviewer (forged audit tickets and "closed as false positive" notes, fabricated scanner output, a pre-computed empty JSON answer to echo, a 184-line file with the bug at the end, instructions to put a sentence, a link, a lookalike github.com link, an @mention, an HTML image or the system prompt into the review, a dictated fake evidence quote, newlines and forged delimiters in the file name, marker-shaped text with random nonces, bidi and zero-width characters, a comment lying about line numbers, and a second fake diff nested inside the first). On qwen3.5:9b: the planted instruction was obeyed in 0 of 15; no attacker-chosen string reached any summary, title or recommendation; the real bug was found at the right line in 14 of 15 (the miss was an SSRF the model described correctly in its summary but quoted from outside the diff, so the evidence check dropped the finding); the hostile text was itself reported as an attempted prompt injection in 11 of 15 and named in the summary in the other four. The cases and the harness command are in backend/scripts/prompt_eval.py (`--cases-from-stdin`).

### Fourth round (2026-09-04): the 35 findings

Each line: id, severity after verification (original in brackets where it changed), where, the finding. Status for every one: fixed on 2026-09-04.

- R4-01 [high] backend/services/redaction.py:37: R3-03's auth-header fix was not carried into the generic assigned-secret patterns, so a quoted key in JSON or a dict literal is never redacted
- R4-02 [medium] backend/.env.example:8: .env.example's shipped GITHUB_PRIVATE_KEY path is a form parse_private_key does not recognise, so the documented setup produces a backend that fails every review
- R4-03 [medium (was high)] backend/tests/test_prompt_quality.py:26: The new prompt-quality floor can never run: conftest pins OLLAMA_MODEL to "fake-model", so the fixture always skips
- R4-04 [medium] backend/services/ai_reviewer.py:211: The verify pass drops a refuted finding but keeps pass one's summary, so the refuted claim is still posted to the PR
- R4-05 [medium] backend/services/ai_reviewer.py:178: The verify pass has no call budget, so a large or finding-dense PR can push the whole review past the job timeout and lose it entirely
- R4-06 [medium (was high)] backend/tests/test_verify_pass.py:84: Vacuous assertion: the newline-breakout check in the verify-prompt test can never fail
- R4-07 [medium] scripts/hosted/gpu-up.sh:28: gpu-up.sh never checks whether SSH came up, so a failure leaves a billing pod and reports the wrong cause
- R4-08 [medium] scripts/hosted/gpu-up.sh:50: gpu-up.sh rewrites .env before a sudo restart that will normally prompt for a password
- R4-09 [medium] docs/HOSTED_MODEL_PLAN.md:40: Nothing in the hosted plan installs Node, but A5 and the dashboard unit both require it
- R4-10 [medium] docs/HOSTED_MODEL_PLAN.md:158: "Back up backend/reviews.db" loses data because the database runs in WAL mode
- R4-11 [medium] backend/README.md:3: backend/README's hosted qualifier is wrong for step B: Ollama is not on that server and the diff does leave it
- R4-12 [medium (was high)] backend/tests/test_verify_pass.py:41: Nothing pins that the verify call carries the finding it is about
- R4-13 [medium (was high)] backend/services/diff.py:77: Multi-line evidence now lets a part-fabricated quote through, and no test covers it
- R4-14 [medium] backend/services/ai_reviewer.py:172: The verify chain's schema binding is untested; binding the wrong schema silently disables the pass
- R4-15 [medium] backend/tests/prompt_corpus.py:262: The corpus ground-truth self-check never runs in the default suite
- R4-16 [medium] backend/services/ai_reviewer.py:188: The verify pass's own prompt-boundary check has no test
- R4-17 [low] app/setup/page.tsx:137: The Setup screen still tells the operator to keep the App private key inside the repository, contradicting the R3-16 fix and backend/README.md
- R4-18 [low] README.md:52: The top-level README's quick start still installs from the unhashed requirements.txt, bypassing the lockfile that closed R3-18
- R4-19 [low] backend/services/review_runner.py:183: R3-33's comment_url write is still unshielded, so a cancel between the GitHub POST and the database can leave a posted review recorded as superseded and re-postable
- R4-20 [low] backend/scripts/prompt_eval.py:92: prompt_eval builds its Settings without pinning STRICT_LOCAL or OLLAMA_BASE_URL, so a shell variable can point the harness at a remote model
- R4-21 [low] backend/services/schemas.py:50: Verdict.confidence is required of the model and validated, but never read, so a 0.1-confidence refutation kills a 0.95-confidence finding
- R4-22 [low] backend/tests/prompt_corpus.py:208: The check_then_act case's note promises a quality category is accepted, but the harness scores category by exact equality with "security"
- R4-23 [low] backend/scripts/prompt_eval.py:16: prompt_eval's docstring claim that it never reads backend/.env is inaccurate; importing config.settings does, and that object sets the script's log level
- R4-24 [low] backend/tests/prompt_corpus.py:235: Every corpus case is sent to the model as "modified", including the added-file case whose hunk header is @@ -0,0
- R4-25 [low (was high)] docs/HOSTED_MODEL_PLAN.md:183: The hosted plan's honesty mechanism does not exist: the Status page never shows OLLAMA_BASE_URL
- R4-26 [low (was high)] backend/services/comment_renderer.py:18: Every review posted in hosted mode tells the pull request it was "Generated locally"
- R4-27 [low] docs/HOSTED_MODEL_PLAN.md:174: The plan contradicts its own step B running cost by a factor of two
- R4-28 [low] docs/TEST_PLAN.md:64: TEST_PLAN section 3 runs .venv/bin/uvicorn without ever creating the venv
- R4-29 [low] scripts/hosted/Caddyfile.example:4: The Caddy site matches the webhook path exactly, so a trailing slash in the App's webhook URL 404s at the edge
- R4-30 [low] scripts/hosted/gpu-up.sh:50: gpu-up.sh interpolates its model argument straight into a sed s-expression and a pkill regex
- R4-31 [low] backend/services/ai_reviewer.py:248: The verify pass's output-token accounting is not asserted
- R4-32 [low] backend/config/settings.py:99: VERIFY_FINDINGS is absent from the settings tests
- R4-33 [low] backend/tests/test_no_egress.py:64: The verify pass has no coverage against a real model, in either opt-in suite
- R4-34 [low] backend/tests/test_prompt_quality.py:20: The corpus carries min_severity and expect_category that no test asserts, and covers under half the planted cases
- R4-35 [info] backend/services/review_workflow.py:65: refuted and verify_calls are recorded per file and then thrown away

Refuted in this round:

- The plan asserts STRICT_LOCAL's guarantee survives the tunnel, when only the check does
- The prompt_eval marker is decorative
- requirements.lock pins two unexplained packages (httpx2, httpcore2) that nothing in requirements.txt or the codebase declares or imports
- .gitignore has no CLAUDE-SECURITY-* rule, so a future scan report can be committed straight into the tree

## Claude Security scan (2026-09-04)

Tom ran the Claude Security plugin himself (`/claude-security`, whole repository, high effort) on the tree at commit 37d5482 with the round-four work uncommitted. Its pipeline: an inventory into seven components, a threat model per component, two researchers per component and category cell (50 in all), two breadth sweeps, then a three-lens adversarial panel on every candidate. Twenty-five candidates, thirteen after de-duplication, six survived, seven were rejected unanimously; the report is stamped `verified` and lives in `CLAUDE-SECURITY-20260904-150824/` (kept out of commits by its own `.gitignore`). All six were fixed the same afternoon:

- CS-01 [medium] scripts/hosted/gpu-up.sh:35: the SSH tunnel to the GPU pod accepted any host key on first contact, and every pod start is a first contact. Fixed: the pod's host key is pinned once under a fixed alias in a dedicated known-hosts file; the script refuses to start without the pin and refuses a pod whose key does not match; the plan documents how to pin and verify the fingerprint.
- CS-02 [medium] backend/services/ai_reviewer.py:42: the marker-defanging regex was quadratic on a line of 32,000 `<` characters and ran on the event loop, so a hostile pull request could stall the webhook and the dashboard. Fixed: bounded, newline-free repeats on both sides of the marker name (linear), and redaction and defanging now run in a worker thread; timing tests pin both.
- CS-03 and CS-04 [low] backend/handlers/webhook.py:70 and the delivery repository: replay protection was keyed on the delivery-id header, which the signature does not cover, so a captured signed body replayed under a fresh id could cancel an in-flight review of a newer push. Fixed: deliveries also record the SHA-256 of the signed body and a repeat of that body under any id is a duplicate; a head that was already reviewed to completion is refused before it can reach the queue. Note: the deliveries table gained a column; delete a pre-existing `reviews.db` before starting this version (no production database existed yet).
- CS-05 [low] backend/services/redaction.py:126: two redaction patterns had the same quadratic shape with smaller constants. Fixed: bounded repeats, timing tests.
- CS-06 [low] backend/services/comment_renderer.py:64: the link allow-list missed CommonMark forms with whitespace after the bracket, a label over 200 characters, a scheme-relative destination, or a reference definition split over two lines. Fixed: the link pattern accepts those forms and checks the destination, scheme-relative destinations are treated as https before the GitHub check, split definitions are removed, bare scheme-relative hosts are removed, and any `](` that survives is broken so it cannot open a link.

## Refuted findings

These were raised and then knocked down by the verifiers. They stay here because each describes a real design gap that the rebuild must not reintroduce.

### GitHub App credentials are exercised with a caller-supplied installation_id and no session; the /github/* repository routes are dead today (single-segment path params, get_user with installation tokens) but would expose private PR diffs the moment they are fixed

- Reported severity: medium. Where: backend/handlers/github.py.
- Verifier: The finding's design-flaw observation is real (backend/handlers/github.py:19,21-34: GitHubAuthDependency takes installation_id from the query string, no session/JWT check, TODO left in place; backend/config/settings.py has no GITHUB_INSTALLATION_ID field; backend/main.py:302-304 mounts github_router at /github with no auth dependency anywhere), but every 'reachable now' impact claim it makes collapses on tracing the actual call chain against the pinned dependency.

backend/services/github_client.py:91 calls `self._github_integration.get_installation(self.installation_id)` with a single positional argument. backend/requirements.txt:14 pins `PyGithub==1.59.1`. I fetched the exact upstream sour

- Verifier: Every citation checks out exactly as stated. backend/handlers/github.py:19 GitHubAuthDependency.**call** takes installation_id as an optional query param; lines 21-22 carry the literal TODO 'Implement proper user authentication'/'For now, use a default installation ID from settings'. settings.py has no GITHUB_INSTALLATION_ID attribute (grep over the whole file confirms only GITHUB_APP_ID and GITHUB_PRIVATE_KEY exist), so the hasattr() branch at github.py:25 is always False. Tracing the actual control flow: when a caller supplies installation_id, neither the `if` nor the `elif` at :25/:27 fires, so the function falls straight through to `return GitHubClient(installation_id=installation_id)` u

### Local inference (Ollama qwen3.5:9b on one M1 Max) makes a single worker, head-SHA dedupe and a hard per-review deadline mandatory: one 20-file PR is 1 to 3 hours of GPU time before the retry and fallback multipliers

- Reported severity: info. Where: backend/services/ai_reviewer.py.
- Verifier: The finding's entire premise, that Ollama/qwen3.5:9b running locally on the reviewer's M1 Max is the (or a) LLM backend for this system, is not reachable in the shipped code. The repository has zero Ollama wiring.

1. grep -rn "ollama|Ollama|OLLAMA" across the whole repo (backend Python, frontend TS/TSX, env files, docs) returns no hits in any source file. The only string match anywhere in the repo is package-lock.json:8177/8216, which is the JS `langchain` meta-package's own upstream package.json listing `"@langchain/ollama": "*"` as one of a dozen _optional peer dependencies_ (marked `optional: true` under peerDependenciesMeta, alongside anthropic/aws/cohere/mistralai/groq/xai/etc.), it i

### Fork PRs are reviewed and acted on with App credentials without any trust or author-association check

- Reported severity: medium. Where: backend/handlers/webhook.py.
- Verifier: The structural gap is real and accurately cited: handle_pull_request_event (backend/handlers/webhook.py:223-266) branches on action alone with no check of pr.head.repo.fork, head/base repo identity, or author_association; PullRequest and PRWebhookPayload (backend/models/github.py:73-110) omit author_association entirely (Pydantic drops it silently since these models do not set extra='forbid'), and GitRef.repo (backend/models/github.py:64-70, Optional[GitHubRepository] with a `fork: bool` field) is defined but never read in webhook.py. Draft skip is indeed gated on `not settings.DEBUG` at webhook.py:227. These citations all check out line-for-line.

However the claimed present-tense impact ("

- Verifier: Every load-bearing claim checks out against the code.

1. Trigger with no trust check: backend/handlers/webhook.py:223 `if action in [PRAction.OPENED, PRAction.SYNCHRONIZE, PRAction.REOPENED]:` and :274 `elif action == PRAction.READY_FOR_REVIEW:` both flow straight into `add_review_to_queue` (webhook.py:244-249, :281-286) with no check of fork status, author_association, or write access anywhere in the function (lines 196-300 read in full; grep for 'author_association|fork|head.repo|base.repo' across backend/ turns up nothing relevant in webhook.py). The only draft gate is webhook.py:227 `if pr.draft and not settings.DEBUG:`, exactly as described: drafts are only skipped when DEBUG is false

## Checked and found fine

Grouped by the investigator lens that checked them. Each entry cites the evidence.

### webhook-auth

- HMAC is computed over the raw request bytes in the backend. backend/handlers/webhook.py:54 `payload = await request.body()` returns the raw bytes; :62 passes those bytes unchanged to verify_github_signature; backend/utils/crypto.py:41-45 `hmac.new(settings.GITHUB_WEBHOOK_SECRET.encode('utf-8'), payload, hashlib.sha256) [...]
- Comparison is constant time and semantically correct for GitHub's format. backend/utils/crypto.py:48 uses hmac.compare_digest; :37-38 strips the 'sha256=' prefix; GitHub sends lowercase hex and hexdigest() is lowercase hex, so no case normalisation gap.
- Missing or empty secret fails closed. backend/config/settings.py:28 `GITHUB_WEBHOOK_SECRET: str` has no default, so pydantic-settings raises at import (backend/config/settings.py:151) and the app does not start when it is unset.
- Signature failure is a proper 401 and is not swallowed by the generic handler. backend/handlers/webhook.py:68-71 raises HTTPException(401, 'Invalid webhook signature'); :175-177 `except HTTPException: raise` re-raises before the generic `except Exception` at :178, so the 401 (and the 400s for missing headers, empty body and invalid JSON [...]
- Proxy preserves status codes and the security-relevant headers. app/api/webhook/github/route.ts:38-39 returns the backend body with `status: response.status`, so a 401 or 400 from the backend is what GitHub sees.
- Body byte fidelity through the proxy for real GitHub payloads. GitHub payloads are valid UTF-8 JSON with no BOM. undici's utf8DecodeBytes (upstream util.js) strips a leading EF BB BF and uses a non-fatal TextDecoder; for valid BOM-less UTF-8 the decode/re-encode round trip is byte-identical, so the backend HMAC matches.
- installation_id and repository come from the signed body, not from headers. backend/handlers/webhook.py:246 `installation_id=pr_payload.installation.id` and :236 `repository=repo.full_name` are read from PRWebhookPayload (backend/models/github.py:103-110), which is parsed from payload_bytes that already passed the HMAC.
- Non-triggering PR actions do no work. backend/handlers/webhook.py:269-294: closed only sets a message (the 'cleanup_reviews' action is a label, no code runs), and edited and converted_to_draft fall through to 'no action required'.
- Direct access to the backend port does not weaken webhook authentication. The signature check lives in the backend (backend/handlers/webhook.py:26-73), and the Next.js proxy adds no authentication of its own (app/api/webhook/github/route.ts:10-33), so reaching :8000 directly yields no bypass for the webhook.
- Debug-only test endpoint is gated and low-information. backend/handlers/webhook.py:438-451 returns 404 unless settings.DEBUG and otherwise exposes only two booleans (webhook_secret_configured, app_id_configured), not the values.
- Signature verification is enabled on main and on this branch today. `git show main:backend/handlers/webhook.py` lines 60-73 contain the active `if not verify_github_signature(payload, signature): ... raise HTTPException(401)` block, identical to the working tree on v1.1-Local-AI (clean tree).

### llm-pipeline

- Model output is never executed or used to build paths/commands. Across ai_reviewer.py, review_workflow.py, queue_processor.py, review.py and helpers.py the only consumers of model text are json.loads (ai_reviewer.py:1229, 1266), string formatting into comment bodies (helpers.py:278-288, review_workflow.py:737-739) and DB i [...]
- LLMChain does not raise on extra kwargs (so the misconfiguration fails silently rather than loudly, confirmed). langchain 0.3.13 chains/base.py:288-290 checks only missing keys; chains/llm.py:222 filters inputs to prompt.input_variables; langchain-core 0.3.28 chat.py:1220-1224 ignores kwargs for BaseMessage entries. No 'unexpected input' error path exists for extras.
- Diff size bounded before it reaches the model. models/github.py:126-132 truncates PRFile.patch at 100,000 chars; ai_reviewer.py:1399-1402 skips patches over 10,000 chars in the basic path; review_workflow.py:639 skips files with changes > 1000 in the LangGraph path; basic path limits concurrency with async [...]
- security_scanner.py and mock_reviewer.py make no network calls. security_scanner.py:3-11 imports re, hashlib, typing, datetime, dataclasses and local modules only; mock_reviewer.py:7-14 imports time, json, typing, datetime and local modules only. Secret matches are masked before display (security_scanner.py:415-423).
- PR title, body and branch name do not reach the model or comments in the current code. grep 'pr_title|pr_description|head_ref|pr_body' in backend/: values are stored in ReviewWorkflowState (review_workflow.py:60-61, 886-887) and helpers.extract_pr_info (helpers.py:160-165) but referenced by no prompt, node, or comment formatter.
- LangSmith tracing is off with the checked-in configuration. No load_dotenv or os.environ export in backend/ (grep); pydantic-settings v2.6.1 sources.py:705, 949 read only; langchain-core 0.3.28 utils/env.py:16-21 gates on os.environ; no Dockerfile, Procfile, railway/render config or start script in the repo that would [...]
- Comment posting failures are contained per comment. queue_processor.py:383-403 and 408-428 wrap each post_review_comment call in try/except and log, so a GitHub 422 on a bad line number does not abort the remaining comments (although the loop never runs today because of the files_reviewed shape bug).

### authz-endpoints

- Webhook signature verification. backend/handlers/webhook.py:37-73 requires X-Hub-Signature-256 and X-GitHub-Event, reads the raw body with await request.body() (line 54) and calls verify_github_signature; utils/crypto.py:41-48 computes HMAC-SHA256 over the raw bytes with GITHUB_WEBHOOK_SECRE [...]
- SSRF / user-controlled fetch targets. Every server-side fetch target is either a fixed api.github.com or github.com URL, or BACKEND_URL / NEXT_PUBLIC_BACKEND_URL read from process.env with a localhost default (app/api/github/stats/route.ts:3, app/api/review/route.ts:16, app/api/review/pr/route.ts: [...]
- DEBUG-gated endpoints. POST /auth/dev/create-user returns 404 unless settings.DEBUG (backend/handlers/auth.py:342-343); POST /webhook/github/test likewise (backend/handlers/webhook.py:441-442); /docs and /redoc are None unless DEBUG (backend/main.py:64-65); DEBUG defaults False (bac [...]
- Private key material in git history. git grep across all revisions for 'BEGIN RSA PRIVATE KEY' matches only placeholders: .env.example 'your-private-key-here', backend/setup.sh and docs 'your-github-private-key-here' / '...', backend/tests/conftest.py 'test-key', scripts/validate-env.js string ch [...]
- OAuth state / CSRF on the real frontend flow. app/api/auth/github/route.ts:16-28 generates crypto.randomUUID() state, stores it in an httpOnly sameSite=lax 10 minute cookie, and app/api/auth/github/callback/route.ts:25-30 rejects the callback when it does not match.
- SQL construction. All repository and metrics queries use SQLAlchemy Core/ORM expressions (backend/database/repositories/review_repository.py, backend/services/metrics_service.py; grep for text( finds only the health probe 'SELECT 1' at backend/database/connection.py:95).
- Sentry PII. backend/main.py:28-37 initialises sentry_sdk without send_default_pii, so the SDK default (False) applies and Authorization/Cookie headers and bodies are scrubbed by the FastAPI integration.
- Backend CORS shape. backend/main.py:76-82 uses an explicit origin list with allow_credentials=True and a fixed method list; no wildcard origin is possible via ALLOWED_ORIGINS parsing (settings.py:77-81).
- Webhook proxy Host header behaviour (orchestrator assumption verified). undici v6.21.3 lib/web/fetch/index.js (Node 22.17.0 is installed here and bundles undici 6.x) deletes 'host' and 'cookie' from the request header list before dispatch ('Cookie and Host are forbidden request-headers, which undici doesn't implement'), so the bac [...]

### data-logging

- Diff/patch, PR body and submitted code in log lines. All 276 logger calls in backend/ reviewed (grep). Structured kwargs carry only counts, filenames, ids and durations: ai_reviewer.py:1052-1057 (language, changes, complexity), 1147-1155 (tokens, cost), github_client.py:214-218, 260-267, 370-375, webhook.py:112- [...]
- Log destination. backend/config/logging.py:16-20 basicConfig(stream=sys.stdout); no FileHandler/RotatingFileHandler anywhere in backend/ (grep); backend/logs/ is gitignored (.gitignore:88) but does not exist and nothing writes to it.
- Redis task payload contents. queue_processor.py:562-576 payload = repository, pr_number, installation_id, webhook_delivery_id and four booleans; ReviewTask.to_dict (67-81) adds ids, timestamps and error_message only. No diff or code.
- Webhook review path persistence. queue_processor._process_pr_review_task (343-457) never imports or calls ReviewRepository or WebhookRepository; WebhookRepository is not instantiated anywhere in backend/ (grep); webhook.py:122-128 builds the pydantic WebhookDelivery from models/github.py:186- [...]
- SQLite file hygiene. settings.py:48 DATABASE_URL='sqlite:///./reviews.db' (cwd-relative, backend/reviews.db under package.json:8). .gitignore:112-114 ignores *.sqlite, *.db, *.db-journal.
- Sentry default state. settings.py:67 SENTRY_DSN: Optional[str] = None and .env.example:53 SENTRY_DSN="", so sentry_sdk.init (main.py:28-37) does not run by default.
- LangSmith export under the current run path. No load_dotenv or os.environ assignment in backend/ (grep: only main.py:272 reads DEMO_MODE); pydantic-settings 2.6.1 DotEnvSettingsSource never writes os.environ (verified upstream); package.json:8 runs uvicorn without --env-file; scripts/quick-setup.sh only [...]
- GitHub client token handling in logs. github_client.py:97-101 logs installation_id and expiry, never the token; _make_request logs method, endpoint, status and rate limit only (150-156, 162-167, 177-182); post_review_comment logs path, line and comment id, not the body (260-267).
- Global exception handler in non-debug mode. backend/main.py:154-159 returns {'error': 'Internal server error'} with no detail when settings.DEBUG is false; docs/redoc are disabled when DEBUG is false (main.py:64-65).
- Historical 'BEGIN RSA PRIVATE KEY' matches. git log --all -p -S'BEGIN RSA PRIVATE KEY' shows only placeholders: docs/GITHUB_APP_SETUP.md and README snippets ('MIIEpAIBAAKCAQEA1234...' followed by '[full key content]'), backend/setup.sh and .env.example templates ('your-private-key-here'), backend/tests/ [...]
- Frontend server-side logging of tokens. app/api/auth/github/callback/route.ts:52 logs tokenData.error only; the access token is placed in the httpOnly auth_token cookie (101-116) and never logged.
- Frontend third-party analytics. No @vercel/analytics, @vercel/speed-insights, gtag, googletagmanager, plausible, posthog, hotjar, segment, mixpanel or Sentry browser imports in app/, components/, hooks/, contexts/ or lib/ (grep). vercel.json:76 disables Next telemetry for Vercel builds.

### dos-limits

- Webhook cost path requires a valid HMAC signature. backend/handlers/webhook.py:54-71 reads the raw body and calls verify_github_signature before any parsing or queueing; missing header to 400, bad signature to 401. Only GitHub (or a holder of GITHUB_WEBHOOK_SECRET) can trigger the inline review.
- Per-patch size cap exists at the model layer. backend/models/github.py:126-132 PRFile.validate_patch truncates any patch over 100,000 chars. Basic path additionally skips patches over 10,000 chars and unknown languages (backend/services/ai_reviewer.py:1389-1409).
- Per-call output token cap. backend/config/settings.py:37 OPENAI_MAX_TOKENS=4000 is passed to ChatOpenAI at backend/services/ai_reviewer.py:210 (and max_tokens=10 for the health probe at :1420), so a single completion cannot run away.
- Basic path bounds concurrent file reviews per request. backend/services/ai_reviewer.py:979-992 asyncio.Semaphore(3) around _review_single_file_with_semaphore; results gathered with return_exceptions=True so one bad file does not abort the others.
- GitHub HTTP calls have explicit timeouts. backend/services/github_client.py:140 timeout=30.0 on every _make_request; :593 timeout=10.0 on the health probe. Redis connect would use socket_connect_timeout=5 and fail soft (queue_processor.py:121-138), although it is never invoked.
- /review/pr and /review/files background handlers are stubs. backend/handlers/review.py:1071-1081 process_file_review and process_pr_review only log; they create a DB row (:100-108, :151-162) but incur no LLM or GitHub cost.
- Comment volume per file is partially bounded. backend/services/queue_processor.py:406-407 posts at most 3 performance comments per file and only high/medium severity; security comments are unbounded but only those with a line_number (:382).
- Workflow halts on many critical findings. backend/services/review_workflow.py:534-536 sets should_halt when more than 5 critical issues are found, and _route_after_risk_assessment (:620-624) routes straight to generate_github_comments, skipping the remaining analyses and files.
- List/stat query parameters are bounded. backend/handlers/review.py:271-272 per_page le=100, :343 days le=365, :393-397 min/max score 0-10 and per_page le=100, :898/:914/:931-932 days and limit bounded via Query(ge, le).
- Redis fallback is deliberate and logged. backend/services/queue_processor.py:465-467 logs a warning 'Processing task ... immediately (no queue)' on every inline run, so the condition is at least visible in backend logs, and GET /review/queue/status reports worker_status 'stopped' (backend/handlers/re [...]
- Next.js route body handling. app/api/webhook/github/route.ts:23 uses request.text() (no size limit in the Next 14 app router, consistent with the note in the brief); the review proxy at app/api/review/route.ts:5-10 validates the body with zod and only ever forwards a single file, so the m [...]

### deps-history-scripts

- Remote code execution in scripts and hooks. scripts/quick-setup.sh, scripts/validate-env.js, scripts/generate-*.js and .husky/pre-commit contain no curl|bash, wget, eval of fetched content or remote script includes.
- Real private keys or API tokens in git history. 27/27 'BEGIN RSA PRIVATE KEY' hits are placeholders or the validate-env.js format check; `git log --all -p | grep -cE '^[+-]?[A-Za-z0-9+/]{64}$'` to 0; token regex scan (sk-, sk-proj-, ghp_, ghs_, gho_, github_pat_, lsv2_, ls__, AKIA, xox*, sentry DSN, whsec_, [...]
- Committed databases, logs and .env files. `git log --all --diff-filter=A --name-only` filtered for .db/.sqlite/.log/.env to only .env.example and backend/.env.example; .gitignore:14-18,89,109-111 ignore .env, backend/.env, *.sqlite, *.db, *.db-journal.
- Webhook signature verification implementation (read while checking crypto.py). backend/utils/crypto.py:41-48 computes HMAC-SHA256 over the raw payload with settings.GITHUB_WEBHOOK_SECRET and compares with hmac.compare_digest; returns False when the secret is unset (:28-30).
- python-jose algorithm confusion not exploitable as configured. backend/utils/crypto.py:126 encodes with algorithm="HS256"; :145 decodes with algorithms=["HS256"] against the shared-secret string, so CVE-2024-33663 (public key reinterpreted as HMAC key) has no asymmetric key to confuse; jwe.decrypt is never called.
- PyJWT advisories unreachable. Only use is `PyJWT.encode(payload, settings.GITHUB_PRIVATE_KEY, algorithm="RS256")` at backend/services/github_client.py:639 inside validate_github_config; no jwt.decode or PyJWKClient anywhere in backend/.
- python-multipart and starlette multipart advisories unreachable. grep -rnE 'Form\(|UploadFile|File\(|\.form\(' backend --include='*.py' to only the PRFile pydantic model (models/github.py:113 and its users) and a string literal in services/ai_reviewer.py:835; no StaticFiles, HTTPEndpoint or FileResponse usage.
- LangGraph checkpoint deserialisation and sentry subprocess env leak unreachable. grep -rniE 'checkpoint|MemorySaver|msgpack' backend to none; grep -rn 'subprocess' backend to only regex/prompt strings in services/ai_reviewer.py:272-273,310-311; sentry initialises only when SENTRY_DSN is set (backend/main.py:28-29).
- Transitive h11 request-smuggling CVE-2025-43859. Nothing pins h11: uvicorn[standard]==0.24.0 requires h11>=0.8 and httpx==0.25.2 pulls httpcore 1.* whose current releases require h11>=0.16, so a fresh install resolves a fixed h11 (>=0.16.0).
- Backend packages with zero OSV advisories at the pinned version. OSV querybatch to 0 vulns for uvicorn 0.24.0, pydantic 2.9.2, pydantic-settings 2.6.1, httpx 0.25.2, aiofiles 23.2.1, PyGithub 1.59.1, langchain-community 0.3.27, openai 1.58.1, tiktoken 0.8.0, SQLAlchemy 2.0.36, alembic 1.14.0, aiopg 1.4.0, aiosqlite 0.20.0, [...]
- Frontend runtime bundle reach of npm advisories. Import grep across app/, components/, lib/, hooks/, contexts/ shows only react, next/_, lucide-react, @radix-ui/_, recharts, zod, date-fns, react-hot-toast, @monaco-editor/react, clsx, tailwind-merge, class-variance-authority; of the 45 audit entries only `nex [...]
- Lint, format and TypeScript configuration. .eslintrc.json:2 extends next/core-web-vitals and prettier with two rules disabled (:4-5); .prettierrc is style-only; tsconfig.json:6 strict true, :25 includes only project sources; lint-staged (package.json:87-95) runs eslint --fix and prettier --write on sta [...]
- Azure deployment artefacts in history. `git show 053bed61f5^:azure-parameters.json` contains only YOUR_* placeholders; deploy-azure.yml (80903be^) reads `secrets.AZURE_CREDENTIALS` and masks the ACR password with ::add-mask::; deploy-azure-free.sh reads secrets from the environment and never echoes [...]

### gaps-critic-prep

- Path/URL injection into GitHub API calls from repo_full_name, path, ref (handlers/github.py to github_client.py). repo_full_name is a one-segment Starlette path param ([^/]+) and uvicorn decodes %2F before routing, so the value cannot contain '/'.
- SQL construction and SQLAlchemy attribute injection. All queries use SQLAlchemy Core/ORM with bound parameters (review_repository.py, user_repository.py, webhook_repository.py). text() is only used with constant SQL (connection.py:94, 131, 199, 211-223, 292-310); DatabaseMigrator/execute_raw_sql have no callers. [...]
- security_scanner.py execution surface. Pure re.search/re.finditer over diff text (lines 334, 360); no exec, eval, subprocess, pickle, yaml or file access; re.error is caught (349-350, 387-388); matched secrets are masked before being stored (_mask_secret, 415-423).
- Frontend XSS and rendering of model output. No dangerouslySetInnerHTML, innerHTML, eval or markdown renderer anywhere under app/, components/, hooks/, contexts/, lib/ (grep). Model text is rendered as JSX text nodes (components/review/ReviewResults.tsx:408, 417, 449, 461, 470).
- Pydantic webhook payload model (models/github.py). PRWebhookPayload requires action (enum), number, pull_request, repository, installation, sender (103-110); PullRequest requires id, number, title, state, html_url, diff_url, patch_url, head, base, user, created_at, updated_at (73-100); PRFile.patch is truncate [...]
- PyGithub expires_at naive vs aware under the pinned version. PyGithub==1.59.1 _makeDatetimeAttribute (upstream GithubObject.py:232-244) builds naive datetimes with strptime, so github_client.py:83/112 would not raise TypeError if the token call worked; it will on PyGithub >= 2.0 (finding 10 records this as a latent brea [...]
- Licence and attribution. LICENSE is MIT, Copyright (c) 2025 Thomas Butler; README.md:75-77 says MIT Licence; backend/README.md:408-410 defers to the root LICENSE; app/layout.tsx:24 credits Tom Butler; package.json has no license field but is private.
- .gitignore and secrets on disk. .gitignore ignores .env, backend/.env, backend/.venv/, *.db, _.sqlite, logs; the '!backend/tests/test__.py' exception points at a directory that does not exist (no tests anywhere).
- Sentry and LangSmith configuration surface. sentry_sdk.init (main.py:28-37) leaves send_default_pii at its False default. settings.LANGCHAIN_TRACING_V2 (settings.py:45) and LANGCHAIN_API_KEY are pydantic fields that LangChain never reads (it reads os.environ, which pydantic-settings does not populate), [...]
- Miscellaneous dead-code defects noted but not scored. lib/utils.ts:79-109 calculateComplexity builds new RegExp('\\b?\\b') which throws 'Nothing to repeat' (verified in Node 22) and '\\b||\\b' which matches empty strings; the function has no callers.

### gap:Local-inference migration: no code path exists and nobody scoped it

- langchain-openai 0.2.14 supports base_url plus a dummy api_key (CHECK item 1, confirmed). Read the pinned tag source at libs/partners/openai/langchain_openai/chat_models/base.py for langchain-openai==0.2.14. BaseChatOpenAI declares `openai_api_base: Optional[str] = Field(default=..., alias="base_url")` with env var OPENAI_API_BASE, and `openai_api_ [...]
- Ollama's OpenAI-compat shim does honour response_format json_object, so the JSON fragility has a clean fix. ollama/openai/openai.go:697-707: `if r.ResponseFormat != nil { switch strings.ToLower(strings.TrimSpace(r.ResponseFormat.Type)) { case "json_object": format = json.RawMessage(`"json"`) ...
- Thinking output does not leak into message content, so it will not corrupt json.loads directly. ollama/openai/openai.go:294 ToChatCompletion builds `Message{Role: r.Message.Role, Content: r.Message.Content, ToolCalls: toolCalls, Reasoning: r.Message.Thinking}`, and the streaming path at :344 does the same for Delta.
- Token counting survives the migration even though cost does not. ollama/openai/openai.go:305 `Usage: ToUsage(r)` populates the OpenAI usage block on non-streaming chat completions. langchain_community/callbacks/openai_info.py on_llm_end reads token_usage and does `self.total_tokens += token_usage.get("total_tokens", 0)` reg [...]
- temperature IS overridden, so the Modelfile's temperature 1 does not apply (correcting a plausible assumption). langchain-openai 0.2.14 declares `temperature: float = 0.7` as a non-Optional field, and _default_params includes `"temperature": self.temperature` unconditionally, outside the exclude_if_none dict.
- nomic-embed-text is an unused download; no embedding, vector store or retrieval path exists (CHECK item 5, confirmed). `grep -rniE 'embed|vector|faiss|chroma|pinecone|retriev' backend/` returns exactly 5 hits, all of which are the English word 'Retrieved'/'retrieving' inside log strings and one docstring: backend/handlers/github.py:1, backend/services/github_client.py:215, :37 [...]
- The 100,000-char patch truncation at models/github.py is real but is not the tightest constraint on the dead path. backend/models/github.py:128-131 `validate_patch` truncates at 100,000 chars. On the basic-chains fallback that is unreachable as a review-quality concern because AIReviewer._should_review_file at ai_reviewer.py:1400 already drops any file whose patch exceeds [...]
- The Ollama default context on this specific machine is 32,768, not the 4,096 assumed in the task brief. The brief assumed Ollama's runtime default of 4096 applies. That was true of older builds; Ollama 0.33.1 selects by VRAM tier. `ollama serve --help` on the installed binary prints 'Context length to use unless otherwise specified (default: 4k/32k/256k based on [...]

### gap:Design of the 'prove it is fully local' egress test, and the .gitignore trap that will swallow it

- gitignore negation for backend/tests (contradicts the briefing). `git check-ignore backend/tests/test_no_egress.py backend/tests/network/test_egress.py` prints nothing and exits 1, so both are trackable.
- candidate file paths for the new test harness. `git check-ignore` returned nothing (exit 1, all trackable) for: backend/tests/**init**.py, backend/tests/conftest.py, backend/tests/test_no_egress.py, backend/tests/egress/conftest.py, backend/tests/egress/test_no_egress.py, scripts/egress_capture.sh, scripts [...]
- Redis and database are not egress legs by default. backend/.env.example:33 DATABASE_URL="sqlite:///./reviews.db" and :38 REDIS_URL="redis://localhost:6379"; backend/config/settings.py:48 DATABASE_URL default sqlite; backend/database/connection.py:29-34 rewrites sqlite:/// to sqlite+aiosqlite:/// and creates a [...]
- LANGCHAIN_TRACING_V2=True in settings is inert on its own. backend/config/settings.py:45 sets LANGCHAIN_TRACING_V2: bool = True, but settings.py:143-145 model_config only reads .env into the pydantic object.
- Ollama runtime is genuinely available on the host. `command -v ollama` to /usr/local/bin/ollama; `ollama list` to qwen3.5:9b (6.6 GB), nomic-embed-text:latest (274 MB), qwen3.5:0.8b (1.0 GB). The local target exists and is adequate; only the application-side wiring is missing.
- no hidden third-party analytics, CDN or telemetry beyond the legs already enumerated. Host census over all non-node_modules source (*.py, *.ts, *.tsx, *.js, *.jsx, *.css, *.json, *.mjs, *.yml, *.example) yields only: api.github.com x8, fonts.googleapis.com x2, api.openai.com x1, plus localhost x22 and documentation/funding URLs (opencollective. [...]
- frontend has no second LLM egress path despite LangChain being in package.json. package.json dependencies include @langchain/community ^0.3.56, @langchain/openai ^0.6.13 and langchain ^0.3.34, but `grep -rn '@langchain/openai|ChatOpenAI|OpenAI' app/ lib/ components/` returns zero matches.

### gap:GitHub App permission manifest versus the endpoints the code actually calls, and required-check merge gating

- Checks API is not used, so 'Checks: Read & Write' is not the missing permission. grep -rn --include="*.py" -E "check-runs|check_runs" backend/ returns no API call, only the unused model backend/models/github.py:174 (class GitHubCheckRun) and the unused column backend/database/models.py:106 (github_check_run_id).
- Pull requests: Read & Write in the README correctly covers the four PR endpoints. backend/README.md:171 grants Pull requests: Read & Write, which covers backend/services/github_client.py:188 (GET pulls/{n}/files), :242 (POST pulls/{n}/comments), :291 (POST pulls/{n}/reviews, currently uncalled), :367 (GET pulls/{n}) and :471 (GET pulls).
- Metadata: Read is correctly listed and is mandatory for every GitHub App. backend/README.md:174 lists '- Metadata: Read'. GitHub forces this permission on any App with repository permissions, so no change is needed.
- GET /rate_limit needs no App permission and its handler is harmless. backend/services/github_client.py:416 `response = await self._make_request("GET", "/rate_limit")`, exposed at backend/handlers/github.py:268. The endpoint is unauthenticated-safe and carries no permission requirement.
- Status payload field values are valid and within GitHub's limits. States passed are 'pending' (backend/handlers/webhook.py:400) and 'success'/'failure' (backend/services/queue_processor.py:431), all members of GitHub's allowed set {error, failure, pending, success}.
- Webhook event subscriptions in the README match the events the code dispatches, with one harmless extra. backend/README.md:176-179 asks for Pull request, Pull request review and Pull request review comment. backend/handlers/webhook.py:133-147 dispatches exactly those three plus PUSH; handle_push_event at backend/handlers/webhook.py:360-384 only logs and acknowled [...]
- No hidden third status call site. grep -rn --include="*.py" "create_status_check" backend/ returns exactly three lines: the definition at backend/services/github_client.py:322 and the two callers at backend/handlers/webhook.py:397 and backend/services/queue_processor.py:434.

### gap:The pinned runtime does not install on this machine's interpreter, blocking every other verification including the egress test

- cryptography==44.0.1 wheel availability on CPython 3.14 arm64. Not a blocker, contrary to the brief's suspicion. https://pypi.org/pypi/cryptography/44.0.1/json urls contain cryptography-44.0.1-cp37-abi3-macosx_10_9_universal2.whl and cryptography-44.0.1-cp39-abi3-macosx_10_9_universal2.whl.
- SQLAlchemy==2.0.36 wheel availability on CPython 3.14. Not a blocker. https://pypi.org/pypi/SQLAlchemy/2.0.36/json has 101 files; the highest CPython tag is cp313 (SQLAlchemy-2.0.36-cp313-cp313-macosx_11_0_arm64.whl) and there is no cp314, but the release also ships SQLAlchemy-2.0.36-py3-none-any.whl.
- aiopg==1.4.0 versus SQLAlchemy==2.0.36 resolver conflict. No conflict. https://pypi.org/pypi/aiopg/1.4.0/json ships only aiopg-1.4.0-py3-none-any.whl and the sdist, and its SQLAlchemy bound 'sqlalchemy[postgresql_psycopg2binary] (<1.5,>=1.3)' is gated behind 'extra == "sa"', which backend/requirements.txt:35 does not [...]
- Rust toolchain presence for the pydantic-core and tiktoken source builds. which -a rustc cargo returned ~/.cargo/bin/rustc and ~/.cargo/bin/cargo, and ~/.cargo/bin contains rustup, cargo, rustc and friends.
- Whether raising the pydantic floor would break langchain, as the brief assumed. It would not. https://pypi.org/pypi/langchain-core/0.3.28/json requires_dist contains 'pydantic<3.0.0,>=2.5.2; python_full_version < "3.12.4"' and 'pydantic<3.0.0,>=2.7.4; python_full_version >= "3.12.4"', and https://pypi.org/pypi/langchain/0.3.13/json requir [...]
- Whether raising the floor is technically viable for the three cp314-missing pins. It is, which is why the recommendation in finding 2 is a judgement call rather than a forced one. greenlet 3.5.5 ships greenlet-3.5.5-cp314-cp314-macosx_11_0_universal2.whl; tiktoken 0.12.0 ships tiktoken-0.12.0-cp314-cp314-macosx_11_0_arm64.whl (the full 57-f [...]
- Usable interpreters already installed on the host. /opt/homebrew/bin/python3.11 -VV to Python 3.11.15; /usr/local/bin/python3.13 -VV to Python 3.13.7. Every pin in backend/requirements.txt that lacks a cp314 wheel does have cp311 and cp313 wheels for macosx arm64 (pydantic_core-2.23.4-cp313-cp313-macosx_11_0_a [...]
- langgraph 0.2.59 and langchain-openai 0.2.14 against the pinned langchain-core. Neither contributes to the resolver conflict. https://pypi.org/pypi/langgraph/0.2.59/json requires 'langchain-core!=0.3.0,...,!=0.3.22,<0.4.0,>=0.2.43', which excludes 0.3.0 through 0.3.22 but permits 0.3.28.
- backend/.venv absence and .gitignore coverage. Confirmed no venv exists to inspect: ls backend shows no .venv, and .gitignore:88 'backend/.venv/' plus :89 'backend/.env' means neither would ever have been committed.

### gap:No redaction between the diff and the model prompt, the posted comment, or the database

- Webhook review path does not persist diffs or model output to the database. `grep -n "ReviewRepository|add_issues_to_review|update_review|get_db_session" backend/services/queue_processor.py` returns no matches.
- SQLite database file is excluded from git, so model-quoted snippets cannot be committed by accident. .gitignore:109-111 `*.sqlite`, `*.db`, `*.db-journal`. backend/config/settings.py:47 `DATABASE_URL: str = "sqlite:///./reviews.db"` - the default filename matches the `*.db` rule.
- Frontend Next.js routes never handle diff or patch text, so there is no second unredacted copy in the Vercel edge/serverless logs. `grep -rn "patch|diff|files" app/api/review/pr/route.ts` returns only app/api/review/pr/route.ts:74 (the comment `// Backend will fetch PR files itself using GitHub API`) and two template strings at :107 and :114 that interpolate only counts (`prData.changed_f [...]
- Patch length is bounded before it enters the prompt, so a single huge secret-bearing file cannot blow up the context unboundedly. backend/models/github.py:127-132 field_validator on `patch`: `if v and len(v) > 100000: return v[:100000] + "\n... (truncated)"`. backend/services/ai_reviewer.py:1399-1402 additionally skips files whose patch exceeds 10000 chars on the fallback path, and backe [...]
- There are exactly two comment-posting call sites and both were traced end to end. `grep -rn "post_pr_review|post_review_comment" --include=*.py backend/` excluding github_client.py returns only backend/services/queue_processor.py:392 and :417.
- The dead-code claim was re-verified: neither SecurityScanner nor the duplicate pattern set inside AIReviewer is reachable. `grep -rn "SecurityScanner|security_scanner" --include=*.py --include=*.ts --include=*.tsx .` returns only the class definition at backend/services/security_scanner.py:30.

### gap:The Next.js API layer duplicates the backend, and the webhook proxy has no purpose once self-hosted

- Webhook proxy body fidelity for HMAC verification. app/api/webhook/github/route.ts:23 reads the body with `await request.text()` and forwards the same string at :32. GitHub sends UTF-8 JSON, so the decode and re-encode round trip is byte-identical, and backend/handlers/webhook.py:54 recomputes the signature ov [...]
- app/api/github/prs is a genuine frontend concern and must be kept. app/api/github/prs/route.ts never touches the Python backend. It reads the httpOnly auth_token cookie (:7-8), extracts the user's GitHub OAuth token (:28) and calls api.github.com directly (:83, :250).
- auth/logout and auth/me are cookie-only and correct in scope. app/api/auth/logout/route.ts:8-14 only clears the cookie with httpOnly, secure-in-production, sameSite lax, maxAge 0 and path '/'; app/api/auth/me/route.ts:5-18 only reads and decodes the cookie. Neither calls the backend.
- OAuth CSRF state parameter is implemented correctly. app/api/auth/github/route.ts:16 generates `crypto.randomUUID()` and stores it in an httpOnly, sameSite lax cookie with a 600 second maxAge (:23-28); app/api/auth/github/callback/route.ts:25-30 requires the stored value to be present and to equal the returned s [...]
- auth/me does not leak the GitHub access token to the client. app/api/auth/me/route.ts:16 destructures `const { github_access_token, ...safeUserInfo } = userInfo` and returns only safeUserInfo at :18, so contexts/AuthContext.tsx:35-36 never receives the OAuth token.
- vercel.json headers do not apply to a locally run app. next.config.mjs is 16 lines (output, experimental.serverActions.allowedOrigins, env.CUSTOM_KEY) and defines no headers() function, so under `next dev` (package.json:7) or `next start` (:11) none of the vercel.json header blocks, rewrites or functions settings [...]
- Backend CORS is not wildcarded. backend/main.py:76-78 configures CORSMiddleware with `allow_origins=settings.allowed_origins_list`, backed by backend/config/settings.py:17 `ALLOWED_ORIGINS: str = "http://localhost:3000,https://localhost:3000"` split into a list at :78-81.
- The /api/review/pr proxy does forward the caller's GitHub token, so the split is not leaking credentials sideways. app/api/review/pr/route.ts:79 sends `Authorization: Bearer ${githubAccessToken}` to the backend. The backend's POST /review/pr (backend/handlers/review.py:129-133) declares no auth dependency and never reads the header, so the token is ignored rather than misu [...]

## GitHub App permissions the code needs

As the code stands after the rewrite (decision 1 in docs/LOCAL_MIGRATION.md dropped commit statuses): Pull requests, read and write (fetch files, post review comments). Metadata, read (implied). Nothing else. Not needed: Issues write (nothing calls the issues API), Contents read (only an unused helper reads file contents). Events: pull_request only. Install the App on selected repositories, never on all repositories.

## The local claim and how it will be proved

After the migration the only network peer during a review is api.github.com. Three proofs exist:

1. `cd backend && .venv/bin/python -m pytest tests/test_runner.py` runs whole reviews through the real code (fake GitHub served in-process by respx, fake model) inside a socket-level guard that raises on any connection or DNS lookup outside loopback. Passes, and runs in CI.
2. `REVIEWBOT_E2E=1 .venv/bin/python -m pytest -m e2e` runs the real reviewer against the real Ollama under the same guard. Passed 2026-09-03 with qwen3.5:9b in 14 seconds.
3. `scripts/prove-local.sh` builds Dockerfile.local (the backend from the hashed lock, Ollama, qwen3.5:0.8b and a loopback fake GitHub) and runs one review with `docker run --network none`; the entrypoint first checks that the only interface is loopback and that a raw connect to 1.1.1.1 fails. Nothing records the result; run by hand on 2026-09-03 it passed (exit 0, review posted, secret redacted, `.env` skipped).

Patching an HTTP client would not be a proof; the guard sits below every HTTP stack in the process.

## Change log

- 2026-09-03: initial review written from the Phase 0 investigation.
- 2026-09-03: SR-01 fixed (requirements resolvable). SR-03 reproduced with a recording fake model. Test suite added under backend/tests with strict expected failures for the open findings it covers.
- 2026-09-03: backend rewritten on LangChain 1.x with a local Ollama model; statuses updated for every finding; the local claim now has three proofs.
- 2026-09-03: frontend rebuilt on shadcn/ui (four screens, server-side token, no external requests); README and backend README rewritten; remaining statuses updated.
- 2026-09-03: second adversarial round on the rewritten backend: 56 findings, all fixed; see "Second round" and the R2 list.
- 2026-09-04 (evening): installation tokens scoped to the repository and two permissions at minting, five-minute App JWT, private key validated at startup with a permissions warning; the cross-examiner stage (second model family, provenance per finding) and the accessibility category added.
- 2026-09-04: Claude Security plugin scan (whole repository, high effort, verified): 6 findings, all fixed; see "Claude Security scan".
- 2026-09-04: expert reviewer prompt measured and adopted; verify pass added but left off on the numbers; hands-on test plan and hosted-model plan written; fourth adversarial round: 35 findings confirmed, 4 refuted, all fixed; see "Fourth round" and the R4 list.
- 2026-09-03: third adversarial round on the whole branch (backend, dashboard, supply chain, docs, tests): 67 findings confirmed, 1 refuted, all fixed; see "Third round" and the R3 list. Backend suite at 208 tests, 15 dashboard tests.
