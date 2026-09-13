"""Direct, GET-only Gmail REST client."""

import codecs
import io
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast
from urllib.parse import quote

import httpx

from demail.archive.gmail_pipeline import ArchivedRawMessage, archive_raw_response
from demail.domain.selection import SelectionCriteria

from .query import GmailListQuery, build_query


class AccessTokenProvider(Protocol):
    def access_token(self) -> str: ...


class GmailApiError(RuntimeError):
    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        *,
        connection_failure: bool = False,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.connection_failure = connection_failure


@dataclass(frozen=True, slots=True)
class GmailProfile:
    email_address: str
    messages_total: int
    threads_total: int
    history_id: str | None


@dataclass(frozen=True, slots=True)
class GmailLabel:
    id: str
    name: str
    type: str | None


@dataclass(frozen=True, slots=True)
class GmailMessageRef:
    id: str
    thread_id: str | None


@dataclass(frozen=True, slots=True)
class GmailMessageMetadata:
    id: str
    thread_id: str | None
    internal_date_ms: int | None
    subject: str | None
    sender: str | None
    label_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SelectionResult:
    messages: tuple[GmailMessageRef, ...]

    @property
    def exact_count(self) -> int:
        return len(self.messages)


class _Utf8IteratorReader(io.TextIOBase):
    """Expose bounded byte chunks as text without materializing the response."""

    def __init__(self, chunks: Iterator[bytes]) -> None:
        self._chunks = chunks
        self._decoder = codecs.getincrementaldecoder("utf-8")("strict")
        self._buffer = ""
        self._finished = False

    def readable(self) -> bool:
        return True

    def read(self, size: int = -1) -> str:
        if size < 0:
            raise ValueError("Bounded Gmail reader requires an explicit read size")
        while len(self._buffer) < size and not self._finished:
            try:
                chunk = next(self._chunks)
            except StopIteration:
                self._buffer += self._decoder.decode(b"", final=True)
                self._finished = True
                break
            self._buffer += self._decoder.decode(chunk, final=False)
        result = self._buffer[:size]
        self._buffer = self._buffer[size:]
        return result


class GmailClient:
    BASE_URL = "https://gmail.googleapis.com/gmail/v1"
    TRANSIENT_STATUS = {429, 500, 502, 503, 504}

    def __init__(
        self,
        tokens: AccessTokenProvider,
        *,
        client: httpx.Client | None = None,
        base_url: str = BASE_URL,
        max_attempts: int = 3,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if max_attempts <= 0:
            raise ValueError("max_attempts must be positive")
        self.tokens = tokens
        self.client = client or httpx.Client(timeout=httpx.Timeout(60, read=120))
        self.base_url = base_url.rstrip("/")
        self.max_attempts = max_attempts
        self.sleeper = sleeper

    def profile(self) -> GmailProfile:
        document = self._json_get("/users/me/profile")
        try:
            return GmailProfile(
                email_address=self._required_string(document, "emailAddress"),
                messages_total=self._required_nonnegative_int(document, "messagesTotal"),
                threads_total=self._required_nonnegative_int(document, "threadsTotal"),
                history_id=self._optional_string(document, "historyId"),
            )
        except (TypeError, ValueError) as error:
            raise GmailApiError("Gmail returned a malformed profile response.") from error

    def labels(self) -> tuple[GmailLabel, ...]:
        document = self._json_get("/users/me/labels")
        rows = document.get("labels", [])
        if not isinstance(rows, list):
            raise GmailApiError("Gmail returned a malformed label response.")
        labels: list[GmailLabel] = []
        try:
            for row in rows:
                if not isinstance(row, dict):
                    raise TypeError
                labels.append(
                    GmailLabel(
                        id=self._required_string(row, "id"),
                        name=self._required_string(row, "name"),
                        type=self._optional_string(row, "type"),
                    )
                )
        except (TypeError, ValueError) as error:
            raise GmailApiError("Gmail returned a malformed label response.") from error
        return tuple(labels)

    def resolve_selection(self, criteria: SelectionCriteria) -> SelectionResult:
        if criteria.is_manual_selection:
            if len(criteria.explicit_message_ids) != len(set(criteria.explicit_message_ids)):
                raise ValueError("Manual message IDs must be unique.")
            if any(not message_id.strip() for message_id in criteria.explicit_message_ids):
                raise ValueError("Manual message IDs cannot be blank.")
            return SelectionResult(
                tuple(
                    GmailMessageRef(message_id, None)
                    for message_id in criteria.explicit_message_ids
                )
            )
        query = build_query(criteria)
        messages: list[GmailMessageRef] = []
        seen_ids: set[str] = set()
        seen_page_tokens: set[str] = set()
        page_token: str | None = None
        while True:
            document = self._list_page(query, page_token)
            rows = document.get("messages", [])
            if not isinstance(rows, list):
                raise GmailApiError("Gmail returned a malformed message list.")
            for row in rows:
                if not isinstance(row, dict):
                    raise GmailApiError("Gmail returned a malformed message list.")
                message_id = self._required_string(row, "id")
                if message_id in seen_ids:
                    raise GmailApiError("Gmail returned a duplicate message ID while counting.")
                seen_ids.add(message_id)
                messages.append(GmailMessageRef(message_id, self._optional_string(row, "threadId")))
            next_token = document.get("nextPageToken")
            if next_token is None:
                return SelectionResult(tuple(messages))
            if not isinstance(next_token, str) or not next_token:
                raise GmailApiError("Gmail returned an invalid next-page token.")
            if next_token in seen_page_tokens:
                raise GmailApiError("Gmail repeated a page token while counting messages.")
            seen_page_tokens.add(next_token)
            page_token = next_token

    def download_raw(self, message_id: str, final_path: Path) -> ArchivedRawMessage:
        if not message_id.strip():
            raise ValueError("message_id cannot be blank")
        path = f"/users/me/messages/{quote(message_id, safe='')}"
        with self._stream_get(path, params={"format": "raw"}) as response:
            reader = _Utf8IteratorReader(response.iter_bytes(chunk_size=8192))
            try:
                result = archive_raw_response(
                    reader, final_path, expected_message_id=message_id
                )
            except ValueError as error:
                if "different message identity" in str(error):
                    raise GmailApiError(
                        "Gmail returned a different message identity than requested."
                    ) from error
                raise GmailApiError("Gmail returned malformed raw message data.") from error
        return result

    def metadata(self, message_id: str) -> GmailMessageMetadata:
        if not message_id.strip():
            raise ValueError("message_id cannot be blank")
        path = f"/users/me/messages/{quote(message_id, safe='')}"
        params = [
            ("format", "metadata"),
            ("metadataHeaders", "Subject"),
            ("metadataHeaders", "From"),
        ]
        document = self._json_get(path, params=params)
        try:
            payload = document.get("payload", {})
            if not isinstance(payload, dict):
                raise TypeError
            header_rows = payload.get("headers", [])
            if not isinstance(header_rows, list):
                raise TypeError
            headers: dict[str, str] = {}
            for row in header_rows:
                if not isinstance(row, dict):
                    raise TypeError
                name = row.get("name")
                value = row.get("value")
                if isinstance(name, str) and isinstance(value, str):
                    headers.setdefault(name.casefold(), value)
            internal_date = self._optional_string(document, "internalDate")
            labels = document.get("labelIds", [])
            if not isinstance(labels, list) or not all(isinstance(item, str) for item in labels):
                raise TypeError
            return GmailMessageMetadata(
                id=self._required_string(document, "id"),
                thread_id=self._optional_string(document, "threadId"),
                internal_date_ms=int(internal_date) if internal_date is not None else None,
                subject=headers.get("subject"),
                sender=headers.get("from"),
                label_ids=tuple(labels),
            )
        except (TypeError, ValueError) as error:
            raise GmailApiError("Gmail returned malformed message metadata.") from error

    def recent_messages(
        self, criteria: SelectionCriteria, limit: int = 100
    ) -> tuple[GmailMessageMetadata, ...]:
        if criteria.is_manual_selection:
            raise ValueError("Manual criteria cannot be used to discover candidates.")
        if not 1 <= limit <= 500:
            raise ValueError("Candidate limit must be from 1 to 500.")
        query = build_query(criteria)
        params: list[tuple[str, str | int | bool]] = [("maxResults", limit)]
        if query.q:
            params.append(("q", query.q))
        params.extend(("labelIds", label_id) for label_id in query.label_ids)
        if query.include_spam_trash:
            params.append(("includeSpamTrash", True))
        document = self._json_get("/users/me/messages", params=params)
        rows = document.get("messages", [])
        if not isinstance(rows, list):
            raise GmailApiError("Gmail returned a malformed candidate list.")
        output: list[GmailMessageMetadata] = []
        for row in rows:
            if not isinstance(row, dict):
                raise GmailApiError("Gmail returned a malformed candidate list.")
            output.append(self.metadata(self._required_string(row, "id")))
        return tuple(output)

    def _list_page(self, query: GmailListQuery, page_token: str | None) -> dict[str, object]:
        params: list[tuple[str, str | int | bool]] = [("maxResults", 500)]
        if query.q:
            params.append(("q", query.q))
        params.extend(("labelIds", label_id) for label_id in query.label_ids)
        if query.include_spam_trash:
            params.append(("includeSpamTrash", True))
        if page_token:
            params.append(("pageToken", page_token))
        return self._json_get("/users/me/messages", params=params)

    def _headers(self) -> dict[str, str]:
        token = self.tokens.access_token()
        if not token:
            raise GmailApiError("Google authorization is unavailable.")
        return {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    def _json_get(
        self, path: str, params: list[tuple[str, str | int | bool]] | None = None
    ) -> dict[str, object]:
        response = self._request_get(path, params=params)
        try:
            document = response.json()
        except ValueError as error:
            raise GmailApiError("Gmail returned malformed JSON.", response.status_code) from error
        if not isinstance(document, dict):
            raise GmailApiError("Gmail returned an unexpected JSON value.", response.status_code)
        return cast(dict[str, object], document)

    def _request_get(
        self, path: str, params: list[tuple[str, str | int | bool]] | None = None
    ) -> httpx.Response:
        for attempt in range(self.max_attempts):
            try:
                response = self.client.get(
                    f"{self.base_url}{path}", headers=self._headers(), params=params
                )
            except httpx.RequestError as error:
                if attempt + 1 == self.max_attempts:
                    raise GmailApiError(
                        "Gmail could not be reached.", connection_failure=True
                    ) from error
                self.sleeper(2**attempt)
                continue
            if response.status_code < 400:
                return response
            if (
                response.status_code not in self.TRANSIENT_STATUS
                or attempt + 1 == self.max_attempts
            ):
                self._raise_status(response.status_code)
            self.sleeper(2**attempt)
        raise AssertionError("unreachable")

    @contextmanager
    def _stream_get(self, path: str, params: dict[str, str]) -> Iterator[httpx.Response]:
        for attempt in range(self.max_attempts):
            try:
                with self.client.stream(
                    "GET", f"{self.base_url}{path}", headers=self._headers(), params=params
                ) as response:
                    if response.status_code < 400:
                        try:
                            yield response
                        except httpx.RequestError as error:
                            raise GmailApiError(
                                "The Gmail download was interrupted.", connection_failure=True
                            ) from error
                        return
                    if (
                        response.status_code not in self.TRANSIENT_STATUS
                        or attempt + 1 == self.max_attempts
                    ):
                        self._raise_status(response.status_code)
            except GmailApiError:
                raise
            except httpx.RequestError as error:
                if attempt + 1 == self.max_attempts:
                    raise GmailApiError(
                        "Gmail could not be reached.", connection_failure=True
                    ) from error
            self.sleeper(2**attempt)
        raise AssertionError("unreachable")

    @staticmethod
    def _raise_status(status_code: int) -> None:
        if status_code in {401, 403}:
            raise GmailApiError("Google authorization was rejected.", status_code)
        if status_code == 404:
            raise GmailApiError("The Gmail message was not found.", status_code)
        raise GmailApiError(
            "Gmail returned an error.",
            status_code,
            connection_failure=status_code in GmailClient.TRANSIENT_STATUS,
        )

    @staticmethod
    def _required_string(document: dict[str, object], key: str) -> str:
        value = document.get(key)
        if not isinstance(value, str) or not value:
            raise ValueError(key)
        return value

    @staticmethod
    def _optional_string(document: dict[str, object], key: str) -> str | None:
        value = document.get(key)
        return value if isinstance(value, str) else None

    @staticmethod
    def _required_nonnegative_int(document: dict[str, object], key: str) -> int:
        value = document.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(key)
        return value
