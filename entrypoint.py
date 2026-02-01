"""Unified Cloud Run entrypoint.

Serves all routes on ``$PORT`` (default 8080):
- POST /webhook/telegram     – Telegram bot updates
- POST /webhook/apple_pay    – Apple Pay transaction logging
- POST /internal/daily-report  – Cloud Scheduler trigger
- POST /internal/monthly-report – Cloud Scheduler trigger
- GET  /health               – Health check
"""

import asyncio
import logging
import os
import threading

from dotenv import load_dotenv

load_dotenv()

from flask import Flask, request, jsonify
from telegram import Update

# ---------------------------------------------------------------------------
# Async bridge: a dedicated event loop running in a background thread so we
# can call async python-telegram-bot handlers from synchronous Flask views.
# ---------------------------------------------------------------------------

_loop = asyncio.new_event_loop()
_thread = threading.Thread(target=_loop.run_forever, daemon=True)
_thread.start()


def run_async(coro):
    """Run *coro* on the background event loop and return the result."""
    future = asyncio.run_coroutine_threadsafe(coro, _loop)
    return future.result(timeout=30)


# ---------------------------------------------------------------------------
# Initialise Telegram bot (webhook mode – no polling)
# ---------------------------------------------------------------------------

from bot import BotConfig, BudgetBot, VisualizationService, ExpenseManager  # noqa: E402

logger = logging.getLogger(__name__)

token = os.getenv("TELEGRAM_BOT_TOKEN")
if not token:
    raise RuntimeError("TELEGRAM_BOT_TOKEN environment variable is required")

config = BotConfig(token=token)
viz = VisualizationService()
budget_bot = BudgetBot(config, viz, ExpenseManager.CATEGORIES)
budget_bot.setup()

# Initialise the Application on the async loop (required before processing updates)
run_async(budget_bot.application.initialize())
run_async(budget_bot.application.start())

# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------

app = Flask(__name__)


@app.route("/webhook/telegram", methods=["POST"])
def telegram_webhook():
    """Receive Telegram updates forwarded by the Telegram API."""
    data = request.get_json(force=True, silent=True) or {}
    update = Update.de_json(data, budget_bot.application.bot)
    run_async(budget_bot.application.process_update(update))
    return "ok", 200


@app.route("/webhook/apple_pay", methods=["POST"])
def apple_pay_proxy():
    """Delegate to the existing apple_webhook handler."""
    from apple_webhook import apple_pay_webhook  # noqa: E402
    return apple_pay_webhook()


@app.route("/internal/daily-report", methods=["POST"])
def trigger_daily_report():
    """Triggered by Cloud Scheduler at 9 PM daily."""
    secret = request.headers.get("X-Scheduler-Secret", "")
    expected = os.getenv("SCHEDULER_SECRET", "")
    if not expected or secret != expected:
        return jsonify({"error": "unauthorized"}), 401
    run_async(budget_bot.send_daily_report())
    return jsonify({"status": "ok"}), 200


@app.route("/internal/monthly-report", methods=["POST"])
def trigger_monthly_report():
    """Triggered by Cloud Scheduler on the 1st of each month at 9 AM."""
    secret = request.headers.get("X-Scheduler-Secret", "")
    expected = os.getenv("SCHEDULER_SECRET", "")
    if not expected or secret != expected:
        return jsonify({"error": "unauthorized"}), 401
    run_async(budget_bot.send_monthly_report())
    return jsonify({"status": "ok"}), 200


@app.route("/health", methods=["GET"])
def health():
    return "ok", 200


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    logger.info("Starting entrypoint on port %s", port)
    app.run(host="0.0.0.0", port=port)
