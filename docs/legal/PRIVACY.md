# de-Mail Desktop Privacy Policy

Effective date: September 19, 2026

de-Mail Desktop is a local Windows application published by Liminal. Questions about this
policy can be sent to alex@liminalmemory.com.

## Information the application accesses

When a person chooses to connect a Google account, de-Mail Desktop requests the
`https://www.googleapis.com/auth/gmail.readonly` scope. This permits the application to view
Gmail messages, message metadata, labels, and mailbox totals. The application cannot use this
scope to send mail, change mail, or delete mail.

## How Google user data is used

Google user data is used only to let the person select Gmail messages, save copies of those
messages as local RFC 822 `.eml` files, create a local archive manifest, and verify the saved
copies. Google user data is not used for advertising, profiling, or training machine-learning
models.

de-Mail Desktop's use and transfer of information received from Google APIs adheres to the
[Google API Services User Data Policy](https://developers.google.com/terms/api-services-user-data-policy),
including its Limited Use requirements.

## Local processing and storage

Message content is processed on the person's Windows computer. Archived messages are written
only to the folder that the person selects. de-Mail Desktop does not operate a server that
receives Gmail message content, attachments, archive manifests, OAuth credentials, or archive
destinations.

OAuth credentials are encrypted using Windows Data Protection API and stored in the current
Windows user's local application-data folder. They are sent only to Google's official OAuth
and Gmail API endpoints as required to authorize and perform the requested archive operation.

## Diagnostics

de-Mail Desktop does not send diagnostics automatically. A problem report is generated locally,
shown in full before it can leave the computer, and redacts email addresses, credentials, file
paths, `.eml` filenames, authorization headers, and long opaque identifiers. The person decides
whether to copy, save, or email it.

## Sharing and sale

Liminal does not receive, sell, rent, or share Google user data through de-Mail Desktop. The
application does not contain advertising or analytics SDKs.

## Retention and deletion

Liminal cannot retain or delete a person's Gmail data because Liminal never receives it. The
person controls every archive folder and can delete it with normal Windows file management.
The person can remove the local OAuth credential with the Disconnect or Reset authorization
control and can revoke the grant from the Google Account connections page.

## Changes

Material changes will be dated and published on the de-Mail Desktop website before a new public
release uses them.
