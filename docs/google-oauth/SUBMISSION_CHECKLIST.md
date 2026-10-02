# OAuth submission checklist

## Identity and public pages

- [ ] Homepage reviewed and approved by the product owner
- [x] Homepage publicly reachable without login: https://liminalmemory.com/de-mail
- [x] Homepage does not redirect to another domain
- [x] Privacy policy linked from homepage and OAuth brand
- [x] Terms, security, and data-deletion sections reachable
- [x] `liminalmemory.com` verified in Google Search Console via DNS TXT on October 2, 2026
- [ ] Support and developer contact email monitored

## Google Cloud production project

- [ ] Separate from development, testing, and Android development projects
- [ ] Production project owners and editors reviewed
- [x] Gmail API enabled
- [x] App name is `de-Mail Desktop`
- [ ] Production monochrome icon uploaded
- [x] User type is External; audience In production after explicit approval on October 2, 2026
- [x] Only `https://www.googleapis.com/auth/gmail.readonly` declared
- [x] Branding published and brand verification complete on October 2, 2026
- [x] Desktop OAuth client created for production: de-Mail Desktop Production
- [ ] Unused or development OAuth clients absent from the production project

## Review build

- [x] Production OAuth client embedded during the private build process
- [ ] OAuth client JSON absent from Git history and release source files
- [ ] Installer Authenticode-signed
- [ ] Installer tested in a clean Windows account or virtual machine
- [ ] First-run disclosure appears before OAuth
- [ ] Disconnect and Reset authorization tested
- [ ] Diagnostics inspected for content and credentials
- [x] Version: `0.2.0`
- [x] Local unsigned review installer: `de-Mail-Desktop-Setup-0.2.0.exe`
- [x] SHA-256: `b4a1911008d2b84420809070c6063de401b75b3f16ad7caccddcd936543aef64`

## Reviewer submission

- [x] Scope justification entered in review form; unsaved until required demo URL is supplied
- [ ] Demo video follows the supplied script
- [ ] Demo video URL: `[DEMO_VIDEO_URL]`
- [ ] Reviewer account and instructions supplied if Google requests them
- [ ] Archive workflow and local-only storage explained
- [ ] Narrower-scope evidence supplied
- [ ] Final submission details checked by the product owner
- [ ] Explicit approval obtained immediately before **Submit for Verification**

## Post-submission

- [ ] Review mailbox monitored
- [ ] Reviewer questions and requested changes tracked
- [ ] No public installer released before approval
- [ ] Production OAuth client made default only in approved signed releases
