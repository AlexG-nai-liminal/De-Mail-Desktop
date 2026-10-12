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

- [x] Scope justification and demo URL saved in the review form on October 2, 2026
- [x] Demo video recorded, edited, and uploaded unlisted
- [x] Demo video URL: https://youtu.be/08roaCv6p34
- [ ] Reviewer account and instructions supplied if Google requests them
- [ ] Archive workflow and local-only storage explained
- [ ] Narrower-scope evidence supplied
- [x] Final submission details checked with the product owner on October 12, 2026
- [x] Explicit approval obtained immediately before **Submit for Verification** on October 12
- [x] Submission completed; Google Verification Center reports data access **under review**

## Post-submission

- [ ] Review mailbox monitored
- [ ] Reviewer questions and requested changes tracked
- [ ] No public installer released before approval
- [ ] Production OAuth client made default only in approved signed releases

## Release status checked October 12, 2026

- Public release-only repository exists.
- Production Desktop identity configured as private Actions secret
  `GOOGLE_DESKTOP_OAUTH_CLIENT_JSON` with explicit owner approval on October 12.
- Signing and public publishing credentials still need configuration before a tagged release.
- Google Cloud reports branding verified and data access under review after submission on
  October 12, 2026. Final scope approval is pending.
- The private local 0.2.0 installer was rebuilt October 3. Its current checksum is in
  `dist/installer/SHA256SUMS.txt`; the October 2 hash above identifies the earlier review build.
