import asyncio
import re

import httpx

from internship_research_demo.models import Candidate, Verification

CLOSED_PHRASES = (
    "no longer accepting applications",
    "position has been filled",
    "job is closed",
    "this job has expired",
    "posting has been closed",
    "no longer available",
)
CLOSED_REDIRECT_PATTERNS = (re.compile(r"[?&]error=true\b"),)
TITLE_STOPWORDS = frozenset(
    {
        "intern",
        "interns",
        "internship",
        "internships",
        "the",
        "and",
        "for",
        "with",
        "summer",
        "fall",
        "spring",
        "winter",
        "coop",
    }
)
TITLE_MATCH_THRESHOLD = 0.6
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

_WORD_RE = re.compile(r"[a-z0-9]+")
_SCRIPT_STYLE_RE = re.compile(r"<(script|style)\b.*?</\1>", re.IGNORECASE | re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")
_YEAR_RE = re.compile(r"\d{4}")


def _page_text(html: str) -> str:
    text = _SCRIPT_STYLE_RE.sub(" ", html)
    text = _TAG_RE.sub(" ", text)
    return " ".join(text.lower().split())


def significant_title_tokens(title: str) -> set[str]:
    return {
        word
        for word in _WORD_RE.findall(title.lower())
        if len(word) >= 3 and word not in TITLE_STOPWORDS and not _YEAR_RE.fullmatch(word)
    }


def _result(status: str, http_status: int | None, reason: str) -> Verification:
    return Verification(status=status, http_status=http_status, reason=reason)


def classify_response(status_code: int, final_url: str, html: str, title: str) -> Verification:
    if status_code in (404, 410):
        return _result("dead", status_code, str(status_code))
    for pattern in CLOSED_REDIRECT_PATTERNS:
        if pattern.search(final_url):
            return _result("dead", status_code, f"closed redirect: {final_url}")
    if status_code != 200:
        return _result("unverifiable", status_code, f"http {status_code}")

    text = _page_text(html)
    for phrase in CLOSED_PHRASES:
        if phrase in text:
            return _result("dead", status_code, f"closed phrase: {phrase}")

    tokens = significant_title_tokens(title)
    if not tokens:
        return _result("unverifiable", status_code, "title too generic to match")
    ratio = len(tokens & set(_WORD_RE.findall(text))) / len(tokens)
    if ratio >= TITLE_MATCH_THRESHOLD:
        return _result("verified_open", status_code, f"title match {ratio:.0%}")
    return _result("unverifiable", status_code, "title not found (likely JS-rendered)")


async def _verify_one(
    client: httpx.AsyncClient, candidate: Candidate, semaphore: asyncio.Semaphore
) -> Verification:
    async with semaphore:
        try:
            response = await client.get(candidate.url)
        except httpx.TimeoutException:
            return _result("unverifiable", None, "timeout")
        except httpx.HTTPError as exc:
            return _result("unverifiable", None, f"connection error: {type(exc).__name__}")
    return classify_response(response.status_code, str(response.url), response.text, candidate.title)


async def verify_all(
    candidates: list[Candidate],
    client: httpx.AsyncClient | None = None,
    concurrency: int = 8,
    timeout: float = 10.0,
) -> list[Verification]:
    owns_client = client is None
    if client is None:
        client = httpx.AsyncClient(
            follow_redirects=True,
            timeout=timeout,
            headers={"User-Agent": USER_AGENT},
        )
    semaphore = asyncio.Semaphore(concurrency)
    try:
        return list(
            await asyncio.gather(*(_verify_one(client, c, semaphore) for c in candidates))
        )
    finally:
        if owns_client:
            await client.aclose()
