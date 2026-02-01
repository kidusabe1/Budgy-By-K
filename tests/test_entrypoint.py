"""Tests for the Cloud Run entrypoint Flask routes."""

import json
import os
import sys
from unittest.mock import patch, MagicMock, AsyncMock

import pytest


@pytest.fixture()
def client():
    """Create a Flask test client with mocked bot internals."""
    # Patch heavy imports before loading entrypoint
    mock_bot = MagicMock()
    mock_bot.application = MagicMock()
    mock_bot.application.bot = MagicMock()
    mock_bot.application.initialize = AsyncMock()
    mock_bot.application.start = AsyncMock()
    mock_bot.application.process_update = AsyncMock()
    mock_bot.send_daily_report = AsyncMock()
    mock_bot.send_monthly_report = AsyncMock()
    mock_bot.setup = MagicMock()

    mock_update_cls = MagicMock()
    mock_update_cls.de_json = MagicMock(return_value=MagicMock())

    with (
        patch.dict(os.environ, {
            "TELEGRAM_BOT_TOKEN": "123:TEST",
            "SCHEDULER_SECRET": "test-secret",
        }),
        patch("bot.BudgetBot", return_value=mock_bot),
        patch("bot.Application"),
    ):
        # Remove cached entrypoint module if present
        sys.modules.pop("entrypoint", None)

        with patch("entrypoint.Update", mock_update_cls):
            import importlib
            import entrypoint
            entrypoint = importlib.reload(entrypoint)

            # Inject our mocks
            entrypoint.budget_bot = mock_bot
            entrypoint.Update = mock_update_cls

            yield entrypoint.app.test_client(), mock_bot, mock_update_cls


class TestHealthEndpoint:
    def test_health(self, client):
        flask_client, _, _ = client
        resp = flask_client.get("/health")
        assert resp.status_code == 200


class TestTelegramWebhook:
    def test_processes_update(self, client):
        flask_client, mock_bot, mock_update = client
        payload = {"update_id": 1, "message": {"text": "/start"}}
        resp = flask_client.post(
            "/webhook/telegram",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert resp.status_code == 200
        mock_update.de_json.assert_called_once()


class TestSchedulerEndpoints:
    def test_daily_report_valid_secret(self, client):
        flask_client, mock_bot, _ = client
        resp = flask_client.post(
            "/internal/daily-report",
            headers={"X-Scheduler-Secret": "test-secret"},
        )
        assert resp.status_code == 200

    def test_daily_report_bad_secret(self, client):
        flask_client, _, _ = client
        resp = flask_client.post(
            "/internal/daily-report",
            headers={"X-Scheduler-Secret": "wrong"},
        )
        assert resp.status_code == 401

    def test_daily_report_missing_secret(self, client):
        flask_client, _, _ = client
        resp = flask_client.post("/internal/daily-report")
        assert resp.status_code == 401

    def test_monthly_report_valid_secret(self, client):
        flask_client, mock_bot, _ = client
        resp = flask_client.post(
            "/internal/monthly-report",
            headers={"X-Scheduler-Secret": "test-secret"},
        )
        assert resp.status_code == 200

    def test_monthly_report_bad_secret(self, client):
        flask_client, _, _ = client
        resp = flask_client.post(
            "/internal/monthly-report",
            headers={"X-Scheduler-Secret": "wrong"},
        )
        assert resp.status_code == 401
