# Structured, Verified Internship Research Flow — Design

Date: 2026-09-18
Status: Approved design, pending implementation plan
CrewAI version: 1.15.22 (project pin upgraded from 1.14.3)

## Goal

Make the internship report trustworthy and the Flow genuinely multi-step:

1. Structured research output (Pydantic models)
2. Deterministic URL verification between research and ranking
3. Task guardrails on research and ranking output
4. Fix the double report write; compute season defaults from today's date
5. Router retry loop when too few candidates survive
6. Parallel research fan-out by source type
7. Optional human review of the shortlist before ranking

Out of scope: run history/persistence, CSV/JSON tracker export, profile-aware
scoring, cost presets.

## Current problems addressed

- `ranking_report_task` hardcodes `output_file: output/internship_report.md`
  while `save_report` writes `output/{report_filename}`, so a custom `--output`
  produces two files and always overwrites `internship_report.md`.
- Season default is hardcoded to `Summer 2026`, which is already past.
- Research output is free-form text; nothing downstream can dedupe, verify, or
  filter it.
- "Still open" and CPT/OPT claims are only LLM-asserted; no deterministic check.
- The Flow is linear (start → one crew → save) and uses no routing.

## Architecture

The single `content_crew` is split into two single-purpose crews. The Flow owns
orchestration, verification, routing, and review.

### Flow graph

```
prepare_inputs
   └─► research_round        (3× ResearchCrew.kickoff_async via asyncio.gather)
          └─► merge_and_dedupe
                 └─► verify_urls          (concurrent HTTP; drop "dead")
                        └─► @router route_after_verify   (also triggered by review_shortlist)
                               ├─ "RESEARCH_MORE" ─► research_round
                               ├─ "REVIEW"        ─► review_shortlist ─► route_after_verify
                               ├─ "RANK"          ─► rank_candidates ─┐
                               └─ "NO_RESULTS"    ─► write_no_results ─┴► save_report
```

CrewAI 1.15.22 constraints (verified by probe):

- Only `@router` methods emit labels; a plain `@listen` method's return value
  triggers nothing. So `route_after_verify` is declared as
  `@router(or_(verify_urls, review_shortlist))`.
- A router label may not equal any handler method name. Labels are uppercase
  constants: `RESEARCH_MORE`, `REVIEW`, `RANK`, `NO_RESULTS`.
- When a task has a guardrail, CrewAI does not parse `output_pydantic` before
  the guardrail runs. The research guardrail parses the raw JSON itself and, on
  success, returns the brief as a JSON string; CrewAI then fills `.pydantic`.

### File layout

```
src/internship_research_demo/
  models.py            Pydantic models (new)
  seasons.py           season list/default logic (new)
  verify.py            URL verification (new)
  review.py            review command parsing + table rendering (new)
  routing.py           decide_route, merge/dedupe, title filter, guardrails (new)
  report.py            "no results" report builder (new)
  crews/research_crew/research_crew.py, config/agents.yaml, config/tasks.yaml (new)
  crews/ranking_crew/ranking_crew.py,  config/agents.yaml, config/tasks.yaml (new)
  crews/content_crew/  (removed)
  main.py              Flow rewrite
  cli.py               --review flag, season picker, dynamic --season default
tests/                 (new; pytest added as a dev dependency)
```

Pure logic lives in `models.py`, `seasons.py`, `verify.py`, `review.py`, and
`routing.py` so it is testable without the Flow or any LLM.

## Data models (`models.py`)

```python
EvidenceLevel = Literal["direct", "indirect", "missing"]
VerifyStatus  = Literal["verified_open", "unverifiable", "dead"]

class Candidate(BaseModel):          # produced by the researcher LLM
    company: str
    title: str
    url: str                         # application / job posting URL
    location: str
    work_mode: str                   # onsite / hybrid / remote / unknown
    field_fit: str
    degree_level_evidence: str
    internship_evidence: str
    cpt_opt_evidence: EvidenceLevel
    cpt_opt_note: str
    open_status_evidence: str
    deadline: str | None = None
    compensation: str | None = None
    risks: list[str] = []
    source_urls: list[str]

class ResearchBrief(BaseModel):      # output_pydantic of the research task
    candidates: list[Candidate]

class Verification(BaseModel):       # set by Python only, never by the LLM
    status: VerifyStatus
    http_status: int | None
    reason: str

class VerifiedCandidate(BaseModel):
    candidate: Candidate
    source_branch: str               # career_pages | job_boards | curated_lists
    verification: Verification
```

### Flow state additions

| Field | Type | Purpose |
|---|---|---|
| `season` | `str` | `default_factory=lambda: default_season(date.today())` |
| `candidates` | `list[VerifiedCandidate]` | surviving (non-dead) candidates |
| `new_candidate_urls` | `list[str]` | URLs added in the latest round (for review) |
| `seen_urls` | `set[str]` | normalized URLs from all rounds |
| `rejected_urls` | `set[str]` | URLs dropped by the user in review |
| `research_round` | `int` | 0-based round counter |
| `max_extra_rounds` | `int = 2` | retry budget |
| `review_enabled` | `bool = False` | set by CLI `--review` / `--interactive` |
| `force_more` | `bool = False` | set when user types `more` |
| `reviewed_round` | `int = -1` | last round the user reviewed |
| `shortfall_note` | `str = ""` | passed to ranking when fewer than count |

Trigger payloads may set `max_extra_rounds`. `review_enabled` is always false
for trigger runs.

## Components

### Research fan-out (`research_round`)

Three `ResearchCrew` runs execute concurrently via `kickoff_async` and
`asyncio.gather(..., return_exceptions=True)`. Each receives a `source_focus`
input:

| Branch | `source_focus` guidance |
|---|---|
| `career_pages` | Employer career pages: large tech and companies known to accept CPT/OPT |
| `job_boards` | Job boards and aggregators: LinkedIn, Handshake, Indeed, Built In |
| `curated_lists` | Curated intern lists: GitHub lists (e.g. SimplifyJobs, Pitt CSC), university career sites |

Additional research inputs:

- `{exclude_urls}` — comma-separated `seen_urls ∪ rejected_urls` (empty in round 0)
- `{round_hint}` — empty in round 0; on later rounds: "Previous rounds found too
  few qualifying candidates. Broaden keywords and adjacent role titles. Do not
  repeat excluded URLs."

A branch that raises (including exhausting guardrail retries) is treated as an
empty brief and logged as a warning. One failed branch never aborts the run.

The research agent keeps its current role/goal/backstory, tools
(`SerperDevTool`, `ScrapeWebsiteTool`), `max_iter=12`, and `inject_date`.

### Research guardrail

Function guardrail on the research task, `guardrail_max_retries=2`. Returns
failure when:

- output does not parse as `ResearchBrief`
- `candidates` is empty
- any candidate's `url` is not `http://` or `https://`
- any candidate has empty `source_urls`

### Merge and dedupe (`merge_and_dedupe`)

- **URL normalization:** lowercase scheme and host, strip query string,
  fragment, and trailing slash. Exception: Greenhouse/Lever/Workday style
  query-borne job IDs (`gh_jid`, `jobId`) are preserved.
- **Duplicate keys:** normalized URL, or normalized `(company, title)`
  (lowercased, whitespace-collapsed).
- **Merge rule:** keep the candidate with more non-empty optional fields;
  union `source_urls`.
- **Title filter (backstop):** drop titles matching
  `new grad|full[- ]time|graduate program|rotational` (case-insensitive).
- **Exclusions:** drop candidates whose normalized URL is in `rejected_urls`
  or already in `candidates`.
- New survivors' normalized URLs are added to `seen_urls`. After verification,
  the non-dead ones are recorded in `new_candidate_urls` (so review never shows
  dead links).

### URL verification (`verify.py`)

`async def verify_all(candidates) -> list[Verification]` using
`httpx.AsyncClient`: concurrency 8 (semaphore), 10s timeout, follow redirects,
browser User-Agent. Only the primary `url` is fetched.

Evaluated in this order (first match wins):

| # | Condition | Status |
|---|---|---|
| 1 | HTTP 404 or 410 | `dead` |
| 2 | Final URL matches a closed-redirect pattern (e.g. Greenhouse `?error=true`) | `dead` |
| 3 | HTTP 200 and page text contains a closed phrase | `dead` |
| 4 | HTTP 200 and ≥60% of significant title tokens appear in page text | `verified_open` |
| 5 | Anything else: 200 without title match, 401/403/429/5xx, timeout, connection error | `unverifiable` |

- `CLOSED_PHRASES` and `CLOSED_REDIRECT_PATTERNS` are module-level constants.
  Initial phrases: "no longer accepting applications", "position has been
  filled", "job is closed", "this job has expired", "posting has been closed",
  "no longer available".
- Significant title tokens: lowercased words of length ≥3, excluding
  stopwords such as "intern", "internship", "the", "and", "summer", "fall",
  "spring", "winter", and four-digit years.
- `reason` records the cause (e.g. `"404"`, `"closed phrase: job is closed"`,
  `"title not found (likely JS-rendered)"`, `"timeout"`).
- `dead` candidates are removed from state; their URLs remain in `seen_urls`.

### Router (`decide_route` in `routing.py`)

Pure function over explicit arguments (not the Flow state object), wrapped by
`@router`. The Flow method applies the state mutations (reset `force_more`,
increment `research_round`, set `shortfall_note`). Labels below are shown in
lowercase for readability; the code uses the uppercase constants.

```
viable = len(candidates)
rounds_left = research_round < max_extra_rounds

if force_more:
    force_more = False
    if rounds_left: return "research_more"
    print("No retry rounds left; continuing to ranking.")
if viable < opportunity_count and rounds_left:
    return "research_more"
if review_enabled and reviewed_round < research_round and new_candidate_urls:
    return "review"
if viable == 0:
    return "no_results"
return "rank"
```

Clarifications:

- `research_more` increments `research_round` before the next research round.
- Automatic retry takes precedence over review when below count and rounds
  remain, so the user reviews the fuller set. The order is:
  force_more → auto-retry (if short and rounds left) → review (if pending) →
  rank. If the user drops candidates in review and the set falls below count,
  the next routing pass auto-retries (rounds permitting) and the new
  candidates are reviewed afterwards.
- If rounds are exhausted and `viable < opportunity_count`, set
  `shortfall_note` (e.g. "Only 2 of 3 requested internships survived
  verification after 3 research rounds.").

### Review (`review_shortlist`, `review.py`)

Runs only when `review_enabled`. Shows candidates from `new_candidate_urls`
as a numbered table: company, title, branch, verification status, CPT/OPT
evidence level, deadline.

`parse_review_command(text: str, n: int) -> Accept | Drop | More | Invalid`:

- empty input → `Accept`
- `more` (case-insensitive) → `More`
- comma/space-separated integers in `1..n` → `Drop(indices)`
- anything else → `Invalid` (re-prompt with usage text)

On `Drop`, remove those candidates from `candidates` and add their URLs to
`rejected_urls`. On `More`, set `force_more = True`. Always set
`reviewed_round = research_round`, then route again.

### Ranking (`RankingCrew`)

Inputs: existing variables plus `{candidates_json}` (serialized
`VerifiedCandidate` list) and `{shortfall_note}`.

Prompt changes to the ranking task:

- Rank only the provided candidates; do not add new opportunities.
- Rank `min(opportunity_count, len(candidates))` items.
- Rubric unchanged, except `unverifiable` candidates are capped at 7 of the
  15 application-status points.
- Ranked table gains a "Verification" column.
- If `shortfall_note` is non-empty, state it in "Watchouts".
- Remove `output_file`; keep `markdown=True`.

Ranking guardrail (`guardrail_max_retries=2`): extract all `http(s)` URLs from
the report; fail if any URL (normalized) is not among the candidates' `url`
or `source_urls`.

### Save (`save_report`)

The only writer of report files. Writes `output/{report_filename}`.

When `candidates` is empty after all rounds, ranking is skipped and
`save_report` writes a short "No qualifying internships found" report that
includes counts by verification status and by branch, plus the search
constraints used.

## Seasons (`seasons.py`)

Month → term mapping: Winter = Dec–Feb, Spring = Mar–May, Summer = Jun–Aug,
Fall = Sep–Nov. December belongs to Winter of the following year.

- `current_term(today) -> tuple[str, int]`
- `upcoming_seasons(today, n=5) -> list[str]` — current term followed by the
  next four in order Winter → Spring → Summer → Fall. For 2026-09-18:
  `["Fall 2026", "Winter 2027", "Spring 2027", "Summer 2027", "Fall 2027"]`.
- `default_season(today) -> str` — the first Summer strictly after the current
  term. 2026-09-18 → `Summer 2027`; 2027-07-01 → `Summer 2028`;
  2027-03-15 → `Summer 2027`.

CLI:

- Interactive mode shows a numbered season picker from `upcoming_seasons`
  plus a custom-text option; default is `default_season`.
- `--season` default is `default_season(date.today())`; any text is accepted.
- Remove hardcoded `"Summer 2026"` from `cli.py`, `main.py`, and README.

## CLI changes (`cli.py`)

- New `--review` flag; `--interactive` also enables review.
- Payload gains `review_enabled` (CLI only) and optional `max_extra_rounds`.
- Season picker and dynamic default as above.

## Error handling summary

| Situation | Behavior |
|---|---|
| One research branch fails | Treated as empty; warning logged |
| All branches fail in a round | Zero new candidates; router retries if rounds remain |
| Network unavailable | All candidates `unverifiable`; ranking proceeds; noted in Watchouts |
| Zero candidates after all rounds | Ranking skipped; "no results" report written |
| Ranking crew fails or guardrail exhausted | Exception propagates; no report written |
| Invalid review input | Re-prompt |

## Testing

No live LLM or network calls in automated tests. `pytest` is added as a dev
dependency.

Unit tests:

- `seasons`: boundary dates (Dec 1, Feb 28, Mar 1, Jun 1, Aug 31, Sep 1,
  Sep 18) for `current_term`, `upcoming_seasons`, `default_season`.
- `verify`: `httpx.MockTransport`, one case per table row, plus precedence
  (closed phrase beats title match).
- `routing`: URL normalization, dedupe/merge, title filter, `decide_route`
  across force_more / short / review-pending / rounds-exhausted cases.
- Guardrails: research guardrail and ranking URL guardrail pass/fail cases.
- `review`: `parse_review_command` for accept, drop, more, invalid,
  out-of-range.
- `cli`: payload building including season default and `review_enabled`.

Flow integration (crews monkeypatched to return fixture briefs/reports):

- Happy path: enough candidates → rank → exactly one report file written at
  `output/{report_filename}`.
- Retry path: first round short → second round fills → rank.
- Zero-candidate path: "no results" report written, ranking not called.

Manual: one smoke run with real API keys after Phase 2.

## Phasing

- **Phase 1 — foundation:** `models.py`, `seasons.py`, `verify.py`, guardrails,
  crew split, a single research branch (all sources), merge/dedupe, verify,
  rank, save; bug fix; CLI season picker; tests for all of the above.
- **Phase 2 — flow:** three-branch fan-out, router retry loop, review step,
  `--review` flag; routing/review/integration tests; README update.

Phase 1 is independently shippable.
