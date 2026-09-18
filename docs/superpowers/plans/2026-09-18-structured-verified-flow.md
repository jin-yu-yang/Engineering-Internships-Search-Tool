# Structured, Verified Internship Research Flow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the linear internship-research Flow into a structured, verified pipeline: parallel structured research, deterministic URL verification, guardrails, a retry router, optional human review, and a single report write.

**Architecture:** The old `content_crew` is split into `ResearchCrew` (one researcher task, Pydantic output, guardrail) and `RankingCrew` (markdown report, URL guardrail). The Flow in `main.py` orchestrates: research (fan-out) → merge/dedupe → HTTP verification → router → optional review → rank → save. All decision logic lives in small pure modules (`seasons.py`, `models.py`, `verify.py`, `routing.py`, `review.py`, `report.py`) that are unit-tested without an LLM or network.

**Tech Stack:** Python 3.12 (project supports >=3.10,<3.14), CrewAI 1.15.22 (`crewai[tools]`), Pydantic v2, httpx 0.28 (installed with CrewAI), pytest, uv.

**Spec:** `docs/superpowers/specs/2026-09-18-structured-verified-flow-design.md`

## Global Constraints

- CrewAI pin: `crewai[tools]==1.15.22`.
- Python: `>=3.10,<3.14`; use `X | None` syntax, no 3.11+-only features.
- Router labels are uppercase constants `RESEARCH_MORE`, `REVIEW`, `RANK`, `NO_RESULTS`, and must never equal a Flow method name (CrewAI 1.15.22 rejects that).
- Only `@router` methods emit labels. `review_shortlist` feeds back into the router through `@router(or_(verify_urls, review_shortlist))`.
- When a task has a guardrail, CrewAI does not parse `output_pydantic` before the guardrail runs. The research guardrail parses raw JSON itself and returns the brief as a JSON string on success.
- `save_report` is the only code that writes report files. No task may set `output_file`.
- No hardcoded season strings like `"Summer 2026"` in `cli.py`, `main.py`, or README defaults.
- Automated tests make no live LLM or network calls.
- Run tests with `uv run pytest -q` from the repo root `/Users/jinyuyang/demo/internship_research_demo`.
- Every commit message ends with the trailer line `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`.

## File Map

| File | Status | Responsibility |
|---|---|---|
| `pyproject.toml` | modify | CrewAI 1.15.22 pin, pytest dev dependency, pytest config |
| `src/internship_research_demo/seasons.py` | create | Term math: current term, upcoming seasons, default season |
| `src/internship_research_demo/models.py` | create | Pydantic contracts between LLM steps and Python steps |
| `src/internship_research_demo/verify.py` | create | Async HTTP verification and response classification |
| `src/internship_research_demo/routing.py` | create | Route labels, URL normalization, merge/dedupe, guardrails, shortfall note, `decide_route` |
| `src/internship_research_demo/report.py` | create | "No qualifying internships found" report text |
| `src/internship_research_demo/review.py` | create | Review command parsing, shortlist table, prompt loop |
| `src/internship_research_demo/crews/research_crew/` | create | Researcher agent + structured research task |
| `src/internship_research_demo/crews/ranking_crew/` | create | Ranking analyst + report task |
| `src/internship_research_demo/crews/content_crew/` | delete | Replaced by the two crews |
| `src/internship_research_demo/main.py` | rewrite | Flow state, orchestration, crew seams |
| `src/internship_research_demo/cli.py` | modify | Season picker, dynamic default, `--review`, `--max-extra-rounds` |
| `README.md` | modify | Season default, new flow description, new flags |
| `tests/conftest.py`, `tests/helpers.py`, `tests/test_*.py` | create | Tests |

---

# Phase 1 — Foundation

### Task 1: Upgrade CrewAI and add the test harness

**Files:**
- Modify: `pyproject.toml`
- Create: `tests/conftest.py`
- Test: `tests/test_environment.py`

**Interfaces:**
- Consumes: nothing
- Produces: `uv run pytest -q` works; `tests/` is on `sys.path` (so tests can `from helpers import ...`); CrewAI tracing/telemetry is disabled for tests.

- [ ] **Step 1: Write the failing test**

Create `tests/test_environment.py`:

```python
import crewai


def test_crewai_version_is_pinned():
    assert crewai.__version__ == "1.15.22"
```

Create `tests/conftest.py`:

```python
import os

# Keep CrewAI from prompting about traces or sending telemetry during tests.
os.environ.setdefault("CREWAI_TRACING_ENABLED", "false")
os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")
```

- [ ] **Step 2: Upgrade CrewAI and add pytest**

Run:

```bash
uv add "crewai[tools]==1.15.22"
```

```bash
uv add --dev pytest
```

Then append to `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["tests"]
```

Confirm `pyproject.toml` now contains `"crewai[tools]==1.15.22"` in `dependencies` and a `[dependency-groups]` table with `dev = ["pytest>=..."]`.

- [ ] **Step 3: Run the test to verify it passes**

Run: `uv run pytest -q tests/test_environment.py`
Expected: `1 passed`

- [ ] **Step 4: Confirm the existing CLI still imports**

Run: `uv run internship-agent --help`
Expected: argparse help text beginning `usage: internship-agent`, no traceback.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock tests/conftest.py tests/test_environment.py
git commit -m "build: upgrade crewai to 1.15.22 and add pytest harness" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 2: Season logic

**Files:**
- Create: `src/internship_research_demo/seasons.py`
- Test: `tests/test_seasons.py`

**Interfaces:**
- Consumes: nothing
- Produces:
  - `current_term(today: date) -> tuple[str, int]`
  - `upcoming_seasons(today: date, n: int = 5) -> list[str]`
  - `default_season(today: date) -> str`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_seasons.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest -q tests/test_seasons.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'internship_research_demo.seasons'`

- [ ] **Step 3: Implement**

Create `src/internship_research_demo/seasons.py`:

```python
from datetime import date

TERMS = ("Winter", "Spring", "Summer", "Fall")


def current_term(today: date) -> tuple[str, int]:
    """Map a date to its academic term. December belongs to next year's Winter."""
    month = today.month
    if month == 12:
        return ("Winter", today.year + 1)
    if month <= 2:
        return ("Winter", today.year)
    if month <= 5:
        return ("Spring", today.year)
    if month <= 8:
        return ("Summer", today.year)
    return ("Fall", today.year)


def _next_term(term: str, year: int) -> tuple[str, int]:
    index = TERMS.index(term)
    if index == len(TERMS) - 1:
        return (TERMS[0], year + 1)
    return (TERMS[index + 1], year)


def upcoming_seasons(today: date, n: int = 5) -> list[str]:
    """The current term followed by the next n - 1 terms."""
    term, year = current_term(today)
    seasons = []
    for _ in range(n):
        seasons.append(f"{term} {year}")
        term, year = _next_term(term, year)
    return seasons


def default_season(today: date) -> str:
    """The first Summer term strictly after the current term."""
    term, year = _next_term(*current_term(today))
    while term != "Summer":
        term, year = _next_term(term, year)
    return f"{term} {year}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest -q tests/test_seasons.py`
Expected: all passed

- [ ] **Step 5: Commit**

```bash
git add src/internship_research_demo/seasons.py tests/test_seasons.py
git commit -m "feat: compute internship seasons from today's date" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 3: Data models

**Files:**
- Create: `src/internship_research_demo/models.py`
- Create: `tests/helpers.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Consumes: nothing
- Produces (all Pydantic `BaseModel`):
  - `EvidenceLevel = Literal["direct", "indirect", "missing"]`
  - `VerifyStatus = Literal["verified_open", "unverifiable", "dead"]`
  - `Candidate(company, title, url, location, work_mode, field_fit, degree_level_evidence, internship_evidence, cpt_opt_evidence: EvidenceLevel, cpt_opt_note, open_status_evidence, deadline: str | None = None, compensation: str | None = None, risks: list[str] = [], source_urls: list[str])`
  - `ResearchBrief(candidates: list[Candidate])`
  - `Verification(status: VerifyStatus, http_status: int | None = None, reason: str)`
  - `BranchResult(branch: str, candidates: list[Candidate] = [], error: str | None = None)`
  - `SourcedCandidate(candidate: Candidate, source_branch: str)`
  - `VerifiedCandidate(SourcedCandidate)` adding `verification: Verification`
  - Test helper `make_candidate(**overrides) -> Candidate` in `tests/helpers.py`

- [ ] **Step 1: Write the test helper and failing tests**

Create `tests/helpers.py`:

```python
from internship_research_demo.models import Candidate


def make_candidate(**overrides) -> Candidate:
    data = {
        "company": "Acme",
        "title": "Software Engineer Intern",
        "url": "https://acme.com/jobs/1",
        "location": "Austin, TX",
        "work_mode": "hybrid",
        "field_fit": "Backend services work",
        "degree_level_evidence": "BS/MS students eligible",
        "internship_evidence": "12-week summer internship",
        "cpt_opt_evidence": "direct",
        "cpt_opt_note": "Posting says CPT/OPT accepted",
        "open_status_evidence": "Apply button is active",
        "source_urls": ["https://acme.com/jobs/1"],
    }
    data.update(overrides)
    return Candidate(**data)
```

Create `tests/test_models.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest -q tests/test_models.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'internship_research_demo.models'`

- [ ] **Step 3: Implement**

Create `src/internship_research_demo/models.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest -q tests/test_models.py`
Expected: all passed

- [ ] **Step 5: Commit**

```bash
git add src/internship_research_demo/models.py tests/helpers.py tests/test_models.py
git commit -m "feat: add structured candidate and verification models" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 4: URL verification

**Files:**
- Create: `src/internship_research_demo/verify.py`
- Test: `tests/test_verify.py`

**Interfaces:**
- Consumes: `Candidate`, `Verification` from `models.py`
- Produces:
  - `significant_title_tokens(title: str) -> set[str]`
  - `classify_response(status_code: int, final_url: str, html: str, title: str) -> Verification`
  - `async verify_all(candidates: list[Candidate], client: httpx.AsyncClient | None = None, concurrency: int = 8, timeout: float = 10.0) -> list[Verification]` (results in the same order as `candidates`)
  - Constants `CLOSED_PHRASES`, `CLOSED_REDIRECT_PATTERNS`, `TITLE_MATCH_THRESHOLD = 0.6`

Rules, evaluated in order (first match wins):

| # | Condition | Status | `reason` |
|---|---|---|---|
| 1 | HTTP 404 or 410 | `dead` | `"404"` / `"410"` |
| 2 | Final URL matches a closed-redirect pattern | `dead` | `"closed redirect: <url>"` |
| 3 | HTTP 200 and page text contains a closed phrase | `dead` | `"closed phrase: <phrase>"` |
| 4 | HTTP 200 and ≥60% of significant title tokens appear in page text | `verified_open` | `"title match NN%"` |
| 5 | HTTP 200, title has no significant tokens | `unverifiable` | `"title too generic to match"` |
| 6 | HTTP 200, title not matched | `unverifiable` | `"title not found (likely JS-rendered)"` |
| 7 | Any other status | `unverifiable` | `"http <code>"` |
| 8 | Timeout | `unverifiable` | `"timeout"` |
| 9 | Other `httpx.HTTPError` | `unverifiable` | `"connection error: <ExceptionClassName>"` |

Page text is the HTML with `<script>` and `<style>` blocks removed, remaining tags replaced by spaces, lowercased, and whitespace collapsed. So a title that appears only inside JavaScript does not count as a match.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_verify.py`:

```python
import asyncio

import httpx
import pytest

from helpers import make_candidate
from internship_research_demo.verify import (
    classify_response,
    significant_title_tokens,
    verify_all,
)

TITLE = "Software Engineer Intern"
JOB_HTML = "<html><body><h1>Software Engineer Intern</h1><button>Apply now</button></body></html>"


def test_significant_title_tokens_drop_stopwords_and_years():
    assert significant_title_tokens("Machine Learning Intern - Summer 2027") == {"machine", "learning"}


@pytest.mark.parametrize("code", [404, 410])
def test_gone_status_is_dead(code):
    result = classify_response(code, "https://acme.com/jobs/1", "", TITLE)
    assert (result.status, result.http_status, result.reason) == ("dead", code, str(code))


def test_closed_redirect_is_dead():
    result = classify_response(200, "https://boards.greenhouse.io/acme?error=true", JOB_HTML, TITLE)
    assert result.status == "dead"
    assert result.reason.startswith("closed redirect")


def test_closed_phrase_beats_title_match():
    html = JOB_HTML.replace("Apply now", "Sorry, this job is closed")
    result = classify_response(200, "https://acme.com/jobs/1", html, TITLE)
    assert (result.status, result.reason) == ("dead", "closed phrase: job is closed")


def test_title_match_is_verified_open():
    result = classify_response(200, "https://acme.com/jobs/1", JOB_HTML, TITLE)
    assert result.status == "verified_open"
    assert result.reason == "title match 100%"


def test_title_only_in_script_is_unverifiable():
    html = "<html><body><div id='root'></div><script>var t = 'Software Engineer Intern';</script></body></html>"
    result = classify_response(200, "https://acme.com/jobs/1", html, TITLE)
    assert (result.status, result.reason) == ("unverifiable", "title not found (likely JS-rendered)")


def test_generic_title_is_unverifiable():
    result = classify_response(200, "https://acme.com/jobs/1", JOB_HTML, "Intern")
    assert (result.status, result.reason) == ("unverifiable", "title too generic to match")


@pytest.mark.parametrize("code", [401, 403, 429, 500, 503])
def test_other_status_is_unverifiable(code):
    result = classify_response(code, "https://acme.com/jobs/1", "", TITLE)
    assert (result.status, result.reason) == ("unverifiable", f"http {code}")


def test_verify_all_end_to_end_with_mock_transport():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "boards.example.com":
            return httpx.Response(200, text="<html>All jobs</html>")
        path = request.url.path
        if path == "/open":
            return httpx.Response(200, text=JOB_HTML)
        if path == "/gone":
            return httpx.Response(404)
        if path == "/moved":
            return httpx.Response(302, headers={"Location": "https://boards.example.com/acme?error=true"})
        if path == "/slow":
            raise httpx.ReadTimeout("timed out", request=request)
        if path == "/down":
            raise httpx.ConnectError("refused", request=request)
        return httpx.Response(403)

    paths = ["open", "gone", "moved", "slow", "down", "blocked"]
    candidates = [make_candidate(url=f"https://acme.example.com/{p}") for p in paths]

    async def run():
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, follow_redirects=True) as client:
            return await verify_all(candidates, client=client)

    results = asyncio.run(run())

    assert [r.status for r in results] == [
        "verified_open",
        "dead",
        "dead",
        "unverifiable",
        "unverifiable",
        "unverifiable",
    ]
    assert results[3].reason == "timeout"
    assert results[4].reason == "connection error: ConnectError"
    assert results[5].reason == "http 403"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest -q tests/test_verify.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'internship_research_demo.verify'`

- [ ] **Step 3: Implement**

Create `src/internship_research_demo/verify.py`:

```python
import asyncio
import re

import httpx

from internship_research_demo.models import Candidate, Verification

CLOSED_PHRASES = (
    "no longer accepting applications",
    "position has been filled",
    "job is closed",
    "this job has expired",
    "posting has been closed",
    "no longer available",
)
CLOSED_REDIRECT_PATTERNS = (re.compile(r"[?&]error=true\b"),)
TITLE_STOPWORDS = frozenset(
    {
        "intern",
        "interns",
        "internship",
        "internships",
        "the",
        "and",
        "for",
        "with",
        "summer",
        "fall",
        "spring",
        "winter",
        "coop",
    }
)
TITLE_MATCH_THRESHOLD = 0.6
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

_WORD_RE = re.compile(r"[a-z0-9]+")
_SCRIPT_STYLE_RE = re.compile(r"<(script|style)\b.*?</\1>", re.IGNORECASE | re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")
_YEAR_RE = re.compile(r"\d{4}")


def _page_text(html: str) -> str:
    text = _SCRIPT_STYLE_RE.sub(" ", html)
    text = _TAG_RE.sub(" ", text)
    return " ".join(text.lower().split())


def significant_title_tokens(title: str) -> set[str]:
    return {
        word
        for word in _WORD_RE.findall(title.lower())
        if len(word) >= 3 and word not in TITLE_STOPWORDS and not _YEAR_RE.fullmatch(word)
    }


def _result(status: str, http_status: int | None, reason: str) -> Verification:
    return Verification(status=status, http_status=http_status, reason=reason)


def classify_response(status_code: int, final_url: str, html: str, title: str) -> Verification:
    if status_code in (404, 410):
        return _result("dead", status_code, str(status_code))
    for pattern in CLOSED_REDIRECT_PATTERNS:
        if pattern.search(final_url):
            return _result("dead", status_code, f"closed redirect: {final_url}")
    if status_code != 200:
        return _result("unverifiable", status_code, f"http {status_code}")

    text = _page_text(html)
    for phrase in CLOSED_PHRASES:
        if phrase in text:
            return _result("dead", status_code, f"closed phrase: {phrase}")

    tokens = significant_title_tokens(title)
    if not tokens:
        return _result("unverifiable", status_code, "title too generic to match")
    ratio = len(tokens & set(_WORD_RE.findall(text))) / len(tokens)
    if ratio >= TITLE_MATCH_THRESHOLD:
        return _result("verified_open", status_code, f"title match {ratio:.0%}")
    return _result("unverifiable", status_code, "title not found (likely JS-rendered)")


async def _verify_one(
    client: httpx.AsyncClient, candidate: Candidate, semaphore: asyncio.Semaphore
) -> Verification:
    async with semaphore:
        try:
            response = await client.get(candidate.url)
        except httpx.TimeoutException:
            return _result("unverifiable", None, "timeout")
        except httpx.HTTPError as exc:
            return _result("unverifiable", None, f"connection error: {type(exc).__name__}")
    return classify_response(response.status_code, str(response.url), response.text, candidate.title)


async def verify_all(
    candidates: list[Candidate],
    client: httpx.AsyncClient | None = None,
    concurrency: int = 8,
    timeout: float = 10.0,
) -> list[Verification]:
    owns_client = client is None
    if client is None:
        client = httpx.AsyncClient(
            follow_redirects=True,
            timeout=timeout,
            headers={"User-Agent": USER_AGENT},
        )
    semaphore = asyncio.Semaphore(concurrency)
    try:
        return list(
            await asyncio.gather(*(_verify_one(client, c, semaphore) for c in candidates))
        )
    finally:
        if owns_client:
            await client.aclose()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest -q tests/test_verify.py`
Expected: all passed

- [ ] **Step 5: Commit**

```bash
git add src/internship_research_demo/verify.py tests/test_verify.py
git commit -m "feat: verify posting URLs over HTTP with three-way status" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 5: Routing helpers — normalization, merge/dedupe, shortfall note

**Files:**
- Create: `src/internship_research_demo/routing.py`
- Test: `tests/test_routing.py`

**Interfaces:**
- Consumes: `BranchResult`, `Candidate`, `SourcedCandidate` from `models.py`
- Produces:
  - Label constants: `RESEARCH_MORE = "RESEARCH_MORE"`, `REVIEW = "REVIEW"`, `RANK = "RANK"`, `NO_RESULTS = "NO_RESULTS"`
  - `normalize_url(url: str) -> str`
  - `company_title_key(candidate: Candidate) -> tuple[str, str]`
  - `is_excluded_title(title: str) -> bool`
  - `merge_new_candidates(results: list[BranchResult], existing: list[Candidate], exclude_urls: set[str]) -> list[SourcedCandidate]` (`exclude_urls` must already be normalized)
  - `build_shortfall_note(viable: int, wanted: int, rounds: int) -> str` (empty string when `viable >= wanted`)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_routing.py`:

```python
from helpers import make_candidate
from internship_research_demo.models import BranchResult
from internship_research_demo.routing import (
    build_shortfall_note,
    is_excluded_title,
    merge_new_candidates,
    normalize_url,
)


def test_normalize_url_strips_query_fragment_trailing_slash_and_host_case():
    assert (
        normalize_url("HTTPS://Jobs.Acme.com/Careers/123/?utm_source=x#apply")
        == "https://jobs.acme.com/Careers/123"
    )


def test_normalize_url_keeps_job_id_query_params():
    assert (
        normalize_url("https://boards.greenhouse.io/acme/jobs?utm=1&gh_jid=42")
        == "https://boards.greenhouse.io/acme/jobs?gh_jid=42"
    )
    assert (
        normalize_url("https://x.wd1.myworkdayjobs.com/job?jobId=7")
        == "https://x.wd1.myworkdayjobs.com/job?jobId=7"
    )


def test_is_excluded_title():
    assert is_excluded_title("New Grad Software Engineer")
    assert is_excluded_title("Full-Time Data Scientist")
    assert is_excluded_title("Full time Engineer")
    assert is_excluded_title("Engineering Graduate Program")
    assert is_excluded_title("Rotational Engineer")
    assert not is_excluded_title("Software Engineer Intern")


def test_merge_dedupes_by_url_keeps_more_complete_and_unions_sources():
    a = make_candidate(url="https://acme.com/jobs/1?utm=x", source_urls=["https://acme.com/jobs/1"])
    b = make_candidate(
        url="https://acme.com/jobs/1/",
        deadline="2026-10-01",
        source_urls=["https://linkedin.com/jobs/9"],
    )
    merged = merge_new_candidates(
        [
            BranchResult(branch="career_pages", candidates=[a]),
            BranchResult(branch="job_boards", candidates=[b]),
        ],
        existing=[],
        exclude_urls=set(),
    )
    assert len(merged) == 1
    assert merged[0].candidate.deadline == "2026-10-01"
    assert merged[0].source_branch == "job_boards"
    assert merged[0].candidate.source_urls == [
        "https://linkedin.com/jobs/9",
        "https://acme.com/jobs/1",
    ]


def test_merge_dedupes_by_company_and_title_first_wins_on_tie():
    a = make_candidate(url="https://acme.com/a")
    b = make_candidate(company="  ACME ", title="software   engineer intern", url="https://lnkd.in/b")
    merged = merge_new_candidates(
        [BranchResult(branch="career_pages", candidates=[a, b])], existing=[], exclude_urls=set()
    )
    assert [m.candidate.url for m in merged] == ["https://acme.com/a"]


def test_merge_drops_excluded_titles_known_urls_and_existing_candidates():
    new = [
        make_candidate(title="New Grad Engineer", url="https://acme.com/ng"),
        make_candidate(company="Beta", url="https://beta.com/jobs/seen"),
        make_candidate(company="Gamma", url="https://gamma.com/jobs/rejected"),
        make_candidate(company="Initech", title="Data Intern", url="https://other.com/j"),
        make_candidate(company="Globex", url="https://globex.com/j"),
    ]
    existing = [make_candidate(company="Initech", title="Data Intern", url="https://initech.com/j")]
    merged = merge_new_candidates(
        [BranchResult(branch="job_boards", candidates=new)],
        existing=existing,
        exclude_urls={"https://beta.com/jobs/seen", "https://gamma.com/jobs/rejected"},
    )
    assert [m.candidate.company for m in merged] == ["Globex"]


def test_shortfall_note():
    assert build_shortfall_note(3, 3, 1) == ""
    assert build_shortfall_note(4, 3, 1) == ""
    assert build_shortfall_note(2, 3, 3) == (
        "Only 2 of 3 requested internships survived verification after 3 research round(s)."
    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest -q tests/test_routing.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'internship_research_demo.routing'`

- [ ] **Step 3: Implement**

Create `src/internship_research_demo/routing.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest -q tests/test_routing.py`
Expected: all passed

- [ ] **Step 5: Commit**

```bash
git add src/internship_research_demo/routing.py tests/test_routing.py
git commit -m "feat: add URL normalization and candidate merge/dedupe" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 6: Guardrails

**Files:**
- Modify: `src/internship_research_demo/routing.py` (append)
- Test: `tests/test_guardrails.py`

**Interfaces:**
- Consumes: `ResearchBrief`, `VerifiedCandidate` from `models.py`; `normalize_url` from Task 5
- Produces:
  - `extract_json(raw: str) -> str`: raises `ValueError` if no `{...}` object is found
  - `parse_brief(raw: str) -> ResearchBrief`: raises `ValueError` (including Pydantic `ValidationError`)
  - `research_guardrail(output) -> tuple[bool, str]`: `output` has `.raw: str` and `.pydantic`. On success it returns `(True, brief_json)`.
  - `allowed_urls_for(candidates: list[VerifiedCandidate]) -> set[str]`: raw `url` plus `source_urls` for every candidate
  - `make_report_url_guardrail(allowed_urls: set[str]) -> Callable[[Any], tuple[bool, str]]`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_guardrails.py`:

```python
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


def test_report_guardrail_rejects_unknown_urls():
    guardrail = make_report_url_guardrail({"https://acme.com/jobs/1"})
    ok, message = guardrail(output("See https://made-up.example.com/job"))
    assert not ok
    assert "https://made-up.example.com/job" in message
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest -q tests/test_guardrails.py`
Expected: FAIL with `ImportError: cannot import name 'allowed_urls_for'`

- [ ] **Step 3: Implement**

In `src/internship_research_demo/routing.py`, change the imports at the top to:

```python
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
```

Append to the end of `routing.py`:

```python
URL_RE = re.compile(r"https?://[^\s)\]>\"'<|]+")


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
        found = {u.rstrip(".,;:") for u in URL_RE.findall(output.raw)}
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest -q tests/test_guardrails.py tests/test_routing.py`
Expected: all passed

- [ ] **Step 5: Commit**

```bash
git add src/internship_research_demo/routing.py tests/test_guardrails.py
git commit -m "feat: add research and report URL guardrails" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 7: "No results" report

**Files:**
- Create: `src/internship_research_demo/report.py`
- Test: `tests/test_report.py`

**Interfaces:**
- Consumes: nothing
- Produces: `build_no_results_report(constraints: dict[str, str], rounds: int, status_counts: dict[str, int], branch_counts: dict[str, int]) -> str`

- [ ] **Step 1: Write the failing test**

Create `tests/test_report.py`:

```python
from internship_research_demo.report import build_no_results_report


def test_no_results_report_lists_constraints_counts_and_branches():
    text = build_no_results_report(
        constraints={"Field": "Robotics & controls", "Season": "Summer 2027"},
        rounds=3,
        status_counts={"dead": 4, "unverifiable": 0},
        branch_counts={"job_boards": 1, "career_pages": 3},
    )
    assert text.startswith("# No qualifying internships found\n")
    assert "after 3 research round(s)" in text
    assert "- Field: Robotics & controls" in text
    assert "- Season: Summer 2027" in text
    assert "- verified_open: 0" in text
    assert "- dead: 4" in text
    assert text.index("- career_pages: 3") < text.index("- job_boards: 1")
    assert text.endswith("\n")


def test_no_results_report_with_no_branch_output():
    text = build_no_results_report(constraints={}, rounds=1, status_counts={}, branch_counts={})
    assert "## Candidates found per research branch\n\n- none" in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest -q tests/test_report.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'internship_research_demo.report'`

- [ ] **Step 3: Implement**

Create `src/internship_research_demo/report.py`:

```python
VERIFY_STATUSES = ("verified_open", "unverifiable", "dead")


def build_no_results_report(
    constraints: dict[str, str],
    rounds: int,
    status_counts: dict[str, int],
    branch_counts: dict[str, int],
) -> str:
    lines = [
        "# No qualifying internships found",
        "",
        f"No postings survived research and URL verification after {rounds} research round(s).",
        "",
        "## Search constraints",
        "",
    ]
    lines += [f"- {name}: {value}" for name, value in constraints.items()] or ["- none"]
    lines += ["", "## Verification results", ""]
    lines += [f"- {status}: {status_counts.get(status, 0)}" for status in VERIFY_STATUSES]
    lines += ["", "## Candidates found per research branch", ""]
    lines += [f"- {branch}: {count}" for branch, count in sorted(branch_counts.items())] or ["- none"]
    lines += [
        "",
        "## Next steps",
        "",
        "- Broaden the field, location, or work modes.",
        "- Re-run with `--no-require-opt-cpt` or `--allow-closed-for-context` to see near misses.",
    ]
    return "\n".join(lines) + "\n"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest -q tests/test_report.py`
Expected: all passed

- [ ] **Step 5: Commit**

```bash
git add src/internship_research_demo/report.py tests/test_report.py
git commit -m "feat: add no-results report builder" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 8: Research and ranking crews

**Files:**
- Create: `src/internship_research_demo/crews/research_crew/__init__.py` (empty)
- Create: `src/internship_research_demo/crews/research_crew/research_crew.py`
- Create: `src/internship_research_demo/crews/research_crew/config/agents.yaml`
- Create: `src/internship_research_demo/crews/research_crew/config/tasks.yaml`
- Create: `src/internship_research_demo/crews/ranking_crew/__init__.py` (empty)
- Create: `src/internship_research_demo/crews/ranking_crew/ranking_crew.py`
- Create: `src/internship_research_demo/crews/ranking_crew/config/agents.yaml`
- Create: `src/internship_research_demo/crews/ranking_crew/config/tasks.yaml`
- Test: `tests/test_crews.py`

(`crews/content_crew/` stays until Task 9 because `main.py` still imports it.)

**Interfaces:**
- Consumes: `ResearchBrief` (models), `research_guardrail`, `make_report_url_guardrail` (routing)
- Produces:
  - `ResearchCrew().crew() -> Crew` with one task `research_task` (`output_pydantic=ResearchBrief`, `guardrail=research_guardrail`, `guardrail_max_retries=2`, no `output_file`)
  - `RankingCrew(allowed_urls: set[str] | None = None).crew() -> Crew` with one task `ranking_report_task` (`markdown=True`, URL guardrail, `guardrail_max_retries=2`, no `output_file`)
  - Research template variables: `season, student_status, source_focus, applied_field, role_family, degree_levels, work_location, work_modes, sponsorship_filter, application_status_filter, employment_type_filter, additional_keywords, round_hint, exclude_urls, opportunity_count`
  - Ranking template variables: `rank_count, season, applied_field, student_status, candidates_json, shortfall_note, ranking_priorities, degree_levels, work_location, work_modes, sponsorship_filter`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_crews.py`:

```python
from types import SimpleNamespace

import pytest

from internship_research_demo.crews.ranking_crew.ranking_crew import RankingCrew
from internship_research_demo.crews.research_crew.research_crew import ResearchCrew
from internship_research_demo.models import ResearchBrief


@pytest.fixture(autouse=True)
def fake_api_keys(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("SERPER_API_KEY", "test")


def test_research_crew_task_is_structured_and_guarded():
    (task,) = ResearchCrew().crew().tasks
    assert task.output_pydantic is ResearchBrief
    assert task.guardrail is not None
    assert task.guardrail_max_retries == 2
    assert task.output_file is None


def test_ranking_crew_task_has_no_output_file_and_url_guardrail():
    (task,) = RankingCrew(allowed_urls={"https://acme.com/jobs/1"}).crew().tasks
    assert task.output_file is None
    assert task.markdown is True
    assert task.guardrail_max_retries == 2
    ok, _ = task.guardrail(SimpleNamespace(raw="Apply: https://acme.com/jobs/1", pydantic=None))
    assert ok
    bad, _ = task.guardrail(SimpleNamespace(raw="Apply: https://invented.example.com/x", pydantic=None))
    assert not bad
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest -q tests/test_crews.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'internship_research_demo.crews.ranking_crew'`

- [ ] **Step 3: Create the research crew**

Create empty `src/internship_research_demo/crews/research_crew/__init__.py`.

Create `src/internship_research_demo/crews/research_crew/config/agents.yaml`:

```yaml
internship_researcher:
  role: >
    Applied Science and Engineering Internship Researcher
  goal: >
    Find current {season} internship opportunities in {applied_field} for
    {degree_levels} who are {student_status}, constrained by {work_location},
    {work_modes}, and the rules: {sponsorship_filter};
    {application_status_filter}; {employment_type_filter}.
  backstory: >
    You are a careful university career researcher who works with F-1
    international students in applied science and engineering. You verify each opportunity
    against primary employer pages whenever possible, prefer current job
    postings over third-party summaries, cite sources, and flag uncertainty
    instead of overstating visa or work-authorization support.
  allow_delegation: false
  inject_date: true
  date_format: "%Y-%m-%d"
```

Create `src/internship_research_demo/crews/research_crew/config/tasks.yaml`:

```yaml
research_task:
  description: >
    Research current {season} internship opportunities for {student_status}.

    Source focus for this search: {source_focus}

    User-selected search constraints:
    - applied science or engineering field: {applied_field}
    - role keywords: {role_family}
    - candidate degree level: {degree_levels}
    - work location or region: {work_location}
    - acceptable work modes: {work_modes}
    - work authorization rule: {sponsorship_filter}
    - application status rule: {application_status_filter}
    - employment type rule: {employment_type_filter}
    - additional search keywords: {additional_keywords}

    {round_hint}

    Do not return any posting whose URL is in this exclusion list: {exclude_urls}

    Find more than {opportunity_count} candidates if possible, then filter
    down to the strongest matches. Use employer career pages or official job
    posts as primary evidence whenever possible. If CPT/OPT support is
    required, include only opportunities with direct CPT/OPT language or
    credible employer evidence that CPT/OPT is accepted for internships. If
    CPT/OPT support is not required, still capture work authorization language
    and visa risk.

    Treat application status as a hard eligibility filter. Do not include any
    posting if the employer page says the application is closed, expired,
    filled, no longer accepting applications, or unavailable. If application
    status is unclear, verify against the official employer page before using
    it and mark the freshness evidence explicitly.

    Treat employment type as a hard eligibility filter. Search for internship,
    intern, co-op, or university internship postings only. Do not include New
    Grad, graduate program, full-time, permanent, returnship, rotational
    program, or long-term employment roles, even if they otherwise match the
    field.

    Treat degree level as an eligibility filter. Prefer postings whose minimum
    qualifications match {degree_levels}. If a posting is explicitly PhD-only,
    include it only when PhD students are selected. If a posting excludes the
    selected degree level, do not include it.

    For each candidate, fill these fields:
    - company
    - title: the exact role title from the posting
    - url: the application or job posting URL, starting with http:// or https://
    - location
    - work_mode: onsite, hybrid, remote, or unknown
    - field_fit: why it fits {applied_field}
    - degree_level_evidence: eligible degree level and evidence from the posting
    - internship_evidence: evidence the role is an internship or co-op, not New Grad or full-time
    - cpt_opt_evidence: exactly one of direct, indirect, or missing
    - cpt_opt_note: the CPT/OPT or work authorization language, or why it is missing
    - open_status_evidence: evidence that applications are still open
    - deadline: application deadline or freshness signal, or null
    - compensation: compensation, team, or technical scope, or null
    - risks: a list of risks, caveats, or missing facts
    - source_urls: every URL you used for this candidate, at least one
  expected_output: >
    A single JSON object with one key, "candidates", whose value is a list of
    candidate objects that use exactly the fields listed above. Return only the
    JSON object, with no markdown fences and no commentary.
  agent: internship_researcher
```

Create `src/internship_research_demo/crews/research_crew/research_crew.py`:

```python
from crewai import Agent, Crew, Process, Task
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import ScrapeWebsiteTool, SerperDevTool

from internship_research_demo.models import ResearchBrief
from internship_research_demo.routing import research_guardrail


@CrewBase
class ResearchCrew:
    """Crew that researches internship candidates from one source focus."""

    agents: list[BaseAgent]
    tasks: list[Task]

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    @agent
    def internship_researcher(self) -> Agent:
        return Agent(
            config=self.agents_config["internship_researcher"],  # type: ignore[index]
            tools=[SerperDevTool(), ScrapeWebsiteTool()],
            max_iter=12,
            verbose=True,
        )

    @task
    def research_task(self) -> Task:
        return Task(
            config=self.tasks_config["research_task"],  # type: ignore[index]
            output_pydantic=ResearchBrief,
            guardrail=research_guardrail,
            guardrail_max_retries=2,
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )
```

- [ ] **Step 4: Create the ranking crew**

Create empty `src/internship_research_demo/crews/ranking_crew/__init__.py`.

Create `src/internship_research_demo/crews/ranking_crew/config/agents.yaml`:

```yaml
ranking_analyst:
  role: >
    Internship Ranking Analyst
  goal: >
    Rank the best {rank_count} internship opportunities for an
    international student seeking {season} {applied_field} internships.
  backstory: >
    You turn messy internship research into concise, decision-ready reports.
    You score opportunities using practical student criteria: field fit,
    evidence of CPT/OPT compatibility when requested, application freshness,
    technical depth, location fit, compensation or brand signal when available,
    and risk.
  allow_delegation: false
```

Create `src/internship_research_demo/crews/ranking_crew/config/tasks.yaml`:

```yaml
ranking_report_task:
  description: >
    Create a ranked markdown report of the top {rank_count} {season}
    {applied_field} internship opportunities for {student_status}, using only
    the candidates below.

    Candidates as JSON. Each item has the researcher's findings under
    "candidate", the research branch under "source_branch", and an automated
    HTTP check under "verification". The verification status is either
    verified_open (the posting page loaded and shows the role title) or
    unverifiable (the page could not be checked automatically, often because
    it is rendered with JavaScript or blocks bots). Dead links were already
    removed.

    {candidates_json}

    Shortfall note: {shortfall_note}

    User ranking priorities: {ranking_priorities}

    Ranking rules:
    - Rank only the candidates above. Never add, invent, or look up other opportunities.
    - Use only URLs that appear in a candidate's url or source_urls fields.
    - Apply the user's degree level ({degree_levels}), work location
      ({work_location}), work modes ({work_modes}), and work authorization
      rule ({sponsorship_filter}).
    - When CPT/OPT is required, prefer direct CPT/OPT evidence over indirect
      employer evidence.
    - Prefer roles with clear {applied_field} responsibilities.
    - Penalize missing deadlines and unclear work authorization language.

    Score each opportunity out of 100 using this rubric unless the user's
    ranking priorities strongly imply different weights:
    - 30 points: fit for {applied_field} and role keywords
    - 25 points: work authorization fit and CPT/OPT evidence
    - 15 points: confirmed open application status, freshness, and application
      clarity. A candidate whose verification status is unverifiable can earn
      at most 7 of these 15 points.
    - 15 points: location and work-mode fit
    - 10 points: degree-level fit, technical depth, mentorship, or team quality
    - 5 points: compensation, brand signal, or career upside

    The report must include:
    - title
    - short methodology that mentions the automated URL check
    - ranked table with score out of 100 and a Verification column
    - one section per opportunity with evidence, fit, CPT/OPT notes, risks,
      degree-level match, verification status, and next action
    - "Watchouts" section for uncertainty; if the shortfall note is not
      "none", state it there
    - source links
  expected_output: >
    A concise markdown report without code fences, ranking exactly
    {rank_count} internship opportunities. Every ranked item must include
    source links, a CPT/OPT evidence note, and its verification status.
  agent: ranking_analyst
```

Create `src/internship_research_demo/crews/ranking_crew/ranking_crew.py`:

```python
from crewai import Agent, Crew, Process, Task
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai.project import CrewBase, agent, crew, task

from internship_research_demo.routing import make_report_url_guardrail


@CrewBase
class RankingCrew:
    """Crew that ranks verified internship candidates into a markdown report."""

    agents: list[BaseAgent]
    tasks: list[Task]

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    def __init__(self, allowed_urls: set[str] | None = None) -> None:
        self.allowed_urls = set(allowed_urls or ())

    @agent
    def ranking_analyst(self) -> Agent:
        return Agent(
            config=self.agents_config["ranking_analyst"],  # type: ignore[index]
            max_iter=8,
            verbose=True,
        )

    @task
    def ranking_report_task(self) -> Task:
        return Task(
            config=self.tasks_config["ranking_report_task"],  # type: ignore[index]
            markdown=True,
            guardrail=make_report_url_guardrail(self.allowed_urls),
            guardrail_max_retries=2,
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest -q tests/test_crews.py`
Expected: all passed

- [ ] **Step 6: Commit**

```bash
git add src/internship_research_demo/crews/research_crew src/internship_research_demo/crews/ranking_crew tests/test_crews.py
git commit -m "feat: split into structured research crew and guarded ranking crew" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 9: Phase 1 Flow rewrite (single research branch)

**Files:**
- Rewrite: `src/internship_research_demo/main.py`
- Delete: `src/internship_research_demo/crews/content_crew/` (entire directory)
- Modify: `tests/helpers.py` (append `FakeCrews`)
- Test: `tests/test_flow.py`

**Interfaces:**
- Consumes: everything from Tasks 2–8
- Produces (in `main.py`):
  - `BRANCHES: dict[str, str]`: branch name → `source_focus` text (Phase 1 has only `"all_sources"`)
  - `ROUND_HINT: str`
  - `InternshipResearchState` with the new fields listed in the code below
  - `base_inputs(state) -> dict[str, Any]`, `research_inputs(state, branch: str) -> dict[str, Any]`, `ranking_inputs(state) -> dict[str, Any]`, `search_constraints(state) -> dict[str, str]`
  - Crew seams, which tests monkeypatch by module attribute: `async run_research_branch(branch: str, inputs: dict[str, Any]) -> ResearchBrief`, `run_ranking(inputs: dict[str, Any], allowed_urls: set[str]) -> str`, and the imported `verify_all`
  - Flow methods: `prepare_research_inputs`, `research_round`, `merge_and_dedupe`, `verify_urls`, `route_after_verify` (router), `rank_candidates`, `write_no_results`, `save_report`
  - `kickoff(payload)`, `plot()`, `run_with_trigger()` (same behavior as before)

- [ ] **Step 1: Add the fake crews test helper**

Append to `tests/helpers.py`:

```python
from internship_research_demo.models import ResearchBrief, Verification


class FakeCrews:
    """Stands in for the LLM crews and HTTP verification in Flow tests.

    ``research(branch, round_index)`` returns the candidates a branch finds in
    that round, or an Exception to raise. ``statuses`` maps a candidate URL to
    a verification status (default ``verified_open``).
    """

    def __init__(self, research, statuses=None, report="# Ranked report\n"):
        self.research = research
        self.statuses = statuses or {}
        self.report = report
        self.research_calls = []
        self.ranking_calls = []
        self._round_by_branch = {}

    async def run_research_branch(self, branch, inputs):
        round_index = self._round_by_branch.get(branch, 0)
        self._round_by_branch[branch] = round_index + 1
        self.research_calls.append((branch, inputs))
        result = self.research(branch, round_index)
        if isinstance(result, Exception):
            raise result
        return ResearchBrief(candidates=result)

    async def verify_all(self, candidates):
        return [
            Verification(status=self.statuses.get(c.url, "verified_open"), http_status=200, reason="fake")
            for c in candidates
        ]

    def run_ranking(self, inputs, allowed_urls):
        self.ranking_calls.append((inputs, allowed_urls))
        return self.report

    def install(self, monkeypatch):
        import internship_research_demo.main as main

        monkeypatch.setattr(main, "run_research_branch", self.run_research_branch)
        monkeypatch.setattr(main, "verify_all", self.verify_all)
        monkeypatch.setattr(main, "run_ranking", self.run_ranking)
```

- [ ] **Step 2: Write the failing Flow tests**

Create `tests/test_flow.py`:

```python
import re
from pathlib import Path

from helpers import FakeCrews, make_candidate
from internship_research_demo import main
from internship_research_demo.main import (
    BRANCHES,
    InternshipResearchState,
    ranking_inputs,
    research_inputs,
)

CREWS_DIR = Path(main.__file__).parent / "crews"
PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")


def _placeholders(crew_name: str) -> set[str]:
    config = CREWS_DIR / crew_name / "config"
    text = (config / "agents.yaml").read_text() + (config / "tasks.yaml").read_text()
    return set(PLACEHOLDER_RE.findall(text))


def test_research_placeholders_are_all_supplied():
    keys = set(research_inputs(InternshipResearchState(), next(iter(BRANCHES))))
    assert _placeholders("research_crew") <= keys


def test_ranking_placeholders_are_all_supplied():
    keys = set(ranking_inputs(InternshipResearchState()))
    assert _placeholders("ranking_crew") <= keys


def _run(monkeypatch, tmp_path, fake, **payload):
    monkeypatch.chdir(tmp_path)
    fake.install(monkeypatch)
    main.kickoff({"report_filename": "custom.md", **payload})
    return tmp_path / "output"


def _three():
    return [make_candidate(company=f"Co{i}", url=f"https://co{i}.com/jobs/1") for i in range(3)]


def test_happy_path_writes_exactly_one_report(monkeypatch, tmp_path):
    cands = _three()
    fake = FakeCrews(research=lambda branch, i: cands if i == 0 else [])
    out = _run(monkeypatch, tmp_path, fake, opportunity_count=3)

    assert sorted(p.name for p in out.iterdir()) == ["custom.md"]
    assert (out / "custom.md").read_text() == "# Ranked report\n"
    inputs, allowed = fake.ranking_calls[0]
    assert inputs["rank_count"] == 3
    assert inputs["shortfall_note"] == "none"
    assert "https://co0.com/jobs/1" in allowed
    assert fake.research_calls[0][1]["round_hint"] == ""
    assert fake.research_calls[0][1]["exclude_urls"] == "none"


def test_dead_candidates_are_not_ranked(monkeypatch, tmp_path):
    cands = _three()
    fake = FakeCrews(
        research=lambda branch, i: cands if i == 0 else [],
        statuses={"https://co1.com/jobs/1": "dead"},
    )
    _run(monkeypatch, tmp_path, fake, opportunity_count=2)

    inputs, _ = fake.ranking_calls[0]
    assert "https://co1.com/jobs/1" not in inputs["candidates_json"]
    assert "https://co0.com/jobs/1" in inputs["candidates_json"]
    assert inputs["rank_count"] == 2


def test_zero_candidates_writes_no_results_report(monkeypatch, tmp_path):
    cands = _three()
    fake = FakeCrews(
        research=lambda branch, i: cands if i == 0 else [],
        statuses={c.url: "dead" for c in cands},
    )
    out = _run(monkeypatch, tmp_path, fake, opportunity_count=3)

    assert fake.ranking_calls == []
    text = (out / "custom.md").read_text()
    assert text.startswith("# No qualifying internships found")
    assert "- dead: 3" in text


def test_failing_research_branch_does_not_crash(monkeypatch, tmp_path):
    fake = FakeCrews(research=lambda branch, i: RuntimeError("guardrail exhausted"))
    out = _run(monkeypatch, tmp_path, fake, opportunity_count=3)

    assert fake.ranking_calls == []
    assert (out / "custom.md").read_text().startswith("# No qualifying internships found")
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest -q tests/test_flow.py`
Expected: FAIL with `ImportError: cannot import name 'BRANCHES' from 'internship_research_demo.main'`

- [ ] **Step 4: Rewrite `main.py`**

Replace the entire contents of `src/internship_research_demo/main.py` with:

```python
#!/usr/bin/env python
import asyncio
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

from crewai.flow import Flow, listen, or_, router, start
from pydantic import BaseModel, Field

from internship_research_demo.crews.ranking_crew.ranking_crew import RankingCrew
from internship_research_demo.crews.research_crew.research_crew import ResearchCrew
from internship_research_demo.models import (
    BranchResult,
    ResearchBrief,
    SourcedCandidate,
    VerifiedCandidate,
)
from internship_research_demo.report import build_no_results_report
from internship_research_demo.routing import (
    NO_RESULTS,
    RANK,
    allowed_urls_for,
    build_shortfall_note,
    merge_new_candidates,
    normalize_url,
    parse_brief,
)
from internship_research_demo.seasons import default_season
from internship_research_demo.verify import verify_all

BRANCHES: dict[str, str] = {
    "all_sources": (
        "Any credible source: employer career pages, job boards and aggregators, "
        "and curated internship lists. Always follow through to the employer's "
        "own posting URL when one exists."
    ),
}
ROUND_HINT = (
    "Previous rounds found too few qualifying candidates. Broaden keywords and "
    "adjacent role titles. Do not repeat excluded URLs."
)


def _as_text(value: Any, default: str) -> str:
    if value is None:
        return default
    if isinstance(value, list):
        return ", ".join(str(item) for item in value if str(item).strip()) or default
    text = str(value).strip()
    return text or default


class InternshipResearchState(BaseModel):
    applied_field: str = "software engineering"
    role_family: str = "software engineering internships"
    season: str = Field(default_factory=lambda: default_season(date.today()))
    work_location: str = "United States"
    work_modes: str = "onsite, hybrid, or remote"
    degree_levels: str = "undergraduate and master's students"
    student_status: str = "international students in the US using CPT or OPT"
    sponsorship_filter: str = "must sponsor or explicitly allow CPT/OPT"
    application_status_filter: str = (
        "must still be accepting applications; exclude closed, expired, or filled postings"
    )
    employment_type_filter: str = (
        "internships only; exclude New Grad, full-time, permanent, and long-term employment roles"
    )
    additional_keywords: str = "internship, intern, university recruiting"
    ranking_priorities: str = (
        "CPT/OPT evidence, field fit, posting freshness, technical depth, location fit"
    )
    opportunity_count: int = 3
    report_filename: str = "internship_report.md"
    final_report: str = ""

    research_round: int = 0
    round_results: list[BranchResult] = Field(default_factory=list)
    pending: list[SourcedCandidate] = Field(default_factory=list)
    candidates: list[VerifiedCandidate] = Field(default_factory=list)
    new_candidate_urls: list[str] = Field(default_factory=list)
    seen_urls: set[str] = Field(default_factory=set)
    rejected_urls: set[str] = Field(default_factory=set)
    status_counts: dict[str, int] = Field(default_factory=dict)
    branch_counts: dict[str, int] = Field(default_factory=dict)
    shortfall_note: str = ""


def base_inputs(state: InternshipResearchState) -> dict[str, Any]:
    return {
        "applied_field": state.applied_field,
        "role_family": state.role_family,
        "season": state.season,
        "work_location": state.work_location,
        "work_modes": state.work_modes,
        "degree_levels": state.degree_levels,
        "student_status": state.student_status,
        "sponsorship_filter": state.sponsorship_filter,
        "application_status_filter": state.application_status_filter,
        "employment_type_filter": state.employment_type_filter,
        "additional_keywords": state.additional_keywords,
        "ranking_priorities": state.ranking_priorities,
        "opportunity_count": state.opportunity_count,
    }


def research_inputs(state: InternshipResearchState, branch: str) -> dict[str, Any]:
    excluded = sorted(state.seen_urls | state.rejected_urls)
    return {
        **base_inputs(state),
        "source_focus": BRANCHES[branch],
        "exclude_urls": ", ".join(excluded) or "none",
        "round_hint": ROUND_HINT if state.research_round > 0 else "",
    }


def ranking_inputs(state: InternshipResearchState) -> dict[str, Any]:
    return {
        **base_inputs(state),
        "rank_count": min(state.opportunity_count, len(state.candidates)),
        "candidates_json": json.dumps([vc.model_dump() for vc in state.candidates], indent=2),
        "shortfall_note": state.shortfall_note or "none",
    }


def search_constraints(state: InternshipResearchState) -> dict[str, str]:
    return {
        "Field": state.applied_field,
        "Season": state.season,
        "Location": state.work_location,
        "Work modes": state.work_modes,
        "Degree levels": state.degree_levels,
        "Work authorization": state.sponsorship_filter,
    }


async def run_research_branch(branch: str, inputs: dict[str, Any]) -> ResearchBrief:
    print(f"Research branch '{branch}' starting")
    result = await ResearchCrew().crew().kickoff_async(inputs=inputs)
    if isinstance(result.pydantic, ResearchBrief):
        return result.pydantic
    return parse_brief(result.raw)


def run_ranking(inputs: dict[str, Any], allowed_urls: set[str]) -> str:
    return RankingCrew(allowed_urls=allowed_urls).crew().kickoff(inputs=inputs).raw


class InternshipResearchFlow(Flow[InternshipResearchState]):
    @start()
    def prepare_research_inputs(self, crewai_trigger_payload: dict = None):
        print("Preparing internship research inputs")

        if crewai_trigger_payload:
            self.state.applied_field = _as_text(
                crewai_trigger_payload.get("applied_field"), self.state.applied_field
            )
            self.state.role_family = crewai_trigger_payload.get(
                "role_family", self.state.role_family
            )
            self.state.season = _as_text(
                crewai_trigger_payload.get("season"), self.state.season
            )
            self.state.work_location = _as_text(
                crewai_trigger_payload.get("work_location")
                or crewai_trigger_payload.get("location"),
                self.state.work_location,
            )
            self.state.work_modes = _as_text(
                crewai_trigger_payload.get("work_modes"), self.state.work_modes
            )
            self.state.degree_levels = _as_text(
                crewai_trigger_payload.get("degree_levels"), self.state.degree_levels
            )
            self.state.student_status = crewai_trigger_payload.get(
                "student_status", self.state.student_status
            )
            self.state.sponsorship_filter = _as_text(
                crewai_trigger_payload.get("sponsorship_filter"),
                self.state.sponsorship_filter,
            )
            self.state.application_status_filter = _as_text(
                crewai_trigger_payload.get("application_status_filter"),
                self.state.application_status_filter,
            )
            self.state.employment_type_filter = _as_text(
                crewai_trigger_payload.get("employment_type_filter"),
                self.state.employment_type_filter,
            )
            self.state.additional_keywords = _as_text(
                crewai_trigger_payload.get("additional_keywords"),
                self.state.additional_keywords,
            )
            self.state.ranking_priorities = _as_text(
                crewai_trigger_payload.get("ranking_priorities"),
                self.state.ranking_priorities,
            )
            self.state.opportunity_count = int(
                crewai_trigger_payload.get(
                    "opportunity_count", self.state.opportunity_count
                )
            )
            self.state.report_filename = _as_text(
                crewai_trigger_payload.get("report_filename"),
                self.state.report_filename,
            )
            print(f"Using trigger payload: {crewai_trigger_payload}")

        print(
            "Goal: rank "
            f"{self.state.opportunity_count} {self.state.season} "
            f"{self.state.applied_field} internships for {self.state.student_status}"
        )

    @listen(prepare_research_inputs)
    async def research_round(self):
        print(f"Research round {self.state.research_round + 1}")
        names = list(BRANCHES)
        outcomes = await asyncio.gather(
            *(run_research_branch(name, research_inputs(self.state, name)) for name in names),
            return_exceptions=True,
        )
        results = []
        for name, outcome in zip(names, outcomes):
            if isinstance(outcome, BaseException):
                print(f"Warning: research branch '{name}' failed: {outcome}")
                results.append(BranchResult(branch=name, error=str(outcome)))
            else:
                results.append(BranchResult(branch=name, candidates=outcome.candidates))
        self.state.round_results = results

    @listen(research_round)
    def merge_and_dedupe(self):
        existing = [vc.candidate for vc in self.state.candidates]
        excluded = self.state.seen_urls | self.state.rejected_urls
        self.state.pending = merge_new_candidates(self.state.round_results, existing, excluded)
        self.state.seen_urls |= {normalize_url(s.candidate.url) for s in self.state.pending}
        for sourced in self.state.pending:
            branch = sourced.source_branch
            self.state.branch_counts[branch] = self.state.branch_counts.get(branch, 0) + 1
        print(f"{len(self.state.pending)} new candidate(s) after merge")

    @listen(merge_and_dedupe)
    async def verify_urls(self):
        pending = self.state.pending
        verifications = await verify_all([s.candidate for s in pending])
        new_urls = []
        for sourced, verification in zip(pending, verifications):
            status = verification.status
            self.state.status_counts[status] = self.state.status_counts.get(status, 0) + 1
            if status == "dead":
                print(f"Dropping dead posting {sourced.candidate.url} ({verification.reason})")
                continue
            self.state.candidates.append(
                VerifiedCandidate(
                    candidate=sourced.candidate,
                    source_branch=sourced.source_branch,
                    verification=verification,
                )
            )
            new_urls.append(normalize_url(sourced.candidate.url))
        self.state.new_candidate_urls = new_urls
        self.state.pending = []

    @router(verify_urls)
    def route_after_verify(self):
        if not self.state.candidates:
            return NO_RESULTS
        self.state.shortfall_note = build_shortfall_note(
            len(self.state.candidates),
            self.state.opportunity_count,
            self.state.research_round + 1,
        )
        return RANK

    @listen(RANK)
    def rank_candidates(self):
        print("Ranking verified internship candidates")
        self.state.final_report = run_ranking(
            ranking_inputs(self.state), allowed_urls_for(self.state.candidates)
        )

    @listen(NO_RESULTS)
    def write_no_results(self):
        print("No qualifying internships found")
        self.state.final_report = build_no_results_report(
            search_constraints(self.state),
            self.state.research_round + 1,
            self.state.status_counts,
            self.state.branch_counts,
        )

    @listen(or_(rank_candidates, write_no_results))
    def save_report(self):
        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)
        report_path = output_dir / self.state.report_filename
        report_path.write_text(self.state.final_report)
        print(f"Report saved to {report_path}")


def kickoff(payload: dict[str, Any] | None = None):
    internship_flow = InternshipResearchFlow()
    if payload:
        return internship_flow.kickoff({"crewai_trigger_payload": payload})
    return internship_flow.kickoff()


def plot():
    internship_flow = InternshipResearchFlow()
    internship_flow.plot()


def run_with_trigger():
    """
    Run the flow with trigger payload.
    """
    if len(sys.argv) < 2:
        raise Exception("No trigger payload provided. Please provide JSON payload as argument.")

    try:
        trigger_payload = json.loads(sys.argv[1])
    except json.JSONDecodeError:
        raise Exception("Invalid JSON payload provided as argument")

    internship_flow = InternshipResearchFlow()

    try:
        return internship_flow.kickoff({"crewai_trigger_payload": trigger_payload})
    except Exception as e:
        raise Exception(f"An error occurred while running the flow with trigger: {e}")


if __name__ == "__main__":
    kickoff()
```

- [ ] **Step 5: Delete the old crew**

Run:

```bash
git rm -r src/internship_research_demo/crews/content_crew
```

Then confirm nothing still references it:

Run: `grep -rn "content_crew\|InternshipResearchCrew" src tests`
Expected: no output

- [ ] **Step 6: Run the full test suite**

Run: `uv run pytest -q`
Expected: all passed

- [ ] **Step 7: Check that the flow graph builds**

Run: `uv run plot`
Expected: CrewAI writes a flow plot HTML file with no traceback. Delete the generated HTML file afterwards and don't commit it.

- [ ] **Step 8: Commit**

```bash
git add src/internship_research_demo/main.py tests/helpers.py tests/test_flow.py
git commit -m "feat: structured, verified flow with single write of the report" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 10: CLI season picker and dynamic default

**Files:**
- Modify: `src/internship_research_demo/cli.py`
- Modify: `README.md`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `upcoming_seasons`, `default_season` from `seasons.py`
- Produces:
  - `_ask_season(today: date) -> str`
  - `parse_args(argv: list[str] | None = None) -> argparse.Namespace`
  - `--season` defaults to `default_season(date.today())`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_cli.py`:

```python
from datetime import date

from internship_research_demo.cli import _ask_season, build_payload_from_args, parse_args
from internship_research_demo.seasons import default_season

SEPT = date(2026, 9, 18)


def test_season_flag_defaults_to_next_summer():
    assert parse_args([]).season == default_season(date.today())


def test_season_flag_accepts_any_text():
    payload = build_payload_from_args(parse_args(["--season", "Fall 2027"]))
    assert payload["season"] == "Fall 2027"


def test_ask_season_by_number(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _prompt: "2")
    assert _ask_season(SEPT) == "Winter 2027"


def test_ask_season_blank_uses_default(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _prompt: "")
    assert _ask_season(SEPT) == "Summer 2027"


def test_ask_season_custom_text(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _prompt: "Summer 2028")
    assert _ask_season(SEPT) == "Summer 2028"


def test_ask_season_out_of_range_number_is_custom_text(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _prompt: "9")
    assert _ask_season(SEPT) == "9"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest -q tests/test_cli.py`
Expected: FAIL with `ImportError: cannot import name '_ask_season'`

- [ ] **Step 3: Implement**

In `src/internship_research_demo/cli.py`:

1. Replace the import block at the top with:

```python
#!/usr/bin/env python
import argparse
from datetime import date
from pathlib import Path
from typing import Any

from internship_research_demo.main import kickoff
from internship_research_demo.seasons import default_season, upcoming_seasons
```

2. Add this function directly after `_ask_field`:

```python
def _ask_season(today: date) -> str:
    options = upcoming_seasons(today)
    default = default_season(today)
    print("\nChoose an internship season or enter your own:")
    for index, season in enumerate(options, start=1):
        marker = "  (default)" if season == default else ""
        print(f"  {index}. {season}{marker}")
    value = input(f"Season [1-{len(options)} or custom, default: {default}]: ").strip()
    if not value:
        return default
    if value.isdigit() and 1 <= int(value) <= len(options):
        return options[int(value) - 1]
    return value
```

3. In `build_interactive_payload`, replace:

```python
    season = _ask_text("Internship season", "Summer 2026")
```

with:

```python
    season = _ask_season(date.today())
```

4. Change the signature and last line of `parse_args`:

```python
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
```

```python
    return parser.parse_args(argv)
```

5. In `parse_args`, replace the `--season` argument with:

```python
    parser.add_argument(
        "--season",
        default=default_season(date.today()),
        help="Internship season, e.g. 'Summer 2027'. Default: the next Summer term.",
    )
```

- [ ] **Step 4: Update README season references**

In `README.md`:
- Replace `- Season: \`Summer 2026\`` with `- Season: the next Summer term after today (for example Summer 2027 when run in September 2026)`
- Replace the `--season` option block text `Internship season. Default: Summer 2026.` with `Internship season. Default: the next Summer term. Interactive mode offers the current term and the next four (for example Fall 2026, Winter 2027, Spring 2027, Summer 2027, Fall 2027).`
- In the robotics example, replace `--season "Summer 2026"` with `--season "Summer 2027"`.

- [ ] **Step 5: Run the full suite and grep for hardcoded seasons**

Run: `uv run pytest -q`
Expected: all passed

Run: `grep -rn "Summer 2026" src README.md`
Expected: no output

- [ ] **Step 6: Commit**

```bash
git add src/internship_research_demo/cli.py tests/test_cli.py README.md
git commit -m "feat: season picker with dynamic default" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

**Phase 1 checkpoint:** `uv run pytest -q` passes. Phase 1 can ship on its own.

---

# Phase 2 — Flow

### Task 11: Router decision function

**Files:**
- Modify: `src/internship_research_demo/routing.py` (append)
- Test: `tests/test_decide_route.py`

**Interfaces:**
- Consumes: label constants from Task 5
- Produces: `decide_route(*, viable: int, wanted: int, research_round: int, max_extra_rounds: int, force_more: bool, review_enabled: bool, reviewed_round: int, has_new: bool) -> str`, which returns one of `RESEARCH_MORE`, `REVIEW`, `RANK`, `NO_RESULTS`

Precedence: force_more (if rounds left) → auto-retry (if short and rounds left) → review (if enabled, pending and there are new candidates) → no results (if zero viable) → rank.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_decide_route.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest -q tests/test_decide_route.py`
Expected: FAIL with `ImportError: cannot import name 'decide_route'`

- [ ] **Step 3: Implement**

Append to `src/internship_research_demo/routing.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest -q tests/test_decide_route.py`
Expected: all passed

- [ ] **Step 5: Commit**

```bash
git add src/internship_research_demo/routing.py tests/test_decide_route.py
git commit -m "feat: add pure router decision function" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 12: Review command parsing and prompt

**Files:**
- Create: `src/internship_research_demo/review.py`
- Test: `tests/test_review.py`

**Interfaces:**
- Consumes: `VerifiedCandidate` from `models.py`
- Produces:
  - Frozen dataclasses `Accept()`, `Drop(indices: tuple[int, ...])` (1-based, sorted, unique), `More()`, `Invalid(message: str)`
  - `parse_review_command(text: str, n: int) -> Accept | Drop | More | Invalid`
  - `render_shortlist(items: list[VerifiedCandidate]) -> str`
  - `run_review(items: list[VerifiedCandidate], input_fn=None, print_fn=None) -> Accept | Drop | More`: prompts again on `Invalid`. The defaults resolve to the built-in `input`/`print` at call time, so tests can monkeypatch `builtins.input`.
  - `USAGE: str`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_review.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest -q tests/test_review.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'internship_research_demo.review'`

- [ ] **Step 3: Implement**

Create `src/internship_research_demo/review.py`:

```python
import re
from collections.abc import Callable
from dataclasses import dataclass

from internship_research_demo.models import VerifiedCandidate

USAGE = "Enter = accept all | numbers (e.g. 2,5) = drop those | more = search again"


@dataclass(frozen=True)
class Accept:
    pass


@dataclass(frozen=True)
class Drop:
    indices: tuple[int, ...]


@dataclass(frozen=True)
class More:
    pass


@dataclass(frozen=True)
class Invalid:
    message: str


def parse_review_command(text: str, n: int) -> Accept | Drop | More | Invalid:
    value = text.strip()
    if not value:
        return Accept()
    if value.lower() == "more":
        return More()
    parts = [part for part in re.split(r"[,\s]+", value) if part]
    if not all(part.isdigit() for part in parts):
        return Invalid(f"Could not read that. {USAGE}")
    indices = sorted({int(part) for part in parts})
    if any(not 1 <= index <= n for index in indices):
        return Invalid(f"Numbers must be between 1 and {n}.")
    return Drop(tuple(indices))


def _clip(value: str, width: int) -> str:
    return value if len(value) <= width else value[: width - 1] + "…"


def render_shortlist(items: list[VerifiedCandidate]) -> str:
    header = (
        f"{'#':>2}  {'Company':<20} {'Title':<36} {'Branch':<14} "
        f"{'Verification':<14} {'CPT/OPT':<8} Deadline"
    )
    lines = [header, "-" * len(header)]
    for index, item in enumerate(items, start=1):
        c = item.candidate
        lines.append(
            f"{index:>2}  {_clip(c.company, 20):<20} {_clip(c.title, 36):<36} "
            f"{item.source_branch:<14} {item.verification.status:<14} "
            f"{c.cpt_opt_evidence:<8} {c.deadline or '-'}"
        )
    return "\n".join(lines)


def run_review(
    items: list[VerifiedCandidate],
    input_fn: Callable[[str], str] | None = None,
    print_fn: Callable[[str], None] | None = None,
) -> Accept | Drop | More:
    # Resolve at call time so tests can monkeypatch builtins.input.
    input_fn = input_fn or input
    print_fn = print_fn or print
    print_fn("\nReview the shortlist before ranking:")
    print_fn(render_shortlist(items))
    print_fn(USAGE)
    while True:
        command = parse_review_command(input_fn("Review> "), len(items))
        if isinstance(command, Invalid):
            print_fn(command.message)
            continue
        return command
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest -q tests/test_review.py`
Expected: all passed

- [ ] **Step 5: Commit**

```bash
git add src/internship_research_demo/review.py tests/test_review.py
git commit -m "feat: add shortlist review prompt" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 13: Phase 2 Flow — fan-out, retry router, review

**Files:**
- Modify: `src/internship_research_demo/main.py`
- Test: `tests/test_flow.py` (append)

**Interfaces:**
- Consumes: `decide_route`, `RESEARCH_MORE`, `REVIEW` (Task 11); `run_review`, `Drop`, `More` (Task 12)
- Produces:
  - `BRANCHES` has exactly the keys `career_pages`, `job_boards`, `curated_lists`
  - New state fields: `max_extra_rounds: int = 2`, `review_enabled: bool = False`, `force_more: bool = False`, `reviewed_round: int = -1`
  - Trigger payload keys read: `max_extra_rounds` (int, clamped to ≥0) and `review_enabled` (bool)
  - New Flow method `review_shortlist`. `research_round` now also listens to `RESEARCH_MORE`, and `route_after_verify` is `@router(or_(verify_urls, review_shortlist))`.

- [ ] **Step 1: Write the failing Flow tests**

Append to `tests/test_flow.py`:

```python
def test_three_branches_run_each_round(monkeypatch, tmp_path):
    fake = FakeCrews(research=lambda branch, i: _three() if i == 0 else [])
    _run(monkeypatch, tmp_path, fake, opportunity_count=3)
    assert sorted(b for b, _ in fake.research_calls) == ["career_pages", "curated_lists", "job_boards"]


def test_retry_round_when_short(monkeypatch, tmp_path):
    first = [make_candidate(company="A", url="https://a.com/1")]
    second = [
        make_candidate(company="B", url="https://b.com/1"),
        make_candidate(company="C", url="https://c.com/1"),
    ]

    def research(branch, i):
        if branch != "career_pages":
            return []
        return {0: first, 1: second}.get(i, [])

    fake = FakeCrews(research=research)
    _run(monkeypatch, tmp_path, fake, opportunity_count=3)

    career = [inputs for branch, inputs in fake.research_calls if branch == "career_pages"]
    assert len(career) == 2
    assert career[0]["round_hint"] == ""
    assert "Broaden" in career[1]["round_hint"]
    assert "https://a.com/1" in career[1]["exclude_urls"]
    inputs, _ = fake.ranking_calls[0]
    assert inputs["rank_count"] == 3
    assert inputs["shortfall_note"] == "none"


def test_shortfall_note_after_rounds_exhausted(monkeypatch, tmp_path):
    def research(branch, i):
        if branch != "career_pages":
            return []
        return [make_candidate(company=f"Co{i}", url=f"https://co{i}.com/j")]

    fake = FakeCrews(research=research)
    _run(monkeypatch, tmp_path, fake, opportunity_count=5, max_extra_rounds=2)

    assert len([b for b, _ in fake.research_calls if b == "career_pages"]) == 3
    inputs, _ = fake.ranking_calls[0]
    assert inputs["rank_count"] == 3
    assert inputs["shortfall_note"] == (
        "Only 3 of 5 requested internships survived verification after 3 research round(s)."
    )


def test_review_drop_removes_candidate(monkeypatch, tmp_path):
    fake = FakeCrews(research=lambda branch, i: _three() if i == 0 else [])
    answers = iter(["2"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))
    _run(monkeypatch, tmp_path, fake, opportunity_count=2, review_enabled=True)

    inputs, allowed = fake.ranking_calls[0]
    assert "https://co1.com/jobs/1" not in inputs["candidates_json"]
    assert "https://co1.com/jobs/1" not in allowed
    assert inputs["rank_count"] == 2


def test_review_more_runs_another_round_then_reviews_new_items(monkeypatch, tmp_path):
    def research(branch, i):
        if branch != "career_pages":
            return []
        if i == 0:
            return [
                make_candidate(company="A", url="https://a.com/1"),
                make_candidate(company="B", url="https://b.com/1"),
            ]
        if i == 1:
            return [make_candidate(company="C", url="https://c.com/1")]
        return []

    fake = FakeCrews(research=research)
    answers = iter(["more", ""])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))
    _run(monkeypatch, tmp_path, fake, opportunity_count=2, review_enabled=True)

    assert len([b for b, _ in fake.research_calls if b == "career_pages"]) == 2
    inputs, _ = fake.ranking_calls[0]
    assert "https://c.com/1" in inputs["candidates_json"]
    assert inputs["rank_count"] == 2


def test_review_disabled_never_prompts(monkeypatch, tmp_path):
    def no_input(_prompt=""):
        raise AssertionError("input() must not be called")

    monkeypatch.setattr("builtins.input", no_input)
    fake = FakeCrews(research=lambda branch, i: _three() if i == 0 else [])
    _run(monkeypatch, tmp_path, fake, opportunity_count=3)
    assert len(fake.ranking_calls) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest -q tests/test_flow.py`
Expected: FAIL. `test_three_branches_run_each_round` fails because only `all_sources` runs, and the retry and review tests fail.

- [ ] **Step 3: Update `main.py`**

Make these edits to `src/internship_research_demo/main.py`:

1. Add the imports. Replace the `routing` import block with:

```python
from internship_research_demo.review import Drop, More, run_review
from internship_research_demo.routing import (
    NO_RESULTS,
    RANK,
    RESEARCH_MORE,
    REVIEW,
    allowed_urls_for,
    build_shortfall_note,
    decide_route,
    merge_new_candidates,
    normalize_url,
    parse_brief,
)
```

2. Replace `BRANCHES` with:

```python
BRANCHES: dict[str, str] = {
    "career_pages": (
        "Employer career pages: large tech companies and employers known to accept "
        "CPT/OPT for interns. Prefer official postings on company career sites and "
        "their applicant tracking systems (Greenhouse, Lever, Workday)."
    ),
    "job_boards": (
        "Job boards and aggregators: LinkedIn, Handshake, Indeed, and Built In. "
        "Always follow through to the employer's own posting URL when one exists."
    ),
    "curated_lists": (
        "Curated internship lists: GitHub internship lists such as SimplifyJobs and "
        "Pitt CSC, and university career center listings. Follow each listing to the "
        "employer's own posting URL."
    ),
}
```

3. In `InternshipResearchState`, add these fields directly after `research_round: int = 0`:

```python
    max_extra_rounds: int = 2
    review_enabled: bool = False
    force_more: bool = False
    reviewed_round: int = -1
```

4. In `prepare_research_inputs`, add directly after the `report_filename` assignment (still inside `if crewai_trigger_payload:`):

```python
            if "max_extra_rounds" in crewai_trigger_payload:
                self.state.max_extra_rounds = max(
                    0, int(crewai_trigger_payload["max_extra_rounds"])
                )
            self.state.review_enabled = bool(
                crewai_trigger_payload.get("review_enabled", False)
            )
```

5. Change the `research_round` decorator from `@listen(prepare_research_inputs)` to:

```python
    @listen(or_(prepare_research_inputs, RESEARCH_MORE))
```

6. Replace the entire Phase 1 `route_after_verify` method with the following two methods. `review_shortlist` must come **before** the router, because the router refers to it:

```python
    @listen(REVIEW)
    def review_shortlist(self):
        new_urls = set(self.state.new_candidate_urls)
        items = [
            vc for vc in self.state.candidates if normalize_url(vc.candidate.url) in new_urls
        ]
        command = run_review(items)
        if isinstance(command, Drop):
            dropped = {normalize_url(items[i - 1].candidate.url) for i in command.indices}
            self.state.candidates = [
                vc
                for vc in self.state.candidates
                if normalize_url(vc.candidate.url) not in dropped
            ]
            self.state.rejected_urls |= dropped
            print(f"Dropped {len(dropped)} candidate(s)")
        elif isinstance(command, More):
            self.state.force_more = True
        self.state.reviewed_round = self.state.research_round

    @router(or_(verify_urls, review_shortlist))
    def route_after_verify(self):
        state = self.state
        label = decide_route(
            viable=len(state.candidates),
            wanted=state.opportunity_count,
            research_round=state.research_round,
            max_extra_rounds=state.max_extra_rounds,
            force_more=state.force_more,
            review_enabled=state.review_enabled,
            reviewed_round=state.reviewed_round,
            has_new=bool(state.new_candidate_urls),
        )
        if state.force_more and label != RESEARCH_MORE:
            print("No retry rounds left; continuing to ranking.")
        state.force_more = False
        if label == RESEARCH_MORE:
            state.research_round += 1
        elif label == RANK:
            state.shortfall_note = build_shortfall_note(
                len(state.candidates), state.opportunity_count, state.research_round + 1
            )
        return label
```

7. In `run_with_trigger`, directly after `trigger_payload = json.loads(sys.argv[1])` succeeds (after the `try/except` block), add:

```python
    # Review needs a human at the terminal; trigger runs are unattended.
    trigger_payload.pop("review_enabled", None)
```

- [ ] **Step 4: Run the full suite**

Run: `uv run pytest -q`
Expected: all passed, including the Phase 1 Flow tests, which don't depend on a particular branch name.

- [ ] **Step 5: Check the flow graph**

Run: `uv run plot`
Expected: a plot HTML file with no traceback. It should show `RESEARCH_MORE` looping back to `research_round` and `review_shortlist` feeding `route_after_verify`. Delete the generated HTML file and don't commit it.

- [ ] **Step 6: Commit**

```bash
git add src/internship_research_demo/main.py tests/test_flow.py
git commit -m "feat: parallel research branches, retry router, and shortlist review" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 14: CLI `--review` / `--max-extra-rounds`, trigger safety, README

**Files:**
- Modify: `src/internship_research_demo/cli.py`
- Modify: `README.md`
- Test: `tests/test_cli.py` (append), `tests/test_flow.py` (append)

**Interfaces:**
- Consumes: payload keys `review_enabled`, `max_extra_rounds` (Task 13)
- Produces: `--review` flag (default off), `--max-extra-rounds N` (0–5, default 2). The interactive payload always has `review_enabled=True`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cli.py`:

```python
import pytest

from internship_research_demo.cli import build_interactive_payload


def test_review_flag_defaults_off_and_rounds_default_two():
    payload = build_payload_from_args(parse_args([]))
    assert payload["review_enabled"] is False
    assert payload["max_extra_rounds"] == 2


def test_review_flag_and_rounds():
    payload = build_payload_from_args(parse_args(["--review", "--max-extra-rounds", "0"]))
    assert payload["review_enabled"] is True
    assert payload["max_extra_rounds"] == 0


def test_max_extra_rounds_rejects_out_of_range():
    with pytest.raises(SystemExit):
        parse_args(["--max-extra-rounds", "6"])


def test_interactive_payload_enables_review(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _prompt="": "")
    payload = build_interactive_payload()
    assert payload["review_enabled"] is True
    assert payload["max_extra_rounds"] == 2
```

Append to `tests/test_flow.py`:

```python
import json
import sys


def test_trigger_runs_never_prompt_for_review(monkeypatch, tmp_path):
    def no_input(_prompt=""):
        raise AssertionError("input() must not be called")

    monkeypatch.setattr("builtins.input", no_input)
    monkeypatch.chdir(tmp_path)
    fake = FakeCrews(research=lambda branch, i: _three() if i == 0 else [])
    fake.install(monkeypatch)
    payload = {"review_enabled": True, "opportunity_count": 3, "report_filename": "t.md"}
    monkeypatch.setattr(sys, "argv", ["run_with_trigger", json.dumps(payload)])

    main.run_with_trigger()

    assert (tmp_path / "output" / "t.md").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest -q tests/test_cli.py tests/test_flow.py`
Expected: `test_review_flag_defaults_off_and_rounds_default_two`, `test_review_flag_and_rounds`, and `test_interactive_payload_enables_review` FAIL with `KeyError` or `SystemExit` (unknown flag). `test_max_extra_rounds_rejects_out_of_range` and the trigger test may already pass: argparse rejects unknown flags, and Task 13 already pops `review_enabled`.

- [ ] **Step 3: Implement**

In `src/internship_research_demo/cli.py`:

1. Add after `_positive_int`:

```python
def _extra_rounds(value: str) -> int:
    parsed = int(value)
    if not 0 <= parsed <= 5:
        raise argparse.ArgumentTypeError("must be between 0 and 5")
    return parsed
```

2. In `build_interactive_payload`, add two keys to the returned dict (after `"report_filename": report_filename,`):

```python
        "review_enabled": True,
        "max_extra_rounds": 2,
```

3. In `build_payload_from_args`, add two keys to the returned dict (after `"report_filename": ...`):

```python
        "review_enabled": args.review,
        "max_extra_rounds": args.max_extra_rounds,
```

4. In `parse_args`, add before `return parser.parse_args(argv)`:

```python
    parser.add_argument(
        "--review",
        action="store_true",
        help="Review the verified shortlist in the terminal before ranking.",
    )
    parser.add_argument(
        "--max-extra-rounds",
        type=_extra_rounds,
        default=2,
        help="Extra research rounds when too few candidates survive (0-5). Default: 2.",
    )
```

- [ ] **Step 4: Update README**

In `README.md`:

1. Replace the whole `## What It Does` section body (everything from `The project runs a sequential CrewAI workflow:` through the paragraph ending `field.`) with:

```markdown
The project runs a CrewAI Flow:

1. Three research branches run in parallel: employer career pages, job boards,
   and curated intern lists. Each returns structured candidates as JSON.
2. Candidates are merged and deduplicated, and New Grad / full-time titles are dropped.
3. Every posting URL is checked over HTTP and labeled `verified_open`,
   `unverifiable` (kept, but ranked lower), or `dead` (dropped).
4. If fewer than `--count` candidates survive, the flow searches again with
   broader keywords, up to `--max-extra-rounds` extra rounds (default 2).
5. With `--review` (or `--interactive`), you review the shortlist in the
   terminal before ranking: press Enter to accept, type numbers to drop, or type
   `more` to search again.
6. `ranking_analyst` scores the surviving candidates and writes the ranked
   report. The report can only link to URLs the research found.

The workflow is designed for international students in the US and can filter by
CPT/OPT compatibility, degree level, work mode, location, application status,
and field.
```

2. In `## CLI Options`, add before `--output OUTPUT`:

```text
--review
  Review the verified shortlist in the terminal before ranking.

--max-extra-rounds N
  Extra research rounds when too few candidates survive (0-5). Default: 2.
```

3. In `## Run Interactively`, add `- shortlist review before ranking` to the end of the "Interactive mode prompts for" list.

- [ ] **Step 5: Run the full suite**

Run: `uv run pytest -q`
Expected: all passed

- [ ] **Step 6: Commit**

```bash
git add src/internship_research_demo/cli.py README.md tests/test_cli.py tests/test_flow.py
git commit -m "feat: add --review and --max-extra-rounds CLI options" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 15: Manual smoke run (live APIs)

This task spends real OpenAI and Serper credits. **Ask the user before running it.**

- [ ] **Step 1: Run the flow**

```bash
uv run internship-agent --field "Robotics & controls" --count 3 --review --output smoke_report.md
```

- [ ] **Step 2: Check the behavior**

- The log shows the three branches (`career_pages`, `job_boards`, `curated_lists`) starting in the same round.
- The log shows `Dropping dead posting ...` lines, or none if nothing was dead.
- The review table appears. Type `1` to drop the first row and confirm it's absent from the report.
- `ls output/` shows `smoke_report.md` and did **not** create or modify `internship_report.md` during this run (compare `git status output/`).
- The report has a Verification column, and every link in it matches a candidate URL.

- [ ] **Step 3: Record findings**

Tell the user what you saw, including any guardrail retries shown in the log, how many candidates each verification status got, and total run time. Don't commit `output/smoke_report.md`.

---

## Self-Review Notes

- **Spec coverage:**
  - Models: Task 3. Seasons: Tasks 2 and 10. Verification rules 1–5 and constants: Task 4.
  - Research guardrail: Tasks 6 and 8. Report URL guardrail: Tasks 6 and 8.
  - Merge/dedupe, URL normalization with job-ID params, title filter: Task 5.
  - Fan-out with `return_exceptions`: Tasks 9 and 13.
  - Router precedence and `NO_RESULTS`: Tasks 9 and 11–13.
  - Review, including rejected URLs and the new-only table: Tasks 12–13.
  - Ranking prompt changes (unverifiable cap, Verification column, rank only the provided candidates): Task 8.
  - Single report write: Tasks 8 and 9. No-results report: Tasks 7 and 9.
  - Trigger runs never review: Tasks 13–14. CLI flags: Tasks 10 and 14.
  - Tests per the spec's Testing section: Tasks 2–14. Manual smoke run: Task 15.
- **Refinements beyond the spec text:**
  - `SourcedCandidate` and `BranchResult` models, a `report.py` module, and a `rank_count` template variable.
  - `new_candidate_urls` is recorded after verification, so review never shows dead links. The spec was updated to match.
