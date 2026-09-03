from config.settings import settings
from services.ai_reviewer import FileReviewer
from services.review_workflow import ReviewWorkflow, risk_score
from tests.conftest import DIFF
from tests.fakes import RecordingChatModel


def _file(name, additions=1):
    return {"filename": name, "language": "python", "status": "modified", "patch": DIFF, "additions": additions}


async def test_risky_files_are_reviewed_first_and_all_files_are_reviewed():
    fake = RecordingChatModel()
    wf = ReviewWorkflow(FileReviewer(fake, settings))
    state = await wf.run("octocat/repo", 1, "a" * 40, [_file("utils.py", 5), _file("auth/login.py", 1), _file("big.py", 80)])
    assert [r.filename for r in state["results"]] == ["auth/login.py", "big.py", "utils.py"]
    assert len(fake.calls) == 3
    assert state["totals"]["files"] == 3 and state["totals"]["prompt_tokens"] == 300


async def test_many_files_do_not_hit_the_recursion_limit():
    fake = RecordingChatModel()
    wf = ReviewWorkflow(FileReviewer(fake, settings))
    state = await wf.run("octocat/repo", 1, "a" * 40, [_file(f"f{i}.py") for i in range(40)])
    assert len(state["results"]) == 40


async def test_no_files_is_a_clean_empty_run():
    state = await ReviewWorkflow(FileReviewer(RecordingChatModel(), settings)).run("octocat/repo", 1, "a" * 40, [])
    assert state["results"] == [] and state["totals"]["files"] == 0


def test_risk_score():
    assert risk_score("src/auth/session.py", 3) > risk_score("src/utils.py", 90)
