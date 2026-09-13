"""Bounded-memory reader for Gmail `format=raw` JSON responses."""

from dataclasses import dataclass
from typing import BinaryIO, TextIO

from demail.archive.base64_stream import Base64UrlDecoder


class GmailResponseError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class RawMessageEnvelope:
    id: str | None
    thread_id: str | None
    internal_date_ms: int | None
    size_estimate: int | None
    history_id: str | None
    snippet: str | None
    label_ids: tuple[str, ...]
    raw_present: bool


class _Chars:
    def __init__(self, source: TextIO, chunk_size: int = 8192) -> None:
        self.source = source
        self.chunk_size = chunk_size
        self.buffer = ""
        self.position = 0

    def peek(self) -> str:
        if self.position >= len(self.buffer):
            self.buffer = self.source.read(self.chunk_size)
            self.position = 0
        return self.buffer[self.position] if self.position < len(self.buffer) else ""

    def read(self) -> str:
        character = self.peek()
        if character:
            self.position += 1
        return character

    def whitespace(self) -> None:
        while self.peek() in " \r\n\t" and self.peek():
            self.read()

    def expect(self, expected: str) -> None:
        actual = self.read()
        if actual != expected:
            found = "end of response" if not actual else repr(actual)
            raise GmailResponseError(
                f"Malformed Gmail response: expected {expected!r}, found {found}"
            )

    def string(self) -> str:
        self.expect('"')
        output: list[str] = []
        while character := self.read():
            if character == '"':
                return "".join(output)
            if character == "\\":
                output.append(self.escape())
            else:
                output.append(character)
        raise GmailResponseError("Malformed Gmail response: unterminated string")

    def stream_raw_string(self, target: BinaryIO) -> None:
        self.expect('"')
        decoder = Base64UrlDecoder(target)
        chunk: list[str] = []
        while character := self.read():
            if character == '"':
                if chunk:
                    decoder.write("".join(chunk))
                decoder.finish()
                return
            if character == "\\":
                raise GmailResponseError("Unexpected escape sequence in base64 message body")
            chunk.append(character)
            if len(chunk) == 8192:
                decoder.write("".join(chunk))
                chunk.clear()
        raise GmailResponseError("Malformed Gmail response: unterminated message body")

    def scalar(self) -> str | None:
        self.whitespace()
        if self.peek() == '"':
            return self.string()
        if self.peek() in "[{":
            self.skip_value()
            return None
        token = self.bare()
        return None if token == "null" else token

    def string_array(self) -> tuple[str, ...]:
        self.whitespace()
        if self.peek() != "[":
            self.skip_value()
            return ()
        self.expect("[")
        values: list[str] = []
        self.whitespace()
        if self.peek() == "]":
            self.read()
            return ()
        while True:
            self.whitespace()
            if self.peek() == '"':
                values.append(self.string())
            else:
                self.skip_value()
            self.whitespace()
            separator = self.read()
            if separator == "]":
                return tuple(values)
            if separator != ",":
                raise GmailResponseError("Malformed Gmail response: invalid array separator")

    def skip_value(self) -> None:
        self.whitespace()
        if self.peek() == '"':
            self.string()
        elif self.peek() == "{":
            self.skip_container("{", "}")
        elif self.peek() == "[":
            self.skip_container("[", "]")
        else:
            self.bare()

    def skip_container(self, opening: str, closing: str) -> None:
        self.expect(opening)
        depth = 1
        while depth:
            character = self.peek()
            if not character:
                raise GmailResponseError("Malformed Gmail response: unterminated container")
            if character == '"':
                self.string()
            else:
                character = self.read()
                if character == opening:
                    depth += 1
                elif character == closing:
                    depth -= 1

    def bare(self) -> str:
        output: list[str] = []
        while (character := self.peek()) and character not in ",}] \r\n\t":
            output.append(self.read())
        if not output:
            raise GmailResponseError("Malformed Gmail response: empty value")
        return "".join(output)

    def escape(self) -> str:
        character = self.read()
        simple = {
            '"': '"',
            "\\": "\\",
            "/": "/",
            "b": "\b",
            "f": "\f",
            "n": "\n",
            "r": "\r",
            "t": "\t",
        }
        if character in simple:
            return simple[character]
        if character != "u":
            raise GmailResponseError("Malformed Gmail response: invalid escape")
        digits = "".join(self.read() for _ in range(4))
        if len(digits) != 4:
            raise GmailResponseError("Malformed Gmail response: truncated unicode escape")
        try:
            return chr(int(digits, 16))
        except ValueError as error:
            raise GmailResponseError("Malformed Gmail response: bad unicode escape") from error


def _integer(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def read_raw_message(source: TextIO, raw_target: BinaryIO) -> RawMessageEnvelope:
    lexer = _Chars(source)
    values: dict[str, object] = {"labelIds": (), "raw": False}
    seen_fields: set[str] = set()
    lexer.whitespace()
    lexer.expect("{")
    lexer.whitespace()
    if lexer.peek() == "}":
        lexer.read()
    else:
        while True:
            lexer.whitespace()
            key = lexer.string()
            if key in seen_fields:
                raise GmailResponseError(f"Malformed Gmail response: duplicate {key} field")
            seen_fields.add(key)
            lexer.whitespace()
            lexer.expect(":")
            lexer.whitespace()
            if key == "raw":
                values["raw"] = True
                lexer.stream_raw_string(raw_target)
            elif key == "labelIds":
                values[key] = lexer.string_array()
            elif key in {"id", "threadId", "internalDate", "sizeEstimate", "historyId", "snippet"}:
                values[key] = lexer.scalar()
            else:
                lexer.skip_value()
            lexer.whitespace()
            separator = lexer.read()
            if separator == "}":
                break
            if separator != ",":
                raise GmailResponseError("Malformed Gmail response: invalid object separator")
    lexer.whitespace()
    if lexer.peek():
        raise GmailResponseError("Malformed Gmail response: trailing content")
    internal_date = values.get("internalDate")
    size_estimate = values.get("sizeEstimate")
    return RawMessageEnvelope(
        id=values.get("id") if isinstance(values.get("id"), str) else None,
        thread_id=values.get("threadId") if isinstance(values.get("threadId"), str) else None,
        internal_date_ms=_integer(internal_date if isinstance(internal_date, str) else None),
        size_estimate=_integer(size_estimate if isinstance(size_estimate, str) else None),
        history_id=values.get("historyId") if isinstance(values.get("historyId"), str) else None,
        snippet=values.get("snippet") if isinstance(values.get("snippet"), str) else None,
        label_ids=values["labelIds"] if isinstance(values["labelIds"], tuple) else (),
        raw_present=bool(values["raw"]),
    )
