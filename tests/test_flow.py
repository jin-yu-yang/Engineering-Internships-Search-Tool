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
