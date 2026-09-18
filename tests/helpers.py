from internship_research_demo.models import Candidate, ResearchBrief, Verification


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
