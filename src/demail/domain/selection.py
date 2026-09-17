from dataclasses import dataclass
from datetime import date


def _parse_date(value: str | None) -> date | None:
    if value is None or not isinstance(value, str) or not value.strip():
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
    date_ranges: tuple[tuple[str | None, str | None], ...] = ()
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
                self.date_ranges,
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
        if self.date_ranges and (self.start_date is not None or self.end_date is not None):
            problems.append("A selection cannot mix one date range with multiple date ranges.")
        for index, value in enumerate(self.date_ranges, start=1):
            if not isinstance(value, tuple) or len(value) != 2:
                problems.append(f"Date range {index} is malformed.")
                continue
            range_start_value, range_end_value = value
            range_start = _parse_date(range_start_value)
            range_end = _parse_date(range_end_value)
            if range_start_value is not None and range_start is None:
                problems.append(f"Date range {index} start is not a valid date.")
            if range_end_value is not None and range_end is None:
                problems.append(f"Date range {index} end is not a valid date.")
            if range_start_value is None and range_end_value is None:
                problems.append(f"Date range {index} cannot cover the whole mailbox.")
            if range_start is not None and range_end is not None and range_end < range_start:
                problems.append(f"Date range {index} ends before it starts.")
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
        if self.date_ranges:
            range_count = len(self.date_ranges)
            noun = "period" if range_count == 1 else "periods"
            parts.append(f"{range_count} separate mailbox {noun}")
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
