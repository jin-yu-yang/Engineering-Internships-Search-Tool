#!/usr/bin/env python
import json
from pathlib import Path
from typing import Any

from crewai.flow import Flow, listen, start
from pydantic import BaseModel

from internship_research_demo.crews.content_crew.content_crew import InternshipResearchCrew


def _as_text(value: Any, default: str) -> str:
    if value is None:
        return default
    if isinstance(value, list):
        return ", ".join(str(item) for item in value if str(item).strip()) or default
    text = str(value).strip()
    return text or default


class InternshipResearchState(BaseModel):
    applied_field: str = "software engineering and applied AI"
    role_family: str = "software engineering and AI engineering"
    season: str = "Summer 2026"
    work_location: str = "United States"
    work_modes: str = "onsite, hybrid, or remote"
    student_status: str = "international students in the US using CPT or OPT"
    sponsorship_filter: str = "must sponsor or explicitly allow CPT/OPT"
    additional_keywords: str = "internship, intern, university recruiting"
    ranking_priorities: str = (
        "CPT/OPT evidence, field fit, posting freshness, technical depth, location fit"
    )
    opportunity_count: int = 3
    report_filename: str = "internship_report.md"
    final_report: str = ""


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
            self.state.season = crewai_trigger_payload.get("season", self.state.season)
            self.state.work_location = _as_text(
                crewai_trigger_payload.get("work_location")
                or crewai_trigger_payload.get("location"),
                self.state.work_location,
            )
            self.state.work_modes = _as_text(
                crewai_trigger_payload.get("work_modes"), self.state.work_modes
            )
            self.state.student_status = crewai_trigger_payload.get(
                "student_status", self.state.student_status
            )
            self.state.sponsorship_filter = _as_text(
                crewai_trigger_payload.get("sponsorship_filter"),
                self.state.sponsorship_filter,
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
    def research_and_rank_internships(self):
        print("Researching and ranking internship opportunities")
        result = (
            InternshipResearchCrew()
            .crew()
            .kickoff(
                inputs={
                    "applied_field": self.state.applied_field,
                    "role_family": self.state.role_family,
                    "season": self.state.season,
                    "work_location": self.state.work_location,
                    "work_modes": self.state.work_modes,
                    "student_status": self.state.student_status,
                    "sponsorship_filter": self.state.sponsorship_filter,
                    "additional_keywords": self.state.additional_keywords,
                    "ranking_priorities": self.state.ranking_priorities,
                    "opportunity_count": self.state.opportunity_count,
                }
            )
        )

        print("Internship report generated")
        self.state.final_report = result.raw

    @listen(research_and_rank_internships)
    def save_report(self):
        print("Saving report")
        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)
        report_path = output_dir / self.state.report_filename
        with open(report_path, "w") as f:
            f.write(self.state.final_report)
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
    import sys

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
