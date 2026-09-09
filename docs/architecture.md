# Architecture

Application code uses a `src` layout under `demail`:

- `domain`: immutable models and archive invariants, with no UI or platform dependencies
- `gmail`: OAuth boundary, REST transport, query construction, pagination, and streaming decode
- `archive`: layout, filenames, atomic file writing, hashing, manifests, and read-back verification
- `persistence`: SQLite migrations and repositories for resumable operation state
- `jobs`: single-owner archive orchestration and recovery
- `ui`: PySide6 Qt Widgets windows, pages, presenters, and view models
- `windows`: Credential Manager or DPAPI secrets, filesystem capability checks, and diagnostics

Dependencies point inward. The domain package does not import PySide6, HTTP, SQLite, or Windows
APIs. UI and job orchestration depend on interfaces at the Gmail, archive, and persistence
boundaries.

The initial dependency set is PySide6, google-auth, google-auth-oauthlib, httpx, keyring, and
pywin32. Test dependencies are pytest, pytest-qt, and pytest-cov. Nuitka is a development and
packaging dependency. `pyside6-deploy` is supplied by PySide6 and will be configured only when an
installer or executable build is explicitly requested.

