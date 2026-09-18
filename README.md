# Internship Research Agent

A small CrewAI Flow with a CLI for researching, filtering, scoring, and ranking
internship opportunities in applied science and engineering fields.

The agent produces a Markdown report in:

```bash
output/internship_report.md
```

Use `--output NAME.md` to write a different file under `output/`. Only that one
file is written per run.

## What It Does

The project runs a CrewAI Flow:

1. Three research branches run in parallel: employer career pages, job boards,
   and curated intern lists. Each returns structured candidates as JSON.
2. Candidates are merged and deduplicated, and New Grad / full-time titles are dropped.
3. Every posting URL is checked over HTTP and labeled `verified_open`,
   `unverifiable` (kept, but ranked lower), or `dead` (dropped). See
   [URL Verification](#url-verification).
4. If fewer than `--count` candidates survive, the flow searches again with
   broader keywords, up to `--max-extra-rounds` extra rounds (default 2).
5. With `--review` (or `--interactive`), you review the shortlist in the
   terminal before ranking: press Enter to accept, type numbers to drop, or type
   `more` to search again.
6. `ranking_analyst` scores the surviving candidates and writes the ranked
   report. The report can only link to URLs the research found.

If no candidates survive, the flow skips ranking and writes a short
"No qualifying internships found" report with verification counts per status
and per research branch.

The workflow is designed for international students in the US and can filter by
CPT/OPT compatibility, degree level, work mode, location, application status,
and field.

## Default Behavior

Defaults are defined in `src/internship_research_demo/main.py` and the CLI:

- Field: `software engineering`
- Season: the next Summer term after today (for example Summer 2027 when run in September 2026)
- Location: `United States`
- Work modes: onsite, hybrid, or remote
- Degree level: undergraduate/master's
- Work authorization: must support or explicitly allow CPT/OPT
- Application status: must still be accepting applications
- Employment type: internships only
- Excluded roles: New Grad, full-time, permanent, and long-term employment
- Report count: 3 ranked opportunities
- Extra research rounds: 2 (when fewer than the report count survive)
- Shortlist review: off (on with `--review` or `--interactive`)

## URL Verification

Each candidate's posting URL is fetched once, without an LLM:

- `dead`: HTTP 404/410, a known "job closed" redirect, or page text such as
  "no longer accepting applications". Dead postings are dropped.
- `verified_open`: the page loads and shows most of the role title's words.
- `unverifiable`: the page could not be confirmed, for example because it is
  rendered with JavaScript, blocks bots (401/403/429), times out, or is not
  HTML. These stay in the ranking but can earn at most 7 of the 15
  application-status points.

For safety, URLs pointing at `localhost`, `.local` names, private or link-local
IP addresses, or ports other than 80/443 are never fetched and are marked
`unverifiable`. At most 2 MB of each page is read.

## Field Picker

Interactive mode lets you choose one of these fields or enter your own:

```text
Software & Computing
 1. Software engineering
 2. Machine learning / AI engineering
 3. Data science & analytics
 4. Cybersecurity
 5. Cloud & DevOps / SRE
 6. Embedded systems & firmware

Hardware & Physical Engineering
 7. Electrical engineering
 8. Computer / hardware engineering
 9. Mechanical engineering
10. Aerospace engineering
11. Robotics & controls
12. Materials science & engineering
13. Civil / structural engineering
14. Chemical engineering
15. Industrial & systems engineering

Life & Earth Sciences
16. Biomedical engineering
17. Bioinformatics / computational biology
18. Environmental & energy engineering
```

## Installation

This project requires Python `>=3.10,<3.14` and CrewAI's `uv`-based tooling.

From this directory:

```bash
crewai install
```

Add API keys to `.env`:

```bash
OPENAI_API_KEY=your_key_here
SERPER_API_KEY=your_key_here
```

`SERPER_API_KEY` is required for web search through `SerperDevTool`.

## Run Interactively

```bash
uv run internship-agent --interactive
```

Interactive mode prompts for:

- field
- season
- role keywords
- location
- work modes: onsite, hybrid, remote
- degree levels: undergraduate/master's, PhD
- CPT/OPT requirement
- open-applications-only filter
- number of opportunities to rank
- extra search keywords
- ranking priorities
- output filename
- shortlist review before ranking

Interactive mode always reviews the shortlist. You can still combine it with
`--max-extra-rounds`, e.g. `uv run internship-agent --interactive --max-extra-rounds 0`.

## Run With Flags

Example for robotics internships for undergraduate/master's students:

```bash
uv run internship-agent \
  --field "Robotics & controls" \
  --season "Summer 2027" \
  --location "United States" \
  --degree-level undergrad-master \
  --work-mode remote \
  --work-mode hybrid \
  --require-opt-cpt \
  --open-applications-only \
  --count 5 \
  --output robotics_report.md
```

Example for PhD AI internships:

```bash
uv run internship-agent \
  --field "Machine learning / AI engineering" \
  --degree-level phd \
  --work-mode onsite \
  --work-mode hybrid \
  --open-applications-only \
  --count 5 \
  --output phd_ai_report.md
```

To review the verified shortlist before ranking and allow up to 3 extra
research rounds:

```bash
uv run internship-agent --field "Cybersecurity" --review --max-extra-rounds 3
```

To include both undergraduate/master's and PhD roles, repeat the flag:

```bash
uv run internship-agent \
  --field "Bioinformatics / computational biology" \
  --degree-level undergrad-master \
  --degree-level phd
```

## CLI Options

```text
--interactive
  Prompt for all options.

--field FIELD
  Applied science or engineering field to search.

--role-keywords ROLE_KEYWORDS
  Override generated role keywords. Defaults to "<field> internships".

--season SEASON
  Internship season. Default: the next Summer term. Interactive mode offers the current term and the next four (for example Fall 2026, Winter 2027, Spring 2027, Summer 2027, Fall 2027).

--location LOCATION
  Work location or region. Default: United States.

--work-mode {onsite,hybrid,remote}
  Allowed work mode. Repeat for multiple modes.

--degree-level {undergrad-master,phd}
  Candidate degree level. Repeat for multiple levels.

--require-opt-cpt / --no-require-opt-cpt
  Require CPT/OPT compatibility or only report authorization risk.

--open-applications-only / --allow-closed-for-context
  Tell the researcher to include only roles still accepting applications
  (default), or to also consider roles whose status is unclear. Postings that
  URL verification finds closed are always dropped before ranking.

--count COUNT
  Number of internships to rank.

--student-status STUDENT_STATUS
  Candidate work-authorization context.

--keywords KEYWORDS
  Additional search keywords.

--priorities PRIORITIES
  Comma-separated ranking priorities.

--review
  Review the verified shortlist in the terminal before ranking.

--max-extra-rounds N
  Extra research rounds when too few candidates survive (0-5). Default: 2.

--output OUTPUT
  Markdown filename under output/.
```

## CrewAI Entrypoints

You can still use the standard CrewAI script:

```bash
crewai run
```

Or pass a trigger payload:

```bash
crewai run_with_trigger '{"applied_field":"Biomedical engineering","degree_levels":"undergraduate and masters students","work_modes":"remote, hybrid","application_status_filter":"must still be accepting applications; exclude closed, expired, or filled postings","opportunity_count":3}'
```

Trigger runs are unattended: `review_enabled` is ignored, so they never wait for
terminal input. The payload may set `max_extra_rounds` (default 2).

## Tests

The test suite makes no LLM or network calls:

```bash
uv sync
uv run pytest -q
```

## Local Storage

CrewAI may create local storage files. To keep those files inside this project
while experimenting:

```bash
HOME="$PWD" CREWAI_STORAGE_DIR=crewai_storage uv run internship-agent --interactive
```

## Project Structure

```text
src/internship_research_demo/main.py
  Flow state, orchestration (research fan-out, verification, router, review), and report saving.

src/internship_research_demo/cli.py
  Interactive prompts and CLI flag parsing.

src/internship_research_demo/crews/research_crew/
  Researcher agent and structured research task (JSON output with a guardrail).

src/internship_research_demo/crews/ranking_crew/
  Ranking analyst and report task (URL guardrail).

src/internship_research_demo/models.py, seasons.py, verify.py, routing.py, review.py, report.py
  Pure logic: data models, season math, URL verification, merge/dedupe, guardrails, router decisions, review prompt, no-results report.
```
