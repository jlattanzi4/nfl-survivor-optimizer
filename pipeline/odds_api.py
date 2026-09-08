"""The Odds API client: de-vigged, Pinnacle-weighted consensus moneylines.

Only the current NFL round is listed by books, so this covers this week
(and occasionally the start of next).  Each call costs one credit per
region touched; with Pinnacle (eu) plus US books that is 2 credits.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

import requests

from .season import week_for
from .teams import to_abbr

BASE = "https://api.the-odds-api.com/v4"
BOOKS = ["pinnacle", "draftkings", "fanduel", "betmgm", "caesars", "betrivers"]
WEIGHTS = {"pinnacle": 2.0}


def american_to_prob(ml: float) -> float:
    ml = float(ml)
    return -ml / (-ml + 100.0) if ml < 0 else 100.0 / (ml + 100.0)


def prob_to_american(p: float) -> int:
    p = min(max(p, 0.001), 0.999)
    return round(-100 * p / (1 - p)) if p >= 0.5 else round(100 * (1 - p) / p)


def devig(p_a: float, p_b: float) -> tuple[float, float]:
    """Multiplicative vig removal: scale both implied probabilities to sum to 1."""
    s = p_a + p_b
    return p_a / s, p_b / s


def consensus(game: dict) -> dict | None:
    """Weighted average of de-vigged h2h prices across bookmakers."""
    home, away = to_abbr(game["home_team"]), to_abbr(game["away_team"])
    num = 0.0
    den = 0.0
    books = []
    for bk in game.get("bookmakers", []):
        h2h = next((m for m in bk.get("markets", []) if m.get("key") == "h2h"), None)
        if not h2h:
            continue
        prices = {to_abbr(o["name"]): o["price"] for o in h2h.get("outcomes", [])}
        if home not in prices or away not in prices:
            continue
        ph, pa = devig(american_to_prob(prices[home]), american_to_prob(prices[away]))
        w = WEIGHTS.get(bk["key"], 1.0)
        num += w * ph
        den += w
        books.append(bk["key"])
    if den == 0:
        return None
    p_home = num / den
    return {"home": home, "away": away, "p_home": p_home, "books": books}


def fetch(api_key: str | None = None, season: int | None = None) -> dict:
    api_key = api_key or os.environ.get("ODDS_API_KEY", "")
    if not api_key:
        raise RuntimeError("ODDS_API_KEY not set")
    resp = requests.get(
        f"{BASE}/sports/americanfootball_nfl/odds",
        params={
            "apiKey": api_key,
            "markets": "h2h",
            "oddsFormat": "american",
            "bookmakers": ",".join(BOOKS),
        },
        timeout=20,
    )
    resp.raise_for_status()
    return {
        "events": resp.json(),
        "remaining": resp.headers.get("x-requests-remaining"),
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def to_games(events: list[dict], season: int) -> list[dict]:
    """One record per team per game with consensus fair probability and moneyline."""
    out = []
    for ev in events:
        c = consensus(ev)
        if not c:
            continue
        when = datetime.fromisoformat(ev["commence_time"].replace("Z", "+00:00"))
        week = week_for(when, season)
        for team, opp, p in ((c["home"], c["away"], c["p_home"]), (c["away"], c["home"], 1 - c["p_home"])):
            out.append({
                "week": week,
                "team": team,
                "opp": opp,
                "p": p,
                "ml": prob_to_american(p),
                "books": len(c["books"]),
                "commence": ev["commence_time"],
            })
    return out
