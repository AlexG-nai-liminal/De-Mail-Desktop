# Google OAuth verification package

This directory contains the reviewer materials for the production de-Mail Desktop
Google Cloud project. Replace every bracketed placeholder and verify every URL
against the final build before submission.

## Submission order

1. Publish the approved site at `https://de-mail.liminalmemory.com`.
2. Verify `liminalmemory.com` ownership in Google Search Console using a project
   owner or editor account.
3. Configure the separate production Google Cloud project and enable Gmail API.
4. Publish and verify the OAuth brand.
5. Declare only `https://www.googleapis.com/auth/gmail.readonly`.
6. Create the Desktop OAuth client and inject it into the signed review build.
7. Record the demonstration using the script in this directory.
8. Submit restricted-scope verification and answer reviewer questions.

## Required materials

- [Scope justification](SCOPE_JUSTIFICATION.md)
- [Reviewer walkthrough](REVIEWER_WALKTHROUGH.md)
- [Demonstration video script](DEMO_VIDEO_SCRIPT.md)
- [Local security model](LOCAL_SECURITY_MODEL.md)
- [Submission checklist](SUBMISSION_CHECKLIST.md)

## Production identity

- App: de-Mail Desktop
- Publisher: Liminal
- Support: alex@liminalmemory.com
- Homepage: https://de-mail.liminalmemory.com
- Privacy: https://de-mail.liminalmemory.com/privacy.html
- Terms: https://de-mail.liminalmemory.com/terms.html
- Data deletion: https://de-mail.liminalmemory.com/delete-data.html
- Security: https://de-mail.liminalmemory.com/security.html

## Official references

- [Google verification requirements](https://support.google.com/cloud/answer/13464321)
- [Restricted-scope verification](https://developers.google.com/identity/protocols/oauth2/production-readiness/restricted-scope-verification)
- [Google Workspace user data policy](https://developers.google.com/workspace/workspace-api-user-data-developer-policy)
- [Gmail messages.get](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/get)
