from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from os import replace
from pathlib import Path
from typing import Any

from demail import __version__
from demail.archive.layout import require_safe_archive_component

VERIFICATION_METHOD = (
    "Every exported file was reopened from the destination, read back in full, "
    "and its SHA-256 compared with the hash recorded when it was written."
)


def _without_none(value: dict[str, Any]) -> dict[str, Any]:
    return {
        key: _clean(item)
        for key, item in value.items()
        if item is not None
    }


def _clean(value: Any) -> Any:
    if isinstance(value, dict):
        return _without_none(value)
    if isinstance(value, list):
        return [_clean(item) for item in value]
    return value


def _internal_date(value: object) -> str | None:
    if value is None:
        return None
    try:
        milliseconds = int(value)
        if milliseconds < 0:
            return None
        return datetime.fromtimestamp(milliseconds / 1000, UTC).isoformat().replace(
            "+00:00", "Z"
        )
    except (OSError, OverflowError, TypeError, ValueError):
        return None


def _json_list(value: object) -> list[object]:
    if value is None:
        return []
    try:
        parsed = json.loads(str(value))
    except (json.JSONDecodeError, TypeError, ValueError):
        return []
    return parsed if isinstance(parsed, list) else []


def _json_object(value: object) -> dict[str, object]:
    try:
        parsed = json.loads(str(value))
    except (json.JSONDecodeError, TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _verification_status(operation: Mapping[str, object]) -> str:
    if int(operation.get("selected_count", 0)) == 0:
        return "NOT_RUN"
    if operation.get("verified_at") is None:
        return "NOT_RUN"
    if operation.get("status") == "VERIFIED":
        return "VERIFIED"
    return "INCOMPLETE" if int(operation.get("verified_count", 0)) else "FAILED"


def _message_path(row: Mapping[str, object]) -> str:
    try:
        file_name = require_safe_archive_component(str(row["file_name"]), suffix=".eml")
    except (KeyError, ValueError):
        return "messages/"
    return f"messages/{file_name}"


def write_manifest(
    path: Path,
    operation: Mapping[str, object],
    messages: Sequence[Mapping[str, object]],
) -> None:
    rows = messages
    criteria = _json_object(operation.get("selection_json", "{}"))
    missing = sum(row["verification"] == "MISSING" for row in rows)
    mismatched = sum(
        row["verification"] in {"UNREADABLE", "SIZE_MISMATCH", "HASH_MISMATCH"}
        for row in rows
    )
    verified_bytes = sum(
        int(row["byte_size"] or 0) for row in rows if row["verification"] == "VERIFIED"
    )
    verified_attachments = sum(
        int(row["attachment_count"] or 0)
        for row in rows
        if row["verification"] == "VERIFIED"
    )
    verified_inline_attachments = sum(
        int(row["inline_attachment_count"] or 0)
        for row in rows
        if row["verification"] == "VERIFIED"
    )
    partial = path.with_name(f"{path.name}.partial")
    try:
        with partial.open("w", encoding="utf-8", newline="\n") as stream:
            archive = _without_none(
                {
                    "archiveId": str(operation["id"]),
                    "createdAt": operation["created_at"],
                    "completedAt": operation["completed_at"],
                    "account": _without_none(
                        {
                            "emailAddress": operation["account_email"],
                            "gmailMessagesTotal": operation["account_messages_total"],
                            "gmailThreadsTotal": operation.get("account_threads_total"),
                        }
                    ),
                    "selection": _without_none(
                        {
                            "description": operation["selection_description"],
                            "gmailQuery": operation["gmail_query"],
                            "gmailLabelIds": _json_list(operation["gmail_label_ids"]),
                            "includeSpamAndTrash": criteria.get("includeSpamAndTrash", False),
                            "criteria": criteria,
                        }
                    ),
                    "destination": {
                        "folderDisplayPath": operation["destination_path"],
                        "archiveFolderName": operation.get("archive_folder_name", path.parent.name),
                        "messagesFolderName": "messages",
                    },
                    "counts": {
                        "selected": operation["selected_count"],
                        "exported": operation["exported_count"],
                        "failed": operation["failed_count"],
                        "verified": operation["verified_count"],
                    },
                    "totalArchivedBytes": verified_bytes or operation["total_bytes"],
                    "totalAttachments": verified_attachments,
                    "totalInlineAttachments": verified_inline_attachments,
                }
            )
            verification = _without_none(
                {
                    "status": _verification_status(operation),
                    "verifiedAt": operation["verified_at"],
                    "selected": operation["selected_count"],
                    "exported": operation["exported_count"],
                    "verified": operation["verified_count"],
                    "failed": operation["failed_count"],
                    "missing": missing,
                    "mismatched": mismatched,
                    "totalVerifiedBytes": verified_bytes,
                    "method": VERIFICATION_METHOD,
                }
            )
            stream.write('{"schemaVersion":1,"generator":')
            json.dump(f"de-Mail Desktop {__version__}", stream, ensure_ascii=False)
            stream.write(',"archive":')
            json.dump(archive, stream, ensure_ascii=False, separators=(",", ":"))
            stream.write(',"verification":')
            json.dump(verification, stream, ensure_ascii=False, separators=(",", ":"))
            stream.write(',"messages":[\n')
            first = True
            for row in rows:
                if not first:
                    stream.write(",\n")
                first = False
                json.dump(
                    _without_none(
                        {
                            "gmailMessageId": row["gmail_message_id"],
                            "gmailThreadId": row["gmail_thread_id"],
                            "subject": row["subject"],
                            "from": row["sender"],
                            "to": row["recipients"],
                            "cc": row["cc_recipients"],
                            "bcc": row["bcc_recipients"],
                            "date": row["date_header"],
                            "internalDate": _internal_date(row["internal_date_ms"]),
                            "rfc822MessageId": row["rfc822_message_id"],
                            "path": _message_path(row),
                            "byteSize": row["byte_size"],
                            "sha256": row["sha256"] or "",
                            "attachmentCount": row["attachment_count"],
                            "inlineAttachmentCount": row["inline_attachment_count"],
                            "attachmentNames": _json_list(row["attachment_names"]),
                            "gmailLabelIds": _json_list(row["label_ids"]),
                            "verification": row["verification"],
                        }
                    ),
                    stream,
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
            stream.write('\n],"failures":[\n')
            first = True
            for row in rows:
                if not (row["failure_stage"] or row["failure_message"]):
                    continue
                if not first:
                    stream.write(",\n")
                first = False
                json.dump(
                    {
                        "gmailMessageId": row["gmail_message_id"],
                        "stage": row["failure_stage"] or "archive",
                        "error": row["failure_message"]
                        or "The message could not be archived.",
                        "attempts": row["attempts"],
                    },
                    stream,
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
            stream.write("\n]}\n")
            stream.flush()
            os.fsync(stream.fileno())
        replace(partial, path)
    except Exception:
        partial.unlink(missing_ok=True)
        raise
