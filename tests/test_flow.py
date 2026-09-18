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
