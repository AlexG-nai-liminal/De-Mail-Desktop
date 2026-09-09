from dataclasses import dataclass
from datetime import date


def _parse_date(value: str | None) -> date | None:
    if value is None or not value.strip():
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _display(value: date) -> str:
    return f"{value.day} {value.strftime('%b %Y')}"


@dataclass(frozen=True, slots=True)
class SelectionCriteria:
    start_date: str | None = None
    end_date: str | None = None
    label_id: str | None = None
    label_name: str | None = None
    sender: str | None = None
    search_query: str | None = None
    include_spam_and_trash: bool = False
    explicit_message_ids: tuple[str, ...] = ()

    @property
    def is_manual_selection(self) -> bool:
        return bool(self.explicit_message_ids)

    @property
    def is_whole_mailbox(self) -> bool:
        return not self.is_manual_selection and not any(
            (
                self.start_date,
                self.end_date,
                self.label_id,
                self.sender and self.sender.strip(),
                self.search_query and self.search_query.strip(),
            )
        )

    def validate(self) -> tuple[str, ...]:
        problems: list[str] = []
        start = _parse_date(self.start_date)
        end = _parse_date(self.end_date)
        if self.start_date is not None and start is None:
            problems.append("Start date is not a valid date.")
        if self.end_date is not None and end is None:
            problems.append("End date is not a valid date.")
        if start is not None and end is not None and end < start:
            problems.append("End date is before the start date.")
        return tuple(problems)

    def describe(self) -> str:
        if self.is_manual_selection:
            count = len(self.explicit_message_ids)
            suffix = "" if count == 1 else "s"
            return f"{count} manually selected message{suffix}"
        parts: list[str] = []
        start = _parse_date(self.start_date)
        end = _parse_date(self.end_date)
        if start and end:
            parts.append(f"{_display(start)} to {_display(end)}")
        elif start:
            parts.append(f"on or after {_display(start)}")
        elif end:
            parts.append(f"on or before {_display(end)}")
        if self.label_name and self.label_name.strip():
            parts.append(f'label "{self.label_name}"')
        elif self.label_id and self.label_id.strip():
            parts.append(f"label {self.label_id}")
        if self.sender and self.sender.strip():
            parts.append(f"from {self.sender}")
        if self.search_query and self.search_query.strip():
            parts.append(f'search "{self.search_query.strip()}"')
        if self.include_spam_and_trash:
            parts.append("including Spam & Trash")
        return " · ".join(parts) if parts else "All mail"

