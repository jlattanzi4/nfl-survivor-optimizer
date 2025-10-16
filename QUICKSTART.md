# Quick Start Guide

## Initial Setup

1. **Navigate to the project directory:**
   ```bash
   cd /Users/josephlattanzi/Scripts/nfl_survivor_optimizer
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables:**
   ```bash
   cp .env.example .env
   ```

   Edit `.env` and add:
   - `ODDS_API_KEY` - Get free key from https://the-odds-api.com/ (optional but recommended)
   - `CURRENT_WEEK` - Update to current NFL week

## Running the Application

### Option 1: Streamlit Web Interface (Recommended)

```bash
streamlit run app.py
```

This will open a web browser with an interactive interface where you can:
- Enter your pool size
- Select teams you've already used
- View top 5 recommended picks with full season paths
- See win-out probabilities and pool-adjusted scores

### Option 2: Test the System

```bash
python test_full_system.py
```

This runs a comprehensive test of all components and shows sample output.

### Option 3: Command Line Testing

Test individual components:

```bash
# Test data collection
cd data_collection
python data_manager.py

# Test optimizer
cd ../optimizer
python hungarian_optimizer.py

# Test pool calculator
python pool_calculator.py
```

## Understanding the Output

The app will show you 5 picks with:

1. **Recommended Team** - The team to pick this week
2. **This Week Win Probability** - Chance this team wins this week
3. **Pick Percentage** - What % of pools are picking this team (lower = more contrarian)
4. **Overall Win-Out Probability** - Your chance of surviving the rest of the season
5. **Pool-Adjusted Score** - Score adjusted for your specific pool size
6. **Optimal Path** - Complete week-by-week picks for rest of season

## Data Sources

The app uses:
- **The Odds API** (if configured) - Current betting lines for accurate near-term odds
- **SurvivorGrid.com** (scraped) - Full season projections and pick percentages

Note: SurvivorGrid scraping may need adjustment based on their current HTML structure. If it fails, the app will use generated placeholder data. You can manually adjust the scraper in `data_collection/survivorgrid_scraper.py`.

## Customization

### Update Current Week
Edit `.env` or change in the Streamlit sidebar

### Adjust Pool Size Strategy
Modify thresholds in `optimizer/pool_calculator.py`:
- Small pool: < 10 entries
- Medium pool: 10-50 entries
- Large pool: 50-200 entries
- Very large: 200+ entries

### Add Custom Data Sources
Implement new scrapers in `data_collection/` and integrate via `data_manager.py`

## Troubleshooting

**No data loading:**
- Check internet connection
- Verify SurvivorGrid.com is accessible
- Check if website HTML structure changed (may need scraper update)

**API errors:**
- Verify ODDS_API_KEY in .env
- Check API quota (free tier has limits)
- Try running without API (will use SurvivorGrid only)

**Import errors:**
- Ensure all dependencies installed: `pip install -r requirements.txt`
- Make sure you're in the project directory

## Next Steps

1. Get a free API key from The Odds API for better data
2. Run the test suite to verify everything works
3. Launch the Streamlit app and start optimizing!
4. Update your picks weekly and re-run the optimizer

Enjoy winning your survivor pool!
