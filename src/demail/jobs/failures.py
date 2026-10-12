"""Actionable failure explanations that never include raw exception text."""

import errno

from demail.auth.token_provider import GoogleAuthorizationError
from demail.gmail.client import GmailApiError


def explain_failure(error: Exception) -> str:
    if isinstance(error, GoogleAuthorizationError) or (
        isinstance(error, GmailApiError) and error.status_code in {401, 403}
    ):
        return "Google authorization is unavailable. Reconnect the original account, then resume."
    if isinstance(error, GmailApiError) and error.connection_failure:
        return "The Gmail connection was interrupted. Check the network, then resume."
    if isinstance(error, OSError):
        if error.errno == errno.ENOSPC or getattr(error, "winerror", None) == 112:
            return "The archive drive is full. Free space on that drive, then resume."
        if isinstance(error, PermissionError):
            return "The archive folder is not writable. Restore write access, then resume."
        return (
            "The destination is unavailable. Reconnect the drive and check write access, "
            "then resume."
        )
    return "The archive stopped safely. Completed files remain available. Review History and retry."
