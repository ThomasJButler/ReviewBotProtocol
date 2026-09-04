"""Secret redaction and exclusion of secret-bearing files.

Runs on every patch before it reaches the model, the posted comment, the
log line or the database, and on every string the model produces. A miss
here is a leak, so the patterns err towards redacting too much. Redaction
never changes the number of lines, because line numbers computed from the
redacted text are what the review comments attach to."""

import fnmatch
import posixpath
import re
from typing import Dict, List, Tuple

# Single-line patterns: (kind, compiled pattern, group index to replace; 0 = whole match).
# None of these may match a newline.
_PATTERNS: List[Tuple[str, re.Pattern, int]] = [
    ("openai-key", re.compile(r"\bsk-(?:proj-|svcacct-|ant-)?[A-Za-z0-9_-]{32,}"), 0),
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}"), 0),
    ("github-token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{22,}"), 0),
    ("npm-token", re.compile(r"\bnpm_[A-Za-z0-9]{36}\b"), 0),
    ("aws-access-key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"), 0),
    ("aws-secret-key", re.compile(r"(?i)aws[_-]?secret[_-]?access[_-]?key\s*[:=]\s*['\"]?([A-Za-z0-9/+=]{40})"), 1),
    ("azure-key", re.compile(r"(?i)\bAccountKey=([A-Za-z0-9+/=]{40,})"), 1),
    ("slack-token", re.compile(r"\bxox[abprse]-[A-Za-z0-9-]{10,}"), 0),
    ("slack-token", re.compile(r"\bxapp-\d-[A-Za-z0-9-]{10,}"), 0),
    ("slack-token", re.compile(r"\bxoxe\.[A-Za-z0-9-]{10,}"), 0),
    ("slack-webhook", re.compile(r"https://hooks\.slack\.com/services/[A-Za-z0-9/]+"), 0),
    ("discord-webhook", re.compile(r"https://discord(?:app)?\.com/api/webhooks/[0-9]+/[A-Za-z0-9_-]+"), 0),
    ("google-api-key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"), 0),
    ("stripe-key", re.compile(r"\b[sr]k_(?:live|test)_[A-Za-z0-9]{20,}"), 0),
    ("langsmith-key", re.compile(r"\b(?:lsv2_[a-z]{2}_[a-f0-9]{32}|ls__[A-Za-z0-9]{20,})"), 0),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"), 0),
    ("url-password", re.compile(r"(?i)\b[a-z][a-z0-9+.-]{0,64}://[^\s:/@]{1,256}:([^\s/]{3,512})@"), 1),
    ("auth-header", re.compile(r"(?i)\bauthorization\b['\"\]]*\s*[:=]\s*['\"]?(?:bearer|basic|token)\s+([A-Za-z0-9._~+/=-]{8,})"), 1),
    ("assigned-secret", re.compile(
        r"(?i)(?:\b|_)(?:password|passwd|pwd|secret|secret[_-]?key|token|api[_-]?key|access[_-]?key|auth[_-]?token|client[_-]?secret|private[_-]?key)\b['\"\]]*"
        r"\s*[:=]\s*['\"]([^'\"\n]{8,})['\"]"), 1),
    # Unquoted assignments (YAML, dotenv, Dockerfile, shell). The value must look like
    # a credential rather than an expression: no brackets or spaces, and at least one digit.
    ("assigned-secret", re.compile(
        r"(?i)(?:\b|_)(?:password|passwd|pwd|secret|secret[_-]?key|token|api[_-]?key|access[_-]?key|auth[_-]?token|client[_-]?secret|private[_-]?key)\b['\"\]]*"
        r"\s*[:=]\s*(?=[A-Za-z0-9_./+=-]{0,256}\d)([A-Za-z0-9_./+=-]{12,512})(?=\s|$|[,;])"), 1),
]

_KEY_BEGIN = re.compile(r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----")
_KEY_END = re.compile(r"-----END (?:[A-Z ]+ )?PRIVATE KEY-----")
_KEY_BODY = re.compile(r"^[A-Za-z0-9+/=]{20,}$")
_MAX_KEY_BODY_LINES = 200

_PLACEHOLDER_PREFIXES = ("your-", "your_", "changeme", "placeholder", "xxxx", "[redacted:", "${", "{{", "<", "example")
_PLACEHOLDER_EXACT = {"example", "test", "secret", "password", "changeme", "none", "null"}

EXCLUDED_BASENAMES = {
    "credentials",
    ".env", ".npmrc", ".pypirc", ".netrc", "kubeconfig", "credentials.json", ".htpasswd", ".git-credentials",
    "secrets.yaml", "secrets.yml", "secrets.json", "secret.yaml", "secret.yml", "credentials.yaml", "credentials.yml",
    "vault.yaml", "vault.yml", ".dockercfg",
}
EXCLUDED_GLOBS = [
    ".env.*", "*.pem", "*.key", "*.p12", "*.pfx", "*.jks", "*.keystore", "*.keytab", "*.tfvars", "*.tfstate", "*.tfstate.*",
    "id_rsa*", "id_ed25519*", "id_ecdsa*", "id_dsa*", "*.kubeconfig", "service-account*.json", "*.ppk", "*.asc", "*.gpg",
]
_TEMPLATE_MARKERS = (".example", ".sample", ".template", ".dist")


def _looks_like_placeholder(value: str) -> bool:
    v = value.strip().lower()
    return v in _PLACEHOLDER_EXACT or v.startswith(_PLACEHOLDER_PREFIXES)


def _diff_prefix(line: str) -> Tuple[str, str]:
    """Split a diff line into its marker ('+', '-', ' ' or nothing) and the rest."""
    if line and line[0] in "+- ":
        return line[0], line[1:]
    return "", line


def _redact_private_keys(text: str, counts: Dict[str, int]) -> str:
    """Replace private key blocks line by line so the line count is unchanged.
    A block starts at a BEGIN marker and ends at the END marker, at a line that
    is not base64 key material, or after a bounded number of lines."""
    out: List[str] = []
    in_block = False
    body = 0
    for line in text.split("\n"):
        marker, rest = _diff_prefix(line)
        if not in_block:
            m = _KEY_BEGIN.search(rest)
            if m:
                counts["private-key"] = counts.get("private-key", 0) + 1
                in_block, body = True, 0
                out.append(marker + rest[:m.start()] + "[REDACTED:private-key]")
                continue
            out.append(line)
            continue
        if _KEY_END.search(rest):
            in_block = False
            out.append(marker + "[REDACTED:private-key]")
        elif body < _MAX_KEY_BODY_LINES and _KEY_BODY.match(rest.strip()):
            body += 1
            out.append(marker + "[REDACTED:private-key]")
        else:
            in_block = False
            out.append(line)
    return "\n".join(out)


def redact(text: str) -> Tuple[str, Dict[str, int]]:
    """Return (redacted_text, {kind: count}). Never changes the number of lines."""
    if not text:
        return text, {}
    counts: Dict[str, int] = {}
    text = _redact_private_keys(text, counts)
    for kind, pattern, group in _PATTERNS:
        def _sub(m: re.Match, kind=kind, group=group) -> str:
            secret = m.group(group)
            if group != 0 and _looks_like_placeholder(secret):
                return m.group(0)
            counts[kind] = counts.get(kind, 0) + 1
            marker = f"[REDACTED:{kind}]"
            if group == 0:
                return marker
            start, end = m.start(group) - m.start(0), m.end(group) - m.start(0)
            whole = m.group(0)
            return whole[:start] + marker + whole[end:]
        text = pattern.sub(_sub, text)
    return text, counts


def redact_text(text: str) -> str:
    """Convenience for model-derived strings: the redacted text only."""
    return redact(text)[0]


def is_excluded_path(path: str) -> bool:
    """True for files that are secret-bearing by nature and must not be reviewed.
    Templates such as .env.example are reviewed: people do commit real values into them."""
    base = posixpath.basename(path or "").lower()
    if base.startswith(".env") and any(m in base for m in _TEMPLATE_MARKERS):
        return False
    if base in EXCLUDED_BASENAMES:
        return True
    return any(fnmatch.fnmatch(base, g) for g in EXCLUDED_GLOBS)
