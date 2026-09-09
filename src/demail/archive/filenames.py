import re
from datetime import UTC, datetime

MAX_SUBJECT_SLUG = 72
RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def slug(raw: str, max_length: int) -> str:
    if max_length <= 0:
        return ""
    ascii_text = "".join(character if character.isascii() else "-" for character in raw)
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", ascii_text)
    safe = re.sub(r"[-._]+", lambda match: match.group(0)[0], safe)
    return safe[:max_length].strip("-._ ")


def eml_filename(internal_date_ms: int | None, subject: str | None, gmail_message_id: str) -> str:
    message_id = slug(gmail_message_id, 40) or "message"
    stamp = None
    if internal_date_ms is not None:
        stamp = datetime.fromtimestamp(internal_date_ms / 1000, UTC).strftime("%Y-%m-%d_%H%M")
    subject_slug = slug(subject or "", MAX_SUBJECT_SLUG)
    base = "_".join(part for part in (stamp, subject_slug or None, message_id) if part)
    if base.upper() in RESERVED_NAMES:
        base = f"_{base}"
    return f"{base}.eml"
