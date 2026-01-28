"""Comprehensive tests for ExpenseManager class."""
import os
from datetime import datetime, timedelta

import pytest

from database import ExpenseManager


@pytest.fixture()
def expense_manager(tmp_path):
    """Create a fresh ExpenseManager with a temp database."""
    db_path = tmp_path / "test_expenses.db"
    manager = ExpenseManager(db_path=str(db_path))
    yield manager


class TestAddExpense:
    """Tests for add_expense functionality."""

    def test_add_expense_basic(self, expense_manager: ExpenseManager):
        """Test adding a basic expense."""
        result = expense_manager.add_expense("🛒 Groceries", 25.0)
        assert "✅ Saved" in result
        assert "$25.00" in result
        assert "🛒 Groceries" in result

    def test_add_expense_with_note(self, expense_manager: ExpenseManager):
        """Test adding expense with a note."""
        result = expense_manager.add_expense("🛒 Groceries", 15.50, "milk and eggs")
        assert "milk and eggs" in result

    def test_add_expense_with_receipt(self, expense_manager: ExpenseManager):
        """Test adding expense with receipt file ID."""
        result = expense_manager.add_expense("🍽️ Dining Out", 45.0, "dinner", "file_id_123")
        assert "📎" in result

    def test_add_expense_negative_amount_rejected(self, expense_manager: ExpenseManager):
        """Test that negative amounts are rejected."""
        result = expense_manager.add_expense("🛒 Groceries", -10.0)
        assert "❌" in result
        assert "positive" in result.lower()

    def test_add_expense_zero_amount_rejected(self, expense_manager: ExpenseManager):
        """Test that zero amounts are rejected."""
        result = expense_manager.add_expense("🛒 Groceries", 0)
        assert "❌" in result

    def test_add_expense_decimal_precision(self, expense_manager: ExpenseManager):
        """Test decimal amounts are handled correctly."""
        expense_manager.add_expense("🛒 Groceries", 12.99)
        transactions = expense_manager.get_recent_transactions(1)
        assert transactions[0]['amount'] == 12.99

    def test_add_expense_large_amount(self, expense_manager: ExpenseManager):
        """Test large expense amounts."""
        result = expense_manager.add_expense("🏠 Housing", 2500.00, "rent")
        assert "$2500.00" in result

    def test_add_multiple_expenses(self, expense_manager: ExpenseManager):
        """Test adding multiple expenses."""
        expense_manager.add_expense("🛒 Groceries", 25.0)
        expense_manager.add_expense("🍽️ Dining Out", 35.0)
        expense_manager.add_expense("🚗 Transportation", 15.0)
        
        transactions = expense_manager.get_all_transactions()
        assert len(transactions) == 3


class TestAddIncome:
    """Tests for add_income functionality."""

    def test_add_income_basic(self, expense_manager: ExpenseManager):
        """Test adding basic income."""
        result = expense_manager.add_income("Salary", 3000.0)
        assert "💰" in result
        assert "$3000.00" in result
        assert "Salary" in result

    def test_add_income_with_note(self, expense_manager: ExpenseManager):
        """Test adding income with note."""
        result = expense_manager.add_income("Freelance", 500.0, "Web design project")
        assert "Web design project" in result

    def test_add_income_projected(self, expense_manager: ExpenseManager):
        """Test adding projected income."""
        result = expense_manager.add_income("Bonus", 1000.0, "Expected", is_projected=True)
        assert "projected" in result.lower()

    def test_add_income_negative_rejected(self, expense_manager: ExpenseManager):
        """Test that negative income is rejected."""
        result = expense_manager.add_income("Salary", -100.0)
        assert "❌" in result

    def test_add_income_zero_rejected(self, expense_manager: ExpenseManager):
        """Test that zero income is rejected."""
        result = expense_manager.add_income("Salary", 0)
        assert "❌" in result

    def test_income_appears_in_monthly_plan(self, expense_manager: ExpenseManager):
        """Test income is tracked in monthly plan."""
        expense_manager.add_income("Salary", 3000.0)
        now = datetime.now()
        plan = expense_manager.get_monthly_plan(now.year, now.month)
        assert plan['actual_income'].get('Salary') == 3000.0


class TestBudgetPlan:
    """Tests for budget planning functionality."""

    def test_set_budget_basic(self, expense_manager: ExpenseManager):
        """Test setting a basic budget."""
        now = datetime.now()
        result = expense_manager.set_budget(now.year, now.month, "🛒 Groceries", 500.0)
        assert "📋" in result
        assert "$500.00" in result

    def test_set_budget_updates_existing(self, expense_manager: ExpenseManager):
        """Test that setting budget overwrites existing."""
        now = datetime.now()
        expense_manager.set_budget(now.year, now.month, "🛒 Groceries", 500.0)
        expense_manager.set_budget(now.year, now.month, "🛒 Groceries", 600.0)
        
        plan = expense_manager.get_monthly_plan(now.year, now.month)
        assert plan['planned_budgets']["🛒 Groceries"] == 600.0

    def test_set_budget_negative_rejected(self, expense_manager: ExpenseManager):
        """Test that negative budget is rejected."""
        now = datetime.now()
        result = expense_manager.set_budget(now.year, now.month, "🛒 Groceries", -100.0)
        assert "❌" in result

    def test_set_budget_zero_allowed(self, expense_manager: ExpenseManager):
        """Test that zero budget is allowed (to clear a budget)."""
        now = datetime.now()
        result = expense_manager.set_budget(now.year, now.month, "🛒 Groceries", 0)
        # Zero should be allowed to effectively disable a budget category
        assert "📋" in result

    def test_set_projected_income_basic(self, expense_manager: ExpenseManager):
        """Test setting projected income."""
        now = datetime.now()
        result = expense_manager.set_projected_income(now.year, now.month, "Salary", 4000.0)
        assert "💵" in result
        assert "$4000.00" in result

    def test_set_projected_income_negative_rejected(self, expense_manager: ExpenseManager):
        """Test that negative projected income is rejected."""
        now = datetime.now()
        result = expense_manager.set_projected_income(now.year, now.month, "Salary", -100.0)
        assert "❌" in result

    def test_get_monthly_plan_complete(self, expense_manager: ExpenseManager):
        """Test getting complete monthly plan."""
        now = datetime.now()
        
        # Set up budget and income
        expense_manager.set_projected_income(now.year, now.month, "Salary", 4000.0)
        expense_manager.set_budget(now.year, now.month, "🛒 Groceries", 500.0)
        expense_manager.set_budget(now.year, now.month, "🍽️ Dining Out", 300.0)
        
        # Add actual transactions
        expense_manager.add_income("Salary", 4000.0)
        expense_manager.add_expense("🛒 Groceries", 150.0)
        
        plan = expense_manager.get_monthly_plan(now.year, now.month)
        
        assert plan['total_projected_income'] == 4000.0
        assert plan['total_actual_income'] == 4000.0
        assert plan['total_planned'] == 800.0
        assert plan['total_spent'] == 150.0
        assert plan['planned_budgets']['🛒 Groceries'] == 500.0
        assert plan['actual_spending']['🛒 Groceries'] == 150.0

    def test_budget_status_formatting(self, expense_manager: ExpenseManager):
        """Test budget status message formatting."""
        now = datetime.now()
        expense_manager.set_budget(now.year, now.month, "🛒 Groceries", 500.0)
        expense_manager.add_expense("🛒 Groceries", 400.0)
        
        status = expense_manager.get_budget_status()
        
        assert "Budget Status" in status
        assert "🛒 Groceries" in status
        assert "$400.00" in status
        assert "$500.00" in status


class TestSummaries:
    """Tests for summary functionality."""

    def test_get_summary_day_no_expenses(self, expense_manager: ExpenseManager):
        """Test day summary with no expenses."""
        summary, chart_data = expense_manager.get_summary("day")
        assert "$0.00" in summary
        assert chart_data == {}

    def test_get_summary_day_with_expenses(self, expense_manager: ExpenseManager):
        """Test day summary with expenses."""
        expense_manager.add_expense("🛒 Groceries", 50.0)
        expense_manager.add_expense("🍽️ Dining Out", 30.0)
        
        summary, chart_data = expense_manager.get_summary("day")
        
        assert "$80.00" in summary
        assert chart_data["🛒 Groceries"] == 50.0
        assert chart_data["🍽️ Dining Out"] == 30.0

    def test_get_summary_invalid_timeframe(self, expense_manager: ExpenseManager):
        """Test invalid timeframe handling."""
        summary, chart_data = expense_manager.get_summary("invalid")
        assert "Invalid" in summary

    def test_get_daily_breakdown_week(self, expense_manager: ExpenseManager):
        """Test weekly daily breakdown."""
        expense_manager.add_expense("🛒 Groceries", 25.0)
        breakdown = expense_manager.get_daily_breakdown("week")
        
        # Should have at least today's data
        assert len(breakdown) >= 1
        today_str = datetime.now().strftime('%Y-%m-%d')
        dates = [row[0] for row in breakdown]
        assert today_str in dates


class TestCategoryMatching:
    """Tests for category matching functionality."""

    def test_match_exact_alias(self, expense_manager: ExpenseManager):
        """Test exact alias matching."""
        assert expense_manager.match_category("groceries") == "🛒 Groceries"
        assert expense_manager.match_category("uber") == "🚗 Transportation"
        assert expense_manager.match_category("netflix") == "📱 Subscriptions"

    def test_match_partial_name(self, expense_manager: ExpenseManager):
        """Test partial category name matching."""
        assert expense_manager.match_category("groc") == "🛒 Groceries"

    def test_match_case_insensitive(self, expense_manager: ExpenseManager):
        """Test case insensitivity."""
        assert expense_manager.match_category("GROCERIES") == "🛒 Groceries"
        assert expense_manager.match_category("Uber") == "🚗 Transportation"

    def test_match_fuzzy(self, expense_manager: ExpenseManager):
        """Test fuzzy matching for typos."""
        # Should match close misspellings
        result = expense_manager.match_category("grocerys")
        assert result is not None

    def test_match_unknown_returns_none(self, expense_manager: ExpenseManager):
        """Test unknown categories return None."""
        assert expense_manager.match_category("xyzabc123") is None


class TestTransactionManagement:
    """Tests for transaction management."""

    def test_delete_last_expense(self, expense_manager: ExpenseManager):
        """Test deleting last expense."""
        expense_manager.add_expense("🛒 Groceries", 10.0)
        expense_manager.add_expense("🍽️ Dining Out", 20.0)
        
        result = expense_manager.delete_last()
        
        assert "Deleted" in result
        assert "$20.00" in result
        
        transactions = expense_manager.get_all_transactions()
        assert len(transactions) == 1

    def test_delete_last_no_expenses(self, expense_manager: ExpenseManager):
        """Test deleting when no expenses exist."""
        result = expense_manager.delete_last()
        assert "No expenses" in result

    def test_get_recent_transactions(self, expense_manager: ExpenseManager):
        """Test getting recent transactions."""
        for i in range(15):
            expense_manager.add_expense("🛒 Groceries", float(i + 1))
        
        recent = expense_manager.get_recent_transactions(10)
        assert len(recent) == 10
        # Most recent should be highest amount
        assert recent[0]['amount'] == 15.0

    def test_get_recent_transactions_with_receipt(self, expense_manager: ExpenseManager):
        """Test recent transactions include receipt info."""
        expense_manager.add_expense("🛒 Groceries", 50.0, "with receipt", "file_123")
        
        recent = expense_manager.get_recent_transactions(1)
        assert recent[0]['receipt'] == "file_123"


class TestUserSettings:
    """Tests for user settings functionality."""

    def test_register_user(self, expense_manager: ExpenseManager):
        """Test user registration."""
        chat_id = 12345
        expense_manager.register_user(chat_id)
        
        users = expense_manager.get_all_registered_users()
        assert chat_id in users

    def test_register_user_idempotent(self, expense_manager: ExpenseManager):
        """Test registering same user twice doesn't duplicate."""
        chat_id = 12345
        expense_manager.register_user(chat_id)
        expense_manager.register_user(chat_id)
        
        users = expense_manager.get_all_registered_users()
        assert users.count(chat_id) == 1

    def test_toggle_daily_report(self, expense_manager: ExpenseManager):
        """Test toggling daily report setting."""
        chat_id = 12345
        expense_manager.register_user(chat_id)
        
        # Default is enabled
        assert expense_manager.is_daily_report_enabled(chat_id) is True
        
        # Toggle off
        new_state = expense_manager.toggle_daily_report(chat_id)
        assert new_state is False
        assert expense_manager.is_daily_report_enabled(chat_id) is False
        
        # Toggle back on
        new_state = expense_manager.toggle_daily_report(chat_id)
        assert new_state is True

    def test_disabled_user_not_in_report_list(self, expense_manager: ExpenseManager):
        """Test users with disabled reports aren't in report list."""
        chat_id = 12345
        expense_manager.register_user(chat_id)
        expense_manager.toggle_daily_report(chat_id)  # Disable
        
        users = expense_manager.get_all_registered_users()
        assert chat_id not in users


class TestDataManagement:
    """Tests for data management functionality."""

    def test_clear_all_data(self, expense_manager: ExpenseManager):
        """Test clearing all data."""
        # Add various data
        expense_manager.add_expense("🛒 Groceries", 50.0)
        expense_manager.add_income("Salary", 3000.0)
        expense_manager.register_user(12345)
        now = datetime.now()
        expense_manager.set_budget(now.year, now.month, "🛒 Groceries", 500.0)
        expense_manager.set_projected_income(now.year, now.month, "Salary", 4000.0)
        
        result = expense_manager.clear_all_data()
        
        assert "cleared" in result.lower()
        assert expense_manager.get_all_transactions() == []
        assert expense_manager.get_all_registered_users() == []

    def test_export_to_csv(self, expense_manager: ExpenseManager):
        """Test CSV export."""
        expense_manager.add_expense("🛒 Groceries", 50.0, "test note")
        expense_manager.add_expense("🍽️ Dining Out", 30.0)
        
        filename = expense_manager.export_to_csv()
        
        assert filename is not None
        assert filename.endswith('.csv')
        assert os.path.exists(filename)
        
        # Verify content
        with open(filename, 'r') as f:
            content = f.read()
            assert "🛒 Groceries" in content
            assert "50.0" in content
        
        os.remove(filename)

    def test_export_to_csv_no_data(self, expense_manager: ExpenseManager):
        """Test CSV export with no data."""
        filename = expense_manager.export_to_csv()
        assert filename is None


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_very_long_note(self, expense_manager: ExpenseManager):
        """Test handling very long notes."""
        long_note = "A" * 1000
        result = expense_manager.add_expense("🛒 Groceries", 10.0, long_note)
        assert "✅" in result
        
        transactions = expense_manager.get_recent_transactions(1)
        assert len(transactions[0]['note']) == 1000

    def test_special_characters_in_note(self, expense_manager: ExpenseManager):
        """Test special characters in notes."""
        special_note = "Test with 'quotes' and \"double quotes\" and emojis 🎉"
        expense_manager.add_expense("🛒 Groceries", 10.0, special_note)
        
        transactions = expense_manager.get_recent_transactions(1)
        assert transactions[0]['note'] == special_note

    def test_unicode_in_source(self, expense_manager: ExpenseManager):
        """Test unicode in income source."""
        result = expense_manager.add_income("工资 Salary", 3000.0)
        assert "✅" in result or "💰" in result

    def test_float_precision_edge(self, expense_manager: ExpenseManager):
        """Test float precision doesn't cause issues."""
        expense_manager.add_expense("🛒 Groceries", 0.1)
        expense_manager.add_expense("🛒 Groceries", 0.2)
        
        summary, chart_data = expense_manager.get_summary("day")
        total = chart_data.get("🛒 Groceries", 0)
        assert abs(total - 0.3) < 0.01  # Allow small float error
