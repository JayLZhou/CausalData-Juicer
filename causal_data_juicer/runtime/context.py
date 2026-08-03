"""What repository content is allowed into an LLM prompt, decided in one place.

The old behavior — "inline every small text file" — walked straight into
`.env` files and symlinks to host files. This module inverts the default:

- **allowlist** of source/doc extensions; anything else never enters;
- **denylist** of secret-bearing names/patterns that wins over the allowlist;
- symlinks are never followed;
- surviving content is scanned for high-entropy strings and known token
  shapes (AWS keys, PEM blocks, bearer tokens, key=value credentials) and
  redacted in place;
- `context_manifest()` reports exactly what would be sent, for display
  before the first LLM call and for `cdj run --context-manifest`.
"""
from __future__ import annotations

import math
import re
from pathlib import Path

ALLOWED_EXTENSIONS = {
    ".py", ".md", ".rst", ".txt", ".toml", ".cfg", ".ini",
    ".json", ".yaml", ".yml", ".sql", ".csv", ".html", ".css", ".js", ".ts",
}

EXCLUDE_DIRS = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache",
                ".tox", ".mypy_cache", ".ruff_cache", ".aws", ".ssh", ".gnupg",
                ".docker", ".kube", ".config"}

DENY_NAME_PATTERNS = [
    r"^\.env(\..*)?$", r"^\.npmrc$", r"^\.pypirc$", r"^\.netrc$",
    r"credential", r"^id_rsa", r"^id_ed25519", r"^id_ecdsa", r"^id_dsa",
    r"\.pem$", r"\.key$", r"\.p12$", r"\.pfx$", r"\.crt$", r"\.cer$",
    r"\.der$", r"\.jks$", r"^\.htpasswd$", r"secret", r"^token", r"\.tfstate",
]
_DENY = [re.compile(p, re.IGNORECASE) for p in DENY_NAME_PATTERNS]

# Token shapes worth refusing to transmit even from allowed files.
SECRET_PATTERNS = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),                      # AWS access key id
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),            # GitHub tokens
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),                 # OpenAI-style keys
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),          # Slack tokens
    re.compile(r"\beyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),  # JWT
    re.compile(r"(?i)\b(api[_-]?key|secret|passwd|password|token|auth)\b\s*[:=]\s*['\"]?[^\s'\"]{8,}"),
]

REDACTED = "[REDACTED]"


def _shannon_entropy(s: str) -> float:
    if not s:
        return 0.0
    freq: dict[str, int] = {}
    for ch in s:
        freq[ch] = freq.get(ch, 0) + 1
    n = len(s)
    return -sum(c / n * math.log2(c / n) for c in freq.values())


_CANDIDATE_TOKEN = re.compile(r"\b[A-Za-z0-9+/_=-]{24,}\b")


def redact_secrets(text: str) -> str:
    for pat in SECRET_PATTERNS:
        text = pat.sub(REDACTED, text)

    def _entropy_sub(m: re.Match) -> str:
        tok = m.group(0)
        return REDACTED if _shannon_entropy(tok) > 4.2 else tok

    return _CANDIDATE_TOKEN.sub(_entropy_sub, text)


def _name_denied(name: str) -> bool:
    return any(p.search(name) for p in _DENY)


def iter_context_files(ws: Path, max_file: int = 4000):
    """Yield (path, redacted_text) for files eligible to enter a prompt."""
    ws = Path(ws)
    for p in sorted(ws.rglob("*")):
        rel_parts = p.relative_to(ws).parts
        if any(seg in EXCLUDE_DIRS for seg in rel_parts):
            continue
        if p.is_symlink():          # never follow, file or directory
            continue
        if not p.is_file():
            continue
        if p.suffix.lower() not in ALLOWED_EXTENSIONS:
            continue
        if any(_name_denied(part) for part in rel_parts):
            continue
        try:
            txt = p.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        if len(txt) > max_file:
            continue
        yield p, redact_secrets(txt)


def build_context(ws: Path, max_file: int = 4000, max_total: int = 9000) -> str:
    parts, total = [], 0
    for p, txt in iter_context_files(ws, max_file=max_file):
        chunk = f"\n--- {p.relative_to(ws)} ---\n{txt}"
        if total + len(chunk) > max_total:
            break
        parts.append(chunk)
        total += len(chunk)
    return "".join(parts)


def context_manifest(ws: Path, max_file: int = 4000, max_total: int = 9000) -> list[str]:
    """The exact relative paths whose content build_context would send."""
    names, total = [], 0
    for p, txt in iter_context_files(ws, max_file=max_file):
        chunk = f"\n--- {p.relative_to(ws)} ---\n{txt}"
        if total + len(chunk) > max_total:
            break
        names.append(str(p.relative_to(ws)))
        total += len(chunk)
    return names
