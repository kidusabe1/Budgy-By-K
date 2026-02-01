import importlib
import json
import os
from datetime import datetime
from pathlib import Path

import pytest

from database import ExpenseManager


def _load_webhook(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Load apple_webhook with isolated DB dir and user."""
    monkeypatch.setenv("USE_FIRESTORE", "false")
    monkeypatch.setenv("APPLE_PAY_USER_KEY", "webhook_user")
    monkeypatch.setenv("APPLE_PAY_DB_DIR", str(tmp_path / "data"))

    # Import inside helper to respect fresh env
    import apple_webhook

    return importlib.reload(apple_webhook)


def test_predict_category_mapping(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    module = _load_webhook(monkeypatch, tmp_path)

    assert module.predict_category("Uber") == "🚗 Transportation"
    assert module.predict_category("Whole Foods Market") == "🛒 Groceries"
    assert module.predict_category("Random Cafe") == "🍽️ Dining Out"
    assert module.predict_category("Unknown Merchant") == "🔧 Other"


def test_webhook_saves_transaction(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    module = _load_webhook(monkeypatch, tmp_path)
    client = module.app.test_client()

    payload = {
        "merchant": "Whole Foods Market",
        "amount": 12.5,
        "date": "2024-01-02T15:04:05",
        "card_name": "Apple Card",
    }

    response = client.post("/webhook/apple_pay", json=payload)
    assert response.status_code == 200
    assert response.get_json()["status"] == "success"

    manager = ExpenseManager(user_id="webhook_user")
    txns = manager.get_all_transactions()
    assert len(txns) == 1

    tx = txns[0]
    assert tx["category"] == "🛒 Groceries"
    assert tx["amount"] == pytest.approx(12.5)
    assert "Apple Pay" in tx["note"] and "Apple Card" in tx["note"]
    assert str(tx["date"]).startswith("2024-01-02")


def test_add_expense_accepts_date_override(tmp_path: Path):
    db_path = tmp_path / "custom_date.db"
    manager = ExpenseManager(db_path=str(db_path))
    manager.add_expense(
        category="🛒 Groceries",
        amount=20.0,
        note="backfill",
        date_override=datetime(2024, 5, 6, 7, 8, 9),
    )

    txns = manager.get_all_transactions()
    assert len(txns) == 1
    assert str(txns[0]["date"]).startswith("2024-05-06 07:08:09")


def test_predict_category_uses_persistent_map(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    module = _load_webhook(monkeypatch, tmp_path)

    module.update_mapping("Mega", "🎬 Entertainment")

    # Should read from persisted map
    assert module.predict_category("mega") == "🎬 Entertainment"

    map_path = module.MAP_FILE
    assert map_path.exists()
    with map_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    assert data.get("mega") == "🎬 Entertainment"


def test_predict_category_ignores_cached_other(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    module = _load_webhook(monkeypatch, tmp_path)

    # Seed cache with a stale "Other" mapping
    module.update_mapping("he eats out", "🔧 Other")

    # Force Gemini path to return a better category
    monkeypatch.setattr(module, "_predict_with_gemini", lambda name: "🍽️ Dining Out")

    cat = module.predict_category("He Eats Out")
    assert cat == "🍽️ Dining Out"

    # The stale mapping should be removed and replaced
    data = module.load_map()
    assert data.get("he eats out") == "🍽️ Dining Out"
