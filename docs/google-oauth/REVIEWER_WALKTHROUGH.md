# Reviewer walkthrough

## Review environment

- Windows 10 or Windows 11
- Review build: `[SIGNED_INSTALLER_FILENAME]`
- SHA-256: `[INSTALLER_SHA256]`
- Test Google account: `[REVIEW_ACCOUNT]`
- Build version: `[VERSION]`

The reviewer account should contain several harmless test messages, at least one
attachment, more than one date range, and at least two labels.

## Walkthrough

1. Install and open de-Mail Desktop.
2. Select **Archive Gmail** and choose **Connect Google account**.
3. Observe the in-product disclosure explaining read-only access, local processing,
   local destination storage, and disconnection. Choose **Continue to Google**.
4. In the system browser, select the review account and grant only Gmail read-only
   access. Return to de-Mail.
5. Confirm that the connected account address is visible in Archive Gmail and in
   Settings.
6. Choose a small date range or label and calculate the exact message count.
7. Select a temporary local destination and begin the archive.
8. Observe retrieval, local writing, and file verification progress.
9. Open the destination and confirm that `.eml` files and the manifest were created.
10. In Settings, choose **Disconnect Google account**. Confirm that the account is
    disconnected while the archive remains untouched.
11. Reconnect, then choose **Reset authorization**. Confirm that the app returns to
    the first-run authorization state and does not delete the archive.
12. Optionally revoke de-Mail in the Google Account third-party access page.

## Expected network behavior

During archiving, Google API traffic is sent over HTTPS to Google endpoints. The
application does not upload Gmail data to a Liminal or de-Mail service. Update
checks retrieve public release metadata and never include Google user data.

## Diagnostics check

Open **Report a problem** and generate a diagnostic report. The report contains
operational status only. It must not contain message subjects, bodies, attachments,
OAuth credentials, full account addresses, or archive file paths.
