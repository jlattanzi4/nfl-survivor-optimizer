"""The browser optimizer (JS) must agree with the Python reference.

Both run on a saved build (``tests/fixtures/season_2026_week10.json``, the file
published on 2026-11-11) at a fixed time. Run against the live file at the
current time, the comparison shrank as the season went on until it compared
nothing; here every case is counted, so it can't pass empty.
"""
import json
import math
import shutil
import subprocess
from datetime import UTC, datetime

import pytest

from pipeline import optimizer
from tests.conftest import ROOT

node = shutil.which("node")
pytestmark = pytest.mark.skipif(node is None, reason="node not installed")

SEASON = ROOT / "tests" / "fixtures" / "season_2026_week10.json"
WEEKS = list(range(10, 19))
USED = ["KC", "BUF", "PHI"]            # PHI is on its bye in week 10; KC and BUF play in the early window
LAMBDAS = [0, 0.5, 1, 1.5]             # every setting the page offers, two-life pools included

WEDNESDAY = datetime(2026, 11, 11, 20, tzinfo=UTC)   # nothing in week 10 has kicked off
SUNDAY = datetime(2026, 11, 15, 19, tzinfo=UTC)      # Thursday's game, the 9:30 game and the early window have
LATE = {"ARI", "LAR", "LV", "SEA", "DAL", "SF", "CIN", "PIT", "BAL", "LAC"}   # still to kick off on Sunday at 19:00


@pytest.fixture(scope="module")
def season():
    return json.loads(SEASON.read_text())


def week10(season):
    return sorted(g["team"] for g in season["games"] if g["week"] == 10)


def js_paths(now, forces):
    opts = {"forces": forces, "lambdas": LAMBDAS, "weeks": WEEKS, "used": USED, "now": now.isoformat()}
    out = subprocess.run([node, str(ROOT / "scripts" / "parity.mjs"), str(SEASON), json.dumps(opts)],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def cost(games, path, lam):
    """The Python objective for a path, whoever found it. Lower is better."""
    total = 0.0
    for week, team in path:
        wk = [g for g in games if g["week"] == week]
        p = next(g["p"] for g in wk if g["team"] == team)
        total += -math.log(min(max(p, 1e-4), 1 - 1e-4)) + lam * math.log(optimizer.field_survival(wk, team))
    return total


def compare(season, now, forces):
    """Check every forced pick at every λ; return how many had a path and how many had none."""
    games = optimizer.pickable(season["games"], now)
    can_pick = {(g["week"], g["team"]) for g in games}
    found = none = 0
    for row in js_paths(now, forces):
        where = f"{row['force']} at λ={row['lam']}"
        py = optimizer.best_path(games, set(USED), WEEKS, lam=row["lam"], force=row["force"])
        assert (py is None) == (row["path"] is None), where
        if py is None:
            none += 1
            continue
        found += 1
        js = [tuple(x) for x in row["path"]]
        # A legal path: this week's forced pick, then one team a week, none twice, none already used.
        assert js[0] == (10, row["force"]), where
        assert [w for w, _ in js] == WEEKS, where
        assert len({t for _, t in js}) == len(WEEKS) and not {t for _, t in js} & set(USED), where
        assert set(js) <= can_pick, where
        # The same optimum. Two paths can tie, so compare what they score, not which teams they use.
        assert math.isclose(cost(games, js, row["lam"]), cost(games, py, row["lam"]), rel_tol=1e-9, abs_tol=1e-12), where
        assert math.isclose(row["winOut"], optimizer.path_win_out(games, js), rel_tol=1e-9), where
    return found, none


def test_every_week_10_pick_has_the_same_best_path_before_kickoff(season):
    forces = [t for t in week10(season) if t not in USED]
    assert len(forces) == 26
    found, none = compare(season, WEDNESDAY, forces)
    assert (found, none) == (26 * len(LAMBDAS), 0)


def test_teams_that_have_kicked_off_cannot_be_picked_in_either(season):
    forces = week10(season)
    found, none = compare(season, SUNDAY, forces)
    # Only the ten teams in games still to start have a path; the 18 that kicked off have none.
    assert found == len(LATE) * len(LAMBDAS)
    assert none == (len(forces) - len(LATE)) * len(LAMBDAS)


def test_a_used_team_or_a_team_on_its_bye_has_no_path_in_either(season):
    assert compare(season, WEDNESDAY, ["KC", "PHI"]) == (0, 2 * len(LAMBDAS))
