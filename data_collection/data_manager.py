"""Data manager to combine and integrate data from multiple sources."""
import pandas as pd
from typing import List, Optional
import config
from data_collection.odds_api import OddsAPIClient
from data_collection.survivorgrid_scraper import SurvivorGridScraper


class DataManager:
    """Manages data collection and integration from multiple sources."""

    def __init__(self, use_odds_api: bool = True):
        """
        Initialize data manager.

        Args:
            use_odds_api: Whether to use The Odds API (requires API key)
        """
        self.use_odds_api = use_odds_api
        self.odds_client = OddsAPIClient() if use_odds_api else None
        self.sg_scraper = SurvivorGridScraper()

    def get_comprehensive_data(self, current_week: Optional[int] = None) -> pd.DataFrame:
        """
        Get comprehensive data combining all sources.

        Strategy:
        - Use The Odds API for current week and next 1-2 weeks (more accurate)
        - Use SurvivorGrid for all weeks including future weeks

        Args:
            current_week: Current NFL week (defaults to config)

        Returns:
            DataFrame with columns: week, team, win_probability, pick_pct, ev, opponent
        """
        current_week = current_week or config.CURRENT_WEEK

        # Get SurvivorGrid data for all weeks (primary source)
        print("Fetching data from SurvivorGrid...")
        sg_data = self.sg_scraper.get_all_weeks_data(current_week=current_week)

        # Get The Odds API data for current week (more accurate for near-term)
        odds_data = pd.DataFrame()
        if self.use_odds_api and self.odds_client:
            try:
                print("Fetching current week odds from The Odds API...")
                odds_data = self.odds_client.get_win_probabilities()
            except Exception as e:
                print(f"Warning: Could not fetch odds API data: {e}")

        # Merge the data sources
        combined_data = self._merge_data_sources(sg_data, odds_data, current_week)

        return combined_data

    def _merge_data_sources(
        self,
        sg_data: pd.DataFrame,
        odds_data: pd.DataFrame,
        current_week: int
    ) -> pd.DataFrame:
        """
        Merge data from SurvivorGrid and Odds API.

        Args:
            sg_data: Data from SurvivorGrid
            odds_data: Data from The Odds API
            current_week: Current week number

        Returns:
            Merged DataFrame
        """
        if sg_data.empty:
            print("Warning: No SurvivorGrid data available")
            return pd.DataFrame()

        # Start with SurvivorGrid data as base
        result = sg_data.copy()
        result.rename(columns={'win_pct': 'win_probability'}, inplace=True)

        # Override with Odds API data if available
        if not odds_data.empty:
            # Get unique weeks from odds data
            odds_weeks = odds_data['week'].unique()

            # Remove those weeks from SurvivorGrid data
            result = result[~result['week'].isin(odds_weeks)]

            # Prepare odds data - DON'T override the week column!
            odds_to_add = odds_data.copy()

            # For each week in odds data, merge pick_pct and spread from SurvivorGrid
            for week in odds_weeks:
                sg_week = sg_data[sg_data['week'] == week][['team', 'pick_pct', 'ev', 'spread']]
                week_mask = odds_to_add['week'] == week

                # Merge pick percentages and spreads for this week
                for idx in odds_to_add[week_mask].index:
                    team = odds_to_add.at[idx, 'team']
                    sg_team_data = sg_week[sg_week['team'] == team]
                    if not sg_team_data.empty:
                        odds_to_add.at[idx, 'pick_pct'] = sg_team_data.iloc[0]['pick_pct']
                        # Also preserve spread from SurvivorGrid since Odds API doesn't provide it
                        if 'spread' in sg_team_data.columns:
                            odds_to_add.at[idx, 'spread'] = sg_team_data.iloc[0]['spread']

            # Fill missing pick_pct with default
            if 'pick_pct' not in odds_to_add.columns:
                odds_to_add['pick_pct'] = 0.05
            else:
                odds_to_add['pick_pct'] = odds_to_add['pick_pct'].fillna(0.05)

            odds_to_add['ev'] = odds_to_add['win_probability'] * (1 - odds_to_add['pick_pct'])

            # Combine
            result = pd.concat([result, odds_to_add], ignore_index=True)

        # Ensure required columns exist
        required_cols = ['week', 'team', 'win_probability', 'pick_pct', 'ev']
        for col in required_cols:
            if col not in result.columns:
                result[col] = 0.0 if col != 'team' else ''

        # Add opponent and moneyline if missing
        if 'opponent' not in result.columns:
            result['opponent'] = ''
        if 'moneyline' not in result.columns:
            result['moneyline'] = None

        # Sort by week and team
        result = result.sort_values(['week', 'team']).reset_index(drop=True)

        return result

    def get_week_data(self, week: int) -> pd.DataFrame:
        """
        Get data for a specific week.

        Args:
            week: Week number

        Returns:
            DataFrame with data for that week only
        """
        all_data = self.get_comprehensive_data()
        return all_data[all_data['week'] == week].copy()

    def get_team_schedule(self, team: str, start_week: Optional[int] = None) -> pd.DataFrame:
        """
        Get schedule/probabilities for a specific team.

        Args:
            team: Team name
            start_week: Starting week (defaults to current week)

        Returns:
            DataFrame with that team's data for all remaining weeks
        """
        start_week = start_week or config.CURRENT_WEEK
        all_data = self.get_comprehensive_data()

        team_data = all_data[
            (all_data['team'] == team) & (all_data['week'] >= start_week)
        ].copy()

        return team_data.sort_values('week')

    def get_available_teams(self, used_teams: List[str]) -> List[str]:
        """
        Get list of teams that haven't been used yet.

        Args:
            used_teams: List of teams already picked

        Returns:
            List of available team names
        """
        all_teams = set(config.NFL_TEAMS)
        used = set(used_teams)
        available = sorted(all_teams - used)
        return available


def test_data_manager():
    """Test the data manager."""
    # Test without Odds API first (doesn't require API key)
    print("Testing with SurvivorGrid only...")
    manager = DataManager(use_odds_api=False)

    data = manager.get_comprehensive_data()
    print(f"\nTotal rows: {len(data)}")
    print(f"Weeks: {sorted(data['week'].unique())}")
    print(f"Teams: {len(data['team'].unique())}")

    if not data.empty:
        print("\nSample data:")
        print(data.head(10))

        print("\nWeek 7 data:")
        week7 = manager.get_week_data(7)
        print(week7.head())

        print("\nKansas City Chiefs schedule:")
        kc_schedule = manager.get_team_schedule('Kansas City Chiefs')
        print(kc_schedule)

    # Test with Odds API if key is available
    if config.ODDS_API_KEY:
        print("\n\nTesting with The Odds API...")
        manager_with_api = DataManager(use_odds_api=True)
        data_with_api = manager_with_api.get_comprehensive_data()
        print(f"Total rows with API: {len(data_with_api)}")


if __name__ == "__main__":
    test_data_manager()
