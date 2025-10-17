"""Streamlit app for NFL Survivor Pool Optimizer."""
import streamlit as st
import pandas as pd
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from data_collection.data_manager import DataManager
from optimizer.hungarian_optimizer import SurvivorOptimizer
from optimizer.pool_calculator import PoolCalculator


# Page configuration
st.set_page_config(
    page_title="NFL Survivor Pool Optimizer",
    layout="wide",
    initial_sidebar_state="expanded"
)


# Custom CSS for professional styling with NFL-inspired theme
st.markdown("""
<style>
    /* Hide Streamlit branding and style top toolbar */
    header[data-testid="stHeader"] {
        background: linear-gradient(135deg, #0a1628 0%, #1a2f4a 100%);
    }

    /* Make Deploy button text white */
    header[data-testid="stHeader"] button {
        color: white !important;
    }

    /* Hide hamburger menu and other toolbar items */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* Main background with subtle gradient */
    .main {
        background: linear-gradient(135deg, #0a1628 0%, #1a2f4a 100%);
    }

    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1e3a5f 0%, #0f2744 100%);
    }

    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3,
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] p {
        color: #e8f4f8 !important;
    }

    /* Main headers */
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        background: linear-gradient(90deg, #00d4ff 0%, #0099ff 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #a0c4d9;
        margin-bottom: 2rem;
    }

    /* Content area text */
    .main h1, .main h2, .main h3, .main h4, .main h5, .main h6 {
        color: #e8f4f8 !important;
    }

    .main p, .main li, .main label {
        color: #c7dae8 !important;
    }

    /* Metrics styling */
    [data-testid="stMetricValue"] {
        color: #00d4ff !important;
        font-weight: 600;
    }

    [data-testid="stMetricLabel"] {
        color: #a0c4d9 !important;
    }

    /* Expander styling with border and larger font - using aggressive selectors */
    div[data-testid="stExpander"] details {
        background: linear-gradient(90deg, #1e3a5f 0%, #2a4a6f 100%) !important;
        border-radius: 8px !important;
        border: 2px solid rgba(16, 185, 129, 0.6) !important;
        box-shadow: 0 2px 8px rgba(16, 185, 129, 0.3) !important;
        margin-bottom: 1rem !important;
    }

    div[data-testid="stExpander"] details summary {
        color: #00d4ff !important;
        font-weight: 700 !important;
        font-size: 1.3rem !important;
        padding: 0.75rem 1rem !important;
    }

    div[data-testid="stExpander"] details summary p {
        color: #00d4ff !important;
        font-weight: 700 !important;
        font-size: 1.3rem !important;
        margin: 0 !important;
    }

    div[data-testid="stExpander"] details:hover {
        background: linear-gradient(90deg, #2a4a6f 0%, #3a5a7f 100%) !important;
        border-color: rgba(16, 185, 129, 1) !important;
        box-shadow: 0 4px 12px rgba(16, 185, 129, 0.5) !important;
    }

    /* Expander content background */
    div[data-testid="stExpander"] details[open] {
        background-color: rgba(26, 47, 74, 0.6) !important;
        border: 2px solid rgba(0, 212, 255, 0.5) !important;
        border-radius: 8px !important;
    }

    div[data-testid="stExpander"] div[class*="streamlit-expanderContent"] {
        background-color: rgba(26, 47, 74, 0.6) !important;
        border-top: 1px solid rgba(0, 212, 255, 0.3) !important;
    }

    /* Dataframe styling with alternating row colors - using aggressive selectors */
    div[data-testid="stDataFrame"] {
        font-size: 0.9rem !important;
    }

    /* Target the actual table elements for zebra striping */
    div[data-testid="stDataFrame"] table tbody tr:nth-child(odd) td {
        background-color: rgba(30, 58, 95, 0.4) !important;
    }

    div[data-testid="stDataFrame"] table tbody tr:nth-child(even) td {
        background-color: rgba(42, 74, 111, 0.4) !important;
    }

    div[data-testid="stDataFrame"] table tbody tr:hover td {
        background-color: rgba(0, 212, 255, 0.2) !important;
    }

    /* Table cell styling */
    div[data-testid="stDataFrame"] table td,
    div[data-testid="stDataFrame"] table th {
        border-color: rgba(0, 212, 255, 0.2) !important;
        padding: 0.5rem !important;
    }

    /* Table header styling */
    div[data-testid="stDataFrame"] table thead tr th {
        background-color: rgba(30, 58, 95, 0.6) !important;
        color: #00d4ff !important;
        font-weight: 600 !important;
    }

    /* Button styling */
    .stButton > button {
        background: linear-gradient(90deg, #10b981 0%, #059669 100%);
        color: white;
        font-weight: 600;
        border: none;
        border-radius: 8px;
        padding: 0.5rem 1rem;
        transition: all 0.3s ease;
    }

    .stButton > button:hover {
        background: linear-gradient(90deg, #34d399 0%, #10b981 100%);
        box-shadow: 0 4px 12px rgba(16, 185, 129, 0.5);
        transform: translateY(-2px);
    }

    /* Info/Success/Warning boxes */
    .stAlert {
        background-color: rgba(30, 58, 95, 0.8);
        border-radius: 8px;
        border-left: 4px solid #00d4ff;
        color: #e8f4f8;
    }

    /* Tighter spacing for sidebar selectboxes */
    section[data-testid="stSidebar"] .stSelectbox {
        margin-bottom: -0.5rem;
    }
    section[data-testid="stSidebar"] label {
        font-size: 0.85rem;
        margin-bottom: 0.1rem;
    }

    /* Divider styling */
    hr {
        border-color: rgba(0, 212, 255, 0.3);
    }
</style>
""", unsafe_allow_html=True)


def load_data(use_odds_api: bool, current_week: int):
    """Load data from sources."""
    manager = DataManager(use_odds_api=use_odds_api)
    data = manager.get_comprehensive_data(current_week=current_week)
    return data


def spread_to_moneyline(spread: float, win_prob: float) -> int:
    """
    Convert point spread to approximate moneyline.

    Args:
        spread: Point spread (negative = favorite)
        win_prob: Win probability

    Returns:
        Moneyline (American odds format)
    """
    if win_prob >= 0.5:
        # Favorite: ML = -100 * win_prob / (1 - win_prob)
        ml = -100 * win_prob / (1 - win_prob)
    else:
        # Underdog: ML = 100 * (1 - win_prob) / win_prob
        ml = 100 * (1 - win_prob) / win_prob
    return int(ml)


def format_line(row):
    """Format betting line for display - always show as moneyline."""
    ml = row.get('moneyline')
    spread = row.get('spread')
    win_prob = row.get('win_probability', 0.5)

    if ml is not None and not pd.isna(ml):
        # Have actual moneyline from Odds API
        ml = int(ml)
        return f"+{ml}" if ml > 0 else str(ml)
    elif spread is not None and not pd.isna(spread):
        # Convert spread to approximate moneyline
        ml = spread_to_moneyline(float(spread), win_prob)
        return f"+{ml}" if ml > 0 else str(ml)
    else:
        return "N/A"


def main():
    """Main Streamlit app."""
    # Header
    st.markdown('<div class="main-header">NFL Survivor Pool Optimizer</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Strategic pick recommendations using advanced optimization algorithms</div>', unsafe_allow_html=True)

    # Sidebar configuration
    with st.sidebar:
        st.header("Configuration")

        # Pool settings
        st.subheader("Pool Settings")
        pool_size = st.number_input(
            "Pool Size",
            min_value=1,
            max_value=10000,
            value=50,
            step=1,
            help="Total number of entries in your pool"
        )

        current_week = st.number_input(
            "Current Week",
            min_value=1,
            max_value=18,
            value=config.CURRENT_WEEK,
            step=1
        )

        st.divider()

        # Week-by-week team selection
        st.subheader("Previous Picks")
        st.caption("Select the team you picked for each week")

        # Initialize session state for picks
        if 'weekly_picks' not in st.session_state:
            st.session_state.weekly_picks = {}

        used_teams_list = []
        base_teams_options = ['None'] + config.NFL_TEAMS

        # Show weeks 1 through current_week - 1
        for week in range(1, current_week):
            # Get the previously selected team for this week
            prev_selection = st.session_state.weekly_picks.get(week, 'None')

            # Filter out already-selected teams (except the current selection for this week)
            other_selections = [st.session_state.weekly_picks.get(w, 'None')
                               for w in range(1, current_week) if w != week]
            teams_options = ['None'] + [t for t in config.NFL_TEAMS
                                        if t not in other_selections or t == prev_selection]

            selected_team = st.selectbox(
                f"Week {week}",
                options=teams_options,
                index=teams_options.index(prev_selection) if prev_selection in teams_options else 0,
                key=f"week_{week}_select"
            )

            # Update session state
            st.session_state.weekly_picks[week] = selected_team

            # Add to used teams list if not 'None'
            if selected_team != 'None':
                used_teams_list.append(selected_team)

        st.divider()

        # Calculate button
        calculate_button = st.button("Calculate Optimal Picks", type="primary", use_container_width=True)

        st.divider()

        # Data source info at bottom
        use_odds_api = bool(config.ODDS_API_KEY)
        if use_odds_api:
            st.success("✓ Using The Odds API")
        else:
            st.info("Using placeholder data only")
            st.caption("Add ODDS_API_KEY to .env for live odds")

    # Main content area
    if calculate_button:
        if not used_teams_list:
            st.info("No teams selected yet. Select your previous picks in the sidebar to get started.")
            return

        with st.spinner("Analyzing data and calculating optimal paths..."):
            try:
                # Load data
                data = load_data(use_odds_api, current_week)

                if data.empty:
                    st.error("Unable to load data. Please check your configuration.")
                    return

                # Initialize optimizer
                optimizer = SurvivorOptimizer(data, used_teams_list)

                # Get top picks
                top_picks = optimizer.get_top_picks(current_week, n_picks=5)

                if not top_picks:
                    st.warning("No valid picks found. Check your configuration.")
                    return

                # Apply pool size adjustments
                pool_calc = PoolCalculator(pool_size)
                adjusted_picks = pool_calc.adjust_picks_for_pool_size(top_picks)

                # Display strategy
                st.info(f"**Strategy for {pool_size}-entry pool:** {pool_calc.get_strategy_recommendation()}")

                # Display picks
                st.markdown(f"### Top Recommendations for Week {current_week}")

                for i, pick in enumerate(adjusted_picks, 1):
                    # Clean expander label without emoji, CSS will handle sizing
                    expander_label = f"#{i} {pick['recommended_team']} — Win Out: {pick['overall_win_probability']*100:.2f}%"

                    with st.expander(
                        expander_label,
                        expanded=(i == 1)
                    ):
                        # Metrics row
                        col1, col2, col3, col4 = st.columns(4)

                        with col1:
                            st.metric("This Week Win %", f"{pick['win_probability_this_week']*100:.1f}%")

                        with col2:
                            st.metric("Win-Out Probability", f"{pick['overall_win_probability']*100:.2f}%")

                        with col3:
                            st.metric("Pool Adjusted Score", f"{pick.get('composite_score', 0):.3f}")

                        with col4:
                            st.metric("Popularity", f"{pick['pick_percentage_this_week']*100:.1f}%")

                        st.markdown("---")

                        # Path table
                        st.markdown("#### Season Outlook")

                        path_data = []
                        for p in pick['full_path']:
                            opponent = p.get('opponent', 'TBD')
                            if opponent:
                                matchup = f"vs {opponent}"
                            else:
                                matchup = "TBD"

                            line = format_line(p)

                            path_data.append({
                                'Week': p['week'],
                                'Pick': p['team'],
                                'Matchup': matchup,
                                'Win %': f"{p['win_probability']*100:.1f}%",
                                'Moneyline': line
                            })

                        path_df = pd.DataFrame(path_data)
                        st.dataframe(
                            path_df,
                            use_container_width=True,
                            hide_index=True,
                            column_config={
                                "Week": st.column_config.NumberColumn("Week", width="small"),
                                "Pick": st.column_config.TextColumn("Pick", width="medium"),
                                "Matchup": st.column_config.TextColumn("Matchup", width="medium"),
                                "Win %": st.column_config.TextColumn("Win %", width="small"),
                                "Moneyline": st.column_config.TextColumn("Moneyline", width="small")
                            }
                        )

                        if 'estimated_final_pool_size' in pick:
                            st.caption(
                                f"Projected final pool size: {pick['estimated_final_pool_size']} entries"
                            )

            except Exception as e:
                st.error(f"An error occurred: {str(e)}")
                with st.expander("Error details"):
                    st.exception(e)

    else:
        # Initial state - show instructions
        st.markdown("### Getting Started")
        st.markdown("""
        1. **Enter your pool size** in the sidebar
        2. **Select your previous picks** for each completed week
        3. **Click "Calculate Optimal Picks"** to see recommendations

        The optimizer will show you the top 5 picks for the current week along with the complete
        optimal path for the rest of the season. Each recommendation is tailored to your pool size
        and previous picks.
        """)

        # Show current configuration
        st.markdown("### Current Configuration")
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Pool Size", f"{pool_size}")

        with col2:
            st.metric("Current Week", f"{current_week}")

        with col3:
            teams_used = len([t for t in st.session_state.get('weekly_picks', {}).values() if t != 'None'])
            st.metric("Teams Used", f"{teams_used}")


if __name__ == "__main__":
    main()
