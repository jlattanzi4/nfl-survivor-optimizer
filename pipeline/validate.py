"""Check a build before it replaces the published file.

    python -m pipeline.validate [docs/data/season.json]

The page trusts ``season.json`` completely, so a bad build is worse than an old
one: the old file stays up, and the page says how old it is. Three kinds of
finding:

* A record the page could not draw (unknown team, impossible week, a
  probability outside 0–1, the same team-week twice) is always an error.
* A game with a problem (one side missing, the two sides disagreeing, an
  upcoming game with no win probability) is a warning for up to
  ``MAX_ODD_GAMES`` games and an error beyond that. One odd cell on
  SurvivorGrid should cost one game, not the whole refresh.
* Whole-file checks: pick shares add up in each week that hasn't started, every
  team has 17 games once the schedule is merged, and no result disappears.

The tolerances are set from the builds already published; see
``scripts/replay_validation.py``.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

MAX_ODD_GAMES = 2
P_SUM_TOLERANCE = 0.002      # each side is rounded to four places
PICK_SUM_TOLERANCE = 0.02    # public shares are published to a tenth of a percent, so 32 of them drift
GAMES_PER_TEAM = 17
TEAMS = 32
WEEKS = range(1, 19)

OTHER_SITE = {"home": "away", "away": "home", "neutral": "neutral"}
OTHER_RESULT = {"W": "L", "L": "W", "T": "T", None: None}
REQUIRED = ("week", "team", "opp", "site", "result", "p")


@dataclass
class Report:
    errors: list[str]
    warnings: list[str]

    @property
    def ok(self) -> bool:
        return not self.errors


def _is_share(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= 1


def _malformed(g: dict, teams: set[str]) -> str | None:
    """Why the page could not draw this record, or None if it could."""
    missing = [k for k in REQUIRED if k not in g]
    if missing:
        return f"missing {', '.join(missing)}"
    if g["week"] not in WEEKS:
        return f"week {g['week']!r} is not 1–18"
    for key in ("team", "opp"):
        if g[key] not in teams:
            return f"unknown team {g[key]!r}"
    if g["team"] == g["opp"]:
        return "plays itself"
    if g["site"] not in OTHER_SITE:
        return f"site {g['site']!r}"
    if g["result"] not in OTHER_RESULT:
        return f"result {g['result']!r}"
    if g["p"] is not None and not _is_share(g["p"]):
        return f"win probability {g['p']!r}"
    if g.get("pick") is not None and not _is_share(g["pick"]):
        return f"pick share {g['pick']!r}"
    if g.get("kickoff") is not None and _when(g["kickoff"]) is None:
        return f"kickoff {g['kickoff']!r}"
    return None


def _when(stamp: object) -> datetime | None:
    """A timestamp as an aware datetime (UTC if it names no zone), or None if it isn't one."""
    try:
        at = datetime.fromisoformat(stamp)
    except (TypeError, ValueError):
        return None
    return at if at.tzinfo else at.replace(tzinfo=UTC)


def _disagreement(a: dict, b: dict) -> str | None:
    """How the two sides of one game contradict each other, if they do."""
    if OTHER_SITE[a["site"]] != b["site"]:
        return f"sites are {a['site']} and {b['site']}"
    if OTHER_RESULT[a["result"]] != b["result"]:
        return f"results are {a['result']} and {b['result']}"
    if a["p"] is not None and b["p"] is not None and abs(a["p"] + b["p"] - 1) > P_SUM_TOLERANCE:
        return f"win probabilities sum to {a['p'] + b['p']:.4g}"
    return None


def _odd_games(games: list[dict]) -> dict[tuple, str]:
    """Each game with a problem, keyed by (week, team, team), with what is wrong."""
    by_side = {(g["week"], g["team"]): g for g in games}
    odd: dict[tuple, str] = {}
    for g in games:
        game = (g["week"], *sorted((g["team"], g["opp"])))
        if game in odd:
            continue
        other = by_side.get((g["week"], g["opp"]))
        if other is None or other["opp"] != g["team"]:
            odd[game] = f"only {g['team']}'s side is there"
        elif why := _disagreement(g, other):
            odd[game] = why
        elif g["result"] is None and g["p"] is None:
            odd[game] = f"{g['team']} has no win probability"
    return odd


def check(data: dict, previous: dict | None = None) -> Report:
    """Validate a build. ``previous`` is the file it would replace, if there is one."""
    errors: list[str] = []
    warnings: list[str] = []

    teams = {t.get("abbr") for t in data.get("teams") or []}
    if len(teams) != TEAMS:
        errors.append(f"{len(teams)} teams in the team table, expected {TEAMS}")
    generated = _when(data.get("generated_at"))
    if generated is None:
        errors.append(f"generated_at {data.get('generated_at')!r} is not a time")
    if data.get("grid_week") not in WEEKS:
        errors.append(f"grid_week {data.get('grid_week')!r} is not 1–18")
    games = data.get("games") or []
    if not games:
        errors.append("no games")

    seen: set[tuple] = set()
    for g in games:
        where = f"wk{g.get('week')} {g.get('team')}"
        if why := _malformed(g, teams):
            errors.append(f"{where}: {why}")
        elif (g["week"], g["team"]) in seen:
            errors.append(f"{where}: listed twice")
        else:
            seen.add((g["week"], g["team"]))
    if errors:
        return Report(errors, warnings)     # the checks below assume well-formed records

    odd = _odd_games(games)
    lines = [f"wk{week} {a}–{b}: {why}" for (week, a, b), why in sorted(odd.items())]
    if len(odd) > MAX_ODD_GAMES:
        shown = "; ".join(lines[:8]) + ("; …" if len(lines) > 8 else "")
        errors.append(f"{len(odd)} games have a problem (up to {MAX_ODD_GAMES} are let through): {shown}")
    else:
        warnings.extend(lines)

    odd_weeks = {game[0] for game in odd}
    for week in WEEKS:
        wk = [g for g in games if g["week"] == week]
        started = any(g["result"] is not None or (g.get("kickoff") and _when(g["kickoff"]) <= generated) for g in wk)
        if not wk or started or week in odd_weeks:
            continue        # shares freeze game by game once a week is under way, so they no longer add up
        total = sum(g.get("pick") or 0 for g in wk)
        if abs(total - 1) > PICK_SUM_TOLERANCE:
            errors.append(f"wk{week}: pick shares sum to {total:.3f}, not 1")

    if "schedule" in (data.get("sources") or {}):
        counts = Counter(g["team"] for g in games)
        off = {t: counts[t] for t in sorted(teams) if counts[t] != GAMES_PER_TEAM}
        if off:
            listed = ", ".join(f"{t} {n}" for t, n in off.items())
            message = f"not every team has {GAMES_PER_TEAM} games: {listed}"
            gap = sum(abs(GAMES_PER_TEAM - n) for n in off.values())
            (errors if gap > 2 * MAX_ODD_GAMES else warnings).append(message)

    if previous and previous.get("season") == data.get("season"):
        by_side = {(g["week"], g["team"]): g for g in games}
        lost = sorted((g["week"], g["team"]) for g in previous.get("games") or []
                      if g.get("result") is not None and (by_side.get((g["week"], g["team"])) or {}).get("result") is None)
        if lost:
            some = ", ".join(f"wk{week} {team}" for week, team in lost[:6]) + (", …" if len(lost) > 6 else "")
            errors.append(f"{len(lost)} team-weeks that were final in the last build are not final now: {some}")

    return Report(errors, warnings)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    path = Path(args[0]) if args else Path(__file__).resolve().parent.parent / "docs" / "data" / "season.json"
    report = check(json.loads(path.read_text()))
    for w in report.warnings:
        print(f"warning: {w}")
    for e in report.errors:
        print(f"error: {e}")
    print(f"{path}: {'ok' if report.ok else 'FAILED'} ({len(report.errors)} errors, {len(report.warnings)} warnings)")
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
