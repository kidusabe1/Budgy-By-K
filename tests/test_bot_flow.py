import pytest

from bot import BudgetBot, BotConfig, ExpenseParser, KeyboardFactory, VisualizationService
from database import ExpenseManager


class DummyUser:
    """Dummy user for testing."""
    def __init__(self, user_id=12345, username='test_user'):
        self.id = user_id
        self.username = username


class DummyMessage:
    def __init__(self):
        self.texts = []
        self.photos = []

    async def reply_text(self, text, **kwargs):
        self.texts.append(text)

    async def reply_photo(self, photo=None, caption=None, **kwargs):
        self.photos.append({"photo": photo, "caption": caption})


class DummyUpdate:
    def __init__(self):
        self.message = DummyMessage()
        self.effective_user = DummyUser()


@pytest.fixture()
def bot_instance(tmp_path):
    config = BotConfig(token="123:TEST")
    viz = VisualizationService()
    categories = [
        "🛒 Groceries", "🍽️ Dining Out", "🚗 Transportation",
        "🎬 Entertainment", "💊 Health", "📱 Utilities",
        "🛍️ Shopping", "📚 Education", "💼 Work", "🎁 Other"
    ]
    # Override the DB_DIR to use temp path
    ExpenseManager.DB_DIR = str(tmp_path / "user_data")
    bot = BudgetBot(config, viz, categories)
    # Mark onboarding as complete so other features work
    manager = bot._get_manager('test_user')
    manager.register_user(12345)
    manager.complete_onboarding(12345)
    return bot


def test_expense_parser_round_trip():
    category, amount, note = ExpenseParser.parse_expense("groceries 12.50 milk")
    assert category == "groceries"
    assert amount == 12.50
    assert note == "milk"

    source, inc_amount, inc_note = ExpenseParser.parse_income("Salary 3000 January")
    assert source == "Salary"
    assert inc_amount == 3000
    assert inc_note == "January"


@pytest.mark.asyncio()
async def test_send_summary_with_charts(bot_instance: BudgetBot):
    manager = bot_instance._get_manager('test_user')
    manager.add_expense("🛒 Groceries", 40.0)
    manager.add_expense("🍽️ Dining Out", 20.0)

    update = DummyUpdate()
    await bot_instance._send_summary_with_charts(update, timeframe="week", include_trend=True)

    assert update.message.texts, "Expected summary text to be sent"
    assert len(update.message.photos) >= 1, "Expected at least one chart image"