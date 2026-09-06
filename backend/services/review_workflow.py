"""The review as a LangGraph state machine.

prioritise -> analyse_file (one structured model call, looped over files)
-> synthesise -> END. The graph keeps the per-file loop explicit and the
recursion limit is set from the file count, which is what the previous
version got wrong. The synthesis is a template, not a model call, and the
comment footer says so.

With a cross-examining model and CROSS_EXAMINE_SEQUENTIAL on, the graph
grows a second phase so only one model is resident at a time:
analyse_file (all files) -> unload_reviewer -> cross_file (all files)
-> unload_cross -> synthesise. Nothing is written to disk between the
phases; the per-file results wait in the graph state, where the redacted
patches already live."""

from typing import Any, Awaitable, Callable, Dict, List, Optional, TypedDict

Progress = Callable[[str, int, int, str], Awaitable[None]]  # phase, files done, files total, current file

from langgraph.graph import END, START, StateGraph

from config.logging import get_logger
from services.ai_reviewer import FileReviewer, FileReviewResult
from services.llm import unload_model

logger = get_logger(__name__)
_RISKY = ("auth", "secret", "token", "password", "crypto", "security", "login", "session", "permission", "webhook", "payment")


class ReviewState(TypedDict, total=False):
    repo: str
    pr_number: int
    head_sha: str
    files: List[Dict[str, Any]]          # filename, language, status, patch, additions
    index: int
    cross_index: int                     # second phase: the next result to cross-examine
    results: List[FileReviewResult]
    totals: Dict[str, int]


def risk_score(filename: str, additions: int) -> int:
    name = filename.lower()
    return (100 if any(k in name for k in _RISKY) else 0) + min(int(additions or 0), 99)


class ReviewWorkflow:
    def __init__(self, reviewer: FileReviewer, unload: Optional[Callable[[str], Awaitable[bool]]] = None,
                 on_progress: Optional[Progress] = None):
        self.reviewer = reviewer
        self._on_progress = on_progress
        settings = reviewer.settings
        self.two_phase = (reviewer.cross_enabled and settings.CROSS_EXAMINE_SEQUENTIAL
                          and reviewer.cross_model_name != reviewer.model_name)
        reviewer.cross_inline = not self.two_phase
        self._unload = unload or (lambda model: unload_model(settings, model))
        g = StateGraph(ReviewState)
        g.add_node("prioritise", self._prioritise)
        g.add_node("analyse_file", self._analyse_file)
        g.add_node("synthesise", self._synthesise)
        g.add_edge(START, "prioritise")
        if self.two_phase:
            g.add_node("unload_reviewer", self._unload_reviewer)
            g.add_node("cross_file", self._cross_file)
            g.add_node("unload_cross", self._unload_cross)
            g.add_conditional_edges("prioritise", self._route, {"next": "analyse_file", "done": "unload_reviewer"})
            g.add_conditional_edges("analyse_file", self._route, {"next": "analyse_file", "done": "unload_reviewer"})
            g.add_conditional_edges("unload_reviewer", self._route_cross, {"next": "cross_file", "done": "unload_cross"})
            g.add_conditional_edges("cross_file", self._route_cross, {"next": "cross_file", "done": "unload_cross"})
            g.add_edge("unload_cross", "synthesise")
        else:
            g.add_conditional_edges("prioritise", self._route, {"next": "analyse_file", "done": "synthesise"})
            g.add_conditional_edges("analyse_file", self._route, {"next": "analyse_file", "done": "synthesise"})
        g.add_edge("synthesise", END)
        self.graph = g.compile()

    async def _progress(self, phase: str, done: int, total: int, current: str) -> None:
        """Tell whoever is watching where the review is up to; never let that fail the review."""
        if self._on_progress is None:
            return
        try:
            await self._on_progress(phase, done, total, current)
        except Exception as e:  # noqa: BLE001
            logger.warning("progress update failed", error=type(e).__name__)

    async def _prioritise(self, state: ReviewState) -> Dict[str, Any]:
        files = sorted(state.get("files", []), key=lambda f: -risk_score(f["filename"], f.get("additions", 0)))
        await self._progress("review", 0, len(files), "")
        return {"files": files, "index": 0, "cross_index": 0, "results": []}

    def _route(self, state: ReviewState) -> str:
        return "next" if state.get("index", 0) < len(state.get("files", [])) else "done"

    def _route_cross(self, state: ReviewState) -> str:
        return "next" if state.get("cross_index", 0) < len(state.get("results", [])) else "done"

    async def _analyse_file(self, state: ReviewState) -> Dict[str, Any]:
        i = state["index"]
        f = state["files"][i]
        logger.info("reviewing file", repo=state.get("repo"), pr=state.get("pr_number"), filename=f["filename"],
                    position=f"{i + 1}/{len(state['files'])}")
        await self._progress("review", i, len(state["files"]), f["filename"])
        result = await self.reviewer.review_file(f["filename"], f.get("language", "unknown"), f.get("status", "modified"), f["patch"])
        result.redactions = f.get("redactions", {})
        return {"results": list(state.get("results", [])) + [result], "index": i + 1}

    async def _cross_file(self, state: ReviewState) -> Dict[str, Any]:
        i = state.get("cross_index", 0)
        results = list(state.get("results", []))
        logger.info("cross-examining file", repo=state.get("repo"), pr=state.get("pr_number"),
                    filename=results[i].filename, position=f"{i + 1}/{len(results)}")
        await self._progress("cross-examine", i, len(results), results[i].filename)
        results[i] = await self.reviewer.cross_examine_file(results[i])
        return {"results": results, "cross_index": i + 1}

    async def _drop(self, model: str) -> None:
        logger.info("unloading model between phases", model=model)
        try:
            await self._unload(model)
        except Exception as e:  # noqa: BLE001 - an unload can never fail a review
            logger.warning("unload failed", model=model, error=type(e).__name__)

    async def _unload_reviewer(self, state: ReviewState) -> Dict[str, Any]:
        await self._drop(self.reviewer.model_name)
        return {"cross_index": 0}

    async def _unload_cross(self, state: ReviewState) -> Dict[str, Any]:
        await self._drop(self.reviewer.cross_model_name)
        return {}

    async def _synthesise(self, state: ReviewState) -> Dict[str, Any]:
        await self._progress("done", len(state.get("results", [])), len(state.get("results", [])), "")
        totals: Dict[str, int] = {"files": len(state.get("results", [])), "findings": 0, "dropped": 0,
                                  "prompt_tokens": 0, "output_tokens": 0, "refuted": 0, "verify_calls": 0,
                                  "cross_calls": 0, "cross_refuted": 0, "cross_added": 0}
        for r in state.get("results", []):
            totals["findings"] += len(r.review.findings)
            totals["dropped"] += r.dropped
            totals["prompt_tokens"] += r.prompt_tokens
            totals["output_tokens"] += r.output_tokens
            totals["refuted"] += r.refuted
            totals["verify_calls"] += r.verify_calls
            totals["cross_calls"] += r.cross_calls
            totals["cross_refuted"] += r.cross_refuted
            totals["cross_added"] += r.cross_added
        return {"totals": totals}

    async def run(self, repo: str, pr_number: int, head_sha: str, files: List[Dict[str, Any]]) -> ReviewState:
        initial: ReviewState = {"repo": repo, "pr_number": pr_number, "head_sha": head_sha, "files": files,
                                "index": 0, "cross_index": 0, "results": [], "totals": {}}
        # one superstep per file per phase, plus prioritise, the unloads, synthesise and headroom
        limit = (2 * len(files) + 8) if self.two_phase else (len(files) + 5)
        return await self.graph.ainvoke(initial, config={"recursion_limit": limit})
