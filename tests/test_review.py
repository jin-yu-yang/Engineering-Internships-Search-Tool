from helpers import make_candidate
from internship_research_demo.models import Verification, VerifiedCandidate
from internship_research_demo.review import (
    Accept,
    Drop,
    Invalid,
    More,
    parse_review_command,
    render_shortlist,
    run_review,
)


def _item(company, status="verified_open", deadline=None):
    return VerifiedCandidate(
        candidate=make_candidate(company=company, url=f"https://{company.lower()}.com/j", deadline=deadline),
        source_branch="career_pages",
        verification=Verification(status=status, http_status=200, reason="ok"),
    )


def test_parse_blank_accepts():
    assert parse_review_command("  ", 3) == Accept()


def test_parse_more_case_insensitive():
    assert parse_review_command("MORE", 3) == More()


def test_parse_numbers_with_commas_and_spaces_dedupes_and_sorts():
    assert parse_review_command("3, 1 3", 3) == Drop((1, 3))


def test_parse_out_of_range_is_invalid():
    result = parse_review_command("4", 3)
    assert isinstance(result, Invalid)
    assert "between 1 and 3" in result.message


def test_parse_garbage_is_invalid():
    assert isinstance(parse_review_command("drop acme", 3), Invalid)


def test_render_shortlist_numbers_rows_and_shows_status():
    text = render_shortlist([_item("Acme", deadline="2026-10-01"), _item("Beta", status="unverifiable")])
    lines = text.splitlines()
    assert lines[2].lstrip().startswith("1")
    assert "Acme" in lines[2] and "verified_open" in lines[2] and "2026-10-01" in lines[2]
    assert "Beta" in lines[3] and "unverifiable" in lines[3] and lines[3].rstrip().endswith("-")


def test_run_review_reprompts_until_valid():
    answers = iter(["nope", "9", "2"])
    printed = []
    result = run_review(
        [_item("Acme"), _item("Beta")],
        input_fn=lambda _prompt: next(answers),
        print_fn=printed.append,
    )
    assert result == Drop((2,))
    assert any("between 1 and 2" in line for line in printed)
