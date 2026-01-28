import os
from datetime import datetime, timedelta

import pytest

from database import ExpenseManager


@pytest.fixture()
def expense_manager(tmp_path):
    db_path = tmp_path / "test_expenses.db"
    manager = ExpenseManager(db_path=str(db_path))
    yield manager


def test_add_expense_and_summary_day(expense_manager: ExpenseManager):
    expense_manager.add_expense("🛒 Groceries", 25.0, "milk")
    summary, chart_data = expense_manager.get_summary("day")

    assert "🛒 Groceries" in summary
    assert "$25.00" in summary
    assert chart_data["🛒 Groceries"] == 25.0


def test_income_and_budget_plan(expense_manager: ExpenseManager):
    now = datetime.now()

    expense_manager.add_income("Salary", 1200.0, "January")
    expense_manager.set_budget(now.year, now.month, "🛒 Groceries", 300.0)
    plan = expense_manager.get_monthly_plan(now.year, now.month)

    assert plan["actual_income"]["Salary"] == 1200.0
    assert plan["planned_budgets"]["🛒 Groceries"] == 300.0
    assert plan["total_actual_income"] == 1200.0


def test_daily_breakdown_week(expense_manager: ExpenseManager):
    expense_manager.add_expense("🛒 Groceries", 10.0)
    expense_manager.add_expense("🍽️ Dining Out", 15.0)

    breakdown = expense_manager.get_daily_breakdown("week")
    assert breakdown, "Expected at least one day of spending in breakdown"
    date_str, amount = breakdown[0]
    assert amount >= 10.0


def test_delete_last(expense_manager: ExpenseManager):
    expense_manager.add_expense("🛒 Groceries", 8.0, "coffee")
    expense_manager.add_expense("🍽️ Dining Out", 12.0, "lunch")

    msg = expense_manager.delete_last()
    assert "Deleted" in msg

    remaining = expense_manager.get_all_transactions()
    assert len(remaining) == 1
    assert remaining[0]["category"] == "🛒 Groceries"


def test_toggle_daily_report(expense_manager: ExpenseManager):
    chat_id = 12345
    expense_manager.register_user(chat_id)

    assert expense_manager.is_daily_report_enabled(chat_id) is True
    new_state = expense_manager.toggle_daily_report(chat_id)
    assert new_state is False
    assert expense_manager.is_daily_report_enabled(chat_id) is False