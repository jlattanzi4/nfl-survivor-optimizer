"""SurvivorGrid.com parser.

The grid is one HTML table: a row per team with the current week's win
probability (W%, moneyline-derived) and public pick share (P%), followed by
one cell per week describing the matchup and spread from the row team's
point of view.

Cell grammar (all seen on the live site)::

    NYG-7          home vs NYG, favored by 7
    @HOU+0.5       away at HOU, underdog by 0.5
    (n)PHI+1.5     neutral site vs PHI
    NEPK           pick'em vs NE
    @SEAPK         pick'em at SEA
    NYG-7(W)       completed game, won
    BYE
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, asdict

import requests
from bs4 import BeautifulSoup

from .teams import to_abbr

URL = "https://www.survivorgrid.com/"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"

CELL_RE = re.compile(
    r"^(?P<neutral>\(n\))?(?P<away>@)?(?P<opp>[A-Z]{2,3})"
    r"(?P<line>PK|[-+]\d+(?:\.\d+)?)?"
    r"(?:\((?P<result>[WLT])\))?$"
)


def spread_to_prob(spread: float) -> float:
    """Win probability from a point spread (negative = favorite).

    Logistic fit that tracks historical straight-up rates: -3 → 62%,
    -7 → 76%, -10 → 84%, -14 → 91%.
    """
    return 1.0 / (1.0 + 10 ** (spread / 14.0))


@dataclass
class Cell:
    week: int
    team: str
    opp: str
    site: str          # home | away | neutral
    spread: float
    result: str | None  # W | L | T | None


@dataclass
class GridRow:
    team: str
    win_pct: float | None
    pick_pct: float | None
    cells: list[Cell]


def parse_cell(text: str, week: int, team: str) -> Cell | None:
    text = text.strip().replace("\xa0", "")
    if not text or text.upper() == "BYE":
        return None
    m = CELL_RE.match(text)
    if not m:
        raise ValueError(f"Unrecognized SurvivorGrid cell {text!r} (team {team}, week {week})")
    line = m.group("line")
    spread = 0.0 if (line is None or line == "PK") else float(line)
    site = "neutral" if m.group("neutral") else ("away" if m.group("away") else "home")
    return Cell(week, team, to_abbr(m.group("opp")), site, spread, m.group("result"))


def _pct(text: str) -> float | None:
    text = text.strip().rstrip("%")
    try:
        return float(text) / 100.0
    except ValueError:
        return None


def parse_html(html: str) -> list[GridRow]:
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table")
    if table is None:
        raise ValueError("SurvivorGrid page has no table")
    rows = table.find_all("tr")
    headers = [c.get_text(strip=True) for c in rows[0].find_all(["th", "td"])]
    week_cols = {int(h): i for i, h in enumerate(headers) if h.isdigit()}
    team_col = headers.index("Team")
    w_col = headers.index("W%")
    p_col = headers.index("P%")

    out: list[GridRow] = []
    for tr in rows[1:]:
        cells = [c.get_text(strip=True) for c in tr.find_all(["td", "th"])]
        if len(cells) <= team_col:
            continue
        team = to_abbr(re.sub(r"\(.\)", "", cells[team_col]))
        parsed = []
        for week, idx in week_cols.items():
            if idx < len(cells):
                c = parse_cell(cells[idx], week, team)
                if c:
                    parsed.append(c)
        out.append(GridRow(team, _pct(cells[w_col]), _pct(cells[p_col]), parsed))
    if len(out) != 32:
        raise ValueError(f"Expected 32 team rows, parsed {len(out)}")
    return out


def grid_current_week(rows: list[GridRow]) -> int:
    """The week SurvivorGrid's W%/P% columns refer to: the first week with an unplayed game."""
    for week in range(1, 19):
        cells = [c for r in rows for c in r.cells if c.week == week]
        if any(c.result is None for c in cells):
            return week
    return 18


def fetch_html(url: str = URL, timeout: int = 20) -> str:
    resp = requests.get(url, headers={"User-Agent": UA}, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def to_games(rows: list[GridRow]) -> list[dict]:
    """Flatten rows into one record per team-week."""
    current = grid_current_week(rows)
    games = []
    for r in rows:
        for c in r.cells:
            rec = asdict(c)
            rec["p"] = spread_to_prob(c.spread)
            rec["src"] = "spread"
            rec["pick"] = None
            if c.week == current and c.result is None:
                if r.win_pct is not None:
                    rec["p"] = r.win_pct
                    rec["src"] = "sg_ml"
                rec["pick"] = r.pick_pct
            games.append(rec)
    return games
