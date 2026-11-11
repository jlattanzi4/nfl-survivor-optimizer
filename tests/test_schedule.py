"""Kickoff times and final scores from nflverse, and what the build does with them."""
from datetime import UTC, datetime

from pipeline import schedule
from pipeline.build import apply_popularity, build, freeze_started, merge_schedule
from tests.conftest import ROOT

# Rows copied from nflverse's games.csv (trimmed to the columns used), except the
# week 18 row: it is made up, with no kickoff time, because the real file had
# none like it when this was written and the parser must cope when it does.
SAMPLE = (ROOT / "tests" / "fixtures" / "nflverse_games_sample.csv").read_text()


def team_weeks() -> dict:
    return {(g["week"], g["team"]): g for g in schedule.parse(SAMPLE, 2026)}


def test_one_record_per_team_for_regular_season_games_of_the_season():
    tw = team_weeks()
    # 6 regular-season games in 2026; the 2025 game and the playoff game are left out.
    assert len(tw) == 12
    assert (19, "KC") not in tw


def test_kickoff_is_converted_from_eastern_to_utc():
    tw = team_weeks()
    assert tw[(1, "SEA")]["kickoff"] == "2026-09-10T00:20:00Z"     # 20:20 EDT, UTC-4
    assert tw[(9, "BUF")]["kickoff"] == "2026-11-10T01:15:00Z"     # 20:15 EST, UTC-5
    assert tw[(18, "KC")]["kickoff"] is None                       # time not set yet


def test_results_are_from_each_team_s_side():
    tw = team_weeks()
    assert (tw[(9, "BUF")]["result"], tw[(9, "BUF")]["score"]) == ("W", "23-6")
    assert (tw[(9, "MIN")]["result"], tw[(9, "MIN")]["score"]) == ("L", "6-23")
    assert tw[(5, "NYG")]["result"] == "T" and tw[(5, "WAS")]["result"] == "T"
    assert tw[(10, "BUF")]["result"] is None and tw[(10, "BUF")]["score"] is None


def test_sites_and_team_names_match_the_rest_of_the_pipeline():
    tw = team_weeks()
    assert tw[(9, "BUF")]["site"] == "away" and tw[(9, "MIN")]["site"] == "home"
    assert tw[(9, "BUF")]["opp"] == "MIN"
    # nflverse calls the Rams "LA"; a neutral-site game is neutral for both teams.
    assert tw[(1, "LAR")]["site"] == "neutral" and tw[(1, "SF")]["site"] == "neutral"
    assert tw[(1, "SF")]["opp"] == "LAR"


def grid_game(week, team, opp, **over):
    return {"week": week, "team": team, "opp": opp, "site": "home", "spread": -3.0, "result": None,
            "p": 0.62, "src": "spread", "pick": None, **over}


def test_merge_adds_kickoffs_and_results_and_the_weeks_the_grid_no_longer_lists():
    games = [grid_game(9, "BUF", "MIN", site="away"), grid_game(10, "BUF", "NYJ", site="away")]
    stats = merge_schedule(games, schedule.parse(SAMPLE, 2026))
    by = {(g["week"], g["team"]): g for g in games}

    assert by[(9, "BUF")]["result"] == "W" and by[(9, "BUF")]["score"] == "23-6"
    assert by[(9, "BUF")]["p"] == 0.62                    # its pre-game numbers stay
    assert by[(10, "BUF")]["kickoff"] == "2026-11-15T18:00:00Z" and by[(10, "BUF")]["result"] is None
    # Week 1 is gone from SurvivorGrid; the schedule brings it back with no price.
    assert by[(1, "SEA")]["result"] == "W" and by[(1, "SEA")]["p"] is None and by[(1, "SEA")]["spread"] is None
    assert len(games) == 12
    assert stats == {"games": 6, "finals": 4, "added": 10, "mismatched": 0}


def test_a_matchup_the_schedule_disagrees_with_is_left_alone_and_counted():
    games = [grid_game(10, "BUF", "MIA")]
    stats = merge_schedule(games, schedule.parse(SAMPLE, 2026))
    buf = next(g for g in games if (g["week"], g["team"]) == (10, "BUF"))
    assert buf["opp"] == "MIA" and "kickoff" not in buf
    assert stats["mismatched"] == 1


NOW = datetime(2026, 11, 10, 2, 0, tzinfo=UTC)   # during the Monday-night game


def test_a_game_that_has_kicked_off_keeps_every_number_it_had_before():
    before = grid_game(9, "BUF", "MIN", spread=-3.0, p=0.6195, src="market", ml=-163, books=5, pick=0.005,
                       pick_src="public", commence="2026-11-10T01:15:00Z", priced_at="2026-11-09T18:32:47+00:00")
    # The next build sees a moved spread, no market price (off the board) and a new public share.
    now_game = grid_game(9, "BUF", "MIN", spread=-3.5, p=0.64, src="sg_ml", pick=0.02, pick_src="public",
                         kickoff="2026-11-10T01:15:00Z")
    upcoming = grid_game(10, "BUF", "NYJ", spread=-8.0, p=0.79, kickoff="2026-11-15T18:00:00Z")
    was_upcoming = grid_game(10, "BUF", "NYJ", spread=-7.5, p=0.78)

    frozen = freeze_started([now_game, upcoming], [before, was_upcoming], NOW)

    assert frozen == 1
    for key in ("spread", "p", "src", "ml", "books", "pick", "pick_src", "commence", "priced_at"):
        assert now_game[key] == before[key], key
    assert upcoming["spread"] == -8.0 and upcoming["p"] == 0.79     # not started: still moves


def test_freezing_needs_a_priced_record_of_the_same_matchup():
    started = grid_game(9, "BUF", "MIN", p=0.64, kickoff="2026-11-10T01:15:00Z")
    assert freeze_started([started], [], NOW) == 0
    assert freeze_started([started], [grid_game(9, "BUF", "KC", p=0.5)], NOW) == 0
    assert freeze_started([started], [grid_game(9, "BUF", "MIN", p=None)], NOW) == 0
    assert started["p"] == 0.64


def test_popularity_survives_a_grid_week_that_is_already_final():
    # Tuesday morning: SurvivorGrid still shows last week, and every game in it has a result.
    teams = ["BUF", "MIN", "KC", "DEN", "SF", "LV", "DAL", "NYG", "PHI", "WAS"]
    games = [grid_game(9, t, "X", p=0.5 + i / 25, result="W", pick=0.1) for i, t in enumerate(teams)]
    games += [grid_game(10, t, "X", p=0.5 + i / 25) for i, t in enumerate(teams)]
    games.append({"week": 1, "team": "SEA", "opp": "NE", "site": "home", "spread": None, "result": "W",
                  "p": None, "src": "schedule", "pick": None})
    k = apply_popularity(games, 9)
    assert k > 0
    week10 = [g for g in games if g["week"] == 10]
    assert abs(sum(g["pick"] for g in week10) - 1) < 1e-9 and all(g["pick_src"] == "model" for g in week10)


def test_build_carries_the_schedule_when_nflverse_cannot_be_reached(grid_html):
    first = build(grid_html, use_odds=False, now=NOW, schedule_csv=SAMPLE)
    assert first["sources"]["schedule"]["carried"] is False
    known = {(g["week"], g["team"]): g for g in first["games"] if "kickoff" in g}
    assert known[(9, "BUF")]["result"] == "W"

    second = build(grid_html, use_odds=False, now=NOW, previous=first, schedule_csv=None)
    again = {(g["week"], g["team"]): g for g in second["games"] if "kickoff" in g}
    assert second["sources"]["schedule"]["carried"] is True
    assert second["sources"]["schedule"]["fetched_at"] == first["sources"]["schedule"]["fetched_at"]
    assert again.keys() == known.keys()
    for key, g in known.items():
        assert (again[key]["kickoff"], again[key]["result"], again[key]["score"]) == (g["kickoff"], g["result"], g["score"])

    # With nothing to carry, the build still succeeds, just without kickoffs.
    alone = build(grid_html, use_odds=False, now=NOW, schedule_csv=None)
    assert "schedule" not in alone["sources"] and not any("kickoff" in g for g in alone["games"])
