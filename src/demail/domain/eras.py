from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum

from .selection import SelectionCriteria


class EraKind(StrEnum):
    FAR_PAST = "Far past"
    RECENT_PAST = "Recent past"
    PRESENT = "Present"


@dataclass(frozen=True, slots=True)
class PeriodCount:
    start: date
    end_exclusive: date
    count: int

    def __post_init__(self) -> None:
        if self.count < 0:
            raise ValueError("Period count cannot be negative")
        if self.end_exclusive <= self.start:
            raise ValueError("Period end must follow its start")


@dataclass(frozen=True, slots=True)
class Era:
    kind: EraKind
    start_date: date | None
    end_exclusive: date | None
    approximate_count: int

    def criteria(self, include_spam_and_trash: bool = False) -> SelectionCriteria:
        inclusive_end = self.end_exclusive - timedelta(days=1) if self.end_exclusive else None
        return SelectionCriteria(
            start_date=self.start_date.isoformat() if self.start_date else None,
            end_date=inclusive_end.isoformat() if inclusive_end else None,
            include_spam_and_trash=include_spam_and_trash,
        )


@dataclass(frozen=True, slots=True)
class EraSplit:
    eras: tuple[Era, ...]
    total_count: int
    worst_deviation_points: float

    @property
    def is_balanced(self) -> bool:
        return self.worst_deviation_points <= 5.0


def combine_eras(
    eras: tuple[Era, ...], include_spam_and_trash: bool = False
) -> SelectionCriteria:
    """Combine chronological mailbox eras without filling gaps between them."""
    if not eras:
        raise ValueError("Choose at least one mailbox third.")

    merged: list[tuple[date | None, date | None]] = []
    for era in eras:
        if era.approximate_count < 0:
            raise ValueError("Mailbox era count cannot be negative.")
        if (
            era.start_date is not None
            and era.end_exclusive is not None
            and era.end_exclusive <= era.start_date
        ):
            raise ValueError("Mailbox era boundaries are invalid.")
        if not merged:
            merged.append((era.start_date, era.end_exclusive))
            continue

        previous_start, previous_end = merged[-1]
        if previous_end is None or era.start_date is None or era.start_date < previous_end:
            raise ValueError("Mailbox eras overlap or are out of order.")
        if era.start_date == previous_end:
            merged[-1] = (previous_start, era.end_exclusive)
        else:
            merged.append((era.start_date, era.end_exclusive))

    ranges = tuple(
        (
            start.isoformat() if start else None,
            (end_exclusive - timedelta(days=1)).isoformat() if end_exclusive else None,
        )
        for start, end_exclusive in merged
    )
    if len(ranges) == 1:
        start, end = ranges[0]
        return SelectionCriteria(
            start_date=start,
            end_date=end,
            include_spam_and_trash=include_spam_and_trash,
        )
    return SelectionCriteria(
        date_ranges=ranges,
        include_spam_and_trash=include_spam_and_trash,
    )


def split_eras(periods: list[PeriodCount]) -> EraSplit:
    populated = sorted(
        (period for period in periods if period.count > 0), key=lambda item: item.start
    )
    total = sum(period.count for period in populated)
    if not populated:
        return EraSplit((), 0, 0.0)
    if len(populated) < 3:
        return EraSplit(
            (
                Era(
                    EraKind.PRESENT,
                    start_date=None,
                    end_exclusive=None,
                    approximate_count=total,
                ),
            ),
            total,
            100.0 * (1.0 - 1.0 / 3.0),
        )

    first = _nearest_cut(populated, total / 3.0, 1, len(populated) - 2)
    second = _nearest_cut(populated, total * 2.0 / 3.0, first + 1, len(populated) - 1)
    groups = (populated[:first], populated[first:second], populated[second:])
    eras = (
        Era(EraKind.FAR_PAST, None, groups[0][-1].end_exclusive, _total(groups[0])),
        Era(
            EraKind.RECENT_PAST,
            groups[1][0].start,
            groups[1][-1].end_exclusive,
            _total(groups[1]),
        ),
        Era(EraKind.PRESENT, groups[2][0].start, None, _total(groups[2])),
    )
    third = total / 3.0
    worst = max(100.0 * abs(era.approximate_count - third) / total for era in eras)
    return EraSplit(eras, total, worst)


def _nearest_cut(periods: list[PeriodCount], target: float, minimum: int, maximum: int) -> int:
    running = 0
    best = minimum
    best_distance = float("inf")
    for index, period in enumerate(periods):
        running += period.count
        boundary = index + 1
        if minimum <= boundary <= maximum:
            distance = abs(running - target)
            if distance < best_distance:
                best = boundary
                best_distance = distance
    return min(max(best, minimum), maximum)


def _total(periods: list[PeriodCount]) -> int:
    return sum(period.count for period in periods)
