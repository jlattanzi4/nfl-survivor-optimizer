import pytest

from pipeline import odds_api


def test_devig_removes_hold():
    ph, pa = odds_api.devig(odds_api.american_to_prob(-200), odds_api.american_to_prob(+170))
    assert ph + pa == pytest.approx(1.0)
    assert ph == pytest.approx(0.643, abs=0.002)


def test_moneyline_roundtrip():
    for ml in (-450, -110, +105, +320):
        p = odds_api.american_to_prob(ml)
        assert abs(odds_api.prob_to_american(p) - ml) <= 1


def test_consensus_weights_pinnacle():
    ev = {
        "home_team": "Kansas City Chiefs", "away_team": "Los Angeles Chargers",
        "bookmakers": [
            {"key": "pinnacle", "markets": [{"key": "h2h", "outcomes": [
                {"name": "Kansas City Chiefs", "price": -150}, {"name": "Los Angeles Chargers", "price": 135}]}]},
            {"key": "draftkings", "markets": [{"key": "h2h", "outcomes": [
                {"name": "Kansas City Chiefs", "price": -180}, {"name": "Los Angeles Chargers", "price": 150}]}]},
        ],
    }
    c = odds_api.consensus(ev)
    pin = odds_api.devig(odds_api.american_to_prob(-150), odds_api.american_to_prob(135))[0]
    dk = odds_api.devig(odds_api.american_to_prob(-180), odds_api.american_to_prob(150))[0]
    assert c["home"] == "KC" and c["away"] == "LAC"
    assert c["p_home"] == pytest.approx((2 * pin + dk) / 3)


def test_to_games_assigns_week():
    ev = {"home_team": "Detroit Lions", "away_team": "New Orleans Saints",
          "commence_time": "2026-09-13T17:00:00Z",
          "bookmakers": [{"key": "fanduel", "markets": [{"key": "h2h", "outcomes": [
              {"name": "Detroit Lions", "price": -300}, {"name": "New Orleans Saints", "price": 240}]}]}]}
    rows = odds_api.to_games([ev], 2026)
    assert {r["team"] for r in rows} == {"DET", "NO"}
    assert all(r["week"] == 1 for r in rows)
    assert sum(r["p"] for r in rows) == pytest.approx(1.0)


def test_merge_requires_two_books():
    from pipeline.build import merge_odds
    games = [{"week": 1, "team": "DET", "opp": "NO", "p": 0.7, "result": None, "src": "spread"},
             {"week": 1, "team": "NO", "opp": "DET", "p": 0.3, "result": None, "src": "spread"}]
    lone = [{"week": 1, "team": "DET", "opp": "NO", "p": 0.8, "ml": -400, "books": 1}]
    assert merge_odds(games, lone) == 0 and games[0]["src"] == "spread"
    pinnacle_only = [{"week": 1, "team": "DET", "opp": "NO", "p": 0.75, "ml": -300, "books": 1, "sharp": True}]
    assert merge_odds(games, pinnacle_only) == 1 and games[0]["p"] == 0.75
    two = [{"week": 1, "team": "DET", "opp": "NO", "p": 0.8, "ml": -400, "books": 2}]
    assert merge_odds(games, two) == 1 and games[0]["src"] == "market" and games[0]["p"] == 0.8
