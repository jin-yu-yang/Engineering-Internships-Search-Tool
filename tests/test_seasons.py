from datetime import date

import pytest

from internship_research_demo.seasons import (
    current_term,
    default_season,
    upcoming_seasons,
)


@pytest.mark.parametrize(
    ("today", "expected"),
    [
        (date(2026, 12, 1), ("Winter", 2027)),
        (date(2027, 2, 28), ("Winter", 2027)),
        (date(2027, 3, 1), ("Spring", 2027)),
        (date(2027, 6, 1), ("Summer", 2027)),
        (date(2027, 8, 31), ("Summer", 2027)),
        (date(2026, 9, 1), ("Fall", 2026)),
        (date(2026, 9, 18), ("Fall", 2026)),
    ],
)
def test_current_term(today, expected):
    assert current_term(today) == expected


def test_upcoming_seasons_from_fall():
    assert upcoming_seasons(date(2026, 9, 18)) == [
        "Fall 2026",
        "Winter 2027",
        "Spring 2027",
        "Summer 2027",
        "Fall 2027",
    ]


def test_upcoming_seasons_from_december_rolls_year():
    assert upcoming_seasons(date(2026, 12, 15), n=3) == [
        "Winter 2027",
        "Spring 2027",
        "Summer 2027",
    ]


@pytest.mark.parametrize(
    ("today", "expected"),
    [
        (date(2026, 9, 18), "Summer 2027"),
        (date(2027, 3, 15), "Summer 2027"),
        (date(2027, 7, 1), "Summer 2028"),
        (date(2026, 12, 1), "Summer 2027"),
    ],
)
def test_default_season_is_next_summer_after_current_term(today, expected):
    assert default_season(today) == expected


@pytest.mark.parametrize(
    "today",
    [date(2026, 1, 10), date(2026, 4, 1), date(2026, 7, 4), date(2026, 10, 1), date(2026, 12, 31)],
)
def test_default_season_is_always_offered(today):
    assert default_season(today) in upcoming_seasons(today)
