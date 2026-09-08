"""Reference Monte Carlo pool simulator (Python, numpy).

Model
-----
* Each remaining week, every game is a Bernoulli draw with the favorite's
  probability.  One draw per game, so both sides are consistent.
* The field (pool size − 1 entries) picks teams in proportion to that
  week's pick shares.  Survivors are drawn ``Binomial(alive, Σ share·won)``,
  which captures small-pool variance.
* The field's trajectory does not depend on *my* pick, so it is simulated
  once and every candidate path is scored against the same outcomes
  (common random numbers ⇒ low-variance comparisons).
* Multi-life pools: each entry (mine and the field's) may absorb
  ``lives − 1`` losses; losers move to the next strike bucket.
* Payout: I win 1 if I'm the last entry standing; if the season ends with
  S survivors (me included) I take 1/S; if every remaining entry loses in
  the same week, that week's entrants split the pot.

The browser port in ``docs/js/simulate.js`` follows this exactly.
"""
from __future__ import annotations

import numpy as np


def prepare(games: list[dict], weeks: list[int]) -> dict:
    """Index games into per-week arrays: unique games, team→(game idx, side)."""
    per_week = []
    for w in weeks:
        wg = [g for g in games if g["week"] == w]
        seen = {}
        entries = []
        for g in wg:
            key = tuple(sorted((g["team"], g["opp"])))
            if key not in seen:
                seen[key] = len(entries)
                # probability that key[0] wins
                p0 = g["p"] if g["team"] == key[0] else 1 - g["p"]
                entries.append(p0)
        team_side = {}
        for g in wg:
            key = tuple(sorted((g["team"], g["opp"])))
            team_side[g["team"]] = (seen[key], 0 if g["team"] == key[0] else 1)
        shares = {g["team"]: (g.get("pick") or 0.0) for g in wg}
        tot = sum(shares.values()) or 1.0
        shares = {t: s / tot for t, s in shares.items()}
        per_week.append({"p0": np.array(entries), "team_side": team_side, "shares": shares})
    return {"weeks": weeks, "per_week": per_week}


def simulate_field(prep: dict, pool_size: int, n_sims: int, rng: np.random.Generator,
                   lives: int = 1, field_strikes: int = 0) -> dict:
    """Draw outcomes and the field's survivor counts for every sim/week.

    ``lives`` is the number of losses that eliminate an entry (1 = single
    elimination).  ``field_strikes`` is how many entries already sit on their
    last life when the simulation starts.
    """
    W = len(prep["weeks"])
    won = []
    field = max(0, pool_size - 1)
    on_last = min(field_strikes, field) if lives > 1 else 0
    bucket = np.zeros((lives, n_sims), dtype=np.int64)      # entries by strikes used
    bucket[0] = field - on_last
    if lives > 1:
        bucket[lives - 1] = on_last
    alive = np.zeros((W + 1, n_sims), dtype=np.int64)
    alive[0] = field
    for i, pw in enumerate(prep["per_week"]):
        outcome = rng.random((n_sims, len(pw["p0"]))) < pw["p0"]
        won.append(outcome)
        frac = np.zeros(n_sims)
        for team, (gi, side) in pw["team_side"].items():
            team_won = outcome[:, gi] if side == 0 else ~outcome[:, gi]
            frac += pw["shares"].get(team, 0.0) * team_won
        frac = np.clip(frac, 0, 1)
        nxt = np.zeros_like(bucket)
        for k in range(lives):
            surv = rng.binomial(bucket[k], frac)
            nxt[k] += surv
            if k + 1 < lives:
                nxt[k + 1] += bucket[k] - surv
        bucket = nxt
        alive[i + 1] = bucket.sum(axis=0)
    return {"won": won, "alive": alive, "lives": lives}


def score_path(prep: dict, field: dict, path: list[tuple[int, str]],
               lives: int = 1, my_strikes: int = 0) -> dict:
    W = len(prep["weeks"])
    n = field["alive"].shape[1]
    week_idx = {w: i for i, w in enumerate(prep["weeks"])}
    me_alive = np.ones(n, dtype=bool)
    strikes = np.full(n, min(my_strikes, lives - 1), dtype=np.int64)
    payout = np.zeros(n)
    settled = np.zeros(n, dtype=bool)
    survive_curve = []
    for w, team in path:
        i = week_idx[w]
        pw = prep["per_week"][i]
        gi, side = pw["team_side"][team]
        my_win = field["won"][i][:, gi] if side == 0 else ~field["won"][i][:, gi]
        before = field["alive"][i]
        after = field["alive"][i + 1]
        lost = me_alive & ~my_win
        strikes[lost] += 1
        out_now = lost & (strikes >= lives)
        everyone_out = out_now & ~settled & (after == 0)
        payout[everyone_out] = 1.0 / (before[everyone_out] + 1)
        settled |= out_now
        me_alive &= ~out_now
        last_standing = ~settled & me_alive & (after == 0)
        payout[last_standing] = 1.0
        settled |= last_standing
        survive_curve.append(me_alive.mean())
    end = ~settled & me_alive
    payout[end] = 1.0 / (field["alive"][W][end] + 1)
    return {
        "equity": float(payout.mean()),
        "p_win_outright": float((payout == 1.0).mean()),
        "p_survive": float(me_alive.mean()),
        "p_clean": float((me_alive & (strikes == 0)).mean()),
        "survive_curve": survive_curve,
        "expected_survivors": (field["alive"][1:].mean(axis=1) + 1).tolist(),
    }
