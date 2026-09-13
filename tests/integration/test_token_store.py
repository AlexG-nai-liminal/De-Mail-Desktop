from pathlib import Path

import pytest

from demail.auth.token_store import (
    MAX_PLAINTEXT_CREDENTIAL_BYTES,
    MAX_PROTECTED_CREDENTIAL_BYTES,
    CredentialStore,
    StoredCredentials,
)


class ReversibleProtector:
    marker = b"protected:"

    def protect(self, plaintext: bytes) -> bytes:
        return self.marker + plaintext[::-1]

    def unprotect(self, ciphertext: bytes) -> bytes:
        if not ciphertext.startswith(self.marker):
            raise ValueError("not protected")
        return ciphertext.removeprefix(self.marker)[::-1]


def credentials(refresh_token: str = "refresh-secret") -> StoredCredentials:
    return StoredCredentials(
        token="access-secret",
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id="123-desktop.apps.googleusercontent.com",
        client_secret="client-secret",
        scopes=("https://www.googleapis.com/auth/gmail.readonly",),
    )


def test_credentials_round_trip_without_plaintext_on_disk(tmp_path: Path) -> None:
    path = tmp_path / "authorization.bin"
    store = CredentialStore(path, ReversibleProtector())
    expected = credentials()
    store.save(expected)
    stored_bytes = path.read_bytes()
    assert b"refresh-secret" not in stored_bytes
    assert b"access-secret" not in stored_bytes
    assert store.load() == expected
    assert not store.partial_path.exists()


def test_atomic_replacement_preserves_one_credential_file(tmp_path: Path) -> None:
    path = tmp_path / "authorization.bin"
    store = CredentialStore(path, ReversibleProtector())
    store.save(credentials("first"))
    store.save(credentials("second"))
    assert store.load() == credentials("second")
    assert [item.name for item in tmp_path.iterdir()] == ["authorization.bin"]


def test_interrupted_partial_is_replaced_on_next_save(tmp_path: Path) -> None:
    path = tmp_path / "authorization.bin"
    store = CredentialStore(path, ReversibleProtector())
    store.partial_path.write_bytes(b"interrupted plaintext must disappear")
    store.save(credentials())
    assert not store.partial_path.exists()
    assert b"plaintext" not in path.read_bytes()


@pytest.mark.parametrize("contents", [b"plaintext token", b"protected:not-json"])
def test_unreadable_credentials_fail_closed(tmp_path: Path, contents: bytes) -> None:
    path = tmp_path / "authorization.bin"
    path.write_bytes(contents)
    with pytest.raises(ValueError):
        CredentialStore(path, ReversibleProtector()).load()


def test_clear_removes_final_and_partial_files(tmp_path: Path) -> None:
    path = tmp_path / "authorization.bin"
    store = CredentialStore(path, ReversibleProtector())
    store.save(credentials())
    store.partial_path.write_bytes(b"partial")
    store.clear()
    assert not path.exists()
    assert not store.partial_path.exists()


def test_blank_refresh_credential_is_never_persisted() -> None:
    with pytest.raises(ValueError, match="refresh credential"):
        credentials("")


def test_oversized_protected_authorization_is_rejected_before_decryption(
    tmp_path: Path,
) -> None:
    class MustNotDecrypt(ReversibleProtector):
        def unprotect(self, ciphertext: bytes) -> bytes:
            raise AssertionError("oversized data reached the decryptor")

    path = tmp_path / "authorization.bin"
    path.write_bytes(b"x" * (MAX_PROTECTED_CREDENTIAL_BYTES + 1))
    with pytest.raises(ValueError, match="invalid or unreadable"):
        CredentialStore(path, MustNotDecrypt()).load()


def test_oversized_plaintext_authorization_is_never_written(tmp_path: Path) -> None:
    path = tmp_path / "authorization.bin"
    huge = credentials("x" * MAX_PLAINTEXT_CREDENTIAL_BYTES)
    with pytest.raises(ValueError, match="unexpectedly large"):
        CredentialStore(path, ReversibleProtector()).save(huge)
    assert not path.exists()
    assert not path.with_name("authorization.bin.partial").exists()
