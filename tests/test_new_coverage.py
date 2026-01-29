"""New tests covering gaps identified in the code review.

Covers:
- copy_budget_from_previous_month (both success and no-data paths)
- Deletion confirmation flow callbacks
- Scheduled reports (send_daily_report, send_monthly_report)
- Guided income callback flow (inc_src_*, inc_amt_*, inc_skip_note)
- Toggle daily and settings callbacks
- Onboarding guard (_require_onboarding)
- Export bot handler
"""
import os
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from bot import BudgetBot, KeyboardFactory
from database import ExpenseManager

from conftest import (
    DummyUpdate,
    DummyCallbackQuery,
    DummyContext,
    setup_completed_onboarding,
)


# ============== copy_budget_from_previous_month ==============


class TestCopyBudgetFromPreviousMonth:
    """Tests for the budget passover feature."""

    def test_copy_success_with_budgets_only(self, expense_manager: ExpenseManager):
        """Copy budgets when previous month has budgets but no projected income."""
        now = datetime.now()
        prev_month = now.month - 1 if now.month > 1 else 12
        prev_year = now.year if now.month > 1 else now.year - 1

        expense_manager.set_budget(prev_year, prev_month, "🛒 Groceries", 300.0)
        expense_manager.set_budget(prev_year, prev_month, "🍽️ Dining Out", 150.0)

        result = expense_manager.copy_budget_from_previous_month(now.year, now.month)

        assert "✅ Copied" in result
        assert "2 category budgets" in result

        plan = expense_manager.get_monthly_plan(now.year, now.month)
        assert plan['planned_budgets'].get("🛒 Groceries") == 300.0
        assert plan['planned_budgets'].get("🍽️ Dining Out") == 150.0

    def test_copy_success_with_budgets_and_income(self, expense_manager: ExpenseManager):
        """Copy budgets and projected income from previous month."""
        now = datetime.now()
        prev_month = now.month - 1 if now.month > 1 else 12
        prev_year = now.year if now.month > 1 else now.year - 1

        expense_manager.set_budget(prev_year, prev_month, "🛒 Groceries", 500.0)
        expense_manager.set_projected_income(prev_year, prev_month, "Salary", 4000.0)

        result = expense_manager.copy_budget_from_previous_month(now.year, now.month)

        assert "✅ Copied" in result
        assert "1 category budgets" in result
        assert "1 projected income sources" in result

        plan = expense_manager.get_monthly_plan(now.year, now.month)
        assert plan['planned_budgets'].get("🛒 Groceries") == 500.0
        assert plan['total_projected_income'] == 4000.0

    def test_copy_no_previous_month_data(self, expense_manager: ExpenseManager):
        """Return error when previous month has no budget data."""
        now = datetime.now()
        result = expense_manager.copy_budget_from_previous_month(now.year, now.month)

        assert "❌" in result
        assert "No budget plans found" in result

    def test_copy_overwrites_existing(self, expense_manager: ExpenseManager):
        """Copying overwrites existing current month budgets."""
        now = datetime.now()
        prev_month = now.month - 1 if now.month > 1 else 12
        prev_year = now.year if now.month > 1 else now.year - 1

        # Set up previous month
        expense_manager.set_budget(prev_year, prev_month, "🛒 Groceries", 500.0)

        # Set up current month with different value
        expense_manager.set_budget(now.year, now.month, "🛒 Groceries", 200.0)

        # Copy should overwrite
        expense_manager.copy_budget_from_previous_month(now.year, now.month)

        plan = expense_manager.get_monthly_plan(now.year, now.month)
        assert plan['planned_budgets'].get("🛒 Groceries") == 500.0

    def test_copy_defaults_to_current_month(self, expense_manager: ExpenseManager):
        """Defaults to current year/month when not specified."""
        now = datetime.now()
        prev_month = now.month - 1 if now.month > 1 else 12
        prev_year = now.year if now.month > 1 else now.year - 1

        expense_manager.set_budget(prev_year, prev_month, "🛒 Groceries", 100.0)

        result = expense_manager.copy_budget_from_previous_month()
        assert "✅ Copied" in result

    def test_copy_january_wraps_to_december(self, expense_manager: ExpenseManager):
        """Copying in January pulls from December of the previous year."""
        expense_manager.set_budget(2025, 12, "🛒 Groceries", 400.0)

        result = expense_manager.copy_budget_from_previous_month(2026, 1)

        assert "✅ Copied" in result
        plan = expense_manager.get_monthly_plan(2026, 1)
        assert plan['planned_budgets'].get("🛒 Groceries") == 400.0

    @pytest.mark.asyncio
    async def test_passover_callback(self, bot_instance: BudgetBot):
        """Test passover_budget callback triggers the copy."""
        manager = setup_completed_onboarding(bot_instance)
        now = datetime.now()
        prev_month = now.month - 1 if now.month > 1 else 12
        prev_year = now.year if now.month > 1 else now.year - 1
        manager.set_budget(prev_year, prev_month, "🛒 Groceries", 250.0)

        update = DummyUpdate()
        context = DummyContext()
        query = DummyCallbackQuery("passover_budget")
        update.callback_query = query

        await bot_instance.button_callback(update, context)

        response = query.message.texts[0]['text']
        assert "✅ Copied" in response


# ============== Deletion Confirmation Flow ==============


class TestDeletionConfirmationFlow:
    """Tests for the delete data callbacks."""

    @pytest.mark.asyncio
    async def test_menu_delete_callback(self, bot_instance: BudgetBot):
        """Test menu_delete shows delete options."""
        update = DummyUpdate()
        context = DummyContext()
        query = DummyCallbackQuery("menu_delete")
        update.callback_query = query

        await bot_instance.button_callback(update, context)

        response = query.message.texts[0]['text']
        assert "Delete Data" in response

    @pytest.mark.asyncio
    async def test_delete_expenses_prompt(self, bot_instance: BudgetBot):
        """Test delete_expenses shows confirmation prompt."""
        update = DummyUpdate()
        context = DummyContext()
        query = DummyCallbackQuery("delete_expenses")
        update.callback_query = query

        await bot_instance.button_callback(update, context)

        response = query.message.texts[0]['text']
        assert "Delete All Expenses" in response

    @pytest.mark.asyncio
    async def test_delete_income_prompt(self, bot_instance: BudgetBot):
        """Test delete_income shows confirmation prompt."""
        update = DummyUpdate()
        context = DummyContext()
        query = DummyCallbackQuery("delete_income")
        update.callback_query = query

        await bot_instance.button_callback(update, context)

        response = query.message.texts[0]['text']
        assert "Delete All Income" in response

    @pytest.mark.asyncio
    async def test_delete_budgets_prompt(self, bot_instance: BudgetBot):
        """Test delete_budgets shows confirmation prompt."""
        update = DummyUpdate()
        context = DummyContext()
        query = DummyCallbackQuery("delete_budgets")
        update.callback_query = query

        await bot_instance.button_callback(update, context)

        response = query.message.texts[0]['text']
        assert "Delete All Budgets" in response

    @pytest.mark.asyncio
    async def test_delete_last_5_prompt(self, bot_instance: BudgetBot):
        """Test delete_last_5 shows confirmation."""
        update = DummyUpdate()
        context = DummyContext()
        query = DummyCallbackQuery("delete_last_5")
        update.callback_query = query

        await bot_instance.button_callback(update, context)

        response = query.message.texts[0]['text']
        assert "Last 5" in response

    @pytest.mark.asyncio
    async def test_delete_last_10_prompt(self, bot_instance: BudgetBot):
        """Test delete_last_10 shows confirmation."""
        update = DummyUpdate()
        context = DummyContext()
        query = DummyCallbackQuery("delete_last_10")
        update.callback_query = query

        await bot_instance.button_callback(update, context)

        response = query.message.texts[0]['text']
        assert "Last 10" in response

    @pytest.mark.asyncio
    async def test_delete_all_confirm_prompt(self, bot_instance: BudgetBot):
        """Test delete_all_confirm shows nuclear option warning."""
        update = DummyUpdate()
        context = DummyContext()
        query = DummyCallbackQuery("delete_all_confirm")
        update.callback_query = query

        await bot_instance.button_callback(update, context)

        response = query.message.texts[0]['text']
        assert "DELETE EVERYTHING" in response
        assert "cannot be undone" in response

    @pytest.mark.asyncio
    async def test_confirm_expenses_deletes(self, bot_instance: BudgetBot):
        """Test confirm_expenses actually deletes expenses."""
        manager = setup_completed_onboarding(bot_instance)
        manager.add_expense("🛒 Groceries", 50.0)
        manager.add_expense("🍽️ Dining Out", 30.0)

        update = DummyUpdate()
        context = DummyContext()
        query = DummyCallbackQuery("confirm_expenses")
        update.callback_query = query

        await bot_instance.button_callback(update, context)

        response = query.message.texts[0]['text']
        assert "Deleted" in response
        assert "2" in response
        assert manager.get_all_transactions() == []

    @pytest.mark.asyncio
    async def test_confirm_income_deletes(self, bot_instance: BudgetBot):
        """Test confirm_income actually deletes income."""
        manager = setup_completed_onboarding(bot_instance)
        manager.add_income("Salary", 3000.0)

        update = DummyUpdate()
        context = DummyContext()
        query = DummyCallbackQuery("confirm_income")
        update.callback_query = query

        await bot_instance.button_callback(update, context)

        response = query.message.texts[0]['text']
        assert "Deleted" in response
        assert "1" in response

    @pytest.mark.asyncio
    async def test_confirm_budgets_deletes(self, bot_instance: BudgetBot):
        """Test confirm_budgets actually deletes budgets."""
        manager = setup_completed_onboarding(bot_instance)
        now = datetime.now()
        manager.set_budget(now.year, now.month, "🛒 Groceries", 500.0)

        update = DummyUpdate()
        context = DummyContext()
        query = DummyCallbackQuery("confirm_budgets")
        update.callback_query = query

        await bot_instance.button_callback(update, context)

        response = query.message.texts[0]['text']
        assert "Deleted" in response

    @pytest.mark.asyncio
    async def test_confirm_last_5_deletes(self, bot_instance: BudgetBot):
        """Test confirm_last_5 actually deletes last 5."""
        manager = setup_completed_onboarding(bot_instance)
        for i in range(8):
            manager.add_expense("🛒 Groceries", float(i + 1))

        update = DummyUpdate()
        context = DummyContext()
        query = DummyCallbackQuery("confirm_last_5")
        update.callback_query = query

        await bot_instance.button_callback(update, context)

        response = query.message.texts[0]['text']
        assert "Deleted" in response
        assert "5" in response
        assert len(manager.get_all_transactions()) == 3

    @pytest.mark.asyncio
    async def test_confirm_last_10_deletes(self, bot_instance: BudgetBot):
        """Test confirm_last_10 deletes up to 10."""
        manager = setup_completed_onboarding(bot_instance)
        for i in range(5):
            manager.add_expense("🛒 Groceries", float(i + 1))

        update = DummyUpdate()
        context = DummyContext()
        query = DummyCallbackQuery("confirm_last_10")
        update.callback_query = query

        await bot_instance.button_callback(update, context)

        response = query.message.texts[0]['text']
        assert "Deleted" in response
        assert manager.get_all_transactions() == []

    @pytest.mark.asyncio
    async def test_confirm_all_deletes_everything(self, bot_instance: BudgetBot):
        """Test confirm_all deletes all data."""
        manager = setup_completed_onboarding(bot_instance)
        manager.add_expense("🛒 Groceries", 50.0)
        manager.add_income("Salary", 3000.0)

        update = DummyUpdate()
        context = DummyContext()
        query = DummyCallbackQuery("confirm_all")
        update.callback_query = query

        await bot_instance.button_callback(update, context)

        response = query.message.texts[0]['text']
        assert "cleared" in response.lower()


# ============== Scheduled Reports ==============


class TestScheduledReports:
    """Tests for send_daily_report and send_monthly_report."""

    @pytest.mark.asyncio
    async def test_send_daily_report_with_data(self, bot_instance: BudgetBot):
        """Test daily report sends to users with reports enabled."""
        manager = setup_completed_onboarding(bot_instance)
        manager.add_expense("🛒 Groceries", 50.0)

        context = DummyContext()
        await bot_instance.send_daily_report(context)

        # Should have sent a message to the registered user
        assert context.bot.send_message.called

    @pytest.mark.asyncio
    async def test_send_daily_report_disabled_user(self, bot_instance: BudgetBot):
        """Test daily report skips users who disabled it."""
        manager = setup_completed_onboarding(bot_instance)
        manager.toggle_daily_report(12345)  # Disable

        context = DummyContext()
        await bot_instance.send_daily_report(context)

        # Should NOT have sent a message
        assert not context.bot.send_message.called

    @pytest.mark.asyncio
    async def test_send_monthly_report_with_data(self, bot_instance: BudgetBot):
        """Test monthly report sends budget status."""
        manager = setup_completed_onboarding(bot_instance)
        now = datetime.now()
        manager.set_budget(now.year, now.month, "🛒 Groceries", 500.0)

        context = DummyContext()
        await bot_instance.send_monthly_report(context)

        assert context.bot.send_message.called

    @pytest.mark.asyncio
    async def test_send_daily_report_no_users(self, bot_instance: BudgetBot):
        """Test daily report gracefully handles no users."""
        context = DummyContext()
        # No users registered
        await bot_instance.send_daily_report(context)
        # Should not fail
        assert not context.bot.send_message.called


# ============== Income Callback Flow ==============


class TestIncomeCallbackFlow:
    """Tests for the guided income entry via callbacks."""

    @pytest.mark.asyncio
    async def test_menu_income_shows_source_keyboard(self, bot_instance: BudgetBot):
        """Test menu_income shows the income source selection."""
        update = DummyUpdate()
        context = DummyContext()
        query = DummyCallbackQuery("menu_income")
        update.callback_query = query

        await bot_instance.button_callback(update, context)

        response = query.message.texts[0]['text']
        assert "Add Income" in response
        assert context.user_data.get('action') == 'add_income'

    @pytest.mark.asyncio
    async def test_income_source_selection(self, bot_instance: BudgetBot):
        """Test selecting a preset income source."""
        update = DummyUpdate()
        context = DummyContext()
        context.user_data['action'] = 'add_income'

        query = DummyCallbackQuery("inc_src_Salary")
        update.callback_query = query

        await bot_instance.button_callback(update, context)

        assert context.user_data.get('income_source') == 'Salary'
        response = query.message.texts[0]['text']
        assert "Salary" in response

    @pytest.mark.asyncio
    async def test_income_source_custom(self, bot_instance: BudgetBot):
        """Test selecting custom income source."""
        update = DummyUpdate()
        context = DummyContext()
        context.user_data['action'] = 'add_income'

        query = DummyCallbackQuery("inc_src_custom")
        update.callback_query = query

        await bot_instance.button_callback(update, context)

        assert context.user_data.get('awaiting') == 'income_source'

    @pytest.mark.asyncio
    async def test_income_amount_selection(self, bot_instance: BudgetBot):
        """Test selecting a preset income amount."""
        update = DummyUpdate()
        context = DummyContext()
        context.user_data['action'] = 'add_income'
        context.user_data['income_source'] = 'Salary'

        query = DummyCallbackQuery("inc_amt_3000")
        update.callback_query = query

        await bot_instance.button_callback(update, context)

        assert context.user_data.get('income_amount') == 3000.0
        assert context.user_data.get('awaiting') == 'income_note'

    @pytest.mark.asyncio
    async def test_income_amount_custom(self, bot_instance: BudgetBot):
        """Test selecting custom income amount."""
        update = DummyUpdate()
        context = DummyContext()
        context.user_data['action'] = 'add_income'
        context.user_data['income_source'] = 'Salary'

        query = DummyCallbackQuery("inc_amt_custom")
        update.callback_query = query

        await bot_instance.button_callback(update, context)

        assert context.user_data.get('awaiting') == 'income_amount'

    @pytest.mark.asyncio
    async def test_income_amount_session_expired(self, bot_instance: BudgetBot):
        """Test income amount callback when session expired (no source)."""
        update = DummyUpdate()
        context = DummyContext()
        # No income_source set

        query = DummyCallbackQuery("inc_amt_1000")
        update.callback_query = query

        await bot_instance.button_callback(update, context)

        response = query.message.texts[0]['text']
        assert "expired" in response.lower() or "Session" in response

    @pytest.mark.asyncio
    async def test_income_skip_note_saves(self, bot_instance: BudgetBot):
        """Test skipping note saves the income entry."""
        manager = setup_completed_onboarding(bot_instance)

        update = DummyUpdate()
        context = DummyContext()
        context.user_data['income_source'] = 'Freelance'
        context.user_data['income_amount'] = 500.0

        query = DummyCallbackQuery("inc_skip_note")
        update.callback_query = query

        await bot_instance.button_callback(update, context)

        response = query.message.texts[0]['text']
        assert "💰" in response
        assert "$500.00" in response
        # User data should be cleared
        assert context.user_data == {}

    @pytest.mark.asyncio
    async def test_income_skip_note_session_expired(self, bot_instance: BudgetBot):
        """Test skipping note when session expired."""
        update = DummyUpdate()
        context = DummyContext()
        # Missing income_source and income_amount

        query = DummyCallbackQuery("inc_skip_note")
        update.callback_query = query

        await bot_instance.button_callback(update, context)

        response = query.message.texts[0]['text']
        assert "expired" in response.lower() or "Session" in response

    @pytest.mark.asyncio
    async def test_guided_income_custom_source_text(self, bot_instance: BudgetBot):
        """Test entering custom income source via text."""
        setup_completed_onboarding(bot_instance)

        update = DummyUpdate()
        context = DummyContext()
        context.user_data['action'] = 'add_income'
        context.user_data['awaiting'] = 'income_source'
        update.message.text = "Side Hustle"

        await bot_instance.handle_text(update, context)

        assert context.user_data.get('income_source') == 'Side Hustle'

    @pytest.mark.asyncio
    async def test_guided_income_custom_amount_text(self, bot_instance: BudgetBot):
        """Test entering custom income amount via text."""
        setup_completed_onboarding(bot_instance)

        update = DummyUpdate()
        context = DummyContext()
        context.user_data['action'] = 'add_income'
        context.user_data['income_source'] = 'Freelance'
        context.user_data['awaiting'] = 'income_amount'
        update.message.text = "750"

        await bot_instance.handle_text(update, context)

        assert context.user_data.get('income_amount') == 750.0

    @pytest.mark.asyncio
    async def test_guided_income_note_text(self, bot_instance: BudgetBot):
        """Test entering income note via text."""
        manager = setup_completed_onboarding(bot_instance)

        update = DummyUpdate()
        context = DummyContext()
        context.user_data['action'] = 'add_income'
        context.user_data['income_source'] = 'Freelance'
        context.user_data['income_amount'] = 750.0
        context.user_data['awaiting'] = 'income_note'
        update.message.text = "January project"

        await bot_instance.handle_text(update, context)

        response = update.message.texts[0]['text']
        assert "💰" in response
        assert "$750.00" in response


# ============== Settings / Toggle Callbacks ==============


class TestSettingsCallbacks:
    """Tests for settings and toggle callbacks."""

    @pytest.mark.asyncio
    async def test_menu_settings_callback(self, bot_instance: BudgetBot):
        """Test menu_settings shows settings with current state."""
        manager = setup_completed_onboarding(bot_instance)

        update = DummyUpdate()
        context = DummyContext()
        query = DummyCallbackQuery("menu_settings")
        update.callback_query = query

        await bot_instance.button_callback(update, context)

        response = query.message.texts[0]['text']
        assert "Settings" in response

    @pytest.mark.asyncio
    async def test_toggle_daily_callback(self, bot_instance: BudgetBot):
        """Test toggle_daily callback toggles the setting."""
        manager = setup_completed_onboarding(bot_instance)
        assert manager.is_daily_report_enabled(12345) is True

        update = DummyUpdate()
        context = DummyContext()
        query = DummyCallbackQuery("toggle_daily")
        update.callback_query = query

        await bot_instance.button_callback(update, context)

        response = query.message.texts[0]['text']
        assert "disabled" in response
        assert manager.is_daily_report_enabled(12345) is False

    @pytest.mark.asyncio
    async def test_toggle_daily_twice(self, bot_instance: BudgetBot):
        """Test toggling daily report on and off."""
        manager = setup_completed_onboarding(bot_instance)

        # Toggle off
        update1 = DummyUpdate()
        context = DummyContext()
        query1 = DummyCallbackQuery("toggle_daily")
        update1.callback_query = query1
        await bot_instance.button_callback(update1, context)
        assert manager.is_daily_report_enabled(12345) is False

        # Toggle back on
        update2 = DummyUpdate()
        query2 = DummyCallbackQuery("toggle_daily")
        update2.callback_query = query2
        await bot_instance.button_callback(update2, context)
        assert manager.is_daily_report_enabled(12345) is True


# ============== Onboarding Guard ==============


class TestOnboardingGuard:
    """Tests verifying that un-onboarded users are blocked from commands."""

    @pytest.mark.asyncio
    async def test_help_blocked_without_onboarding(self, bot_instance: BudgetBot):
        """Test /help is blocked for un-onboarded users."""
        # Register user but do NOT complete onboarding
        manager = bot_instance._get_manager("test_user")
        manager.register_user(12345)

        update = DummyUpdate()
        context = DummyContext()

        await bot_instance.help(update, context)

        response = update.message.texts[0]['text']
        assert "complete the setup" in response.lower() or "onboarding" in response.lower() or "/start" in response

    @pytest.mark.asyncio
    async def test_today_blocked_without_onboarding(self, bot_instance: BudgetBot):
        """Test /today is blocked for un-onboarded users."""
        manager = bot_instance._get_manager("test_user")
        manager.register_user(12345)

        update = DummyUpdate()
        context = DummyContext()

        await bot_instance.today(update, context)

        response = update.message.texts[0]['text']
        assert "/start" in response

    @pytest.mark.asyncio
    async def test_week_blocked_without_onboarding(self, bot_instance: BudgetBot):
        """Test /week is blocked for un-onboarded users."""
        manager = bot_instance._get_manager("test_user")
        manager.register_user(12345)

        update = DummyUpdate()
        context = DummyContext()

        await bot_instance.week(update, context)

        response = update.message.texts[0]['text']
        assert "/start" in response

    @pytest.mark.asyncio
    async def test_month_blocked_without_onboarding(self, bot_instance: BudgetBot):
        """Test /month is blocked for un-onboarded users."""
        manager = bot_instance._get_manager("test_user")
        manager.register_user(12345)

        update = DummyUpdate()
        context = DummyContext()

        await bot_instance.month(update, context)

        response = update.message.texts[0]['text']
        assert "/start" in response

    @pytest.mark.asyncio
    async def test_budget_blocked_without_onboarding(self, bot_instance: BudgetBot):
        """Test /budget is blocked for un-onboarded users."""
        manager = bot_instance._get_manager("test_user")
        manager.register_user(12345)

        update = DummyUpdate()
        context = DummyContext()

        await bot_instance.budget(update, context)

        response = update.message.texts[0]['text']
        assert "/start" in response

    @pytest.mark.asyncio
    async def test_settings_blocked_without_onboarding(self, bot_instance: BudgetBot):
        """Test /settings is blocked for un-onboarded users."""
        manager = bot_instance._get_manager("test_user")
        manager.register_user(12345)

        update = DummyUpdate()
        context = DummyContext()

        await bot_instance.settings(update, context)

        response = update.message.texts[0]['text']
        assert "/start" in response

    @pytest.mark.asyncio
    async def test_text_input_blocked_without_onboarding(self, bot_instance: BudgetBot):
        """Test free-form text input is blocked for un-onboarded users."""
        manager = bot_instance._get_manager("test_user")
        manager.register_user(12345)

        update = DummyUpdate()
        context = DummyContext()
        update.message.text = "groceries 25 milk"

        await bot_instance.handle_text(update, context)

        response = update.message.texts[0]['text']
        assert "/start" in response

    @pytest.mark.asyncio
    async def test_menu_button_blocked_without_onboarding(self, bot_instance: BudgetBot):
        """Test menu button press is blocked for un-onboarded users."""
        manager = bot_instance._get_manager("test_user")
        manager.register_user(12345)

        update = DummyUpdate()
        context = DummyContext()
        update.message.text = "📱 Menu"

        await bot_instance.handle_text(update, context)

        response = update.message.texts[0]['text']
        assert "/start" in response


# ============== Export Bot Handler ==============


class TestExportHandler:
    """Tests for the /export bot handler."""

    @pytest.mark.asyncio
    async def test_export_with_data(self, bot_instance: BudgetBot):
        """Test export creates and sends CSV file."""
        manager = setup_completed_onboarding(bot_instance)
        manager.add_expense("🛒 Groceries", 50.0, "test")

        update = DummyUpdate()
        context = DummyContext()

        await bot_instance.export(update, context)

        # Should have sent a document
        assert context.bot.send_document.called

    @pytest.mark.asyncio
    async def test_export_no_data(self, bot_instance: BudgetBot):
        """Test export with no expenses sends error message."""
        setup_completed_onboarding(bot_instance)

        update = DummyUpdate()
        context = DummyContext()

        await bot_instance.export(update, context)

        # Should have sent error message
        assert context.bot.send_message.called
        call_args = context.bot.send_message.call_args
        assert "No expenses" in call_args[1].get('text', '') or "No expenses" in str(call_args)
