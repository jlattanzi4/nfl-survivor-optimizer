"""Client for The Odds API to fetch NFL betting lines."""
import requests
from typing import Dict, List, Optional
import pandas as pd
from datetime import datetime
import config


def moneyline_to_probability(moneyline: int) -> float:
    """
    Convert American odds moneyline to implied win probability.

    Args:
        moneyline: American odds (e.g., -150, +200)

    Returns:
        Implied probability as a decimal (0-1)
    """
    if moneyline < 0:
        # Favorite: probability = |moneyline| / (|moneyline| + 100)
        return abs(moneyline) / (abs(moneyline) + 100)
    else:
        # Underdog: probability = 100 / (moneyline + 100)
        return 100 / (moneyline + 100)


def normalize_team_name(api_team_name: str) -> str:
    """
    Normalize team names from API to standard format.

    Args:
        api_team_name: Team name from API

    Returns:
        Standardized team name
    """
    # The Odds API typically uses full team names
    # Map common variations
    name_map = {
        'Arizona Cardinals': 'Arizona Cardinals',
        'Atlanta Falcons': 'Atlanta Falcons',
        'Baltimore Ravens': 'Baltimore Ravens',
        'Buffalo Bills': 'Buffalo Bills',
        'Carolina Panthers': 'Carolina Panthers',
        'Chicago Bears': 'Chicago Bears',
        'Cincinnati Bengals': 'Cincinnati Bengals',
        'Cleveland Browns': 'Cleveland Browns',
        'Dallas Cowboys': 'Dallas Cowboys',
        'Denver Broncos': 'Denver Broncos',
        'Detroit Lions': 'Detroit Lions',
        'Green Bay Packers': 'Green Bay Packers',
        'Houston Texans': 'Houston Texans',
        'Indianapolis Colts': 'Indianapolis Colts',
        'Jacksonville Jaguars': 'Jacksonville Jaguars',
        'Kansas City Chiefs': 'Kansas City Chiefs',
        'Las Vegas Raiders': 'Las Vegas Raiders',
        'Los Angeles Chargers': 'Los Angeles Chargers',
        'Los Angeles Rams': 'Los Angeles Rams',
        'Miami Dolphins': 'Miami Dolphins',
        'Minnesota Vikings': 'Minnesota Vikings',
        'New England Patriots': 'New England Patriots',
        'New Orleans Saints': 'New Orleans Saints',
        'New York Giants': 'New York Giants',
        'New York Jets': 'New York Jets',
        'Philadelphia Eagles': 'Philadelphia Eagles',
        'Pittsburgh Steelers': 'Pittsburgh Steelers',
        'San Francisco 49ers': 'San Francisco 49ers',
        'Seattle Seahawks': 'Seattle Seahawks',
        'Tampa Bay Buccaneers': 'Tampa Bay Buccaneers',
        'Tennessee Titans': 'Tennessee Titans',
        'Washington Commanders': 'Washington Commanders',
    }

    return name_map.get(api_team_name, api_team_name)


class OddsAPIClient:
    """Client for fetching NFL odds from The Odds API."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the Odds API client.

        Args:
            api_key: The Odds API key (defaults to config)
        """
        self.api_key = api_key or config.ODDS_API_KEY
        self.base_url = config.ODDS_API_BASE_URL

        if not self.api_key:
            raise ValueError("ODDS_API_KEY not found. Set it in .env file.")

    def get_nfl_odds(self, markets: str = 'h2h') -> Dict:
        """
        Fetch NFL odds from The Odds API.

        Args:
            markets: Betting markets to fetch (h2h=moneyline, spreads, totals)

        Returns:
            Raw API response as dict
        """
        url = f"{self.base_url}/sports/americanfootball_nfl/odds"

        params = {
            'apiKey': self.api_key,
            'regions': 'us',
            'markets': markets,
            'oddsFormat': 'american'
        }

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching odds: {e}")
            return []

    def parse_odds_to_dataframe(self, odds_data: List[Dict]) -> pd.DataFrame:
        """
        Parse odds data into a structured DataFrame.

        Args:
            odds_data: Raw odds data from API

        Returns:
            DataFrame with columns: week, team, opponent, moneyline, win_probability
        """
        parsed_games = []

        for game in odds_data:
            home_team = normalize_team_name(game.get('home_team', ''))
            away_team = normalize_team_name(game.get('away_team', ''))
            commence_time = game.get('commence_time', '')

            # Get best odds across bookmakers (average or use a specific book)
            bookmakers = game.get('bookmakers', [])
            if not bookmakers:
                continue

            # Use first available bookmaker (or could average across multiple)
            bookmaker = bookmakers[0]
            markets = bookmaker.get('markets', [])

            for market in markets:
                if market.get('key') != 'h2h':
                    continue

                outcomes = market.get('outcomes', [])

                for outcome in outcomes:
                    team = normalize_team_name(outcome.get('name', ''))
                    moneyline = outcome.get('price', 0)

                    if team == home_team:
                        opponent = away_team
                    else:
                        opponent = home_team

                    win_prob = moneyline_to_probability(moneyline)

                    parsed_games.append({
                        'team': team,
                        'opponent': opponent,
                        'moneyline': moneyline,
                        'win_probability': win_prob,
                        'commence_time': commence_time,
                        'is_home': team == home_team
                    })

        df = pd.DataFrame(parsed_games)
        return df

    def get_win_probabilities(self) -> pd.DataFrame:
        """
        Get win probabilities for all NFL teams with upcoming games.

        Returns:
            DataFrame with team win probabilities
        """
        odds_data = self.get_nfl_odds()

        if not odds_data:
            print("Warning: No odds data retrieved")
            return pd.DataFrame()

        df = self.parse_odds_to_dataframe(odds_data)

        # Calculate week number from game dates
        if not df.empty:
            df['week'] = df['commence_time'].apply(self._estimate_week_from_date)

        return df

    def _estimate_week_from_date(self, commence_time_str: str) -> int:
        """
        Estimate NFL week number from game date.

        Args:
            commence_time_str: ISO format datetime string

        Returns:
            Estimated week number
        """
        from datetime import datetime, timedelta

        try:
            game_date = datetime.fromisoformat(commence_time_str.replace('Z', '+00:00'))

            # NFL 2025 Season start: September 4, 2025 (Thursday Night)
            # This is an approximation - adjust based on actual season start
            season_start = datetime(2025, 9, 4, tzinfo=game_date.tzinfo)

            # Calculate days since season start
            days_diff = (game_date - season_start).days

            # Each week is roughly 7 days, starting from week 1
            estimated_week = max(1, min(18, (days_diff // 7) + 1))

            return estimated_week
        except:
            # Fallback to current week if parsing fails
            return config.CURRENT_WEEK


def test_odds_api():
    """Test function to verify API connectivity."""
    try:
        client = OddsAPIClient()
        df = client.get_win_probabilities()

        if not df.empty:
            print(f"Successfully fetched odds for {len(df)} team matchups")
            print("\nSample data:")
            print(df.head())
            print(f"\nWin probabilities range: {df['win_probability'].min():.3f} - {df['win_probability'].max():.3f}")
            return True
        else:
            print("No data retrieved")
            return False
    except Exception as e:
        print(f"Test failed: {e}")
        return False


if __name__ == "__main__":
    test_odds_api()
