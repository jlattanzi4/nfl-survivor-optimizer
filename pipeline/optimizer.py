"""Reference survivor-path optimizer (Python).

The browser runs a JavaScript port of this; ``tests/test_parity.py`` checks
the two agree on the same data.

Objective for a path is the sum over weeks of
``log p  −  λ · log fs``
where ``p`` is the pick's win probability and ``fs`` is the expected fraction
of the field that survives the week *given that pick wins*
(``share_pick + Σ_{other} share·p``).  λ = 0 maximizes pure win-out
probability; λ = 1 maximizes the product of weekly pool "expected value"
(SurvivorGrid's EV), which rewards low-popularity picks.
"""
from __future__ import annotations

import math

import numpy as np
from scipy.optimize import linear_sum_assignment

BIG = 1e6


def field_survival(week_games: list[dict], pick: str) -> float:
    """Expected fraction of the field surviving this week if ``pick`` wins."""
    shares = {g["team"]: (g.get("pick") or 0.0) for g in week_games}
    total = sum(shares.values())
    if total <= 0:
        return 1.0
    shares = {t: s / total for t, s in shares.items()}
    fs = shares.get(pick, 0.0)
    for g in week_games:
        if g["team"] != pick:
            fs += shares[g["team"]] * g["p"]
    return max(fs, 1e-6)


def build_cost(games: list[dict], weeks: list[int], teams: list[str], lam: float) -> np.ndarray:
    by_week = {w: [g for g in games if g["week"] == w] for w in weeks}
    cost = np.full((len(weeks), len(teams)), BIG)
    for i, w in enumerate(weeks):
        for g in by_week[w]:
            if g["team"] in teams:
                j = teams.index(g["team"])
                p = min(max(g["p"], 1e-4), 1 - 1e-4)
                c = -math.log(p)
                if lam > 0:
                    c += lam * math.log(field_survival(by_week[w], g["team"]))
                cost[i, j] = c
    return cost


def best_path(games: list[dict], used: set[str], weeks: list[int], lam: float = 0.0,
              force: str | None = None) -> list[tuple[int, str]] | None:
    teams = sorted({g["team"] for g in games} - set(used))
    if len(weeks) > len(teams):
        return None
    cost = build_cost(games, weeks, teams, lam)
    if force is not None:
        if force not in teams or cost[0, teams.index(force)] >= BIG:
            return None
        j = teams.index(force)
        cost[0, :] = BIG
        cost[0, j] = -1e3   # cheap enough to always be chosen, finite so the solver stays stable
    rows, cols = linear_sum_assignment(cost)
    path = [(weeks[i], teams[j]) for i, j in zip(rows, cols)]
    if any(cost[i, j] >= BIG for i, j in zip(rows, cols)):
        return None
    return sorted(path)


def path_win_out(games: list[dict], path: list[tuple[int, str]]) -> float:
    idx = {(g["week"], g["team"]): g["p"] for g in games}
    return float(np.prod([idx[(w, t)] for w, t in path]))
