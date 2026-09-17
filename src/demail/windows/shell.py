import os
import re
from collections.abc import Callable
from pathlib import Path
from urllib.parse import quote, urlencode

MAILTO_URI_LIMIT = 8_000
_EMAIL_ADDRESS = re.compile(r"^[^@\s,;]+@[^@\s,;]+\.[^@\s,;]+$")


def open_folder(path: Path, opener: Callable[[str], object] | None = None) -> None:
    if not path.is_absolute() or not path.is_dir():
        raise OSError("Archive folder is unavailable.")
    launch = opener or os.startfile
    launch(str(path))


def open_email_draft(
    recipient: str,
    subject: str,
    body: str,
    opener: Callable[[str], object] | None = None,
) -> None:
    if not _EMAIL_ADDRESS.fullmatch(recipient) or any(
        ord(character) < 32 for character in recipient
    ):
        raise ValueError("The report email address is invalid.")
    if not subject.strip() or "\r" in subject or "\n" in subject:
        raise ValueError("The report email subject is invalid.")
    if not body.strip() or "\x00" in body:
        raise ValueError("The diagnostic report is blank or invalid.")
    query = urlencode({"subject": subject, "body": body}, quote_via=quote)
    uri = f"mailto:{quote(recipient, safe='@')}?{query}"
    if len(uri) > MAILTO_URI_LIMIT:
        raise ValueError("The diagnostic report is too large for an email draft.")
    launch = opener or os.startfile
    result = launch(uri)
    if result is False:
        raise OSError("The default email application did not accept the draft.")
