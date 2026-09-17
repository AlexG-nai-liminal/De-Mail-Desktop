from dataclasses import dataclass
from datetime import date, timedelta

from demail.domain.selection import SelectionCriteria


@dataclass(frozen=True, slots=True)
class GmailListQuery:
    q: str | None
    label_ids: tuple[str, ...]
    include_spam_trash: bool


def _gmail_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"Invalid ISO date: {value}") from error


def _quote_sender(value: str) -> str:
    if any(character.isspace() or character in "():" for character in value):
        return f'"{value.replace(chr(34), "")}"'
    return value


def _date_terms(start_date: str | None, end_date: str | None) -> list[str]:
    terms: list[str] = []
    if start_date:
        terms.append(f"after:{_gmail_date(start_date):%Y/%m/%d}")
    if end_date:
        exclusive_end = _gmail_date(end_date) + timedelta(days=1)
        terms.append(f"before:{exclusive_end:%Y/%m/%d}")
    return terms


def build_query(criteria: SelectionCriteria) -> GmailListQuery:
    if criteria.is_manual_selection:
        raise ValueError(
            "A manual selection is resolved from its explicit message IDs, not from a Gmail query"
        )
    problems = criteria.validate()
    if problems:
        raise ValueError(" ".join(problems))

    terms: list[str] = []
    terms.extend(_date_terms(criteria.start_date, criteria.end_date))
    if criteria.date_ranges:
        alternatives = [
            f"({' '.join(_date_terms(start, end))})" for start, end in criteria.date_ranges
        ]
        terms.append(f"({' OR '.join(alternatives)})")
    if criteria.sender and (sender := criteria.sender.strip()):
        terms.append(f"from:{_quote_sender(sender)}")
    if criteria.search_query and (search := criteria.search_query.strip()):
        grouped = search.startswith("(") and search.endswith(")")
        terms.append(f"({search})" if " " in search and not grouped else search)

    label_ids = (criteria.label_id,) if criteria.label_id and criteria.label_id.strip() else ()
    return GmailListQuery(" ".join(terms) or None, label_ids, criteria.include_spam_and_trash)
