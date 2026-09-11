import sys

import pytest

from demail.auth.dpapi import CredentialProtectionError, DpapiProtector

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows DPAPI only")


def test_dpapi_round_trip_and_ciphertext_is_not_plaintext() -> None:
    protector = DpapiProtector()
    plaintext = b"refresh-token-secret"
    try:
        ciphertext = protector.protect(plaintext)
    except CredentialProtectionError as error:
        if error.errno == 2:
            pytest.skip("The isolated Windows account has no DPAPI profile key")
        raise
    assert plaintext not in ciphertext
    assert protector.unprotect(ciphertext) == plaintext


def test_dpapi_rejects_malformed_ciphertext() -> None:
    with pytest.raises(CredentialProtectionError):
        DpapiProtector().unprotect(b"not a DPAPI blob")
