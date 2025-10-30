"""Configuration settings for NFL Survivor Pool Optimizer."""
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# API Configuration
ODDS_API_KEY = os.getenv('ODDS_API_KEY', '')
ODDS_API_BASE_URL = 'https://api.the-odds-api.com/v4'

# NFL Configuration
NFL_TEAMS = [
    'Arizona Cardinals', 'Atlanta Falcons', 'Baltimore Ravens', 'Buffalo Bills',
    'Carolina Panthers', 'Chicago Bears', 'Cincinnati Bengals', 'Cleveland Browns',
    'Dallas Cowboys', 'Denver Broncos', 'Detroit Lions', 'Green Bay Packers',
    'Houston Texans', 'Indianapolis Colts', 'Jacksonville Jaguars', 'Kansas City Chiefs',
    'Las Vegas Raiders', 'Los Angeles Chargers', 'Los Angeles Rams', 'Miami Dolphins',
    'Minnesota Vikings', 'New England Patriots', 'New Orleans Saints', 'New York Giants',
    'New York Jets', 'Philadelphia Eagles', 'Pittsburgh Steelers', 'San Francisco 49ers',
    'Seattle Seahawks', 'Tampa Bay Buccaneers', 'Tennessee Titans', 'Washington Commanders'
]

# Team abbreviation mappings (for different data sources)
TEAM_ABBREV_MAP = {
    'ARI': 'Arizona Cardinals', 'ATL': 'Atlanta Falcons', 'BAL': 'Baltimore Ravens',
    'BUF': 'Buffalo Bills', 'CAR': 'Carolina Panthers', 'CHI': 'Chicago Bears',
    'CIN': 'Cincinnati Bengals', 'CLE': 'Cleveland Browns', 'DAL': 'Dallas Cowboys',
    'DEN': 'Denver Broncos', 'DET': 'Detroit Lions', 'GB': 'Green Bay Packers',
    'HOU': 'Houston Texans', 'IND': 'Indianapolis Colts', 'JAX': 'Jacksonville Jaguars',
    'KC': 'Kansas City Chiefs', 'LV': 'Las Vegas Raiders', 'LAC': 'Los Angeles Chargers',
    'LAR': 'Los Angeles Rams', 'MIA': 'Miami Dolphins', 'MIN': 'Minnesota Vikings',
    'NE': 'New England Patriots', 'NO': 'New Orleans Saints', 'NYG': 'New York Giants',
    'NYJ': 'New York Jets', 'PHI': 'Philadelphia Eagles', 'PIT': 'Pittsburgh Steelers',
    'SF': 'San Francisco 49ers', 'SEA': 'Seattle Seahawks', 'TB': 'Tampa Bay Buccaneers',
    'TEN': 'Tennessee Titans', 'WAS': 'Washington Commanders'
}


def get_current_nfl_week(season_year=None):
    """
    Calculate the current NFL week based on the current date.

    The NFL season typically starts on the Thursday following Labor Day (first Monday in September).
    For the 2025 season, Week 1 starts on September 4, 2025.

    Args:
        season_year: The season year (e.g., 2025). If None, auto-detects from current date.

    Returns:
        int: Current NFL week (1-18), or 1 if before season starts
    """
    now = datetime.now()

    if season_year is None:
        season_year = now.year

    # NFL Week 1 start dates by year (Thursday of Week 1)
    # These can be updated each year
    season_start_dates = {
        2024: datetime(2024, 9, 5),   # Week 1 started Sept 5, 2024
        2025: datetime(2025, 9, 4),   # Week 1 starts Sept 4, 2025
        2026: datetime(2026, 9, 10),  # Estimated Week 1 start
    }

    # Get the season start date, or calculate it if not in the dict
    if season_year in season_start_dates:
        season_start = season_start_dates[season_year]
    else:
        # Fallback: estimate as first Thursday in September
        september_first = datetime(season_year, 9, 1)
        days_until_thursday = (3 - september_first.weekday()) % 7
        if days_until_thursday == 0 and september_first.weekday() != 3:
            days_until_thursday = 7
        season_start = september_first + timedelta(days=days_until_thursday)

    # If we're before the season starts, return week 1
    if now < season_start:
        return 1

    # Calculate weeks since season start
    days_since_start = (now - season_start).days
    current_week = (days_since_start // 7) + 1

    # Cap at week 18 (end of regular season)
    return min(current_week, 18)


# Season Configuration
CURRENT_SEASON = int(os.getenv('CURRENT_SEASON', datetime.now().year))
CURRENT_WEEK = int(os.getenv('CURRENT_WEEK', get_current_nfl_week(CURRENT_SEASON)))
TOTAL_WEEKS = 18  # Regular season weeks

# Data Sources
SURVIVORGRID_URL = 'https://www.survivorgrid.com/'

# Cache settings
CACHE_DIR = 'cache'
CACHE_EXPIRY_HOURS = 6
