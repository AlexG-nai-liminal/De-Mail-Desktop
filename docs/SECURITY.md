# Local-only security model

## Boundary

de-Mail Desktop is a local Windows application. Its production design has no Liminal application
server in the Gmail data path.

| Data | Source | Destination | Liminal receives it |
| --- | --- | --- | --- |
| OAuth authorization request | Desktop app | Google OAuth endpoints | No |
| Access and refresh credentials | Google | DPAPI-encrypted local file | No |
| Gmail messages and attachments | Gmail API | Memory, then user-selected folder | No |
| Archive manifest and hashes | Desktop app | User-selected folder | No |
| Archive operation history | Desktop app | Local SQLite database | No |
| Problem report | Desktop app | Local preview; user-selected delivery | Only if the user emails it |
| Update metadata | Public GitHub API | Desktop app | No Gmail data is sent |

## Authorization

The archive workflow requests exactly `https://www.googleapis.com/auth/gmail.readonly`. It does
not request permission to send, modify, trash, or permanently delete Gmail messages. The OAuth
flow opens Google's system-browser page and returns through an ephemeral localhost callback.
Refresh credentials are protected with Windows Data Protection API for the current Windows user.

Disconnect removes the protected local credential. Reset authorization additionally clears the
privacy acknowledgement and any development-only client selection. Revoking the app from the
Google Account connections page invalidates the server-side grant.

## Archive processing

Message data is streamed through bounded memory into atomic local files. A partial file is not
promoted to its final name until its content is complete. de-Mail records SHA-256 hashes and
reads the stored message back for verification. The destination is always selected by the user.

## Diagnostics

Diagnostics are constructed from an explicit allowlist of operational counts and platform facts.
Message subjects, message bodies, attachment content, OAuth credentials, authorization headers,
full email addresses, archive paths, and `.eml` filenames are not collected. User-entered problem
descriptions pass through redaction and the complete report is shown before delivery controls are
enabled. There is no automatic telemetry endpoint.

## Updates

The update checker reads bounded JSON metadata from a fixed public GitHub repository. It validates
a strict stable version and expected installer name, constructs its own trusted release URL, and
does not download or execute an update. Tagged production releases require Authenticode signing
and checksum publication.
