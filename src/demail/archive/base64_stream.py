"""Incremental base64url decoding for Gmail raw-message bodies."""

from typing import BinaryIO


class Base64DecodeError(ValueError):
    pass


class Base64UrlDecoder:
    """Decode base64url text incrementally into a binary stream."""

    _ALPHABET = {
        **{chr(code): code - ord("A") for code in range(ord("A"), ord("Z") + 1)},
        **{chr(code): code - ord("a") + 26 for code in range(ord("a"), ord("z") + 1)},
        **{chr(code): code - ord("0") + 52 for code in range(ord("0"), ord("9") + 1)},
        "-": 62,
        "+": 62,
        "_": 63,
        "/": 63,
    }

    def __init__(self, target: BinaryIO, buffer_size: int = 8192) -> None:
        if buffer_size <= 0:
            raise ValueError("buffer_size must be positive")
        self._target = target
        self._buffer_size = buffer_size
        self._buffer = bytearray()
        self._accumulator = 0
        self._sextets = 0
        self._data_characters = 0
        self._padding = 0
        self._finished = False

    def write(self, text: str) -> None:
        if self._finished:
            raise RuntimeError("Decoder already finished")
        for character in text:
            if character in "\r\n\t ":
                continue
            if character == "=":
                self._padding += 1
                if self._padding > 2:
                    raise Base64DecodeError("Invalid base64 padding in Gmail message body")
                continue
            if self._padding:
                raise Base64DecodeError("Base64 data follows padding in Gmail message body")
            try:
                value = self._ALPHABET[character]
            except KeyError as error:
                raise Base64DecodeError(
                    f"Invalid base64 character U+{ord(character):04X} in Gmail message body"
                ) from error
            self._accumulator = (self._accumulator << 6) | value
            self._sextets += 1
            self._data_characters += 1
            if self._sextets == 4:
                self._append(
                    bytes(
                        (
                            (self._accumulator >> 16) & 0xFF,
                            (self._accumulator >> 8) & 0xFF,
                            self._accumulator & 0xFF,
                        )
                    )
                )
                self._accumulator = 0
                self._sextets = 0

    def finish(self) -> None:
        if self._finished:
            return
        self._finished = True
        remainder = self._data_characters % 4
        expected_padding = {0: 0, 2: 2, 3: 1}.get(remainder)
        if expected_padding is None or self._padding not in (0, expected_padding):
            raise Base64DecodeError("Invalid base64 length or padding in Gmail message body")
        if self._sextets == 2:
            if self._accumulator & 0x0F:
                raise Base64DecodeError("Nonzero trailing bits in Gmail message body")
            self._append(bytes(((self._accumulator >> 4) & 0xFF,)))
        elif self._sextets == 3:
            if self._accumulator & 0x03:
                raise Base64DecodeError("Nonzero trailing bits in Gmail message body")
            self._append(bytes(((self._accumulator >> 10) & 0xFF, (self._accumulator >> 2) & 0xFF)))
        self._flush()

    def _append(self, data: bytes) -> None:
        self._buffer.extend(data)
        if len(self._buffer) >= self._buffer_size:
            self._flush()

    def _flush(self) -> None:
        if self._buffer:
            self._target.write(self._buffer)
            self._buffer.clear()

