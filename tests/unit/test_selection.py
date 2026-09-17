import pytest

from demail.domain.selection import SelectionCriteria
from demail.gmail.query import GmailListQuery, build_query


def test_empty_criteria_select_whole_mailbox() -> None:
    criteria = SelectionCriteria()
    assert criteria.is_whole_mailbox
    assert build_query(criteria) == GmailListQuery(None, (), False)
    assert criteria.describe() == "All mail"


def test_inclusive_date_range_uses_following_day_for_before() -> None:
    query = build_query(SelectionCriteria(start_date="2023-01-15", end_date="2023-02-04"))
    assert query.q == "after:2023/01/15 before:2023/02/05"


def test_leap_day_rolls_into_march() -> None:
    assert build_query(SelectionCriteria(end_date="2024-02-29")).q == "before:2024/03/01"


def test_year_boundary_rolls_forward() -> None:
    assert build_query(SelectionCriteria(end_date="2024-12-31")).q == "before:2025/01/01"


def test_sender_search_label_and_spam_options_are_preserved() -> None:
    query = build_query(
        SelectionCriteria(
            label_id="Label_42",
            sender="Alice Smith",
            search_query="from:bob OR from:carol",
            include_spam_and_trash=True,
        )
    )
    assert query == GmailListQuery(
        'from:"Alice Smith" (from:bob OR from:carol)', ("Label_42",), True
    )


def test_sender_quotes_are_removed_inside_quoted_sender() -> None:
    assert build_query(SelectionCriteria(sender='Alice "Danger" Smith')).q == (
        'from:"Alice Danger Smith"'
    )


@pytest.mark.parametrize("value", ["", " ", "\t"])
def test_blank_fields_are_ignored(value: str) -> None:
    assert build_query(SelectionCriteria(sender=value, search_query=value, label_id=value)) == (
        GmailListQuery(None, (), False)
    )


@pytest.mark.parametrize(
    ("criteria", "problem"),
    [
        (SelectionCriteria(start_date="yesterday"), "Start date is not a valid date."),
        (SelectionCriteria(end_date="2023-02-29"), "End date is not a valid date."),
        (
            SelectionCriteria(start_date="2024-03-01", end_date="2024-02-01"),
            "End date is before the start date.",
        ),
    ],
)
def test_malformed_date_input_is_rejected(criteria: SelectionCriteria, problem: str) -> None:
    assert problem in criteria.validate()
    with pytest.raises(ValueError, match=problem):
        build_query(criteria)


def test_manual_selection_never_becomes_a_search() -> None:
    criteria = SelectionCriteria(explicit_message_ids=("a", "b"), search_query="ignored")
    assert not criteria.is_whole_mailbox
    assert criteria.describe() == "2 manually selected messages"
    with pytest.raises(ValueError, match="manual selection"):
        build_query(criteria)


def test_description_uses_display_language_without_dash_characters() -> None:
    description = SelectionCriteria(
        start_date="2023-01-15",
        end_date="2023-02-04",
        label_id="Label_1",
        label_name="Receipts",
        sender="alice@example.com",
        include_spam_and_trash=True,
    ).describe()
    assert description == (
        '15 Jan 2023 to 4 Feb 2023 · label "Receipts" · from alice@example.com · '
        "including Spam & Trash"
    )
    assert "—" not in description and "–" not in description


def test_disjoint_date_ranges_become_one_grouped_gmail_query() -> None:
    criteria = SelectionCriteria(
        date_ranges=((None, "2011-12-31"), ("2021-01-01", None)),
        sender="archive@example.com",
    )
    assert build_query(criteria).q == (
        "((before:2012/01/01) OR (after:2021/01/01)) from:archive@example.com"
    )
    assert criteria.describe() == "2 separate mailbox periods · from archive@example.com"


@pytest.mark.parametrize(
    ("criteria", "problem"),
    [
        (
            SelectionCriteria(start_date="2024-01-01", date_ranges=((None, "2020-01-01"),)),
            "cannot mix",
        ),
        (SelectionCriteria(date_ranges=((None, None),)), "cannot cover the whole mailbox"),
        (SelectionCriteria(date_ranges=(("bad", None),)), "start is not a valid date"),
        (
            SelectionCriteria(date_ranges=(("2024-02-01", "2024-01-01"),)),
            "ends before it starts",
        ),
    ],
)
def test_malformed_multiple_date_ranges_are_rejected(
    criteria: SelectionCriteria, problem: str
) -> None:
    assert any(problem in value for value in criteria.validate())
    with pytest.raises(ValueError, match=problem):
        build_query(criteria)
