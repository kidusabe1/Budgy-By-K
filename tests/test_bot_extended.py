"""Comprehensive tests for bot components and flows."""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from bot import (
    BudgetBot, 
    BotConfig, 
    ExpenseParser, 
    KeyboardFactory, 
    VisualizationService
)
from database import ExpenseManager


# ============== Test Fixtures ==============

@pytest.fixture()
def expense_manager(tmp_path):
    """Create a fresh ExpenseManager with temp database."""
    db_path = tmp_path / "test_bot.db"
    return ExpenseManager(db_path=str(db_path))


@pytest.fixture()
def keyboards(expense_manager):
    """Create KeyboardFactory instance."""
    return KeyboardFactory(expense_manager.CATEGORIES)


@pytest.fixture()
def bot_instance(expense_manager, keyboards):
    """Create BudgetBot instance."""
    config = BotConfig(token="123:TEST")
    viz = VisualizationService()
    return BudgetBot(expense_manager, config, viz, keyboards)


class DummyMessage:
    """Mock message object for testing."""
    def __init__(self):
        self.texts = []
        self.photos = []
        self.documents = []
        self.chat = MagicMock()
        self.chat.id = 12345

    async def reply_text(self, text, **kwargs):
        self.texts.append({"text": text, "kwargs": kwargs})
        return MagicMock()

    async def reply_photo(self, photo=None, caption=None, **kwargs):
        self.photos.append({"photo": photo, "caption": caption, "kwargs": kwargs})
        return MagicMock()

    async def reply_document(self, document=None, filename=None, caption=None, **kwargs):
        self.documents.append({"document": document, "filename": filename, "caption": caption})
        return MagicMock()


class DummyChat:
    """Mock chat object."""
    def __init__(self, chat_id=12345):
        self.id = chat_id


class DummyUpdate:
    """Mock update object for testing."""
    def __init__(self, chat_id=12345):
        self.message = DummyMessage()
        self.effective_chat = DummyChat(chat_id)
        self.callback_query = None


class DummyCallbackQuery:
    """Mock callback query object."""
    def __init__(self, data, chat_id=12345):
        self.data = data
        self.message = DummyMessage()
        self.message.chat_id = chat_id

    async def answer(self):
        pass

    async def edit_message_text(self, text, **kwargs):
        self.message.texts.append({"text": text, "kwargs": kwargs})


class DummyContext:
    """Mock context object for testing."""
    def __init__(self):
        self.user_data = {}
        self.bot = MagicMock()
        self.bot.send_message = AsyncMock()
        self.bot.send_photo = AsyncMock()
        self.bot.send_document = AsyncMock()


# ============== ExpenseParser Tests ==============

class TestExpenseParser:
    """Tests for ExpenseParser class."""

    def test_parse_expense_basic(self):
        """Test basic expense parsing."""
        category, amount, note = ExpenseParser.parse_expense("groceries 25.50")
        assert category == "groceries"
        assert amount == 25.50
        assert note == ""

    def test_parse_expense_with_note(self):
        """Test expense parsing with note."""
        category, amount, note = ExpenseParser.parse_expense("dining 45.00 anniversary dinner")
        assert category == "dining"
        assert amount == 45.00
        assert note == "anniversary dinner"

    def test_parse_expense_with_dollar_sign(self):
        """Test parsing amount with dollar sign."""
        category, amount, note = ExpenseParser.parse_expense("uber $15.00")
        assert amount == 15.00

    def test_parse_expense_with_comma(self):
        """Test parsing amount with comma separator."""
        category, amount, note = ExpenseParser.parse_expense("rent 1,500")
        assert amount == 1500.0

    def test_parse_expense_invalid_format(self):
        """Test invalid format raises error."""
        with pytest.raises(ValueError) as exc_info:
            ExpenseParser.parse_expense("groceries")
        assert "Format" in str(exc_info.value)

    def test_parse_expense_invalid_amount(self):
        """Test invalid amount raises error."""
        with pytest.raises(ValueError) as exc_info:
            ExpenseParser.parse_expense("groceries abc")
        assert "Invalid amount" in str(exc_info.value)

    def test_parse_income_basic(self):
        """Test basic income parsing."""
        source, amount, note = ExpenseParser.parse_income("Salary 3000")
        assert source == "Salary"
        assert amount == 3000.0
        assert note == ""

    def test_parse_income_with_note(self):
        """Test income parsing with note."""
        source, amount, note = ExpenseParser.parse_income("Freelance 500 Web project")
        assert source == "Freelance"
        assert amount == 500.0
        assert note == "Web project"

    def test_parse_income_invalid_format(self):
        """Test invalid income format."""
        with pytest.raises(ValueError):
            ExpenseParser.parse_income("Salary")


# ============== KeyboardFactory Tests ==============

class TestKeyboardFactory:
    """Tests for KeyboardFactory class."""

    def test_main_menu_structure(self, keyboards):
        """Test main menu has expected buttons."""
        menu = keyboards.main_menu()
        assert menu is not None
        
        # Flatten all buttons
        all_buttons = [btn for row in menu.inline_keyboard for btn in row]
        button_texts = [btn.text for btn in all_buttons]
        
        assert "➕ Add Expense" in button_texts
        assert "💰 Add Income" in button_texts
        assert "📅 Today" in button_texts
        assert "📊 Week" in button_texts

    def test_categories_keyboard_structure(self, keyboards):
        """Test categories keyboard has all categories."""
        cat_kb = keyboards.categories_keyboard()
        all_buttons = [btn for row in cat_kb.inline_keyboard for btn in row]
        
        # Should have all categories plus cancel button
        assert len(all_buttons) == len(keyboards.categories) + 1
        
        # Check cancel button exists
        cancel_buttons = [b for b in all_buttons if b.callback_data == "cancel"]
        assert len(cancel_buttons) == 1

    def test_quick_amount_keyboard(self, keyboards):
        """Test quick amount keyboard."""
        amt_kb = KeyboardFactory.quick_amount_keyboard()
        all_buttons = [btn for row in amt_kb.inline_keyboard for btn in row]
        button_data = [btn.callback_data for btn in all_buttons]
        
        assert "amt_5" in button_data
        assert "amt_10" in button_data
        assert "amt_50" in button_data
        assert "amt_100" in button_data
        assert "amt_custom" in button_data
        assert "cancel" in button_data

    def test_settings_keyboard_enabled(self, keyboards):
        """Test settings keyboard when daily report enabled."""
        settings_kb = KeyboardFactory.settings_keyboard(daily_enabled=True)
        all_buttons = [btn for row in settings_kb.inline_keyboard for btn in row]
        
        daily_btn = [b for b in all_buttons if "Daily Report" in b.text][0]
        assert "ON" in daily_btn.text

    def test_settings_keyboard_disabled(self, keyboards):
        """Test settings keyboard when daily report disabled."""
        settings_kb = KeyboardFactory.settings_keyboard(daily_enabled=False)
        all_buttons = [btn for row in settings_kb.inline_keyboard for btn in row]
        
        daily_btn = [b for b in all_buttons if "Daily Report" in b.text][0]
        assert "OFF" in daily_btn.text


# ============== VisualizationService Tests ==============

class TestVisualizationService:
    """Tests for VisualizationService class."""

    def test_pie_chart_empty_data(self):
        """Test pie chart with empty data returns None."""
        viz = VisualizationService()
        result = viz.pie_chart({}, "Test")
        assert result is None

    def test_pie_chart_with_data(self):
        """Test pie chart generation with data."""
        viz = VisualizationService()
        data = {"🛒 Groceries": 100.0, "🍽️ Dining Out": 50.0}
        result = viz.pie_chart(data, "Test Chart")
        
        assert result is not None
        # Check it's a BytesIO object with PNG data
        result.seek(0)
        header = result.read(8)
        # PNG magic bytes
        assert header[:4] == b'\x89PNG'

    def test_bar_chart_empty_data(self):
        """Test bar chart with empty data returns None."""
        viz = VisualizationService()
        result = viz.bar_chart([], "Test")
        assert result is None

    def test_bar_chart_with_data(self):
        """Test bar chart generation."""
        viz = VisualizationService()
        data = [("2026-01-25", 50.0), ("2026-01-26", 75.0), ("2026-01-27", 30.0)]
        result = viz.bar_chart(data, "Daily Spending")
        
        assert result is not None
        result.seek(0)
        header = result.read(4)
        assert header == b'\x89PNG'

    def test_budget_chart_generation(self, expense_manager):
        """Test budget chart generation."""
        now = datetime.now()
        expense_manager.set_budget(now.year, now.month, "🛒 Groceries", 500.0)
        expense_manager.add_expense("🛒 Groceries", 200.0)
        expense_manager.set_projected_income(now.year, now.month, "Salary", 3000.0)
        
        plan = expense_manager.get_monthly_plan()
        viz = VisualizationService()
        result = viz.budget_chart(plan)
        
        assert result is not None


# ============== Photo Handling Tests ==============

class TestPhotoHandling:
    """Tests for photo/receipt handling."""

    @pytest.mark.asyncio
    async def test_photo_with_valid_caption(self, bot_instance):
        """Test photo with valid expense caption."""
        update = DummyUpdate()
        context = DummyContext()
        
        # Mock photo message
        update.message.caption = "groceries 45.50 weekly shopping"
        mock_photo = MagicMock()
        mock_photo.file_id = "test_file_id_123"
        update.message.photo = [mock_photo]
        
        await bot_instance.handle_photo(update, context)
        
        assert len(update.message.texts) == 1
        response = update.message.texts[0]['text']
        assert "✅ Saved" in response
        assert "📎" in response  # Receipt indicator
        
        # Verify stored in DB
        transactions = bot_instance.expense_manager.get_recent_transactions(1)
        assert transactions[0]['receipt'] == "test_file_id_123"

    @pytest.mark.asyncio
    async def test_photo_without_caption(self, bot_instance):
        """Test photo without caption shows help message."""
        update = DummyUpdate()
        context = DummyContext()
        
        # Mock photo message without caption
        update.message.caption = None
        mock_photo = MagicMock()
        mock_photo.file_id = "test_file_id_456"
        update.message.photo = [mock_photo]
        
        await bot_instance.handle_photo(update, context)
        
        response = update.message.texts[0]['text']
        assert "caption" in response.lower()

    @pytest.mark.asyncio
    async def test_photo_with_invalid_caption(self, bot_instance):
        """Test photo with invalid caption format."""
        update = DummyUpdate()
        context = DummyContext()
        
        # Mock photo message with bad caption
        update.message.caption = "just some text"
        mock_photo = MagicMock()
        mock_photo.file_id = "test_file_id_789"
        update.message.photo = [mock_photo]
        
        await bot_instance.handle_photo(update, context)
        
        response = update.message.texts[0]['text']
        assert "❌" in response

    @pytest.mark.asyncio
    async def test_photo_with_unknown_category(self, bot_instance):
        """Test photo with unknown category in caption."""
        update = DummyUpdate()
        context = DummyContext()
        
        # Mock photo message with unknown category
        update.message.caption = "unknowncat 50.00 test"
        mock_photo = MagicMock()
        mock_photo.file_id = "test_file_id_abc"
        update.message.photo = [mock_photo]
        
        await bot_instance.handle_photo(update, context)
        
        response = update.message.texts[0]['text']
        assert "not recognized" in response


# ============== Bot Flow Tests ==============

class TestBotFlows:
    """Tests for bot conversation flows."""

    @pytest.mark.asyncio
    async def test_start_command(self, bot_instance):
        """Test /start command."""
        update = DummyUpdate()
        context = DummyContext()
        
        await bot_instance.start(update, context)
        
        assert len(update.message.texts) >= 1
        welcome_text = update.message.texts[0]['text']
        assert "Personal Finance Bot" in welcome_text
        
        # Check onboarding state is set
        assert 'onboarding' in context.user_data
        assert context.user_data['onboarding']['stage'] == 'income'

    @pytest.mark.asyncio
    async def test_help_command(self, bot_instance):
        """Test /help command."""
        update = DummyUpdate()
        context = DummyContext()
        
        await bot_instance.help(update, context)
        
        assert len(update.message.texts) == 1
        help_text = update.message.texts[0]['text']
        assert "Help Guide" in help_text

    @pytest.mark.asyncio
    async def test_today_command(self, bot_instance):
        """Test /today command."""
        update = DummyUpdate()
        context = DummyContext()
        
        await bot_instance.today(update, context)
        
        # Should send at least the summary text
        assert len(update.message.texts) >= 1

    @pytest.mark.asyncio
    async def test_add_expense_via_text(self, bot_instance):
        """Test adding expense via text message."""
        update = DummyUpdate()
        context = DummyContext()
        update.message.text = "groceries 45.50 weekly shopping"
        
        await bot_instance.handle_text(update, context)
        
        assert len(update.message.texts) == 1
        response = update.message.texts[0]['text']
        assert "✅ Saved" in response
        assert "$45.50" in response

    @pytest.mark.asyncio
    async def test_add_expense_unknown_category(self, bot_instance):
        """Test adding expense with unknown category."""
        update = DummyUpdate()
        context = DummyContext()
        update.message.text = "xyzunknown 25.00"
        
        await bot_instance.handle_text(update, context)
        
        response = update.message.texts[0]['text']
        assert "not recognized" in response

    @pytest.mark.asyncio
    async def test_add_income_flow(self, bot_instance):
        """Test add income flow."""
        update = DummyUpdate()
        context = DummyContext()
        
        # First set action
        context.user_data['action'] = 'add_income'
        update.message.text = "Salary 3000 January payment"
        
        await bot_instance.handle_text(update, context)
        
        response = update.message.texts[0]['text']
        assert "💰" in response
        assert "$3000.00" in response

    @pytest.mark.asyncio
    async def test_set_budget_flow(self, bot_instance):
        """Test set budget flow."""
        update = DummyUpdate()
        context = DummyContext()
        
        # Set up state as if category was selected
        context.user_data['action'] = 'set_budget'
        context.user_data['category'] = '🛒 Groceries'
        update.message.text = "500"
        
        await bot_instance.handle_text(update, context)
        
        response = update.message.texts[0]['text']
        assert "📋" in response
        assert "$500.00" in response

    @pytest.mark.asyncio
    async def test_custom_amount_flow(self, bot_instance):
        """Test custom amount entry flow."""
        update = DummyUpdate()
        context = DummyContext()
        
        # Set up state for awaiting amount
        context.user_data['category'] = '🛒 Groceries'
        context.user_data['action'] = 'add_expense'
        context.user_data['awaiting'] = 'amount'
        update.message.text = "42.50"
        
        await bot_instance.handle_text(update, context)
        
        # Should prompt for note
        response = update.message.texts[0]['text']
        assert "$42.50" in response
        assert context.user_data['awaiting'] == 'note'

    @pytest.mark.asyncio
    async def test_note_entry_flow(self, bot_instance):
        """Test note entry flow."""
        update = DummyUpdate()
        context = DummyContext()
        
        # Set up state for awaiting note
        context.user_data['category'] = '🛒 Groceries'
        context.user_data['amount'] = 42.50
        context.user_data['awaiting'] = 'note'
        update.message.text = "weekly groceries"
        
        await bot_instance.handle_text(update, context)
        
        response = update.message.texts[0]['text']
        assert "✅ Saved" in response
        # User data should be cleared
        assert 'category' not in context.user_data

    @pytest.mark.asyncio
    async def test_invalid_amount_handling(self, bot_instance):
        """Test invalid amount entry."""
        update = DummyUpdate()
        context = DummyContext()
        
        context.user_data['category'] = '🛒 Groceries'
        context.user_data['awaiting'] = 'amount'
        update.message.text = "not a number"
        
        await bot_instance.handle_text(update, context)
        
        response = update.message.texts[0]['text']
        assert "Invalid amount" in response

    @pytest.mark.asyncio
    async def test_session_expired_missing_category(self, bot_instance):
        """Test session expired when category is missing."""
        update = DummyUpdate()
        context = DummyContext()
        
        # Set up state with amount but no category
        context.user_data['amount'] = 25.0
        context.user_data['awaiting'] = 'note'
        update.message.text = "test note"
        
        await bot_instance.handle_text(update, context)
        
        response = update.message.texts[0]['text']
        assert "Session expired" in response or "expired" in response.lower()

    @pytest.mark.asyncio
    async def test_session_expired_missing_amount(self, bot_instance):
        """Test session expired when amount is missing."""
        update = DummyUpdate()
        context = DummyContext()
        
        # Set up state with category but no amount
        context.user_data['category'] = '🛒 Groceries'
        context.user_data['awaiting'] = 'note'
        update.message.text = "test note"
        
        await bot_instance.handle_text(update, context)
        
        response = update.message.texts[0]['text']
        assert "Session expired" in response or "expired" in response.lower()

    @pytest.mark.asyncio
    async def test_onboarding_income_skip(self, bot_instance):
        """Test skipping income during onboarding."""
        update = DummyUpdate()
        context = DummyContext()
        
        context.user_data['onboarding'] = {
            'stage': 'income',
            'year': 2026,
            'month': 1,
        }
        update.message.text = "skip"
        
        await bot_instance._handle_onboarding(update, context, "skip")
        
        # Should advance to categories stage
        assert context.user_data['onboarding']['stage'] == 'categories'

    @pytest.mark.asyncio
    async def test_onboarding_set_income(self, bot_instance):
        """Test setting income during onboarding."""
        update = DummyUpdate()
        context = DummyContext()
        
        context.user_data['onboarding'] = {
            'stage': 'income',
            'year': 2026,
            'month': 1,
        }
        update.message.text = "5000"
        
        await bot_instance._handle_onboarding(update, context, "5000")
        
        # Check income was set
        plan = bot_instance.expense_manager.get_monthly_plan(2026, 1)
        assert plan['total_projected_income'] == 5000.0

    @pytest.mark.asyncio
    async def test_onboarding_invalid_income(self, bot_instance):
        """Test invalid income during onboarding shows error."""
        update = DummyUpdate()
        context = DummyContext()
        
        context.user_data['onboarding'] = {
            'stage': 'income',
            'year': 2026,
            'month': 1,
        }
        update.message.text = "not a number"
        
        await bot_instance._handle_onboarding(update, context, "not a number")
        
        response = update.message.texts[0]['text']
        assert "❌" in response
        # Should stay in income stage
        assert context.user_data['onboarding']['stage'] == 'income'

    @pytest.mark.asyncio
    async def test_onboarding_category_budget_set(self, bot_instance):
        """Test setting category budget during onboarding."""
        update = DummyUpdate()
        context = DummyContext()
        
        context.user_data['onboarding'] = {
            'stage': 'categories',
            'category_index': 0,
            'year': 2026,
            'month': 1,
        }
        update.message.text = "300"
        
        await bot_instance._handle_onboarding(update, context, "300")
        
        # Check budget was set
        plan = bot_instance.expense_manager.get_monthly_plan(2026, 1)
        first_category = bot_instance.keyboards.categories[0]
        assert plan['planned_budgets'].get(first_category) == 300.0
        # Should advance to next category
        assert context.user_data['onboarding']['category_index'] == 1

    @pytest.mark.asyncio
    async def test_onboarding_category_skip(self, bot_instance):
        """Test skipping category budget during onboarding."""
        update = DummyUpdate()
        context = DummyContext()
        
        context.user_data['onboarding'] = {
            'stage': 'categories',
            'category_index': 0,
            'year': 2026,
            'month': 1,
        }
        update.message.text = "skip"
        
        await bot_instance._handle_onboarding(update, context, "skip")
        
        # Should advance without setting budget
        assert context.user_data['onboarding']['category_index'] == 1
        plan = bot_instance.expense_manager.get_monthly_plan(2026, 1)
        first_category = bot_instance.keyboards.categories[0]
        assert first_category not in plan['planned_budgets']


# ============== Callback Handler Tests ==========================

class TestCallbackHandlers:
    """Tests for callback query handlers."""

    @pytest.mark.asyncio
    async def test_cancel_callback(self, bot_instance):
        """Test cancel callback clears user data."""
        update = DummyUpdate()
        context = DummyContext()
        
        # Set up some user data
        context.user_data['category'] = 'test'
        context.user_data['action'] = 'add_expense'
        
        query = DummyCallbackQuery("cancel")
        update.callback_query = query
        
        await bot_instance.button_callback(update, context)
        
        # User data should be cleared
        assert context.user_data == {}

    @pytest.mark.asyncio
    async def test_back_menu_callback(self, bot_instance):
        """Test back_menu callback returns to main menu."""
        update = DummyUpdate()
        context = DummyContext()
        
        query = DummyCallbackQuery("back_menu")
        update.callback_query = query
        
        await bot_instance.button_callback(update, context)
        
        # Should show main menu
        assert len(query.message.texts) >= 1
        assert "Main Menu" in query.message.texts[0]['text']

    @pytest.mark.asyncio
    async def test_amount_callback_session_expired(self, bot_instance):
        """Test amount callback when session expired (no category)."""
        update = DummyUpdate()
        context = DummyContext()
        
        # No category set - session expired
        query = DummyCallbackQuery("amt_25")
        update.callback_query = query
        
        await bot_instance.button_callback(update, context)
        
        response = query.message.texts[0]['text']
        assert "expired" in response.lower() or "Session" in response

    @pytest.mark.asyncio
    async def test_skip_note_session_expired(self, bot_instance):
        """Test skip note callback when session expired."""
        update = DummyUpdate()
        context = DummyContext()
        
        # Missing category and amount - session expired
        query = DummyCallbackQuery("skip_note")
        update.callback_query = query
        
        await bot_instance.button_callback(update, context)
        
        response = query.message.texts[0]['text']
        assert "expired" in response.lower() or "Session" in response

    @pytest.mark.asyncio
    async def test_menu_add_callback(self, bot_instance):
        """Test menu_add callback."""
        update = DummyUpdate()
        context = DummyContext()
        
        query = DummyCallbackQuery("menu_add")
        update.callback_query = query
        
        await bot_instance.button_callback(update, context)
        
        # Should show category selection
        assert len(query.message.texts) >= 1
        assert "Select Category" in query.message.texts[0]['text']

    @pytest.mark.asyncio
    async def test_quick_amount_callback(self, bot_instance):
        """Test quick amount selection callback."""
        update = DummyUpdate()
        context = DummyContext()
        
        # Set up category first
        context.user_data['category'] = '🛒 Groceries'
        
        query = DummyCallbackQuery("amt_25")
        update.callback_query = query
        
        await bot_instance.button_callback(update, context)
        
        # Should store amount and prompt for note
        assert context.user_data.get('amount') == 25.0
        assert context.user_data.get('awaiting') == 'note'

    @pytest.mark.asyncio
    async def test_skip_note_callback(self, bot_instance):
        """Test skip note callback saves expense."""
        update = DummyUpdate()
        context = DummyContext()
        
        # Set up state
        context.user_data['category'] = '🛒 Groceries'
        context.user_data['amount'] = 25.0
        
        query = DummyCallbackQuery("skip_note")
        update.callback_query = query
        
        await bot_instance.button_callback(update, context)
        
        # Should have saved the expense
        response = query.message.texts[0]['text']
        assert "✅ Saved" in response
        # User data should be cleared
        assert context.user_data == {}

    @pytest.mark.asyncio
    async def test_set_budget_category_selection(self, bot_instance):
        """Test category selection during budget setting."""
        update = DummyUpdate()
        context = DummyContext()
        
        # Set up action for budget category selection
        context.user_data['action'] = 'select_budget_category'
        
        query = DummyCallbackQuery("cat_0")  # First category
        update.callback_query = query
        
        await bot_instance.button_callback(update, context)
        
        # Should now be ready to set budget
        assert context.user_data.get('action') == 'set_budget'
        assert context.user_data.get('category') == bot_instance.keyboards.categories[0]


# ============== Integration Tests ==============

class TestIntegration:
    """Integration tests for complete flows."""

    @pytest.mark.asyncio
    async def test_complete_expense_flow_guided(self, bot_instance):
        """Test complete guided expense entry flow."""
        context = DummyContext()
        
        # Step 1: User clicks Add Expense
        update1 = DummyUpdate()
        query1 = DummyCallbackQuery("menu_add")
        update1.callback_query = query1
        await bot_instance.button_callback(update1, context)
        
        # Step 2: User selects category
        update2 = DummyUpdate()
        query2 = DummyCallbackQuery("cat_0")
        update2.callback_query = query2
        await bot_instance.button_callback(update2, context)
        
        # Step 3: User selects amount
        update3 = DummyUpdate()
        query3 = DummyCallbackQuery("amt_50")
        update3.callback_query = query3
        await bot_instance.button_callback(update3, context)
        
        # Step 4: User skips note
        update4 = DummyUpdate()
        query4 = DummyCallbackQuery("skip_note")
        update4.callback_query = query4
        await bot_instance.button_callback(update4, context)
        
        # Verify expense was saved
        transactions = bot_instance.expense_manager.get_all_transactions()
        assert len(transactions) == 1
        assert transactions[0]['amount'] == 50.0

    @pytest.mark.asyncio
    async def test_complete_budget_setup_flow(self, bot_instance):
        """Test complete budget setup flow."""
        context = DummyContext()
        now = datetime.now()
        
        # Step 1: User clicks Budget Plan
        update1 = DummyUpdate()
        query1 = DummyCallbackQuery("menu_budget")
        update1.callback_query = query1
        await bot_instance.button_callback(update1, context)
        
        # Step 2: User clicks Set Budget
        update2 = DummyUpdate()
        query2 = DummyCallbackQuery("set_budget")
        update2.callback_query = query2
        await bot_instance.button_callback(update2, context)
        
        # Step 3: User selects category
        update3 = DummyUpdate()
        query3 = DummyCallbackQuery("cat_0")
        update3.callback_query = query3
        await bot_instance.button_callback(update3, context)
        
        # Step 4: User enters budget amount
        update4 = DummyUpdate()
        update4.message.text = "300"
        await bot_instance.handle_text(update4, context)
        
        # Verify budget was set
        plan = bot_instance.expense_manager.get_monthly_plan(now.year, now.month)
        assert plan['planned_budgets'].get(bot_instance.keyboards.categories[0]) == 300.0

    @pytest.mark.asyncio
    async def test_summary_with_expenses(self, bot_instance):
        """Test summary generation with actual expenses."""
        # Add some expenses
        bot_instance.expense_manager.add_expense("🛒 Groceries", 100.0)
        bot_instance.expense_manager.add_expense("🍽️ Dining Out", 50.0)
        bot_instance.expense_manager.add_expense("🚗 Transportation", 30.0)
        
        update = DummyUpdate()
        context = DummyContext()
        
        await bot_instance._send_summary_with_charts(update, "day", include_trend=False)
        
        # Should have text summary
        assert len(update.message.texts) >= 1
        summary = update.message.texts[0]['text']
        assert "$180.00" in summary or "180" in summary
