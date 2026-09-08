import math

import pytest

from pipeline import optimizer


def _g(week, team, opp, p, pick=0.1):
    return {"week": week, "team": team, "opp": opp, "p": p, "pick": pick, "result": None}


def test_prefers_max_product_not_max_first_week():
    games = [_g(1, "A", "B", 0.9), _g(1, "B", "A", 0.1), _g(1, "C", "D", 0.7), _g(1, "D", "C", 0.3),
             _g(2, "A", "C", 0.9), _g(2, "C", "A", 0.1), _g(2, "B", "D", 0.6), _g(2, "D", "B", 0.4)]
    # Greedy would take A in week 1 (0.9) then B (0.6) = 0.54; optimal is C then A = 0.63.
    assert optimizer.best_path(games, set(), [1, 2]) == [(1, "C"), (2, "A")]


def test_force_and_used():
    games = [_g(1, "A", "B", 0.9), _g(1, "B", "A", 0.1), _g(1, "C", "D", 0.7), _g(1, "D", "C", 0.3),
             _g(2, "A", "C", 0.9), _g(2, "C", "A", 0.1), _g(2, "B", "D", 0.6), _g(2, "D", "B", 0.4)]
    assert optimizer.best_path(games, set(), [1, 2], force="A") == [(1, "A"), (2, "B")]
    assert optimizer.best_path(games, {"A", "C"}, [1, 2]) == [(1, "B"), (2, "D")] or \
           optimizer.best_path(games, {"A", "C"}, [1, 2]) == [(1, "D"), (2, "B")]
    assert optimizer.best_path(games, set(), [1, 2], force="Z") is None


def test_leverage_moves_off_chalk():
    games = [_g(1, "A", "B", 0.80, pick=0.70), _g(1, "B", "A", 0.20, pick=0.0),
             _g(1, "C", "D", 0.75, pick=0.05), _g(1, "D", "C", 0.25, pick=0.0)]
    assert optimizer.best_path(games, set(), [1], lam=0.0) == [(1, "A")]
    assert optimizer.best_path(games, set(), [1], lam=1.0) == [(1, "C")]


def test_full_season_on_real_grid(games):
    weeks = list(range(1, 19))
    path = optimizer.best_path(games, set(), weeks)
    assert [w for w, _ in path] == weeks
    assert len({t for _, t in path}) == 18
    assert 0.001 < optimizer.path_win_out(games, path) < 0.2
    forced = optimizer.best_path(games, set(), weeks, force="JAX")
    assert forced[0] == (1, "JAX")
    assert optimizer.path_win_out(games, forced) <= optimizer.path_win_out(games, path)
