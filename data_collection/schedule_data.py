"""NFL Schedule data and projection generator for 2025 season."""
import pandas as pd
import random
from typing import Dict, List
import config

# Simplified 2025 NFL Schedule (This should ideally come from an API or be manually updated)
# Format: {week: [(home_team, away_team), ...]}
# This is a template - you'll want to fill in actual 2025 schedule
NFL_2025_SCHEDULE = {
    7: [
        ('New England Patriots', 'Jacksonville Jaguars'),
        ('Cincinnati Bengals', 'Cleveland Browns'),
        ('Green Bay Packers', 'Houston Texans'),
        ('Philadelphia Eagles', 'New York Giants'),
        ('Miami Dolphins', 'Indianapolis Colts'),
        ('Minnesota Vikings', 'Detroit Lions'),
        ('Las Vegas Raiders', 'Los Angeles Rams'),
        ('Buffalo Bills', 'Tennessee Titans'),
        ('Seattle Seahawks', 'Atlanta Falcons'),
        ('Kansas City Chiefs', 'San Francisco 49ers'),
        ('Pittsburgh Steelers', 'New York Jets'),
        ('Los Angeles Chargers', 'Arizona Cardinals'),
        ('Denver Broncos', 'New Orleans Saints'),
        ('Baltimore Ravens', 'Tampa Bay Buccaneers'),
        ('Washington Commanders', 'Carolina Panthers'),
        ('Dallas Cowboys', 'Chicago Bears'),
    ],
    # Additional weeks can be added as schedule is released
}


def generate_schedule_based_data(start_week: int = 7, end_week: int = 18) -> pd.DataFrame:
    """
    Generate schedule-based data with realistic projections.

    Args:
        start_week: Starting week
        end_week: Ending week

    Returns:
        DataFrame with schedule and win probability projections
    """
    # Team strength ratings (0-100 scale) - adjust based on current season performance
    team_ratings = {
        'Kansas City Chiefs': 92,
        'Buffalo Bills': 90,
        'San Francisco 49ers': 88,
        'Baltimore Ravens': 87,
        'Philadelphia Eagles': 86,
        'Detroit Lions': 85,
        'Dallas Cowboys': 82,
        'Miami Dolphins': 80,
        'Cincinnati Bengals': 79,
        'Los Angeles Rams': 78,
        'Green Bay Packers': 77,
        'Pittsburgh Steelers': 76,
        'Seattle Seahawks': 75,
        'Minnesota Vikings': 74,
        'Los Angeles Chargers': 73,
        'Houston Texans': 72,
        'Cleveland Browns': 70,
        'New Orleans Saints': 68,
        'Tampa Bay Buccaneers': 67,
        'Jacksonville Jaguars': 66,
        'Atlanta Falcons': 65,
        'Indianapolis Colts': 63,
        'Las Vegas Raiders': 60,
        'New York Jets': 58,
        'Tennessee Titans': 57,
        'Denver Broncos': 55,
        'Arizona Cardinals': 53,
        'New England Patriots': 52,
        'Washington Commanders': 50,
        'Chicago Bears': 48,
        'New York Giants': 45,
        'Carolina Panthers': 42,
    }

    data = []

    for week in range(start_week, end_week + 1):
        if week in NFL_2025_SCHEDULE:
            # Use actual schedule
            matchups = NFL_2025_SCHEDULE[week]
        else:
            # Generate random matchups for weeks without schedule data
            matchups = _generate_random_matchups(list(team_ratings.keys()))

        for home_team, away_team in matchups:
            # Calculate win probabilities based on team ratings
            home_rating = team_ratings.get(home_team, 60)
            away_rating = team_ratings.get(away_team, 60)

            # Home field advantage
            home_advantage = 3

            # Calculate probabilities using logistic function
            rating_diff = (home_rating + home_advantage) - away_rating
            home_win_prob = 1 / (1 + 10 ** (-rating_diff / 25))
            away_win_prob = 1 - home_win_prob

            # Add some randomness to make it more realistic (±3%)
            home_win_prob = max(0.05, min(0.95, home_win_prob + random.uniform(-0.03, 0.03)))
            away_win_prob = max(0.05, min(0.95, away_win_prob + random.uniform(-0.03, 0.03)))

            # Estimate moneylines from probabilities
            home_ml = _prob_to_moneyline(home_win_prob)
            away_ml = _prob_to_moneyline(away_win_prob)

            # Estimate pick percentages (favorites get picked more)
            home_pick_pct = 0.03 + (home_win_prob - 0.5) * 0.20
            away_pick_pct = 0.03 + (away_win_prob - 0.5) * 0.20

            # Add home team data
            data.append({
                'week': week,
                'team': home_team,
                'opponent': away_team,
                'win_probability': home_win_prob,
                'moneyline': home_ml,
                'pick_pct': max(0.01, home_pick_pct),
                'ev': home_win_prob * (1 - max(0.01, home_pick_pct)),
                'is_home': True
            })

            # Add away team data
            data.append({
                'week': week,
                'team': away_team,
                'opponent': home_team,
                'win_probability': away_win_prob,
                'moneyline': away_ml,
                'pick_pct': max(0.01, away_pick_pct),
                'ev': away_win_prob * (1 - max(0.01, away_pick_pct)),
                'is_home': False
            })

    return pd.DataFrame(data)


def _prob_to_moneyline(prob: float) -> int:
    """Convert probability to American odds moneyline."""
    if prob >= 0.5:
        # Favorite
        return int(-100 * prob / (1 - prob))
    else:
        # Underdog
        return int(100 * (1 - prob) / prob)


def _generate_random_matchups(teams: List[str]) -> List[tuple]:
    """Generate random matchups when schedule data is not available."""
    shuffled = teams.copy()
    random.shuffle(shuffled)

    matchups = []
    for i in range(0, len(shuffled) - 1, 2):
        matchups.append((shuffled[i], shuffled[i+1]))

    return matchups


if __name__ == "__main__":
    # Test the generator
    df = generate_schedule_based_data(7, 10)
    print(df.head(20))
    print(f"\nGenerated {len(df)} team-week entries")
    print(f"Weeks: {sorted(df['week'].unique())}")
