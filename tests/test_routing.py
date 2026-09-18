from helpers import make_candidate
from internship_research_demo.models import BranchResult
from internship_research_demo.routing import (
    build_shortfall_note,
    is_excluded_title,
    merge_new_candidates,
    normalize_url,
)


def test_normalize_url_strips_query_fragment_trailing_slash_and_host_case():
    assert (
        normalize_url("HTTPS://Jobs.Acme.com/Careers/123/?utm_source=x#apply")
        == "https://jobs.acme.com/Careers/123"
    )


def test_normalize_url_keeps_job_id_query_params():
    assert (
        normalize_url("https://boards.greenhouse.io/acme/jobs?utm=1&gh_jid=42")
        == "https://boards.greenhouse.io/acme/jobs?gh_jid=42"
    )
    assert (
        normalize_url("https://x.wd1.myworkdayjobs.com/job?jobId=7")
        == "https://x.wd1.myworkdayjobs.com/job?jobId=7"
    )


def test_is_excluded_title():
    assert is_excluded_title("New Grad Software Engineer")
    assert is_excluded_title("Full-Time Data Scientist")
    assert is_excluded_title("Full time Engineer")
    assert is_excluded_title("Engineering Graduate Program")
    assert is_excluded_title("Rotational Engineer")
    assert not is_excluded_title("Software Engineer Intern")


def test_merge_dedupes_by_url_keeps_more_complete_and_unions_sources():
    a = make_candidate(url="https://acme.com/jobs/1?utm=x", source_urls=["https://acme.com/jobs/1"])
    b = make_candidate(
        url="https://acme.com/jobs/1/",
        deadline="2026-10-01",
        source_urls=["https://linkedin.com/jobs/9"],
    )
    merged = merge_new_candidates(
        [
            BranchResult(branch="career_pages", candidates=[a]),
            BranchResult(branch="job_boards", candidates=[b]),
        ],
        existing=[],
        exclude_urls=set(),
    )
    assert len(merged) == 1
    assert merged[0].candidate.deadline == "2026-10-01"
    assert merged[0].source_branch == "job_boards"
    assert merged[0].candidate.source_urls == [
        "https://linkedin.com/jobs/9",
        "https://acme.com/jobs/1",
    ]


def test_merge_dedupes_by_company_and_title_first_wins_on_tie():
    a = make_candidate(url="https://acme.com/a")
    b = make_candidate(company="  ACME ", title="software   engineer intern", url="https://lnkd.in/b")
    merged = merge_new_candidates(
        [BranchResult(branch="career_pages", candidates=[a, b])], existing=[], exclude_urls=set()
    )
    assert [m.candidate.url for m in merged] == ["https://acme.com/a"]


def test_merge_drops_excluded_titles_known_urls_and_existing_candidates():
    new = [
        make_candidate(title="New Grad Engineer", url="https://acme.com/ng"),
        make_candidate(company="Beta", url="https://beta.com/jobs/seen"),
        make_candidate(company="Gamma", url="https://gamma.com/jobs/rejected"),
        make_candidate(company="Initech", title="Data Intern", url="https://other.com/j"),
        make_candidate(company="Globex", url="https://globex.com/j"),
    ]
    existing = [make_candidate(company="Initech", title="Data Intern", url="https://initech.com/j")]
    merged = merge_new_candidates(
        [BranchResult(branch="job_boards", candidates=new)],
        existing=existing,
        exclude_urls={"https://beta.com/jobs/seen", "https://gamma.com/jobs/rejected"},
    )
    assert [m.candidate.company for m in merged] == ["Globex"]


def test_shortfall_note():
    assert build_shortfall_note(3, 3, 1) == ""
    assert build_shortfall_note(4, 3, 1) == ""
    assert build_shortfall_note(2, 3, 3) == (
        "Only 2 of 3 requested internships survived verification after 3 research round(s)."
    )
