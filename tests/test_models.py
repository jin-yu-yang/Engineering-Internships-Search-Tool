import pytest
from pydantic import ValidationError

from helpers import make_candidate
from internship_research_demo.models import (
    ResearchBrief,
    Verification,
    VerifiedCandidate,
)


def test_candidate_optional_fields_default():
    candidate = make_candidate()
    assert candidate.deadline is None
    assert candidate.compensation is None
    assert candidate.risks == []


def test_candidate_rejects_unknown_evidence_level():
    with pytest.raises(ValidationError):
        make_candidate(cpt_opt_evidence="probably")


def test_research_brief_round_trips_json():
    brief = ResearchBrief(candidates=[make_candidate()])
    assert ResearchBrief.model_validate_json(brief.model_dump_json()) == brief


def test_verified_candidate_serializes_nested_fields():
    verified = VerifiedCandidate(
        candidate=make_candidate(),
        source_branch="career_pages",
        verification=Verification(status="verified_open", http_status=200, reason="title match 100%"),
    )
    dumped = verified.model_dump()
    assert dumped["candidate"]["company"] == "Acme"
    assert dumped["source_branch"] == "career_pages"
    assert dumped["verification"]["status"] == "verified_open"


def test_verification_rejects_unknown_status():
    with pytest.raises(ValidationError):
        Verification(status="maybe", reason="x")
