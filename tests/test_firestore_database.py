"""Tests for FirestoreExpenseManager using the in-memory mock client."""

import os
from datetime import datetime, timedelta

import pytest

from firestore_database import FirestoreExpenseManager
from tests.mock_firestore import MockFirestoreClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture()
def mgr():
    """Shorthand fixture: a fresh FirestoreExpenseManager with mock client."""
    client = MockFirestoreClient()
    return FirestoreExpenseManager(user_id="test_user", db_client=client)


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

class TestConstruction:
    def test_user_id_required(self):
        with pytest.raises(ValueError, match="Either db_path or user_id"):
            FirestoreExpenseManager(db_client=MockFirestoreClient())

    def test_db_path_derives_user_id(self):
        mgr = FirestoreExpenseManager(db_path="/tmp/foo.db", db_client=MockFirestoreClient())
        assert mgr._user_id == "foo"

    def test_user_id_sanitised(self):
        mgr = FirestoreExpenseManager(user_id="a/b@c!d", db_client=MockFirestoreClient())
        assert mgr._user_id == "abcd"


# ---------------------------------------------------------------------------
# Expense CRUD
# ---------------------------------------------------------------------------

class TestAddExpense:
    def test_basic(self, mgr):
        result = mgr.add_expense("🛒 Groceries", 25.0)
        assert "✅ Saved" in result
        assert "$25.00" in result
        txns = mgr.get_all_transactions()
        assert len(txns) == 1
        assert txns[0]["category"] == "🛒 Groceries"
        assert txns[0]["amount"] == 25.0

    def test_with_note(self, mgr):
        result = mgr.add_expense("🍽️ Dining Out", 12.50, note="lunch")
        assert "(lunch)" in result
        txns = mgr.get_all_transactions()
        assert txns[0]["note"] == "lunch"

    def test_with_receipt(self, mgr):
        result = mgr.add_expense("🛒 Groceries", 10.0, receipt_file_id="abc123")
        assert "📎" in result
        recent = mgr.get_recent_transactions(1)
        assert recent[0]["receipt"] == "abc123"

    def test_negative_rejected(self, mgr):
        result = mgr.add_expense("🛒 Groceries", -5)
        assert "❌" in result
        assert len(mgr.get_all_transactions()) == 0

    def test_zero_rejected(self, mgr):
        result = mgr.add_expense("🛒 Groceries", 0)
        assert "❌" in result

    def test_date_override_datetime(self, mgr):
        dt = datetime(2025, 6, 15, 10, 30, 0)
        mgr.add_expense("🛒 Groceries", 20.0, date_override=dt)
        txns = mgr.get_all_transactions()
        assert "2025-06-15" in txns[0]["date"]

    def test_date_override_string(self, mgr):
        mgr.add_expense("🛒 Groceries", 20.0, date_override="2025-06-15 10:30:00")
        txns = mgr.get_all_transactions()
        assert "2025-06-15" in txns[0]["date"]

    def test_multiple(self, mgr):
        mgr.add_expense("🛒 Groceries", 10.0)
        mgr.add_expense("🍽️ Dining Out", 20.0)
        mgr.add_expense("🚗 Transportation", 30.0)
        assert len(mgr.get_all_transactions()) == 3


class TestGetRecentTransactions:
    def test_limit(self, mgr):
        for i in range(5):
            mgr.add_expense("🛒 Groceries", float(i + 1))
        assert len(mgr.get_recent_transactions(3)) == 3

    def test_fields(self, mgr):
        mgr.add_expense("🛒 Groceries", 10.0, note="milk")
        txn = mgr.get_recent_transactions(1)[0]
        assert "id" in txn
        assert "date" in txn
        assert txn["category"] == "🛒 Groceries"
        assert txn["amount"] == 10.0
        assert txn["note"] == "milk"


class TestDeleteLast:
    def test_delete_last(self, mgr):
        mgr.add_expense("🛒 Groceries", 10.0)
        mgr.add_expense("🍽️ Dining Out", 20.0)
        result = mgr.delete_last()
        assert "🗑️" in result
        assert len(mgr.get_all_transactions()) == 1

    def test_delete_last_empty(self, mgr):
        result = mgr.delete_last()
        assert "❌" in result

    def test_delete_last_n(self, mgr):
        for i in range(5):
            mgr.add_expense("🛒 Groceries", float(i + 1))
        result = mgr.delete_last_n(3)
        assert "3" in result
        assert len(mgr.get_all_transactions()) == 2

    def test_delete_last_n_zero(self, mgr):
        result = mgr.delete_last_n(0)
        assert "❌" in result

    def test_delete_last_n_negative(self, mgr):
        result = mgr.delete_last_n(-1)
        assert "❌" in result


# ---------------------------------------------------------------------------
# Income
# ---------------------------------------------------------------------------

class TestIncome:
    def test_add_income(self, mgr):
        result = mgr.add_income("Salary", 5000.0)
        assert "💰" in result
        assert "$5000.00" in result

    def test_add_income_with_note(self, mgr):
        result = mgr.add_income("Freelance", 500.0, note="web project")
        assert "(web project)" in result

    def test_add_projected_income(self, mgr):
        result = mgr.add_income("Salary", 5000.0, is_projected=True)
        assert "projected" in result

    def test_negative_rejected(self, mgr):
        result = mgr.add_income("Salary", -100)
        assert "❌" in result

    def test_zero_rejected(self, mgr):
        result = mgr.add_income("Salary", 0)
        assert "❌" in result


# ---------------------------------------------------------------------------
# Summaries
# ---------------------------------------------------------------------------

class TestSummaries:
    def test_empty_day(self, mgr):
        summary, data = mgr.get_summary("day")
        assert "$0.00" in summary
        assert data == {}

    def test_day_with_data(self, mgr):
        mgr.add_expense("🛒 Groceries", 25.0)
        mgr.add_expense("🍽️ Dining Out", 15.0)
        summary, data = mgr.get_summary("day")
        assert "$40.00" in summary
        assert "🛒 Groceries" in data
        assert "🍽️ Dining Out" in data

    def test_week(self, mgr):
        mgr.add_expense("🛒 Groceries", 50.0)
        summary, data = mgr.get_summary("week")
        assert "This Week" in summary

    def test_month(self, mgr):
        mgr.add_expense("🛒 Groceries", 100.0)
        summary, data = mgr.get_summary("month")
        assert "This Month" in summary

    def test_invalid_timeframe(self, mgr):
        summary, data = mgr.get_summary("year")
        assert "Invalid" in summary
        assert data == {}

    def test_daily_breakdown(self, mgr):
        mgr.add_expense("🛒 Groceries", 10.0)
        mgr.add_expense("🍽️ Dining Out", 20.0)
        breakdown = mgr.get_daily_breakdown("week")
        assert len(breakdown) >= 1
        # Each entry is (date_str, total)
        for date_str, total in breakdown:
            assert isinstance(date_str, str)
            assert total > 0

    def test_category_trend(self, mgr):
        mgr.add_expense("🛒 Groceries", 50.0)
        trend = mgr.get_category_trend("🛒 Groceries", months=3)
        assert len(trend) >= 1


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

class TestExport:
    def test_export_csv(self, mgr):
        mgr.add_expense("🛒 Groceries", 10.0, note="milk")
        mgr.add_expense("🍽️ Dining Out", 20.0, note="lunch")
        path = mgr.export_to_csv()
        assert path is not None
        with open(path) as f:
            lines = f.readlines()
        assert len(lines) == 3  # header + 2 rows
        os.unlink(path)

    def test_export_empty(self, mgr):
        assert mgr.export_to_csv() is None


# ---------------------------------------------------------------------------
# Budget planning
# ---------------------------------------------------------------------------

class TestBudgetPlanning:
    def test_set_budget(self, mgr):
        result = mgr.set_budget(2025, 6, "🛒 Groceries", 300.0)
        assert "📋" in result
        assert "$300.00" in result

    def test_negative_budget(self, mgr):
        result = mgr.set_budget(2025, 6, "🛒 Groceries", -100)
        assert "❌" in result

    def test_zero_budget_allowed(self, mgr):
        result = mgr.set_budget(2025, 6, "🛒 Groceries", 0)
        assert "📋" in result

    def test_set_projected_income(self, mgr):
        result = mgr.set_projected_income(2025, 6, "Salary", 5000.0)
        assert "💵" in result

    def test_projected_income_negative(self, mgr):
        result = mgr.set_projected_income(2025, 6, "Salary", -100)
        assert "❌" in result

    def test_has_budget_for_month(self, mgr):
        assert not mgr.has_budget_for_month(2025, 6)
        mgr.set_budget(2025, 6, "🛒 Groceries", 300.0)
        assert mgr.has_budget_for_month(2025, 6)

    def test_budget_upsert(self, mgr):
        mgr.set_budget(2025, 6, "🛒 Groceries", 300.0)
        mgr.set_budget(2025, 6, "🛒 Groceries", 400.0)
        plan = mgr.get_monthly_plan(2025, 6)
        assert plan["planned_budgets"]["🛒 Groceries"] == 400.0

    def test_copy_budget_from_previous_month(self, mgr):
        mgr.set_budget(2025, 5, "🛒 Groceries", 300.0)
        mgr.set_budget(2025, 5, "🍽️ Dining Out", 200.0)
        mgr.set_projected_income(2025, 5, "Salary", 5000.0)

        result = mgr.copy_budget_from_previous_month(2025, 6)
        assert "✅ Copied" in result
        assert "2 category budgets" in result
        assert "1 projected income" in result

        plan = mgr.get_monthly_plan(2025, 6)
        assert plan["planned_budgets"]["🛒 Groceries"] == 300.0
        assert plan["projected_income"]["Salary"] == 5000.0

    def test_copy_budget_no_previous(self, mgr):
        result = mgr.copy_budget_from_previous_month(2025, 6)
        assert "❌" in result

    def test_copy_budget_january_wraps(self, mgr):
        mgr.set_budget(2024, 12, "🛒 Groceries", 300.0)
        result = mgr.copy_budget_from_previous_month(2025, 1)
        assert "✅ Copied" in result


class TestMonthlyPlan:
    def test_empty_plan(self, mgr):
        plan = mgr.get_monthly_plan()
        assert plan["total_planned"] == 0
        assert plan["total_spent"] == 0

    def test_plan_with_data(self, mgr):
        now = datetime.now()
        mgr.set_budget(now.year, now.month, "🛒 Groceries", 300.0)
        mgr.add_expense("🛒 Groceries", 100.0)
        mgr.set_projected_income(now.year, now.month, "Salary", 5000.0)
        mgr.add_income("Salary", 3000.0)

        plan = mgr.get_monthly_plan()
        assert plan["planned_budgets"]["🛒 Groceries"] == 300.0
        assert plan["actual_spending"]["🛒 Groceries"] == 100.0
        assert plan["projected_income"]["Salary"] == 5000.0
        assert plan["total_actual_income"] == 3000.0


class TestBudgetStatus:
    def test_budget_status_format(self, mgr):
        now = datetime.now()
        mgr.set_budget(now.year, now.month, "🛒 Groceries", 300.0)
        mgr.add_expense("🛒 Groceries", 100.0)
        status = mgr.get_budget_status()
        assert "Budget Status" in status
        assert "INCOME" in status
        assert "EXPENSES" in status
        assert "BALANCE" in status

    def test_budget_status_indicators(self, mgr):
        now = datetime.now()
        mgr.set_budget(now.year, now.month, "🛒 Groceries", 100.0)
        # Under 80% → green
        mgr.add_expense("🛒 Groceries", 50.0)
        status = mgr.get_budget_status()
        assert "🟢" in status


# ---------------------------------------------------------------------------
# User settings
# ---------------------------------------------------------------------------

class TestUserSettings:
    def test_register_user(self, mgr):
        mgr.register_user(12345)
        users = mgr.get_all_registered_users()
        assert 12345 in users

    def test_register_idempotent(self, mgr):
        mgr.register_user(12345)
        mgr.register_user(12345)
        users = mgr.get_all_registered_users()
        assert users.count(12345) == 1

    def test_toggle_daily_report(self, mgr):
        mgr.register_user(12345)
        # Default is enabled
        assert mgr.is_daily_report_enabled(12345)
        # Toggle off
        new_state = mgr.toggle_daily_report(12345)
        assert new_state is False
        assert not mgr.is_daily_report_enabled(12345)
        # Toggle back on
        new_state = mgr.toggle_daily_report(12345)
        assert new_state is True

    def test_daily_report_default_unregistered(self, mgr):
        # Unregistered user should default to True
        assert mgr.is_daily_report_enabled(99999)

    def test_disabled_user_not_in_registered(self, mgr):
        mgr.register_user(12345)
        mgr.toggle_daily_report(12345)  # disable
        users = mgr.get_all_registered_users()
        assert 12345 not in users


class TestOnboarding:
    def test_not_completed_by_default(self, mgr):
        assert not mgr.is_onboarding_completed(12345)

    def test_complete_onboarding(self, mgr):
        mgr.complete_onboarding(12345)
        assert mgr.is_onboarding_completed(12345)

    def test_complete_onboarding_with_existing_user(self, mgr):
        mgr.register_user(12345)
        mgr.complete_onboarding(12345)
        assert mgr.is_onboarding_completed(12345)
        # Should still be registered
        assert 12345 in mgr.get_all_registered_users()


# ---------------------------------------------------------------------------
# Clear / delete
# ---------------------------------------------------------------------------

class TestClearData:
    def test_clear_all(self, mgr):
        mgr.add_expense("🛒 Groceries", 10.0)
        mgr.add_income("Salary", 1000.0)
        mgr.set_budget(2025, 6, "🛒 Groceries", 300.0)
        mgr.register_user(12345)
        result = mgr.clear_all_data()
        assert "🧹" in result
        assert len(mgr.get_all_transactions()) == 0

    def test_clear_expenses(self, mgr):
        mgr.add_expense("🛒 Groceries", 10.0)
        mgr.add_expense("🍽️ Dining Out", 20.0)
        result = mgr.clear_expenses()
        assert "2 expense" in result
        assert len(mgr.get_all_transactions()) == 0

    def test_clear_income(self, mgr):
        mgr.add_income("Salary", 1000.0)
        result = mgr.clear_income()
        assert "1 income" in result

    def test_clear_budgets(self, mgr):
        mgr.set_budget(2025, 6, "🛒 Groceries", 300.0)
        mgr.set_projected_income(2025, 6, "Salary", 5000.0)
        result = mgr.clear_budgets()
        assert "1 budget" in result
        assert "1 projected" in result

    def test_clear_expenses_empty(self, mgr):
        result = mgr.clear_expenses()
        assert "0 expense" in result


# ---------------------------------------------------------------------------
# Category matching
# ---------------------------------------------------------------------------

class TestCategoryMatching:
    def test_exact_alias(self, mgr):
        assert mgr.match_category("groceries") == "🛒 Groceries"

    def test_partial_name(self, mgr):
        assert mgr.match_category("entertain") == "🎬 Entertainment"

    def test_case_insensitive(self, mgr):
        assert mgr.match_category("GROCERIES") == "🛒 Groceries"

    def test_fuzzy(self, mgr):
        result = mgr.match_category("groceris")  # typo
        assert result == "🛒 Groceries"

    def test_unknown(self, mgr):
        assert mgr.match_category("xyzzy") is None

    def test_empty(self, mgr):
        assert mgr.match_category("") is None

    def test_whitespace(self, mgr):
        assert mgr.match_category("   ") is None


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_large_amount(self, mgr):
        mgr.add_expense("🛒 Groceries", 99999.99)
        txns = mgr.get_all_transactions()
        assert txns[0]["amount"] == 99999.99

    def test_unicode_note(self, mgr):
        mgr.add_expense("🛒 Groceries", 10.0, note="שופרסל אונליין")
        txns = mgr.get_all_transactions()
        assert txns[0]["note"] == "שופרסל אונליין"

    def test_special_chars_in_note(self, mgr):
        mgr.add_expense("🛒 Groceries", 10.0, note="Tom's <store> & \"more\"")
        txns = mgr.get_all_transactions()
        assert txns[0]["note"] == "Tom's <store> & \"more\""

    def test_decimal_precision(self, mgr):
        mgr.add_expense("🛒 Groceries", 10.33)
        txns = mgr.get_all_transactions()
        assert abs(txns[0]["amount"] - 10.33) < 0.001
