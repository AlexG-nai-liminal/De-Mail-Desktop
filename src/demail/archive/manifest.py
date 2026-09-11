import json
import os
from collections.abc import Iterable, Mapping
from pathlib import Path


def write_manifest(
    path: Path, operation: Mapping[str, object], messages: Iterable[Mapping[str, object]]
) -> None:
    partial = path.with_name(f"{path.name}.partial")
    try:
        with partial.open("w", encoding="utf-8", newline="\n") as stream:
            archive = {
                "archiveId": str(operation["id"]),
                "createdAt": operation["created_at"],
                "completedAt": operation["completed_at"],
                "account": {
                    "emailAddress": operation["account_email"],
                    "gmailMessagesTotal": operation["account_messages_total"],
                },
                "selection": {
                    "description": operation["selection_description"],
                    "gmailQuery": operation["gmail_query"],
                    "gmailLabelIds": json.loads(str(operation["gmail_label_ids"])),
                },
                "destination": {"folderDisplayPath": operation["destination_path"]},
                "counts": {
                    "selected": operation["selected_count"],
                    "exported": operation["exported_count"],
                    "failed": operation["failed_count"],
                    "verified": operation["verified_count"],
                },
                "totalArchivedBytes": operation["total_bytes"],
                "totalAttachments": operation["attachment_count"],
            }
            verification = {
                "status": operation["status"],
                "verifiedAt": operation["verified_at"],
                "selected": operation["selected_count"],
                "verified": operation["verified_count"],
                "failed": operation["failed_count"],
            }
            stream.write('{"schemaVersion":1,"archive":')
            json.dump(archive, stream, ensure_ascii=False, separators=(",", ":"))
            stream.write(',"verification":')
            json.dump(verification, stream, ensure_ascii=False, separators=(",", ":"))
            stream.write(',"messages":[\n')
            first = True
            failures: list[dict[str, object]] = []
            for row in messages:
                if not first:
                    stream.write(",\n")
                first = False
                json.dump(
                    {
                        "gmailMessageId": row["gmail_message_id"],
                        "gmailThreadId": row["gmail_thread_id"],
                        "subject": row["subject"],
                        "from": row["sender"],
                        "internalDateMillis": row["internal_date_ms"],
                        "path": row["relative_path"],
                        "byteSize": row["byte_size"],
                        "sha256": row["sha256"],
                        "attachmentCount": row["attachment_count"],
                        "verification": row["verification"],
                    },
                    stream,
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                if row["failure_stage"] or row["failure_message"]:
                    failures.append(
                        {
                            "gmailMessageId": row["gmail_message_id"],
                            "stage": row["failure_stage"],
                            "reason": row["failure_message"],
                        }
                    )
            stream.write('\n],"failures":')
            json.dump(failures, stream, ensure_ascii=False, separators=(",", ":"))
            stream.write("}\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(partial, path)
    except Exception:
        partial.unlink(missing_ok=True)
        raise
