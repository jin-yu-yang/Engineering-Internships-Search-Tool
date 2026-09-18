from types import SimpleNamespace

from helpers import make_candidate
from internship_research_demo.models import ResearchBrief, Verification, VerifiedCandidate
from internship_research_demo.routing import (
    allowed_urls_for,
    make_report_url_guardrail,
    parse_brief,
    research_guardrail,
)

VALID = ResearchBrief(candidates=[make_candidate()]).model_dump_json()


def output(raw, pydantic=None):
    return SimpleNamespace(raw=raw, pydantic=pydantic)


def test_research_guardrail_accepts_valid_json_and_returns_json():
    ok, data = research_guardrail(output(VALID))
    assert ok
    assert ResearchBrief.model_validate_json(data).candidates[0].company == "Acme"


def test_research_guardrail_accepts_fenced_json():
    ok, _ = research_guardrail(output("Here you go:\n```json\n" + VALID + "\n```"))
    assert ok


def test_research_guardrail_prefers_parsed_pydantic():
    ok, _ = research_guardrail(output("not json", pydantic=ResearchBrief(candidates=[make_candidate()])))
    assert ok


def test_research_guardrail_rejects_non_json():
    ok, message = research_guardrail(output("I found three great roles!"))
    assert not ok
    assert "ResearchBrief" in message


def test_research_guardrail_rejects_empty_candidates():
    ok, message = research_guardrail(output('{"candidates": []}'))
    assert not ok
    assert "at least one candidate" in message


def test_research_guardrail_rejects_bad_url_and_missing_sources():
    brief = ResearchBrief(
        candidates=[
            make_candidate(url="acme.com/jobs/1"),
            make_candidate(company="Beta", url="https://beta.com/j", source_urls=[]),
        ]
    )
    ok, message = research_guardrail(output(brief.model_dump_json()))
    assert not ok
    assert "candidate 1 (Acme): url must start with http:// or https://" in message
    assert "candidate 2 (Beta): source_urls is empty" in message


def test_parse_brief_raises_value_error_on_garbage():
    try:
        parse_brief("nothing here")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")


def _verified(**overrides):
    return VerifiedCandidate(
        candidate=make_candidate(**overrides),
        source_branch="career_pages",
        verification=Verification(status="verified_open", http_status=200, reason="ok"),
    )


def test_allowed_urls_include_url_and_sources():
    allowed = allowed_urls_for([_verified(source_urls=["https://news.example.com/acme"])])
    assert allowed == {"https://acme.com/jobs/1", "https://news.example.com/acme"}


def test_report_guardrail_accepts_known_urls_with_punctuation_and_variants():
    guardrail = make_report_url_guardrail({"https://acme.com/jobs/1"})
    report = "Apply at [Acme](https://acme.com/jobs/1). Also https://ACME.com/jobs/1/?utm=x, done."
    ok, data = guardrail(output(report))
    assert ok
    assert data == report


def test_report_guardrail_accepts_bold_markdown_url():
    guardrail = make_report_url_guardrail({"https://acme.com/jobs/1"})
    report = "Apply at **https://acme.com/jobs/1**."
    ok, data = guardrail(output(report))
    assert ok
    assert data == report


def test_report_guardrail_accepts_backtick_wrapped_url():
    guardrail = make_report_url_guardrail({"https://acme.com/jobs/1"})
    report = "Apply at `https://acme.com/jobs/1` today."
    ok, data = guardrail(output(report))
    assert ok
    assert data == report


def test_report_guardrail_accepts_italic_markdown_url():
    guardrail = make_report_url_guardrail({"https://acme.com/jobs/1"})
    report = "Apply at _https://acme.com/jobs/1_ today."
    ok, data = guardrail(output(report))
    assert ok
    assert data == report


def test_report_guardrail_rejects_unknown_urls():
    guardrail = make_report_url_guardrail({"https://acme.com/jobs/1"})
    ok, message = guardrail(output("See https://made-up.example.com/job"))
    assert not ok
    assert "https://made-up.example.com/job" in message
