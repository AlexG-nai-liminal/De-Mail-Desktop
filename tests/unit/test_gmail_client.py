import base64
import json
from pathlib import Path

import httpx
import pytest

from demail.domain.selection import SelectionCriteria
from demail.gmail.client import GmailApiError, GmailClient


class Token:
    def access_token(self) -> str:
        return "access-secret"


def client(handler, *, max_attempts: int = 3, sleeper=lambda _: None) -> GmailClient:
    transport = httpx.MockTransport(handler)
    return GmailClient(
        Token(),
        client=httpx.Client(transport=transport),
        max_attempts=max_attempts,
        sleeper=sleeper,
    )


def test_profile_and_labels_validate_response_shapes() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/profile"):
            return httpx.Response(
                200,
                json={
                    "emailAddress": "someone@gmail.com",
                    "messagesTotal": 42,
                    "threadsTotal": 30,
                    "historyId": "9",
                },
            )
        return httpx.Response(
            200, json={"labels": [{"id": "INBOX", "name": "Inbox", "type": "system"}]}
        )

    gmail = client(handler)
    assert gmail.profile().messages_total == 42
    assert gmail.labels()[0].id == "INBOX"


def test_exact_selection_walks_every_page_and_passes_query_options() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.params.get("pageToken") == "next":
            return httpx.Response(200, json={"messages": [{"id": "c", "threadId": "tc"}]})
        return httpx.Response(
            200,
            json={
                "messages": [{"id": "a"}, {"id": "b", "threadId": "tb"}],
                "nextPageToken": "next",
                "resultSizeEstimate": 999_999,
            },
        )

    result = client(handler).resolve_selection(
        SelectionCriteria(
            sender="alice@example.com",
            label_id="Label_1",
            include_spam_and_trash=True,
        )
    )
    assert result.exact_count == 3
    assert [message.id for message in result.messages] == ["a", "b", "c"]
    assert len(requests) == 2
    assert requests[0].url.params.get("maxResults") == "500"
    assert requests[0].url.params.get("q") == "from:alice@example.com"
    assert requests[0].url.params.get("labelIds") == "Label_1"
    assert requests[0].url.params.get("includeSpamTrash") == "true"


def test_manual_selection_makes_no_http_request() -> None:
    def forbidden(_: httpx.Request) -> httpx.Response:
        raise AssertionError("manual selection must not call Gmail list")

    result = client(forbidden).resolve_selection(
        SelectionCriteria(explicit_message_ids=("b", "a"))
    )
    assert [message.id for message in result.messages] == ["b", "a"]


def test_recent_candidates_apply_filters_and_load_metadata() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/messages"):
            return httpx.Response(200, json={"messages": [{"id": "message-1"}]})
        return httpx.Response(
            200,
            json={
                "id": "message-1",
                "threadId": "thread-1",
                "internalDate": "1234",
                "labelIds": ["Label_1"],
                "payload": {
                    "headers": [
                        {"name": "Subject", "value": "A receipt"},
                        {"name": "From", "value": "shop@example.com"},
                    ]
                },
            },
        )

    result = client(handler).recent_messages(
        SelectionCriteria(
            sender="shop@example.com",
            label_id="Label_1",
            include_spam_and_trash=True,
        ),
        limit=25,
    )
    assert result[0].subject == "A receipt"
    assert requests[0].url.params.get("maxResults") == "25"
    assert requests[0].url.params.get("q") == "from:shop@example.com"
    assert requests[0].url.params.get("labelIds") == "Label_1"
    assert requests[0].url.params.get("includeSpamTrash") == "true"


@pytest.mark.parametrize("limit", [0, 501])
def test_recent_candidates_reject_out_of_range_limit(limit: int) -> None:
    with pytest.raises(ValueError, match="limit"):
        client(lambda _: httpx.Response(500)).recent_messages(SelectionCriteria(), limit)


def test_recent_candidates_reject_manual_criteria_without_network() -> None:
    def forbidden(_: httpx.Request) -> httpx.Response:
        raise AssertionError("invalid candidate lookup must not call Gmail")

    with pytest.raises(ValueError, match="Manual"):
        client(forbidden).recent_messages(SelectionCriteria(explicit_message_ids=("a",)))


@pytest.mark.parametrize("document", [{"messages": "bad"}, {"messages": [None]}])
def test_recent_candidates_fail_closed_on_malformed_rows(document: dict) -> None:
    with pytest.raises(GmailApiError, match="malformed candidate list"):
        client(lambda _: httpx.Response(200, json=document)).recent_messages(
            SelectionCriteria()
        )


@pytest.mark.parametrize("ids", [("a", "a"), ("a", "")])
def test_malformed_manual_ids_are_rejected(ids: tuple[str, ...]) -> None:
    with pytest.raises(ValueError):
        client(lambda _: httpx.Response(500)).resolve_selection(
            SelectionCriteria(explicit_message_ids=ids)
        )


def test_transient_status_retries_then_succeeds() -> None:
    attempts = 0
    delays: list[float] = []

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(503 if attempts < 3 else 200, json={"messages": []})

    result = client(handler, sleeper=delays.append).resolve_selection(SelectionCriteria())
    assert result.exact_count == 0
    assert attempts == 3
    assert delays == [1, 2]


def test_exhausted_transient_status_is_marked_as_connection_failure() -> None:
    with pytest.raises(GmailApiError) as caught:
        client(lambda _: httpx.Response(503), max_attempts=1).resolve_selection(
            SelectionCriteria()
        )
    assert caught.value.status_code == 503
    assert caught.value.connection_failure


@pytest.mark.parametrize(
    ("body", "message"),
    [
        (b"not-json", "malformed JSON"),
        (b"[]", "unexpected JSON"),
        (json.dumps({"messages": "wrong"}).encode(), "malformed message list"),
    ],
)
def test_malformed_list_response_fails_closed(body: bytes, message: str) -> None:
    with pytest.raises(GmailApiError, match=message):
        client(lambda _: httpx.Response(200, content=body)).resolve_selection(SelectionCriteria())


def test_repeated_page_token_is_detected() -> None:
    with pytest.raises(GmailApiError, match="repeated a page token"):
        client(
            lambda _: httpx.Response(
                200, json={"messages": [], "nextPageToken": "same"}
            )
        ).resolve_selection(SelectionCriteria())


def test_authorization_error_is_sanitized() -> None:
    with pytest.raises(GmailApiError, match="authorization was rejected") as caught:
        client(lambda _: httpx.Response(401, text="sensitive server body")).profile()
    assert caught.value.status_code == 401
    assert "sensitive" not in str(caught.value)


def test_download_rejects_wrong_gmail_identity_and_preserves_existing_file(
    tmp_path: Path,
) -> None:
    raw = base64.urlsafe_b64encode(b"message").decode().rstrip("=")
    gmail = client(lambda _: httpx.Response(200, json={"id": "wrong", "raw": raw}))
    final = tmp_path / "expected.eml"
    final.write_bytes(b"previous verified message")
    with pytest.raises(GmailApiError, match="different message identity"):
        gmail.download_raw("expected", final)
    assert final.read_bytes() == b"previous verified message"
