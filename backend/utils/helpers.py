"""Small helpers."""

from datetime import datetime, timezone
from pathlib import Path

_EXTENSIONS = {
    '.py': 'python', '.js': 'javascript', '.mjs': 'javascript', '.cjs': 'javascript', '.ts': 'typescript',
    '.jsx': 'javascript', '.tsx': 'typescript', '.java': 'java', '.kt': 'kotlin', '.scala': 'scala',
    '.c': 'c', '.h': 'c', '.cpp': 'cpp', '.cc': 'cpp', '.cxx': 'cpp', '.hpp': 'cpp', '.cs': 'csharp',
    '.go': 'go', '.rs': 'rust', '.rb': 'ruby', '.php': 'php', '.swift': 'swift', '.m': 'objective-c',
    '.sh': 'bash', '.bash': 'bash', '.zsh': 'bash', '.ps1': 'powershell', '.sql': 'sql', '.r': 'r', '.R': 'r',
    '.lua': 'lua', '.pl': 'perl', '.dart': 'dart', '.ex': 'elixir', '.exs': 'elixir', '.erl': 'erlang',
    '.hs': 'haskell', '.clj': 'clojure', '.ml': 'ocaml', '.fs': 'fsharp', '.vue': 'vue', '.svelte': 'svelte',
    '.html': 'html', '.htm': 'html', '.css': 'css', '.scss': 'scss', '.sass': 'sass', '.less': 'less',
    '.json': 'json', '.yaml': 'yaml', '.yml': 'yaml', '.toml': 'toml', '.ini': 'ini', '.cfg': 'ini', '.xml': 'xml',
    '.tf': 'terraform', '.hcl': 'hcl', '.gradle': 'groovy', '.groovy': 'groovy',
    '.md': 'markdown', '.markdown': 'markdown', '.rst': 'rst', '.txt': 'text',
}
_SPECIAL = {'dockerfile': 'dockerfile', 'makefile': 'makefile', 'jenkinsfile': 'groovy', 'vagrantfile': 'ruby'}


def get_file_language(filename: str) -> str:
    name = Path(filename or "").name
    if name.startswith(".env"):
        return "dotenv"
    if name.lower() in _SPECIAL:
        return _SPECIAL[name.lower()]
    return _EXTENSIONS.get(Path(name).suffix.lower(), 'unknown')


def get_utc_timestamp() -> datetime:
    return datetime.now(timezone.utc)
