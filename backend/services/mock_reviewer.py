"""Mock AI Reviewer for development and testing without OpenAI API.

This service provides fallback functionality when OpenAI API is not available,
inspired by the instructor's implementation approach.
"""

import time
import json
from typing import Dict, List, Any
from datetime import datetime

from config.logging import get_logger
from models.github import PRFile
from utils.helpers import get_file_language, calculate_complexity_score

logger = get_logger(__name__)


class MockAIReviewer:
    """Mock AI reviewer providing simulated responses for testing/demo."""

    def __init__(self):
        logger.info("Initializing Mock AI Reviewer (OpenAI not available)")

    async def review_pr_files(self, files: List[PRFile]) -> Dict[str, Any]:
        """Simulate PR file review without OpenAI."""
        start_time = time.time()

        logger.info(f"Mock review started for {len(files)} files")

        review_results = {
            "files_reviewed": [],
            "total_issues": 0,
            "security_issues": [],
            "performance_issues": [],
            "quality_issues": [],
            "summary": "",
            "overall_score": 0.0,
            "processing_time": 0.0,
            "ai_metrics": {
                "total_tokens": 0,
                "total_cost": 0.0,
                "chains_executed": 0,
                "mock_mode": True
            }
        }

        for file in files:
            if self._should_review_file(file):
                file_result = self._mock_review_file(file)
                if file_result:
                    review_results["files_reviewed"].append(file_result)
                    review_results["security_issues"].extend(file_result.get("security_issues", []))
                    review_results["performance_issues"].extend(file_result.get("performance_issues", []))
                    review_results["quality_issues"].extend(file_result.get("quality_issues", []))

        # Calculate totals
        review_results["total_issues"] = (
            len(review_results["security_issues"]) +
            len(review_results["performance_issues"]) +
            len(review_results["quality_issues"])
        )

        # Generate mock summary
        review_results.update(self._generate_mock_summary(review_results))
        review_results["processing_time"] = time.time() - start_time

        logger.info(
            "Mock review completed",
            files_reviewed=len(review_results["files_reviewed"]),
            total_issues=review_results["total_issues"],
            processing_time=review_results["processing_time"]
        )

        return review_results

    def _mock_review_file(self, file: PRFile) -> Dict[str, Any]:
        """Generate mock review for a single file."""
        language = get_file_language(file.filename)
        complexity = calculate_complexity_score(file.patch)
        lines = file.patch.count('\n') + 1

        file_result = {
            "filename": file.filename,
            "language": language,
            "complexity": complexity,
            "security_issues": [],
            "performance_issues": [],
            "quality_issues": [],
            "documentation_issues": [],
            "testing_issues": [],
            "architecture_issues": [],
            "ai_metrics": {
                "total_tokens": 0,
                "total_cost": 0.0,
                "chains_executed": 0,
                "mock_mode": True
            }
        }

        # Generate sample findings based on file characteristics
        # Security findings (pattern-based)
        if 'password' in file.patch.lower() or 'secret' in file.patch.lower():
            file_result["security_issues"].append({
                "type": "potential_credential_exposure",
                "severity": "high",
                "line_number": None,
                "description": "File contains keywords suggesting potential credential exposure",
                "recommendation": "Review for hardcoded credentials and move to environment variables",
                "cwe_id": "CWE-798",
                "confidence": 0.6
            })

        if 'eval(' in file.patch or 'exec(' in file.patch:
            file_result["security_issues"].append({
                "type": "code_injection",
                "severity": "critical",
                "line_number": None,
                "description": "Potential code injection vulnerability detected (eval/exec usage)",
                "recommendation": "Avoid using eval() and exec() with user input. Use safer alternatives.",
                "cwe_id": "CWE-94",
                "confidence": 0.8
            })

        # Performance findings (heuristic)
        if complexity > 15:
            file_result["performance_issues"].append({
                "type": "high_complexity",
                "severity": "medium",
                "line_number": None,
                "description": f"File has high complexity ({complexity}), may impact performance",
                "recommendation": "Consider refactoring to reduce complexity and improve maintainability",
                "impact": "May slow down execution and make testing difficult",
                "complexity_before": f"O(n) estimated",
                "complexity_after": "Could be improved with optimization"
            })

        if lines > 300:
            file_result["performance_issues"].append({
                "type": "large_file",
                "severity": "low",
                "line_number": None,
                "description": f"Large file ({lines} lines) may be difficult to maintain",
                "recommendation": "Consider splitting into smaller, focused modules",
                "impact": "Affects maintainability and team productivity",
                "complexity_before": "Large monolithic file",
                "complexity_after": "Smaller, focused modules"
            })

        # Quality findings (basic analysis)
        if not any(doc_keyword in file.patch.lower() for doc_keyword in ['"""', "'''", '/*', '//']):
            file_result["quality_issues"].append({
                "type": "missing_documentation",
                "severity": "warning",
                "line_number": None,
                "description": "File appears to lack comprehensive documentation",
                "recommendation": "Add docstrings, comments, and type hints to improve code clarity",
                "maintainability_impact": "Makes onboarding and maintenance more difficult"
            })

        # Documentation findings
        if language in ["python", "javascript", "typescript"]:
            file_result["documentation_issues"].append({
                "type": "documentation_review_needed",
                "severity": "info",
                "line_number": None,
                "description": "Documentation should be reviewed for completeness",
                "recommendation": "Ensure all public functions have docstrings and type hints",
                "coverage_impact": "Medium"
            })

        # Testing findings
        if 'test' not in file.filename.lower():
            file_result["testing_issues"].append({
                "type": "testing_coverage",
                "severity": "medium",
                "line_number": None,
                "description": "No associated test file detected",
                "recommendation": "Create corresponding test file to ensure code quality",
                "testability_impact": "High"
            })

        return file_result

    def _generate_mock_summary(self, review_results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate mock summary and scoring."""
        total_issues = review_results["total_issues"]
        security_count = len(review_results["security_issues"])
        performance_count = len(review_results["performance_issues"])
        quality_count = len(review_results["quality_issues"])

        # Calculate mock score (0-100)
        base_score = 100.0
        base_score -= security_count * 15
        base_score -= performance_count * 8
        base_score -= quality_count * 5
        overall_score = max(0.0, min(100.0, base_score))

        # Convert to letter grade
        if overall_score >= 90:
            letter_grade = "A"
        elif overall_score >= 80:
            letter_grade = "B"
        elif overall_score >= 70:
            letter_grade = "C"
        elif overall_score >= 60:
            letter_grade = "D"
        else:
            letter_grade = "F"

        # Generate summary message
        summary = f"""📋 **Mock Code Review Complete** (Demo Mode)

**Grade:** {letter_grade} ({overall_score:.1f}/100)

**Issues Found:**
- 🔒 Security: {security_count}
- ⚡ Performance: {performance_count}
- 🎯 Quality: {quality_count}
- **Total**: {total_issues}

**Note:** This is a mock review generated without AI analysis.
For production use, please configure OPENAI_API_KEY.

**Mock Analysis Summary:**
- {len(review_results['files_reviewed'])} files reviewed
- Basic pattern matching applied
- Heuristic complexity analysis performed
"""

        # Add issue-specific guidance
        if security_count > 0:
            summary += "\n**⚠️ Security Concerns:**\n"
            summary += "- Review potential credential exposure\n"
            summary += "- Check for injection vulnerabilities\n"

        if performance_count > 0:
            summary += "\n**⚡ Performance Notes:**\n"
            summary += "- Consider code complexity reduction\n"
            summary += "- Review file sizes and structure\n"

        if quality_count > 0:
            summary += "\n**🎯 Quality Improvements:**\n"
            summary += "- Add comprehensive documentation\n"
            summary += "- Implement type hints where applicable\n"

        summary += "\n**Next Steps:**\n"
        summary += "1. Configure OpenAI API for full AI-powered analysis\n"
        summary += "2. Review flagged issues manually\n"
        summary += "3. Run automated tests\n"

        return {
            "summary": summary,
            "overall_score": overall_score / 10,  # Convert to 0-10 scale
            "letter_grade": letter_grade,
            "scoring_breakdown": {
                "security_score": max(0, 100 - security_count * 15),
                "performance_score": max(0, 100 - performance_count * 8),
                "quality_score": max(0, 100 - quality_count * 5),
                "documentation_score": 75,
                "testing_score": 70,
                "architecture_score": 80,
                "overall_score": overall_score,
                "letter_grade": letter_grade
            },
            "code_suggestions": [],
            "priority_fixes": [
                "Configure OpenAI API for full analysis",
                "Review security findings manually",
                "Add comprehensive test coverage"
            ],
            "quick_wins": [
                "Add docstrings to functions",
                "Add type hints",
                "Extract magic numbers to constants"
            ],
            "confidence_score": 0.3  # Low confidence for mock mode
        }

    def _should_review_file(self, file: PRFile) -> bool:
        """Determine if a file should be reviewed (mock mode)."""
        # Skip deleted files
        if file.status == "removed":
            return False

        # Skip files without patch content
        if not file.patch:
            return False

        # Skip very large files
        if len(file.patch) > 50000:
            logger.warning(f"Skipping very large file {file.filename}")
            return False

        # Skip binary files
        language = get_file_language(file.filename)
        if language == "unknown":
            return False

        return True


async def get_mock_ai_health() -> Dict[str, Any]:
    """Return mock AI health status."""
    return {
        "available": True,
        "model": "mock-reviewer-v1",
        "status": "healthy",
        "test_successful": True,
        "mode": "mock",
        "message": "Mock AI reviewer active. Configure OPENAI_API_KEY for full analysis."
    }