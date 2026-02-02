"""Quick visual test — generates sample charts as PNGs you can open."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from my_budget.bot.visualization import VisualizationService

viz = VisualizationService()
out = ROOT / "chart_previews"
out.mkdir(exist_ok=True)

# --- 1. Donut (pie) chart ---
pie_data = {
    "🛒 Groceries": 320.50,
    "🍽️ Dining Out": 185.00,
    "🚗 Transportation": 95.75,
    "📱 Subscriptions": 42.99,
    "🎬 Entertainment": 67.00,
    "💊 Healthcare": 25.00,
    "🏠 Housing": 1200.00,
    "🔧 Other": 58.30,
}
buf = viz.pie_chart(pie_data, "January Spending by Category")
if buf:
    (out / "donut_chart.png").write_bytes(buf.read())
    print("✓ donut_chart.png")

# --- 2. Bar chart ---
bar_data = [
    ("2026-01-27", 45.00),
    ("2026-01-28", 112.50),
    ("2026-01-29", 23.00),
    ("2026-01-30", 88.75),
    ("2026-01-31", 156.20),
    ("2026-02-01", 34.00),
    ("2026-02-02", 67.50),
]
buf = viz.bar_chart(bar_data, "Daily Spending — Last 7 Days")
if buf:
    (out / "bar_chart.png").write_bytes(buf.read())
    print("✓ bar_chart.png")

# --- 3. Budget chart ---
plan = {
    "planned_budgets": {
        "🛒 Groceries": 400,
        "🍽️ Dining Out": 200,
        "🚗 Transportation": 150,
        "📱 Subscriptions": 50,
        "🎬 Entertainment": 100,
        "💊 Healthcare": 75,
        "🏠 Housing": 1200,
    },
    "actual_spending": {
        "🛒 Groceries": 320.50,
        "🍽️ Dining Out": 185.00,
        "🚗 Transportation": 95.75,
        "📱 Subscriptions": 42.99,
        "🎬 Entertainment": 67.00,
        "💊 Healthcare": 25.00,
        "🏠 Housing": 1200.00,
    },
    "total_actual_income": 3500,
    "total_projected_income": 4000,
    "total_spent": 1936.24,
}
buf = viz.budget_chart(plan)
if buf:
    (out / "budget_chart.png").write_bytes(buf.read())
    print("✓ budget_chart.png")

print(f"\nAll charts saved to {out}/")
