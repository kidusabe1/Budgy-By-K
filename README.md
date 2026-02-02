# 💰 Personal Finance Telegram Bot

A powerful Python-based Telegram bot for tracking personal expenses with SQLite backend, beautiful visualizations, budget planning, and automated reports.

## 🧱 Architecture (OO)
- `BudgetBot` orchestrates Telegram handlers, scheduling, and user interactions.
- `ExpenseManager` is the data layer (SQLite) for expenses, income, budgets, user settings.
- `VisualizationService` renders pie/bar/budget charts via matplotlib.
- `KeyboardFactory` builds inline keyboards for common actions.
- `ExpenseParser` handles free-form text parsing for expenses and income.

## ✨ Features

### Core Features
- ✅ **Natural Language Expense Logging** - Just send "groceries 45.50 milk"
- ✅ **Smart Category Matching** - Fuzzy matching for typos (e.g., "groc" → "Groceries")
- ✅ **Receipt Attachments** - Send photos with captions to attach receipts
- ✅ **Interactive Menu** - Button-based interface for easy navigation
- ✅ **Quick Amount Buttons** - Common amounts ($5, $10, $25, etc.)

### Reports & Visualizations
- 📊 **Beautiful Charts** - Pie charts for category breakdown
- 📈 **Daily Trends** - Bar charts showing daily spending
- 📅 **Multiple Timeframes** - Today, Week, Month summaries
- 🎨 **Color-coded Progress Bars** - Visual spending indicators

### Budget Planning
- 📋 **Monthly Budgets** - Set spending limits per category
- 💵 **Income Tracking** - Track actual and projected income
- ⚖️ **Balance Overview** - See projected vs actual balance
- 🚦 **Status Indicators** - Green/Yellow/Red budget alerts

### Automated Reports
- 🌙 **Daily Reports** - Automatic weekly summary every day at 9 PM
- 📅 **Monthly Reports** - Budget review on the 1st of each month
- 🔔 **Configurable** - Enable/disable automatic reports

### Categories (11 Total)
🛒 Groceries | 🍽️ Dining Out | 🚗 Transportation | 🎬 Entertainment
💅 Personal Care | 🏠 Housing | 💊 Healthcare | 📚 Education
🎁 Gifts | 📱 Subscriptions | 🔧 Other

## 🚀 Quick Start

### 1. Get Your Telegram Bot Token

1. Open Telegram and search for **@BotFather**
2. Send `/newbot` and follow the prompts
3. Copy the API token

### 2. Install Dependencies

```bash
cd /Users/kidus/Desktop/My_Budget
pip install -r requirements.txt
```

### 3. Run the Bot

```bash
export TELEGRAM_BOT_TOKEN='your-token-here'
python bot.py
```

## ✅ Testing

```bash
pip install -r requirements.txt
pytest
```

Included test coverage:
- Unit: `ExpenseParser`, `ExpenseManager` CRUD/budgets/settings.
- Integration: summary + chart generation via `BudgetBot._send_summary_with_charts` using stubs.

## 📱 Usage Guide

### Quick Expense Entry
Just send a message:
```
groceries 45.50 milk and eggs
uber 15 ride to work
dining 28.50
```

### With Receipt
Send a photo with caption:
```
groceries 45.50 weekly shopping
```

### Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message + main menu |
| `/menu` | Open interactive menu |
| `/today` | Today's spending summary |
| `/week` | Weekly report with charts |
| `/month` | Monthly report with charts |
| `/budget` | View/set budget plan |
| `/income` | Add income |
| `/recent` | View recent transactions |
| `/delete_last` | Remove last entry |
| `/export` | Download CSV |
| `/settings` | Configure bot |
| `/help` | Full help guide |

### Interactive Menu Options
- ➕ **Add Expense** - Category selection → Amount → Note
- 💰 **Add Income** - Track your earnings
- 📊 **Reports** - View summaries with visualizations
- 📋 **Budget Plan** - Set monthly budgets
- ⚙️ **Settings** - Toggle daily reports

## 📊 Sample Outputs

### Daily Summary
```
📅 Today's Spending: $125.75
─────────────────────────
🛒 Groceries
  $45.50 (36.2%) ███░░░░░
🍽️ Dining Out
  $40.00 (31.8%) ██░░░░░░
🚗 Transportation
  $15.00 (11.9%) █░░░░░░░
```

### Budget Status
```
📊 January 2026 Budget Status
══════════════════════════════

💰 INCOME
  Projected: $3500.00
  Actual: $3500.00 ████████

💸 EXPENSES
  🛒 Groceries
    $150.00 / $200.00 🟢 ██████░░
  🍽️ Dining Out
    $180.00 / $150.00 🔴 ████████

─────────────────────────────
📈 BALANCE
  Projected: $500.00
  Actual: $320.00 ✅
```

## 📁 File Structure

```
My_Budget/
├── bot.py              # Main bot with handlers & visualizations
├── database.py         # Database manager (SQLite)
├── requirements.txt    # Python dependencies
├── .gitignore          # Git ignore rules
├── user_data/          # Per-user SQLite databases (auto-created)
├── logs/               # Rotating log files (auto-created)
├── tests/              # Test suite (pytest)
│   ├── conftest.py
│   ├── test_expense_manager.py
│   ├── test_expense_manager_extended.py
│   ├── test_bot_flow.py
│   └── test_bot_extended.py
└── README.md           # This file
```

## 🗄️ Database Schema

### transactions
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| date | DATETIME | Timestamp |
| category | TEXT | Expense category |
| amount | REAL | Amount in dollars |
| note | TEXT | Optional description |
| receipt_file_id | TEXT | Telegram file ID for receipt |

### income
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| date | DATETIME | Timestamp |
| source | TEXT | Income source |
| amount | REAL | Amount |
| note | TEXT | Description |
| is_projected | BOOLEAN | Is this projected income? |

### budget_plans
| Column | Type | Description |
|--------|------|-------------|
| year | INTEGER | Budget year |
| month | INTEGER | Budget month |
| category | TEXT | Category name |
| planned_amount | REAL | Budgeted amount |

## ⚙️ Configuration

### Automatic Reports
- **Daily Report**: Sent at 9:00 PM with weekly summary
- **Monthly Report**: Sent on 1st of month at 9:00 AM
- Toggle in Settings or `/settings` command

### Category Aliases
The bot understands common shortcuts:
- "groc", "food" → 🛒 Groceries
- "uber", "gas", "bus" → 🚗 Transportation
- "netflix", "spotify" → 📱 Subscriptions
- And many more...

## 🔒 Security

- Token stored as environment variable (never in code)
- All data stored locally in SQLite
- Receipt photos stored as Telegram file IDs (not downloaded)

## 📈 Future Enhancements

- 🔄 Cloud backup integration
- 👥 Multi-user support
- 🔐 Data encryption
- 📊 More chart types
- 🎯 Savings goals

---

<!-- Badges -->
[![License](https://img.shields.io/github/license/kidusabe1/Budgy-By-K)](https://github.com/kidusabe1/Budgy-By-K/blob/main/LICENSE)
[![Stars](https://img.shields.io/github/stars/kidusabe1/Budgy-By-K?style=flat-square)](https://github.com/kidusabe1/Budgy-By-K/stargazers)
[![Forks](https://img.shields.io/github/forks/kidusabe1/Budgy-By-K?style=flat-square)](https://github.com/kidusabe1/Budgy-By-K/network)
[![Last Commit](https://img.shields.io/github/last-commit/kidusabe1/Budgy-By-K?style=flat-square)](https://github.com/kidusabe1/Budgy-By-K/commits/main)
[![Contributors](https://img.shields.io/github/contributors/kidusabe1/Budgy-By-K?style=flat-square)](https://github.com/kidusabe1/Budgy-By-K/graphs/contributors)

Happy budgeting! 💸
