"""Helper utility functions for the Git Review Assistant backend."""

import asyncio
import re
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timezone
from pathlib import Path

from config.logging import get_logger

logger = get_logger(__name__)


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename for safe filesystem operations.

    Args:
        filename: The filename to sanitize

    Returns:
        str: Sanitized filename
    """
    # Remove or replace dangerous characters
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # Remove leading/trailing dots and spaces
    sanitized = sanitized.strip('. ')
    # Ensure it's not empty
    return sanitized or 'unnamed_file'


def get_file_language(filename: str) -> str:
    """
    Determine programming language from filename extension.

    Args:
        filename: The filename to analyze

    Returns:
        str: Detected language or 'unknown'
    """
    extension_map = {
        '.py': 'python',
        '.js': 'javascript',
        '.ts': 'typescript',
        '.jsx': 'javascript',
        '.tsx': 'typescript',
        '.java': 'java',
        '.c': 'c',
        '.cpp': 'cpp',
        '.cc': 'cpp',
        '.cxx': 'cpp',
        '.h': 'c',
        '.hpp': 'cpp',
        '.cs': 'csharp',
        '.php': 'php',
        '.rb': 'ruby',
        '.go': 'go',
        '.rs': 'rust',
        '.swift': 'swift',
        '.kt': 'kotlin',
        '.scala': 'scala',
        '.sh': 'bash',
        '.bash': 'bash',
        '.zsh': 'bash',
        '.fish': 'bash',
        '.ps1': 'powershell',
        '.sql': 'sql',
        '.html': 'html',
        '.htm': 'html',
        '.css': 'css',
        '.scss': 'scss',
        '.sass': 'sass',
        '.less': 'less',
        '.vue': 'vue',
        '.json': 'json',
        '.xml': 'xml',
        '.yaml': 'yaml',
        '.yml': 'yaml',
        '.toml': 'toml',
        '.ini': 'ini',
        '.cfg': 'ini',
        '.conf': 'ini',
        '.md': 'markdown',
        '.markdown': 'markdown',
        '.rst': 'rst',
        '.txt': 'text',
        '.dockerfile': 'dockerfile',
        '.gitignore': 'gitignore',
        '.env': 'env',
        '.r': 'r',
        '.R': 'r',
        '.m': 'matlab',
        '.pl': 'perl',
        '.lua': 'lua',
        '.dart': 'dart',
        '.elm': 'elm',
        '.ex': 'elixir',
        '.exs': 'elixir',
        '.erl': 'erlang',
        '.hrl': 'erlang',
        '.fs': 'fsharp',
        '.fsx': 'fsharp',
        '.fsi': 'fsharp',
        '.ml': 'ocaml',
        '.mli': 'ocaml',
        '.clj': 'clojure',
        '.cljs': 'clojure',
        '.cljc': 'clojure',
        '.hs': 'haskell',
        '.lhs': 'haskell',
    }

    # Get extension
    ext = Path(filename).suffix.lower()
    return extension_map.get(ext, 'unknown')


def is_binary_file(filename: str) -> bool:
    """
    Check if a file is likely binary based on its extension.

    Args:
        filename: The filename to check

    Returns:
        bool: True if likely binary, False otherwise
    """
    binary_extensions = {
        '.exe', '.dll', '.so', '.dylib', '.lib', '.a',
        '.bin', '.dat', '.db', '.sqlite', '.sqlite3',
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.ico',
        '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
        '.zip', '.tar', '.gz', '.bz2', '.7z', '.rar',
        '.mp3', '.mp4', '.avi', '.mov', '.wmv', '.flv',
        '.ttf', '.otf', '.woff', '.woff2', '.eot',
        '.jar', '.war', '.class', '.pyc', '.pyo', '.pyd',
        '.node', '.wasm', '.o', '.obj',
    }

    ext = Path(filename).suffix.lower()
    return ext in binary_extensions


def extract_pr_info(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract relevant PR information from GitHub webhook payload.

    Args:
        payload: GitHub webhook payload

    Returns:
        dict: Extracted PR information
    """
    pr = payload.get('pull_request', {})
    repo = payload.get('repository', {})

    return {
        'pr_number': pr.get('number'),
        'pr_title': pr.get('title'),
        'pr_body': pr.get('body'),
        'pr_url': pr.get('html_url'),
        'head_sha': pr.get('head', {}).get('sha'),
        'base_sha': pr.get('base', {}).get('sha'),
        'head_ref': pr.get('head', {}).get('ref'),
        'base_ref': pr.get('base', {}).get('ref'),
        'repo_name': repo.get('name'),
        'repo_full_name': repo.get('full_name'),
        'repo_owner': repo.get('owner', {}).get('login'),
        'author': pr.get('user', {}).get('login'),
        'author_id': pr.get('user', {}).get('id'),
        'created_at': pr.get('created_at'),
        'updated_at': pr.get('updated_at'),
        'mergeable': pr.get('mergeable'),
        'merged': pr.get('merged'),
        'draft': pr.get('draft'),
        'state': pr.get('state'),
        'installation_id': payload.get('installation', {}).get('id'),
    }


def calculate_complexity_score(code: str) -> int:
    """
    Calculate a simple complexity score for code.

    Args:
        code: The code to analyze

    Returns:
        int: Complexity score (1-10, where 10 is most complex)
    """
    if not code:
        return 1

    lines = code.split('\n')
    non_empty_lines = [line for line in lines if line.strip()]

    # Base score on line count
    score = min(len(non_empty_lines) // 10, 5)

    # Add complexity for control structures
    complexity_keywords = [
        'if', 'else', 'elif', 'for', 'while', 'try', 'except', 'finally',
        'switch', 'case', 'catch', 'with', 'async', 'await'
    ]

    keyword_count = 0
    for line in non_empty_lines:
        line_lower = line.lower()
        for keyword in complexity_keywords:
            if f' {keyword} ' in line_lower or line_lower.startswith(f'{keyword} '):
                keyword_count += 1

    score += min(keyword_count // 5, 3)

    # Add complexity for nesting (rough estimate)
    max_indent = 0
    for line in lines:
        if line.strip():
            indent = len(line) - len(line.lstrip())
            max_indent = max(max_indent, indent // 4)  # Assuming 4-space indents

    score += min(max_indent, 2)

    return min(max(score, 1), 10)


def format_review_comment(comment_type: str, severity: str, message: str,
                         suggestion: str = None, line_number: int = None) -> str:
    """
    Format a review comment with proper markdown and emoji.

    Args:
        comment_type: Type of comment (security, performance, quality, etc.)
        severity: Severity level (critical, high, medium, low, info)
        message: Main comment message
        suggestion: Optional suggestion text
        line_number: Optional line number reference

    Returns:
        str: Formatted markdown comment
    """
    # Emoji mapping for different types and severities
    emoji_map = {
        'security': {
            'critical': '🚨',
            'high': '🔒',
            'medium': '⚠️',
            'low': '🔐',
            'info': 'ℹ️'
        },
        'performance': {
            'critical': '🐌',
            'high': '⚡',
            'medium': '📊',
            'low': '💡',
            'info': 'ℹ️'
        },
        'quality': {
            'critical': '💥',
            'high': '🧹',
            'medium': '📝',
            'low': '✨',
            'info': 'ℹ️'
        },
        'style': {
            'critical': '🎨',
            'high': '🎨',
            'medium': '🎨',
            'low': '🎨',
            'info': '🎨'
        }
    }

    emoji = emoji_map.get(comment_type, {}).get(severity, '📋')
    severity_text = severity.upper() if severity != 'info' else 'INFO'

    comment = f"{emoji} **{comment_type.title()} Issue** ({severity_text})\n\n"

    if line_number:
        comment += f"**Line {line_number}:** "

    comment += message

    if suggestion:
        comment += f"\n\n**Suggestion:** {suggestion}"

    return comment


def truncate_text(text: str, max_length: int = 1000, suffix: str = "...") -> str:
    """
    Truncate text to a maximum length.

    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add when truncating

    Returns:
        str: Truncated text
    """
    if len(text) <= max_length:
        return text

    return text[:max_length - len(suffix)] + suffix


def normalize_line_endings(text: str) -> str:
    """
    Normalize line endings to Unix style (LF).

    Args:
        text: Text to normalize

    Returns:
        str: Text with normalized line endings
    """
    return text.replace('\r\n', '\n').replace('\r', '\n')


async def retry_async(func, max_retries: int = 3, delay: float = 1.0,
                     backoff: float = 2.0, exceptions: tuple = (Exception,)):
    """
    Retry an async function with exponential backoff.

    Args:
        func: Async function to retry
        max_retries: Maximum number of retries
        delay: Initial delay between retries
        backoff: Backoff multiplier
        exceptions: Exceptions to catch and retry

    Returns:
        Any: Result of the function

    Raises:
        Exception: Last exception if all retries fail
    """
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            return await func()
        except exceptions as e:
            last_exception = e
            if attempt < max_retries:
                wait_time = delay * (backoff ** attempt)
                logger.warning(
                    f"Attempt {attempt + 1} failed, retrying in {wait_time}s",
                    error=str(e)
                )
                await asyncio.sleep(wait_time)
            else:
                logger.error(f"All {max_retries + 1} attempts failed", error=str(e))

    raise last_exception


def get_utc_timestamp() -> datetime:
    """Get current UTC timestamp."""
    return datetime.now(timezone.utc)


def parse_git_diff(diff_text: str) -> List[Dict[str, Any]]:
    """
    Parse git diff text into structured data.

    Args:
        diff_text: Raw git diff text

    Returns:
        list: List of diff chunks with line information
    """
    chunks = []
    current_file = None
    current_chunk = None

    lines = diff_text.split('\n')

    for line in lines:
        if line.startswith('diff --git'):
            # New file
            if current_chunk:
                chunks.append(current_chunk)
            current_file = line.split()[-1][2:]  # Remove 'b/' prefix
            current_chunk = {
                'file': current_file,
                'changes': []
            }
        elif line.startswith('@@'):
            # New hunk
            if current_chunk:
                # Parse hunk header
                match = re.search(r'@@ -(\d+),?\d* \+(\d+),?\d* @@', line)
                if match:
                    current_chunk['old_start'] = int(match.group(1))
                    current_chunk['new_start'] = int(match.group(2))
        elif current_chunk and (line.startswith('+') or line.startswith('-') or line.startswith(' ')):
            # Code line
            change_type = 'addition' if line.startswith('+') else 'deletion' if line.startswith('-') else 'context'
            current_chunk['changes'].append({
                'type': change_type,
                'content': line[1:],  # Remove +/- prefix
                'line_number': len([c for c in current_chunk['changes'] if c['type'] in ['addition', 'context']]) + current_chunk.get('new_start', 1)
            })

    if current_chunk:
        chunks.append(current_chunk)

    return chunks