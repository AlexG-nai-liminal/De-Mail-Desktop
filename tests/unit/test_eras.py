from datetime import date

import pytest

from demail.domain.eras import Era, EraKind, PeriodCount, combine_eras, split_eras


def years(first: int, *counts: int) -> list[PeriodCount]:
    return [
        PeriodCount(date(first + index, 1, 1), date(first + index + 1, 1, 1), count)
        for index, count in enumerate(counts)
    ]


def test_even_mailbox_splits_into_three_equal_eras() -> None:
    split = split_eras(years(2019, 100, 100, 100, 100, 100, 100))
    assert split.total_count == 600
    assert [era.approximate_count for era in split.eras] == [200, 200, 200]
    assert split.is_balanced


def test_eras_cover_mailbox_without_gaps() -> None:
    far, recent, present = split_eras(years(2018, 300, 300, 300, 300, 300, 300)).eras
    assert far.kind == EraKind.FAR_PAST
    assert recent.kind == EraKind.RECENT_PAST
    assert present.kind == EraKind.PRESENT
    assert far.start_date is None
    assert far.end_exclusive == recent.start_date
    assert recent.end_exclusive == present.start_date
    assert present.end_exclusive is None


def test_split_follows_messages_and_reports_unbalanced_result() -> None:
    split = split_eras(years(2004, *([100] * 20), 20_000))
    assert all(era.approximate_count > 0 for era in split.eras)
    assert not split.is_balanced


def test_too_few_populated_periods_produce_one_honest_era() -> None:
    split = split_eras(years(2024, 4_000, 5_000))
    assert len(split.eras) == 1
    assert split.eras[0].kind == EraKind.PRESENT
    assert not split.is_balanced


def test_empty_periods_and_empty_mailbox_are_safe() -> None:
    assert split_eras([]).eras == ()
    assert split_eras(years(2020, 0, 0, 0)).eras == ()


def test_era_criteria_converts_exclusive_boundary_to_inclusive_end() -> None:
    era = split_eras(years(2020, 1, 1, 1)).eras[0]
    criteria = era.criteria()
    assert criteria.start_date is None
    assert criteria.end_date == "2020-12-31"


@pytest.mark.parametrize(
    "start,end,count",
    [(date(2024, 1, 1), date(2024, 1, 1), 1), (date(2024, 1, 1), date(2025, 1, 1), -1)],
)
def test_malformed_periods_are_rejected(start: date, end: date, count: int) -> None:
    with pytest.raises(ValueError):
        PeriodCount(start, end, count)


def test_adjacent_selected_eras_are_merged_without_duplicate_boundaries() -> None:
    oldest, middle, _ = split_eras(years(2018, 10, 10, 10, 10, 10, 10)).eras
    criteria = combine_eras((oldest, middle), include_spam_and_trash=True)
    assert criteria.start_date is None
    assert criteria.end_date == "2021-12-31"
    assert criteria.date_ranges == ()
    assert criteria.include_spam_and_trash


def test_separated_selected_eras_remain_separate() -> None:
    oldest, _, newest = split_eras(years(2018, 10, 10, 10, 10, 10, 10)).eras
    assert combine_eras((oldest, newest)).date_ranges == (
        (None, "2019-12-31"),
        ("2022-01-01", None),
    )


def test_combining_every_era_selects_whole_mailbox() -> None:
    eras = split_eras(years(2018, 10, 10, 10, 10, 10, 10)).eras
    assert combine_eras(eras).is_whole_mailbox


@pytest.mark.parametrize(
    "eras",
    [
        (),
        (
            Era(EraKind.PRESENT, date(2024, 1, 2), date(2024, 1, 1), 1),
        ),
        (
            Era(EraKind.FAR_PAST, None, date(2024, 1, 3), 1),
            Era(EraKind.PRESENT, date(2024, 1, 2), None, 1),
        ),
    ],
)
def test_invalid_era_combinations_fail_safely(eras: tuple[Era, ...]) -> None:
    with pytest.raises(ValueError):
        combine_eras(eras)
