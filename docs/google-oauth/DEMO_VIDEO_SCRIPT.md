# Demonstration video script

Record one continuous, unedited-enough-to-follow desktop capture. Keep the browser
address bar, app title, and important clicks visible. Do not expose real personal
mail; use the dedicated review account.

## Recording sequence

1. Show the public homepage, privacy policy, security page, and data-deletion page.
2. Show the production Google Cloud project name and OAuth brand. Briefly show that
   Gmail API is enabled and that the only declared Gmail scope is `gmail.readonly`.
3. Launch the exact Windows build supplied to Google.
4. Click **Connect Google account** and pause on the first-run privacy disclosure.
5. Continue into Google's OAuth flow. Keep the consent screen and requested scope
   visible long enough to read.
   Google requires the expected unverified-app screen to be shown in the recording.
   The account owner must handle that screen and approve Gmail access themselves.
6. Return to de-Mail and show the connected review account.
7. Select a small set containing a plain message and a message with an attachment.
8. Choose an empty local folder, archive the selection, and allow verification to
   complete.
9. Open the local folder and show the resulting `.eml` files and manifest without
   opening private content.
10. Return to Settings and show the privacy and scope explanation.
11. Click **Disconnect Google account** and demonstrate that local archive files
    remain.
12. Reconnect, click **Reset authorization**, and demonstrate the first-run state.
13. End by showing the Google Account access-revocation location and the public
    deletion instructions.

## Spoken summary

“de-Mail Desktop uses Gmail read-only access to create user-directed local email
archives. Complete RFC-formatted messages require message bodies and attachments,
which metadata-only access cannot provide. Gmail data moves directly from Google
to the user's selected local folder and is never transmitted to de-Mail or Liminal
servers. The application cannot modify or delete Gmail messages.”

## Before uploading

- Blur unrelated account identifiers and notifications.
- Verify the video link is accessible to Google's reviewers.
- Confirm the video shows the same OAuth client, branding, scope, and executable
  submitted for review.
- Put the final video URL in `[DEMO_VIDEO_URL]` in the submission checklist.
- Upload to YouTube as **Unlisted**, then provide that URL in Google's scope-review
  form. The form cannot save the intended-use category and justification until
  this required video link is supplied. Do not use a placeholder or a simulated
  app demonstration.
