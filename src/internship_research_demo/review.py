import re
from collections.abc import Callable
from dataclasses import dataclass

from internship_research_demo.models import VerifiedCandidate

USAGE = "Enter = accept all | numbers (e.g. 2,5) = drop those | more = search again"


@dataclass(frozen=True)
class Accept:
    pass


@dataclass(frozen=True)
class Drop:
    indices: tuple[int, ...]


@dataclass(frozen=True)
class More:
    pass


@dataclass(frozen=True)
class Invalid:
    message: str


def parse_review_command(text: str, n: int) -> Accept | Drop | More | Invalid:
    value = text.strip()
    if not value:
        return Accept()
    if value.lower() == "more":
        return More()
    parts = [part for part in re.split(r"[,\s]+", value) if part]
    if not all(part.isdigit() for part in parts):
        return Invalid(f"Could not read that. {USAGE}")
    indices = sorted({int(part) for part in parts})
    if any(not 1 <= index <= n for index in indices):
        return Invalid(f"Numbers must be between 1 and {n}.")
    return Drop(tuple(indices))


def _clip(value: str, width: int) -> str:
    return value if len(value) <= width else value[: width - 1] + "…"


def render_shortlist(items: list[VerifiedCandidate]) -> str:
    header = (
        f"{'#':>2}  {'Company':<20} {'Title':<36} {'Branch':<14} "
        f"{'Verification':<14} {'CPT/OPT':<8} Deadline"
    )
    lines = [header, "-" * len(header)]
    for index, item in enumerate(items, start=1):
        c = item.candidate
        lines.append(
            f"{index:>2}  {_clip(c.company, 20):<20} {_clip(c.title, 36):<36} "
            f"{item.source_branch:<14} {item.verification.status:<14} "
            f"{c.cpt_opt_evidence:<8} {c.deadline or '-'}"
        )
    return "\n".join(lines)


def run_review(
    items: list[VerifiedCandidate],
    input_fn: Callable[[str], str] | None = None,
    print_fn: Callable[[str], None] | None = None,
) -> Accept | Drop | More:
    # Resolve at call time so tests can monkeypatch builtins.input.
    input_fn = input_fn or input
    print_fn = print_fn or print
    print_fn("\nReview the shortlist before ranking:")
    print_fn(render_shortlist(items))
    print_fn(USAGE)
    while True:
        command = parse_review_command(input_fn("Review> "), len(items))
        if isinstance(command, Invalid):
            print_fn(command.message)
            continue
        return command
