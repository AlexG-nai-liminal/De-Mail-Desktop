import os
import re
import webbrowser
from collections.abc import Callable
from pathlib import Path
from urllib.parse import quote, urlencode, urlsplit

MAILTO_URI_LIMIT = 8_000
_EMAIL_ADDRESS = re.compile(r"^[^@\s,;]+@[^@\s,;]+\.[^@\s,;]+$")
_RELEASE_PATH = "/AlexG-nai-liminal/de-mail-desktop-releases/releases/"


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


def open_release_page(
    url: str, opener: Callable[[str], object] | None = None
) -> None:
    """Open only a trusted HTTPS page in the public release repository."""
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.netloc != "github.com"
        or not parsed.path.startswith(_RELEASE_PATH)
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("The update page address is not trusted.")
    launch = opener or webbrowser.open
    if launch(url) is False:
        raise OSError("The default browser did not accept the update page.")
