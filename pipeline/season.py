"""NFL season calendar.

A "week" in survivor-pool terms runs Tuesday to Monday: Tuesday is when
SurvivorGrid publishes, and Monday night is the last game.  ``WEEK1_TUESDAY``
is the Tuesday before the season's kickoff Thursday.  Add a row each year.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

TOTAL_WEEKS = 18

# Tuesday 06:00 UTC (≈ 2am ET) before kickoff Thursday, by season.
WEEK1_TUESDAY: dict[int, datetime] = {
    2024: datetime(2024, 9, 3, 6, tzinfo=timezone.utc),
    2025: datetime(2025, 9, 2, 6, tzinfo=timezone.utc),
    2026: datetime(2026, 9, 8, 6, tzinfo=timezone.utc),   # kickoff Thu Sep 10, 2026
}


def _first_tuesday_of_september(year: int) -> datetime:
    d = datetime(year, 9, 1, 6, tzinfo=timezone.utc)
    return d + timedelta(days=(1 - d.weekday()) % 7)


def season_for(now: datetime) -> int:
    """The season a date belongs to (Feb–Aug still counts as the coming season)."""
    return now.year if now.month >= 3 else now.year - 1


def week1_start(season: int) -> datetime:
    return WEEK1_TUESDAY.get(season) or _first_tuesday_of_september(season)


def week_starts(season: int) -> list[datetime]:
    start = week1_start(season)
    return [start + timedelta(days=7 * i) for i in range(TOTAL_WEEKS)]


def week_for(when: datetime, season: int | None = None) -> int:
    """Week number (1–18) a moment falls in; clamps to 1 before kickoff and 18 after."""
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    season = season or season_for(when)
    delta = when - week1_start(season)
    if delta.days < 0:
        return 1
    return min(TOTAL_WEEKS, delta.days // 7 + 1)


def current_week(season: int | None = None) -> int:
    return week_for(datetime.now(timezone.utc), season)
