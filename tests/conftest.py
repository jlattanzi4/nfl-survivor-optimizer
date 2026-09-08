import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FIXTURE = ROOT / "tests" / "fixtures" / "survivorgrid_2026_week1.html"


@pytest.fixture(scope="session")
def grid_html() -> str:
    return FIXTURE.read_text()


@pytest.fixture(scope="session")
def grid_rows(grid_html):
    from pipeline import survivorgrid
    return survivorgrid.parse_html(grid_html)


@pytest.fixture(scope="session")
def games(grid_rows):
    from pipeline import survivorgrid
    from pipeline.build import apply_popularity
    g = survivorgrid.to_games(grid_rows)
    apply_popularity(g, survivorgrid.grid_current_week(grid_rows))
    return g
