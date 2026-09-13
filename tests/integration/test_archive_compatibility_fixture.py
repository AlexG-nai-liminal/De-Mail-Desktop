import hashlib
import json
from pathlib import Path

from demail.archive.eml_scanner import scan_eml
from demail.archive.verification import VerificationResult, verify_file

FIXTURE = Path(__file__).parents[1] / "fixtures" / "android-archive-v1"


def test_android_archive_v1_fixture_is_self_consistent_and_verifiable() -> None:
    manifest = json.loads((FIXTURE / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schemaVersion"] == 1
    assert set(manifest) == {
        "schemaVersion",
        "generator",
        "archive",
        "verification",
        "messages",
        "failures",
    }
    assert manifest["archive"]["counts"] == {
        "selected": 1,
        "exported": 1,
        "failed": 0,
        "verified": 1,
    }
    message = manifest["messages"][0]
    eml = FIXTURE / message["path"]
    assert eml.stat().st_size == message["byteSize"]
    assert hashlib.sha256(eml.read_bytes()).hexdigest() == message["sha256"]
    assert verify_file(eml, message["byteSize"], message["sha256"]).result == (
        VerificationResult.VERIFIED
    )


def test_android_archive_v1_fixture_metadata_matches_original_eml() -> None:
    manifest = json.loads((FIXTURE / "manifest.json").read_text(encoding="utf-8"))
    message = manifest["messages"][0]
    scan = scan_eml(FIXTURE / message["path"], chunk_size=11)
    assert scan.subject == message["subject"]
    assert scan.sender == message["from"]
    assert scan.recipients == message["to"]
    assert scan.date_header == message["date"]
    assert scan.rfc822_message_id == message["rfc822MessageId"]
    assert scan.attachment_count == message["attachmentCount"]
    assert list(scan.attachment_names) == message["attachmentNames"]


def test_compatibility_fixture_contains_no_credential_shaped_fields() -> None:
    manifest_text = (FIXTURE / "manifest.json").read_text(encoding="utf-8").lower()
    forbidden = ("access_token", "refresh_token", "client_secret", "authorization", "bearer")
    assert all(item not in manifest_text for item in forbidden)
    assert '": null' not in manifest_text
