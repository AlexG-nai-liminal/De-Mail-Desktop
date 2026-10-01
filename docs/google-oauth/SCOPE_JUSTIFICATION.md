# Scope justification

## Requested scope

`https://www.googleapis.com/auth/gmail.readonly`

de-Mail Desktop is a user-directed Windows email backup and archive application.
The user chooses which Gmail messages to preserve and selects a local destination.
The application retrieves each selected message in its original RFC-formatted form,
writes it to that destination, and verifies the saved bytes. This is an approved
use case under Google's category for applications that automatically back up email.

The scope is used for these visible features only:

- Read the account profile to show which Google account is connected.
- List message identifiers matching the user's selected dates, labels, senders,
  or archive portions.
- Read label names for the selection interface.
- Retrieve each selected message with `users.messages.get` and `format=raw`.
- Save and verify the resulting message locally at the user's chosen destination.

de-Mail does not send, modify, delete, label, forward, or change any Gmail data.
It does not request `gmail.modify` or the full `mail.google.com` scope.

## Why a narrower scope is insufficient

`gmail.metadata` is not sufficient. A complete portable archive needs the original
message body, MIME structure, headers, and attachments. Google's Gmail resource
documentation states that the `raw` field is the entire RFC-formatted message and
is returned for `format=raw`. Metadata format is limited to message metadata and
selected headers; it cannot provide the complete message content required for a
restorable `.eml` archive.

The `users.messages.get` reference permits `gmail.readonly` for this operation.
It also lists broader scopes, but those would grant modification or full mailbox
access that de-Mail neither needs nor uses. Therefore `gmail.readonly` is the
least-privilege scope that can retrieve complete messages without modification.

## Data handling

Gmail data travels directly from Google's HTTPS API to the user's Windows device.
It is processed locally and written only to the destination the user selected.
No Gmail message data, headers, attachments, access tokens, or refresh tokens are
sent to de-Mail, Liminal, analytics providers, or another third-party server.

The local OAuth token is encrypted at rest using Windows Data Protection API for
the current Windows user. The user can delete it through Disconnect Google account
or Reset authorization. The user can separately revoke the grant in their Google
Account security settings.

Use of information received from Google Workspace APIs adheres to the Google API
Services User Data Policy, including the Limited Use requirements.
