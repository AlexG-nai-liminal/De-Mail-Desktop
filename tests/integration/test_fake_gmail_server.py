import base64
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from demail.domain.selection import SelectionCriteria
from demail.gmail.client import GmailApiError, GmailClient


class Token:
    def access_token(self) -> str:
        return "test-token"


@pytest.fixture
def fake_gmail_server():
    requests: list[tuple[str, dict[str, list[str]], str | None]] = []
    message = b"From: sender@example.com\r\nSubject: Archive me\r\n\r\nExact bytes"
    raw = base64.urlsafe_b64encode(message).decode().rstrip("=")

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            requests.append((parsed.path, query, self.headers.get("Authorization")))
            if parsed.path.endswith("/profile"):
                self.send_json(
                    {
                        "emailAddress": "archive@example.com",
                        "messagesTotal": 3,
                        "threadsTotal": 2,
                    }
                )
            elif parsed.path.endswith("/messages"):
                if query.get("pageToken") == ["page-2"]:
                    self.send_json({"messages": [{"id": "c"}]})
                else:
                    self.send_json(
                        {
                            "messages": [{"id": "a"}, {"id": "b"}],
                            "nextPageToken": "page-2",
                        }
                    )
            elif parsed.path.endswith("/messages/interrupted"):
                body = b'{"id":"interrupted","raw":"' + raw.encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body) + 100))
                self.end_headers()
                self.wfile.write(body)
                self.wfile.flush()
                self.connection.close()
            elif "/messages/" in parsed.path:
                message_id = parsed.path.rsplit("/", 1)[1]
                self.send_json({"id": message_id, "raw": raw})
            else:
                self.send_error(404)

        def send_json(self, document: object) -> None:
            body = json.dumps(document).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            for index in range(0, len(body), 7):
                self.wfile.write(body[index : index + 7])

        def log_message(self, format: str, *args: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, requests, message
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_real_http_pagination_profile_and_streaming_download(
    fake_gmail_server, tmp_path: Path
) -> None:
    server, requests, message = fake_gmail_server
    base_url = f"http://127.0.0.1:{server.server_port}/gmail/v1"
    gmail = GmailClient(Token(), base_url=base_url, sleeper=lambda _: None)
    assert gmail.profile().email_address == "archive@example.com"
    selection = gmail.resolve_selection(SelectionCriteria(search_query="has:attachment"))
    assert selection.exact_count == 3
    final = tmp_path / "a.eml"
    archived = gmail.download_raw("a", final)
    assert archived.file.byte_size == len(message)
    assert final.read_bytes() == message
    assert all(authorization == "Bearer test-token" for _, _, authorization in requests)
    assert requests[-1][1]["format"] == ["raw"]


def test_interrupted_http_body_never_publishes_final_file(
    fake_gmail_server, tmp_path: Path
) -> None:
    server, _, _ = fake_gmail_server
    gmail = GmailClient(
        Token(),
        base_url=f"http://127.0.0.1:{server.server_port}/gmail/v1",
        sleeper=lambda _: None,
    )
    final = tmp_path / "interrupted.eml"
    with pytest.raises(GmailApiError, match="interrupted"):
        gmail.download_raw("interrupted", final)
    assert not final.exists()
    assert not final.with_name("interrupted.eml.partial").exists()

