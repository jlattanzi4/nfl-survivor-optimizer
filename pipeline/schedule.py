"""The NFL schedule and final scores, from nflverse.

SurvivorGrid lists only the weeks still to play and doesn't mark results, so
on its own the app can't tell a finished game from an upcoming one. nflverse's
``games.csv`` has every game of the season with its kickoff time and, once it's
over, its score. That gives the build three things: which games have started
(they can no longer be picked, and their numbers stop moving), who won (strikes
are counted from it), and the weeks already played (so the grid shows them).

Kickoff times in the file are US Eastern; they are converted to UTC here.
"""
from __future__ import annotations

import csv
import io
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import requests

from .teams import to_abbr

URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"
EASTERN = ZoneInfo("America/New_York")


def fetch_csv(url: str = URL, timeout: int = 30) -> str:
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def _kickoff(gameday: str, gametime: str) -> str | None:
    """Kickoff as a UTC timestamp, or None while the league hasn't set a time."""
    if not gameday or not gametime:
        return None
    local = datetime.strptime(f"{gameday} {gametime}", "%Y-%m-%d %H:%M").replace(tzinfo=EASTERN)
    return local.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _score(text: str) -> int | None:
    return int(text) if text not in ("", "NA") else None


def parse(csv_text: str, season: int) -> list[dict]:
    """One record per team for each regular-season game of ``season``.

    Fields: week, team, opp, site (home | away | neutral), kickoff (UTC, or
    None), result (W | L | T, or None until the game is final) and score
    ("23-6", the team's points first).
    """
    out = []
    for row in csv.DictReader(io.StringIO(csv_text)):
        if row["season"] != str(season) or row["game_type"] != "REG":
            continue
        home, away = to_abbr(row["home_team"]), to_abbr(row["away_team"])
        neutral = row["location"] == "Neutral"
        kickoff = _kickoff(row["gameday"], row["gametime"])
        home_pts, away_pts = _score(row["home_score"]), _score(row["away_score"])
        for team, opp, site, pts, opp_pts in (
            (home, away, "home", home_pts, away_pts),
            (away, home, "away", away_pts, home_pts),
        ):
            final = pts is not None and opp_pts is not None
            out.append({
                "week": int(row["week"]),
                "team": team,
                "opp": opp,
                "site": "neutral" if neutral else site,
                "kickoff": kickoff,
                "result": ("W" if pts > opp_pts else "L" if pts < opp_pts else "T") if final else None,
                "score": f"{pts}-{opp_pts}" if final else None,
            })
    return out
