"""The browser optimizer (JS) must agree with the Python reference."""
import json
import math
import shutil
import subprocess

import pytest

from pipeline import optimizer
from tests.conftest import ROOT

node = shutil.which("node")
pytestmark = pytest.mark.skipif(node is None, reason="node not installed")


def test_js_matches_python_paths(games):
    season_json = ROOT / "docs" / "data" / "season.json"
    forces = ["LAC", "JAX", "DET", "PHI", "CIN", "SEA", "PIT", "LV"]
    lambdas = [0, 0.5, 1]
    weeks = list(range(1, 19))
    used = ["KC", "BUF"]
    opts = {"forces": forces, "lambdas": lambdas, "weeks": weeks, "used": used}
    out = subprocess.run([node, str(ROOT / "scripts" / "parity.mjs"), str(season_json), json.dumps(opts)],
                         capture_output=True, text=True, check=True).stdout
    js = json.loads(out)
    data = json.loads(season_json.read_text())["games"]
    for row in js:
        py = optimizer.best_path(data, set(used), weeks, lam=row["lam"], force=row["force"])
        assert (py is None) == (row["path"] is None)
        if py is None:
            continue
        assert py[0] == (1, row["force"])
        # Same optimum: identical objective (ties may pick different equal-cost paths).
        assert math.isclose(optimizer.path_win_out(data, py), row["winOut"], rel_tol=1e-9) or row["lam"] > 0
        if row["lam"] == 0:
            assert [list(x) for x in py] == row["path"]
