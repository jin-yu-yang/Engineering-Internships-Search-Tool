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
from internship_research_demo.seasons import default_season
from internship_research_demo.verify import verify_all

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
    max_extra_rounds: int = 2
    review_enabled: bool = False
    force_more: bool = False
    reviewed_round: int = -1
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
            if "max_extra_rounds" in crewai_trigger_payload:
                self.state.max_extra_rounds = max(
                    0, int(crewai_trigger_payload["max_extra_rounds"])
                )
            self.state.review_enabled = bool(
                crewai_trigger_payload.get("review_enabled", False)
            )
            print(f"Using trigger payload: {crewai_trigger_payload}")

        print(
            "Goal: rank "
            f"{self.state.opportunity_count} {self.state.season} "
            f"{self.state.applied_field} internships for {self.state.student_status}"
        )

    @listen(or_(prepare_research_inputs, RESEARCH_MORE))
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

    # Review needs a human at the terminal; trigger runs are unattended.
    trigger_payload.pop("review_enabled", None)

    internship_flow = InternshipResearchFlow()

    try:
        return internship_flow.kickoff({"crewai_trigger_payload": trigger_payload})
    except Exception as e:
        raise Exception(f"An error occurred while running the flow with trigger: {e}")


if __name__ == "__main__":
    kickoff()
