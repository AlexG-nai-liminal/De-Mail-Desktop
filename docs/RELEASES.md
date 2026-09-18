# de-Mail Desktop releases

## Repository split

`AlexG-nai-liminal/De-Mail-Desktop` is the private source repository. It contains code,
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

The public token cannot read the private repository. The default workflow token cannot write
to the public repository. The signing certificate is decoded only on the temporary Windows
runner and deleted before the job ends.

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
