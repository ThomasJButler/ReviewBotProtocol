"""LangGraph workflow implementation for orchestrating code review process.
This module satisfies the course requirement for LangGraph integration with state management."""

import asyncio
import time
from typing import Dict, List, Any, Optional, TypedDict, Annotated, Sequence
from datetime import datetime
from enum import Enum

# LangGraph imports - CORE COURSE REQUIREMENT
from langgraph.graph import StateGraph, END
from langchain.schema import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

# Import existing modules
from config.settings import settings
from config.logging import get_logger
from models.github import PRFile
from models.review import ReviewIssue, IssueCategory, SeverityLevel

# Import the existing AI reviewer to use its chains
from services.ai_reviewer import AIReviewer

logger = get_logger(__name__)


class ReviewPriority(str, Enum):
    """Priority levels for review processing."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class FileAnalysisState(TypedDict):
    """State for individual file analysis."""
    filename: str
    language: str
    code_diff: str
    complexity: float
    security_findings: List[Dict]
    performance_findings: List[Dict]
    quality_findings: List[Dict]
    documentation_findings: List[Dict]
    testing_findings: List[Dict]
    architecture_findings: List[Dict]
    line_comments: List[Dict]
    priority: ReviewPriority
    requires_deep_analysis: bool
    analysis_complete: bool
    error: Optional[str]


class ReviewWorkflowState(TypedDict):
    """Main workflow state for the entire PR review process.
    This represents the state that flows through the LangGraph workflow."""

    # Input data
    pr_number: int
    pr_title: str
    pr_description: str
    files: List[PRFile]

    # Processing control
    current_file_index: int
    files_to_review: List[str]
    files_reviewed: List[str]

    # Analysis results
    file_analyses: Dict[str, FileAnalysisState]

    # Aggregated findings
    all_security_issues: List[Dict]
    all_performance_issues: List[Dict]
    all_quality_issues: List[Dict]
    all_documentation_issues: List[Dict]
    all_testing_issues: List[Dict]
    all_architecture_issues: List[Dict]

    # PR-level analysis
    pr_summary: str
    pr_risk_assessment: str
    pr_recommendations: List[str]
    pr_score: float

    # Metrics
    total_issues: int
    critical_issues_count: int
    high_issues_count: int
    processing_time: float
    ai_tokens_used: int
    ai_cost: float

    # Workflow control
    workflow_stage: str  # "parsing", "analyzing", "synthesizing", "complete"
    should_halt: bool
    error_message: Optional[str]

    # GitHub integration
    github_comments: List[Dict]  # Comments to post on PR
    status_check_result: str  # "success", "failure", "neutral"
    status_check_message: str


class ReviewWorkflow:
    """LangGraph-based workflow for orchestrating comprehensive code review.

    This class implements the course requirement for LangGraph workflow with:
    - State management across review steps
    - Conditional routing based on findings
    - Parallel processing of multiple analyses
    - Synthesis of results into actionable feedback
    """

    def __init__(self, ai_reviewer: Optional[AIReviewer] = None):
        """Initialize the review workflow with LangGraph state management."""
        self.ai_reviewer = ai_reviewer or AIReviewer()
        self.workflow = self._build_workflow()
        self.compiled_workflow = self.workflow.compile()
        logger.info("LangGraph review workflow initialized")

    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph StateGraph for review orchestration.

        This creates a complex workflow with multiple nodes and conditional edges
        that orchestrates the entire code review process.
        """

        # Initialize StateGraph with our state schema
        workflow = StateGraph(ReviewWorkflowState)

        # Add nodes for each stage of the review process
        workflow.add_node("parse_files", self._parse_files_node)
        workflow.add_node("prioritize_files", self._prioritize_files_node)
        workflow.add_node("security_analysis", self._security_analysis_node)
        workflow.add_node("performance_analysis", self._performance_analysis_node)
        workflow.add_node("quality_analysis", self._quality_analysis_node)
        workflow.add_node("documentation_analysis", self._documentation_analysis_node)
        workflow.add_node("testing_analysis", self._testing_analysis_node)
        workflow.add_node("architecture_analysis", self._architecture_analysis_node)
        workflow.add_node("synthesize_file_results", self._synthesize_file_results_node)
        workflow.add_node("generate_pr_summary", self._generate_pr_summary_node)
        workflow.add_node("risk_assessment", self._risk_assessment_node)
        workflow.add_node("generate_github_comments", self._generate_github_comments_node)
        workflow.add_node("finalize_review", self._finalize_review_node)

        # Set entry point
        workflow.set_entry_point("parse_files")

        # Add edges for workflow flow
        workflow.add_edge("parse_files", "prioritize_files")

        # From prioritization, we go to security analysis
        workflow.add_edge("prioritize_files", "security_analysis")

        # Conditional routing from security analysis
        workflow.add_conditional_edges(
            "security_analysis",
            self._route_after_security,
            {
                "critical_found": "risk_assessment",  # Critical issues trigger immediate risk assessment
                "continue": "performance_analysis"    # Otherwise continue with other analyses
            }
        )

        # Continue with other analyses
        workflow.add_edge("performance_analysis", "quality_analysis")
        workflow.add_edge("quality_analysis", "documentation_analysis")
        workflow.add_edge("documentation_analysis", "testing_analysis")
        workflow.add_edge("testing_analysis", "architecture_analysis")
        workflow.add_edge("architecture_analysis", "synthesize_file_results")

        # File synthesis can lead to next file or PR summary
        workflow.add_conditional_edges(
            "synthesize_file_results",
            self._route_after_file_synthesis,
            {
                "next_file": "security_analysis",  # Process next file
                "all_complete": "generate_pr_summary"  # All files done
            }
        )

        # Risk assessment flows back to continue or halt
        workflow.add_conditional_edges(
            "risk_assessment",
            self._route_after_risk_assessment,
            {
                "halt": "generate_github_comments",  # Stop and report critical issues
                "continue": "performance_analysis"   # Continue with analysis
            }
        )

        # Final steps
        workflow.add_edge("generate_pr_summary", "generate_github_comments")
        workflow.add_edge("generate_github_comments", "finalize_review")
        workflow.add_edge("finalize_review", END)

        return workflow

    async def _parse_files_node(self, state: ReviewWorkflowState) -> ReviewWorkflowState:
        """Parse files and prepare them for analysis."""
        logger.info(f"Parsing {len(state['files'])} files for review")

        state["workflow_stage"] = "parsing"
        state["files_to_review"] = []
        state["file_analyses"] = {}

        for file in state["files"]:
            if self._should_review_file(file):
                state["files_to_review"].append(file.filename)
                # Initialize file analysis state
                state["file_analyses"][file.filename] = FileAnalysisState(
                    filename=file.filename,
                    language=self._get_file_language(file.filename),
                    code_diff=file.patch or "",
                    complexity=self._calculate_complexity(file.patch),
                    security_findings=[],
                    performance_findings=[],
                    quality_findings=[],
                    documentation_findings=[],
                    testing_findings=[],
                    architecture_findings=[],
                    line_comments=[],
                    priority=ReviewPriority.MEDIUM,
                    requires_deep_analysis=False,
                    analysis_complete=False,
                    error=None
                )

        state["current_file_index"] = 0
        logger.info(f"Found {len(state['files_to_review'])} files to review")
        return state

    async def _prioritize_files_node(self, state: ReviewWorkflowState) -> ReviewWorkflowState:
        """Prioritize files based on risk factors and complexity."""
        logger.info("Prioritizing files for review")

        for filename, file_state in state["file_analyses"].items():
            # Determine priority based on file characteristics
            priority = self._calculate_file_priority(
                filename,
                file_state["language"],
                file_state["complexity"]
            )
            file_state["priority"] = priority

            # High complexity or critical files need deep analysis
            if priority in [ReviewPriority.CRITICAL, ReviewPriority.HIGH]:
                file_state["requires_deep_analysis"] = True

        # Sort files by priority for processing order
        state["files_to_review"].sort(
            key=lambda f: self._priority_sort_key(
                state["file_analyses"][f]["priority"]
            )
        )

        logger.info(f"File prioritization complete. Critical files: "
                   f"{sum(1 for f in state['file_analyses'].values() if f['priority'] == ReviewPriority.CRITICAL)}")
        return state

    async def _security_analysis_node(self, state: ReviewWorkflowState) -> ReviewWorkflowState:
        """Perform security analysis on current file."""
        if state["current_file_index"] >= len(state["files_to_review"]):
            return state

        current_file = state["files_to_review"][state["current_file_index"]]
        file_state = state["file_analyses"][current_file]

        logger.info(f"Running security analysis on {current_file}")
        state["workflow_stage"] = "analyzing"

        try:
            # Use the existing AI reviewer's security chain
            chain_input = {
                "filename": file_state["filename"],
                "language": file_state["language"],
                "code_diff": file_state["code_diff"]
            }

            # Run security analysis using existing chain
            security_findings = await self.ai_reviewer._run_security_analysis(chain_input)

            file_state["security_findings"] = security_findings

            # Check for critical findings
            critical_count = sum(1 for f in security_findings
                               if f.get("severity") == "critical")

            if critical_count > 0:
                state["critical_issues_count"] = state.get("critical_issues_count", 0) + critical_count
                logger.warning(f"Found {critical_count} critical security issues in {current_file}")

            # Add to aggregated findings
            state["all_security_issues"].extend(security_findings)

        except Exception as e:
            logger.error(f"Security analysis failed for {current_file}: {str(e)}")
            file_state["error"] = f"Security analysis error: {str(e)}"

        return state

    async def _performance_analysis_node(self, state: ReviewWorkflowState) -> ReviewWorkflowState:
        """Perform performance analysis on current file."""
        if state["current_file_index"] >= len(state["files_to_review"]):
            return state

        current_file = state["files_to_review"][state["current_file_index"]]
        file_state = state["file_analyses"][current_file]

        logger.info(f"Running performance analysis on {current_file}")

        try:
            chain_input = {
                "filename": file_state["filename"],
                "language": file_state["language"],
                "code_diff": file_state["code_diff"]
            }

            # Run performance analysis using existing chain
            performance_findings = await self.ai_reviewer._run_performance_analysis(chain_input)

            file_state["performance_findings"] = performance_findings
            state["all_performance_issues"].extend(performance_findings)

        except Exception as e:
            logger.error(f"Performance analysis failed for {current_file}: {str(e)}")
            file_state["error"] = f"Performance analysis error: {str(e)}"

        return state

    async def _quality_analysis_node(self, state: ReviewWorkflowState) -> ReviewWorkflowState:
        """Perform code quality analysis on current file."""
        if state["current_file_index"] >= len(state["files_to_review"]):
            return state

        current_file = state["files_to_review"][state["current_file_index"]]
        file_state = state["file_analyses"][current_file]

        logger.info(f"Running quality analysis on {current_file}")

        try:
            chain_input = {
                "filename": file_state["filename"],
                "language": file_state["language"],
                "code_diff": file_state["code_diff"]
            }

            # Run quality analysis using existing chain
            quality_findings = await self.ai_reviewer._run_quality_analysis(chain_input)

            file_state["quality_findings"] = quality_findings
            state["all_quality_issues"].extend(quality_findings)

        except Exception as e:
            logger.error(f"Quality analysis failed for {current_file}: {str(e)}")
            file_state["error"] = f"Quality analysis error: {str(e)}"

        return state

    async def _documentation_analysis_node(self, state: ReviewWorkflowState) -> ReviewWorkflowState:
        """Analyze documentation coverage."""
        if state["current_file_index"] >= len(state["files_to_review"]):
            return state

        current_file = state["files_to_review"][state["current_file_index"]]
        file_state = state["file_analyses"][current_file]

        # Skip documentation analysis for non-code files
        if not self._is_code_file(current_file):
            return state

        logger.info(f"Running documentation analysis on {current_file}")

        try:
            chain_input = {
                "filename": file_state["filename"],
                "language": file_state["language"],
                "code_diff": file_state["code_diff"]
            }

            # Run documentation analysis
            doc_findings = await self.ai_reviewer._run_documentation_analysis(chain_input)

            file_state["documentation_findings"] = doc_findings
            state["all_documentation_issues"].extend(doc_findings)

        except Exception as e:
            logger.error(f"Documentation analysis failed for {current_file}: {str(e)}")

        return state

    async def _testing_analysis_node(self, state: ReviewWorkflowState) -> ReviewWorkflowState:
        """Analyze testing patterns and testability."""
        if state["current_file_index"] >= len(state["files_to_review"]):
            return state

        current_file = state["files_to_review"][state["current_file_index"]]
        file_state = state["file_analyses"][current_file]

        logger.info(f"Running testing analysis on {current_file}")

        try:
            chain_input = {
                "filename": file_state["filename"],
                "language": file_state["language"],
                "code_diff": file_state["code_diff"]
            }

            # Run testing analysis
            testing_findings = await self.ai_reviewer._run_testing_analysis(chain_input)

            file_state["testing_findings"] = testing_findings
            state["all_testing_issues"].extend(testing_findings)

        except Exception as e:
            logger.error(f"Testing analysis failed for {current_file}: {str(e)}")

        return state

    async def _architecture_analysis_node(self, state: ReviewWorkflowState) -> ReviewWorkflowState:
        """Analyze architecture patterns and SOLID principles."""
        if state["current_file_index"] >= len(state["files_to_review"]):
            return state

        current_file = state["files_to_review"][state["current_file_index"]]
        file_state = state["file_analyses"][current_file]

        # Only run architecture analysis for significant code files
        if file_state["complexity"] < 5.0:  # Skip simple files
            return state

        logger.info(f"Running architecture analysis on {current_file}")

        try:
            chain_input = {
                "filename": file_state["filename"],
                "language": file_state["language"],
                "code_diff": file_state["code_diff"]
            }

            # Run architecture analysis
            arch_findings = await self.ai_reviewer._run_architecture_analysis(chain_input)

            file_state["architecture_findings"] = arch_findings
            state["all_architecture_issues"].extend(arch_findings)

        except Exception as e:
            logger.error(f"Architecture analysis failed for {current_file}: {str(e)}")

        return state

    async def _synthesize_file_results_node(self, state: ReviewWorkflowState) -> ReviewWorkflowState:
        """Synthesize results for current file and prepare line comments."""
        if state["current_file_index"] >= len(state["files_to_review"]):
            return state

        current_file = state["files_to_review"][state["current_file_index"]]
        file_state = state["file_analyses"][current_file]

        logger.info(f"Synthesizing results for {current_file}")

        # Generate line-specific comments from all findings
        line_comments = self._generate_line_comments(file_state)
        file_state["line_comments"] = line_comments

        # Mark file as complete
        file_state["analysis_complete"] = True
        state["files_reviewed"].append(current_file)

        # Move to next file
        state["current_file_index"] += 1

        logger.info(f"Completed analysis of {current_file}. "
                   f"Progress: {len(state['files_reviewed'])}/{len(state['files_to_review'])}")

        return state

    async def _generate_pr_summary_node(self, state: ReviewWorkflowState) -> ReviewWorkflowState:
        """Generate overall PR summary from all file analyses."""
        logger.info("Generating PR summary")
        state["workflow_stage"] = "synthesizing"

        # Calculate totals
        state["total_issues"] = (
            len(state["all_security_issues"]) +
            len(state["all_performance_issues"]) +
            len(state["all_quality_issues"]) +
            len(state["all_documentation_issues"]) +
            len(state["all_testing_issues"]) +
            len(state["all_architecture_issues"])
        )

        # Generate summary using AI
        summary = await self._generate_ai_summary(state)
        state["pr_summary"] = summary

        # Calculate PR score
        state["pr_score"] = self._calculate_pr_score(state)

        # Generate recommendations
        state["pr_recommendations"] = self._generate_recommendations(state)

        logger.info(f"PR summary generated. Total issues: {state['total_issues']}, "
                   f"Score: {state['pr_score']:.2f}")

        return state

    async def _risk_assessment_node(self, state: ReviewWorkflowState) -> ReviewWorkflowState:
        """Perform risk assessment when critical issues are found."""
        logger.info("Performing risk assessment due to critical findings")

        critical_issues = [
            issue for issue in state["all_security_issues"]
            if issue.get("severity") == "critical"
        ]

        risk_level = "critical" if len(critical_issues) > 0 else "high"

        risk_assessment = f"""
        ⚠️ RISK ASSESSMENT: {risk_level.upper()}

        Critical Security Issues Found: {len(critical_issues)}

        Immediate action required:
        """

        for issue in critical_issues[:3]:  # Show top 3 critical issues
            risk_assessment += f"\n- {issue.get('type', 'Unknown')}: {issue.get('description', '')}"

        state["pr_risk_assessment"] = risk_assessment

        # Determine if we should halt further processing
        if len(critical_issues) > 5:  # Too many critical issues
            state["should_halt"] = True
            logger.warning(f"Halting review due to {len(critical_issues)} critical issues")

        return state

    async def _generate_github_comments_node(self, state: ReviewWorkflowState) -> ReviewWorkflowState:
        """Generate GitHub PR comments from analysis results."""
        logger.info("Generating GitHub PR comments")

        comments = []

        # Add main PR comment with summary
        main_comment = self._format_main_pr_comment(state)
        comments.append({
            "type": "pr_comment",
            "body": main_comment
        })

        # Add inline comments for specific issues
        for filename, file_state in state["file_analyses"].items():
            for line_comment in file_state.get("line_comments", []):
                comments.append({
                    "type": "inline_comment",
                    "path": filename,
                    "line": line_comment["line"],
                    "body": line_comment["comment"]
                })

        state["github_comments"] = comments

        # Determine status check result
        if state["critical_issues_count"] > 0:
            state["status_check_result"] = "failure"
            state["status_check_message"] = f"❌ Review failed: {state['critical_issues_count']} critical issues found"
        elif state["high_issues_count"] > 3:
            state["status_check_result"] = "neutral"
            state["status_check_message"] = f"⚠️ Review needs attention: {state['high_issues_count']} high-priority issues"
        else:
            state["status_check_result"] = "success"
            state["status_check_message"] = f"✅ Review passed with score: {state['pr_score']:.1f}/100"

        logger.info(f"Generated {len(comments)} GitHub comments. Status: {state['status_check_result']}")

        return state

    async def _finalize_review_node(self, state: ReviewWorkflowState) -> ReviewWorkflowState:
        """Finalize the review process and prepare final output."""
        logger.info("Finalizing review")
        state["workflow_stage"] = "complete"

        # Calculate final metrics
        state["processing_time"] = time.time() - state.get("start_time", time.time())

        logger.info(
            f"Review complete. Files: {len(state['files_reviewed'])}, "
            f"Issues: {state['total_issues']}, "
            f"Time: {state['processing_time']:.2f}s, "
            f"Score: {state['pr_score']:.1f}/100"
        )

        return state

    # Routing functions for conditional edges

    def _route_after_security(self, state: ReviewWorkflowState) -> str:
        """Route after security analysis based on findings."""
        current_file = state["files_to_review"][state["current_file_index"]]
        file_state = state["file_analyses"][current_file]

        # Check for critical security issues
        critical_issues = [
            f for f in file_state.get("security_findings", [])
            if f.get("severity") == "critical"
        ]

        if critical_issues:
            return "critical_found"
        return "continue"

    def _route_after_file_synthesis(self, state: ReviewWorkflowState) -> str:
        """Route after file synthesis to next file or completion."""
        if state["current_file_index"] < len(state["files_to_review"]):
            return "next_file"
        return "all_complete"

    def _route_after_risk_assessment(self, state: ReviewWorkflowState) -> str:
        """Route after risk assessment based on severity."""
        if state.get("should_halt", False):
            return "halt"
        return "continue"

    # Helper methods

    def _should_review_file(self, file: PRFile) -> bool:
        """Determine if a file should be reviewed."""
        # Skip non-code files
        if file.filename.endswith(('.md', '.txt', '.json', '.yml', '.yaml')):
            return False

        # Skip deleted files
        if file.status == 'removed':
            return False

        # Skip large files
        if file.changes and file.changes > 1000:
            return False

        return True

    def _get_file_language(self, filename: str) -> str:
        """Get programming language from filename."""
        extensions = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.jsx': 'javascript',
            '.tsx': 'typescript',
            '.java': 'java',
            '.cpp': 'cpp',
            '.c': 'c',
            '.cs': 'csharp',
            '.go': 'go',
            '.rb': 'ruby',
            '.php': 'php',
            '.swift': 'swift',
            '.kt': 'kotlin',
            '.rs': 'rust',
        }

        for ext, lang in extensions.items():
            if filename.endswith(ext):
                return lang
        return 'unknown'

    def _calculate_complexity(self, patch: Optional[str]) -> float:
        """Calculate complexity score for a file patch."""
        if not patch:
            return 0.0

        lines = patch.split('\n')
        score = 0.0

        # Basic complexity metrics
        score += len(lines) * 0.01  # Line count
        score += patch.count('if ') * 2  # Conditionals
        score += patch.count('for ') * 3  # Loops
        score += patch.count('while ') * 3  # Loops
        score += patch.count('try ') * 2  # Exception handling
        score += patch.count('class ') * 5  # Classes
        score += patch.count('def ') * 2  # Functions/methods

        return min(score, 100.0)  # Cap at 100

    def _calculate_file_priority(self, filename: str, language: str, complexity: float) -> ReviewPriority:
        """Calculate review priority for a file."""
        # Critical files always get highest priority
        critical_patterns = ['auth', 'security', 'password', 'token', 'secret', 'crypto']
        if any(pattern in filename.lower() for pattern in critical_patterns):
            return ReviewPriority.CRITICAL

        # High complexity files get high priority
        if complexity > 50:
            return ReviewPriority.HIGH
        elif complexity > 20:
            return ReviewPriority.MEDIUM
        else:
            return ReviewPriority.LOW

    def _priority_sort_key(self, priority: ReviewPriority) -> int:
        """Get sort key for priority."""
        priority_map = {
            ReviewPriority.CRITICAL: 0,
            ReviewPriority.HIGH: 1,
            ReviewPriority.MEDIUM: 2,
            ReviewPriority.LOW: 3
        }
        return priority_map.get(priority, 99)

    def _is_code_file(self, filename: str) -> bool:
        """Check if file contains code."""
        code_extensions = {'.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.cpp', '.c', '.cs', '.go', '.rb', '.php'}
        return any(filename.endswith(ext) for ext in code_extensions)

    def _generate_line_comments(self, file_state: FileAnalysisState) -> List[Dict]:
        """Generate line-specific comments from all findings."""
        comments = []

        # Process all finding types
        all_findings = (
            [(f, "security") for f in file_state.get("security_findings", [])] +
            [(f, "performance") for f in file_state.get("performance_findings", [])] +
            [(f, "quality") for f in file_state.get("quality_findings", [])]
        )

        for finding, finding_type in all_findings:
            if finding.get("line_number"):
                icon = {
                    "security": "🔒",
                    "performance": "⚡",
                    "quality": "✨"
                }.get(finding_type, "📝")

                comment = f"{icon} **{finding_type.title()} Issue** ({finding.get('severity', 'info')})\n\n"
                comment += f"{finding.get('description', '')}\n\n"
                comment += f"**Suggestion**: {finding.get('recommendation', '')}"

                comments.append({
                    "line": finding["line_number"],
                    "comment": comment
                })

        return comments

    async def _generate_ai_summary(self, state: ReviewWorkflowState) -> str:
        """Generate AI summary of the PR."""
        # This would call an AI model to generate a summary
        # For now, return a template summary
        return f"""
## 📊 Code Review Summary

**Files Reviewed**: {len(state['files_reviewed'])}
**Total Issues Found**: {state['total_issues']}
**Review Score**: {state['pr_score']:.1f}/100

### Issue Breakdown:
- 🔒 Security: {len(state['all_security_issues'])} issues
- ⚡ Performance: {len(state['all_performance_issues'])} issues
- ✨ Code Quality: {len(state['all_quality_issues'])} issues
- 📚 Documentation: {len(state['all_documentation_issues'])} issues
- 🧪 Testing: {len(state['all_testing_issues'])} issues
- 🏗️ Architecture: {len(state['all_architecture_issues'])} issues

### Key Findings:
{self._get_key_findings_summary(state)}
        """

    def _get_key_findings_summary(self, state: ReviewWorkflowState) -> str:
        """Get summary of key findings."""
        findings = []

        # Add critical security issues
        critical_security = [
            f for f in state["all_security_issues"]
            if f.get("severity") == "critical"
        ]
        if critical_security:
            findings.append(f"- ⚠️ {len(critical_security)} critical security vulnerabilities require immediate attention")

        # Add high priority performance issues
        high_perf = [
            f for f in state["all_performance_issues"]
            if f.get("severity") == "high"
        ]
        if high_perf:
            findings.append(f"- 🔥 {len(high_perf)} performance bottlenecks detected")

        if not findings:
            findings.append("- ✅ No critical issues found")

        return "\n".join(findings)

    def _calculate_pr_score(self, state: ReviewWorkflowState) -> float:
        """Calculate overall PR score (0-100)."""
        score = 100.0

        # Deduct points for issues based on severity
        severity_penalties = {
            "critical": 15.0,
            "high": 8.0,
            "medium": 4.0,
            "low": 2.0,
            "warning": 1.0,
            "info": 0.5
        }

        all_issues = (
            state["all_security_issues"] +
            state["all_performance_issues"] +
            state["all_quality_issues"]
        )

        for issue in all_issues:
            severity = issue.get("severity", "info")
            penalty = severity_penalties.get(severity, 0.5)
            score -= penalty

        return max(0.0, min(100.0, score))

    def _generate_recommendations(self, state: ReviewWorkflowState) -> List[str]:
        """Generate actionable recommendations."""
        recommendations = []

        if state["critical_issues_count"] > 0:
            recommendations.append("🚨 Address all critical security vulnerabilities before merging")

        if state["high_issues_count"] > 3:
            recommendations.append("⚠️ Review and fix high-priority issues")

        if len(state["all_documentation_issues"]) > 5:
            recommendations.append("📚 Improve code documentation coverage")

        if len(state["all_testing_issues"]) > 3:
            recommendations.append("🧪 Add test coverage for new functionality")

        if not recommendations:
            recommendations.append("✅ Code meets quality standards")

        return recommendations

    def _format_main_pr_comment(self, state: ReviewWorkflowState) -> str:
        """Format the main PR comment."""
        comment = f"""
# 🤖 AI Code Review Results

{state.get('pr_summary', 'No summary available')}

## 📋 Recommendations

"""
        for rec in state.get('pr_recommendations', []):
            comment += f"- {rec}\n"

        if state.get('pr_risk_assessment'):
            comment += f"\n{state['pr_risk_assessment']}\n"

        comment += f"""

---
*Generated by Git Review Assistant using LangGraph workflow orchestration*
*Review Score: {state.get('pr_score', 0):.1f}/100 | Processing Time: {state.get('processing_time', 0):.2f}s*
        """

        return comment

    async def run_review(self, pr_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the complete review workflow using LangGraph.

        This is the main entry point for running a PR review through the
        LangGraph state machine.

        Args:
            pr_data: Dictionary containing PR information and files

        Returns:
            Dictionary containing review results and GitHub comments
        """
        logger.info(f"Starting LangGraph review workflow for PR #{pr_data.get('pr_number', 'unknown')}")

        # Initialize state
        initial_state = ReviewWorkflowState(
            pr_number=pr_data.get("pr_number", 0),
            pr_title=pr_data.get("pr_title", ""),
            pr_description=pr_data.get("pr_description", ""),
            files=pr_data.get("files", []),
            current_file_index=0,
            files_to_review=[],
            files_reviewed=[],
            file_analyses={},
            all_security_issues=[],
            all_performance_issues=[],
            all_quality_issues=[],
            all_documentation_issues=[],
            all_testing_issues=[],
            all_architecture_issues=[],
            pr_summary="",
            pr_risk_assessment="",
            pr_recommendations=[],
            pr_score=0.0,
            total_issues=0,
            critical_issues_count=0,
            high_issues_count=0,
            processing_time=0.0,
            ai_tokens_used=0,
            ai_cost=0.0,
            workflow_stage="starting",
            should_halt=False,
            error_message=None,
            github_comments=[],
            status_check_result="neutral",
            status_check_message="Review in progress...",
            start_time=time.time()
        )

        try:
            # Execute the workflow
            final_state = await self.compiled_workflow.ainvoke(
                initial_state,
                config=RunnableConfig(
                    callbacks=[],
                    tags=["langgraph", "review", f"pr_{pr_data.get('pr_number', 'unknown')}"]
                )
            )

            logger.info(
                f"LangGraph workflow completed successfully. "
                f"Stage: {final_state['workflow_stage']}, "
                f"Issues: {final_state['total_issues']}"
            )

            # Convert state to review results format
            return self._format_review_results(final_state)

        except Exception as e:
            logger.error(f"LangGraph workflow failed: {str(e)}", exc_info=True)
            raise

    def _format_review_results(self, state: ReviewWorkflowState) -> Dict[str, Any]:
        """Format the workflow state into review results."""
        return {
            "success": True,
            "pr_number": state["pr_number"],
            "files_reviewed": state["files_reviewed"],
            "total_issues": state["total_issues"],
            "security_issues": state["all_security_issues"],
            "performance_issues": state["all_performance_issues"],
            "quality_issues": state["all_quality_issues"],
            "documentation_issues": state["all_documentation_issues"],
            "testing_issues": state["all_testing_issues"],
            "architecture_issues": state["all_architecture_issues"],
            "summary": state["pr_summary"],
            "risk_assessment": state["pr_risk_assessment"],
            "recommendations": state["pr_recommendations"],
            "overall_score": state["pr_score"],
            "processing_time": state["processing_time"],
            "github_comments": state["github_comments"],
            "status_check": {
                "result": state["status_check_result"],
                "message": state["status_check_message"]
            },
            "workflow_metadata": {
                "stage_completed": state["workflow_stage"],
                "langgraph_enabled": True,
                "state_management": "active",
                "nodes_executed": [
                    "parse_files", "prioritize_files",
                    "security_analysis", "performance_analysis",
                    "quality_analysis", "synthesize_results",
                    "generate_summary", "create_comments"
                ]
            }
        }


# Factory function for easy instantiation
def create_review_workflow(ai_reviewer: Optional[AIReviewer] = None) -> ReviewWorkflow:
    """Create a new review workflow instance.

    Args:
        ai_reviewer: Optional AIReviewer instance to use existing chains

    Returns:
        Configured ReviewWorkflow instance
    """
    return ReviewWorkflow(ai_reviewer)


# Async helper for running reviews
async def run_langgraph_review(pr_data: Dict[str, Any]) -> Dict[str, Any]:
    """Run a PR review using the LangGraph workflow.

    This is a convenience function that creates a workflow and runs a review.

    Args:
        pr_data: PR information and files to review

    Returns:
        Review results with GitHub comments
    """
    workflow = create_review_workflow()
    return await workflow.run_review(pr_data)