"""One model resident at a time. With CROSS_EXAMINE_SEQUENTIAL on, the
workflow reviews every file with the first model, unloads it, cross-examines
every file with the second, and unloads that; the result is the same as the
inline path, only the order of the calls changes."""

import json
from typing import Any, List, Optional

from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatResult

from config.settings import settings
from services.ai_reviewer import FileReviewer
from services.review_workflow import ReviewWorkflow
from tests.conftest import DIFF
from tests.fakes import RecordingChatModel

FIND = json.dumps({"findings": [
    {"category": "security", "severity": "critical", "title": "eval on user input", "line": 2,
     "evidence": "eval(user_input)", "recommendation": "Parse it.", "confidence": 0.95}], "summary": "One problem."})
CONFIRM = json.dumps({"verdicts": [{"index": 0, "verdict": "real", "severity": "high", "reason": "line 2", "confidence": 0.9}],
                      "additions": [{"category": "quality", "severity": "low", "title": "import os is unused", "line": 1,
                                     "evidence": "import os", "recommendation": "Delete it.", "confidence": 0.7}],
                      "summary_note": "agreed"})
FILES = [{"filename": f"{name}.py", "language": "python", "status": "modified", "patch": DIFF, "additions": 3}
         for name in ("a", "b", "c")]


class _Ordered(RecordingChatModel):
    """A fake that writes its model name into a log shared with the other fake."""
    log: Any = None

    def _generate(self, messages: List[BaseMessage], stop: Optional[List[str]] = None,
                  run_manager: Any = None, **kwargs: Any) -> ChatResult:
        self.log.append(self.model)
        return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


def _setup(sequential=True, cross=True, **updates):
    log: List[str] = []
    local = settings.model_copy(update={"CROSS_EXAMINE_SEQUENTIAL": sequential, **updates})
    reviewer_llm = _Ordered(model="qwen-fake", response=FIND, log=log)
    cross_llm = _Ordered(model="gemma-fake", response=CONFIRM, log=log) if cross else None

    async def unload(model: str) -> bool:
        log.append(f"unload:{model}")
        return True

    workflow = ReviewWorkflow(FileReviewer(reviewer_llm, local, cross_llm=cross_llm), unload=unload)
    return workflow, log


async def test_the_reviewer_sees_every_file_before_the_cross_model_sees_any_and_each_model_is_unloaded_once():
    workflow, log = _setup()
    assert workflow.two_phase
    state = await workflow.run("o/r", 1, "sha", FILES)
    assert log == ["qwen-fake"] * 3 + ["unload:qwen-fake"] + ["gemma-fake"] * 3 + ["unload:gemma-fake"]
    assert [r.filename for r in state["results"]] == ["a.py", "b.py", "c.py"], "results keep their prioritised order"
    assert state["totals"]["cross_calls"] == 3 and state["totals"]["cross_added"] == 3
    for r in state["results"]:
        assert {f.source_model for f in r.review.findings} == {"qwen-fake", "gemma-fake"}
        assert r.prompt_tokens == 200 and r.output_tokens == 40, "both calls' tokens land on the file"


async def test_nothing_is_unloaded_without_a_cross_model():
    workflow, log = _setup(cross=False)
    assert not workflow.two_phase
    state = await workflow.run("o/r", 1, "sha", FILES)
    assert log == ["qwen-fake"] * 3 and state["totals"]["cross_calls"] == 0


async def test_with_sequential_off_the_cross_examiner_runs_inline_and_nothing_is_unloaded():
    workflow, log = _setup(sequential=False)
    assert not workflow.two_phase
    state = await workflow.run("o/r", 1, "sha", FILES)
    assert log == ["qwen-fake", "gemma-fake"] * 3 and state["totals"]["cross_calls"] == 3


async def test_the_two_paths_produce_the_same_totals_and_findings():
    inline, _ = _setup(sequential=False)
    phased, _ = _setup(sequential=True)
    a = await inline.run("o/r", 1, "sha", FILES)
    b = await phased.run("o/r", 1, "sha", FILES)
    assert a["totals"] == b["totals"]
    same = lambda s: [[(f.line, f.severity.value, f.source_model, f.cross_verdict) for f in r.review.findings] for r in s["results"]]  # noqa: E731
    assert same(a) == same(b)


async def test_the_budget_still_holds_across_files_in_the_second_phase():
    workflow, log = _setup(CROSS_EXAMINE_MAX_CALLS_PER_REVIEW=1)
    state = await workflow.run("o/r", 1, "sha", FILES)
    assert state["totals"]["cross_calls"] == 1 and log.count("gemma-fake") == 1
    assert len(state["results"][1].review.findings) == 1, "the unexamined files keep the first review"


async def test_an_unload_that_raises_does_not_stop_the_review():
    log: List[str] = []
    local = settings.model_copy(update={"CROSS_EXAMINE_SEQUENTIAL": True})
    reviewer = FileReviewer(_Ordered(model="qwen-fake", response=FIND, log=log), local,
                            cross_llm=_Ordered(model="gemma-fake", response=CONFIRM, log=log))

    async def broken(model: str) -> bool:
        raise RuntimeError("ollama gone")

    state = await ReviewWorkflow(reviewer, unload=broken).run("o/r", 1, "sha", FILES)
    assert state["totals"]["cross_calls"] == 3 and log == ["qwen-fake"] * 3 + ["gemma-fake"] * 3


async def test_a_review_with_no_files_completes_in_two_phase_mode():
    workflow, log = _setup()
    state = await workflow.run("o/r", 1, "sha", [])
    assert state["totals"]["files"] == 0 and log == ["unload:qwen-fake", "unload:gemma-fake"]


async def test_review_file_still_cross_examines_in_one_shot_for_direct_callers():
    log: List[str] = []
    reviewer = FileReviewer(_Ordered(model="qwen-fake", response=FIND, log=log), settings,
                            cross_llm=_Ordered(model="gemma-fake", response=CONFIRM, log=log))
    assert reviewer.cross_inline and reviewer.cross_enabled
    result = await reviewer.review_file("a.py", "python", "modified", DIFF)
    assert log == ["qwen-fake", "gemma-fake"] and result.cross_calls == 1 and result.patch, "the redacted patch rides on the result"
