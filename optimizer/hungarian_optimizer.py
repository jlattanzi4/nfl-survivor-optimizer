"""Hungarian algorithm optimizer for NFL Survivor Pool."""
import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
from typing import List, Dict, Tuple, Optional
import config


class SurvivorOptimizer:
    """Optimizer using Hungarian algorithm to find optimal survivor pool paths."""

    def __init__(self, data: pd.DataFrame, used_teams: List[str]):
        """
        Initialize the optimizer.

        Args:
            data: DataFrame with columns [week, team, win_probability, pick_pct, ev]
            used_teams: List of teams already used
        """
        self.data = data
        self.used_teams = set(used_teams)
        self.available_teams = self._get_available_teams()

    def _get_available_teams(self) -> List[str]:
        """Get list of teams that haven't been used yet."""
        all_teams = set(self.data['team'].unique())
        available = sorted(all_teams - self.used_teams)
        return available

    def create_cost_matrix(self, weeks: List[int]) -> Tuple[np.ndarray, List[str], List[int]]:
        """
        Create cost matrix for Hungarian algorithm.

        The Hungarian algorithm minimizes cost, so we use (1 - win_probability)
        as the cost. This way, maximizing win probability = minimizing cost.

        Args:
            weeks: List of week numbers to optimize over

        Returns:
            Tuple of (cost_matrix, team_names, week_numbers)
        """
        teams = self.available_teams
        n_teams = len(teams)
        n_weeks = len(weeks)

        # If more teams than weeks, we only need to use some teams
        # If more weeks than teams, we can't fill all weeks (error case)
        if n_weeks > n_teams:
            raise ValueError(f"Not enough available teams ({n_teams}) for remaining weeks ({n_weeks})")

        # Create cost matrix: rows = teams, cols = weeks
        cost_matrix = np.ones((n_teams, n_weeks)) * 999  # High cost for missing data

        for i, team in enumerate(teams):
            team_data = self.data[self.data['team'] == team]

            for j, week in enumerate(weeks):
                week_data = team_data[team_data['week'] == week]

                if not week_data.empty:
                    win_prob = week_data.iloc[0]['win_probability']
                    # To maximize PRODUCT of probabilities (win-out probability),
                    # we minimize the SUM of -log(probabilities)
                    # Cost = -log(win_prob)
                    cost_matrix[i, j] = -np.log(max(win_prob, 0.001))  # Avoid log(0)
                else:
                    # If no data for this team-week combination, high cost
                    cost_matrix[i, j] = 999

        return cost_matrix, teams, weeks

    def optimize_path(
        self,
        current_week: int,
        end_week: Optional[int] = None,
        force_team: Optional[str] = None
    ) -> Dict:
        """
        Find optimal path using Hungarian algorithm.

        Args:
            current_week: Current week number
            end_week: End week (defaults to end of season)
            force_team: Force selection of specific team for current week

        Returns:
            Dictionary with path details including team assignments and probability
        """
        end_week = end_week or config.TOTAL_WEEKS
        weeks = list(range(current_week, end_week + 1))

        # Create cost matrix
        cost_matrix, teams, week_list = self.create_cost_matrix(weeks)

        # If forcing a specific team for current week
        if force_team:
            if force_team not in teams:
                return {
                    'error': f'{force_team} not available (already used or not found)',
                    'path': [],
                    'probability': 0.0
                }

            # Modify cost matrix to force this team for first week
            team_idx = teams.index(force_team)
            # Make this assignment very cheap
            original_cost = cost_matrix[team_idx, 0]
            cost_matrix[team_idx, 0] = -1000

            # Make all other teams very expensive for first week
            for i in range(len(teams)):
                if i != team_idx:
                    cost_matrix[i, 0] = 1000

        # Run Hungarian algorithm
        row_ind, col_ind = linear_sum_assignment(cost_matrix)

        # Extract the path
        path = []
        total_cost = 0
        total_log_prob = 0

        for team_idx, week_idx in zip(row_ind, col_ind):
            if week_idx >= len(week_list):
                continue

            team = teams[team_idx]
            week = week_list[week_idx]
            cost = cost_matrix[team_idx, week_idx]

            # Skip if cost is too high (invalid assignment)
            if cost > 100:
                continue

            # Get actual win probability
            win_prob = 1 - cost if cost < 1 else 0.01

            # Get pick percentage for EV calculation
            team_week_data = self.data[
                (self.data['team'] == team) & (self.data['week'] == week)
            ]

            pick_pct = 0.05  # Default
            opponent = ''
            moneyline = None
            spread = None
            if not team_week_data.empty:
                win_prob = team_week_data.iloc[0]['win_probability']
                pick_pct = team_week_data.iloc[0].get('pick_pct', 0.05)
                opponent = team_week_data.iloc[0].get('opponent', '')
                moneyline = team_week_data.iloc[0].get('moneyline', None)
                spread = team_week_data.iloc[0].get('spread', None)

            path.append({
                'week': week,
                'team': team,
                'opponent': opponent,
                'win_probability': win_prob,
                'pick_pct': pick_pct,
                'moneyline': moneyline,
                'spread': spread
            })

            total_cost += cost
            total_log_prob += np.log(max(win_prob, 0.001))  # Avoid log(0)

        # Calculate overall probability of winning out
        overall_prob = np.exp(total_log_prob) if path else 0.0

        return {
            'path': sorted(path, key=lambda x: x['week']),
            'probability': overall_prob,
            'total_cost': total_cost,
            'weeks_covered': len(path)
        }

    def get_top_picks(
        self,
        current_week: int,
        n_picks: int = 5,
        end_week: Optional[int] = None
    ) -> List[Dict]:
        """
        Get top N picks for current week with their optimal paths.

        For each available team, we force it as the current week pick,
        then optimize the rest of the season.

        Args:
            current_week: Current week number
            n_picks: Number of top picks to return
            end_week: End week for optimization

        Returns:
            List of dictionaries, each containing a pick and its optimal path
        """
        results = []

        # CRITICAL: Only consider teams that actually play in current_week
        # Filter out teams on BYE or not playing this week
        teams_this_week = set(self.data[self.data['week'] == current_week]['team'].unique())
        available_this_week = [t for t in self.available_teams if t in teams_this_week]

        print(f"Evaluating {len(available_this_week)} teams playing in week {current_week}...")

        for team in available_this_week:
            result = self.optimize_path(current_week, end_week, force_team=team)

            if 'error' not in result and result['path']:
                # First pick in path should be the forced team
                current_pick = result['path'][0]

                results.append({
                    'current_week': current_week,
                    'recommended_team': team,
                    'win_probability_this_week': current_pick['win_probability'],
                    'pick_percentage_this_week': current_pick['pick_pct'],
                    'full_path': result['path'],
                    'overall_win_probability': result['probability'],
                    'weeks_covered': result['weeks_covered']
                })

        # Sort by overall win probability (best paths first)
        results.sort(key=lambda x: x['overall_win_probability'], reverse=True)

        return results[:n_picks]

    def format_path_display(self, path: List[Dict]) -> str:
        """
        Format a path for display.

        Args:
            path: List of picks by week

        Returns:
            Formatted string
        """
        lines = []
        for pick in path:
            week = pick['week']
            team = pick['team']
            prob = pick['win_probability'] * 100
            lines.append(f"  Week {week:2d}: {team:25s} ({prob:.1f}%)")

        return '\n'.join(lines)


def test_optimizer():
    """Test the optimizer with sample data."""
    from data_collection.data_manager import DataManager

    # Get data
    print("Fetching data...")
    manager = DataManager(use_odds_api=False)
    data = manager.get_comprehensive_data()

    if data.empty:
        print("No data available for testing")
        return

    # Test with some used teams
    used_teams = ['Kansas City Chiefs', 'Buffalo Bills', 'San Francisco 49ers']
    current_week = config.CURRENT_WEEK

    print(f"\nOptimizing for week {current_week}")
    print(f"Already used: {', '.join(used_teams)}")

    optimizer = SurvivorOptimizer(data, used_teams)

    print(f"\nAvailable teams: {len(optimizer.available_teams)}")

    # Get top 5 picks
    print("\nCalculating top 5 picks...")
    top_picks = optimizer.get_top_picks(current_week, n_picks=5)

    print("\n" + "=" * 80)
    print("TOP 5 PICKS FOR WEEK", current_week)
    print("=" * 80)

    for i, pick in enumerate(top_picks, 1):
        print(f"\n#{i} PICK: {pick['recommended_team']}")
        print(f"   This week win probability: {pick['win_probability_this_week']*100:.1f}%")
        print(f"   Overall win-out probability: {pick['overall_win_probability']*100:.2f}%")
        print(f"   Pick percentage: {pick['pick_percentage_this_week']*100:.1f}%")
        print(f"\n   Optimal Path:")
        print(optimizer.format_path_display(pick['full_path']))
        print()


if __name__ == "__main__":
    test_optimizer()
