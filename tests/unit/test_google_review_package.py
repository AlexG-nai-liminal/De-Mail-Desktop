from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "docs" / "google-oauth"


def read(name: str) -> str:
    return (PACKAGE / name).read_text(encoding="utf-8")


def test_review_package_contains_every_required_document() -> None:
    assert {path.name for path in PACKAGE.glob("*.md")} == {
        "README.md",
        "SCOPE_JUSTIFICATION.md",
        "REVIEWER_WALKTHROUGH.md",
        "DEMO_VIDEO_SCRIPT.md",
        "LOCAL_SECURITY_MODEL.md",
        "SUBMISSION_CHECKLIST.md",
    }


def test_scope_justification_uses_only_readonly_and_explains_raw_requirement() -> None:
    document = read("SCOPE_JUSTIFICATION.md")
    assert "https://www.googleapis.com/auth/gmail.readonly" in document
    assert "format=raw" in document
    assert "gmail.metadata" in document
    assert "least-privilege" in document
    assert "does not request `gmail.modify`" in document


def test_security_claims_include_local_only_and_limited_use() -> None:
    combined = "\n".join(path.read_text(encoding="utf-8") for path in PACKAGE.glob("*.md"))
    assert "never transmitted to de-Mail or Liminal" in combined
    assert "Windows Data Protection API" in combined
    assert "Limited Use" in combined
    assert "Google makes the final determination" in combined


def test_submission_cannot_be_mistaken_for_complete() -> None:
    checklist = read("SUBMISSION_CHECKLIST.md")
    assert "[ ]" in checklist
    for placeholder in ("[VERSION]", "[SIGNED_INSTALLER_FILENAME]", "[INSTALLER_SHA256]"):
        assert placeholder in checklist
    assert "No public installer released before approval" in checklist
