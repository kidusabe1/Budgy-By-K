import sqlite3
import csv
import io
import calendar
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from difflib import get_close_matches


class ExpenseManager:
    """Manages all database operations for expense tracking."""
    
    DB_PATH = "expenses.db"
    CATEGORIES = [
        "🛒 Groceries", 
        "🍽️ Dining Out", 
        "🚗 Transportation", 
        "🎬 Entertainment", 
        "💅 Personal Care", 
        "🏠 Housing", 
        "💊 Healthcare",
        "📚 Education",
        "🎁 Gifts",
        "📱 Subscriptions",
        "🔧 Other"
    ]
    
    # Short names for matching
    CATEGORY_ALIASES = {
        "groceries": "🛒 Groceries",
        "groc": "🛒 Groceries",
        "food": "🛒 Groceries",
        "dining": "🍽️ Dining Out",
        "restaurant": "🍽️ Dining Out",
        "eat": "🍽️ Dining Out",
        "transport": "🚗 Transportation",
        "transportation": "🚗 Transportation",
        "gas": "🚗 Transportation",
        "fuel": "🚗 Transportation",
        "uber": "🚗 Transportation",
        "bus": "🚗 Transportation",
        "taxi": "🚗 Transportation",
        "entertainment": "🎬 Entertainment",
        "fun": "🎬 Entertainment",
        "movie": "🎬 Entertainment",
        "games": "🎬 Entertainment",
        "personal": "💅 Personal Care",
        "care": "💅 Personal Care",
        "beauty": "💅 Personal Care",
        "housing": "🏠 Housing",
        "rent": "🏠 Housing",
        "utilities": "🏠 Housing",
        "electric": "🏠 Housing",
        "water": "🏠 Housing",
        "healthcare": "💊 Healthcare",
        "medical": "💊 Healthcare",
        "doctor": "💊 Healthcare",
        "pharmacy": "💊 Healthcare",
        "education": "📚 Education",
        "books": "📚 Education",
        "course": "📚 Education",
        "gifts": "🎁 Gifts",
        "gift": "🎁 Gifts",
        "present": "🎁 Gifts",
        "subscriptions": "📱 Subscriptions",
        "subscription": "📱 Subscriptions",
        "netflix": "📱 Subscriptions",
        "spotify": "📱 Subscriptions",
        "other": "🔧 Other",
        "misc": "🔧 Other",
    }
    
    def __init__(self, db_path: Optional[str] = None):
        """Initialize database connection and create schema if needed.

        Args:
            db_path: Optional custom database path (used by tests)
        """
        self.db_path = db_path or self.DB_PATH
        self._init_db()
    
    def _init_db(self):
        """Create all necessary tables if they don't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Main transactions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATETIME DEFAULT CURRENT_TIMESTAMP,
                category TEXT NOT NULL,
                amount REAL NOT NULL,
                note TEXT,
                receipt_file_id TEXT
            )
        ''')
        
        # Income tracking table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS income (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATETIME DEFAULT CURRENT_TIMESTAMP,
                source TEXT NOT NULL,
                amount REAL NOT NULL,
                note TEXT,
                is_projected BOOLEAN DEFAULT 0
            )
        ''')
        
        # Monthly budget plans table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS budget_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                year INTEGER NOT NULL,
                month INTEGER NOT NULL,
                category TEXT NOT NULL,
                planned_amount REAL NOT NULL,
                UNIQUE(year, month, category)
            )
        ''')
        
        # User settings table (for storing chat IDs for scheduled reports)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER UNIQUE,
                daily_report_enabled BOOLEAN DEFAULT 1,
                report_time TEXT DEFAULT '21:00'
            )
        ''')
        
        # Projected income table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS projected_income (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                year INTEGER NOT NULL,
                month INTEGER NOT NULL,
                source TEXT NOT NULL,
                amount REAL NOT NULL,
                UNIQUE(year, month, source)
            )
        ''')
        
        conn.commit()
        self._ensure_receipt_column(conn)
        conn.close()

    @staticmethod
    def _ensure_receipt_column(conn: sqlite3.Connection) -> None:
        """Add receipt_file_id column if the database was created before receipts existed."""
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(transactions)")
        columns = [row[1] for row in cursor.fetchall()]
        if 'receipt_file_id' not in columns:
            cursor.execute("ALTER TABLE transactions ADD COLUMN receipt_file_id TEXT")
            conn.commit()

    def clear_all_data(self) -> str:
        """Remove all user data from every table and vacuum the database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        for table in (
            'transactions',
            'income',
            'budget_plans',
            'projected_income',
            'user_settings',
        ):
            cursor.execute(f'DELETE FROM {table}')
        conn.commit()
        conn.close()
        
        # VACUUM must be run outside of a transaction
        conn = sqlite3.connect(self.db_path)
        conn.execute('VACUUM')
        conn.close()
        return "🧹 All data cleared."

    def clear_expenses(self) -> str:
        """Remove all expense transactions."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM transactions')
        count = cursor.fetchone()[0]
        cursor.execute('DELETE FROM transactions')
        conn.commit()
        conn.close()
        return f"🗑️ Deleted {count} expense(s)."

    def clear_income(self) -> str:
        """Remove all income records."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM income')
        count = cursor.fetchone()[0]
        cursor.execute('DELETE FROM income')
        conn.commit()
        conn.close()
        return f"🗑️ Deleted {count} income record(s)."

    def clear_budgets(self) -> str:
        """Remove all budget plans and projected income."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM budget_plans')
        budget_count = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM projected_income')
        income_count = cursor.fetchone()[0]
        cursor.execute('DELETE FROM budget_plans')
        cursor.execute('DELETE FROM projected_income')
        conn.commit()
        conn.close()
        return f"🗑️ Deleted {budget_count} budget(s) and {income_count} projected income(s)."

    def delete_last_n(self, n: int) -> str:
        """Delete the last N expense transactions."""
        if n <= 0:
            return "❌ Number must be positive."
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM transactions')
        total = cursor.fetchone()[0]
        to_delete = min(n, total)
        cursor.execute('''
            DELETE FROM transactions WHERE id IN (
                SELECT id FROM transactions ORDER BY id DESC LIMIT ?
            )
        ''', (to_delete,))
        conn.commit()
        conn.close()
        return f"🗑️ Deleted last {to_delete} expense(s)."
    
    def add_expense(self, category: str, amount: float, note: str = "", receipt_file_id: str = None) -> str:
        """Add an expense to the database."""
        if amount <= 0:
            return "❌ Amount must be positive."
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO transactions (category, amount, note, date, receipt_file_id)
            VALUES (?, ?, ?, datetime('now', 'localtime'), ?)
        ''', (category, amount, note, receipt_file_id))
        
        conn.commit()
        conn.close()
        
        note_text = f" ({note})" if note else ""
        receipt_text = " 📎" if receipt_file_id else ""
        return f"✅ Saved: ${amount:.2f} to {category}{note_text}{receipt_text}"
    
    def add_income(self, source: str, amount: float, note: str = "", is_projected: bool = False) -> str:
        """Add income to the database."""
        if amount <= 0:
            return "❌ Amount must be positive."
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO income (source, amount, note, date, is_projected)
            VALUES (?, ?, ?, datetime('now', 'localtime'), ?)
        ''', (source, amount, note, is_projected))
        
        conn.commit()
        conn.close()
        
        income_type = "projected " if is_projected else ""
        note_text = f" ({note})" if note else ""
        return f"💰 Added {income_type}income: ${amount:.2f} from {source}{note_text}"
    
    def get_summary(self, timeframe: str = "day") -> Tuple[str, Dict]:
        """Get spending summary for specified timeframe."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if timeframe == "day":
            date_filter = self._get_today_filter()
            header = "📅 Today's Spending"
        elif timeframe == "week":
            date_filter = self._get_week_filter()
            header = "📊 This Week's Spending"
        elif timeframe == "month":
            date_filter = self._get_month_filter()
            header = "📈 This Month's Spending"
        else:
            return "Invalid timeframe.", {}
        
        # Get total
        cursor.execute(f'SELECT SUM(amount) FROM transactions WHERE {date_filter}')
        total = cursor.fetchone()[0] or 0
        
        # Get breakdown by category
        cursor.execute(f'''
            SELECT category, SUM(amount) FROM transactions 
            WHERE {date_filter}
            GROUP BY category
            ORDER BY SUM(amount) DESC
        ''')
        
        rows = cursor.fetchall()
        conn.close()
        
        # Build data for charts
        chart_data = {cat: amt for cat, amt in rows}
        
        if not rows:
            return f"{header}: $0.00\n📭 No expenses recorded.", {}
        
        summary = f"{header}: ${total:.2f}\n{'─' * 25}\n"
        for category, amount in rows:
            percentage = (amount / total * 100) if total > 0 else 0
            bar = self._create_progress_bar(percentage)
            summary += f"{category}\n  ${amount:.2f} ({percentage:.1f}%) {bar}\n"
        
        return summary.strip(), chart_data
    
    def get_daily_breakdown(self, timeframe: str = "week") -> List[Tuple[str, float]]:
        """Get daily spending breakdown for charts."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if timeframe == "week":
            date_filter = self._get_week_filter()
        else:
            date_filter = self._get_month_filter()
        
        cursor.execute(f'''
            SELECT DATE(date) as day, SUM(amount) 
            FROM transactions 
            WHERE {date_filter}
            GROUP BY DATE(date)
            ORDER BY day
        ''')
        
        rows = cursor.fetchall()
        conn.close()
        return rows
    
    def get_category_trend(self, category: str, months: int = 3) -> List[Tuple[str, float]]:
        """Get spending trend for a category over months."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT strftime('%Y-%m', date) as month, SUM(amount)
            FROM transactions
            WHERE category = ? AND date >= date('now', ?)
            GROUP BY month
            ORDER BY month
        ''', (category, f'-{months} months'))
        
        rows = cursor.fetchall()
        conn.close()
        return rows
    
    def delete_last(self) -> str:
        """Delete the most recently inserted expense entry (highest id)."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('SELECT id, amount, category, note FROM transactions ORDER BY id DESC LIMIT 1')
        result = cursor.fetchone()

        if not result:
            conn.close()
            return "❌ No expenses to delete."

        last_id, amount, category, note = result
        cursor.execute('DELETE FROM transactions WHERE id = ?', (last_id,))

        conn.commit()
        conn.close()

        note_text = f" ({note})" if note else ""
        return f"🗑️ Deleted: ${amount:.2f} from {category}{note_text}"
    
    def get_recent_transactions(self, limit: int = 10) -> List[Dict]:
        """Get recent transactions."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, date, category, amount, note, receipt_file_id 
            FROM transactions ORDER BY date DESC LIMIT ?
        ''', (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        transactions = []
        for row in rows:
            transactions.append({
                'id': row[0],
                'date': row[1],
                'category': row[2],
                'amount': row[3],
                'note': row[4],
                'receipt': row[5]
            })
        return transactions
    
    def export_to_csv(self) -> Optional[str]:
        """Export all transactions to a CSV file."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT date, category, amount, note FROM transactions ORDER BY date DESC')
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            return None
        
        filename = f"expenses_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        with open(filename, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Date', 'Category', 'Amount', 'Note'])
            writer.writerows(rows)
        
        return filename
    
    # ===== Budget Planning Methods =====
    
    def set_budget(self, year: int, month: int, category: str, amount: float) -> str:
        """Set budget for a category in a specific month."""
        if amount < 0:
            return "❌ Budget amount cannot be negative."
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO budget_plans (year, month, category, planned_amount)
            VALUES (?, ?, ?, ?)
        ''', (year, month, category, amount))
        
        conn.commit()
        conn.close()
        
        month_name = calendar.month_name[month]
        return f"📋 Budget set: ${amount:.2f} for {category} in {month_name} {year}"
    
    def set_projected_income(self, year: int, month: int, source: str, amount: float) -> str:
        """Set projected income for a month."""
        if amount <= 0:
            return "❌ Amount must be positive."
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO projected_income (year, month, source, amount)
            VALUES (?, ?, ?, ?)
        ''', (year, month, source, amount))
        
        conn.commit()
        conn.close()
        
        month_name = calendar.month_name[month]
        return f"💵 Projected income set: ${amount:.2f} from {source} for {month_name} {year}"
    
    def get_monthly_plan(self, year: int = None, month: int = None) -> Dict:
        """Get complete monthly financial plan."""
        if year is None:
            year = datetime.now().year
        if month is None:
            month = datetime.now().month
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get planned budgets
        cursor.execute('''
            SELECT category, planned_amount FROM budget_plans
            WHERE year = ? AND month = ?
        ''', (year, month))
        planned_budgets = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Get actual spending
        month_filter = f"strftime('%Y-%m', date) = '{year:04d}-{month:02d}'"
        cursor.execute(f'''
            SELECT category, SUM(amount) FROM transactions
            WHERE {month_filter}
            GROUP BY category
        ''')
        actual_spending = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Get projected income
        cursor.execute('''
            SELECT source, amount FROM projected_income
            WHERE year = ? AND month = ?
        ''', (year, month))
        projected_income = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Get actual income
        cursor.execute(f'''
            SELECT source, SUM(amount) FROM income
            WHERE {month_filter} AND is_projected = 0
            GROUP BY source
        ''')
        actual_income = {row[0]: row[1] for row in cursor.fetchall()}
        
        conn.close()
        
        return {
            'year': year,
            'month': month,
            'planned_budgets': planned_budgets,
            'actual_spending': actual_spending,
            'projected_income': projected_income,
            'actual_income': actual_income,
            'total_planned': sum(planned_budgets.values()),
            'total_spent': sum(actual_spending.values()),
            'total_projected_income': sum(projected_income.values()),
            'total_actual_income': sum(actual_income.values())
        }
    
    def get_budget_status(self) -> str:
        """Get current month's budget status with progress bars."""
        plan = self.get_monthly_plan()
        
        month_name = calendar.month_name[plan['month']]
        
        summary = f"📊 {month_name} {plan['year']} Budget Status\n{'═' * 30}\n\n"
        
        # Income section
        summary += "💰 INCOME\n"
        total_projected = plan['total_projected_income']
        total_actual = plan['total_actual_income']
        
        if total_projected > 0:
            pct = min(100, (total_actual / total_projected * 100))
            bar = self._create_progress_bar(pct)
            summary += f"  Projected: ${total_projected:.2f}\n"
            summary += f"  Actual: ${total_actual:.2f} {bar}\n\n"
        else:
            summary += f"  Actual: ${total_actual:.2f}\n"
            summary += "  (No projected income set)\n\n"
        
        # Expenses section
        summary += "💸 EXPENSES\n"
        all_categories = set(plan['planned_budgets'].keys()) | set(plan['actual_spending'].keys())
        
        for category in sorted(all_categories):
            planned = plan['planned_budgets'].get(category, 0)
            actual = plan['actual_spending'].get(category, 0)
            
            if planned > 0:
                pct = min(100, (actual / planned * 100))
                status = "🟢" if pct < 80 else "🟡" if pct < 100 else "🔴"
                bar = self._create_progress_bar(pct)
                summary += f"  {category}\n"
                summary += f"    ${actual:.2f} / ${planned:.2f} {status} {bar}\n"
            else:
                summary += f"  {category}: ${actual:.2f}\n"
        
        # Balance section
        summary += f"\n{'─' * 30}\n"
        summary += f"📈 BALANCE\n"
        balance_projected = total_projected - plan['total_planned']
        balance_actual = total_actual - plan['total_spent']
        
        summary += f"  Projected: ${balance_projected:.2f}\n"
        summary += f"  Actual: ${balance_actual:.2f}"
        
        if balance_actual >= 0:
            summary += " ✅"
        else:
            summary += " ⚠️"
        
        return summary
    
    # ===== User Settings =====
    
    def register_user(self, chat_id: int) -> None:
        """Register a user for scheduled reports."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR IGNORE INTO user_settings (chat_id) VALUES (?)
        ''', (chat_id,))
        
        conn.commit()
        conn.close()
    
    def get_all_registered_users(self) -> List[int]:
        """Get all registered chat IDs for scheduled reports."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT chat_id FROM user_settings WHERE daily_report_enabled = 1')
        rows = cursor.fetchall()
        conn.close()
        
        return [row[0] for row in rows]
    
    def toggle_daily_report(self, chat_id: int) -> bool:
        """Toggle daily report for a user. Returns new state."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT daily_report_enabled FROM user_settings WHERE chat_id = ?', (chat_id,))
        result = cursor.fetchone()
        
        if result:
            new_state = not result[0]
            cursor.execute('UPDATE user_settings SET daily_report_enabled = ? WHERE chat_id = ?', (new_state, chat_id))
        else:
            new_state = True
            cursor.execute('INSERT INTO user_settings (chat_id, daily_report_enabled) VALUES (?, ?)', (chat_id, new_state))
        
        conn.commit()
        conn.close()
        return new_state

    def is_daily_report_enabled(self, chat_id: int) -> bool:
        """Return whether daily reports are enabled for a user."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT daily_report_enabled FROM user_settings WHERE chat_id = ?', (chat_id,))
        result = cursor.fetchone()
        conn.close()
        return bool(result[0]) if result else True
    
    # ===== Helper Methods =====
    
    @staticmethod
    def _create_progress_bar(percentage: float, length: int = 8) -> str:
        """Create a text-based progress bar."""
        filled_length = int(length * percentage / 100)
        return '█' * filled_length + '░' * (length - filled_length)
    
    @staticmethod
    def _get_today_filter() -> str:
        """Get SQL filter for today's date."""
        today = datetime.now().strftime('%Y-%m-%d')
        return f"DATE(date) = '{today}'"
    
    @staticmethod
    def _get_week_filter() -> str:
        """Get SQL filter for current week (Monday to Sunday)."""
        today = datetime.now()
        monday = today - timedelta(days=today.weekday())
        monday_str = monday.strftime('%Y-%m-%d')
        return f"DATE(date) >= '{monday_str}'"
    
    @staticmethod
    def _get_month_filter() -> str:
        """Get SQL filter for current month."""
        today = datetime.now()
        return f"strftime('%Y-%m', date) = '{today.year:04d}-{today.month:02d}'"
    
    def match_category(self, user_input: str) -> Optional[str]:
        """Match user input to a category using aliases and fuzzy matching."""
        user_input_lower = user_input.lower().strip()
        
        # Reject empty or whitespace-only input
        if not user_input_lower:
            return None
        
        # Check aliases first
        if user_input_lower in self.CATEGORY_ALIASES:
            return self.CATEGORY_ALIASES[user_input_lower]
        
        # Check for partial matches in category names
        for category in self.CATEGORIES:
            cat_name = category.split(' ', 1)[1].lower() if ' ' in category else category.lower()
            if user_input_lower in cat_name or cat_name in user_input_lower:
                return category
        
        # Fuzzy match
        all_names = list(self.CATEGORY_ALIASES.keys())
        matches = get_close_matches(user_input_lower, all_names, n=1, cutoff=0.6)
        
        if matches:
            return self.CATEGORY_ALIASES[matches[0]]
        
        return None
    
    def get_all_transactions(self) -> List[Dict]:
        """Get all transactions from the database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT id, date, category, amount, note FROM transactions ORDER BY date DESC')
        rows = cursor.fetchall()
        conn.close()
        
        transactions = []
        for row in rows:
            transactions.append({
                'id': row[0],
                'date': row[1],
                'category': row[2],
                'amount': row[3],
                'note': row[4]
            })
        
        return transactions
