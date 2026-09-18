from internship_research_demo.routing import (
    NO_RESULTS,
    RANK,
    RESEARCH_MORE,
    REVIEW,
    decide_route,
)

BASE = dict(
    viable=3,
    wanted=3,
    research_round=0,
    max_extra_rounds=2,
    force_more=False,
    review_enabled=False,
    reviewed_round=-1,
    has_new=True,
)


def route(**overrides):
    return decide_route(**{**BASE, **overrides})


def test_enough_candidates_ranks():
    assert route() == RANK


def test_short_with_rounds_left_researches_more():
    assert route(viable=1) == RESEARCH_MORE


def test_short_with_no_rounds_left_ranks():
    assert route(viable=1, research_round=2) == RANK


def test_zero_with_no_rounds_left_is_no_results():
    assert route(viable=0, research_round=2) == NO_RESULTS


def test_zero_retry_budget_goes_straight_to_no_results():
    assert route(viable=0, max_extra_rounds=0) == NO_RESULTS


def test_force_more_with_rounds_left_researches_even_when_enough():
    assert route(force_more=True) == RESEARCH_MORE


def test_force_more_without_rounds_falls_through_to_rank():
    assert route(force_more=True, research_round=2) == RANK


def test_review_pending_reviews():
    assert route(review_enabled=True) == REVIEW


def test_review_already_done_this_round_ranks():
    assert route(review_enabled=True, reviewed_round=0) == RANK


def test_review_skipped_when_round_found_nothing_new():
    assert route(review_enabled=True, has_new=False) == RANK


def test_auto_retry_takes_precedence_over_review():
    assert route(viable=1, review_enabled=True) == RESEARCH_MORE
