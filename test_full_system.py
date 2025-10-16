"""Comprehensive test of the full NFL Survivor Pool Optimizer system."""
import sys
import config
from data_collection.data_manager import DataManager
from optimizer.hungarian_optimizer import SurvivorOptimizer
from optimizer.pool_calculator import PoolCalculator
from utils.cache_manager import CacheManager


def print_header(title: str):
    """Print a formatted header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def test_data_collection():
    """Test data collection components."""
    print_header("Testing Data Collection")

    print("\n1. Testing without Odds API (SurvivorGrid only)...")
    manager = DataManager(use_odds_api=False)
    data = manager.get_comprehensive_data()

    if data.empty:
        print("   ⚠️  Warning: Using placeholder data (SurvivorGrid scraping may need adjustment)")
    else:
        print(f"   ✓ Successfully loaded data")
        print(f"   - Teams: {len(data['team'].unique())}")
        print(f"   - Weeks: {sorted(data['week'].unique())}")
        print(f"   - Total records: {len(data)}")

    if config.ODDS_API_KEY:
        print("\n2. Testing with Odds API...")
        try:
            manager_api = DataManager(use_odds_api=True)
            data_api = manager_api.get_comprehensive_data()
            print(f"   ✓ Odds API integration successful")
            print(f"   - Total records with API: {len(data_api)}")
        except Exception as e:
            print(f"   ✗ Odds API error: {e}")
    else:
        print("\n2. Skipping Odds API test (no API key found)")
        print("   Add ODDS_API_KEY to .env to test API integration")

    return data


def test_optimizer(data):
    """Test the optimizer."""
    print_header("Testing Optimizer")

    # Sample configuration
    used_teams = ['Kansas City Chiefs', 'Buffalo Bills']
    current_week = config.CURRENT_WEEK

    print(f"\nConfiguration:")
    print(f"  - Current week: {current_week}")
    print(f"  - Used teams: {', '.join(used_teams)}")

    print("\nInitializing optimizer...")
    optimizer = SurvivorOptimizer(data, used_teams)

    print(f"  - Available teams: {len(optimizer.available_teams)}")

    print("\nCalculating top 5 picks...")
    top_picks = optimizer.get_top_picks(current_week, n_picks=5)

    if not top_picks:
        print("   ✗ No picks generated")
        return None

    print(f"   ✓ Successfully generated {len(top_picks)} picks")

    print("\nTop 3 picks (without pool adjustment):")
    for i, pick in enumerate(top_picks[:3], 1):
        print(f"\n  #{i} {pick['recommended_team']}")
        print(f"     This week: {pick['win_probability_this_week']*100:.1f}%")
        print(f"     Win out: {pick['overall_win_probability']*100:.2f}%")
        print(f"     Path length: {pick['weeks_covered']} weeks")

    return top_picks


def test_pool_calculator(top_picks):
    """Test pool size adjustments."""
    print_header("Testing Pool Size Adjustments")

    pool_sizes = [10, 50, 200]

    for pool_size in pool_sizes:
        print(f"\n{pool_size}-entry pool:")

        calc = PoolCalculator(pool_size)
        print(f"  Strategy: {calc.get_strategy_recommendation()}")

        adjusted = calc.adjust_picks_for_pool_size(top_picks)

        print(f"\n  Top pick after adjustment: {adjusted[0]['recommended_team']}")
        print(f"    Composite score: {adjusted[0].get('composite_score', 0):.3f}")
        print(f"    Win out: {adjusted[0]['overall_win_probability']*100:.2f}%")

        if 'path_ev' in adjusted[0]:
            print(f"    Path EV: {adjusted[0]['path_ev']:.3f}")


def test_cache():
    """Test caching system."""
    print_header("Testing Cache System")

    cache = CacheManager()

    # Test cache operations
    print("\n1. Testing cache.set()...")
    test_data = {'test': 'data', 'value': 123}
    success = cache.set('test_key', test_data)
    print(f"   {'✓' if success else '✗'} Cache set: {success}")

    print("\n2. Testing cache.get()...")
    retrieved = cache.get('test_key')
    print(f"   {'✓' if retrieved else '✗'} Cache get: {retrieved == test_data}")

    print("\n3. Testing cache.is_cache_valid()...")
    is_valid = cache.is_cache_valid('test_key')
    print(f"   {'✓' if is_valid else '✗'} Cache valid: {is_valid}")

    print("\n4. Cache info:")
    info = cache.get_cache_info()
    print(f"   Items: {info['total_items']}")
    print(f"   Size: {info['total_size_bytes']} bytes")

    # Cleanup
    cache.clear('test_key')
    print("\n5. Cache cleared")


def test_full_workflow():
    """Test complete workflow."""
    print_header("Full Workflow Test")

    print("\nSimulating user workflow:")
    print("  1. User has used: Chiefs, Bills, 49ers")
    print("  2. Pool size: 100 entries")
    print("  3. Current week: 7")

    used_teams = ['Kansas City Chiefs', 'Buffalo Bills', 'San Francisco 49ers']
    pool_size = 100
    current_week = 7

    # Load data
    print("\nStep 1: Loading data...")
    manager = DataManager(use_odds_api=False)
    data = manager.get_comprehensive_data()

    if data.empty:
        print("   ✗ Failed to load data")
        return

    print(f"   ✓ Data loaded ({len(data)} records)")

    # Optimize
    print("\nStep 2: Running optimization...")
    optimizer = SurvivorOptimizer(data, used_teams)
    top_picks = optimizer.get_top_picks(current_week, n_picks=5)

    if not top_picks:
        print("   ✗ Optimization failed")
        return

    print(f"   ✓ Found {len(top_picks)} optimal picks")

    # Adjust for pool size
    print("\nStep 3: Adjusting for pool size...")
    calc = PoolCalculator(pool_size)
    adjusted = calc.adjust_picks_for_pool_size(top_picks)

    print(f"   ✓ Adjusted rankings for {pool_size}-entry pool")

    # Display results
    print("\n" + "=" * 80)
    print("FINAL RECOMMENDATIONS")
    print("=" * 80)

    for i, pick in enumerate(adjusted[:3], 1):
        print(f"\n#{i} Recommendation: {pick['recommended_team']}")
        print(f"   This Week Win Probability: {pick['win_probability_this_week']*100:.1f}%")
        print(f"   Pick Percentage: {pick['pick_percentage_this_week']*100:.1f}%")
        print(f"   Overall Win-Out Probability: {pick['overall_win_probability']*100:.2f}%")

        if 'composite_score' in pick:
            print(f"   Pool-Adjusted Score: {pick['composite_score']:.3f}")

        print(f"\n   Optimal Path:")
        for p in pick['full_path'][:5]:  # Show first 5 weeks
            print(f"      Week {p['week']}: {p['team']:25s} ({p['win_probability']*100:.1f}%)")

        if len(pick['full_path']) > 5:
            print(f"      ... and {len(pick['full_path'])-5} more weeks")

    print("\n" + "=" * 80)
    print("✓ Full workflow test completed successfully!")
    print("=" * 80)


def main():
    """Run all tests."""
    print("\n")
    print("╔" + "═" * 78 + "╗")
    print("║" + " " * 20 + "NFL SURVIVOR POOL OPTIMIZER TEST SUITE" + " " * 20 + "║")
    print("╚" + "═" * 78 + "╝")

    try:
        # Test individual components
        data = test_data_collection()

        if not data.empty:
            top_picks = test_optimizer(data)

            if top_picks:
                test_pool_calculator(top_picks)

        test_cache()

        # Test full workflow
        test_full_workflow()

        print("\n" + "=" * 80)
        print("ALL TESTS COMPLETED")
        print("=" * 80)
        print("\nTo run the app:")
        print("  streamlit run app.py")
        print("\n")

    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
