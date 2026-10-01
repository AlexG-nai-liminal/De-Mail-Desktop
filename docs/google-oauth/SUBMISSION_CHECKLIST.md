# OAuth submission checklist

## Identity and public pages

- [ ] Homepage reviewed and approved by the product owner
- [ ] Homepage publicly reachable without login
- [ ] Homepage does not redirect to another domain
- [ ] Privacy policy linked from homepage and OAuth brand
- [ ] Terms, security, and data-deletion pages reachable
- [ ] `liminalmemory.com` verified in Google Search Console
- [ ] Support and developer contact email monitored

## Google Cloud production project

- [ ] Separate from development, testing, and Android development projects
- [ ] Production project owners and editors reviewed
- [ ] Gmail API enabled
- [ ] App name is `de-Mail Desktop`
- [ ] Production monochrome icon uploaded
- [ ] User type is External
- [ ] Only `https://www.googleapis.com/auth/gmail.readonly` declared
- [ ] Branding published and brand verification complete
- [ ] Desktop OAuth client created for production
- [ ] Unused or development OAuth clients absent from the production project

## Review build

- [ ] Production OAuth client embedded during the private build process
- [ ] OAuth client JSON absent from Git history and release source files
- [ ] Installer Authenticode-signed
- [ ] Installer tested in a clean Windows account or virtual machine
- [ ] First-run disclosure appears before OAuth
- [ ] Disconnect and Reset authorization tested
- [ ] Diagnostics inspected for content and credentials
- [ ] Version: `[VERSION]`
- [ ] Installer: `[SIGNED_INSTALLER_FILENAME]`
- [ ] SHA-256: `[INSTALLER_SHA256]`

## Reviewer submission

- [ ] Scope justification pasted without changing technical meaning
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
