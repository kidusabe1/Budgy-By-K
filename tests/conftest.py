import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bot import BudgetBot, BotConfig, VisualizationService
from database import ExpenseManager


# ============== Shared Dummy / Mock Objects ==============


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


class DummyUser:
    """Mock user object."""
    def __init__(self, user_id=12345, username="test_user"):
        self.id = user_id
        self.username = username


class DummyChat:
    """Mock chat object."""
    def __init__(self, chat_id=12345):
        self.id = chat_id


class DummyUpdate:
    """Mock update object for testing."""
    def __init__(self, chat_id=12345, user_id=12345, username="test_user"):
        self.message = DummyMessage()
        self.effective_chat = DummyChat(chat_id)
        self.effective_user = DummyUser(user_id, username)
        self.callback_query = None


class DummyCallbackQuery:
    """Mock callback query object."""
    def __init__(self, data, chat_id=12345, user_id=12345, username="test_user"):
        self.data = data
        self.message = DummyMessage()
        self.message.chat_id = chat_id
        self.from_user = DummyUser(user_id, username)

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


# ============== Shared Fixtures ==============


@pytest.fixture()
def expense_manager(tmp_path):
    """Create a fresh ExpenseManager with a temp database."""
    db_path = tmp_path / "test_expenses.db"
    return ExpenseManager(db_path=str(db_path))


@pytest.fixture()
def bot_instance(tmp_path):
    """Create BudgetBot instance with test configuration."""
    config = BotConfig(token="123:TEST")
    viz = VisualizationService()
    bot = BudgetBot(config, viz, ExpenseManager.CATEGORIES)
    # Override the DB_DIR to use temp path
    ExpenseManager.DB_DIR = str(tmp_path / "user_data")
    return bot


def setup_completed_onboarding(bot_instance, chat_id=12345, username="test_user"):
    """Helper to mark onboarding as complete for a test user."""
    manager = bot_instance._get_manager(username)
    manager.register_user(chat_id)
    manager.complete_onboarding(chat_id)
    return manager


# ============== Firestore Fixtures ==============


@pytest.fixture()
def mock_firestore_client():
    """Create a fresh in-memory MockFirestoreClient."""
    from tests.mock_firestore import MockFirestoreClient
    return MockFirestoreClient()


@pytest.fixture()
def firestore_expense_manager(mock_firestore_client):
    """Create a FirestoreExpenseManager backed by the in-memory mock."""
    from firestore_database import FirestoreExpenseManager
    return FirestoreExpenseManager(user_id="test_user", db_client=mock_firestore_client)
