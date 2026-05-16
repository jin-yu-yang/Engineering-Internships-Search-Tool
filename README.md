# Internship Research Agent

A small CrewAI Flow with a CLI for researching, filtering, scoring, and ranking
internship opportunities in applied science and engineering fields.

The agent produces a Markdown report in:

```bash
output/internship_report.md
```

## What It Does

The project runs a sequential CrewAI workflow:

1. `internship_researcher` searches for active internship postings and verifies them against source pages.
2. `ranking_analyst` scores the qualified opportunities and writes a ranked report.

The workflow is designed for international students in the US and can filter by
CPT/OPT compatibility, degree level, work mode, location, application status,
and field.

## Default Behavior

Defaults are defined in `src/internship_research_demo/main.py` and the CLI:

- Field: `software engineering`
- Season: `Summer 2026`
- Location: `United States`
- Work modes: onsite, hybrid, or remote
- Degree level: undergraduate/master's
- Work authorization: must support or explicitly allow CPT/OPT
- Application status: must still be accepting applications
- Employment type: internships only
- Excluded roles: New Grad, full-time, permanent, and long-term employment
- Report count: 3 ranked opportunities

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

## Run With Flags

Example for robotics internships for undergraduate/master's students:

```bash
uv run internship-agent \
  --field "Robotics & controls" \
  --season "Summer 2026" \
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
  Internship season. Default: Summer 2026.

--location LOCATION
  Work location or region. Default: United States.

--work-mode {onsite,hybrid,remote}
  Allowed work mode. Repeat for multiple modes.

--degree-level {undergrad-master,phd}
  Candidate degree level. Repeat for multiple levels.

--require-opt-cpt / --no-require-opt-cpt
  Require CPT/OPT compatibility or only report authorization risk.

--open-applications-only / --allow-closed-for-context
  Rank only roles still accepting applications, or allow closed roles as context
  while keeping them out of the ranking.

--count COUNT
  Number of internships to rank.

--student-status STUDENT_STATUS
  Candidate work-authorization context.

--keywords KEYWORDS
  Additional search keywords.

--priorities PRIORITIES
  Comma-separated ranking priorities.

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

## Local Storage

CrewAI may create local storage files. To keep those files inside this project
while experimenting:

```bash
HOME="$PWD" CREWAI_STORAGE_DIR=crewai_storage uv run internship-agent --interactive
```

## Project Structure

```text
src/internship_research_demo/main.py
  Flow state, trigger payload handling, and report saving.

src/internship_research_demo/cli.py
  Interactive prompts and CLI flag parsing.

src/internship_research_demo/crews/content_crew/content_crew.py
  Crew, agents, tools, tasks, and sequential process wiring.

src/internship_research_demo/crews/content_crew/config/agents.yaml
  Agent roles, goals, and backstories.

src/internship_research_demo/crews/content_crew/config/tasks.yaml
  Research and ranking instructions.
```
