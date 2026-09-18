from typing import Literal

from pydantic import BaseModel, Field

EvidenceLevel = Literal["direct", "indirect", "missing"]
VerifyStatus = Literal["verified_open", "unverifiable", "dead"]


class Candidate(BaseModel):
    """One internship posting as reported by the researcher LLM."""

    company: str
    title: str
    url: str
    location: str
    work_mode: str
    field_fit: str
    degree_level_evidence: str
    internship_evidence: str
    cpt_opt_evidence: EvidenceLevel
    cpt_opt_note: str
    open_status_evidence: str
    deadline: str | None = None
    compensation: str | None = None
    risks: list[str] = Field(default_factory=list)
    source_urls: list[str]


class ResearchBrief(BaseModel):
    candidates: list[Candidate]


class Verification(BaseModel):
    """Result of the HTTP check. Set by Python only, never by the LLM."""

    status: VerifyStatus
    http_status: int | None = None
    reason: str


class BranchResult(BaseModel):
    branch: str
    candidates: list[Candidate] = Field(default_factory=list)
    error: str | None = None


class SourcedCandidate(BaseModel):
    candidate: Candidate
    source_branch: str


class VerifiedCandidate(SourcedCandidate):
    verification: Verification
