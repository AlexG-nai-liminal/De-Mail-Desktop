# Android compatibility requirements

The Android repository was inspected as a behavioral and archive-format reference. The desktop
implementation must preserve these contracts:

- Selection dates are ISO local dates. Both ends are inclusive to the user, so the Gmail query's
  exclusive `before:` date is the following day.
- Exact label IDs use `labelIds`, not a `label:` search term. Manual selections resolve directly
  from their fixed Gmail message IDs. User search expressions containing spaces are grouped.
- The selection is materialized as one durable row per Gmail message before downloading starts.
  Its selected count is a fixed denominator and lost rows count as missing.
- Every operation has a unique dated folder containing `messages` and `manifest.json`. Original
  RFC 822 bytes remain in `.eml` files and attachments remain inside MIME parts.
- Message filenames are deterministic across retries, sortable by UTC internal date, retain the
  Gmail message ID, and are safe for Windows and FAT-like filesystems.
- Gmail raw JSON is decoded incrementally through a base64url decoder. Archive bytes are hashed as
  written to a sibling `.partial` file, closed, and atomically promoted with `os.replace`.
- A message becomes exported only after the final path exists and its byte size and hash are
  durably recorded. Resume skips completed rows and reuses the stored deterministic filename.
- Verification is a separate full read-back. Only equality of selected, recorded, exported, and
  verified counts, with no failures or outstanding checks, produces `VERIFIED`.
- Operation states distinguish queued, exporting, verifying, verified, partial, failed, and
  cancelled. Only one worker may own an operation.
- Manifest schema version 1 records account, selection, destination, fixed counts, message Gmail
  IDs and headers, relative path, bytes, SHA-256, attachments, verification, and failures.
- Mailbox eras follow cumulative message counts rather than elapsed time, cover the mailbox with
  open outer bounds, and do not invent three eras when the data cannot support them.
- Diagnostic reports redact addresses, bearer tokens, paths, document identifiers, and filenames
  that may expose subjects. They never include credentials, recipients, or persistent logs.
- Ordinary archive authorization is exactly `gmail.readonly`. Reclaim remains out of scope until
  archive and verification are stable, and later uses separate explicit `gmail.modify` consent.
- User-facing text must not contain em dash or en dash characters.

The Android core tests for query construction, selection validation, naming, archive layout,
streaming base64url and raw JSON parsing, MIME scanning, manifest codecs, verification summaries,
mailbox eras, diagnostics redaction, and reclaim gates are the compatibility test inventory.

