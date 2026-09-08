"""Model public pick share for weeks where no public data exists yet.

SurvivorGrid only publishes P% for the current week.  For future weeks we
assume the public spreads its picks across the teams playing that week in
proportion to ``exp(k · p)``: a softmax over win probability.  ``k`` is fit
each build to the current week's observed distribution, so the model tracks
how chalk-heavy the public actually is this season.
"""
from __future__ import annotations

import math

DEFAULT_K = 12.0


def softmax_shares(probs: dict[str, float], k: float) -> dict[str, float]:
    if not probs:
        return {}
    m = max(probs.values())
    raw = {t: math.exp(k * (p - m)) for t, p in probs.items()}
    z = sum(raw.values())
    return {t: v / z for t, v in raw.items()}


def fit_k(probs: dict[str, float], observed: dict[str, float]) -> float:
    """Grid-search the temperature that best matches observed shares (sum of squared error)."""
    teams = [t for t in probs if t in observed]
    if len(teams) < 8:
        return DEFAULT_K
    total = sum(observed[t] for t in teams) or 1.0
    obs = {t: observed[t] / total for t in teams}
    sub = {t: probs[t] for t in teams}
    best_k, best_err = DEFAULT_K, float("inf")
    k = 2.0
    while k <= 40.0:
        pred = softmax_shares(sub, k)
        err = sum((pred[t] - obs[t]) ** 2 for t in teams)
        if err < best_err:
            best_k, best_err = k, err
        k += 0.5
    return best_k
