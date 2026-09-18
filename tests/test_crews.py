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
