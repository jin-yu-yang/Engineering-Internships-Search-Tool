#!/usr/bin/env python
import argparse
from pathlib import Path
from typing import Any

from internship_research_demo.main import kickoff


FIELD_CHOICES = [
    "software engineering and applied AI",
    "machine learning engineering",
    "robotics engineering",
    "data science and analytics engineering",
    "aerospace engineering",
    "biomedical engineering",
    "environmental engineering",
    "electrical and computer engineering",
]

WORK_MODE_CHOICES = ["onsite", "hybrid", "remote"]


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
    for index, field in enumerate(FIELD_CHOICES, start=1):
        print(f"  {index}. {field}")
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


def _sponsorship_text(require_opt_cpt: bool) -> str:
    if require_opt_cpt:
        return "must sponsor, support, or explicitly allow CPT/OPT for internships"
    return "do not require CPT/OPT support, but note work authorization and visa risk"


def build_interactive_payload() -> dict[str, Any]:
    field = _ask_field("software engineering and applied AI")
    season = _ask_text("Internship season", "Summer 2026")
    role_family = _ask_text(
        "Role keywords",
        f"{field} internships, applied science internships, engineering internships",
    )
    work_location = _ask_text("Work location or region", "United States")
    work_modes = _ask_work_modes(["onsite", "hybrid", "remote"])
    require_opt_cpt = _ask_yes_no("Require CPT/OPT sponsorship or compatibility?", True)
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
        "student_status": "international students in the US using CPT or OPT",
        "sponsorship_filter": _sponsorship_text(require_opt_cpt),
        "additional_keywords": additional_keywords,
        "ranking_priorities": ranking_priorities,
        "opportunity_count": opportunity_count,
        "report_filename": report_filename,
    }


def build_payload_from_args(args: argparse.Namespace) -> dict[str, Any]:
    field = args.field or "software engineering and applied AI"
    work_modes = args.work_mode or ["onsite", "hybrid", "remote"]
    return {
        "applied_field": field,
        "role_family": args.role_keywords
        or f"{field} internships, applied science internships, engineering internships",
        "season": args.season,
        "work_location": args.location,
        "work_modes": ", ".join(work_modes),
        "student_status": args.student_status,
        "sponsorship_filter": _sponsorship_text(args.require_opt_cpt),
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
