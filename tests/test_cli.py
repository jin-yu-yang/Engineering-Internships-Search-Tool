from datetime import date

from internship_research_demo.cli import _ask_season, build_payload_from_args, parse_args
from internship_research_demo.seasons import default_season

SEPT = date(2026, 9, 18)


def test_season_flag_defaults_to_next_summer():
    assert parse_args([]).season == default_season(date.today())


def test_season_flag_accepts_any_text():
    payload = build_payload_from_args(parse_args(["--season", "Fall 2027"]))
    assert payload["season"] == "Fall 2027"


def test_ask_season_by_number(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _prompt: "2")
    assert _ask_season(SEPT) == "Winter 2027"


def test_ask_season_blank_uses_default(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _prompt: "")
    assert _ask_season(SEPT) == "Summer 2027"


def test_ask_season_custom_text(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _prompt: "Summer 2028")
    assert _ask_season(SEPT) == "Summer 2028"


def test_ask_season_out_of_range_number_is_custom_text(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _prompt: "9")
    assert _ask_season(SEPT) == "9"
