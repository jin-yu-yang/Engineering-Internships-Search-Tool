from internship_research_demo.report import build_no_results_report


def test_no_results_report_lists_constraints_counts_and_branches():
    text = build_no_results_report(
        constraints={"Field": "Robotics & controls", "Season": "Summer 2027"},
        rounds=3,
        status_counts={"dead": 4, "unverifiable": 0},
        branch_counts={"job_boards": 1, "career_pages": 3},
    )
    assert text.startswith("# No qualifying internships found\n")
    assert "after 3 research round(s)" in text
    assert "- Field: Robotics & controls" in text
    assert "- Season: Summer 2027" in text
    assert "- verified_open: 0" in text
    assert "- dead: 4" in text
    assert text.index("- career_pages: 3") < text.index("- job_boards: 1")
    assert text.endswith("\n")


def test_no_results_report_with_no_branch_output():
    text = build_no_results_report(constraints={}, rounds=1, status_counts={}, branch_counts={})
    assert "## Candidates found per research branch\n\n- none" in text
