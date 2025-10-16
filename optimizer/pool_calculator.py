"""Pool size adjustment calculator for survivor pool strategy."""
import numpy as np
import pandas as pd
from typing import List, Dict, Optional


class PoolCalculator:
    """Calculator for pool size adjustments and expected value."""

    def __init__(self, pool_size: int):
        """
        Initialize pool calculator.

        Args:
            pool_size: Total number of entries in the pool
        """
        self.pool_size = pool_size

    def calculate_expected_value(
        self,
        win_prob: float,
        pick_pct: float,
        remaining_entries: Optional[int] = None
    ) -> float:
        """
        Calculate expected value of a pick considering pool dynamics.

        EV formula considers:
        - Your win probability
        - What % of pool picks each team
        - Value of surviving vs being eliminated

        Args:
            win_prob: Win probability of your pick (0-1)
            pick_pct: % of pool picking this team (0-1)
            remaining_entries: Current entries still alive (defaults to pool_size)

        Returns:
            Expected value (higher is better)
        """
        remaining_entries = remaining_entries or self.pool_size

        # If pick is very popular, value decreases
        # If pick is contrarian and wins, value increases significantly

        # Expected number of survivors if you pick this team and it wins
        survivors_if_win = remaining_entries * (
            pick_pct * win_prob +  # Those who picked winning team
            (1 - pick_pct) * (1 - win_prob)  # Those who picked other teams that might win
        )

        # Your entry value increases when field gets smaller
        entry_value_if_survive = remaining_entries / max(survivors_if_win, 1)

        # EV = P(you survive) * (value if you survive)
        ev = win_prob * entry_value_if_survive

        return ev

    def calculate_path_ev(
        self,
        path: List[Dict],
        initial_pool_size: Optional[int] = None
    ) -> Dict:
        """
        Calculate expected value for an entire path.

        Simulates pool dynamics week by week.

        Args:
            path: List of picks with win_probability and pick_pct
            initial_pool_size: Starting pool size (defaults to self.pool_size)

        Returns:
            Dictionary with EV metrics
        """
        initial_pool_size = initial_pool_size or self.pool_size

        remaining = initial_pool_size
        cumulative_survival_prob = 1.0
        week_evs = []

        for pick in path:
            win_prob = pick['win_probability']
            pick_pct = pick.get('pick_pct', 0.05)

            # Calculate EV for this week
            ev = self.calculate_expected_value(win_prob, pick_pct, remaining)
            week_evs.append(ev)

            # Update survival probability
            cumulative_survival_prob *= win_prob

            # Estimate remaining pool size after this week
            # Assumes average survivor rate based on pick distribution
            avg_survival_rate = self._estimate_survival_rate(win_prob, pick_pct)
            remaining = int(remaining * avg_survival_rate)
            remaining = max(remaining, 1)  # At least 1

        return {
            'path_ev': np.mean(week_evs),  # Average EV across weeks
            'final_survival_prob': cumulative_survival_prob,
            'estimated_final_pool_size': remaining,
            'estimated_win_prob': 1.0 / max(remaining, 1),
            'week_evs': week_evs
        }

    def _estimate_survival_rate(self, your_win_prob: float, pick_pct: float) -> float:
        """
        Estimate what fraction of the pool survives this week.

        Args:
            your_win_prob: Win probability of the team you picked
            pick_pct: What % picked your team

        Returns:
            Estimated survival rate (0-1)
        """
        # Simple model: assume rest of pool has average win probability
        # In reality, you'd want actual pick distribution across all teams

        # If your pick has high win prob, likely many others picked good teams too
        # Rough estimate: survival rate correlates with average quality of picks
        avg_win_prob = 0.5 + (your_win_prob - 0.5) * 0.7  # Regress to mean

        return avg_win_prob

    def adjust_picks_for_pool_size(self, picks: List[Dict]) -> List[Dict]:
        """
        Re-rank picks based on pool size considerations.

        Larger pools benefit from contrarian picks.
        Smaller pools benefit from consensus safe picks.

        Args:
            picks: List of pick dictionaries with paths

        Returns:
            Adjusted and re-ranked list of picks
        """
        adjusted_picks = []

        for pick in picks:
            path = pick['full_path']

            # Calculate path EV with pool dynamics
            path_metrics = self.calculate_path_ev(path)

            # Create adjusted pick with new metrics
            adjusted = pick.copy()
            adjusted['path_ev'] = path_metrics['path_ev']
            adjusted['estimated_win_probability'] = path_metrics['estimated_win_prob']
            adjusted['estimated_final_pool_size'] = path_metrics['estimated_final_pool_size']

            # Calculate composite score
            # For large pools: favor EV (contrarian value)
            # For small pools: favor raw win probability (safety)
            if self.pool_size > 100:
                # Large pool: weight EV heavily
                score = 0.4 * adjusted['overall_win_probability'] + 0.6 * path_metrics['path_ev']
            elif self.pool_size > 20:
                # Medium pool: balanced
                score = 0.6 * adjusted['overall_win_probability'] + 0.4 * path_metrics['path_ev']
            else:
                # Small pool: mostly win probability
                score = 0.8 * adjusted['overall_win_probability'] + 0.2 * path_metrics['path_ev']

            adjusted['composite_score'] = score
            adjusted_picks.append(adjusted)

        # Re-sort by composite score
        adjusted_picks.sort(key=lambda x: x['composite_score'], reverse=True)

        return adjusted_picks

    def get_strategy_recommendation(self) -> str:
        """
        Get strategic recommendation based on pool size.

        Returns:
            Strategy description string
        """
        if self.pool_size < 10:
            return "Small pool: Prioritize highest win probabilities. Play it safe."
        elif self.pool_size < 50:
            return "Medium pool: Balance safety with some contrarian value picks."
        elif self.pool_size < 200:
            return "Large pool: Consider contrarian picks with good value. Look for differentiation."
        else:
            return "Very large pool: Maximize EV with contrarian strategy. Heavy focus on unique paths."


def test_pool_calculator():
    """Test the pool calculator."""
    print("Testing Pool Calculator")
    print("=" * 60)

    # Test with different pool sizes
    pool_sizes = [10, 50, 200]

    for pool_size in pool_sizes:
        calc = PoolCalculator(pool_size)

        print(f"\nPool Size: {pool_size}")
        print(f"Strategy: {calc.get_strategy_recommendation()}")

        # Test EV calculation
        print("\nEV for different scenarios:")

        scenarios = [
            ("Chalk pick", 0.75, 0.40),  # High win prob, high pick %
            ("Value pick", 0.65, 0.10),  # Good win prob, low pick %
            ("Contrarian", 0.55, 0.03),  # Moderate win prob, very low pick %
        ]

        for name, win_prob, pick_pct in scenarios:
            ev = calc.calculate_expected_value(win_prob, pick_pct)
            print(f"  {name:15s}: Win%={win_prob*100:4.0f}%, Pick%={pick_pct*100:4.1f}%, EV={ev:.3f}")

    # Test path EV
    print("\n" + "=" * 60)
    print("Testing path EV calculation")

    sample_path = [
        {'week': 7, 'team': 'Team A', 'win_probability': 0.70, 'pick_pct': 0.25},
        {'week': 8, 'team': 'Team B', 'win_probability': 0.65, 'pick_pct': 0.15},
        {'week': 9, 'team': 'Team C', 'win_probability': 0.60, 'pick_pct': 0.10},
    ]

    calc = PoolCalculator(100)
    metrics = calc.calculate_path_ev(sample_path)

    print(f"Path EV: {metrics['path_ev']:.3f}")
    print(f"Final survival probability: {metrics['final_survival_prob']*100:.2f}%")
    print(f"Estimated final pool size: {metrics['estimated_final_pool_size']}")
    print(f"Estimated win probability: {metrics['estimated_win_prob']*100:.2f}%")


if __name__ == "__main__":
    test_pool_calculator()
