"""The review as a LangGraph state machine.

prioritise -> analyse_file (one structured model call, looped over files)
-> synthesise -> END. The graph keeps the per-file loop explicit and the
recursion limit is set from the file count, which is what the previous
version got wrong. The synthesis is a template, not a model call, and the
comment footer says so."""

from typing import Any, Dict, List, TypedDict

from langgraph.graph import END, START, StateGraph

from config.logging import get_logger
from services.ai_reviewer import FileReviewer, FileReviewResult

logger = get_logger(__name__)
_RISKY = ("auth", "secret", "token", "password", "crypto", "security", "login", "session", "permission", "webhook", "payment")


class ReviewState(TypedDict, total=False):
    repo: str
    pr_number: int
    head_sha: str
    files: List[Dict[str, Any]]          # filename, language, status, patch, additions
    index: int
    results: List[FileReviewResult]
    totals: Dict[str, int]


def risk_score(filename: str, additions: int) -> int:
    name = filename.lower()
    return (100 if any(k in name for k in _RISKY) else 0) + min(int(additions or 0), 99)


class ReviewWorkflow:
    def __init__(self, reviewer: FileReviewer):
        self.reviewer = reviewer
        g = StateGraph(ReviewState)
        g.add_node("prioritise", self._prioritise)
        g.add_node("analyse_file", self._analyse_file)
        g.add_node("synthesise", self._synthesise)
        g.add_edge(START, "prioritise")
        g.add_conditional_edges("prioritise", self._route, {"next": "analyse_file", "done": "synthesise"})
        g.add_conditional_edges("analyse_file", self._route, {"next": "analyse_file", "done": "synthesise"})
        g.add_edge("synthesise", END)
        self.graph = g.compile()

    async def _prioritise(self, state: ReviewState) -> Dict[str, Any]:
        files = sorted(state.get("files", []), key=lambda f: -risk_score(f["filename"], f.get("additions", 0)))
        return {"files": files, "index": 0, "results": []}

    def _route(self, state: ReviewState) -> str:
        return "next" if state.get("index", 0) < len(state.get("files", [])) else "done"

    async def _analyse_file(self, state: ReviewState) -> Dict[str, Any]:
        i = state["index"]
        f = state["files"][i]
        logger.info("reviewing file", repo=state.get("repo"), pr=state.get("pr_number"), filename=f["filename"],
                    position=f"{i + 1}/{len(state['files'])}")
        result = await self.reviewer.review_file(f["filename"], f.get("language", "unknown"), f.get("status", "modified"), f["patch"])
        result.redactions = f.get("redactions", {})
        return {"results": list(state.get("results", [])) + [result], "index": i + 1}

    async def _synthesise(self, state: ReviewState) -> Dict[str, Any]:
        totals: Dict[str, int] = {"files": len(state.get("results", [])), "findings": 0, "dropped": 0,
                                  "prompt_tokens": 0, "output_tokens": 0}
        for r in state.get("results", []):
            totals["findings"] += len(r.review.findings)
            totals["dropped"] += r.dropped
            totals["prompt_tokens"] += r.prompt_tokens
            totals["output_tokens"] += r.output_tokens
        return {"totals": totals}

    async def run(self, repo: str, pr_number: int, head_sha: str, files: List[Dict[str, Any]]) -> ReviewState:
        initial: ReviewState = {"repo": repo, "pr_number": pr_number, "head_sha": head_sha, "files": files,
                                "index": 0, "results": [], "totals": {}}
        limit = len(files) + 5  # one superstep per file plus prioritise, synthesise and headroom
        return await self.graph.ainvoke(initial, config={"recursion_limit": limit})
