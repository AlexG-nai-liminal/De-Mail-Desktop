"""Privacy boundary for all user-visible diagnostic text."""

import re

MASK = "•••"
MAX_LENGTH = 4_000

_BEARER = re.compile(r"\bBearer\s+\S+", re.IGNORECASE)
_CREDENTIAL = re.compile(
    r"\b(access_token|refresh_token|client_secret)\s*[:=]\s*\S+",
    re.IGNORECASE,
)
_NON_BEARER_AUTHORIZATION = re.compile(
    r"\bAuthorization\s*[:=]\s*(?!Bearer\b)\S+(?:\s+\S+)?", re.IGNORECASE
)
_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@([A-Za-z0-9.\-]+\.[A-Za-z]{2,})")
_EML_FILE = re.compile(r"[^\s/\\\"']*\.eml", re.IGNORECASE)
_FILE_URI = re.compile(r"file://\S+", re.IGNORECASE)
_WINDOWS_PATH = re.compile(r"(?<![\w])(?:[A-Za-z]:\\|\\\\)[^\r\n]+")
_POSIX_PATH = re.compile(r"(?<![\w:/])/(?:[\w .\-]+/)+[\w .\-]*")
_LONG_OPAQUE = re.compile(r"\b[A-Za-z0-9_\-]{28,}\b")


def redact(text: str | None) -> str:
    if text is None or not text.strip():
        return ""
    value = _BEARER.sub(f"Bearer {MASK}", text)
    value = _CREDENTIAL.sub(lambda match: f"{match.group(1)}: {MASK}", value)
    value = _NON_BEARER_AUTHORIZATION.sub(f"Authorization: {MASK}", value)
    value = _EMAIL.sub(lambda match: f"{MASK}@{match.group(1)}", value)
    value = _EML_FILE.sub(f"{MASK}.eml", value)
    value = _FILE_URI.sub(f"file://{MASK}", value)
    value = _WINDOWS_PATH.sub(lambda _: f"{MASK}\\", value)
    value = _POSIX_PATH.sub(f"/{MASK}/", value)
    value = _LONG_OPAQUE.sub(MASK, value)
    return "\n".join(line.rstrip() for line in value.splitlines())[:MAX_LENGTH]


def mask_account(address: str | None) -> str:
    if address is None or not address.strip():
        return "not connected"
    _, separator, domain = address.partition("@")
    return f"{MASK}@{domain}" if separator and domain else MASK
