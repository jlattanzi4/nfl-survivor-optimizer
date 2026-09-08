import pytest

from pipeline import popularity


def test_shares_sum_to_one():
    s = popularity.softmax_shares({"A": 0.8, "B": 0.6, "C": 0.5}, 12)
    assert sum(s.values()) == pytest.approx(1.0)
    assert s["A"] > s["B"] > s["C"]


def test_fit_recovers_generating_k():
    probs = {f"T{i}": 0.45 + i * 0.03 for i in range(14)}
    obs = popularity.softmax_shares(probs, 17.0)
    assert popularity.fit_k(probs, obs) == pytest.approx(17.0, abs=0.5)


def test_fit_on_real_week_is_chalk_heavy(games):
    wk1 = [g for g in games if g["week"] == 1]
    assert all(g["pick_src"] == "public" for g in wk1)
    assert all(g["pick_src"] == "model" for g in games if g["week"] == 9)
    assert sum(g["pick"] for g in games if g["week"] == 9) == pytest.approx(1.0)
