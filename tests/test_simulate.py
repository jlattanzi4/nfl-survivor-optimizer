import numpy as np
import pytest

from pipeline import simulate


def _week(p, my_share):
    return [
        {"week": 1, "team": "ME", "opp": "OPP", "p": p, "pick": my_share, "result": None},
        {"week": 1, "team": "OPP", "opp": "ME", "p": 1 - p, "pick": 1 - my_share, "result": None},
    ]


def test_field_all_on_my_team_splits_evenly():
    prep = simulate.prepare(_week(0.7, my_share=1.0), [1])
    field = simulate.simulate_field(prep, pool_size=25, n_sims=5000, rng=np.random.default_rng(1))
    res = simulate.score_path(prep, field, [(1, "ME")])
    assert res["equity"] == pytest.approx(1 / 25)


def test_field_all_on_opponent_pays_win_probability():
    prep = simulate.prepare(_week(0.7, my_share=0.0), [1])
    field = simulate.simulate_field(prep, pool_size=25, n_sims=40000, rng=np.random.default_rng(2))
    res = simulate.score_path(prep, field, [(1, "ME")])
    assert res["equity"] == pytest.approx(0.7, abs=0.01)
    assert res["p_win_outright"] == pytest.approx(0.7, abs=0.01)


def test_common_random_numbers_rank_candidates(games):
    weeks = list(range(1, 19))
    prep = simulate.prepare(games, weeks)
    field = simulate.simulate_field(prep, pool_size=100, n_sims=4000, rng=np.random.default_rng(3))
    from pipeline import optimizer
    a = optimizer.best_path(games, set(), weeks, force="LAC")
    b = optimizer.best_path(games, set(), weeks, force="JAX")
    ra, rb = simulate.score_path(prep, field, a), simulate.score_path(prep, field, b)
    for r in (ra, rb):
        assert 0 <= r["equity"] <= 1
        assert len(r["survive_curve"]) == 18
        assert r["survive_curve"][-1] == pytest.approx(r["p_survive"])
        assert all(x >= y for x, y in zip(r["survive_curve"], r["survive_curve"][1:]))


def _two_weeks(p, my_share):
    g = []
    for w in (1, 2):
        g += [{"week": w, "team": "ME", "opp": "OPP", "p": p, "pick": my_share, "result": None},
              {"week": w, "team": "OPP", "opp": "ME", "p": 1 - p, "pick": 1 - my_share, "result": None}]
    return g


def test_two_lives_cannot_be_eliminated_in_one_week():
    prep = simulate.prepare(_week(0.6, my_share=0.0), [1])
    field = simulate.simulate_field(prep, 40, 4000, np.random.default_rng(4), lives=2)
    res = simulate.score_path(prep, field, [(1, "ME")], lives=2)
    assert res["p_survive"] == 1.0
    assert res["equity"] == pytest.approx(1 / 40)       # nobody can be eliminated: even split


def test_two_lives_field_all_on_opponent():
    # Field always fades me. Each week: I win -> field loses a life; I lose -> I lose a life.
    prep = simulate.prepare(_two_weeks(0.7, my_share=0.0), [1, 2])
    field = simulate.simulate_field(prep, 25, 40000, np.random.default_rng(5), lives=2)
    res = simulate.score_path(prep, field, [(1, "ME"), (2, "ME")], lives=2)
    # win-win: field out after week 2 -> 1; win-lose or lose-win: everyone has one strike -> 1/25; lose-lose: 0
    expected = 0.7 * 0.7 * 1 + 2 * 0.7 * 0.3 * (1 / 25)
    assert res["equity"] == pytest.approx(expected, abs=0.01)
    assert res["p_survive"] == pytest.approx(1 - 0.3 * 0.3, abs=0.01)
    assert res["p_clean"] == pytest.approx(0.49, abs=0.01)


def test_my_strike_already_used_equals_single_elim():
    prep = simulate.prepare(_two_weeks(0.7, my_share=0.0), [1, 2])
    rng = np.random.default_rng(6)
    field = simulate.simulate_field(prep, 25, 20000, rng, lives=2)
    one_left = simulate.score_path(prep, field, [(1, "ME"), (2, "ME")], lives=2, my_strikes=1)
    assert one_left["p_survive"] == pytest.approx(0.49, abs=0.01)
    assert one_left["p_clean"] == 0.0


def test_field_strikes_thin_the_field(games):
    weeks = list(range(1, 19))
    prep = simulate.prepare(games, weeks)
    fresh = simulate.simulate_field(prep, 81, 3000, np.random.default_rng(7), lives=2, field_strikes=0)
    worn = simulate.simulate_field(prep, 81, 3000, np.random.default_rng(7), lives=2, field_strikes=60)
    assert worn["alive"][-1].mean() < fresh["alive"][-1].mean()


def test_single_life_default_unchanged(games):
    weeks = list(range(1, 19))
    prep = simulate.prepare(games, weeks)
    a = simulate.simulate_field(prep, 50, 2000, np.random.default_rng(8))
    b = simulate.simulate_field(prep, 50, 2000, np.random.default_rng(8), lives=1)
    assert (a["alive"] == b["alive"]).all()
