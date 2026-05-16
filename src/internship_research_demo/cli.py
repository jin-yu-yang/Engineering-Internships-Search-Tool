#!/usr/bin/env python
import argparse
from pathlib import Path
from typing import Any

from internship_research_demo.main import kickoff


DEFAULT_FIELD = "software engineering"

FIELD_GROUPS = [
    (
        "Software & Computing",
        [
            "Software engineering",
            "Machine learning / AI engineering",
            "Data science & analytics",
            "Cybersecurity",
            "Cloud & DevOps / SRE",
            "Embedded systems & firmware",
        ],
    ),
    (
        "Hardware & Physical Engineering",
        [
            "Electrical engineering",
            "Computer / hardware engineering",
            "Mechanical engineering",
            "Aerospace engineering",
            "Robotics & controls",
            "Materials science & engineering",
            "Civil / structural engineering",
            "Chemical engineering",
            "Industrial & systems engineering",
        ],
    ),
    (
        "Life & Earth Sciences",
        [
            "Biomedical engineering",
            "Bioinformatics / computational biology",
            "Environmental & energy engineering",
        ],
    ),
]
FIELD_CHOICES = [field for _, fields in FIELD_GROUPS for field in fields]

WORK_MODE_CHOICES = ["onsite", "hybrid", "remote"]
DEGREE_LEVEL_CHOICES = ["undergrad-master", "phd"]


def _ask_text(label: str, default: str) -> str:
    value = input(f"{label} [{default}]: ").strip()
    return value or default


def _clean_report_filename(value: str) -> str:
    filename = Path(value.strip() or "internship_report.md").name
    return filename if filename.endswith(".md") else f"{filename}.md"


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return parsed


def _ask_int(label: str, default: int, minimum: int = 1, maximum: int = 20) -> int:
    while True:
        value = input(f"{label} [{default}]: ").strip()
        if not value:
            return default
        try:
            parsed = int(value)
        except ValueError:
            print(f"Enter a number from {minimum} to {maximum}.")
            continue
        if minimum <= parsed <= maximum:
            return parsed
        print(f"Enter a number from {minimum} to {maximum}.")


def _ask_yes_no(label: str, default: bool) -> bool:
    suffix = "Y/n" if default else "y/N"
    while True:
        value = input(f"{label} [{suffix}]: ").strip().lower()
        if not value:
            return default
        if value in {"y", "yes"}:
            return True
        if value in {"n", "no"}:
            return False
        print("Enter y or n.")


def _ask_field(default: str) -> str:
    print("\nChoose a field or enter your own:")
    index = 1
    for group, fields in FIELD_GROUPS:
        print(f"\n  {group}")
        for field in fields:
            print(f"  {index:2}. {field}")
            index += 1
    value = input(f"Field [1-{len(FIELD_CHOICES)} or custom, default: {default}]: ").strip()
    if not value:
        return default
    if value.isdigit():
        index = int(value)
        if 1 <= index <= len(FIELD_CHOICES):
            return FIELD_CHOICES[index - 1]
    return value


def _ask_work_modes(default_modes: list[str]) -> list[str]:
    print("\nToggle work modes:")
    selected: list[str] = []
    for mode in WORK_MODE_CHOICES:
        enabled = mode in default_modes
        if _ask_yes_no(f"Include {mode} roles?", enabled):
            selected.append(mode)
    return selected or default_modes


def _ask_degree_levels(default_levels: list[str]) -> list[str]:
    print("\nToggle candidate degree levels:")
    selected: list[str] = []
    if _ask_yes_no("Include undergraduate/master's internships?", "undergrad-master" in default_levels):
        selected.append("undergrad-master")
    if _ask_yes_no("Include PhD internships?", "phd" in default_levels):
        selected.append("phd")
    return selected or default_levels


def _sponsorship_text(require_opt_cpt: bool) -> str:
    if require_opt_cpt:
        return "must sponsor, support, or explicitly allow CPT/OPT for internships"
    return "do not require CPT/OPT support, but note work authorization and visa risk"


def _application_status_text(open_only: bool) -> str:
    if open_only:
        return "must still be accepting applications; exclude closed, expired, or filled postings"
    return "may include closed postings only if clearly labeled as closed and not ranked"


def _degree_levels_text(levels: list[str]) -> str:
    has_undergrad_master = "undergrad-master" in levels
    has_phd = "phd" in levels
    if has_undergrad_master and has_phd:
        return "undergraduate, master's, and PhD students"
    if has_phd:
        return "PhD students"
    return "undergraduate and master's students"


def _employment_type_text() -> str:
    return "internships only; exclude New Grad, full-time, permanent, and long-term employment roles"


def build_interactive_payload() -> dict[str, Any]:
    field = _ask_field(DEFAULT_FIELD)
    season = _ask_text("Internship season", "Summer 2026")
    role_family = _ask_text(
        "Role keywords",
        f"{field} internships",
    )
    work_location = _ask_text("Work location or region", "United States")
    work_modes = _ask_work_modes(["onsite", "hybrid", "remote"])
    degree_levels = _ask_degree_levels(["undergrad-master"])
    require_opt_cpt = _ask_yes_no("Require CPT/OPT sponsorship or compatibility?", True)
    open_applications_only = _ask_yes_no("Only rank roles still accepting applications?", True)
    opportunity_count = _ask_int("How many internships should be ranked?", 3)
    additional_keywords = _ask_text(
        "Extra search keywords",
        "internship, intern, university recruiting",
    )
    ranking_priorities = _ask_text(
        "Ranking priorities",
        "CPT/OPT evidence, field fit, posting freshness, technical depth, location fit",
    )
    report_filename = _clean_report_filename(
        _ask_text("Report filename in output/", "internship_report.md")
    )

    return {
        "applied_field": field,
        "role_family": role_family,
        "season": season,
        "work_location": work_location,
        "work_modes": ", ".join(work_modes),
        "degree_levels": _degree_levels_text(degree_levels),
        "student_status": "international students in the US using CPT or OPT",
        "sponsorship_filter": _sponsorship_text(require_opt_cpt),
        "application_status_filter": _application_status_text(open_applications_only),
        "employment_type_filter": _employment_type_text(),
        "additional_keywords": additional_keywords,
        "ranking_priorities": ranking_priorities,
        "opportunity_count": opportunity_count,
        "report_filename": report_filename,
    }


def build_payload_from_args(args: argparse.Namespace) -> dict[str, Any]:
    field = args.field or DEFAULT_FIELD
    work_modes = args.work_mode or ["onsite", "hybrid", "remote"]
    degree_levels = args.degree_level or ["undergrad-master"]
    return {
        "applied_field": field,
        "role_family": args.role_keywords
        or f"{field} internships",
        "season": args.season,
        "work_location": args.location,
        "work_modes": ", ".join(work_modes),
        "degree_levels": _degree_levels_text(degree_levels),
        "student_status": args.student_status,
        "sponsorship_filter": _sponsorship_text(args.require_opt_cpt),
        "application_status_filter": _application_status_text(args.open_applications_only),
        "employment_type_filter": _employment_type_text(),
        "additional_keywords": args.keywords,
        "ranking_priorities": args.priorities,
        "opportunity_count": args.count,
        "report_filename": _clean_report_filename(args.output),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Research and rank applied science or engineering internships with CrewAI."
    )
    parser.add_argument("--interactive", action="store_true", help="Prompt for all options.")
    parser.add_argument("--field", help="Applied science or engineering field to search.")
    parser.add_argument("--role-keywords", help="Role title keywords to search.")
    parser.add_argument("--season", default="Summer 2026", help="Internship season.")
    parser.add_argument("--location", default="United States", help="Work location or region.")
    parser.add_argument(
        "--work-mode",
        action="append",
        choices=WORK_MODE_CHOICES,
        help="Allowed work mode. Repeat for multiple modes.",
    )
    parser.add_argument(
        "--degree-level",
        action="append",
        choices=DEGREE_LEVEL_CHOICES,
        help=(
            "Candidate degree level. Repeat for multiple levels. "
            "Choices: undergrad-master, phd."
        ),
    )
    parser.add_argument(
        "--require-opt-cpt",
        dest="require_opt_cpt",
        action="store_true",
        default=True,
        help="Require CPT/OPT sponsorship or explicit compatibility.",
    )
    parser.add_argument(
        "--no-require-opt-cpt",
        dest="require_opt_cpt",
        action="store_false",
        help="Do not require CPT/OPT compatibility; report authorization risk instead.",
    )
    parser.add_argument(
        "--open-applications-only",
        dest="open_applications_only",
        action="store_true",
        default=True,
        help="Only rank internships that are still accepting applications.",
    )
    parser.add_argument(
        "--allow-closed-for-context",
        dest="open_applications_only",
        action="store_false",
        help="Allow closed postings as context, but do not rank them.",
    )
    parser.add_argument(
        "--count",
        type=_positive_int,
        default=3,
        help="Number of internships to rank.",
    )
    parser.add_argument(
        "--student-status",
        default="international students in the US using CPT or OPT",
        help="Candidate work-authorization context.",
    )
    parser.add_argument(
        "--keywords",
        default="internship, intern, university recruiting",
        help="Additional search keywords.",
    )
    parser.add_argument(
        "--priorities",
        default="CPT/OPT evidence, field fit, posting freshness, technical depth, location fit",
        help="Comma-separated ranking priorities.",
    )
    parser.add_argument(
        "--output",
        default="internship_report.md",
        help="Markdown filename under output/.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_interactive_payload() if args.interactive else build_payload_from_args(args)
    kickoff(payload)


if __name__ == "__main__":
    main()
