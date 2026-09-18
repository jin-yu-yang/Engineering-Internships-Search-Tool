import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from internship_research_demo.models import BranchResult, Candidate, SourcedCandidate

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
