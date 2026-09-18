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


def test_review_flag_defaults_off_and_rounds_default_two():
    payload = build_payload_from_args(parse_args([]))
    assert payload["review_enabled"] is False
    assert payload["max_extra_rounds"] == 2


def test_review_flag_and_rounds():
    payload = build_payload_from_args(parse_args(["--review", "--max-extra-rounds", "0"]))
    assert payload["review_enabled"] is True
    assert payload["max_extra_rounds"] == 0


def test_max_extra_rounds_rejects_out_of_range():
    import pytest
    with pytest.raises(SystemExit):
        parse_args(["--max-extra-rounds", "6"])


def test_interactive_payload_enables_review(monkeypatch):
    from internship_research_demo.cli import build_interactive_payload
    monkeypatch.setattr("builtins.input", lambda _prompt="": "")
    payload = build_interactive_payload()
    assert payload["review_enabled"] is True
    assert payload["max_extra_rounds"] == 2
