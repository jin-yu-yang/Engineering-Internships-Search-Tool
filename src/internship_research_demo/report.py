VERIFY_STATUSES = ("verified_open", "unverifiable", "dead")


def build_no_results_report(
    constraints: dict[str, str],
    rounds: int,
    status_counts: dict[str, int],
    branch_counts: dict[str, int],
) -> str:
    lines = [
        "# No qualifying internships found",
        "",
        f"No postings survived research and URL verification after {rounds} research round(s).",
        "",
        "## Search constraints",
        "",
    ]
    lines += [f"- {name}: {value}" for name, value in constraints.items()] or ["- none"]
    lines += ["", "## Verification results", ""]
    lines += [f"- {status}: {status_counts.get(status, 0)}" for status in VERIFY_STATUSES]
    lines += ["", "## Candidates found per research branch", ""]
    lines += [f"- {branch}: {count}" for branch, count in sorted(branch_counts.items())] or ["- none"]
    lines += [
        "",
        "## Next steps",
        "",
        "- Broaden the field, location, or work modes.",
        "- Re-run with `--no-require-opt-cpt` or `--allow-closed-for-context` to see near misses.",
    ]
    return "\n".join(lines) + "\n"
