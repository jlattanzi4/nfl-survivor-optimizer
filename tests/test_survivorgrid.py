import pytest

from pipeline import survivorgrid
from pipeline.survivorgrid import parse_cell, spread_to_prob


def test_parses_every_team_and_game(grid_rows):
    assert len(grid_rows) == 32
    cells = [c for r in grid_rows for c in r.cells]
    assert len(cells) == 32 * 17          # 17 games each; byes excluded


def test_neutral_site_games_are_kept(grid_rows):
    jax = next(r for r in grid_rows if r.team == "JAX")
    wk5 = next(c for c in jax.cells if c.week == 5)
    assert (wk5.opp, wk5.site, wk5.spread) == ("PHI", "neutral", 1.5)
    assert sum(c.site == "neutral" for r in grid_rows for c in r.cells) == 18


def test_pickem_cells_parse(grid_rows):
    det = next(r for r in grid_rows if r.team == "DET")
    wk10 = next(c for c in det.cells if c.week == 10)
    assert (wk10.opp, wk10.spread, wk10.site) == ("NE", 0.0, "neutral")
    lar = next(r for r in grid_rows if r.team == "LAR")
    wk16 = next(c for c in lar.cells if c.week == 16)
    assert (wk16.opp, wk16.spread, wk16.site) == ("SEA", 0.0, "away")


@pytest.mark.parametrize("text,expected", [
    ("NYG-7", ("NYG", "home", -7.0, None)),
    ("@HOU+0.5", ("HOU", "away", 0.5, None)),
    ("(n)PHI+1.5", ("PHI", "neutral", 1.5, None)),
    ("NEPK", ("NE", "home", 0.0, None)),
    ("@SEAPK", ("SEA", "away", 0.0, None)),
    ("NYG-7(W)", ("NYG", "home", -7.0, "W")),
    ("@KC+3(L)", ("KC", "away", 3.0, "L")),
])
def test_cell_grammar(text, expected):
    c = parse_cell(text, 1, "XXX")
    assert (c.opp, c.site, c.spread, c.result) == expected


def test_bye_is_none():
    assert parse_cell("BYE", 7, "LAC") is None
    assert parse_cell("", 7, "LAC") is None


def test_garbage_cell_raises():
    with pytest.raises(ValueError):
        parse_cell("??", 1, "LAC")


def test_matchups_are_symmetric(grid_rows):
    idx = {(c.week, c.team): c for r in grid_rows for c in r.cells}
    for (w, t), c in idx.items():
        back = idx[(w, c.opp)]
        assert back.opp == t
        assert back.spread == pytest.approx(-c.spread)
        if c.site == "neutral":
            assert back.site == "neutral"
        else:
            assert {c.site, back.site} == {"home", "away"}


def test_current_week_and_pick_shares(grid_rows):
    assert survivorgrid.grid_current_week(grid_rows) == 1
    shares = [r.pick_pct for r in grid_rows if r.pick_pct is not None]
    assert 0.95 < sum(shares) < 1.05


def test_spread_to_prob_calibration():
    assert spread_to_prob(0) == 0.5
    assert 0.60 < spread_to_prob(-3) < 0.64
    assert 0.73 < spread_to_prob(-7) < 0.77
    assert 0.82 < spread_to_prob(-10) < 0.86
    assert spread_to_prob(7) == pytest.approx(1 - spread_to_prob(-7))
