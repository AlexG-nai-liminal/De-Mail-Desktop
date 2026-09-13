from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Protocol

from demail.domain.eras import EraSplit, PeriodCount, split_eras
from demail.domain.selection import SelectionCriteria

from .client import GmailClient, GmailLabel, GmailMessageMetadata, SelectionResult


class SelectionSource(Protocol):
    def labels(self) -> tuple[GmailLabel, ...]: ...

    def resolve_selection(self, criteria: SelectionCriteria) -> SelectionResult: ...

    def recent_messages(
        self, criteria: SelectionCriteria, limit: int
    ) -> tuple[GmailMessageMetadata, ...]: ...


@dataclass(frozen=True, slots=True)
class ScanProgress:
    periods_done: int
    periods_total: int
    messages_seen: int


class MailboxEraScanner:
    FIRST_GMAIL_YEAR = 2004

    def __init__(self, source: SelectionSource, today: Callable[[], date] = date.today) -> None:
        self.source = source
        self.today = today

    def scan(
        self,
        include_spam_and_trash: bool = False,
        progress: Callable[[ScanProgress], None] | None = None,
    ) -> EraSplit:
        years = list(range(self.FIRST_GMAIL_YEAR, self.today().year + 1))
        periods: list[PeriodCount] = []
        seen = 0
        for index, year in enumerate(years):
            start = date(year, 1, 1)
            end = date(year + 1, 1, 1)
            count = self._count(start, end, include_spam_and_trash)
            periods.append(PeriodCount(start, end, count))
            seen += count
            if progress:
                progress(ScanProgress(index + 1, len(years), seen))
        coarse = split_eras(periods)
        if len(coarse.eras) < 3:
            return coarse
        boundary_years = {era.start_date.year for era in coarse.eras if era.start_date}
        refined: list[PeriodCount] = []
        for period in periods:
            if not period.count:
                continue
            if period.start.year not in boundary_years:
                refined.append(period)
                continue
            for month in range(1, 13):
                start = date(period.start.year, month, 1)
                end = date(start.year + 1, 1, 1) if month == 12 else date(start.year, month + 1, 1)
                refined.append(
                    PeriodCount(start, end, self._count(start, end, include_spam_and_trash))
                )
        return split_eras(refined)

    def _count(self, start: date, end_exclusive: date, include_spam_and_trash: bool) -> int:
        criteria = SelectionCriteria(
            start_date=start.isoformat(),
            end_date=(end_exclusive - timedelta(days=1)).isoformat(),
            include_spam_and_trash=include_spam_and_trash,
        )
        return self.source.resolve_selection(criteria).exact_count


class MailboxSelectionService:
    def __init__(self, gmail: GmailClient) -> None:
        self.gmail = gmail

    def labels(self) -> tuple[GmailLabel, ...]:
        return self.gmail.labels()

    def exact_selection(self, criteria: SelectionCriteria) -> SelectionResult:
        return self.gmail.resolve_selection(criteria)

    def resolve_selection(self, criteria: SelectionCriteria) -> SelectionResult:
        """Expose the scanner's exact-count source contract."""
        return self.gmail.resolve_selection(criteria)

    def recent_messages(
        self, criteria: SelectionCriteria, limit: int = 100
    ) -> tuple[GmailMessageMetadata, ...]:
        return self.gmail.recent_messages(criteria, limit)
