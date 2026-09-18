import asyncio

import httpx
import pytest

from helpers import make_candidate
from internship_research_demo.verify import (
    classify_response,
    significant_title_tokens,
    verify_all,
)

TITLE = "Software Engineer Intern"
JOB_HTML = "<html><body><h1>Software Engineer Intern</h1><button>Apply now</button></body></html>"


def test_significant_title_tokens_drop_stopwords_and_years():
    assert significant_title_tokens("Machine Learning Intern - Summer 2027") == {"machine", "learning"}


@pytest.mark.parametrize("code", [404, 410])
def test_gone_status_is_dead(code):
    result = classify_response(code, "https://acme.com/jobs/1", "", TITLE)
    assert (result.status, result.http_status, result.reason) == ("dead", code, str(code))


def test_closed_redirect_is_dead():
    result = classify_response(200, "https://boards.greenhouse.io/acme?error=true", JOB_HTML, TITLE)
    assert result.status == "dead"
    assert result.reason.startswith("closed redirect")


def test_closed_phrase_beats_title_match():
    html = JOB_HTML.replace("Apply now", "Sorry, this job is closed")
    result = classify_response(200, "https://acme.com/jobs/1", html, TITLE)
    assert (result.status, result.reason) == ("dead", "closed phrase: job is closed")


def test_title_match_is_verified_open():
    result = classify_response(200, "https://acme.com/jobs/1", JOB_HTML, TITLE)
    assert result.status == "verified_open"
    assert result.reason == "title match 100%"


def test_title_only_in_script_is_unverifiable():
    html = "<html><body><div id='root'></div><script>var t = 'Software Engineer Intern';</script></body></html>"
    result = classify_response(200, "https://acme.com/jobs/1", html, TITLE)
    assert (result.status, result.reason) == ("unverifiable", "title not found (likely JS-rendered)")


def test_generic_title_is_unverifiable():
    result = classify_response(200, "https://acme.com/jobs/1", JOB_HTML, "Intern")
    assert (result.status, result.reason) == ("unverifiable", "title too generic to match")


@pytest.mark.parametrize("code", [401, 403, 429, 500, 503])
def test_other_status_is_unverifiable(code):
    result = classify_response(code, "https://acme.com/jobs/1", "", TITLE)
    assert (result.status, result.reason) == ("unverifiable", f"http {code}")


def test_verify_all_end_to_end_with_mock_transport():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "boards.example.com":
            return httpx.Response(200, text="<html>All jobs</html>")
        path = request.url.path
        if path == "/open":
            return httpx.Response(200, text=JOB_HTML)
        if path == "/gone":
            return httpx.Response(404)
        if path == "/moved":
            return httpx.Response(302, headers={"Location": "https://boards.example.com/acme?error=true"})
        if path == "/slow":
            raise httpx.ReadTimeout("timed out", request=request)
        if path == "/down":
            raise httpx.ConnectError("refused", request=request)
        return httpx.Response(403)

    paths = ["open", "gone", "moved", "slow", "down", "blocked"]
    candidates = [make_candidate(url=f"https://acme.example.com/{p}") for p in paths]

    async def run():
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, follow_redirects=True) as client:
            return await verify_all(candidates, client=client)

    results = asyncio.run(run())

    assert [r.status for r in results] == [
        "verified_open",
        "dead",
        "dead",
        "unverifiable",
        "unverifiable",
        "unverifiable",
    ]
    assert results[3].reason == "timeout"
    assert results[4].reason == "connection error: ConnectError"
    assert results[5].reason == "http 403"
