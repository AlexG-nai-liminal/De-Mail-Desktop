"""DPAPI-protected OAuth credential persistence."""

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol


class Protector(Protocol):
    def protect(self, plaintext: bytes) -> bytes: ...

    def unprotect(self, ciphertext: bytes) -> bytes: ...


@dataclass(frozen=True, slots=True)
class StoredCredentials:
    token: str | None
    refresh_token: str
    token_uri: str
    client_id: str
    client_secret: str
    scopes: tuple[str, ...]
    expiry: str | None = None

    def __post_init__(self) -> None:
        if not self.refresh_token:
            raise ValueError("A refresh credential is required for durable authorization.")


class CredentialStore:
    def __init__(self, path: Path, protector: Protector) -> None:
        self.path = path
        self.partial_path = path.with_name(f"{path.name}.partial")
        self.protector = protector

    def save(self, credentials: StoredCredentials) -> None:
        document = asdict(credentials)
        document["scopes"] = list(credentials.scopes)
        plaintext = json.dumps(document, separators=(",", ":")).encode("utf-8")
        protected = self.protector.protect(plaintext)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self.partial_path.open("wb") as stream:
                stream.write(protected)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(self.partial_path, self.path)
        except Exception:
            self.partial_path.unlink(missing_ok=True)
            raise

    def load(self) -> StoredCredentials | None:
        if not self.path.exists():
            return None
        try:
            plaintext = self.protector.unprotect(self.path.read_bytes())
            document = json.loads(plaintext.decode("utf-8"))
            return StoredCredentials(
                token=document.get("token"),
                refresh_token=document["refresh_token"],
                token_uri=document["token_uri"],
                client_id=document["client_id"],
                client_secret=document["client_secret"],
                scopes=tuple(document["scopes"]),
                expiry=document.get("expiry"),
            )
        except (KeyError, TypeError, ValueError, UnicodeError, json.JSONDecodeError) as error:
            raise ValueError("Saved Google authorization is invalid or unreadable.") from error

    def clear(self) -> None:
        self.path.unlink(missing_ok=True)
        self.partial_path.unlink(missing_ok=True)

