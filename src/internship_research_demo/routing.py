import re
from collections.abc import Callable
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from internship_research_demo.models import (
    BranchResult,
    Candidate,
    ResearchBrief,
    SourcedCandidate,
    VerifiedCandidate,
)

RESEARCH_MORE = "RESEARCH_MORE"
REVIEW = "REVIEW"
RANK = "RANK"
NO_RESULTS = "NO_RESULTS"

# Query parameters that identify a job posting and must survive normalization.
KEEP_QUERY_KEYS = frozenset({"gh_jid", "jobid", "job_id"})
EXCLUDED_TITLE_RE = re.compile(r"new grad|full[- ]time|graduate program|rotational", re.IGNORECASE)


def normalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    kept = sorted((k, v) for k, v in parse_qsl(parts.query) if k.lower() in KEEP_QUERY_KEYS)
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), urlencode(kept), "")
    )


def _norm_text(value: str) -> str:
    return " ".join(value.lower().split())


def company_title_key(candidate: Candidate) -> tuple[str, str]:
    return (_norm_text(candidate.company), _norm_text(candidate.title))


def is_excluded_title(title: str) -> bool:
    return bool(EXCLUDED_TITLE_RE.search(title))


def _completeness(candidate: Candidate) -> int:
    return sum(bool(value) for value in (candidate.deadline, candidate.compensation, candidate.risks))


def _merge_pair(current: SourcedCandidate, incoming: SourcedCandidate) -> SourcedCandidate:
    if _completeness(incoming.candidate) > _completeness(current.candidate):
        winner, loser = incoming, current
    else:
        winner, loser = current, incoming
    sources = list(winner.candidate.source_urls)
    sources += [u for u in loser.candidate.source_urls if u not in sources]
    return SourcedCandidate(
        candidate=winner.candidate.model_copy(update={"source_urls": sources}),
        source_branch=winner.source_branch,
    )


def merge_new_candidates(
    results: list[BranchResult],
    existing: list[Candidate],
    exclude_urls: set[str],
) -> list[SourcedCandidate]:
    """Combine one round of branch results into new, deduplicated candidates.

    Drops excluded titles, URLs in ``exclude_urls`` (already normalized), and
    anything matching an existing candidate by URL or company + title.
    """
    existing_urls = {normalize_url(c.url) for c in existing}
    existing_keys = {company_title_key(c) for c in existing}
    merged: list[SourcedCandidate] = []
    for result in results:
        for candidate in result.candidates:
            if is_excluded_title(candidate.title):
                continue
            url = normalize_url(candidate.url)
            key = company_title_key(candidate)
            if url in exclude_urls or url in existing_urls or key in existing_keys:
                continue
            incoming = SourcedCandidate(candidate=candidate, source_branch=result.branch)
            for index, current in enumerate(merged):
                if normalize_url(current.candidate.url) == url or company_title_key(current.candidate) == key:
                    merged[index] = _merge_pair(current, incoming)
                    break
            else:
                merged.append(incoming)
    return merged


def build_shortfall_note(viable: int, wanted: int, rounds: int) -> str:
    if viable >= wanted:
        return ""
    return (
        f"Only {viable} of {wanted} requested internships survived verification "
        f"after {rounds} research round(s)."
    )


URL_RE = re.compile(r"https?://[^\s)\]>\"'<|*`]+")


def extract_json(raw: str) -> str:
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end < start:
        raise ValueError("no JSON object found in output")
    return raw[start : end + 1]


def parse_brief(raw: str) -> ResearchBrief:
    return ResearchBrief.model_validate_json(extract_json(raw))


def research_guardrail(output: Any) -> tuple[bool, str]:
    """Validate the researcher's output and hand CrewAI clean JSON on success."""
    try:
        if isinstance(output.pydantic, ResearchBrief):
            brief = output.pydantic
        else:
            brief = parse_brief(output.raw)
    except ValueError as exc:
        return (False, f"Output must be a single JSON object matching ResearchBrief: {exc}")

    if not brief.candidates:
        return (False, "Return at least one candidate in the candidates list.")

    problems = []
    for index, candidate in enumerate(brief.candidates, start=1):
        label = f"candidate {index} ({candidate.company})"
        if not candidate.url.startswith(("http://", "https://")):
            problems.append(f"{label}: url must start with http:// or https://")
        elif not urlsplit(candidate.url).netloc:
            problems.append(f"{label}: url has no host")
        if not candidate.source_urls:
            problems.append(f"{label}: source_urls is empty")
    if problems:
        return (False, "; ".join(problems))
    return (True, brief.model_dump_json())


def allowed_urls_for(candidates: list[VerifiedCandidate]) -> set[str]:
    allowed: set[str] = set()
    for verified in candidates:
        allowed.add(verified.candidate.url)
        allowed.update(verified.candidate.source_urls)
    return allowed


def make_report_url_guardrail(allowed_urls: set[str]) -> Callable[[Any], tuple[bool, str]]:
    allowed = {normalize_url(u) for u in allowed_urls}

    def report_url_guardrail(output: Any) -> tuple[bool, str]:
        found = {u.rstrip(".,;:*`_") for u in URL_RE.findall(output.raw)}
        unknown = sorted(u for u in found if normalize_url(u) not in allowed)
        if unknown:
            return (
                False,
                "The report contains URLs that are not in the provided candidates. "
                "Use only each candidate's url or source_urls. Unknown URLs: "
                + ", ".join(unknown[:10]),
            )
        return (True, output.raw)

    return report_url_guardrail


def decide_route(
    *,
    viable: int,
    wanted: int,
    research_round: int,
    max_extra_rounds: int,
    force_more: bool,
    review_enabled: bool,
    reviewed_round: int,
    has_new: bool,
) -> str:
    rounds_left = research_round < max_extra_rounds
    if force_more and rounds_left:
        return RESEARCH_MORE
    if viable < wanted and rounds_left:
        return RESEARCH_MORE
    if review_enabled and reviewed_round < research_round and has_new:
        return REVIEW
    if viable == 0:
        return NO_RESULTS
    return RANK
