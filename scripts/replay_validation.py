"""Run the build validator over every season.json ever published.

    uv run python scripts/replay_validation.py [git-ref]

Each published build is checked against the one before it, the way a live build
is. Run this after changing a rule or a tolerance in ``pipeline/validate.py``:
a rule that would have stopped a build that was fine is too tight. It needs the
full git history, so it is a script and not a test (CI clones one commit).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import validate

FILE = "docs/data/season.json"


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout


def main() -> int:
    ref = sys.argv[1] if len(sys.argv) > 1 else "HEAD"
    commits = [line.split(" ", 1) for line in git("log", "--reverse", "--format=%H %cI", ref, "--", FILE).splitlines()]
    previous = None
    stopped = warned = 0
    worst_pick, worst_p = 0.0, 0.0
    for sha, when in commits:
        data = json.loads(git("show", f"{sha}:{FILE}"))
        report = validate.check(data, previous)
        if not report.ok:
            stopped += 1
            print(f"{when} {sha[:7]} would be stopped: {'; '.join(report.errors)}")
        elif report.warnings:
            warned += 1
            print(f"{when} {sha[:7]} warns: {'; '.join(report.warnings)}")
        games = data["games"]
        by_side = {(g["week"], g["team"]): g for g in games}
        for g in games:
            other = by_side.get((g["week"], g["opp"]))
            if other and g.get("p") is not None and other.get("p") is not None:
                worst_p = max(worst_p, abs(g["p"] + other["p"] - 1))
        for week in validate.WEEKS:
            wk = [g for g in games if g["week"] == week]
            if wk and all(g["result"] is None for g in wk) and any(g.get("pick") is not None for g in wk):
                worst_pick = max(worst_pick, abs(sum(g.get("pick") or 0 for g in wk) - 1))
        previous = data
    print(f"{len(commits)} builds from {commits[0][1][:10]} to {commits[-1][1][:10]}: "
          f"{stopped} would be stopped, {warned} pass with warnings")
    print(f"largest gap seen: win probabilities {worst_p:.4f} (allowed {validate.P_SUM_TOLERANCE}), "
          f"pick shares {worst_pick:.4f} (allowed {validate.PICK_SUM_TOLERANCE})")
    return 1 if stopped else 0


if __name__ == "__main__":
    sys.exit(main())
