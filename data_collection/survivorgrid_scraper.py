"""Web scraper for SurvivorGrid.com to fetch NFL survivor pool data."""
import requests
from bs4 import BeautifulSoup
import pandas as pd
from typing import Dict, List, Optional
import re
import config


def normalize_team_name_from_survivorgrid(sg_name: str) -> str:
    """
    Normalize team names from SurvivorGrid to standard format.

    Args:
        sg_name: Team name or abbreviation from SurvivorGrid

    Returns:
        Standardized full team name
    """
    # Common abbreviations used on SurvivorGrid
    abbrev_map = {
        'ARI': 'Arizona Cardinals',
        'ATL': 'Atlanta Falcons',
        'BAL': 'Baltimore Ravens',
        'BUF': 'Buffalo Bills',
        'CAR': 'Carolina Panthers',
        'CHI': 'Chicago Bears',
        'CIN': 'Cincinnati Bengals',
        'CLE': 'Cleveland Browns',
        'DAL': 'Dallas Cowboys',
        'DEN': 'Denver Broncos',
        'DET': 'Detroit Lions',
        'GB': 'Green Bay Packers',
        'HOU': 'Houston Texans',
        'IND': 'Indianapolis Colts',
        'JAX': 'Jacksonville Jaguars',
        'JAC': 'Jacksonville Jaguars',
        'KC': 'Kansas City Chiefs',
        'LV': 'Las Vegas Raiders',
        'LAC': 'Los Angeles Chargers',
        'LAR': 'Los Angeles Rams',
        'MIA': 'Miami Dolphins',
        'MIN': 'Minnesota Vikings',
        'NE': 'New England Patriots',
        'NO': 'New Orleans Saints',
        'NYG': 'New York Giants',
        'NYJ': 'New York Jets',
        'PHI': 'Philadelphia Eagles',
        'PIT': 'Pittsburgh Steelers',
        'SF': 'San Francisco 49ers',
        'SEA': 'Seattle Seahawks',
        'TB': 'Tampa Bay Buccaneers',
        'TEN': 'Tennessee Titans',
        'WAS': 'Washington Commanders',
        'WSH': 'Washington Commanders',
    }

    # Check if it's an abbreviation
    sg_name_upper = sg_name.strip().upper()
    if sg_name_upper in abbrev_map:
        return abbrev_map[sg_name_upper]

    # If it's already a full name, return as is
    for full_name in config.NFL_TEAMS:
        if sg_name.lower() in full_name.lower() or full_name.lower() in sg_name.lower():
            return full_name

    return sg_name


def spread_to_win_probability(spread: float) -> float:
    """
    Convert point spread to win probability.

    Args:
        spread: Point spread (negative = favorite, positive = underdog)

    Returns:
        Win probability (0-1)
    """
    # Use logistic regression formula commonly used for NFL
    # P(win) = 1 / (1 + 10^(spread/14))
    # Negative spread = favorite, positive = underdog
    return 1 / (1 + 10 ** (spread / 14))


class SurvivorGridScraper:
    """Scraper for SurvivorGrid.com data."""

    def __init__(self):
        """Initialize the scraper."""
        self.base_url = config.SURVIVORGRID_URL
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def fetch_page(self, url: Optional[str] = None) -> Optional[BeautifulSoup]:
        """
        Fetch and parse a page from SurvivorGrid.

        Args:
            url: URL to fetch (defaults to base_url)

        Returns:
            BeautifulSoup object or None if failed
        """
        url = url or self.base_url

        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return BeautifulSoup(response.text, 'lxml')
        except requests.exceptions.RequestException as e:
            print(f"Error fetching {url}: {e}")
            return None

    def scrape_grid_data(self, current_week: Optional[int] = None) -> pd.DataFrame:
        """
        Scrape the main grid data from SurvivorGrid.

        Args:
            current_week: Current week to start from (defaults to config.CURRENT_WEEK)

        Returns:
            DataFrame with columns: week, team, opponent, win_pct, pick_pct, spread, ev
        """
        current_week = current_week or config.CURRENT_WEEK
        soup = self.fetch_page()

        if not soup:
            print("Failed to fetch SurvivorGrid page")
            return pd.DataFrame()

        all_data = []

        try:
            # Find the main table
            tables = soup.find_all('table')

            if not tables:
                print("No tables found on page")
                return pd.DataFrame()

            main_table = tables[0]  # First (and usually only) table
            rows = main_table.find_all('tr')

            if len(rows) < 2:
                print("Table has insufficient rows")
                return pd.DataFrame()

            # Parse header to find week columns
            header_row = rows[0]
            headers = [th.get_text(strip=True) for th in header_row.find_all(['th', 'td'])]

            # Find week column indices - only include current week and future weeks
            week_columns = {}
            for i, header in enumerate(headers):
                if header.isdigit():
                    week_num = int(header)
                    if week_num >= current_week:
                        week_columns[week_num] = i

            # Find index of key columns
            team_col_idx = headers.index('Team') if 'Team' in headers else 3
            w_pct_idx = headers.index('W%') if 'W%' in headers else 1
            p_pct_idx = headers.index('P%') if 'P%' in headers else 2
            ev_idx = headers.index('EV▼') if 'EV▼' in headers else (headers.index('EV') if 'EV' in headers else 0)

            print(f"Found {len(week_columns)} week columns: {sorted(week_columns.keys())}")

            # Parse data rows
            for row in rows[1:]:
                cells = row.find_all(['td', 'th'])

                if len(cells) < max(team_col_idx + 1, max(week_columns.values()) if week_columns else 0):
                    continue

                # Get team info
                team_abbrev = cells[team_col_idx].get_text(strip=True)
                # Remove (W) or (L) from team names (indicates past game results)
                team_abbrev = team_abbrev.replace('(W)', '').replace('(L)', '').strip()
                team_name = normalize_team_name_from_survivorgrid(team_abbrev)

                # Get overall stats from the row - these apply to current week (week 7)
                try:
                    current_w_pct = float(cells[w_pct_idx].get_text(strip=True).replace('%', '')) / 100
                except:
                    current_w_pct = None

                try:
                    current_p_pct = float(cells[p_pct_idx].get_text(strip=True).replace('%', '')) / 100
                except:
                    current_p_pct = 0.05

                # Parse each week's data
                for week_num, col_idx in week_columns.items():
                    if col_idx >= len(cells):
                        continue

                    cell_text = cells[col_idx].get_text(strip=True)

                    # Skip BYE weeks
                    if not cell_text or cell_text.upper() == 'BYE':
                        continue

                    # Skip past game results that contain (W) or (L)
                    if '(W)' in cell_text or '(L)' in cell_text:
                        continue

                    # Parse matchup format: "NYG-7" or "@HOU+0.5"
                    # @ means away game, opponent is abbreviated, +/- is spread
                    is_away = cell_text.startswith('@')
                    cell_text = cell_text.lstrip('@')

                    # Extract opponent and spread
                    # Pattern: OPPONENT+/-SPREAD
                    match = re.match(r'([A-Z]{2,3})([-+][\d.]+)?', cell_text)

                    if not match:
                        continue

                    opponent_abbrev = match.group(1)
                    spread_str = match.group(2) if match.group(2) else '0'

                    opponent = normalize_team_name_from_survivorgrid(opponent_abbrev)

                    try:
                        spread = float(spread_str)
                    except:
                        spread = 0.0

                    # For the first week in the list (current week), use the W% column
                    # For future weeks, calculate from spread
                    first_week = min(week_columns.keys())
                    if week_num == first_week and current_w_pct is not None:
                        win_prob = current_w_pct
                        pick_pct = current_p_pct
                    else:
                        # Calculate win probability from spread for future weeks
                        win_prob = spread_to_win_probability(spread)
                        pick_pct = 0.05  # Default for future weeks

                    all_data.append({
                        'week': week_num,
                        'team': team_name,
                        'opponent': opponent,
                        'win_probability': win_prob,
                        'spread': spread,
                        'pick_pct': pick_pct,
                        'ev': win_prob * (1 - pick_pct),
                        'is_home': not is_away,
                        'moneyline': None  # We have spread, not moneyline from SurvivorGrid
                    })

        except Exception as e:
            print(f"Error parsing SurvivorGrid data: {e}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame()

        df = pd.DataFrame(all_data)

        if not df.empty:
            print(f"Successfully scraped {len(df)} team-week combinations from SurvivorGrid")

        return df

    def get_all_weeks_data(self, current_week: Optional[int] = None) -> pd.DataFrame:
        """
        Get data for all remaining weeks in the season.

        Args:
            current_week: Current week to start from (defaults to config.CURRENT_WEEK)

        Returns:
            DataFrame with win probabilities for all teams and weeks
        """
        df = self.scrape_grid_data(current_week=current_week)

        if df.empty:
            print("Warning: Failed to scrape SurvivorGrid, no data available")

        return df


def test_scraper():
    """Test function to verify scraper functionality."""
    scraper = SurvivorGridScraper()
    df = scraper.get_all_weeks_data()

    if not df.empty:
        print(f"\n✓ Successfully scraped data for {len(df)} team-week combinations")
        print(f"\nWeeks covered: {sorted(df['week'].unique())}")
        print(f"Teams covered: {len(df['team'].unique())}")
        print("\nSample data:")
        print(df.head(10))

        # Show some specific matchups
        print("\nSample Week 7 matchups:")
        week7 = df[df['week'] == 7].head(5)
        for _, row in week7.iterrows():
            print(f"  {row['team']:25s} vs {row['opponent']:25s} | Spread: {row['spread']:+5.1f} | Win%: {row['win_probability']*100:.1f}%")

        return True
    else:
        print("✗ Failed to scrape data")
        return False


if __name__ == "__main__":
    test_scraper()
