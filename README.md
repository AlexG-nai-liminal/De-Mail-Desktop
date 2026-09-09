# de-Mail Desktop

de-Mail Desktop is a Windows archive utility that copies original Gmail messages into a
user-controlled folder and verifies every copied byte. It is not an email client and never
permanently deletes mail.

This repository currently contains the first tested vertical slice: domain models, Gmail query
construction, deterministic Windows-safe filenames, streaming SHA-256 utilities, and a durable
SQLite schema with forward-only migrations.

## Development

Python 3.12 is required.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[test,dev]"
.venv\Scripts\python -m pytest
```

The Android project at `../LiteSyncProject` is a read-only behavioral reference. Compatibility
requirements identified during the initial review are recorded in
[`docs/android-compatibility.md`](docs/android-compatibility.md).

