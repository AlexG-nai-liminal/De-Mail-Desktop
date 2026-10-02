# Google OAuth verification package

This directory contains the reviewer materials for the production de-Mail Desktop
Google Cloud project. Replace every bracketed placeholder and verify every URL
against the final build before submission.

## Submission order

1. Publish the app information and policies at `https://liminalmemory.com/de-mail`.
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
- Homepage: https://liminalmemory.com/de-mail
- Privacy: https://liminalmemory.com/de-mail#privacy
- Terms: https://liminalmemory.com/de-mail#terms
- Data deletion: https://liminalmemory.com/de-mail#delete-data
- Security: https://liminalmemory.com/de-mail#privacy

The live site uses the existing Squarespace Liminal website. Its published
rendered content is preserved in `squarespace-page.html`, including page-scoped formatting
and the privacy, terms, and deletion anchors. `public-site/` remains an alternative
standalone static-site package; its old subdomain is not the live OAuth website.

## Packaging the Desktop identity

Project: `de-mail-desktop-prod`. The local review build uses its Desktop app
client named `de-Mail Desktop Production`.

To install a downloaded Google Desktop client for a private local build:

```powershell
.venv\Scripts\python tools\configure_oauth.py "C:\path\to\downloaded-client.json"
tools\build_release.ps1
```

The configuration command validates Google's endpoints, Desktop client type,
and localhost callback before atomically replacing the ignored
`src/demail/assets/google-oauth-client.json` file. Nuitka includes the assets
directory in the frozen app. Customers then connect without selecting a JSON
file. The identity must also be supplied on a clean CI runner; it is intentionally
absent from Git, and a source-only checkout does not include it.

The app identity is distributed in the installer and is not a user access or
refresh token. A desktop client cannot keep its client secret confidential.
User credentials remain protected separately with Windows DPAPI.

As checked on October 2, 2026: Gmail API is enabled, Gmail read-only is declared,
and the audience is External / Testing with `alex@liminalmemory.com` added as a
test user. The homepage and policies are publicly reachable on Squarespace, and
Google branding changes were saved. Domain-wide Search Console ownership was
verified on October 2, 2026 using an additional DNS TXT record at Squarespace.
Public rollout still needs a real connection/archive demonstration, a change
from Testing to Production, and Google's restricted-scope verification.
Packaging an identity does not complete Google approval.

Local review installer: `de-Mail-Desktop-Setup-0.2.0.exe` (unsigned).
SHA-256: `b4a1911008d2b84420809070c6063de401b75b3f16ad7caccddcd936543aef64`.

## Official references

- [Google verification requirements](https://support.google.com/cloud/answer/13464321)
- [Restricted-scope verification](https://developers.google.com/identity/protocols/oauth2/production-readiness/restricted-scope-verification)
- [Google Workspace user data policy](https://developers.google.com/workspace/workspace-api-user-data-developer-policy)
- [Gmail messages.get](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/get)
