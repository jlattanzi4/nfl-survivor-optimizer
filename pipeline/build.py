"""Build ``docs/data/season.json`` from SurvivorGrid, The Odds API and nflverse.

    python -m pipeline.build                 # live fetch (Odds API if ODDS_API_KEY is set)
    python -m pipeline.build --no-odds       # no market lines
    python -m pipeline.build --no-schedule   # no kickoff times or results
    python -m pipeline.build --fixture tests/fixtures/survivorgrid_2026_week1.html
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from . import odds_api, popularity, schedule, season, survivorgrid, teams

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "docs" / "data" / "season.json"


def log(msg: str) -> None:
    print(f"[build] {msg}", file=sys.stderr)


MIN_BOOKS = 2   # a lone soft book's look-ahead line is not a consensus; a lone Pinnacle line is fine


def merge_odds(games: list[dict], odds_games: list[dict]) -> int:
    """Overwrite SurvivorGrid probabilities with consensus market lines where the matchup agrees."""
    idx = {(g["week"], g["team"]): g for g in games}
    applied = 0
    for og in odds_games:
        if og["books"] < MIN_BOOKS and not og.get("sharp"):
            continue
        g = idx.get((og["week"], og["team"]))
        if g is None or g["opp"] != og["opp"] or g["result"] is not None:
            log(f"odds row not matched: wk{og['week']} {og['team']} vs {og['opp']}")
            continue
        g["p"] = og["p"]
        g["ml"] = og["ml"]
        g["src"] = "market"
        g["books"] = og["books"]
        g["commence"] = og.get("commence")
        g["priced_at"] = og.get("priced_at")
        applied += 1
    return applied


def _utc(ts: str) -> datetime:
    return datetime.fromisoformat(ts)


def carry_forward(games: list[dict], previous: list[dict]) -> int:
    """Keep a game's last pre-game market price once it drops off the odds board.

    The odds request only covers games that haven't kicked off, so a game in
    progress (or finished, before SurvivorGrid posts the result) gets no fresh
    price and would otherwise fall back to the spread mid-game. Only prices
    taken before kickoff carry; older records without timestamps never do.
    """
    prev = {(g["week"], g["team"]): g for g in previous if g.get("src") == "market"}
    carried = 0
    for g in games:
        if g["result"] is not None or g.get("src") == "market":
            continue
        old = prev.get((g["week"], g["team"]))
        if not old or old["opp"] != g["opp"] or not old.get("commence") or not old.get("priced_at"):
            continue
        if _utc(old["priced_at"]) >= _utc(old["commence"]):
            continue
        for key in ("p", "ml", "src", "books", "commence", "priced_at"):
            g[key] = old[key]
        carried += 1
    return carried


def merge_schedule(games: list[dict], team_weeks: list[dict]) -> dict:
    """Add kickoff times and final results, and the weeks SurvivorGrid no longer lists.

    A game SurvivorGrid has keeps its own numbers and gains a kickoff and, once
    final, a result and score. A game it doesn't have (a week already played)
    is added with no price. If the two sources disagree on who plays whom, the
    record is left alone and counted, because a result attached to the wrong
    matchup is worse than none.
    """
    idx = {(g["week"], g["team"]): g for g in games}
    stats = {"games": len(team_weeks) // 2, "finals": sum(t["result"] is not None for t in team_weeks) // 2,
             "added": 0, "mismatched": 0}
    for tw in team_weeks:
        g = idx.get((tw["week"], tw["team"]))
        if g is None:
            games.append({**tw, "spread": None, "p": None, "src": "schedule", "pick": None})
            stats["added"] += 1
        elif g["opp"] != tw["opp"]:
            log(f"schedule disagrees: wk{tw['week']} {tw['team']} vs {tw['opp']} (grid has {g['opp']})")
            stats["mismatched"] += 1
        else:
            g["kickoff"], g["score"] = tw["kickoff"], tw["score"]
            if tw["result"] is not None:
                g["result"] = tw["result"]
    return stats


def schedule_from(previous: list[dict]) -> list[dict]:
    """The schedule as the last build knew it, for a build that can't reach nflverse.

    Without it a failed download would make finished games look upcoming again.
    """
    fields = ("week", "team", "opp", "site", "kickoff", "result", "score")
    return [{f: g.get(f) for f in fields} for g in previous if "kickoff" in g]


FROZEN_AT_KICKOFF = ("spread", "p", "ml", "src", "books", "commence", "priced_at", "pick", "pick_src")


def freeze_started(games: list[dict], previous: list[dict], now: datetime) -> int:
    """Once a game has kicked off, nothing about it moves.

    Its spread, win probability and public share are taken from the last build,
    which was either made before kickoff or was itself frozen. Without this the
    page would show in-game lines and a still-shifting pick share next to a
    pick that can no longer be changed.
    """
    prev = {(g["week"], g["team"]): g for g in previous}
    frozen = 0
    for g in games:
        if not g.get("kickoff") or _utc(g["kickoff"]) > now:
            continue
        old = prev.get((g["week"], g["team"]))
        if not old or old["opp"] != g["opp"] or old.get("p") is None:
            continue
        for key in FROZEN_AT_KICKOFF:
            if key in old:
                g[key] = old[key]
            else:
                g.pop(key, None)
        frozen += 1
    return frozen


def apply_popularity(games: list[dict], sg_week: int) -> float:
    # Fit on the grid's week even when its games are already final (Tuesday
    # morning, before SurvivorGrid rolls over): how chalky the public was
    # last week is still the best guide to next week.
    current = {g["team"]: g["p"] for g in games if g["week"] == sg_week and g.get("p") is not None}
    observed = {g["team"]: g["pick"] for g in games if g["week"] == sg_week and g.get("pick") is not None}
    k = popularity.fit_k(current, observed)
    for w in range(1, season.TOTAL_WEEKS + 1):
        wk = [g for g in games if g["week"] == w and g["result"] is None and g.get("p") is not None]
        if w == sg_week and observed:
            for g in wk:
                g["pick"] = g.get("pick") or 0.0
                g["pick_src"] = "public"
            continue
        shares = popularity.softmax_shares({g["team"]: g["p"] for g in wk}, k)
        for g in wk:
            g["pick"] = shares.get(g["team"], 0.0)
            g["pick_src"] = "model"
    return k


def build(html: str, use_odds: bool, now: datetime | None = None, previous: dict | None = None,
          schedule_csv: str | None = None) -> dict:
    now = now or datetime.now(UTC)
    yr = int(os.environ.get("SEASON") or season.season_for(now))
    rows = survivorgrid.parse_html(html)
    games = survivorgrid.to_games(rows)
    sg_week = survivorgrid.grid_current_week(rows)
    log(f"survivorgrid: {len(games)} team-weeks, grid week {sg_week}")

    sources = {"survivorgrid": {"fetched_at": now.isoformat(timespec="seconds"), "week": sg_week}}
    if use_odds:
        try:
            raw = odds_api.fetch(season=yr)
            og = odds_api.to_games(raw["events"], yr, priced_at=raw["fetched_at"])
            applied = merge_odds(games, og)
            sources["odds_api"] = {
                "fetched_at": raw["fetched_at"],
                "events": len(raw["events"]),
                "applied": applied,
                "credits_remaining": raw["remaining"],
                "credits_last_call": raw["cost"],
                "books": odds_api.BOOKS,
            }
            log(f"odds api: {len(raw['events'])} events, {applied} team-weeks updated, "
                f"call cost {raw['cost']} credits, {raw['remaining']} left")
        except Exception as exc:  # noqa: BLE001  network, quota or key problems must not break the build
            log(f"odds api skipped: {exc}")
            sources["odds_api"] = {"error": str(exc)}
        if previous and previous.get("season") == yr:
            carried = carry_forward(games, previous["games"])
            sources["odds_api"]["carried"] = carried
            log(f"kept the last pre-game price for {carried} team-weeks off the odds board")

    same_season = bool(previous) and previous.get("season") == yr
    if schedule_csv is not None:
        team_weeks, fetched_at = schedule.parse(schedule_csv, yr), now.isoformat(timespec="seconds")
    else:   # no download this time: keep what the last build knew
        team_weeks = schedule_from(previous["games"]) if same_season else []
        fetched_at = previous["sources"].get("schedule", {}).get("fetched_at") if team_weeks else None
    if team_weeks:
        stats = merge_schedule(games, team_weeks)
        sources["schedule"] = {"fetched_at": fetched_at, "carried": schedule_csv is None, **stats}
        log(f"schedule{' (from the last build)' if schedule_csv is None else ''}: {stats['games']} games, "
            f"{stats['finals']} final, {stats['added']} team-weeks added for weeks already played, "
            f"{stats['mismatched']} mismatched")

    k = apply_popularity(games, sg_week)
    log(f"popularity model k={k}")

    if same_season:
        frozen = freeze_started(games, previous["games"], now)
        log(f"froze {frozen} team-weeks that have kicked off")

    for g in games:
        if g["p"] is not None:
            g["p"] = round(g["p"], 4)
        if g.get("pick") is not None:
            g["pick"] = round(g["pick"], 4)
        g.setdefault("ml", None)
        g.setdefault("pick_src", None)

    return {
        "season": yr,
        "generated_at": now.isoformat(timespec="seconds"),
        "week_starts": [d.isoformat(timespec="seconds") for d in season.week_starts(yr)],
        "grid_week": sg_week,
        "popularity_k": k,
        "sources": sources,
        "teams": teams.as_json(),
        "games": games,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture", help="parse a saved SurvivorGrid HTML file instead of fetching")
    ap.add_argument("--no-odds", action="store_true")
    ap.add_argument("--no-schedule", action="store_true", help="skip nflverse kickoff times and results")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args(argv)

    html = Path(args.fixture).read_text() if args.fixture else survivorgrid.fetch_html()
    use_odds = not args.no_odds and bool(os.environ.get("ODDS_API_KEY"))
    if not use_odds and not args.no_odds:
        log("ODDS_API_KEY not set; SurvivorGrid only")
    out = Path(args.out)
    # The last build is the memory of pre-game prices for games now underway.
    previous = json.loads(out.read_text()) if out.exists() else None
    schedule_csv = None
    if not args.no_schedule:
        try:
            schedule_csv = schedule.fetch_csv()
        except Exception as exc:  # noqa: BLE001  a schedule outage must not stop the lines from refreshing
            log(f"schedule skipped: {exc}")
    data = build(html, use_odds, previous=previous, schedule_csv=schedule_csv)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, separators=(",", ":")))
    log(f"wrote {out} ({out.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
