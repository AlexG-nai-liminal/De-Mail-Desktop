from __future__ import annotations

from dataclasses import dataclass
from email.header import decode_header, make_header
from email.message import Message
from pathlib import Path


@dataclass(frozen=True, slots=True)
class EmlScan:
    subject: str | None = None
    sender: str | None = None
    recipients: str | None = None
    cc_recipients: str | None = None
    bcc_recipients: str | None = None
    date_header: str | None = None
    rfc822_message_id: str | None = None
    attachment_count: int = 0
    inline_attachment_count: int = 0
    attachment_names: tuple[str, ...] = ()
    truncated_line_count: int = 0
    truncated_header_count: int = 0


class EmlScanner:
    """Incrementally extract bounded metadata without materializing an EML file."""

    def __init__(
        self,
        *,
        max_line_length: int = 8 * 1024,
        max_headers: int = 256,
        max_attachment_names: int = 200,
    ) -> None:
        if min(max_line_length, max_headers, max_attachment_names) <= 0:
            raise ValueError("EML scanner limits must be positive.")
        self.max_line_length = max_line_length
        self.max_headers = max_headers
        self.max_attachment_names = max_attachment_names
        self._line = bytearray()
        self._line_truncated = False
        self._truncated_lines = 0
        self._truncated_headers = 0
        self._state = "top_headers"
        self._headers: list[tuple[str, str]] = []
        self._boundaries: list[bytes] = []
        self._top: dict[str, str] = {}
        self._attachments = 0
        self._inline_attachments = 0
        self._attachment_names: list[str] = []
        self._finished = False

    def write(self, data: bytes | bytearray) -> None:
        if self._finished:
            raise RuntimeError("The EML scan is already finished.")
        for value in data:
            if value == 10:
                self._accept_line()
            elif len(self._line) < self.max_line_length:
                self._line.append(value)
            elif not self._line_truncated:
                self._line_truncated = True
                self._truncated_lines += 1

    def finish(self) -> EmlScan:
        if not self._finished:
            if self._line or self._line_truncated:
                self._accept_line()
            if self._state in {"top_headers", "part_headers"}:
                self._finish_headers()
            self._finished = True
        return EmlScan(
            subject=self._top.get("subject"),
            sender=self._top.get("from"),
            recipients=self._top.get("to"),
            cc_recipients=self._top.get("cc"),
            bcc_recipients=self._top.get("bcc"),
            date_header=self._top.get("date"),
            rfc822_message_id=self._top.get("message-id"),
            attachment_count=self._attachments,
            inline_attachment_count=self._inline_attachments,
            attachment_names=tuple(self._attachment_names),
            truncated_line_count=self._truncated_lines,
            truncated_header_count=self._truncated_headers,
        )

    def _accept_line(self) -> None:
        line = bytes(self._line)
        if line.endswith(b"\r"):
            line = line[:-1]
        self._line.clear()
        self._line_truncated = False
        if self._state in {"top_headers", "part_headers"}:
            if not line:
                self._finish_headers()
            else:
                self._add_header_line(line)
            return
        self._accept_body_line(line)

    def _add_header_line(self, line: bytes) -> None:
        text = line.decode("utf-8", errors="replace")
        if text[:1] in {" ", "\t"} and self._headers:
            name, value = self._headers[-1]
            self._headers[-1] = (name, f"{value} {text.strip()}")
            return
        if len(self._headers) >= self.max_headers:
            self._truncated_headers += 1
            return
        name, separator, value = text.partition(":")
        if separator and name.strip():
            self._headers.append((name.strip().lower(), value.strip()))

    def _finish_headers(self) -> None:
        message = Message()
        for name, value in self._headers:
            message[name] = value
        if self._state == "top_headers":
            for name in ("subject", "from", "to", "cc", "bcc", "date", "message-id"):
                value = message.get(name)
                if value is not None:
                    self._top[name] = _decode_header(value)
        content_type = message.get_content_type()
        disposition = message.get_content_disposition()
        filename = message.get_filename()
        is_multipart = content_type.startswith("multipart/")
        if self._state == "part_headers" and not is_multipart:
            if disposition == "inline" and filename:
                self._inline_attachments += 1
                self._remember_name(filename)
            elif disposition == "attachment" or filename:
                self._attachments += 1
                if filename:
                    self._remember_name(filename)
        boundary = message.get_boundary() if is_multipart else None
        if boundary:
            self._boundaries.append(boundary.encode("utf-8", errors="replace"))
        self._headers.clear()
        self._state = "body"

    def _accept_body_line(self, line: bytes) -> None:
        for index in range(len(self._boundaries) - 1, -1, -1):
            marker = b"--" + self._boundaries[index]
            if line == marker:
                del self._boundaries[index + 1 :]
                self._headers.clear()
                self._state = "part_headers"
                return
            if line == marker + b"--":
                del self._boundaries[index:]
                return

    def _remember_name(self, value: str) -> None:
        if len(self._attachment_names) < self.max_attachment_names:
            self._attachment_names.append(_decode_header(value))


def _decode_header(value: str) -> str:
    try:
        return str(make_header(decode_header(value))).strip()
    except (LookupError, UnicodeError, ValueError):
        return value.strip()


def scan_eml(path: Path, *, chunk_size: int = 64 * 1024) -> EmlScan:
    if chunk_size <= 0:
        raise ValueError("EML scan chunk size must be positive.")
    scanner = EmlScanner()
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            scanner.write(chunk)
    return scanner.finish()
