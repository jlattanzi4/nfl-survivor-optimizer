"""Build ``docs/data/season.json`` from SurvivorGrid and The Odds API.

    python -m pipeline.build                 # live fetch (Odds API if ODDS_API_KEY is set)
    python -m pipeline.build --no-odds       # SurvivorGrid only
    python -m pipeline.build --fixture tests/fixtures/survivorgrid_2026_week1.html
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import odds_api, popularity, season, survivorgrid, teams

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "docs" / "data" / "season.json"


def log(msg: str) -> None:
    print(f"[build] {msg}", file=sys.stderr)


def merge_odds(games: list[dict], odds_games: list[dict]) -> int:
    """Overwrite SurvivorGrid probabilities with consensus market lines where the matchup agrees."""
    idx = {(g["week"], g["team"]): g for g in games}
    applied = 0
    for og in odds_games:
        g = idx.get((og["week"], og["team"]))
        if g is None or g["opp"] != og["opp"] or g["result"] is not None:
            log(f"odds row not matched: wk{og['week']} {og['team']} vs {og['opp']}")
            continue
        g["p"] = og["p"]
        g["ml"] = og["ml"]
        g["src"] = "market"
        g["books"] = og["books"]
        applied += 1
    return applied


def apply_popularity(games: list[dict], sg_week: int) -> float:
    current = {g["team"]: g["p"] for g in games if g["week"] == sg_week and g["result"] is None}
    observed = {g["team"]: g["pick"] for g in games if g["week"] == sg_week and g.get("pick") is not None}
    k = popularity.fit_k(current, observed)
    for w in range(1, season.TOTAL_WEEKS + 1):
        wk = [g for g in games if g["week"] == w and g["result"] is None]
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


def build(html: str, use_odds: bool, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    yr = int(os.environ.get("SEASON") or season.season_for(now))
    rows = survivorgrid.parse_html(html)
    games = survivorgrid.to_games(rows)
    sg_week = survivorgrid.grid_current_week(rows)
    log(f"survivorgrid: {len(games)} team-weeks, grid week {sg_week}")

    sources = {"survivorgrid": {"fetched_at": now.isoformat(timespec="seconds"), "week": sg_week}}
    if use_odds:
        try:
            raw = odds_api.fetch(season=yr)
            og = odds_api.to_games(raw["events"], yr)
            applied = merge_odds(games, og)
            sources["odds_api"] = {
                "fetched_at": raw["fetched_at"],
                "events": len(raw["events"]),
                "applied": applied,
                "credits_remaining": raw["remaining"],
                "books": odds_api.BOOKS,
            }
            log(f"odds api: {len(raw['events'])} events, {applied} team-weeks updated, {raw['remaining']} credits left")
        except Exception as exc:  # network / quota / key problems must not break the build
            log(f"odds api skipped: {exc}")
            sources["odds_api"] = {"error": str(exc)}

    k = apply_popularity(games, sg_week)
    log(f"popularity model k={k}")

    for g in games:
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
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args(argv)

    html = Path(args.fixture).read_text() if args.fixture else survivorgrid.fetch_html()
    use_odds = not args.no_odds and bool(os.environ.get("ODDS_API_KEY"))
    if not use_odds and not args.no_odds:
        log("ODDS_API_KEY not set; SurvivorGrid only")
    data = build(html, use_odds)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, separators=(",", ":")))
    log(f"wrote {out} ({out.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
