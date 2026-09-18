from datetime import date

TERMS = ("Winter", "Spring", "Summer", "Fall")


def current_term(today: date) -> tuple[str, int]:
    """Map a date to its academic term. December belongs to next year's Winter."""
    month = today.month
    if month == 12:
        return ("Winter", today.year + 1)
    if month <= 2:
        return ("Winter", today.year)
    if month <= 5:
        return ("Spring", today.year)
    if month <= 8:
        return ("Summer", today.year)
    return ("Fall", today.year)


def _next_term(term: str, year: int) -> tuple[str, int]:
    index = TERMS.index(term)
    if index == len(TERMS) - 1:
        return (TERMS[0], year + 1)
    return (TERMS[index + 1], year)


def upcoming_seasons(today: date, n: int = 5) -> list[str]:
    """The current term followed by the next n - 1 terms."""
    term, year = current_term(today)
    seasons = []
    for _ in range(n):
        seasons.append(f"{term} {year}")
        term, year = _next_term(term, year)
    return seasons


def default_season(today: date) -> str:
    """The first Summer term strictly after the current term."""
    term, year = _next_term(*current_term(today))
    while term != "Summer":
        term, year = _next_term(term, year)
    return f"{term} {year}"
