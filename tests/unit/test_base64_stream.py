import base64
import io
import random

import pytest

from demail.archive.base64_stream import Base64DecodeError, Base64UrlDecoder


def decode(encoded: str, buffer_size: int = 8192) -> bytes:
    output = io.BytesIO()
    decoder = Base64UrlDecoder(output, buffer_size)
    decoder.write(encoded)
    decoder.finish()
    return output.getvalue()


def test_decodes_url_and_standard_alphabets() -> None:
    original = bytes(range(256))
    assert decode(base64.urlsafe_b64encode(original).decode().rstrip("=")) == original
    assert decode(base64.b64encode(original).decode()) == original


@pytest.mark.parametrize("length", range(17))
def test_every_remainder_length(length: int) -> None:
    original = bytes((index * 7) % 256 for index in range(length))
    encoded = base64.urlsafe_b64encode(original).decode().rstrip("=")
    assert decode(encoded) == original


def test_chunk_boundaries_do_not_change_output() -> None:
    original = random.Random(7).randbytes(50_000)
    encoded = base64.urlsafe_b64encode(original).decode().rstrip("=")
    output = io.BytesIO()
    decoder = Base64UrlDecoder(output, buffer_size=17)
    index = 0
    width = 1
    while index < len(encoded):
        decoder.write(encoded[index : index + width])
        index += width
        width = 1 if width >= 13 else width + 3
    decoder.finish()
    assert output.getvalue() == original


def test_whitespace_and_valid_padding_are_accepted() -> None:
    encoded = base64.urlsafe_b64encode(b"Subject: hi\r\n\r\nbody").decode()
    wrapped = "\r\n".join(encoded[index : index + 4] for index in range(0, len(encoded), 4))
    assert decode(wrapped) == b"Subject: hi\r\n\r\nbody"


@pytest.mark.parametrize("encoded", ["aGVsbG8%%%", "A", "Zh", "Zg=", "Zg===", "Zg==A"])
def test_malformed_input_is_rejected(encoded: str) -> None:
    with pytest.raises(Base64DecodeError):
        decode(encoded)


def test_finish_is_idempotent_but_writing_after_finish_is_rejected() -> None:
    output = io.BytesIO()
    decoder = Base64UrlDecoder(output)
    decoder.write("aGk")
    decoder.finish()
    decoder.finish()
    assert output.getvalue() == b"hi"
    with pytest.raises(RuntimeError, match="finished"):
        decoder.write("aA")
