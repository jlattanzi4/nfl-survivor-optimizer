"""A build is checked before it replaces the published file."""
import copy
import json
from datetime import UTC, datetime

import pytest

from pipeline import build, validate
from tests.conftest import FIXTURE, with_cell

NOW = datetime(2026, 9, 8, 12, tzinfo=UTC)   # the Tuesday before week 1, when the fixture was saved


@pytest.fixture(scope="module")
def good(grid_html):
    """A real build from the saved SurvivorGrid page: 272 games, none played."""
    return build.build(grid_html, use_odds=False, now=NOW)


@pytest.fixture
def data(good):
    return copy.deepcopy(good)


def side(data, week, team):
    return next(g for g in data["games"] if g["week"] == week and g["team"] == team)


def drop(data, week, team):
    data["games"].remove(side(data, week, team))


def weeks_played(data, team):
    return sorted(g["week"] for g in data["games"] if g["team"] == team)


def cancel(data, week, team):
    """Take a whole game out, as a build would see it: the week's other shares still add up."""
    gone = side(data, week, team)
    for g in (gone, side(data, week, gone["opp"])):
        data["games"].remove(g)
    rest = [g for g in data["games"] if g["week"] == week]
    total = sum(g["pick"] for g in rest)
    for g in rest:
        g["pick"] /= total


def test_a_real_build_passes(good):
    report = validate.check(good)
    assert report.errors == []
    assert report.warnings == []
    assert report.ok


# --- records the page could not draw: always an error -------------------------------------------

@pytest.mark.parametrize("field,value,says", [
    ("opp", "XYZ", "unknown team"),
    ("week", 19, "week"),
    ("site", "moon", "site"),
    ("result", "X", "result"),
    ("p", 1.2, "probability"),
    ("p", float("nan"), "probability"),
    ("pick", -0.1, "pick share"),
    ("kickoff", "next Sunday", "kickoff"),
])
def test_a_malformed_record_is_an_error(data, field, value, says):
    side(data, 3, "GB")[field] = value
    report = validate.check(data)
    assert not report.ok
    assert any("GB" in e and says in e for e in report.errors)


def test_a_record_missing_a_field_is_an_error(data):
    del side(data, 3, "GB")["site"]
    assert any("wk3 GB" in e and "site" in e for e in validate.check(data).errors)


def test_the_same_team_week_twice_is_an_error(data):
    data["games"].append(dict(side(data, 3, "GB")))
    assert any("wk3 GB" in e and "twice" in e for e in validate.check(data).errors)


def test_a_missing_team_table_is_an_error(data):
    data["teams"] = data["teams"][:31]
    assert any("31 teams" in e for e in validate.check(data).errors)


def test_no_games_is_an_error(data):
    data["games"] = []
    assert not validate.check(data).ok


# --- games with a problem: a couple are let through with a warning ------------------------------

def test_a_game_with_one_side_missing_is_a_warning(data):
    drop(data, 3, "GB")
    report = validate.check(data)
    assert report.ok
    assert len(report.warnings) == 1
    assert "wk3" in report.warnings[0] and "GB" in report.warnings[0]


def test_two_games_with_a_problem_are_still_let_through(data):
    first, second, *_ = weeks_played(data, "KC")
    drop(data, first, "KC")
    drop(data, second, "KC")
    report = validate.check(data)
    assert report.ok
    assert len(report.warnings) == 2


def test_three_games_with_a_problem_stop_the_build(data):
    for week in weeks_played(data, "KC")[:3]:
        drop(data, week, "KC")
    report = validate.check(data)
    assert not report.ok
    assert any("3 games" in e for e in report.errors)


def test_sides_whose_probabilities_do_not_sum_to_one_are_a_problem(data):
    side(data, 3, "GB")["p"] = 0.9
    side(data, 3, side(data, 3, "GB")["opp"])["p"] = 0.9
    report = validate.check(data)
    assert report.ok
    assert any("wk3" in w and "sum to 1.8" in w for w in report.warnings)


def test_rounding_to_four_places_is_not_a_problem(data):
    gb = side(data, 3, "GB")
    gb["p"], side(data, 3, gb["opp"])["p"] = 0.6667, 0.3334
    assert validate.check(data).warnings == []


def test_sides_that_disagree_on_the_site_are_a_problem(data):
    gb = side(data, 3, "GB")
    gb["site"] = side(data, 3, gb["opp"])["site"] = "home"
    assert any("wk3" in w and "home" in w for w in validate.check(data).warnings)


def test_sides_that_disagree_on_the_result_are_a_problem(data):
    gb = side(data, 3, "GB")
    gb["result"] = side(data, 3, gb["opp"])["result"] = "W"
    assert any("wk3" in w and "result" in w for w in validate.check(data).warnings)


def test_an_upcoming_game_with_no_probability_is_a_problem(data):
    side(data, 3, "GB")["p"] = None
    assert any("wk3" in w and "no win probability" in w for w in validate.check(data).warnings)


def test_a_played_game_needs_no_probability(data):
    gb = side(data, 1, "GB")
    other = side(data, 1, gb["opp"])
    gb.update(p=None, pick=None, result="W")
    other.update(p=None, pick=None, result="L")
    # Week 1 has started, so its pick shares are no longer expected to add up.
    assert validate.check(data).warnings == []


# --- whole-file checks ---------------------------------------------------------------------------

def test_pick_shares_must_add_up_in_a_week_that_has_not_started(data):
    for g in data["games"]:
        if g["week"] == 6:
            g["pick"] = g["pick"] / 2
    report = validate.check(data)
    assert any("wk6" in e and "pick shares" in e for e in report.errors)


def test_pick_shares_are_not_checked_once_a_week_has_kicked_off(data):
    data["generated_at"] = "2026-10-18T20:00:00+00:00"
    for g in data["games"]:
        if g["week"] == 6:
            g["kickoff"] = "2026-10-18T17:00:00Z"
            g["pick"] = g["pick"] / 2
    assert validate.check(data).ok


def test_with_the_schedule_merged_every_team_has_seventeen_games(data):
    data["sources"]["schedule"] = {"games": 272}
    assert validate.check(data).ok
    for week in weeks_played(data, "GB")[-3:]:     # three whole games gone: more than a cancelled game or two
        cancel(data, week, "GB")
    report = validate.check(data)
    assert any("17 games" in e and "GB" in e for e in report.errors)


def test_one_cancelled_game_is_a_warning(data):
    data["sources"]["schedule"] = {"games": 272}
    cancel(data, weeks_played(data, "GB")[-1], "GB")
    report = validate.check(data)
    assert report.errors == []
    assert any("17 games" in w for w in report.warnings)


def test_a_result_must_not_disappear(data):
    previous = copy.deepcopy(data)
    gb = side(previous, 1, "GB")
    gb["result"], side(previous, 1, gb["opp"])["result"] = "W", "L"
    report = validate.check(data, previous)
    assert any("final in the last build" in e and "wk1" in e for e in report.errors)


def test_last_seasons_results_are_not_compared(data):
    previous = copy.deepcopy(data)
    previous["season"] = data["season"] - 1
    side(previous, 1, "GB")["result"] = "W"
    assert validate.check(data, previous).ok


# --- one bad cell on SurvivorGrid costs one game, not the refresh ---------------------------------

def test_a_cell_that_cannot_be_read_is_recorded_and_the_build_still_passes(grid_html):
    data = build.build(with_cell(grid_html, "JAX", "CLE<br>", "C?E<br>"), use_odds=False, now=NOW)
    skipped = data["sources"]["survivorgrid"]["skipped"]
    assert len(skipped) == 1 and "JAX" in skipped[0]
    report = validate.check(data)
    assert report.ok
    assert len(report.warnings) == 1 and "CLE" in report.warnings[0]


def test_a_clean_build_records_nothing_skipped(good):
    assert good["sources"]["survivorgrid"]["skipped"] == []


def test_a_page_missing_a_team_stops_the_build(grid_html):
    html = grid_html.replace('<td class="teamname">JAX</td>', '<td class="teamname">LON</td>')
    report = validate.check(build.build(html, use_odds=False, now=NOW))
    assert not report.ok
    assert any("17 games have a problem" in e for e in report.errors)


# --- the build refuses to publish a file that fails ----------------------------------------------

ARGS = ["--fixture", str(FIXTURE), "--no-odds", "--no-schedule"]


def test_a_valid_build_is_written(tmp_path, monkeypatch):
    out = tmp_path / "season.json"
    monkeypatch.setenv("SEASON", "2026")
    assert build.main([*ARGS, "--out", str(out)]) == 0
    assert len(json.loads(out.read_text())["games"]) == 544


def test_a_build_that_fails_validation_leaves_the_last_file_alone(tmp_path, monkeypatch, capsys, data):
    # The last build knew a result that this build (an older page, no schedule) does not.
    gb = side(data, 1, "GB")
    gb["result"], side(data, 1, gb["opp"])["result"] = "W", "L"
    out = tmp_path / "season.json"
    out.write_text(json.dumps(data))
    monkeypatch.setenv("SEASON", "2026")
    assert build.main([*ARGS, "--out", str(out)]) == 1
    assert json.loads(out.read_text()) == data
    assert "final in the last build" in capsys.readouterr().err
