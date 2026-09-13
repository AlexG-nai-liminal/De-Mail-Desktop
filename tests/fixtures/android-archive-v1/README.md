# Android archive schema v1 fixture

This synthetic archive contains no real mailbox data. It exercises the shared Android and Windows
manifest contract, RFC 822 header extraction, embedded MIME attachments, relative paths, byte
counts, and SHA-256 verification.

If the EML payload changes, regenerate its byte size and digest in `manifest.json` and run the
compatibility tests before committing the fixture.
