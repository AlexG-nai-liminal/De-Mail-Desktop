from collections.abc import Sequence
from pathlib import Path

import pytest

from demail.archive.manifest import write_manifest


class RepeatedRows(Sequence[dict[str, object]]):
    def __init__(self, row: dict[str, object], count: int) -> None:
        self.row = row
        self.count = count

    def __len__(self) -> int:
        return self.count

    def __getitem__(self, index: int) -> dict[str, object]:
        if not 0 <= index < self.count:
            raise IndexError(index)
        return self.row


def operation() -> dict[str, object]:
    return {
        "id": 1,
        "created_at": "2026-09-12T00:00:00+00:00",
        "completed_at": None,
        "verified_at": None,
        "account_email": "archive@example.com",
        "account_messages_total": 1,
        "selection_description": "All mail",
        "gmail_query": None,
        "gmail_label_ids": "[]",
        "destination_path": "C:/Archive",
        "selected_count": 0,
        "exported_count": 0,
        "failed_count": 0,
        "verified_count": 0,
        "total_bytes": 0,
        "attachment_count": 0,
        "status": "VERIFIED",
    }


def test_manifest_rename_failure_preserves_previous_file_and_cleans_partial(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    final = tmp_path / "manifest.json"
    final.write_text('{"previous":true}', encoding="utf-8")

    def fail_replace(source: Path, destination: Path) -> None:
        raise PermissionError("simulated antivirus lock")

    monkeypatch.setattr("demail.archive.manifest.replace", fail_replace)
    with pytest.raises(PermissionError, match="antivirus"):
        write_manifest(final, operation(), ())
    assert final.read_text(encoding="utf-8") == '{"previous":true}'
    assert not (tmp_path / "manifest.json.partial").exists()


def test_large_manifest_accepts_reiterable_rows_without_copying_them(tmp_path: Path) -> None:
    row = {
        "gmail_message_id": "repeated",
        "gmail_thread_id": None,
        "subject": None,
        "sender": None,
        "recipients": None,
        "cc_recipients": None,
        "bcc_recipients": None,
        "date_header": None,
        "internal_date_ms": None,
        "rfc822_message_id": None,
        "file_name": "repeated.eml",
        "relative_path": "messages/repeated.eml",
        "byte_size": 1,
        "sha256": "00",
        "attachment_count": 0,
        "inline_attachment_count": 0,
        "attachment_names": "[]",
        "label_ids": "[]",
        "verification": "VERIFIED",
        "failure_stage": None,
        "failure_message": None,
        "attempts": 1,
    }
    archive = operation()
    archive.update(
        {
            "archive_folder_name": "large",
            "selection_json": "{}",
            "selected_count": 10_001,
            "exported_count": 10_001,
            "verified_count": 10_001,
            "verified_at": "2026-09-12T00:00:01+00:00",
            "total_bytes": 10_001,
        }
    )
    final = tmp_path / "manifest.json"
    write_manifest(final, archive, RepeatedRows(row, 10_001))
    text = final.read_text(encoding="utf-8")
    assert text.count('"gmailMessageId":"repeated"') == 10_001
    assert not final.with_name("manifest.json.partial").exists()
