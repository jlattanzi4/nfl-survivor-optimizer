"""Market probabilities come from pre-game odds only, and survive kickoff."""
from datetime import UTC, datetime

from pipeline import odds_api
from pipeline.build import build, carry_forward

KICKOFF = "2026-11-10T01:15:00Z"  # a Monday-night game


def unresolved(team: str, opp: str, p: float, src: str = "spread", result: str | None = None) -> dict:
    return {"week": 10, "team": team, "opp": opp, "p": p, "result": result, "src": src}


def priced(team: str, opp: str, p: float, priced_at: str, ml: int = -400) -> dict:
    return {**unresolved(team, opp, p, "market"), "ml": ml, "books": 6, "commence": KICKOFF, "priced_at": priced_at}


BEFORE_KICKOFF = "2026-11-09T16:00:00+00:00"
AFTER_KICKOFF = "2026-11-10T02:00:00+00:00"


class FakeResponse:
    def __init__(self) -> None:
        self.headers = {"x-requests-remaining": "478", "x-requests-last": "1"}

    def raise_for_status(self) -> None:
        pass

    def json(self) -> list:
        return []


def test_fetch_asks_only_for_games_not_yet_started(monkeypatch):
    sent = {}

    def fake_get(url, params, timeout):
        sent.update(params)
        return FakeResponse()

    monkeypatch.setattr(odds_api.requests, "get", fake_get)
    odds_api.fetch(api_key="test", now=datetime(2026, 11, 9, 16, 0, tzinfo=UTC))

    assert sent["commenceTimeFrom"] == "2026-11-09T16:00:00Z"


def test_keeps_the_last_pregame_price_once_a_game_drops_off_the_board():
    games = [unresolved("KC", "LAC", 0.70)]

    carried = carry_forward(games, [priced("KC", "LAC", 0.80, BEFORE_KICKOFF)])

    assert carried == 1
    assert games[0]["p"] == 0.80
    assert games[0]["src"] == "market"
    assert games[0]["ml"] == -400


def test_never_carries_a_price_taken_after_kickoff():
    games = [unresolved("KC", "LAC", 0.70)]

    carry_forward(games, [priced("KC", "LAC", 0.93, AFTER_KICKOFF)])

    assert games[0]["p"] == 0.70


def test_never_carries_prices_without_timestamps():
    # Records written before kickoff times were tracked may hold in-play prices.
    old = {**unresolved("KC", "LAC", 0.93, "market"), "ml": -1300, "books": 6}
    games = [unresolved("KC", "LAC", 0.70)]

    carry_forward(games, [old])

    assert games[0]["p"] == 0.70


def test_leaves_finished_games_alone():
    games = [unresolved("KC", "LAC", 1.0, result="W")]

    carry_forward(games, [priced("KC", "LAC", 0.80, BEFORE_KICKOFF)])

    assert games[0]["p"] == 1.0


def test_needs_the_same_matchup():
    games = [unresolved("KC", "DEN", 0.70)]

    carry_forward(games, [priced("KC", "LAC", 0.80, BEFORE_KICKOFF)])

    assert games[0]["p"] == 0.70


def test_a_fresh_price_beats_a_carried_one():
    games = [{**priced("KC", "LAC", 0.85, BEFORE_KICKOFF), "ml": -567}]

    carry_forward(games, [priced("KC", "LAC", 0.80, "2026-11-08T16:00:00+00:00")])

    assert games[0]["p"] == 0.85


# Week 1 of the SurvivorGrid fixture has Detroit hosting New Orleans.
DET_NO = {
    "home_team": "Detroit Lions", "away_team": "New Orleans Saints",
    "commence_time": "2026-09-13T17:00:00Z",
    "bookmakers": [
        {"key": "pinnacle", "markets": [{"key": "h2h", "outcomes": [
            {"name": "Detroit Lions", "price": -400}, {"name": "New Orleans Saints", "price": 330}]}]},
        {"key": "fanduel", "markets": [{"key": "h2h", "outcomes": [
            {"name": "Detroit Lions", "price": -420}, {"name": "New Orleans Saints", "price": 340}]}]},
    ],
}


def fake_fetch(events: list[dict], fetched_at: str):
    return lambda **_: {"events": events, "remaining": "478", "cost": "1", "fetched_at": fetched_at}


def detroit(data: dict) -> dict:
    return next(g for g in data["games"] if g["week"] == 1 and g["team"] == "DET")


def test_a_started_game_keeps_its_pregame_price_across_rebuilds(grid_html, monkeypatch):
    monkeypatch.setattr(odds_api, "fetch", fake_fetch([DET_NO], "2026-09-13T08:00:00+00:00"))
    morning = build(grid_html, use_odds=True, now=datetime(2026, 9, 13, 8, 0, tzinfo=UTC))
    # After kickoff the odds request no longer returns the game.
    monkeypatch.setattr(odds_api, "fetch", fake_fetch([], "2026-09-13T18:00:00+00:00"))
    in_play = build(grid_html, use_odds=True, now=datetime(2026, 9, 13, 18, 0, tzinfo=UTC), previous=morning)

    assert detroit(morning)["src"] == "market"
    assert detroit(in_play)["src"] == "market"
    assert detroit(in_play)["p"] == detroit(morning)["p"]


def test_ignores_prices_from_another_season(grid_html, monkeypatch):
    monkeypatch.setattr(odds_api, "fetch", fake_fetch([DET_NO], "2026-09-13T08:00:00+00:00"))
    last_year = build(grid_html, use_odds=True, now=datetime(2026, 9, 13, 8, 0, tzinfo=UTC))
    last_year["season"] = 2025
    monkeypatch.setattr(odds_api, "fetch", fake_fetch([], "2026-09-13T18:00:00+00:00"))

    rebuilt = build(grid_html, use_odds=True, now=datetime(2026, 9, 13, 18, 0, tzinfo=UTC), previous=last_year)

    assert detroit(rebuilt)["src"] != "market"
