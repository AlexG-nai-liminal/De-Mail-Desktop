# Local-only security model

## Data flow

1. The installed Windows application opens Google's OAuth page in the system browser.
2. Google returns authorization through a localhost callback to the application.
3. The refresh credential is encrypted for the current Windows user with DPAPI.
4. Gmail messages are requested from Google's API over HTTPS.
5. Message bytes are streamed to the local destination selected by the user.
6. Each completed file is reopened and verified against its recorded size and hash.

There is no de-Mail or Liminal application server in this flow.

## Storage boundaries

- OAuth credentials: protected local application-data directory.
- Archive content: only the destination explicitly selected by the user.
- Operation history: local database containing operational metadata.
- Diagnostics: generated locally and shown before the user chooses to save, copy,
  or place them into an email draft.

## Credential removal

**Disconnect Google account** deletes the protected local token. It does not remove
the Google-side grant and does not delete archives. **Reset authorization** deletes
the token and clears the local OAuth client selection and privacy acknowledgement.
The user can revoke the Google-side grant from Google Account security settings.

## Server assessment statement

The application has no capability to transmit restricted Gmail data to or through
a de-Mail, Liminal, analytics, advertising, or other third-party server. On that
architecture, Google's published assessment rule indicates the third-party-server
security-assessment trigger should not apply. Google makes the final determination
during review, and this statement must not be presented as an exemption granted in
advance.
