# de-Mail Desktop

de-Mail Desktop is a Windows archive utility that copies original Gmail messages into a
user-controlled folder and verifies every copied byte. It is not an email client and never
permanently deletes mail.

The application now includes Google Desktop OAuth, exact Gmail selection, bounded-memory RFC 822
downloads, MIME metadata scanning, read-back verification, durable history and resume, and
privacy-safe diagnostics. Archive manifests preserve the Android schema version 1 contract.

## Development

Python 3.12 is required.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[test,dev]"
.venv\Scripts\python -m pytest
```

Run the application from the source tree with:

```powershell
.venv\Scripts\python main.py
```

## Packaging preparation

The checked-in `pysidedeploy.spec` configures a GUI-only standalone Nuitka build. Inspect the
resolved deployment command without producing an executable:

```powershell
.venv\Scripts\pyside6-deploy --config-file pysidedeploy.spec --dry-run --extra-ignore-dirs=tools
```

Build the standalone Windows application with a project-local Nuitka cache:

```powershell
$env:NUITKA_CACHE_DIR = Join-Path $PWD ".nuitka-cache"
$env:PYTHONPATH = Join-Path $PWD "src"
.venv\Scripts\pyside6-deploy --config-file pysidedeploy.spec --extra-ignore-dirs=tools --force
```

The runnable folder is written to `dist\de-Mail Desktop.dist`. Keep that folder intact when
copying the application because the executable depends on the adjacent DLLs and Qt plugins.

Build the per-user Inno Setup installer after the standalone folder has been created:

```powershell
.venv\Scripts\python tools\build_installer.py
```

The setup executable is written to `dist\installer`. It installs without administrator rights
and leaves application data in place when the program is uninstalled.

Build the installer and update an existing permanent installation in place with:

```powershell
.venv\Scripts\python tools\build_installer.py --install
```

The stable installer identity preserves the installation directory, OAuth authorization,
settings, archive history, and user-created archives across updates. No uninstall is required.

The Android project at `../LiteSyncProject` is a read-only behavioral reference. Compatibility
requirements identified during the initial review are recorded in
[`docs/android-compatibility.md`](docs/android-compatibility.md).
