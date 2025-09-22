"""AI-powered code review engine using LangChain and OpenAI.
Enhanced with course-inspired patterns and comprehensive analysis."""

import asyncio
import time
import json
import re
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

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
from utils.helpers import get_file_language, calculate_complexity_score, format_review_comment

logger = get_logger(__name__)


class VulnerabilityType(Enum):
    """Security vulnerability types with CWE mappings."""
    HARDCODED_SECRET = ("hardcoded_secret", "CWE-798")
    CODE_INJECTION = ("code_injection", "CWE-94")
    COMMAND_INJECTION = ("command_injection", "CWE-78")
    SQL_INJECTION = ("sql_injection", "CWE-89")
    PATH_TRAVERSAL = ("path_traversal", "CWE-22")
    WEAK_CRYPTO = ("weak_crypto", "CWE-327")
    INSECURE_RANDOM = ("insecure_random", "CWE-338")


@dataclass
class PatternFinding:
    """Pattern-based security finding."""
    vulnerability_type: VulnerabilityType
    line_number: int
    line_content: str
    severity: str
    description: str
    recommendation: str
    confidence: float
    cwe_id: str


# Enhanced Pydantic models for structured AI output
class SecurityFinding(BaseModel):
    """Enhanced security finding from AI analysis."""
    model_config = {'protected_namespaces': ()}

    type: str = Field(description="Type of security issue")
    severity: str = Field(description="Severity level: critical, high, medium, low")
    line_number: Optional[int] = Field(description="Line number where issue occurs")
    description: str = Field(description="Description of the security issue")
    recommendation: str = Field(description="Recommended fix")
    cwe_id: Optional[str] = Field(description="CWE identifier if applicable")
    confidence: float = Field(description="Confidence score 0-1", default=0.8)


class PerformanceFinding(BaseModel):
    """Enhanced performance finding from AI analysis."""
    model_config = {'protected_namespaces': ()}

    type: str = Field(description="Type of performance issue")
    severity: str = Field(description="Severity level: high, medium, low")
    line_number: Optional[int] = Field(description="Line number where issue occurs")
    description: str = Field(description="Description of the performance issue")
    recommendation: str = Field(description="Optimization suggestion")
    impact: str = Field(description="Expected performance impact")
    complexity_before: Optional[str] = Field(description="Current complexity", default="Unknown")
    complexity_after: Optional[str] = Field(description="Optimized complexity", default="Unknown")


class QualityFinding(BaseModel):
    """Enhanced quality finding from AI analysis."""
    model_config = {'protected_namespaces': ()}

    type: str = Field(description="Type of quality issue")
    severity: str = Field(description="Severity level: warning, info")
    line_number: Optional[int] = Field(description="Line number where issue occurs")
    description: str = Field(description="Description of the quality issue")
    recommendation: str = Field(description="Improvement suggestion")
    maintainability_impact: str = Field(description="Impact on team productivity", default="Unknown")


class DocumentationFinding(BaseModel):
    """Documentation and comments analysis."""
    model_config = {'protected_namespaces': ()}

    type: str = Field(description="Type of documentation issue")
    severity: str = Field(description="Severity level: warning, info")
    line_number: Optional[int] = Field(description="Line number where issue occurs")
    description: str = Field(description="Description of the documentation issue")
    recommendation: str = Field(description="Documentation improvement suggestion")
    coverage_impact: str = Field(description="Impact on code understanding", default="Medium")

class TestingFinding(BaseModel):
    """Testing and testability analysis."""
    model_config = {'protected_namespaces': ()}

    type: str = Field(description="Type of testing issue")
    severity: str = Field(description="Severity level: high, medium, low")
    line_number: Optional[int] = Field(description="Line number where issue occurs")
    description: str = Field(description="Description of the testing issue")
    recommendation: str = Field(description="Testing improvement suggestion")
    testability_impact: str = Field(description="Impact on code testability", default="Medium")

class ArchitectureFinding(BaseModel):
    """Architecture and design principles analysis."""
    model_config = {'protected_namespaces': ()}

    type: str = Field(description="Type of architectural issue")
    severity: str = Field(description="Severity level: high, medium, low")
    line_number: Optional[int] = Field(description="Line number where issue occurs")
    description: str = Field(description="Description of the architectural issue")
    recommendation: str = Field(description="Architecture improvement suggestion")
    principle_violated: str = Field(description="SOLID principle or pattern violated", default="Unknown")

class CodeSuggestion(BaseModel):
    """Code improvement suggestions with examples."""
    model_config = {'protected_namespaces': ()}

    type: str = Field(description="Type of improvement")
    line_number: Optional[int] = Field(description="Line number to improve")
    current_code: str = Field(description="Current code snippet")
    suggested_code: str = Field(description="Improved code suggestion")
    explanation: str = Field(description="Why this improvement is better")
    impact: str = Field(description="Expected improvement impact")

class ScoringBreakdown(BaseModel):
    """Detailed scoring breakdown."""
    security_score: float = Field(description="Security score 0-100", default=100.0)
    performance_score: float = Field(description="Performance score 0-100", default=100.0)
    quality_score: float = Field(description="Code quality score 0-100", default=100.0)
    documentation_score: float = Field(description="Documentation score 0-100", default=100.0)
    testing_score: float = Field(description="Testing score 0-100", default=100.0)
    architecture_score: float = Field(description="Architecture score 0-100", default=100.0)
    overall_score: float = Field(description="Weighted overall score 0-100", default=100.0)
    letter_grade: str = Field(description="Letter grade A-F", default="A")

class AIReviewResult(BaseModel):
    """Enhanced AI review result with comprehensive analysis."""
    model_config = {'protected_namespaces': ()}

    # Comprehensive findings
    security_findings: List[SecurityFinding] = Field(default_factory=list)
    performance_findings: List[PerformanceFinding] = Field(default_factory=list)
    quality_findings: List[QualityFinding] = Field(default_factory=list)
    documentation_findings: List[DocumentationFinding] = Field(default_factory=list)
    testing_findings: List[TestingFinding] = Field(default_factory=list)
    architecture_findings: List[ArchitectureFinding] = Field(default_factory=list)

    # Code suggestions with examples
    code_suggestions: List[CodeSuggestion] = Field(default_factory=list)

    # Enhanced scoring
    scoring: ScoringBreakdown = Field(default_factory=ScoringBreakdown)

    # Summary and assessment
    overall_assessment: str = Field(description="Overall code assessment")
    summary: str = Field(description="Executive summary of review")

    # Actionable recommendations
    priority_fixes: List[str] = Field(description="Top 3 critical fixes", default_factory=list)
    quick_wins: List[str] = Field(description="Easy improvements", default_factory=list)
    long_term_improvements: List[str] = Field(description="Refactoring suggestions", default_factory=list)

    # Learning and improvement
    learning_resources: List[str] = Field(description="Educational links", default_factory=list)
    best_practices_violated: List[str] = Field(description="Violated best practices", default_factory=list)

    # Time estimates
    estimated_fix_time: str = Field(description="Time to fix critical issues", default="Unknown")

    # Legacy fields for compatibility
    confidence_score: float = Field(description="AI confidence in analysis (0-1)", default=0.9)
    line_by_line_review: str = Field(description="Detailed line-by-line analysis", default="")
    refactored_code: Optional[str] = Field(description="Improved code version", default=None)
    improvement_summary: List[str] = Field(description="List of improvements made", default_factory=list)


class AIReviewer:
    """LangChain-based AI code reviewer with course-inspired enhancements."""

    def __init__(self):
        # Initialize OpenAI model
        self.llm = ChatOpenAI(
            model_name=settings.OPENAI_MODEL,
            temperature=settings.OPENAI_TEMPERATURE,
            max_tokens=settings.OPENAI_MAX_TOKENS,
            openai_api_key=settings.OPENAI_API_KEY,
            streaming=False
        )

        # Initialize pattern-based security detection
        self._setup_security_patterns()

        # Initialize output parsers
        self.security_parser = PydanticOutputParser(pydantic_object=SecurityFinding)
        self.performance_parser = PydanticOutputParser(pydantic_object=PerformanceFinding)
        self.quality_parser = PydanticOutputParser(pydantic_object=QualityFinding)
        self.result_parser = PydanticOutputParser(pydantic_object=AIReviewResult)

        # Setup enhanced prompts
        self._setup_prompts()

        # Setup chains
        self._setup_chains()

    def _setup_security_patterns(self):
        """Setup regex patterns for vulnerability detection based on bad_code_python.py."""

        # Hardcoded secrets patterns (inspired by bad_code_python.py lines 15-18)
        self.secret_patterns = [
            # API Keys
            (r'(?i)(api_key|apikey)\s*=\s*["\']([a-z0-9\-_]{8,})["\']', "API Key"),
            (r'(?i)["\']sk-[a-zA-Z0-9]{8,}["\']', "OpenAI API Key"),
            (r'(?i)["\']ghp_[a-zA-Z0-9]{36}["\']', "GitHub Token"),

            # Passwords and secrets
            (r'(?i)(password|pwd|secret|token)\s*=\s*["\']([^"\']{8,})["\']', "Password/Secret"),
            (r'(?i)SECRET_KEY\s*=\s*["\']([^"\']{10,})["\']', "Secret Key"),

            # Database credentials
            (r'(?i)(db_password|database_password)\s*=\s*["\']([^"\']+)["\']', "Database Password"),

            # Environment variable assignments with secrets
            (r'os\.environ\[["\']([^"\']*(?:secret|key|password|token)[^"\']*)["\']]\s*=\s*["\']([^"\']+)["\']', "Environment Secret"),
        ]

        # Code injection patterns (line 59)
        self.code_injection_patterns = [
            (r'\beval\s*\(\s*([^)]+)\s*\)', "eval() usage with user input"),
            (r'\bexec\s*\(\s*([^)]+)\s*\)', "exec() usage with user input"),
            (r'__import__\s*\(\s*([^)]+)\s*\)', "Dynamic import with user input"),
            (r'compile\s*\(\s*([^,]+),', "Code compilation with user input"),
        ]

        # Command injection patterns (line 66)
        self.command_injection_patterns = [
            (r'subprocess\.(run|call|check_output|Popen)\s*\(\s*f?["\']([^"\']* \{[^}]* \}[^"\']* )["\'].*shell\s*=\s*True', "Subprocess with shell=True and f-string"),
            (r'subprocess\.(run|call|check_output|Popen)\s*\(\s*([^,]+\s*\+[^,]+ ).*shell\s*=\s*True', "Subprocess with shell=True and concatenation"),
            (r'os\.system\s*\(\s*f?["\']([^"\']* \{[^}]* \}[^"\']* )["\']', "os.system with f-string"),
            (r'os\.system\s*\(\s*([^)]+\s*\+[^)]+ )', "os.system with concatenation"),
        ]

        # SQL injection patterns (line 75)
        self.sql_injection_patterns = [
            (r'["\']SELECT[^"\']*\{[^}]*\}[^"\']*["\']', "SQL query with f-string"),
            (r'["\']SELECT[^"\']*%[^"\']*["\'].*%', "SQL query with % formatting"),
            (r'cursor\.execute\s*\(\s*f?["\']([^"\']*\{[^}]*\}[^"\']*)["\']', "SQL execute with f-string"),
            (r'["\'](?:SELECT|INSERT|UPDATE|DELETE)[^"\']*\+[^"\']*["\']', "SQL query with concatenation"),
            (r'f["\']SELECT[^"\']*\{[^}]*\}[^"\']*["\']', "F-string SQL query"),
            (r'f"[^"]*\{[^}]*\}[^"]*"', "General f-string with variables"),
        ]

    def _setup_prompts(self):
        """Setup enhanced LangChain prompts with course-inspired patterns."""

        # Enhanced security analysis prompt with specific patterns from course
        self.security_prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="""You are a cybersecurity expert conducting a comprehensive code security review.

CRITICAL SECURITY PATTERNS TO DETECT:

🔴 CRITICAL VULNERABILITIES:

1. HARDCODED SECRETS:
   - Patterns: API_KEY = "sk-...", PASSWORD = "...", SECRET_TOKEN = "...", os.environ["SECRET"] = "..."
   - Example: DATABASE_PASSWORD = "admin123"
   - CWE: CWE-798 (Use of Hard-coded Credentials)

2. CODE INJECTION:
   - Patterns: eval(user_input), exec(user_data), __import__(user_string)
   - Example: calculation = eval(user_data.get("formula", "0"))
   - CWE: CWE-94 (Improper Control of Generation of Code)

3. COMMAND INJECTION:
   - Patterns: subprocess.run(f"command {user_input}", shell=True), os.system(f"cmd {input}")
   - Example: command = f"cat {filename}" with subprocess.run(command, shell=True)
   - CWE: CWE-78 (OS Command Injection)

4. SQL INJECTION:
   - Patterns: f"SELECT * FROM table WHERE id = '{user_input}'", % formatting in SQL
   - Example: query = f"SELECT * FROM users WHERE id = '{user_id}'"
   - CWE: CWE-89 (SQL Injection)

ANALYSIS REQUIREMENTS:
- Provide EXACT line numbers for each finding
- Map to CWE identifiers when possible
- Include severity: critical, high, medium, low
- Provide concrete remediation steps
- Consider context and false positive risk

Return findings as JSON array with structure:
{
  "type": "brief_issue_name",
  "severity": "critical|high|medium|low",
  "line_number": number,
  "description": "detailed_explanation",
  "recommendation": "concrete_fix_steps",
  "cwe_id": "CWE-XXX",
  "confidence": 0.95
}"""),

            HumanMessage(content="""File: {filename}
Language: {language}
Code to analyze:
{code_diff}

Analyze this code for security vulnerabilities using the patterns above. Focus on:
1. Exact line numbers where issues occur
2. High confidence findings (avoid false positives)
3. Actionable remediation steps
4. CWE mapping where applicable

Return ONLY a JSON array of findings, no other text.""")
        ])

        # Enhanced performance analysis prompt with O(n) complexity detection
        self.performance_prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="""You are a performance optimization expert analyzing code for efficiency issues.

PERFORMANCE ANTI-PATTERNS TO DETECT:

🔴 HIGH IMPACT:

1. EXPENSIVE INITIALIZATION:
   - Pattern: Loading all data in __init__, self.all_items = load_everything()
   - Example: self.all_users = self.load_all_users() # Loads 10,000 users upfront
   - Better: Lazy loading, pagination, on-demand loading

2. O(N) SEARCH IN COLLECTIONS:
   - Pattern: for item in large_list: if item.id == target_id
   - Example: Linear search through all users for one ID
   - Better: Use dict/set for O(1) lookup, index by ID

3. STRING CONCATENATION IN LOOPS:
   - Pattern: result = ""; for item in items: result += item + ","
   - Example: O(n²) complexity due to string immutability
   - Better: join(), list comprehension, f-strings

4. INEFFICIENT MEMBERSHIP TESTING:
   - Pattern: if item in large_list (repeated checks)
   - Example: Checking membership in list vs set
   - Better: Convert to set for O(1) lookup

🟡 MEDIUM IMPACT:

5. POOR ALGORITHM CHOICES:
   - Pattern: Bubble sort O(n²), nested loops for sorting
   - Example: Manual sorting instead of built-in sort()
   - Better: Use optimized algorithms (quicksort, mergesort)

6. EXPONENTIAL RECURSION:
   - Pattern: Fibonacci without memoization, tree recursion
   - Example: fibonacci(n-1) + fibonacci(n-2) recalculates same values
   - Better: Dynamic programming, memoization, iterative approach

7. MEMORY INEFFICIENCY:
   - Pattern: Loading entire file into memory, keeping large objects
   - Example: all_lines = f.readlines() for large files
   - Better: Stream processing, generators, line-by-line reading

ANALYSIS REQUIREMENTS:
- Estimate performance impact (high/medium/low)
- Provide Big O complexity analysis
- Suggest specific optimizations
- Include before/after code examples when helpful

Return findings as JSON array."""),

            HumanMessage(content="""File: {filename}
Language: {language}
Code to analyze:
{code_diff}

Analyze this code for performance issues using the patterns above. Focus on:
1. Algorithmic complexity (O(n), O(n²), etc.)
2. Memory usage patterns
3. Specific optimization opportunities
4. Quantifiable impact estimates

Return ONLY a JSON array with structure:
{
  "type": "issue_type",
  "severity": "high|medium|low",
  "line_number": number,
  "description": "detailed_explanation_with_complexity",
  "recommendation": "specific_optimization_steps",
  "impact": "quantified_improvement_estimate",
  "complexity_before": "O(n²)",
  "complexity_after": "O(n log n)"
}""")
        ])

        # Enhanced code quality analysis prompt detecting maintainability issues
        self.quality_prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="""You are a senior software architect reviewing code for quality and maintainability.

CODE QUALITY ANTI-PATTERNS TO DETECT:

🔴 CRITICAL QUALITY ISSUES:

1. TOO MANY PARAMETERS:
   - Pattern: def function(a, b, c, d, e, f, g, h) # 5+ parameters
   - Example: doEverything(a, b, c, d, e, f, g, h)
   - Better: Configuration object, builder pattern, parameter object

2. DEEP NESTING:
   - Pattern: 4+ levels of if/for nesting
   - Example: if d: if e: if f: if g: if h: return x
   - Better: Early returns, guard clauses, extract methods

3. MAGIC NUMBERS:
   - Pattern: Unexplained numeric constants
   - Example: if a > 42: x = b * 3.14159
   - Better: Named constants, configuration

🟡 HIGH PRIORITY:

4. GLOBAL STATE MODIFICATION:
   - Pattern: global variables, mutable module-level state
   - Example: global global_counter; global_counter += 1
   - Better: Class state, dependency injection, immutable data

5. POOR EXCEPTION HANDLING:
   - Pattern: bare except:, silent failures, generic exceptions
   - Example: except: pass # Silent failure
   - Better: Specific exceptions, logging, graceful degradation

6. MUTABLE DEFAULT ARGUMENTS:
   - Pattern: def function(items=[]), def function(cache={})
   - Example: def add_item(item, items=[])
   - Better: def add_item(item, items=None): items = items or []

🟢 MEDIUM PRIORITY:

7. LONG FUNCTIONS/CLASSES:
   - Pattern: Functions > 50 lines, classes > 500 lines
   - Better: Single responsibility, extract methods

8. POOR NAMING:
   - Pattern: Single letter variables, unclear names
   - Example: def doEverything, variable names like 'x', 'data'
   - Better: Descriptive names, intention-revealing

9. MISSING DOCUMENTATION:
   - Pattern: Functions without docstrings, unclear purpose
   - Better: Comprehensive docstrings, type hints

10. ANTI-PATTERNS:
    - Pattern: Not using list comprehensions, manual enumeration
    - Example: for i in range(len(items)): instead of enumerate
    - Better: Pythonic constructs, built-in functions

ANALYSIS REQUIREMENTS:
- Focus on maintainability impact
- Provide refactoring suggestions
- Consider team productivity impact
- Include readability improvements

Return findings as JSON array."""),

            HumanMessage(content="""File: {filename}
Language: {language}
Code to analyze:
{code_diff}

Analyze this code for quality issues using the patterns above. Focus on:
1. Maintainability and readability
2. SOLID principles violations
3. Language-specific best practices
4. Team collaboration impact

Return ONLY a JSON array with structure:
{
  "type": "quality_issue_type",
  "severity": "warning|info",
  "line_number": number,
  "description": "detailed_explanation",
  "recommendation": "specific_improvement_steps",
  "maintainability_impact": "how_this_affects_team_productivity"
}""")
        ])

        # Line-by-line analysis prompt inspired by course notebooks
        self.line_by_line_prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="""You are conducting a detailed line-by-line code review like a senior developer mentor.

Provide line-by-line analysis including:
1. Logic explanation for complex lines
2. Potential improvements
3. Best practice suggestions
4. Educational insights

Focus on being constructive and educational."""),

            HumanMessage(content="""File: {filename}
Language: {language}
Code to analyze:
{code_diff}

Provide line-by-line review in this format:

**Line-by-Line Review:**
- Line X: [Explanation of what this line does and any concerns]
- Line Y: [Analysis and suggestions]

**Key Observations:**
- [Overall patterns noticed]
- [Main areas for improvement]

**Learning Opportunities:**
- [Educational insights about better patterns]

Return as structured text, not JSON.""")
        ])

        # Refactoring prompt for improved code generation
        self.refactoring_prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="""You are a code improvement specialist who provides refactored versions of problematic code.

Your task:
1. Identify the main issues in the provided code
2. Create an improved version that fixes these issues
3. Explain the improvements made
4. Ensure the refactored code maintains the same functionality

Focus on:
- Security improvements
- Performance optimizations
- Code quality enhancements
- Best practices implementation"""),

            HumanMessage(content="""Original Code:
{code}

Language: {language}
Issues Found: {issues_summary}

Provide a refactored version that addresses the identified issues:

**Refactored Code:**
```{language}
[improved_code_here]
```

**Improvements Made:**
1. [Security fixes]
2. [Performance optimizations]
3. [Quality improvements]

**Key Changes Explained:**
- [Detailed explanation of major changes]
- [Why these changes improve the code]""")
        ])

        # Overall assessment prompt for generating summary and score
        self.assessment_prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="""You are a senior code reviewer providing an overall assessment of a code review.

Based on the findings from security, performance, and quality analysis, provide:
1. Overall assessment summary
2. Confidence score in the analysis (0.0 to 1.0)
3. Key recommendations for the development team

Focus on:
- Critical issues that need immediate attention
- Overall code health and maintainability
- Team productivity impact
- Actionable next steps"""),

            HumanMessage(content="""Review Summary:
- Files analyzed: {filename}
- Language: {language}
- Security findings: {security_findings}
- Performance findings: {performance_findings}
- Quality findings: {quality_findings}

Provide overall assessment as JSON:

{{
  "overall_assessment": "comprehensive_summary_of_findings_and_recommendations",
  "confidence_score": 0.85,
  "key_recommendations": ["recommendation1", "recommendation2", "recommendation3"],
  "priority_actions": ["urgent_action1", "urgent_action2"]
}}""")
        ])

        # Documentation analysis prompt
        self.documentation_prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="""You are a documentation specialist reviewing code for comprehensive documentation coverage.

DOCUMENTATION REQUIREMENTS TO CHECK:

🔴 CRITICAL DOCUMENTATION ISSUES:

1. MISSING FUNCTION DOCSTRINGS:
   - Pattern: Functions without docstrings, especially public APIs
   - Example: def complex_function(data, config): # No docstring
   - Better: Complete docstrings with args, returns, raises

2. MISSING TYPE HINTS:
   - Pattern: Functions without type annotations
   - Example: def process(data): return data.upper()
   - Better: def process(data: str) -> str: return data.upper()

3. UNCLEAR VARIABLE NAMES:
   - Pattern: Single letters, abbreviations, unclear names
   - Example: d = get_data(); x = d.process()
   - Better: user_data = get_data(); processed_result = user_data.process()

🟡 HIGH PRIORITY:

4. MISSING CLASS DOCUMENTATION:
   - Pattern: Classes without docstrings
   - Better: Comprehensive class documentation

5. MISSING INLINE COMMENTS:
   - Pattern: Complex logic without explanation
   - Better: Comments explaining non-obvious code

6. OUTDATED COMMENTS:
   - Pattern: Comments that don't match current code
   - Better: Keep comments synchronized with code

Return findings as JSON array."""),

            HumanMessage(content="""File: {filename}
Language: {language}
Code to analyze:
{code_diff}

Analyze documentation coverage and clarity. Return ONLY a JSON array:

{{
  "type": "documentation_issue_type",
  "severity": "warning|info",
  "line_number": number,
  "description": "specific_documentation_issue",
  "recommendation": "how_to_improve_documentation",
  "coverage_impact": "High|Medium|Low"
}}""")
        ])

        # Testing analysis prompt
        self.testing_prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="""You are a testing specialist reviewing code for testability and testing patterns.

TESTING ISSUES TO DETECT:

🔴 CRITICAL TESTING ISSUES:

1. HARD TO TEST CODE:
   - Pattern: Tight coupling, static dependencies, global state
   - Example: def process(): data = requests.get(GLOBAL_URL)
   - Better: Dependency injection, mocking capabilities

2. MISSING ERROR HANDLING:
   - Pattern: No exception handling for external calls
   - Example: result = api.call() # Can throw exceptions
   - Better: try/except with specific exception types

3. UNTESTABLE SIDE EFFECTS:
   - Pattern: Functions that modify global state or files
   - Better: Pure functions, dependency injection

🟡 HIGH PRIORITY:

4. COMPLEX FUNCTIONS:
   - Pattern: Functions doing multiple things (hard to test)
   - Better: Single responsibility functions

5. MISSING VALIDATION:
   - Pattern: No input validation
   - Better: Validate inputs, handle edge cases

Return findings as JSON array."""),

            HumanMessage(content="""File: {filename}
Language: {language}
Code to analyze:
{code_diff}

Analyze code testability and testing patterns. Return ONLY a JSON array:

{{
  "type": "testing_issue_type",
  "severity": "high|medium|low",
  "line_number": number,
  "description": "specific_testing_issue",
  "recommendation": "how_to_improve_testability",
  "testability_impact": "High|Medium|Low"
}}""")
        ])

        # Architecture analysis prompt
        self.architecture_prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="""You are a software architect reviewing code for design principles and architecture patterns.

SOLID PRINCIPLES & ARCHITECTURE ANTI-PATTERNS:

🔴 CRITICAL ARCHITECTURE ISSUES:

1. SINGLE RESPONSIBILITY VIOLATION:
   - Pattern: Classes/functions doing multiple unrelated things
   - Example: class UserManagerEmailSenderLogger
   - Better: Separate concerns into different classes

2. OPEN/CLOSED PRINCIPLE VIOLATION:
   - Pattern: Need to modify existing code to add features
   - Better: Use interfaces, inheritance, composition

3. DEPENDENCY INVERSION VIOLATION:
   - Pattern: High-level modules depending on low-level modules
   - Example: class Service: def __init__(self): self.db = MySQL()
   - Better: class Service: def __init__(self, db: Database)

🟡 HIGH PRIORITY:

4. INTERFACE SEGREGATION VIOLATION:
   - Pattern: Fat interfaces with unused methods
   - Better: Small, focused interfaces

5. LISKOV SUBSTITUTION VIOLATION:
   - Pattern: Subclasses that can't replace parent
   - Better: Proper inheritance hierarchy

6. GOD OBJECTS:
   - Pattern: Classes that know too much or do too much
   - Better: Smaller, focused classes

Return findings as JSON array."""),

            HumanMessage(content="""File: {filename}
Language: {language}
Code to analyze:
{code_diff}

Analyze architectural design and SOLID principles. Return ONLY a JSON array:

{{
  "type": "architecture_issue_type",
  "severity": "high|medium|low",
  "line_number": number,
  "description": "specific_architecture_issue",
  "recommendation": "how_to_fix_architecture",
  "principle_violated": "SRP|OCP|LSP|ISP|DIP|Other"
}}""")
        ])

        # Enhanced scoring and suggestions prompt
        self.enhanced_scoring_prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="""You are a comprehensive code reviewer providing final scoring and actionable recommendations.

SCORING CRITERIA (0-100 scale):

- Security Score: Deduct 20 points per critical, 10 per high, 5 per medium, 2 per low
- Performance Score: Deduct 15 points per high, 8 per medium, 3 per low
- Quality Score: Deduct 10 points per warning, 5 per info
- Documentation Score: Deduct 8 points per missing docstring, 5 per type hint, 3 per comment
- Testing Score: Deduct 12 points per testability issue
- Architecture Score: Deduct 15 points per SOLID violation

LETTER GRADES:
- A: 90-100 (Excellent)
- B: 80-89 (Good)
- C: 70-79 (Acceptable)
- D: 60-69 (Needs improvement)
- F: 0-59 (Major issues)

Provide actionable code suggestions with before/after examples."""),

            HumanMessage(content="""Analysis Results:
Security: {security_findings}
Performance: {performance_findings}
Quality: {quality_findings}
Documentation: {documentation_findings}
Testing: {testing_findings}
Architecture: {architecture_findings}

Code to analyze:
{code_diff}

Return comprehensive scoring and suggestions as JSON:

{{
  "scoring": {{
    "security_score": 95,
    "performance_score": 88,
    "quality_score": 92,
    "documentation_score": 75,
    "testing_score": 85,
    "architecture_score": 90,
    "overall_score": 87,
    "letter_grade": "B"
  }},
  "code_suggestions": [
    {{
      "type": "Security Fix",
      "line_number": 15,
      "current_code": "password = request.args.get('pwd')",
      "suggested_code": "password = request.form.get('pwd')  # Use POST for sensitive data",
      "explanation": "Passwords should not be sent via GET parameters",
      "impact": "High security improvement"
    }}
  ],
  "priority_fixes": ["Fix SQL injection on line 23", "Add input validation", "Improve error handling"],
  "quick_wins": ["Add type hints", "Add docstrings", "Extract magic numbers"],
  "long_term_improvements": ["Refactor to use dependency injection", "Implement proper error handling strategy"],
  "learning_resources": ["https://owasp.org/www-project-top-ten/", "https://docs.python.org/3/library/typing.html"],
  "estimated_fix_time": "2-4 hours"
}}""")
        ])

    def _setup_chains(self):
        """Setup enhanced LangChain chains for comprehensive analysis."""

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

        self.line_by_line_chain = LLMChain(
            llm=self.llm,
            prompt=self.line_by_line_prompt,
            output_key="line_by_line_analysis"
        )

        self.refactoring_chain = LLMChain(
            llm=self.llm,
            prompt=self.refactoring_prompt,
            output_key="refactoring_analysis"
        )

        self.assessment_chain = LLMChain(
            llm=self.llm,
            prompt=self.assessment_prompt,
            output_key="overall_assessment"
        )

        # New comprehensive analysis chains
        self.documentation_chain = LLMChain(
            llm=self.llm,
            prompt=self.documentation_prompt,
            output_key="documentation_analysis"
        )

        self.testing_chain = LLMChain(
            llm=self.llm,
            prompt=self.testing_prompt,
            output_key="testing_analysis"
        )

        self.architecture_chain = LLMChain(
            llm=self.llm,
            prompt=self.architecture_prompt,
            output_key="architecture_analysis"
        )

        self.enhanced_scoring_chain = LLMChain(
            llm=self.llm,
            prompt=self.enhanced_scoring_prompt,
            output_key="enhanced_scoring"
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
            "documentation_issues": [],
            "testing_issues": [],
            "architecture_issues": [],
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

                # Documentation analysis
                try:
                    documentation_result = await self._run_documentation_analysis(chain_input)
                    file_result["documentation_issues"] = documentation_result
                    file_result["ai_metrics"]["chains_executed"] += 1
                except Exception as e:
                    logger.error(f"Documentation analysis failed for {file.filename}: {str(e)}")

                # Testing analysis
                try:
                    testing_result = await self._run_testing_analysis(chain_input)
                    file_result["testing_issues"] = testing_result
                    file_result["ai_metrics"]["chains_executed"] += 1
                except Exception as e:
                    logger.error(f"Testing analysis failed for {file.filename}: {str(e)}")

                # Architecture analysis
                try:
                    architecture_result = await self._run_architecture_analysis(chain_input)
                    file_result["architecture_issues"] = architecture_result
                    file_result["ai_metrics"]["chains_executed"] += 1
                except Exception as e:
                    logger.error(f"Architecture analysis failed for {file.filename}: {str(e)}")

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

    async def _run_documentation_analysis(self, chain_input: Dict[str, str]) -> List[Dict[str, Any]]:
        """Run documentation analysis chain."""
        try:
            result = await self.documentation_chain.arun(**chain_input)
            return self._parse_json_result(result, "documentation")
        except Exception as e:
            logger.error(f"Documentation analysis chain failed: {str(e)}")
            return []

    async def _run_testing_analysis(self, chain_input: Dict[str, str]) -> List[Dict[str, Any]]:
        """Run testing analysis chain."""
        try:
            result = await self.testing_chain.arun(**chain_input)
            return self._parse_json_result(result, "testing")
        except Exception as e:
            logger.error(f"Testing analysis chain failed: {str(e)}")
            return []

    async def _run_architecture_analysis(self, chain_input: Dict[str, str]) -> List[Dict[str, Any]]:
        """Run architecture analysis chain."""
        try:
            result = await self.architecture_chain.arun(**chain_input)
            return self._parse_json_result(result, "architecture")
        except Exception as e:
            logger.error(f"Architecture analysis chain failed: {str(e)}")
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
        """Generate comprehensive overall summary with enhanced scoring."""
        try:
            # Prepare enhanced scoring input with all findings
            scoring_input = {
                "security_findings": json.dumps(review_results.get("security_issues", [])),
                "performance_findings": json.dumps(review_results.get("performance_issues", [])),
                "quality_findings": json.dumps(review_results.get("quality_issues", [])),
                "documentation_findings": json.dumps(review_results.get("documentation_issues", [])),
                "testing_findings": json.dumps(review_results.get("testing_issues", [])),
                "architecture_findings": json.dumps(review_results.get("architecture_issues", [])),
                "code_diff": "\n".join([f"File: {file['filename']}\n{file.get('content', '')[:1000]}"
                                      for file in review_results.get("files_reviewed", [])])
            }

            with get_openai_callback() as cb:
                # Use enhanced scoring chain for comprehensive analysis
                scoring_result = await self.enhanced_scoring_chain.arun(**scoring_input)

            # Parse enhanced scoring result
            try:
                scoring_data = json.loads(scoring_result.strip())

                # Extract scoring breakdown
                scoring = scoring_data.get("scoring", {})
                code_suggestions = scoring_data.get("code_suggestions", [])
                priority_fixes = scoring_data.get("priority_fixes", [])
                quick_wins = scoring_data.get("quick_wins", [])

                # Get overall score and letter grade
                overall_score = scoring.get("overall_score", 85)
                letter_grade = scoring.get("letter_grade", "B")

                # Create comprehensive summary
                summary = f"Code Review Complete\n\nGrade: {letter_grade}\n"
                if overall_score >= 90:
                    summary += "Excellent code quality with minimal issues."
                elif overall_score >= 80:
                    summary += "Good code quality with minor improvements suggested."
                elif overall_score >= 70:
                    summary += "Acceptable code quality with several areas for improvement."
                elif overall_score >= 60:
                    summary += "Code needs improvement to meet quality standards."
                else:
                    summary += "Code requires significant improvements before deployment."

                if priority_fixes:
                    summary += f"\n\nPriority fixes needed: {len(priority_fixes)}"
                if quick_wins:
                    summary += f"\nQuick wins available: {len(quick_wins)}"

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse enhanced scoring result: {e}")
                # Fallback to basic scoring
                overall_score = self._calculate_overall_score(review_results)
                letter_grade = self._score_to_letter_grade(overall_score * 10)  # Convert 0-10 to 0-100
                scoring = {
                    "overall_score": overall_score * 10,
                    "letter_grade": letter_grade,
                    "security_score": 85,
                    "performance_score": 85,
                    "quality_score": 85,
                    "documentation_score": 70,
                    "testing_score": 70,
                    "architecture_score": 80
                }
                code_suggestions = []
                priority_fixes = []
                quick_wins = []
                summary = f"Code Review Complete\n\nGrade: {letter_grade}\nBasic analysis completed with fallback scoring."

            # Update AI metrics
            review_results["ai_metrics"]["total_tokens"] += cb.total_tokens
            review_results["ai_metrics"]["total_cost"] += cb.total_cost
            review_results["ai_metrics"]["chains_executed"] += 1

            return {
                "summary": summary,
                "overall_score": overall_score / 10,  # Convert back to 0-10 scale for compatibility
                "letter_grade": letter_grade,
                "scoring_breakdown": scoring,
                "code_suggestions": code_suggestions,
                "priority_fixes": priority_fixes,
                "quick_wins": quick_wins,
                "confidence_score": 0.9
            }

        except Exception as e:
            logger.error(f"Failed to generate enhanced summary: {str(e)}")
            # Fallback to basic scoring
            fallback_score = self._calculate_overall_score(review_results)
            fallback_grade = self._score_to_letter_grade(fallback_score * 10)

            return {
                "summary": f"Code Review Complete\n\nGrade: {fallback_grade}\nReview completed with basic analysis.",
                "overall_score": fallback_score,
                "letter_grade": fallback_grade,
                "scoring_breakdown": {
                    "overall_score": fallback_score * 10,
                    "letter_grade": fallback_grade
                },
                "code_suggestions": [],
                "priority_fixes": [],
                "quick_wins": [],
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

    def _score_to_letter_grade(self, score: float) -> str:
        """Convert numerical score (0-100) to letter grade."""
        if score >= 90:
            return "A"
        elif score >= 80:
            return "B"
        elif score >= 70:
            return "C"
        elif score >= 60:
            return "D"
        else:
            return "F"

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