"""AI-powered code review engine using LangChain and OpenAI."""

import asyncio
import time
import json
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

# LangChain imports
from langchain.chat_models import ChatOpenAI
from langchain.prompts import ChatPromptTemplate, PromptTemplate
from langchain.schema import HumanMessage, SystemMessage, BaseMessage
from langchain.chains import LLMChain, SequentialChain
from langchain.output_parsers import PydanticOutputParser, OutputFixingParser
from langchain.callbacks import get_openai_callback
from langchain.memory import ConversationBufferMemory

# Pydantic for structured output
from pydantic import BaseModel, Field

from config.settings import settings
from config.logging import get_logger, review_logger
from models.review import ReviewIssue, IssueCategory, SeverityLevel, AIAnalysisResult
from models.github import PRFile
from services.security_scanner import SecurityScanner
from utils.helpers import get_file_language, calculate_complexity_score, format_review_comment

logger = get_logger(__name__)


# Pydantic models for structured AI output
class SecurityFinding(BaseModel):
    """Structured security finding from AI analysis."""
    type: str = Field(description="Type of security issue")
    severity: str = Field(description="Severity level: critical, high, medium, low")
    line_number: Optional[int] = Field(description="Line number where issue occurs")
    description: str = Field(description="Description of the security issue")
    recommendation: str = Field(description="Recommended fix")
    cwe_id: Optional[str] = Field(description="CWE identifier if applicable")


class PerformanceFinding(BaseModel):
    """Structured performance finding from AI analysis."""
    type: str = Field(description="Type of performance issue")
    severity: str = Field(description="Severity level: high, medium, low")
    line_number: Optional[int] = Field(description="Line number where issue occurs")
    description: str = Field(description="Description of the performance issue")
    recommendation: str = Field(description="Optimization suggestion")
    impact: str = Field(description="Expected performance impact")


class QualityFinding(BaseModel):
    """Structured quality finding from AI analysis."""
    type: str = Field(description="Type of quality issue")
    severity: str = Field(description="Severity level: warning, info")
    line_number: Optional[int] = Field(description="Line number where issue occurs")
    description: str = Field(description="Description of the quality issue")
    recommendation: str = Field(description="Improvement suggestion")


class AIReviewResult(BaseModel):
    """Structured AI review result."""
    security_findings: List[SecurityFinding] = Field(default_factory=list)
    performance_findings: List[PerformanceFinding] = Field(default_factory=list)
    quality_findings: List[QualityFinding] = Field(default_factory=list)
    overall_assessment: str = Field(description="Overall code assessment")
    confidence_score: float = Field(description="AI confidence in analysis (0-1)")


class AIReviewer:
    """LangChain-based AI code reviewer."""

    def __init__(self):
        # Initialize OpenAI model
        self.llm = ChatOpenAI(
            model_name=settings.OPENAI_MODEL,
            temperature=settings.OPENAI_TEMPERATURE,
            max_tokens=settings.OPENAI_MAX_TOKENS,
            openai_api_key=settings.OPENAI_API_KEY,
            streaming=False
        )

        # Initialize security scanner
        self.security_scanner = SecurityScanner()

        # Initialize output parsers
        self.security_parser = PydanticOutputParser(pydantic_object=SecurityFinding)
        self.performance_parser = PydanticOutputParser(pydantic_object=PerformanceFinding)
        self.quality_parser = PydanticOutputParser(pydantic_object=QualityFinding)
        self.result_parser = PydanticOutputParser(pydantic_object=AIReviewResult)

        # Setup prompts
        self._setup_prompts()

        # Setup chains
        self._setup_chains()

    def _setup_prompts(self):
        """Setup LangChain prompts for different analysis types."""

        # Security analysis prompt
        self.security_prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="""You are a security expert conducting a thorough code review.
            Analyze the provided code diff for security vulnerabilities including:

            1. Injection vulnerabilities (SQL, XSS, Command injection)
            2. Authentication and authorization issues
            3. Cryptographic weaknesses
            4. Input validation problems
            5. Information disclosure
            6. Insecure configurations
            7. Business logic flaws

            Focus ONLY on security issues. Be specific about:
            - Exact line numbers where issues occur
            - Severity level (critical, high, medium, low)
            - CWE identifiers when applicable
            - Concrete remediation steps

            Return valid JSON only."""),

            HumanMessage(content="""File: {filename}
Language: {language}
Code Diff:
{code_diff}

Analyze this code for security vulnerabilities. Return findings as a JSON array of objects with:
- type: string (brief issue type)
- severity: "critical"|"high"|"medium"|"low"
- line_number: number (if applicable)
- description: string (detailed explanation)
- recommendation: string (how to fix)
- cwe_id: string (if applicable)

Return only the JSON array, no other text.""")
        ])

        # Performance analysis prompt
        self.performance_prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="""You are a performance optimization expert.
            Analyze the provided code diff for performance issues including:

            1. Algorithmic inefficiencies (O(n²) vs O(n log n))
            2. Memory leaks and excessive memory usage
            3. Database query optimization opportunities
            4. Unnecessary computations or iterations
            5. Blocking operations in async contexts
            6. Resource management issues
            7. Caching opportunities

            Focus ONLY on performance. Be specific about:
            - Impact on performance (high, medium, low)
            - Quantifiable improvements where possible
            - Alternative approaches

            Return valid JSON only."""),

            HumanMessage(content="""File: {filename}
Language: {language}
Code Diff:
{code_diff}

Analyze this code for performance issues. Return findings as a JSON array of objects with:
- type: string (brief issue type)
- severity: "high"|"medium"|"low"
- line_number: number (if applicable)
- description: string (detailed explanation)
- recommendation: string (optimization suggestion)
- impact: string (expected improvement)

Return only the JSON array, no other text.""")
        ])

        # Code quality analysis prompt
        self.quality_prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="""You are a code quality expert and senior developer.
            Analyze the provided code diff for quality issues including:

            1. Code maintainability and readability
            2. SOLID principles violations
            3. Code smells and anti-patterns
            4. Naming conventions
            5. Function/class design issues
            6. Error handling problems
            7. Documentation gaps
            8. Testing considerations

            Focus ONLY on quality and maintainability. Be constructive and specific.

            Return valid JSON only."""),

            HumanMessage(content="""File: {filename}
Language: {language}
Code Diff:
{code_diff}

Analyze this code for quality issues. Return findings as a JSON array of objects with:
- type: string (brief issue type)
- severity: "warning"|"info"
- line_number: number (if applicable)
- description: string (detailed explanation)
- recommendation: string (improvement suggestion)

Return only the JSON array, no other text.""")
        ])

        # Overall assessment prompt
        self.assessment_prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="""You are a senior code reviewer providing an overall assessment.
            Based on the security, performance, and quality findings, provide:

            1. Overall code assessment (2-3 sentences)
            2. Confidence score (0.0-1.0) in your analysis
            3. Priority recommendations

            Be balanced, constructive, and helpful."""),

            HumanMessage(content="""Analysis Results:

Security Findings: {security_findings}
Performance Findings: {performance_findings}
Quality Findings: {quality_findings}

File: {filename}
Language: {language}

Provide an overall assessment including:
- overall_assessment: string (2-3 sentence summary)
- confidence_score: number (0.0-1.0)

Return as JSON only.""")
        ])

    def _setup_chains(self):
        """Setup LangChain chains for analysis."""

        # Individual analysis chains
        self.security_chain = LLMChain(
            llm=self.llm,
            prompt=self.security_prompt,
            output_key="security_analysis"
        )

        self.performance_chain = LLMChain(
            llm=self.llm,
            prompt=self.performance_prompt,
            output_key="performance_analysis"
        )

        self.quality_chain = LLMChain(
            llm=self.llm,
            prompt=self.quality_prompt,
            output_key="quality_analysis"
        )

        self.assessment_chain = LLMChain(
            llm=self.llm,
            prompt=self.assessment_prompt,
            output_key="overall_assessment"
        )

    async def review_pr_files(self, files: List[PRFile]) -> Dict[str, Any]:
        """Review all files in a pull request."""
        start_time = time.time()

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
                "chains_executed": 0
            }
        }

        logger.info(f"Starting AI review of {len(files)} files")

        # Process files concurrently (with semaphore to limit concurrent API calls)
        semaphore = asyncio.Semaphore(3)  # Limit to 3 concurrent API calls
        tasks = []

        for file in files:
            if self._should_review_file(file):
                task = self._review_single_file_with_semaphore(file, semaphore)
                tasks.append(task)

        if not tasks:
            logger.warning("No files to review")
            return review_results

        # Execute all file reviews
        file_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Aggregate results
        for i, result in enumerate(file_results):
            if isinstance(result, Exception):
                logger.error(f"Failed to review file {files[i].filename}: {str(result)}")
                continue

            if result:
                review_results["files_reviewed"].append(result)
                review_results["security_issues"].extend(result.get("security_issues", []))
                review_results["performance_issues"].extend(result.get("performance_issues", []))
                review_results["quality_issues"].extend(result.get("quality_issues", []))

                # Update AI metrics
                ai_metrics = result.get("ai_metrics", {})
                review_results["ai_metrics"]["total_tokens"] += ai_metrics.get("total_tokens", 0)
                review_results["ai_metrics"]["total_cost"] += ai_metrics.get("total_cost", 0.0)
                review_results["ai_metrics"]["chains_executed"] += ai_metrics.get("chains_executed", 0)

        # Calculate totals
        review_results["total_issues"] = (
                len(review_results["security_issues"]) +
                len(review_results["performance_issues"]) +
                len(review_results["quality_issues"])
        )

        # Generate overall summary and score
        if review_results["files_reviewed"]:
            summary_result = await self._generate_overall_summary(review_results)
            review_results.update(summary_result)

        review_results["processing_time"] = time.time() - start_time

        logger.info(
            "AI review completed",
            files_reviewed=len(review_results["files_reviewed"]),
            total_issues=review_results["total_issues"],
            processing_time=review_results["processing_time"],
            ai_cost=review_results["ai_metrics"]["total_cost"]
        )

        return review_results

    async def _review_single_file_with_semaphore(self, file: PRFile, semaphore: asyncio.Semaphore):
        """Review a single file with semaphore control."""
        async with semaphore:
            return await self._review_single_file(file)

    async def _review_single_file(self, file: PRFile) -> Dict[str, Any]:
        """Review a single file using AI analysis."""
        start_time = time.time()

        if not file.patch:
            logger.warning(f"No patch content for file {file.filename}")
            return None

        language = get_file_language(file.filename)
        complexity = calculate_complexity_score(file.patch)

        logger.info(
            f"Reviewing file {file.filename}",
            language=language,
            changes=file.changes,
            complexity=complexity
        )

        file_result = {
            "filename": file.filename,
            "language": language,
            "complexity": complexity,
            "security_issues": [],
            "performance_issues": [],
            "quality_issues": [],
            "ai_metrics": {
                "total_tokens": 0,
                "total_cost": 0.0,
                "chains_executed": 0
            }
        }

        try:
            # Prepare input for AI chains
            chain_input = {
                "filename": file.filename,
                "language": language,
                "code_diff": file.patch
            }

            # Run AI analysis chains
            with get_openai_callback() as cb:
                # Security analysis
                try:
                    security_result = await self._run_security_analysis(chain_input)
                    file_result["security_issues"] = security_result
                    file_result["ai_metrics"]["chains_executed"] += 1
                except Exception as e:
                    logger.error(f"Security analysis failed for {file.filename}: {str(e)}")

                # Performance analysis
                try:
                    performance_result = await self._run_performance_analysis(chain_input)
                    file_result["performance_issues"] = performance_result
                    file_result["ai_metrics"]["chains_executed"] += 1
                except Exception as e:
                    logger.error(f"Performance analysis failed for {file.filename}: {str(e)}")

                # Quality analysis
                try:
                    quality_result = await self._run_quality_analysis(chain_input)
                    file_result["quality_issues"] = quality_result
                    file_result["ai_metrics"]["chains_executed"] += 1
                except Exception as e:
                    logger.error(f"Quality analysis failed for {file.filename}: {str(e)}")

                # Update metrics
                file_result["ai_metrics"]["total_tokens"] = cb.total_tokens
                file_result["ai_metrics"]["total_cost"] = cb.total_cost

            processing_time = time.time() - start_time

            review_logger.ai_chain_executed(
                f"file_review_{file.filename}",
                processing_time,
                cb.prompt_tokens,
                cb.completion_tokens
            )

            logger.info(
                f"Completed review of {file.filename}",
                processing_time=processing_time,
                issues_found=len(file_result["security_issues"]) +
                             len(file_result["performance_issues"]) +
                             len(file_result["quality_issues"]),
                tokens_used=cb.total_tokens,
                cost=cb.total_cost
            )

            return file_result

        except Exception as e:
            logger.error(f"Failed to review file {file.filename}: {str(e)}")
            return None

    async def _run_security_analysis(self, chain_input: Dict[str, str]) -> List[Dict[str, Any]]:
        """Run security analysis chain."""
        try:
            result = await self.security_chain.arun(**chain_input)
            return self._parse_json_result(result, "security")
        except Exception as e:
            logger.error(f"Security analysis chain failed: {str(e)}")
            return []

    async def _run_performance_analysis(self, chain_input: Dict[str, str]) -> List[Dict[str, Any]]:
        """Run performance analysis chain."""
        try:
            result = await self.performance_chain.arun(**chain_input)
            return self._parse_json_result(result, "performance")
        except Exception as e:
            logger.error(f"Performance analysis chain failed: {str(e)}")
            return []

    async def _run_quality_analysis(self, chain_input: Dict[str, str]) -> List[Dict[str, Any]]:
        """Run quality analysis chain."""
        try:
            result = await self.quality_chain.arun(**chain_input)
            return self._parse_json_result(result, "quality")
        except Exception as e:
            logger.error(f"Quality analysis chain failed: {str(e)}")
            return []

    def _parse_json_result(self, result: str, analysis_type: str) -> List[Dict[str, Any]]:
        """Parse JSON result from AI analysis."""
        try:
            # Clean up the result string
            result = result.strip()
            if result.startswith("```json"):
                result = result[7:]
            if result.endswith("```"):
                result = result[:-3]
            result = result.strip()

            # Parse JSON
            findings = json.loads(result)

            # Ensure it's a list
            if not isinstance(findings, list):
                findings = [findings] if findings else []

            return findings

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse {analysis_type} JSON result: {str(e)}")
            logger.debug(f"Raw result: {result}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error parsing {analysis_type} result: {str(e)}")
            return []

    async def _generate_overall_summary(self, review_results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate overall summary and score."""
        try:
            # Prepare summary input
            summary_input = {
                "security_findings": len(review_results["security_issues"]),
                "performance_findings": len(review_results["performance_issues"]),
                "quality_findings": len(review_results["quality_issues"]),
                "filename": f"{len(review_results['files_reviewed'])} files",
                "language": "mixed"
            }

            with get_openai_callback() as cb:
                summary_result = await self.assessment_chain.arun(**summary_input)

            # Parse summary result
            try:
                summary_data = json.loads(summary_result.strip())
                summary = summary_data.get("overall_assessment", "Review completed")
                confidence = float(summary_data.get("confidence_score", 0.8))
            except:
                summary = "Review completed with AI analysis"
                confidence = 0.8

            # Calculate overall score
            score = self._calculate_overall_score(review_results)

            # Update AI metrics
            review_results["ai_metrics"]["total_tokens"] += cb.total_tokens
            review_results["ai_metrics"]["total_cost"] += cb.total_cost
            review_results["ai_metrics"]["chains_executed"] += 1

            return {
                "summary": summary,
                "overall_score": score,
                "confidence_score": confidence
            }

        except Exception as e:
            logger.error(f"Failed to generate overall summary: {str(e)}")
            return {
                "summary": "Review completed",
                "overall_score": self._calculate_overall_score(review_results),
                "confidence_score": 0.5
            }

    def _calculate_overall_score(self, review_results: Dict[str, Any]) -> float:
        """Calculate overall review score (0-10)."""
        base_score = 10.0

        # Deduct points for different issue types
        security_count = len(review_results["security_issues"])
        performance_count = len(review_results["performance_issues"])
        quality_count = len(review_results["quality_issues"])

        # Weight security issues more heavily
        critical_security = len([i for i in review_results["security_issues"]
                                if i.get("severity") == "critical"])
        high_security = len([i for i in review_results["security_issues"]
                            if i.get("severity") == "high"])

        # Deductions
        base_score -= critical_security * 3.0  # Critical security: -3 points each
        base_score -= high_security * 2.0      # High security: -2 points each
        base_score -= (security_count - critical_security - high_security) * 1.0  # Other security: -1 point
        base_score -= min(performance_count * 0.5, 2.0)  # Performance: max -2 points
        base_score -= min(quality_count * 0.2, 1.0)      # Quality: max -1 point

        return max(0.0, min(10.0, base_score))

    def _should_review_file(self, file: PRFile) -> bool:
        """Determine if a file should be reviewed."""
        # Skip deleted files
        if file.status == "removed":
            return False

        # Skip files without patch content
        if not file.patch:
            return False

        # Skip large files (over 10KB diff)
        if len(file.patch) > 10000:
            logger.warning(f"Skipping large file {file.filename} ({len(file.patch)} chars)")
            return False

        # Skip binary files or unrecognized types
        language = get_file_language(file.filename)
        if language == "unknown":
            return False

        return True


# Health check function
async def get_ai_health() -> Dict[str, Any]:
    """Check AI service health and availability."""
    try:
        # Simple test of OpenAI API
        test_llm = ChatOpenAI(
            model_name=settings.OPENAI_MODEL,
            temperature=0,
            max_tokens=10,
            openai_api_key=settings.OPENAI_API_KEY
        )

        test_message = [HumanMessage(content="test")]
        result = await test_llm.agenerate([test_message])

        return {
            "available": True,
            "model": settings.OPENAI_MODEL,
            "status": "healthy",
            "test_successful": True
        }

    except Exception as e:
        return {
            "available": False,
            "model": settings.OPENAI_MODEL,
            "status": "unhealthy",
            "error": str(e)
        }