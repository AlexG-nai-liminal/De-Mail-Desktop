from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "windows-release.yml"
GUIDE = ROOT / "docs" / "RELEASES.md"


def test_release_workflow_keeps_source_and_public_feed_separate() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "DEMAIL_RELEASES_TOKEN" in workflow
    assert "AlexG-nai-liminal/de-mail-desktop-releases" in workflow
    assert "Publish private source release" in workflow
    assert "Publish public release-only feed" in workflow
    assert "actions/checkout" in workflow
    assert "repository:" not in workflow
    assert "push" not in workflow.casefold().split("publish public release-only feed", 1)[1]


def test_tagged_release_requires_matching_version_and_signatures() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert 'if ($tag -ne "v$version")' in workflow
    assert "WINDOWS_SIGNING_CERTIFICATE_BASE64" in workflow
    assert "signtool.FullName sign" in workflow
    assert workflow.count("signtool.FullName verify") == 2
    assert "Tagged releases require" in workflow


def test_workflow_publishes_only_setup_and_checksum_assets() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    public_step = workflow.split("- name: Publish public release-only feed", 1)[1]

    assert "de-Mail-Desktop-Setup-" in public_step
    assert "SHA256SUMS.txt" in public_step
    assert "src/" not in public_step
    assert "CHANGELOG.md" not in public_step


def test_release_guide_documents_least_privilege_and_no_silent_execution() -> None:
    guide = GUIDE.read_text(encoding="utf-8")

    assert "Contents: Read and write" in guide
    assert "cannot read the private repository" in guide
    assert "does not" in guide and "execute anything" in guide
    assert "Local setup builds are intentionally unsigned" in guide
