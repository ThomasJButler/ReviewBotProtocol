"""A whole review, end to end, against a fake GitHub API (respx) and a fake
model. respx intercepts httpx below the client, so nothing here can reach a
socket; the socket-level guard is exercised by test_no_egress.py and the
real-model proof is the REVIEWBOT_E2E test."""

import asyncio
import json

import httpx
import pytest
import respx

from config.settings import settings
from database.repositories.review_repository import ReviewRepository
from database.repositories.webhook_repository import WebhookRepository
from services.review_queue import ReviewJob
import services.review_runner as review_runner
from services.review_runner import ReviewCutShort, RunnerDeps, Superseded, review_budget, run_review, select_files
from tests.fakes import RecordingChatModel

# Every whole-review test runs under the socket guard: respx answers GitHub in-process,
# and anything else in the process that tries to leave loopback fails the test.
pytestmark = pytest.mark.usefixtures("no_egress")

BASE = "https://api.github.com"
SECRET_DIFF = ("@@ -1,2 +1,4 @@\n"
               " import requests\n"
               "+TOKEN = 'ghp_" + "z" * 36 + "'\n"
               "+query = f\"SELECT * FROM users WHERE id = '{user_id}'\"\n"
               " main()\n")
MODEL_REPLY = json.dumps({"findings": [
    {"category": "security", "severity": "high", "title": "SQL built with an f-string", "line": 3,
     "evidence": "SELECT * FROM users WHERE id = '{user_id}'", "recommendation": "Use a parameterised query.", "confidence": 0.9},
], "summary": "One high severity issue."})
PR_TITLE = "Add <b>feature</b> @everyone SECRET-TITLE-TOKEN"


def _routes(head="c" * 40, extra=()):
    respx.post(f"{BASE}/app/installations/555/access_tokens").mock(return_value=httpx.Response(201, json={"token": "ghs_t", "expires_at": "2099-01-01T00:00:00Z"}))
    respx.get(f"{BASE}/repos/octocat/repo/pulls/42").mock(return_value=httpx.Response(200, json={"number": 42, "title": PR_TITLE, "body": "SECRET-BODY-TOKEN", "head": {"sha": head}}))
    respx.get(f"{BASE}/repos/octocat/repo/pulls/42/files").mock(return_value=httpx.Response(200, json=[*extra,
        {"filename": "db.py", "status": "modified", "additions": 2, "deletions": 0, "patch": SECRET_DIFF},
        {"filename": ".env", "status": "added", "additions": 1, "deletions": 0, "patch": "+SECRET=abcdefghijklmnop"},
        {"filename": "README.md", "status": "modified", "additions": 1, "deletions": 0, "patch": "+hello"},
        {"filename": "old.py", "status": "removed", "additions": 0, "deletions": 5, "patch": "-x"},
        {"filename": "image.png", "status": "added", "additions": 0, "deletions": 0},
        {"filename": "moved.py", "status": "renamed", "additions": 0, "deletions": 0},
    ]))
    return respx.post(f"{BASE}/repos/octocat/repo/pulls/42/reviews").mock(return_value=httpx.Response(200, json={"id": 1, "html_url": "https://github.com/octocat/repo/pull/42#pullrequestreview-1"}))


@respx.mock
async def test_full_review_against_a_fake_github(db):
    reviews_route = _routes()
    fake = RecordingChatModel(response=MODEL_REPLY)
    async with db() as session:
        await WebhookRepository(session).record("d-1", "pull_request", "opened", "octocat/repo", 42, "c" * 40)
    async with httpx.AsyncClient() as http:
        deps = RunnerDeps(settings=settings, llm=fake, session_factory=db, http=http)
        outcome = await run_review(ReviewJob("octocat/repo", 42, "c" * 40, 555, "d-1", True, "someone/repo"), deps)

    assert outcome.findings == 1 and outcome.files_reviewed == 1 and outcome.files_skipped == 5
    # the secret and the PR title and body never reached the model, the posted review, or the database
    assert "ghp_zzzz" not in fake.seen_text and "[REDACTED:github-token]" in fake.seen_text
    assert "SECRET-TITLE-TOKEN" not in fake.seen_text and "SECRET-BODY-TOKEN" not in fake.seen_text
    posted = json.loads(reviews_route.calls[0].request.content)
    assert "ghp_zzzz" not in json.dumps(posted)
    assert posted["commit_id"] == "c" * 40 and posted["event"] == "COMMENT"
    assert len(posted["comments"]) == 1 and posted["comments"][0]["path"] == "db.py" and posted["comments"][0]["line"] == 3
    assert "someone/repo" in posted["body"] and "1 credential-looking value was redacted" in posted["body"]
    assert "`.env`" in posted["body"] and "never sent to the model" in posted["body"]
    assert "renamed or copied with no content change" in posted["body"]
    assert "fake-model" in posted["body"]

    async with db() as session:
        review = await ReviewRepository(session).get(outcome.review_id)
        assert review.status == "completed" and review.findings_count == 1 and review.files_total == 6
        assert review.severity_counts == {"high": 1}
        assert review.is_fork is True and review.comment_url.startswith("https://github.com/")
        assert review.pr_title == "Add feature ＠everyone SECRET-TITLE-TOKEN"
        assert review.prompt_tokens == 100 and review.redactions == 1
        assert [f.line for f in review.findings] == [3]
        assert "ghp_zzzz" not in json.dumps({"s": review.summary, "f": [x.evidence for x in review.findings]})
        deliveries = await WebhookRepository(session).recent(5)
        assert deliveries[0].status == "completed" and deliveries[0].review_id == outcome.review_id


@respx.mock
async def test_github_failure_marks_the_review_failed_without_leaking_and_leaves_one_line(db):
    """A review that fails before anything is posted leaves one line on the
    pull request naming the exception and nothing else: silence reads as
    approval, and the message can carry text from GitHub's error body."""
    respx.post(f"{BASE}/app/installations/555/access_tokens").mock(return_value=httpx.Response(201, json={"token": "ghs_t", "expires_at": "2099-01-01T00:00:00Z"}))
    respx.get(f"{BASE}/repos/octocat/repo/pulls/42").mock(return_value=httpx.Response(500, json={"message": "boom sk-proj-abcdefghijklmnopqrstuvwxyz0123456789ABCD"}))
    reviews_route = respx.post(f"{BASE}/repos/octocat/repo/pulls/42/reviews").mock(return_value=httpx.Response(200, json={"id": 2}))
    async with httpx.AsyncClient() as http:
        deps = RunnerDeps(settings=settings, llm=RecordingChatModel(), session_factory=db, http=http)
        with pytest.raises(Exception):
            await run_review(ReviewJob("octocat/repo", 42, "c" * 40, 555, ""), deps)
    posted = json.loads(reviews_route.calls[0].request.content)
    assert "could not complete this review (GitHubError after" in posted["body"] and "Nothing was reviewed" in posted["body"]
    assert "sk-proj" not in posted["body"] and "boom" not in posted["body"] and "comments" not in posted
    async with db() as session:
        (latest,) = await ReviewRepository(session).list(limit=5)
        assert latest.status == "failed" and "GitHubError" in latest.error_message
        assert "sk-proj-abcdef" not in latest.error_message


@respx.mock
async def test_a_failure_after_the_post_does_not_post_again(db, monkeypatch):
    """Once the review may be on GitHub, a failure in the bookkeeping is a
    failed row, not a second comment saying nothing was reviewed."""
    reviews_route = _routes()

    async def broken(self, *args, **kwargs):
        raise RuntimeError("disk full")

    monkeypatch.setattr(ReviewRepository, "add_findings", broken)
    async with httpx.AsyncClient() as http:
        deps = RunnerDeps(settings=settings, llm=RecordingChatModel(response=MODEL_REPLY), session_factory=db, http=http)
        with pytest.raises(RuntimeError):
            await run_review(ReviewJob("octocat/repo", 42, "c" * 40, 555, ""), deps)
    assert len(reviews_route.calls) == 1
    async with db() as session:
        (latest,) = await ReviewRepository(session).list(limit=5)
        assert latest.status == "failed" and "RuntimeError" in latest.error_message
        assert latest.comment_url.startswith("https://github.com/"), "the URL was written before the bookkeeping failed"


@respx.mock
async def test_a_note_that_cannot_be_posted_does_not_hide_the_failure(db):
    """GitHub down is the likeliest reason for a failed review; the note fails
    the same way and the row still says what happened."""
    respx.post(f"{BASE}/app/installations/555/access_tokens").mock(return_value=httpx.Response(201, json={"token": "ghs_t", "expires_at": "2099-01-01T00:00:00Z"}))
    respx.get(f"{BASE}/repos/octocat/repo/pulls/42").mock(return_value=httpx.Response(502, json={"message": "bad gateway"}))
    respx.post(f"{BASE}/repos/octocat/repo/pulls/42/reviews").mock(return_value=httpx.Response(502, json={"message": "bad gateway"}))
    async with httpx.AsyncClient() as http:
        deps = RunnerDeps(settings=settings, llm=RecordingChatModel(), session_factory=db, http=http)
        with pytest.raises(Exception):
            await run_review(ReviewJob("octocat/repo", 42, "c" * 40, 555, ""), deps)
    async with db() as session:
        (latest,) = await ReviewRepository(session).list(limit=5)
        assert latest.status == "failed" and "GitHubError" in latest.error_message


@respx.mock
async def test_moved_head_supersedes_the_job_without_posting(db):
    reviews_route = _routes(head="d" * 40)
    async with httpx.AsyncClient() as http:
        deps = RunnerDeps(settings=settings, llm=RecordingChatModel(response=MODEL_REPLY), session_factory=db, http=http)
        with pytest.raises(Superseded):
            await run_review(ReviewJob("octocat/repo", 42, "c" * 40, 555, ""), deps)
    assert not reviews_route.called
    async with db() as session:
        (latest,) = await ReviewRepository(session).list(limit=5)
        assert latest.status == "superseded"


class SlowModel(RecordingChatModel):
    """A model that never answers in time, for the cancellation path."""

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        await asyncio.sleep(30)
        return await super()._agenerate(messages, stop=stop, run_manager=run_manager, **kwargs)


class SlowAfter(RecordingChatModel):
    """Answers the first file at once and never answers the next: a review
    that runs out of time part way through. `started` counts calls as they
    begin, since `calls` only sees one once it has been answered."""
    answers: int = 1
    started: int = 0

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        self.started += 1
        if self.started > self.answers:
            await asyncio.sleep(30)
        return await super()._agenerate(messages, stop=stop, run_manager=run_manager, **kwargs)


LATE = {"filename": "late.py", "status": "modified", "additions": 1, "deletions": 0, "patch": "@@ -1 +1,2 @@\n x = 1\n+y = 2\n"}


async def _cancel_after_first_file(db, model, reason):
    """Start a two-file review, wait for the first file to land, cancel it the way the queue does."""
    async with httpx.AsyncClient() as http:
        deps = RunnerDeps(settings=settings, llm=model, session_factory=db, http=http)
        job = ReviewJob("octocat/repo", 42, "c" * 40, 555, "")
        task = asyncio.create_task(run_review(job, deps))
        for _ in range(100):
            await asyncio.sleep(0.05)
            if model.started >= 2:
                break
        if reason:
            job.state["cancel_reason"] = reason
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    async with db() as session:
        (latest,) = await ReviewRepository(session).list(limit=5)
        latest = await ReviewRepository(session).get(latest.id)  # list() leaves the findings unloaded
        return latest, [f.line for f in latest.findings]


@respx.mock
async def test_a_review_cut_short_posts_the_files_that_finished(db):
    """The first review of a rewrite-sized pull request hit the ceiling at 24
    of 25 files and posted nothing. Now the files that finished are posted,
    the rest are listed under Not reviewed, and the row carries the findings,
    the URL and how far it got."""
    reviews_route = _routes(extra=[LATE])
    latest, lines = await _cancel_after_first_file(db, SlowAfter(response=MODEL_REPLY), "timeout")
    assert len(reviews_route.calls) == 1
    posted = json.loads(reviews_route.calls[0].request.content)
    assert "1 of 2 files were reviewed; the rest are listed under Not reviewed" in posted["body"], posted["body"]
    assert "`late.py`: not reached before the review's time ran out" in posted["body"]
    assert [c["path"] for c in posted["comments"]] == ["db.py"]
    assert latest.status == "timed_out" and latest.files_reviewed == 1 and latest.files_skipped == 6
    assert latest.comment_url.startswith("https://github.com/") and lines == [3]
    assert "at 1 of 2 files in the review phase" in latest.error_message, latest.error_message
    assert latest.summary and "ran out of time" in latest.summary


@respx.mock
@pytest.mark.parametrize("reason, status", [("", "superseded"), ("shutdown", "interrupted")])
async def test_a_review_stopped_for_a_newer_push_or_a_shutdown_posts_nothing(db, reason, status):
    """Only the ceiling earns a partial post. A newer push gets its own review
    and a shutdown has no time to spend on GitHub."""
    reviews_route = _routes(extra=[LATE])
    latest, lines = await _cancel_after_first_file(db, SlowAfter(response=MODEL_REPLY), reason)
    assert not reviews_route.called
    assert latest.status == status and latest.comment_url is None and lines == []


@respx.mock
async def test_a_review_cut_short_by_its_own_budget_posts_and_raises_review_cut_short(db, monkeypatch):
    """The queue's ceiling is one number for every review. The runner's own
    deadline is the file count times REVIEW_SECONDS_PER_FILE, so a two-file
    pull request stops holding the queue for an hour, and it ends the same
    way the ceiling does: what finished is posted, the row is written once."""
    monkeypatch.setattr(review_runner, "TIMEOUT_MARGIN_SECONDS", 0)
    reviews_route = _routes(extra=[LATE])
    tight = settings.model_copy(update={"REVIEW_SECONDS_PER_FILE": 1})
    async with httpx.AsyncClient() as http:
        deps = RunnerDeps(settings=tight, llm=SlowAfter(response=MODEL_REPLY), session_factory=db, http=http)
        with pytest.raises(ReviewCutShort) as raised:
            await run_review(ReviewJob("octocat/repo", 42, "c" * 40, 555, ""), deps)
    assert raised.value.recorded and "budget of 2s" in str(raised.value) and "at 1 of 2 files" in str(raised.value)
    assert len(reviews_route.calls) == 1
    posted = json.loads(reviews_route.calls[0].request.content)
    assert "1 of 2 files were reviewed" in posted["body"] and [c["path"] for c in posted["comments"]] == ["db.py"]
    async with db() as session:
        (latest,) = await ReviewRepository(session).list(limit=5)
        latest = await ReviewRepository(session).get(latest.id)
        assert latest.status == "timed_out" and latest.files_reviewed == 1 and latest.comment_url
        assert [f.line for f in latest.findings] == [3] and "budget" in latest.error_message


def test_the_budget_is_files_times_the_per_file_setting_under_the_ceiling():
    s = settings.model_copy(update={"REVIEW_TIMEOUT_SECONDS": 3600, "REVIEW_SECONDS_PER_FILE": 300})
    assert review_budget(s, 2, elapsed=10) == 600 - 10 - review_runner.TIMEOUT_MARGIN_SECONDS
    assert review_budget(s, 25, elapsed=10) == 3600 - 10 - review_runner.TIMEOUT_MARGIN_SECONDS, "the product is over the ceiling, so the ceiling holds"
    assert review_budget(s.model_copy(update={"REVIEW_SECONDS_PER_FILE": 0}), 2, elapsed=10) == 3600 - 10 - review_runner.TIMEOUT_MARGIN_SECONDS
    assert review_budget(s, 1, elapsed=10_000) == 1.0, "setup that already overran leaves a second, never a negative timeout"


@respx.mock
async def test_a_review_cut_short_before_the_cross_examiner_ran_does_not_claim_it_did(db):
    """With the two models run one at a time, a review cut short in the first
    phase has findings no second model has seen. Naming the cross-examiner
    then, with 0 added and 0 refuted, would read as verified and clean."""
    reviews_route = _routes(extra=[LATE])
    two_phase = settings.model_copy(update={"CROSS_EXAMINE_MODEL": "gemma-fake", "CROSS_EXAMINE_SEQUENTIAL": True})
    model = SlowAfter(response=MODEL_REPLY)
    async with httpx.AsyncClient() as http:
        deps = RunnerDeps(settings=two_phase, llm=model, session_factory=db, http=http,
                          cross_llm=RecordingChatModel(model="gemma-fake"))
        job = ReviewJob("octocat/repo", 42, "c" * 40, 555, "")
        task = asyncio.create_task(run_review(job, deps))
        for _ in range(100):
            await asyncio.sleep(0.05)
            if model.started >= 2:
                break
        job.state["cancel_reason"] = "timeout"
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    posted = json.loads(reviews_route.calls[0].request.content)
    assert "Cross-examined by" not in posted["body"], posted["body"]
    assert "1 of 2 files were reviewed" in posted["body"]


@respx.mock
async def test_a_review_cut_short_before_any_file_finished_says_so(db):
    """Nothing reviewed is still worth one line on the pull request: silence
    reads as approval."""
    reviews_route = _routes()
    async with httpx.AsyncClient() as http:
        deps = RunnerDeps(settings=settings, llm=SlowModel(response=MODEL_REPLY), session_factory=db, http=http)
        job = ReviewJob("octocat/repo", 42, "c" * 40, 555, "")
        task = asyncio.create_task(run_review(job, deps))
        await asyncio.sleep(0.5)
        job.state["cancel_reason"] = "timeout"
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    posted = json.loads(reviews_route.calls[0].request.content)
    assert "ran out of time" in posted["body"] and "before finishing a file" in posted["body"]
    assert "`db.py`: not reached before the review's time ran out" in posted["body"] and posted.get("comments", []) == []
    async with db() as session:
        (latest,) = await ReviewRepository(session).list(limit=5)
        assert latest.status == "timed_out" and latest.files_reviewed == 0
        assert "at 0 of 1 files in the review phase" in latest.error_message, latest.error_message


@respx.mock
async def test_a_review_cut_short_after_the_head_moved_is_recorded_but_not_posted(db):
    """A post to a stale commit would 422 anyway; the newer push gets its own review."""
    _routes(extra=[LATE])
    reviews_route = respx.post(f"{BASE}/repos/octocat/repo/pulls/42/reviews")
    model = SlowAfter(response=MODEL_REPLY)
    async with httpx.AsyncClient() as http:
        deps = RunnerDeps(settings=settings, llm=model, session_factory=db, http=http)
        job = ReviewJob("octocat/repo", 42, "c" * 40, 555, "")
        task = asyncio.create_task(run_review(job, deps))
        for _ in range(100):
            await asyncio.sleep(0.05)
            if model.started >= 2:
                break
        respx.get(f"{BASE}/repos/octocat/repo/pulls/42").mock(return_value=httpx.Response(200, json={"number": 42, "title": PR_TITLE, "head": {"sha": "d" * 40}}))
        job.state["cancel_reason"] = "timeout"
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert not reviews_route.called
    async with db() as session:
        (latest,) = await ReviewRepository(session).list(limit=5)
        latest = await ReviewRepository(session).get(latest.id)
        assert latest.status == "timed_out" and latest.files_reviewed == 1 and latest.comment_url is None
        assert [f.line for f in latest.findings] == [3], "the findings that were made are kept for the dashboard"


@respx.mock
async def test_model_failure_on_every_file_is_recorded_as_failed_and_posted_honestly(db):
    reviews_route = _routes()
    async with httpx.AsyncClient() as http:
        deps = RunnerDeps(settings=settings, llm=RecordingChatModel(fail_with="ollama down"), session_factory=db, http=http)
        outcome = await run_review(ReviewJob("octocat/repo", 42, "c" * 40, 555, ""), deps)
    assert outcome.files_reviewed == 0
    posted = json.loads(reviews_route.calls[0].request.content)
    assert "Warning: the model did not return a usable review for 1 file" in posted["body"]
    assert "No findings in 0 reviewed files" in posted["body"] and "RuntimeError" in posted["body"]
    async with db() as session:
        (latest,) = await ReviewRepository(session).list(limit=5)
        assert latest.status == "failed" and latest.files_reviewed == 0 and "every file" in latest.error_message


def test_select_files_applies_every_rule_and_keeps_the_riskiest_under_the_cap():
    raw = [
        {"filename": "a.py", "status": "modified", "patch": "+x"},
        {"filename": "gone.py", "status": "removed", "patch": "-x"},
        {"filename": "bin.png", "status": "added"},
        {"filename": "moved.py", "status": "renamed"},
        {"filename": "same.py", "status": "unchanged"},
        {"filename": ".env.local", "status": "added", "patch": "+x"},
        {"filename": ".env.example", "status": "added", "patch": "+KEY=value"},
        {"filename": "package-lock.json", "status": "modified", "patch": "+x"},
        {"filename": "vendor/lib.js", "status": "modified", "patch": "+x"},
        {"filename": "app.min.js", "status": "modified", "patch": "+x"},
        {"filename": "notes.md", "status": "modified", "patch": "+x"},
        {"filename": "huge.py", "status": "modified", "patch": "+" + "x" * 50_000},
    ] + [{"filename": f"f{i}.py", "status": "modified", "patch": "+x"} for i in range(30)] + [
        {"filename": "zz/auth/session.py", "status": "modified", "patch": "+x", "additions": 1},
    ]
    capped = settings.model_copy(update={"MAX_FILES_PER_REVIEW": 25})  # the developer's .env must not decide a test
    selected, skipped = select_files(raw, capped)
    names = [f["filename"] for f in selected]
    assert len(selected) == capped.MAX_FILES_PER_REVIEW
    assert names[0] == "zz/auth/session.py", "the riskiest eligible file must survive the cap even when GitHub lists it last"
    assert ".env.example" in names, "templates are reviewed because people commit real values into them"
    reasons = dict(skipped)
    assert reasons["gone.py"] == "deleted file" and "binary" in reasons["bin.png"]
    assert reasons["moved.py"] == "renamed or copied with no content change" and reasons["same.py"] == "unchanged in this pull request"
    assert "never sent" in reasons[".env.local"] and reasons["package-lock.json"] == "generated or vendored"
    assert reasons["vendor/lib.js"] == "generated or vendored" and reasons["app.min.js"] == "generated or vendored"
    assert reasons["notes.md"] == "not code" and "larger than" in reasons["huge.py"]
    assert sum(1 for _, r in skipped if "file limit" in r) == 32 + 1 - capped.MAX_FILES_PER_REVIEW


def test_patch_that_cannot_fit_the_context_window_is_skipped():
    big = {"filename": "big.py", "status": "modified", "patch": "+" + "y" * (settings.MAX_PATCH_BYTES - 10)}
    tight = settings.model_copy(update={"OLLAMA_NUM_CTX": 2048})
    selected, skipped = select_files([big], tight)
    assert selected == [] and "context window" in dict(skipped)["big.py"]
