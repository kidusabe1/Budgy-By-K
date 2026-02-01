"""Firestore-backed ExpenseManager with the same public API as the SQLite version."""

import calendar
import csv
import os
import tempfile
from collections import defaultdict
from datetime import datetime, timedelta
from difflib import get_close_matches
from typing import Dict, List, Optional, Tuple


def _get_firestore_client():
    """Lazy-import and create a Firestore client."""
    from google.cloud import firestore
    return firestore.Client()


class FirestoreExpenseManager:
    """Manages all database operations for expense tracking via Firestore.

    Drop-in replacement for the SQLite ``ExpenseManager``.  Every public
    method has an identical signature and return value so that ``bot.py``
    and ``apple_webhook.py`` can switch backends with a single import change.
    """

    DB_DIR = "user_data"  # Kept for backward compatibility (unused)

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
        "🔧 Other",
    ]

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

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(
        self,
        db_path: Optional[str] = None,
        user_id: Optional[str] = None,
        db_client=None,
    ):
        """Initialise with the same signature as the SQLite version.

        Args:
            db_path: Ignored (kept for test-fixture compatibility).
            user_id: Required user identifier – maps to ``users/{user_id}``.
            db_client: Optional Firestore client (injected in tests).
        """
        if user_id is None and db_path is not None:
            # When tests pass only db_path, derive a stable user_id from it.
            user_id = os.path.splitext(os.path.basename(db_path))[0]
        if user_id is None:
            raise ValueError("Either db_path or user_id must be provided")

        safe_id = "".join(
            c for c in str(user_id) if c.isalnum() or c in ("_", "-")
        )
        self._user_id = safe_id
        self._db = db_client or _get_firestore_client()
        self._user_ref = self._db.collection("users").document(safe_id)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @property
    def _txn_col(self):
        return self._user_ref.collection("transactions")

    @property
    def _income_col(self):
        return self._user_ref.collection("income")

    @property
    def _budget_col(self):
        return self._user_ref.collection("budget_plans")

    @property
    def _proj_income_col(self):
        return self._user_ref.collection("projected_income")

    # ---- date ranges ---------------------------------------------------

    @staticmethod
    def _today_range():
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow = today + timedelta(days=1)
        return today, tomorrow

    @staticmethod
    def _week_range():
        now = datetime.now()
        monday = (now - timedelta(days=now.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        return monday, None

    @staticmethod
    def _month_range():
        now = datetime.now()
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return start, None

    def _query_transactions_in_range(self, start, end=None):
        """Return list of transaction dicts within *[start, end)*."""
        q = self._txn_col.where("date", ">=", start)
        if end is not None:
            q = q.where("date", "<", end)
        return [doc.to_dict() | {"_id": doc.id} for doc in q.stream()]

    # ---- progress bar --------------------------------------------------

    @staticmethod
    def _create_progress_bar(percentage: float, length: int = 8) -> str:
        filled_length = int(length * percentage / 100)
        return "█" * filled_length + "░" * (length - filled_length)

    # ------------------------------------------------------------------
    # Expense CRUD
    # ------------------------------------------------------------------

    def add_expense(
        self,
        category: str,
        amount: float,
        note: str = "",
        receipt_file_id: str = None,
        date_override: Optional[datetime] = None,
    ) -> str:
        if amount <= 0:
            return "❌ Amount must be positive."

        if date_override is not None:
            if isinstance(date_override, datetime):
                date_value = date_override
            else:
                try:
                    date_value = datetime.strptime(
                        str(date_override), "%Y-%m-%d %H:%M:%S"
                    )
                except ValueError:
                    date_value = datetime.fromisoformat(str(date_override))
        else:
            date_value = datetime.now()

        self._txn_col.add(
            {
                "date": date_value,
                "category": category,
                "amount": amount,
                "note": note,
                "receipt_file_id": receipt_file_id,
            }
        )

        note_text = f" ({note})" if note else ""
        receipt_text = " 📎" if receipt_file_id else ""
        return f"✅ Saved: ${amount:.2f} to {category}{note_text}{receipt_text}"

    def get_recent_transactions(self, limit: int = 10) -> List[Dict]:
        docs = (
            self._txn_col
            .order_by("date", direction="DESCENDING")
            .limit(limit)
            .stream()
        )
        txns = []
        for doc in docs:
            d = doc.to_dict()
            date_val = d.get("date")
            if isinstance(date_val, datetime):
                date_str = date_val.strftime("%Y-%m-%d %H:%M:%S")
            else:
                date_str = str(date_val) if date_val else ""
            txns.append(
                {
                    "id": doc.id,
                    "date": date_str,
                    "category": d.get("category", ""),
                    "amount": d.get("amount", 0),
                    "note": d.get("note", ""),
                    "receipt": d.get("receipt_file_id"),
                }
            )
        return txns

    def get_all_transactions(self) -> List[Dict]:
        docs = (
            self._txn_col
            .order_by("date", direction="DESCENDING")
            .stream()
        )
        txns = []
        for doc in docs:
            d = doc.to_dict()
            date_val = d.get("date")
            if isinstance(date_val, datetime):
                date_str = date_val.strftime("%Y-%m-%d %H:%M:%S")
            else:
                date_str = str(date_val) if date_val else ""
            txns.append(
                {
                    "id": doc.id,
                    "date": date_str,
                    "category": d.get("category", ""),
                    "amount": d.get("amount", 0),
                    "note": d.get("note", ""),
                }
            )
        return txns

    def delete_last(self) -> str:
        docs = list(
            self._txn_col
            .order_by("date", direction="DESCENDING")
            .limit(1)
            .stream()
        )
        if not docs:
            return "❌ No expenses to delete."

        d = docs[0].to_dict()
        amount = d.get("amount", 0)
        category = d.get("category", "")
        note = d.get("note", "")
        docs[0].reference.delete()

        note_text = f" ({note})" if note else ""
        return f"🗑️ Deleted: ${amount:.2f} from {category}{note_text}"

    def delete_last_n(self, n: int) -> str:
        if n <= 0:
            return "❌ Number must be positive."

        docs = list(
            self._txn_col
            .order_by("date", direction="DESCENDING")
            .limit(n)
            .stream()
        )
        to_delete = len(docs)
        batch = self._db.batch()
        for doc in docs:
            batch.delete(doc.reference)
        batch.commit()
        return f"🗑️ Deleted last {to_delete} expense(s)."

    # ------------------------------------------------------------------
    # Income
    # ------------------------------------------------------------------

    def add_income(
        self,
        source: str,
        amount: float,
        note: str = "",
        is_projected: bool = False,
    ) -> str:
        if amount <= 0:
            return "❌ Amount must be positive."

        self._income_col.add(
            {
                "date": datetime.now(),
                "source": source,
                "amount": amount,
                "note": note,
                "is_projected": is_projected,
            }
        )

        income_type = "projected " if is_projected else ""
        note_text = f" ({note})" if note else ""
        return f"💰 Added {income_type}income: ${amount:.2f} from {source}{note_text}"

    # ------------------------------------------------------------------
    # Summaries / reporting
    # ------------------------------------------------------------------

    def get_summary(self, timeframe: str = "day") -> Tuple[str, Dict]:
        if timeframe == "day":
            start, end = self._today_range()
            header = "📅 Today's Spending"
        elif timeframe == "week":
            start, end = self._week_range()
            header = "📊 This Week's Spending"
        elif timeframe == "month":
            start, end = self._month_range()
            header = "📈 This Month's Spending"
        else:
            return "Invalid timeframe.", {}

        rows = self._query_transactions_in_range(start, end)

        if not rows:
            return f"{header}: $0.00\n📭 No expenses recorded.", {}

        total = sum(r["amount"] for r in rows)
        by_cat: Dict[str, float] = defaultdict(float)
        for r in rows:
            by_cat[r["category"]] += r["amount"]

        # Sort descending by amount
        sorted_cats = sorted(by_cat.items(), key=lambda x: x[1], reverse=True)
        chart_data = dict(sorted_cats)

        summary = f"{header}: ${total:.2f}\n{'─' * 25}\n"
        for category, amount in sorted_cats:
            pct = (amount / total * 100) if total > 0 else 0
            bar = self._create_progress_bar(pct)
            summary += f"{category}\n  ${amount:.2f} ({pct:.1f}%) {bar}\n"

        return summary.strip(), chart_data

    def get_daily_breakdown(self, timeframe: str = "week") -> List[Tuple[str, float]]:
        if timeframe == "week":
            start, end = self._week_range()
        else:
            start, end = self._month_range()

        rows = self._query_transactions_in_range(start, end)
        by_day: Dict[str, float] = defaultdict(float)
        for r in rows:
            dt = r["date"]
            if isinstance(dt, datetime):
                day_str = dt.strftime("%Y-%m-%d")
            else:
                day_str = str(dt)[:10]
            by_day[day_str] += r["amount"]

        return sorted(by_day.items())

    def get_category_trend(
        self, category: str, months: int = 3
    ) -> List[Tuple[str, float]]:
        cutoff = datetime.now() - timedelta(days=months * 30)
        q = (
            self._txn_col
            .where("category", "==", category)
            .where("date", ">=", cutoff)
        )
        rows = [doc.to_dict() for doc in q.stream()]

        by_month: Dict[str, float] = defaultdict(float)
        for r in rows:
            dt = r["date"]
            if isinstance(dt, datetime):
                key = dt.strftime("%Y-%m")
            else:
                key = str(dt)[:7]
            by_month[key] += r["amount"]

        return sorted(by_month.items())

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export_to_csv(self) -> Optional[str]:
        txns = self.get_all_transactions()
        if not txns:
            return None

        suffix = f"_expenses_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        fd, filepath = tempfile.mkstemp(suffix=suffix)
        with os.fdopen(fd, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Date", "Category", "Amount", "Note"])
            for t in txns:
                writer.writerow([t["date"], t["category"], t["amount"], t["note"]])
        return filepath

    # ------------------------------------------------------------------
    # Budget planning
    # ------------------------------------------------------------------

    def set_budget(self, year: int, month: int, category: str, amount: float) -> str:
        if amount < 0:
            return "❌ Budget amount cannot be negative."

        doc_id = f"{year:04d}-{month:02d}_{category}"
        self._budget_col.document(doc_id).set(
            {
                "year": year,
                "month": month,
                "category": category,
                "planned_amount": amount,
            }
        )

        month_name = calendar.month_name[month]
        return f"📋 Budget set: ${amount:.2f} for {category} in {month_name} {year}"

    def set_projected_income(
        self, year: int, month: int, source: str, amount: float
    ) -> str:
        if amount <= 0:
            return "❌ Amount must be positive."

        doc_id = f"{year:04d}-{month:02d}_{source}"
        self._proj_income_col.document(doc_id).set(
            {
                "year": year,
                "month": month,
                "source": source,
                "amount": amount,
            }
        )

        month_name = calendar.month_name[month]
        return f"💵 Projected income set: ${amount:.2f} from {source} for {month_name} {year}"

    def copy_budget_from_previous_month(
        self, year: int = None, month: int = None
    ) -> str:
        if year is None:
            year = datetime.now().year
        if month is None:
            month = datetime.now().month

        if month == 1:
            prev_year, prev_month = year - 1, 12
        else:
            prev_year, prev_month = year, month - 1

        # Previous budgets
        prev_budgets = list(
            self._budget_col
            .where("year", "==", prev_year)
            .where("month", "==", prev_month)
            .stream()
        )

        if not prev_budgets:
            prev_month_name = calendar.month_name[prev_month]
            return f"❌ No budget plans found for {prev_month_name} {prev_year} to copy."

        batch = self._db.batch()
        copied_count = 0
        for doc in prev_budgets:
            d = doc.to_dict()
            new_id = f"{year:04d}-{month:02d}_{d['category']}"
            batch.set(
                self._budget_col.document(new_id),
                {
                    "year": year,
                    "month": month,
                    "category": d["category"],
                    "planned_amount": d["planned_amount"],
                },
            )
            copied_count += 1

        # Previous projected income
        prev_income = list(
            self._proj_income_col
            .where("year", "==", prev_year)
            .where("month", "==", prev_month)
            .stream()
        )
        income_copied = 0
        for doc in prev_income:
            d = doc.to_dict()
            new_id = f"{year:04d}-{month:02d}_{d['source']}"
            batch.set(
                self._proj_income_col.document(new_id),
                {
                    "year": year,
                    "month": month,
                    "source": d["source"],
                    "amount": d["amount"],
                },
            )
            income_copied += 1

        batch.commit()

        prev_month_name = calendar.month_name[prev_month]
        curr_month_name = calendar.month_name[month]
        msg = f"✅ Copied budget from {prev_month_name} to {curr_month_name}:\n"
        msg += f"• {copied_count} category budgets\n"
        if income_copied:
            msg += f"• {income_copied} projected income sources"
        return msg

    def has_budget_for_month(self, year: int = None, month: int = None) -> bool:
        if year is None:
            year = datetime.now().year
        if month is None:
            month = datetime.now().month

        docs = list(
            self._budget_col
            .where("year", "==", year)
            .where("month", "==", month)
            .limit(1)
            .stream()
        )
        return len(docs) > 0

    def get_monthly_plan(self, year: int = None, month: int = None) -> Dict:
        if year is None:
            year = datetime.now().year
        if month is None:
            month = datetime.now().month

        # Planned budgets
        planned_budgets: Dict[str, float] = {}
        for doc in (
            self._budget_col
            .where("year", "==", year)
            .where("month", "==", month)
            .stream()
        ):
            d = doc.to_dict()
            planned_budgets[d["category"]] = d["planned_amount"]

        # Actual spending this month
        month_start = datetime(year, month, 1)
        if month == 12:
            month_end = datetime(year + 1, 1, 1)
        else:
            month_end = datetime(year, month + 1, 1)

        actual_spending: Dict[str, float] = defaultdict(float)
        for doc in (
            self._txn_col
            .where("date", ">=", month_start)
            .where("date", "<", month_end)
            .stream()
        ):
            d = doc.to_dict()
            actual_spending[d["category"]] += d["amount"]
        actual_spending = dict(actual_spending)

        # Projected income
        projected_income: Dict[str, float] = {}
        for doc in (
            self._proj_income_col
            .where("year", "==", year)
            .where("month", "==", month)
            .stream()
        ):
            d = doc.to_dict()
            projected_income[d["source"]] = d["amount"]

        # Actual income
        actual_income: Dict[str, float] = defaultdict(float)
        for doc in (
            self._income_col
            .where("date", ">=", month_start)
            .where("date", "<", month_end)
            .where("is_projected", "==", False)
            .stream()
        ):
            d = doc.to_dict()
            actual_income[d["source"]] += d["amount"]
        actual_income = dict(actual_income)

        return {
            "year": year,
            "month": month,
            "planned_budgets": planned_budgets,
            "actual_spending": actual_spending,
            "projected_income": projected_income,
            "actual_income": actual_income,
            "total_planned": sum(planned_budgets.values()),
            "total_spent": sum(actual_spending.values()),
            "total_projected_income": sum(projected_income.values()),
            "total_actual_income": sum(actual_income.values()),
        }

    def get_budget_status(self) -> str:
        plan = self.get_monthly_plan()

        month_name = calendar.month_name[plan["month"]]

        summary = f"📊 {month_name} {plan['year']} Budget Status\n{'═' * 30}\n\n"

        # Income section
        summary += "💰 INCOME\n"
        total_projected = plan["total_projected_income"]
        total_actual = plan["total_actual_income"]

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
        all_categories = set(plan["planned_budgets"].keys()) | set(
            plan["actual_spending"].keys()
        )

        for category in sorted(all_categories):
            planned = plan["planned_budgets"].get(category, 0)
            actual = plan["actual_spending"].get(category, 0)

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
        summary += "📈 BALANCE\n"
        balance_projected = total_projected - plan["total_planned"]
        balance_actual = total_actual - plan["total_spent"]

        summary += f"  Projected: ${balance_projected:.2f}\n"
        summary += f"  Actual: ${balance_actual:.2f}"

        if balance_actual >= 0:
            summary += " ✅"
        else:
            summary += " ⚠️"

        return summary

    # ------------------------------------------------------------------
    # User settings
    # ------------------------------------------------------------------

    def register_user(self, chat_id: int) -> None:
        self._user_ref.set(
            {
                "chat_id": chat_id,
                "daily_report_enabled": True,
                "report_time": "21:00",
            },
            merge=True,
        )

    def get_all_registered_users(self) -> List[int]:
        doc = self._user_ref.get()
        if not doc.exists:
            return []
        d = doc.to_dict()
        if d.get("daily_report_enabled"):
            chat_id = d.get("chat_id")
            return [chat_id] if chat_id is not None else []
        return []

    def toggle_daily_report(self, chat_id: int) -> bool:
        doc = self._user_ref.get()
        if doc.exists:
            current = doc.to_dict().get("daily_report_enabled", True)
            new_state = not current
        else:
            new_state = True
        self._user_ref.set(
            {"chat_id": chat_id, "daily_report_enabled": new_state}, merge=True
        )
        return new_state

    def is_daily_report_enabled(self, chat_id: int) -> bool:
        doc = self._user_ref.get()
        if doc.exists:
            return bool(doc.to_dict().get("daily_report_enabled", True))
        return True

    def is_onboarding_completed(self, chat_id: int) -> bool:
        doc = self._user_ref.get()
        if doc.exists:
            return bool(doc.to_dict().get("onboarding_completed", False))
        return False

    def complete_onboarding(self, chat_id: int) -> None:
        self._user_ref.set(
            {"chat_id": chat_id, "onboarding_completed": True}, merge=True
        )

    # ------------------------------------------------------------------
    # Clear / delete
    # ------------------------------------------------------------------

    def _delete_collection(self, col_ref) -> int:
        """Delete every document in *col_ref*. Returns count deleted."""
        docs = list(col_ref.stream())
        batch = self._db.batch()
        for doc in docs:
            batch.delete(doc.reference)
        if docs:
            batch.commit()
        return len(docs)

    def clear_all_data(self) -> str:
        for col_name in (
            "transactions",
            "income",
            "budget_plans",
            "projected_income",
        ):
            self._delete_collection(self._user_ref.collection(col_name))
        # Also wipe the user profile document
        self._user_ref.delete()
        return "🧹 All data cleared."

    def clear_expenses(self) -> str:
        count = self._delete_collection(self._txn_col)
        return f"🗑️ Deleted {count} expense(s)."

    def clear_income(self) -> str:
        count = self._delete_collection(self._income_col)
        return f"🗑️ Deleted {count} income record(s)."

    def clear_budgets(self) -> str:
        budget_count = self._delete_collection(self._budget_col)
        income_count = self._delete_collection(self._proj_income_col)
        return f"🗑️ Deleted {budget_count} budget(s) and {income_count} projected income(s)."

    # ------------------------------------------------------------------
    # Category matching  (pure Python – identical to SQLite version)
    # ------------------------------------------------------------------

    def match_category(self, user_input: str) -> Optional[str]:
        user_input_lower = user_input.lower().strip()

        if not user_input_lower:
            return None

        # Check aliases first
        if user_input_lower in self.CATEGORY_ALIASES:
            return self.CATEGORY_ALIASES[user_input_lower]

        # Partial match in category names
        for category in self.CATEGORIES:
            cat_name = (
                category.split(" ", 1)[1].lower()
                if " " in category
                else category.lower()
            )
            if user_input_lower in cat_name or cat_name in user_input_lower:
                return category

        # Fuzzy match
        all_names = list(self.CATEGORY_ALIASES.keys())
        matches = get_close_matches(user_input_lower, all_names, n=1, cutoff=0.6)

        if matches:
            return self.CATEGORY_ALIASES[matches[0]]

        return None
