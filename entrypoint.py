"""Unified Cloud Run entrypoint.

Serves all routes on ``$PORT`` (default 8080):
- POST /webhook/telegram     - Telegram bot updates
- POST /webhook/apple_pay    - Apple Pay transaction logging
- POST /internal/daily-report  - Cloud Scheduler trigger
- POST /internal/monthly-report - Cloud Scheduler trigger
- GET  /health               - Health check
"""

import asyncio
import logging
import os
import threading
import traceback
from typing import Optional, Tuple

from dotenv import load_dotenv
from flask import Flask, jsonify, request

load_dotenv()


# ---------------------------------------------------------------------------
# Async bridge: dedicated loop in background thread to run PTB coroutines
# ---------------------------------------------------------------------------

_loop = asyncio.new_event_loop()
_loop_thread = threading.Thread(target=_loop.run_forever, daemon=True)
_loop_thread.start()


def run_async(coro, timeout: float = 60.0):
    """Run *coro* on the background loop and wait for result."""
    future = asyncio.run_coroutine_threadsafe(coro, _loop)
    return future.result(timeout=timeout)


# ---------------------------------------------------------------------------
# Flask app created early so Cloud Run sees port binding immediately
# ---------------------------------------------------------------------------

app = Flask(__name__)
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

# Bot state; initialisation is lazy and resilient
_bot_ready = threading.Event()
_bot_starting = threading.Event()
_bot_error: Optional[str] = None
budget_bot = None
_Update = None  # telegram.Update class, populated after bot import
_init_thread: Optional[threading.Thread] = None


def _init_bot():
    """Initialise the Telegram bot in the background."""
    global budget_bot, _Update, _bot_error
    try:
        from telegram import Update as TgUpdate
        from my_budget.bot import BotConfig, BudgetBot, VisualizationService
        from my_budget.database import ExpenseManager

        _Update = TgUpdate

        token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not token:
            _bot_error = "TELEGRAM_BOT_TOKEN not set"
            logger.error(_bot_error)
            return

        config = BotConfig(token=token)
        viz = VisualizationService()
        bot = BudgetBot(config, viz, ExpenseManager.CATEGORIES)
        bot.setup()

        # initialize() contacts the Telegram API to validate the token
        run_async(bot.application.initialize())
        run_async(bot.application.start())

        budget_bot = bot
        _bot_ready.set()
        logger.info("Telegram bot initialised successfully")
    except Exception:  # noqa: BLE001
        _bot_error = traceback.format_exc()
        logger.exception("Telegram bot initialisation failed")


def _start_bot_once():
    """Kick off bot startup in a daemon thread (idempotent)."""
    global _init_thread
    if _bot_starting.is_set():
        return
    _bot_starting.set()
    _init_thread = threading.Thread(target=_init_bot, daemon=True)
    _init_thread.start()


def _wait_for_bot(timeout: float = 30.0) -> Tuple[bool, str]:
    """Wait for bot readiness, returning (ok, message)."""
    if _bot_error:
        return False, "Bot failed to start"
    if _bot_ready.wait(timeout=timeout):
        return True, ""
    return False, "Bot not ready"


@app.before_request
def _ensure_bot_started():
    if request.path == "/health":
        return
    _start_bot_once()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/webhook/telegram", methods=["POST"])
def telegram_webhook():
    """Receive Telegram updates forwarded by the Telegram API."""
    ok, msg = _wait_for_bot()
    if not ok:
        return jsonify({"error": msg}), 503
    data = request.get_json(force=True, silent=True) or {}
    update = _Update.de_json(data, budget_bot.application.bot)
    run_async(budget_bot.application.process_update(update))
    return "ok", 200


@app.route("/webhook/apple_pay", methods=["POST"])
def apple_pay_proxy():
    """Delegate to the existing apple_webhook handler."""
    from apple_webhook import apple_pay_webhook
    return apple_pay_webhook()


@app.route("/internal/daily-report", methods=["POST"])
def trigger_daily_report():
    """Triggered by Cloud Scheduler at 9 PM daily."""
    secret = request.headers.get("X-Scheduler-Secret", "")
    expected = os.getenv("SCHEDULER_SECRET", "")
    if not expected or secret != expected:
        return jsonify({"error": "unauthorized"}), 401
    ok, msg = _wait_for_bot()
    if not ok:
        return jsonify({"error": msg}), 503
    run_async(budget_bot.send_daily_report())
    return jsonify({"status": "ok"}), 200


@app.route("/internal/monthly-report", methods=["POST"])
def trigger_monthly_report():
    """Triggered by Cloud Scheduler on the 1st of each month at 9 AM."""
    secret = request.headers.get("X-Scheduler-Secret", "")
    expected = os.getenv("SCHEDULER_SECRET", "")
    if not expected or secret != expected:
        return jsonify({"error": "unauthorized"}), 401
    ok, msg = _wait_for_bot()
    if not ok:
        return jsonify({"error": msg}), 503
    run_async(budget_bot.send_monthly_report())
    return jsonify({"status": "ok"}), 200


@app.route("/health", methods=["GET"])
def health():
    if _bot_error:
        return jsonify({"status": "error", "detail": _bot_error}), 500
    status = "ready" if _bot_ready.is_set() else "starting"
    return jsonify({"status": status}), 200


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    logger.info("Starting entrypoint on port %s", port)
    _start_bot_once()
    app.run(host="0.0.0.0", port=port)
