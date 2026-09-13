from datetime import date

from demail.gmail.client import SelectionResult
from demail.gmail.selection_service import MailboxEraScanner


class CountingSource:
    def __init__(self, counts: dict[tuple[str, str], int]) -> None:
        self.counts = counts
        self.criteria = []

    def resolve_selection(self, criteria):
        self.criteria.append(criteria)
        count = self.counts.get((criteria.start_date, criteria.end_date), 0)
        return SelectionResult(tuple(object() for _ in range(count)))


def test_scanner_counts_each_year_exactly_and_reports_progress() -> None:
    counts = {
        ("2004-01-01", "2004-12-31"): 100,
        ("2005-01-01", "2005-12-31"): 100,
        ("2006-01-01", "2006-12-31"): 100,
    }
    for year in (2005, 2006):
        for month in range(1, 13):
            start = date(year, month, 1)
            end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
            counts[(start.isoformat(), date.fromordinal(end.toordinal() - 1).isoformat())] = (
                10 if month <= 10 else 0
            )
    source = CountingSource(counts)
    progress = []
    split = MailboxEraScanner(source, today=lambda: date(2006, 6, 1)).scan(progress=progress.append)
    assert split.total_count == 300
    assert progress[-1].periods_done == 3
    assert progress[-1].messages_seen == 300


def test_boundary_years_are_refined_by_month() -> None:
    counts = {
        ("2004-01-01", "2004-12-31"): 120,
        ("2005-01-01", "2005-12-31"): 120,
        ("2006-01-01", "2006-12-31"): 120,
    }
    for year in (2005, 2006):
        for month in range(1, 13):
            start = date(year, month, 1)
            end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
            counts[(start.isoformat(), date.fromordinal(end.toordinal() - 1).isoformat())] = 10
    source = CountingSource(counts)
    split = MailboxEraScanner(source, today=lambda: date(2006, 1, 1)).scan()
    assert split.total_count == 360
    assert len(source.criteria) > 3
