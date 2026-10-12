# de-Mail Desktop releases

## Repository split

`AlexG-nai-liminal/De-Mail-Desktop` is the source repository. It contains code,
tests, and the Windows build workflow.

`AlexG-nai-liminal/de-mail-desktop-releases` is the public release-only repository. It
contains release notes and these customer-facing files only:

- `de-Mail-Desktop-Setup-<version>.exe`
- `SHA256SUMS.txt`

The desktop app reads only the public repository's latest-release metadata. It does not
receive GitHub credentials, read the private repository, download an update silently, or
execute anything returned by the update service.

## One-time GitHub setup

1. Create the public repository `AlexG-nai-liminal/de-mail-desktop-releases` with a short
   README and no source code.
2. Create a fine-grained personal access token whose repository access is limited to that
   one public repository and whose only repository permission is `Contents: Read and write`.
3. Add the token to the private source repository as the Actions secret
   `DEMAIL_RELEASES_TOKEN`.
4. Obtain a Windows code-signing certificate. Export it as a password-protected PFX, Base64
   encode the PFX, and save it as the private repository secret
   `WINDOWS_SIGNING_CERTIFICATE_BASE64`. Save its password as
   `WINDOWS_SIGNING_CERTIFICATE_PASSWORD`.
5. Keep GitHub Actions permission for the private repository's workflow at `Contents: Read
   and write` so it can create the matching private release.
6. Store the validated production Desktop client JSON as the Actions secret
   `GOOGLE_DESKTOP_OAUTH_CLIENT_JSON`. The workflow validates it before packaging; it
   must never be committed to source control.
7. Set the Actions repository variable `GOOGLE_OAUTH_VERIFIED` to `true` only after
   confirming Google's final scope approval. Tagged publication fails closed while
   this is unset, false, or any required release secret is missing.

The public token cannot read the private repository. The default workflow token cannot write
to the public repository. The signing certificate is decoded only on the temporary Windows
runner and deleted before the job ends.

Source visibility was confirmed public on October 12, 2026. An encrypted Actions secret does
not make workflow artifacts private. Unsigned test installers are uploaded only when the
source repository is private. A public source repository can upload a tagged installer only
after the Google approval and signature gates have passed. Public source remains publicly
readable regardless of publishing-token permissions.

## Making a release

1. Update `CHANGELOG.md` with the customer-facing changes.
2. Advance the version with one of these commands:

   ```powershell
   .venv\Scripts\python tools\bump_version.py patch --note "Description"
   .venv\Scripts\python tools\bump_version.py minor --note "Description"
   .venv\Scripts\python tools\bump_version.py 1.0.0 --note "Description"
   ```

3. Run `tools\build_release.ps1` and inspect its setup executable and checksum.
4. Commit the release changes and push them to the private `main` branch.
5. Create and push a matching tag, such as `v0.2.0`.

The tagged workflow refuses a tag that does not exactly match the application version. It
builds from a clean runner, signs both the application and setup executable, verifies both
signatures and versions, and publishes identical assets to the private source release and the
public release-only repository.

Manual workflow runs build downloadable test artifacts but do not publish a GitHub release.
Local setup builds are intentionally unsigned and cannot be promoted by the tagged workflow.

## Clean Windows release check

Use a disposable Windows account or VM before public release. Do not perform uninstall
experiments against the owner's existing installation.

1. Install the signed setup as a standard user; verify the installed version and signature.
2. Confirm the production Google client is built in and the privacy disclosure appears before
   connection. Connect a test account and archive harmless messages, including an attachment.
3. Compare the saved originals with Gmail, inspect the manifest, and confirm all selected items
   were verified. Confirm disconnect removes the local credential.
4. Install the next release over the existing installation and confirm settings, history,
   saved archives, and account authorization survive the upgrade.
5. Uninstall and confirm user-created archives remain available. Reinstall and reconnect.

For planned 0.3, additionally pause during export and verification, resume, remove or alter a
test archive file, and verify again while disconnected from Google. Exercise a full/read-only
drive and confirm the report offers the correct recovery action. Destination checks require
at least 16 MiB free to start; they do not predict the size of every selected message.

### Status as of October 12, 2026

Google data-access verification has been submitted and is under review. The public feed
repository exists. The production Desktop identity is configured as the private Actions secret
`GOOGLE_DESKTOP_OAUTH_CLIENT_JSON`. The source repository is currently public, so manual
unsigned installer uploads are blocked. Keep preview installers local or make the source
repository private before using downloadable preview artifacts.
A trusted signing certificate and publishing token are still required by the tagged public
release workflow.
Windows Sandbox is not installed on this machine; the clean-account/VM check is still pending.
