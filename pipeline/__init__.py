"""Data pipeline for the NFL Survivor Optimizer.

Fetches SurvivorGrid (season-long spreads + public pick shares) and The Odds
API (current-week consensus moneylines), merges them into a single
``docs/data/season.json`` that the static site consumes.
"""
