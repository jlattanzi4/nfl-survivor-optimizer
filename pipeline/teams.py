"""Canonical NFL team table and name normalization.

Every data source spells teams differently (SurvivorGrid uses ``WSH``/``JAC``,
The Odds API uses full names, ESPN logos use ``wsh``/``lar``).  Everything in
the pipeline is keyed by the canonical ``abbr`` below.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Team:
    abbr: str
    city: str
    nick: str
    primary: str
    secondary: str
    espn: str  # slug used by the ESPN logo CDN

    @property
    def name(self) -> str:
        return f"{self.city} {self.nick}"


TEAMS: list[Team] = [
    Team("ARI", "Arizona", "Cardinals", "#97233F", "#FFB612", "ari"),
    Team("ATL", "Atlanta", "Falcons", "#A71930", "#000000", "atl"),
    Team("BAL", "Baltimore", "Ravens", "#241773", "#9E7C0C", "bal"),
    Team("BUF", "Buffalo", "Bills", "#00338D", "#C60C30", "buf"),
    Team("CAR", "Carolina", "Panthers", "#0085CA", "#101820", "car"),
    Team("CHI", "Chicago", "Bears", "#0B162A", "#C83803", "chi"),
    Team("CIN", "Cincinnati", "Bengals", "#FB4F14", "#000000", "cin"),
    Team("CLE", "Cleveland", "Browns", "#311D00", "#FF3C00", "cle"),
    Team("DAL", "Dallas", "Cowboys", "#041E42", "#869397", "dal"),
    Team("DEN", "Denver", "Broncos", "#FB4F14", "#002244", "den"),
    Team("DET", "Detroit", "Lions", "#0076B6", "#B0B7BC", "det"),
    Team("GB", "Green Bay", "Packers", "#203731", "#FFB612", "gb"),
    Team("HOU", "Houston", "Texans", "#03202F", "#A71930", "hou"),
    Team("IND", "Indianapolis", "Colts", "#002C5F", "#A2AAAD", "ind"),
    Team("JAX", "Jacksonville", "Jaguars", "#006778", "#D7A22A", "jax"),
    Team("KC", "Kansas City", "Chiefs", "#E31837", "#FFB81C", "kc"),
    Team("LV", "Las Vegas", "Raiders", "#000000", "#A5ACAF", "lv"),
    Team("LAC", "Los Angeles", "Chargers", "#0080C6", "#FFC20E", "lac"),
    Team("LAR", "Los Angeles", "Rams", "#003594", "#FFA300", "lar"),
    Team("MIA", "Miami", "Dolphins", "#008E97", "#FC4C02", "mia"),
    Team("MIN", "Minnesota", "Vikings", "#4F2683", "#FFC62F", "min"),
    Team("NE", "New England", "Patriots", "#002244", "#C60C30", "ne"),
    Team("NO", "New Orleans", "Saints", "#D3BC8D", "#101820", "no"),
    Team("NYG", "New York", "Giants", "#0B2265", "#A71930", "nyg"),
    Team("NYJ", "New York", "Jets", "#125740", "#000000", "nyj"),
    Team("PHI", "Philadelphia", "Eagles", "#004C54", "#A5ACAF", "phi"),
    Team("PIT", "Pittsburgh", "Steelers", "#FFB612", "#101820", "pit"),
    Team("SF", "San Francisco", "49ers", "#AA0000", "#B3995D", "sf"),
    Team("SEA", "Seattle", "Seahawks", "#002244", "#69BE28", "sea"),
    Team("TB", "Tampa Bay", "Buccaneers", "#D50A0A", "#34302B", "tb"),
    Team("TEN", "Tennessee", "Titans", "#0C2340", "#4B92DB", "ten"),
    Team("WAS", "Washington", "Commanders", "#5A1414", "#FFB612", "wsh"),
]

BY_ABBR: dict[str, Team] = {t.abbr: t for t in TEAMS}

# Alternate spellings seen in the wild -> canonical abbr.
ALIASES: dict[str, str] = {
    "JAC": "JAX",
    "WSH": "WAS",
    "LA": "LAR",
    "OAK": "LV",
    "SD": "LAC",
    "STL": "LAR",
    "NEP": "NE",   # artifact of "NEPK" pick'em cells on SurvivorGrid
}
for _t in TEAMS:
    ALIASES[_t.name.upper()] = _t.abbr
    ALIASES[_t.nick.upper()] = _t.abbr
    ALIASES[_t.abbr] = _t.abbr


def to_abbr(raw: str) -> str:
    """Resolve any team spelling to the canonical abbreviation.

    Raises ``KeyError`` for unknown teams so bad source data fails loudly
    rather than silently producing an unknown row.
    """
    key = raw.strip().upper()
    if key in ALIASES:
        return ALIASES[key]
    for t in TEAMS:
        if key == t.name.upper() or key.endswith(t.nick.upper()):
            return t.abbr
    raise KeyError(f"Unknown team: {raw!r}")


def as_json() -> list[dict]:
    return [
        {
            "abbr": t.abbr,
            "city": t.city,
            "nick": t.nick,
            "name": t.name,
            "colors": [t.primary, t.secondary],
            "espn": t.espn,
        }
        for t in TEAMS
    ]
