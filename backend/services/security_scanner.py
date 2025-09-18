"""Security vulnerability scanner for code review."""

import re
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass

from config.logging import get_logger, security_logger
from models.review import ReviewIssue, IssueCategory, SeverityLevel
from utils.helpers import get_file_language

logger = get_logger(__name__)


@dataclass
class SecurityRule:
    """Security rule definition."""
    id: str
    name: str
    description: str
    severity: SeverityLevel
    pattern: str
    languages: List[str]
    cwe_id: Optional[str] = None
    owasp_category: Optional[str] = None
    confidence: float = 0.8  # 0.0 - 1.0


class SecurityScanner:
    """Static security analysis scanner."""

    def __init__(self):
        self.rules = self._load_security_rules()
        self.secret_patterns = self._load_secret_patterns()

    def _load_security_rules(self) -> List[SecurityRule]:
        """Load security scanning rules."""
        return [
            # SQL Injection
            SecurityRule(
                id="sql_injection_1",
                name="SQL Injection - String Concatenation",
                description="SQL query constructed using string concatenation with user input",
                severity=SeverityLevel.HIGH,
                pattern=r'(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER).*(\+|\|\|).*[\'"]',
                languages=["python", "javascript", "typescript", "java", "csharp", "php"],
                cwe_id="CWE-89",
                owasp_category="A03:2021 - Injection"
            ),
            SecurityRule(
                id="sql_injection_2",
                name="SQL Injection - Format String",
                description="SQL query using string formatting with potential user input",
                severity=SeverityLevel.HIGH,
                pattern=r'(SELECT|INSERT|UPDATE|DELETE).*(%s|%d|\{\}|\{[^}]+\})',
                languages=["python", "java", "csharp"],
                cwe_id="CWE-89",
                owasp_category="A03:2021 - Injection"
            ),

            # XSS Vulnerabilities
            SecurityRule(
                id="xss_dom_1",
                name="DOM-based XSS",
                description="Direct DOM manipulation with unsanitized user input",
                severity=SeverityLevel.HIGH,
                pattern=r'innerHTML\s*=\s*.*[\+\$]',
                languages=["javascript", "typescript"],
                cwe_id="CWE-79",
                owasp_category="A03:2021 - Injection"
            ),
            SecurityRule(
                id="xss_dom_2",
                name="DOM-based XSS - document.write",
                description="Use of document.write with dynamic content",
                severity=SeverityLevel.HIGH,
                pattern=r'document\.write\s*\([^)]*[\+\$]',
                languages=["javascript", "typescript"],
                cwe_id="CWE-79",
                owasp_category="A03:2021 - Injection"
            ),

            # Command Injection
            SecurityRule(
                id="command_injection_1",
                name="Command Injection - exec/eval",
                description="Dangerous use of exec, eval, or system commands",
                severity=SeverityLevel.CRITICAL,
                pattern=r'(exec|eval|system|shell_exec|passthru)\s*\([^)]*[\+\$]',
                languages=["python", "javascript", "typescript", "php"],
                cwe_id="CWE-78",
                owasp_category="A03:2021 - Injection"
            ),

            # Path Traversal
            SecurityRule(
                id="path_traversal_1",
                name="Path Traversal",
                description="Potential path traversal vulnerability",
                severity=SeverityLevel.MEDIUM,
                pattern=r'\.\./|\.\.\\',
                languages=["all"],
                cwe_id="CWE-22",
                owasp_category="A01:2021 - Broken Access Control"
            ),

            # Hardcoded Secrets
            SecurityRule(
                id="hardcoded_secret_1",
                name="Hardcoded Password",
                description="Potential hardcoded password in source code",
                severity=SeverityLevel.HIGH,
                pattern=r'(password|pwd|secret|key|token)\s*=\s*[\'"][^\'"]{8,}[\'"]',
                languages=["all"],
                cwe_id="CWE-798",
                owasp_category="A07:2021 - Identification and Authentication Failures"
            ),

            # Insecure Randomness
            SecurityRule(
                id="weak_random_1",
                name="Weak Random Number Generation",
                description="Use of predictable random number generator",
                severity=SeverityLevel.MEDIUM,
                pattern=r'(Math\.random|random\.randint|rand\(\))',
                languages=["javascript", "typescript", "python", "java"],
                cwe_id="CWE-338",
                owasp_category="A02:2021 - Cryptographic Failures"
            ),

            # Weak Cryptography
            SecurityRule(
                id="weak_crypto_1",
                name="Weak Cryptographic Algorithm",
                description="Use of weak or deprecated cryptographic algorithms",
                severity=SeverityLevel.MEDIUM,
                pattern=r'(MD5|SHA1|DES|RC4|ECB)',
                languages=["all"],
                cwe_id="CWE-327",
                owasp_category="A02:2021 - Cryptographic Failures"
            ),

            # Insecure HTTP
            SecurityRule(
                id="insecure_http_1",
                name="Insecure HTTP Usage",
                description="Use of insecure HTTP instead of HTTPS",
                severity=SeverityLevel.LOW,
                pattern=r'http://[^/\s]+',
                languages=["all"],
                cwe_id="CWE-319",
                owasp_category="A02:2021 - Cryptographic Failures"
            ),

            # Debug Information
            SecurityRule(
                id="debug_info_1",
                name="Debug Information Disclosure",
                description="Debug or sensitive information exposed in logs",
                severity=SeverityLevel.LOW,
                pattern=r'(console\.log|print|echo|printf).*(?:password|secret|key|token)',
                languages=["all"],
                cwe_id="CWE-532",
                owasp_category="A09:2021 - Security Logging and Monitoring Failures",
                confidence=0.6
            ),

            # Unsafe Reflection
            SecurityRule(
                id="unsafe_reflection_1",
                name="Unsafe Reflection",
                description="Dangerous use of reflection with user input",
                severity=SeverityLevel.HIGH,
                pattern=r'(getattr|setattr|hasattr|eval|exec).*input',
                languages=["python"],
                cwe_id="CWE-470",
                owasp_category="A08:2021 - Software and Data Integrity Failures"
            ),

            # LDAP Injection
            SecurityRule(
                id="ldap_injection_1",
                name="LDAP Injection",
                description="Potential LDAP injection vulnerability",
                severity=SeverityLevel.MEDIUM,
                pattern=r'(LdapContext|DirContext).*[\+\$]',
                languages=["java", "csharp"],
                cwe_id="CWE-90",
                owasp_category="A03:2021 - Injection"
            ),

            # XML/XXE
            SecurityRule(
                id="xxe_1",
                name="XML External Entity (XXE)",
                description="Potential XXE vulnerability in XML parsing",
                severity=SeverityLevel.MEDIUM,
                pattern=r'DocumentBuilderFactory.*newInstance\(\)',
                languages=["java"],
                cwe_id="CWE-611",
                owasp_category="A05:2021 - Security Misconfiguration"
            ),

            # Unsafe Deserialization
            SecurityRule(
                id="unsafe_deserialization_1",
                name="Unsafe Deserialization",
                description="Potential unsafe deserialization",
                severity=SeverityLevel.HIGH,
                pattern=r'(pickle\.loads|yaml\.load|unserialize)(?!\s*\(.*safe)',
                languages=["python", "php"],
                cwe_id="CWE-502",
                owasp_category="A08:2021 - Software and Data Integrity Failures"
            ),

            # CSRF
            SecurityRule(
                id="csrf_1",
                name="Missing CSRF Protection",
                description="Form without CSRF protection",
                severity=SeverityLevel.MEDIUM,
                pattern=r'<form[^>]*method\s*=\s*[\'"]post[\'"][^>]*>(?!.*csrf)',
                languages=["html"],
                cwe_id="CWE-352",
                owasp_category="A01:2021 - Broken Access Control",
                confidence=0.6
            ),
        ]

    def _load_secret_patterns(self) -> Dict[str, str]:
        """Load patterns for detecting hardcoded secrets."""
        return {
            "aws_access_key": r"AKIA[0-9A-Z]{16}",
            "aws_secret_key": r"[A-Za-z0-9/+=]{40}",
            "github_token": r"ghp_[A-Za-z0-9]{36}",
            "github_oauth": r"gho_[A-Za-z0-9]{36}",
            "github_app": r"(ghu|ghs)_[A-Za-z0-9]{36}",
            "slack_token": r"xox[baprs]-[A-Za-z0-9-]+",
            "slack_webhook": r"https://hooks\.slack\.com/services/T[A-Z0-9]+/B[A-Z0-9]+/[A-Za-z0-9]+",
            "discord_webhook": r"https://discord(app)?\.com/api/webhooks/[0-9]+/[A-Za-z0-9_-]+",
            "openai_api_key": r"sk-[A-Za-z0-9]{48}",
            "anthropic_api_key": r"sk-ant-[A-Za-z0-9-_]{95}",
            "jwt_token": r"eyJ[A-Za-z0-9_-]*\.eyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*",
            "private_key": r"-----BEGIN (RSA |EC |DSA )?PRIVATE KEY-----",
            "google_api_key": r"AIza[0-9A-Za-z_-]{35}",
            "firebase_token": r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
            "mailgun_api_key": r"key-[A-Za-z0-9]{32}",
            "stripe_key": r"(sk|pk)_(test|live)_[A-Za-z0-9]{24,}",
        }

    async def scan_diff(self, diff_content: str, filename: str = "") -> List[ReviewIssue]:
        """
        Scan git diff content for security vulnerabilities.

        Args:
            diff_content: Git diff patch content
            filename: Name of the file being scanned

        Returns:
            List of security issues found
        """
        issues = []
        language = get_file_language(filename) if filename else "unknown"

        logger.info(f"Scanning {filename} for security issues", language=language)

        # Split diff into lines for analysis
        lines = diff_content.split('\n')
        current_line_number = 0

        for i, line in enumerate(lines):
            # Track line numbers in the new file
            if line.startswith('@@'):
                # Parse hunk header to get line number
                match = re.search(r'@@ -\d+,?\d* \+(\d+),?\d* @@', line)
                if match:
                    current_line_number = int(match.group(1)) - 1
                continue
            elif line.startswith('+'):
                # This is an added line
                current_line_number += 1
                line_content = line[1:]  # Remove the '+' prefix

                # Scan this line for vulnerabilities
                line_issues = await self._scan_line(
                    line_content, current_line_number, filename, language
                )
                issues.extend(line_issues)

            elif not line.startswith('-'):
                # This is a context line (unchanged)
                current_line_number += 1

        # Also scan for hardcoded secrets in the entire diff
        secret_issues = await self._scan_secrets(diff_content, filename)
        issues.extend(secret_issues)

        # Remove duplicates based on line number and message
        issues = self._deduplicate_issues(issues)

        logger.info(
            f"Security scan completed for {filename}",
            issues_found=len(issues),
            critical=len([i for i in issues if i.severity == SeverityLevel.CRITICAL]),
            high=len([i for i in issues if i.severity == SeverityLevel.HIGH])
        )

        security_logger.security_scan_result(
            filename or "unknown",
            0,  # No PR number available here
            len(issues)
        )

        return issues

    async def _scan_line(
        self,
        line_content: str,
        line_number: int,
        filename: str,
        language: str
    ) -> List[ReviewIssue]:
        """Scan a single line for security issues."""
        issues = []

        for rule in self.rules:
            # Skip if rule doesn't apply to this language
            if rule.languages != ["all"] and language not in rule.languages:
                continue

            # Check if pattern matches
            try:
                match = re.search(rule.pattern, line_content, re.IGNORECASE)
                if match:
                    issue = ReviewIssue(
                        category=IssueCategory.SECURITY,
                        severity=rule.severity,
                        title=rule.name,
                        message=f"{rule.description}\n\nDetected pattern: {match.group(0)}",
                        file_path=filename,
                        line_number=line_number,
                        code_snippet=line_content.strip(),
                        suggestion=self._get_suggestion_for_rule(rule, match.group(0)),
                        rule_id=rule.id
                    )
                    issues.append(issue)

            except re.error as e:
                logger.warning(f"Invalid regex pattern in rule {rule.id}: {e}")

        return issues

    async def _scan_secrets(self, content: str, filename: str) -> List[ReviewIssue]:
        """Scan for hardcoded secrets and sensitive information."""
        issues = []

        for secret_type, pattern in self.secret_patterns.items():
            try:
                matches = re.finditer(pattern, content, re.MULTILINE)
                for match in matches:
                    # Calculate line number
                    line_number = content[:match.start()].count('\n') + 1

                    # Get the line content
                    lines = content.split('\n')
                    if 0 <= line_number - 1 < len(lines):
                        line_content = lines[line_number - 1]
                    else:
                        line_content = match.group(0)

                    # Create issue
                    issue = ReviewIssue(
                        category=IssueCategory.SECURITY,
                        severity=SeverityLevel.HIGH,
                        title=f"Hardcoded {secret_type.replace('_', ' ').title()}",
                        message=f"Potential hardcoded {secret_type.replace('_', ' ')} detected in source code. "
                               f"This could lead to unauthorized access if the code is public.",
                        file_path=filename,
                        line_number=line_number,
                        code_snippet=self._mask_secret(line_content, match.group(0)),
                        suggestion="Move secrets to environment variables or a secure secret management system.",
                        rule_id=f"secret_{secret_type}"
                    )
                    issues.append(issue)

            except re.error as e:
                logger.warning(f"Invalid regex pattern for {secret_type}: {e}")

        return issues

    def _get_suggestion_for_rule(self, rule: SecurityRule, matched_text: str) -> str:
        """Get specific suggestion for a security rule."""
        suggestions = {
            "sql_injection_1": "Use parameterized queries or prepared statements instead of string concatenation.",
            "sql_injection_2": "Use parameterized queries with proper input validation and sanitization.",
            "xss_dom_1": "Sanitize user input before inserting into DOM. Use textContent instead of innerHTML for plain text.",
            "xss_dom_2": "Avoid document.write. Use safer DOM manipulation methods and sanitize input.",
            "command_injection_1": "Avoid executing user input. Use safe alternatives or strict input validation.",
            "path_traversal_1": "Validate and sanitize file paths. Use path normalization and whitelist allowed directories.",
            "hardcoded_secret_1": "Move secrets to environment variables or a secure secret management system.",
            "weak_random_1": "Use cryptographically secure random number generators (e.g., crypto.getRandomValues()).",
            "weak_crypto_1": "Use modern, secure cryptographic algorithms like SHA-256, AES-256, or bcrypt.",
            "insecure_http_1": "Use HTTPS for all network communications to ensure data encryption.",
            "debug_info_1": "Remove debug statements or ensure sensitive information is not logged.",
            "unsafe_reflection_1": "Avoid reflection with user input. Use explicit method calls or strict input validation.",
            "ldap_injection_1": "Use parameterized LDAP queries and validate user input.",
            "xxe_1": "Disable external entity processing in XML parsers.",
            "unsafe_deserialization_1": "Avoid deserializing untrusted data. Use safe serialization formats like JSON.",
            "csrf_1": "Add CSRF tokens to forms and validate them on the server side."
        }

        return suggestions.get(rule.id, "Review this code for security implications and apply appropriate security measures.")

    def _mask_secret(self, line_content: str, secret: str) -> str:
        """Mask a secret in the line content for safe display."""
        if len(secret) <= 8:
            masked = "*" * len(secret)
        else:
            # Show first 4 and last 4 characters
            masked = secret[:4] + "*" * (len(secret) - 8) + secret[-4:]

        return line_content.replace(secret, masked)

    def _deduplicate_issues(self, issues: List[ReviewIssue]) -> List[ReviewIssue]:
        """Remove duplicate issues based on line number and rule ID."""
        seen = set()
        deduplicated = []

        for issue in issues:
            key = (issue.file_path, issue.line_number, issue.rule_id)
            if key not in seen:
                seen.add(key)
                deduplicated.append(issue)

        return deduplicated

    async def scan_repository_files(self, files: Dict[str, str]) -> Dict[str, List[ReviewIssue]]:
        """
        Scan multiple files for security issues.

        Args:
            files: Dictionary mapping filename to content

        Returns:
            Dictionary mapping filename to list of issues
        """
        results = {}

        for filename, content in files.items():
            try:
                # For full file content, treat as if entire file is added
                diff_content = '\n'.join(f'+{line}' for line in content.split('\n'))
                issues = await self.scan_diff(diff_content, filename)
                results[filename] = issues
            except Exception as e:
                logger.error(f"Failed to scan file {filename}: {str(e)}")
                results[filename] = []

        return results

    def get_security_metrics(self, issues: List[ReviewIssue]) -> Dict[str, Any]:
        """Calculate security metrics from issues."""
        if not issues:
            return {
                "total_issues": 0,
                "critical_count": 0,
                "high_count": 0,
                "medium_count": 0,
                "low_count": 0,
                "owasp_categories": {},
                "cwe_categories": {},
                "risk_score": 0.0
            }

        severity_counts = {
            "critical": len([i for i in issues if i.severity == SeverityLevel.CRITICAL]),
            "high": len([i for i in issues if i.severity == SeverityLevel.HIGH]),
            "medium": len([i for i in issues if i.severity == SeverityLevel.MEDIUM]),
            "low": len([i for i in issues if i.severity == SeverityLevel.LOW])
        }

        # Calculate risk score (0-100)
        risk_score = (
                severity_counts["critical"] * 25 +
                severity_counts["high"] * 15 +
                severity_counts["medium"] * 7 +
                severity_counts["low"] * 2
        )
        risk_score = min(100, risk_score)

        return {
            "total_issues": len(issues),
            "critical_count": severity_counts["critical"],
            "high_count": severity_counts["high"],
            "medium_count": severity_counts["medium"],
            "low_count": severity_counts["low"],
            "risk_score": risk_score
        }