import io
import logging
import os
from dataclasses import dataclass
from datetime import datetime, time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib

matplotlib.use('Agg')  # Use non-interactive backend for servers
import matplotlib.pyplot as plt
import numpy as np
from logging.handlers import RotatingFileHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputFile, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from telegram.error import BadRequest

from database import ExpenseManager

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FILE = os.getenv("LOG_FILE", "logs/bot.log")

root_logger = logging.getLogger()
root_logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)
if not any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers):
    root_logger.addHandler(stream_handler)

log_path = Path(LOG_FILE).expanduser().resolve()
log_path.parent.mkdir(parents=True, exist_ok=True)
if not any(isinstance(h, RotatingFileHandler) and getattr(h, 'baseFilename', None) == str(log_path) for h in root_logger.handlers):
    file_handler = RotatingFileHandler(log_path, maxBytes=1_000_000, backupCount=3)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

logger = logging.getLogger(__name__)


@dataclass
class BotConfig:
    token: str
    daily_report_time: time = time(hour=21, minute=0, second=0)
    monthly_report_time: time = time(hour=9, minute=0, second=0)
    monthly_report_day: int = 1


class VisualizationService:
    """Creates charts for summaries."""

    @staticmethod
    def pie_chart(data: Dict[str, float], title: str) -> Optional[io.BytesIO]:
        if not data:
            return None

        plt.style.use('seaborn-v0_8-whitegrid')
        fig, ax = plt.subplots(figsize=(10, 8))

        labels = [cat.split(' ', 1)[1] if ' ' in cat else cat for cat in data.keys()]
        values = list(data.values())

        colors = [
            '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7',
            '#DDA0DD', '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E9', '#F8B500',
        ]

        explode = [0.02] * len(values)
        wedges, texts, autotexts = ax.pie(
            values,
            labels=labels,
            autopct='%1.1f%%',
            colors=colors[:len(values)],
            explode=explode,
            shadow=True,
            startangle=90,
            textprops={'fontsize': 11, 'fontweight': 'bold'},
        )

        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontsize(10)

        ax.set_title(title, fontsize=16, fontweight='bold', pad=20)
        total = sum(values)
        ax.annotate(
            f'Total: ${total:.2f}',
            xy=(0, 0),
            fontsize=14,
            ha='center',
            va='center',
            fontweight='bold',
            bbox=dict(boxstyle='round', facecolor='white', alpha=0.8),
        )

        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='white', edgecolor='none')
        buf.seek(0)
        plt.close(fig)
        return buf

    @staticmethod
    def bar_chart(daily_data: List[Tuple[str, float]], title: str) -> Optional[io.BytesIO]:
        if not daily_data:
            return None

        plt.style.use('seaborn-v0_8-whitegrid')
        fig, ax = plt.subplots(figsize=(12, 6))

        dates = [d[0] for d in daily_data]
        amounts = [d[1] for d in daily_data]
        date_labels = [datetime.strptime(d, '%Y-%m-%d').strftime('%a\n%m/%d') for d in dates]

        max_amount = max(amounts) if amounts else 1
        colors = plt.cm.RdYlGn_r([a / max_amount for a in amounts])

        bars = ax.bar(range(len(dates)), amounts, color=colors, edgecolor='white', linewidth=1.5)
        for bar, amount in zip(bars, amounts):
            height = bar.get_height()
            ax.annotate(
                f'${amount:.0f}',
                xy=(bar.get_x() + bar.get_width() / 2, height),
                xytext=(0, 3),
                textcoords="offset points",
                ha='center',
                va='bottom',
                fontsize=10,
                fontweight='bold',
            )

        ax.set_xticks(range(len(dates)))
        ax.set_xticklabels(date_labels, fontsize=10)
        ax.set_ylabel('Amount ($)', fontsize=12, fontweight='bold')
        ax.set_title(title, fontsize=16, fontweight='bold', pad=20)

        avg = sum(amounts) / len(amounts)
        ax.axhline(y=avg, color='#E74C3C', linestyle='--', linewidth=2, label=f'Avg: ${avg:.2f}')
        ax.legend(loc='upper right')

        total = sum(amounts)
        ax.annotate(
            f'Total: ${total:.2f}',
            xy=(0.98, 0.98),
            xycoords='axes fraction',
            fontsize=12,
            ha='right',
            va='top',
            fontweight='bold',
            bbox=dict(boxstyle='round', facecolor='#3498DB', alpha=0.8, edgecolor='none'),
            color='white',
        )

        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='white', edgecolor='none')
        buf.seek(0)
        plt.close(fig)
        return buf

    @staticmethod
    def budget_chart(plan: Dict) -> Optional[io.BytesIO]:
        plt.style.use('seaborn-v0_8-whitegrid')
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

        all_categories = set(plan['planned_budgets'].keys()) | set(plan['actual_spending'].keys())
        categories = sorted(all_categories)

        if categories:
            short_names = [cat.split(' ', 1)[1][:10] if ' ' in cat else cat[:10] for cat in categories]
            planned = [plan['planned_budgets'].get(cat, 0) for cat in categories]
            actual = [plan['actual_spending'].get(cat, 0) for cat in categories]

            x = np.arange(len(categories))
            width = 0.35

            ax1.bar(x - width / 2, planned, width, label='Planned', color='#3498DB', alpha=0.8)
            ax1.bar(x + width / 2, actual, width, label='Actual', color='#E74C3C', alpha=0.8)

            ax1.set_xlabel('Category', fontsize=11)
            ax1.set_ylabel('Amount ($)', fontsize=11)
            ax1.set_title('Budget vs Actual by Category', fontsize=14, fontweight='bold')
            ax1.set_xticks(x)
            ax1.set_xticklabels(short_names, rotation=45, ha='right', fontsize=9)
            ax1.legend()
            ax1.grid(axis='y', alpha=0.3)

        total_income = plan['total_actual_income'] or plan['total_projected_income'] or 1
        total_spent = plan['total_spent']
        remaining = max(0, total_income - total_spent)
        overspent = max(0, total_spent - total_income)

        if overspent > 0:
            sizes = [total_spent, overspent]
            labels = ['Spent', 'Overspent']
            colors = ['#E74C3C', '#C0392B']
        else:
            sizes = [total_spent, remaining]
            labels = ['Spent', 'Remaining']
            colors = ['#E74C3C', '#27AE60']

        ax2.pie(
            sizes,
            labels=labels,
            autopct='%1.1f%%',
            colors=colors,
            startangle=90,
            wedgeprops=dict(width=0.5),
        )
        ax2.annotate(
            f'${total_spent:.0f}\nof\n${total_income:.0f}',
            xy=(0, 0),
            fontsize=14,
            ha='center',
            va='center',
            fontweight='bold',
        )
        ax2.set_title('Overall Budget Status', fontsize=14, fontweight='bold')

        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='white', edgecolor='none')
        buf.seek(0)
        plt.close(fig)
        return buf


class KeyboardFactory:
    """Builds inline keyboards."""

    def __init__(self, categories: List[str]):
        self.categories = categories

    def main_menu(self) -> InlineKeyboardMarkup:
        keyboard = [
            [InlineKeyboardButton("➕ Add Expense", callback_data="menu_add"), InlineKeyboardButton("💰 Add Income", callback_data="menu_income")],
            [InlineKeyboardButton("📅 Today", callback_data="report_day"), InlineKeyboardButton("📊 Week", callback_data="report_week"), InlineKeyboardButton("📈 Month", callback_data="report_month")],
            [InlineKeyboardButton("📋 Budget Plan", callback_data="menu_budget"), InlineKeyboardButton("📜 Recent", callback_data="menu_recent")],
            [InlineKeyboardButton("⚙️ Settings", callback_data="menu_settings"), InlineKeyboardButton("📤 Export", callback_data="menu_export")],
        ]
        return InlineKeyboardMarkup(keyboard)

    def categories_keyboard(self) -> InlineKeyboardMarkup:
        keyboard: List[List[InlineKeyboardButton]] = []
        for i in range(0, len(self.categories), 2):
            row = [InlineKeyboardButton(self.categories[i], callback_data=f"cat_{i}")]
            if i + 1 < len(self.categories):
                row.append(InlineKeyboardButton(self.categories[i + 1], callback_data=f"cat_{i + 1}"))
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def quick_amount_keyboard() -> InlineKeyboardMarkup:
        keyboard = [
            [InlineKeyboardButton("$5", callback_data="amt_5"), InlineKeyboardButton("$10", callback_data="amt_10"), InlineKeyboardButton("$15", callback_data="amt_15"), InlineKeyboardButton("$20", callback_data="amt_20")],
            [InlineKeyboardButton("$25", callback_data="amt_25"), InlineKeyboardButton("$50", callback_data="amt_50"), InlineKeyboardButton("$75", callback_data="amt_75"), InlineKeyboardButton("$100", callback_data="amt_100")],
            [InlineKeyboardButton("✏️ Custom Amount", callback_data="amt_custom")],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel")],
        ]
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def settings_keyboard(daily_enabled: bool) -> InlineKeyboardMarkup:
        status = "✅ ON" if daily_enabled else "❌ OFF"
        keyboard = [
            [InlineKeyboardButton(f"🔔 Daily Report: {status}", callback_data="toggle_daily")],
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="back_menu")],
        ]
        return InlineKeyboardMarkup(keyboard)


class ExpenseParser:
    """Parses free-form user input for expenses and income."""

    @staticmethod
    def parse_expense(text: str) -> Tuple[str, float, str]:
        parts = text.strip().split(None, 2)
        if len(parts) < 2:
            raise ValueError("Format: `[Category] [Amount] [Note optional]`")
        category_raw = parts[0]
        try:
            amount = float(parts[1].replace('$', '').replace(',', ''))
        except ValueError as exc:
            raise ValueError("Invalid amount") from exc
        note = parts[2] if len(parts) > 2 else ""
        return category_raw, amount, note

    @staticmethod
    def parse_income(text: str) -> Tuple[str, float, str]:
        parts = text.strip().split(None, 2)
        if len(parts) < 2:
            raise ValueError("Format: `[Source] [Amount] [Note optional]`")
        source = parts[0]
        try:
            amount = float(parts[1].replace('$', '').replace(',', ''))
        except ValueError as exc:
            raise ValueError("Invalid amount") from exc
        note = parts[2] if len(parts) > 2 else ""
        return source, amount, note


class BudgetBot:
    """Object-oriented Telegram bot for personal finance tracking."""

    def __init__(self, expense_manager: ExpenseManager, config: BotConfig, viz: VisualizationService, keyboards: KeyboardFactory):
        self.expense_manager = expense_manager
        self.config = config
        self.viz = viz
        self.keyboards = keyboards
        self.application = Application.builder().token(config.token).build()

    def run(self) -> None:
        self._register_handlers()
        self._schedule_jobs()
        logger.info("Starting bot...")
        print("🤖 Bot is running! Press Ctrl+C to stop.")
        print("📊 Daily reports scheduled for 9:00 PM")
        print("📅 Monthly reports scheduled for 1st of each month at 9:00 AM")
        self.application.run_polling()

    def _register_handlers(self) -> None:
        app = self.application
        app.add_handler(CommandHandler("start", self.start))
        app.add_handler(CommandHandler("help", self.help))
        app.add_handler(CommandHandler("menu", self.menu))
        app.add_handler(CommandHandler("today", self.today))
        app.add_handler(CommandHandler("week", self.week))
        app.add_handler(CommandHandler("month", self.month))
        app.add_handler(CommandHandler("budget", self.budget))
        app.add_handler(CommandHandler("income", self.income))
        app.add_handler(CommandHandler("recent", self.recent))
        app.add_handler(CommandHandler("delete_last", self.delete_last))
        app.add_handler(CommandHandler("export", self.export))
        app.add_handler(CommandHandler("settings", self.settings))
        app.add_handler(CommandHandler("reset_data", self.reset_data))

        app.add_handler(CallbackQueryHandler(self.button_callback))
        app.add_handler(MessageHandler(filters.PHOTO, self.handle_photo))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text))
        app.add_error_handler(self.error_handler)

    def _schedule_jobs(self) -> None:
        job_queue = self.application.job_queue
        job_queue.run_daily(self.send_daily_report, time=self.config.daily_report_time, name="daily_report")
        job_queue.run_monthly(
            self.send_monthly_report,
            when=self.config.monthly_report_time,
            day=self.config.monthly_report_day,
            name="monthly_report",
        )

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = update.effective_chat.id
        self.expense_manager.register_user(chat_id)
        welcome = (
            "🎯 *Personal Finance Bot*\n\n"
            "Track expenses, budgets, and income with ease.\n\n"
            "*Quick Entry:* `groceries 45.50 note`\n"
            "*With receipt:* send photo + caption\n\n"
            "Or tap the menu below."
        )
        await update.message.reply_text(welcome, parse_mode='Markdown', reply_markup=self.keyboards.main_menu())

        now = datetime.now()
        month_label = now.strftime('%B %Y')
        context.user_data['onboarding'] = {
            'stage': 'income',
            'year': now.year,
            'month': now.month,
        }
        await update.message.reply_text(
            f"Let's set up your {month_label} plan.\nEnter projected monthly income (number) or type 'skip' to skip.",
        )

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        help_msg = (
            "📚 *Help Guide*\n\n"
            "• `groceries 45.50 milk`\n"
            "• `uber 15 office ride`\n"
            "• Photo caption: `dining 28.5 pizza`\n\n"
            "Commands:\n"
            "/menu, /today, /week, /month, /budget, /income, /recent, /delete_last, /export, /settings\n"
        )
        await update.message.reply_text(help_msg, parse_mode='Markdown', reply_markup=self.keyboards.main_menu())

    async def menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text("📱 *Main Menu*", parse_mode='Markdown', reply_markup=self.keyboards.main_menu())

    async def today(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._send_summary_with_charts(update, timeframe="day", include_trend=False)

    async def week(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._send_summary_with_charts(update, timeframe="week", include_trend=True)

    async def month(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._send_summary_with_charts(update, timeframe="month", include_trend=True)

    async def budget(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        status = self.expense_manager.get_budget_status()
        plan = self.expense_manager.get_monthly_plan()
        await update.message.reply_text(status)
        chart = self.viz.budget_chart(plan)
        if chart:
            await update.message.reply_photo(photo=InputFile(chart, filename="budget_status.png"), caption="📊 Budget Overview")
        keyboard = [
            [InlineKeyboardButton("📝 Set Category Budget", callback_data="set_budget")],
            [InlineKeyboardButton("💵 Set Projected Income", callback_data="set_income_proj")],
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="back_menu")],
        ]
        await update.message.reply_text("Update your budget plan?", reply_markup=InlineKeyboardMarkup(keyboard))

    async def reset_data(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(self.expense_manager.clear_all_data())

    async def income(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        context.user_data.clear()
        context.user_data['action'] = 'add_income'
        await update.message.reply_text(
            "💰 *Add Income*\nFormat: `[Source] [Amount] [Note optional]`\nExample: `Salary 3500 January`",
            parse_mode='Markdown',
        )

    async def recent(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = update.effective_chat.id if update.effective_chat else None
        transactions = self.expense_manager.get_recent_transactions(10)
        if not transactions:
            await context.bot.send_message(chat_id=chat_id, text="📭 No transactions yet.", reply_markup=self.keyboards.main_menu())
            return
        msg = "📜 *Recent Transactions*\n\n"
        for tx in transactions:
            date_str = tx['date'][:10] if tx['date'] else 'N/A'
            receipt_icon = " 📎" if tx.get('receipt') else ""
            note = f" ({tx['note']})" if tx['note'] else ""
            msg += f"• {date_str}\n  {tx['category']}: ${tx['amount']:.2f}{note}{receipt_icon}\n\n"
        await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode='Markdown', reply_markup=self.keyboards.main_menu())

    async def delete_last(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(self.expense_manager.delete_last())

    async def export(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = update.effective_chat.id if update.effective_chat else None
        try:
            filename = self.expense_manager.export_to_csv()
            if not filename:
                if chat_id:
                    await context.bot.send_message(chat_id=chat_id, text="❌ No expenses to export.")
                return
            with open(filename, 'rb') as f:
                if chat_id:
                    await context.bot.send_document(
                        chat_id=chat_id,
                        document=f,
                        filename=filename,
                        caption="📊 Your expense data",
                    )
            os.remove(filename)
        except Exception as exc:
            logger.error("Export failed: %s", exc)
            if chat_id:
                await context.bot.send_message(chat_id=chat_id, text="❌ Export failed. Please try again.")

    async def settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = update.effective_chat.id
        enabled = self.expense_manager.is_daily_report_enabled(chat_id)
        await update.message.reply_text("⚙️ Settings", parse_mode='Markdown', reply_markup=KeyboardFactory.settings_keyboard(enabled))

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        chat_id = query.message.chat_id
        data = query.data
        logger.debug("callback: chat_id=%s data=%s state=%s", chat_id, data, dict(context.user_data))

        async def edit_or_send(text: str, reply_markup=None, parse_mode=None):
            try:
                await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
            except BadRequest as exc:
                logger.debug("edit_message_text fallback: %s", exc)
                await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup, parse_mode=parse_mode)

        if data == "back_menu":
            await edit_or_send("📱 Main Menu", reply_markup=self.keyboards.main_menu())
            return

        if data == "menu_add":
            context.user_data.clear()
            await edit_or_send("➕ Select Category", reply_markup=self.keyboards.categories_keyboard())
            return

        if data.startswith("cat_"):
            idx = int(data.split('_')[1])
            category = self.keyboards.categories[idx]
            context.user_data['category'] = category

            # Check if we're selecting category for budget setting
            if context.user_data.get('action') == 'select_budget_category':
                context.user_data['action'] = 'set_budget'
                await edit_or_send(f"Setting budget for {category}\n\n💵 Enter budget amount:")
                return

            context.user_data['action'] = 'add_expense'
            await edit_or_send(
                f"Selected: {category}\n\n💵 Choose or enter amount:",
                reply_markup=KeyboardFactory.quick_amount_keyboard(),
            )
            return

        if data.startswith("amt_"):
            if 'category' not in context.user_data:
                await edit_or_send("Session expired. Use /menu to restart.")
                return
            amount_str = data.split('_')[1]
            if amount_str == "custom":
                context.user_data['awaiting'] = 'amount'
                await edit_or_send("✏️ Enter the amount:")
            else:
                context.user_data['amount'] = float(amount_str)
                context.user_data['awaiting'] = 'note'
                keyboard = [
                    [InlineKeyboardButton("⏭️ Skip Note", callback_data="skip_note")],
                    [InlineKeyboardButton("❌ Cancel", callback_data="cancel")],
                ]
                await edit_or_send(
                    f"Amount: ${context.user_data['amount']:.2f}\n\n📝 Add a note (or skip):",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                )
            return

        if data == "skip_note":
            if 'category' in context.user_data and 'amount' in context.user_data:
                category = context.user_data['category']
                amount = context.user_data['amount']
                response = self.expense_manager.add_expense(category, amount)
                context.user_data.clear()
                await edit_or_send(response, reply_markup=self.keyboards.main_menu())
            else:
                await edit_or_send("Session expired. Use /menu.")
            return

        if data in {"report_day", "report_week", "report_month"}:
            timeframe = data.split('_')[1]
            summary, chart_data = self.expense_manager.get_summary(timeframe)
            await edit_or_send(summary)
            if chart_data:
                chart = self.viz.pie_chart(chart_data, f"This {timeframe.title()} Spending")
                if chart:
                    await context.bot.send_photo(chat_id=chat_id, photo=InputFile(chart, filename=f"{timeframe}.png"), reply_markup=self.keyboards.main_menu())
            return

        if data == "menu_budget":
            status = self.expense_manager.get_budget_status()
            keyboard = [
                [InlineKeyboardButton("📝 Set Budget", callback_data="set_budget")],
                [InlineKeyboardButton("💵 Set Income", callback_data="set_income_proj")],
                [InlineKeyboardButton("🔙 Back", callback_data="back_menu")],
            ]
            await edit_or_send(status, reply_markup=InlineKeyboardMarkup(keyboard))
            return

        if data == "set_budget":
            context.user_data.clear()
            context.user_data['action'] = 'select_budget_category'
            await edit_or_send("Select a category to budget:", reply_markup=self.keyboards.categories_keyboard())
            return

        if data == "set_income_proj":
            context.user_data.clear()
            context.user_data['action'] = 'set_projected_income'
            await edit_or_send("Send: `[Source] [Amount]`", parse_mode='Markdown')
            return

        if data == "menu_income":
            context.user_data.clear()
            context.user_data['action'] = 'add_income'
            await edit_or_send("Send income: `[Source] [Amount] [Note]`", parse_mode='Markdown')
            return

        if data == "menu_recent":
            await self.recent(update, context)
            return

        if data == "menu_export":
            await self.export(update, context)
            return

        if data == "menu_settings":
            enabled = self.expense_manager.is_daily_report_enabled(chat_id)
            await edit_or_send("⚙️ Settings", reply_markup=KeyboardFactory.settings_keyboard(enabled), parse_mode='Markdown')
            return

        if data == "toggle_daily":
            new_state = self.expense_manager.toggle_daily_report(chat_id)
            status = "enabled ✅" if new_state else "disabled ❌"
            await edit_or_send(
                f"Daily report {status}",
                reply_markup=KeyboardFactory.settings_keyboard(new_state),
            )
            return

        if data == "cancel":
            context.user_data.clear()
            await edit_or_send("❌ Cancelled", reply_markup=self.keyboards.main_menu())
            return

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        logger.error("Unhandled error", exc_info=context.error)

    async def _prompt_budget_category(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        onboarding = context.user_data.get('onboarding', {})
        idx = onboarding.get('category_index', 0)
        categories = self.keyboards.categories
        if idx >= len(categories):
            context.user_data.pop('onboarding', None)
            status = self.expense_manager.get_budget_status()
            await update.message.reply_text(
                "✅ Onboarding complete. Current budget status:\n\n" + status,
                reply_markup=self.keyboards.main_menu(),
            )
            return
        category = categories[idx]
        await update.message.reply_text(
            f"Set budget for {category} (number). Type 'skip' to leave it blank.",
        )

    async def _handle_onboarding(self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
        onboarding = context.user_data.get('onboarding', {})
        year = onboarding.get('year', datetime.now().year)
        month = onboarding.get('month', datetime.now().month)

        if onboarding.get('stage') == 'income':
            if text.lower() != 'skip':
                try:
                    amount = float(text.replace('$', '').replace(',', ''))
                except ValueError:
                    await update.message.reply_text("❌ Enter a number for income (or 'skip').")
                    return
                response = self.expense_manager.set_projected_income(year, month, "Income", amount)
                await update.message.reply_text(response)
            onboarding['stage'] = 'categories'
            onboarding['category_index'] = 0
            context.user_data['onboarding'] = onboarding
            await update.message.reply_text("Now let's set budgets per category.")
            await self._prompt_budget_category(update, context)
            return

        if onboarding.get('stage') == 'categories':
            idx = onboarding.get('category_index', 0)
            categories = self.keyboards.categories
            if idx >= len(categories):
                context.user_data.pop('onboarding', None)
                status = self.expense_manager.get_budget_status()
                await update.message.reply_text(
                    "✅ Onboarding complete. Current budget status:\n\n" + status,
                    reply_markup=self.keyboards.main_menu(),
                )
                return

            category = categories[idx]
            if text.lower() != 'skip':
                try:
                    amount = float(text.replace('$', '').replace(',', ''))
                    response = self.expense_manager.set_budget(year, month, category, amount)
                    await update.message.reply_text(response)
                except ValueError:
                    await update.message.reply_text("❌ Enter a number for budget or 'skip'.")
                    return

            onboarding['category_index'] = idx + 1
            context.user_data['onboarding'] = onboarding
            await self._prompt_budget_category(update, context)
            return

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        text = update.message.text.strip()
        onboarding = context.user_data.get('onboarding')
        if onboarding:
            await self._handle_onboarding(update, context, text)
            return
        user_state = context.user_data

        if user_state.get('awaiting') == 'amount':
            try:
                amount = float(text.replace('$', '').replace(',', ''))
                user_state['amount'] = amount
                user_state['awaiting'] = 'note'
                keyboard = [
                    [InlineKeyboardButton("⏭️ Skip Note", callback_data="skip_note")],
                    [InlineKeyboardButton("❌ Cancel", callback_data="cancel")],
                ]
                await update.message.reply_text(
                    f"Amount: ${amount:.2f}\n\n📝 Add a note (or skip):",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                )
            except ValueError:
                await update.message.reply_text("❌ Invalid amount. Enter a number.")
            return

        if user_state.get('awaiting') == 'note':
            category = user_state.get('category')
            amount = user_state.get('amount')
            note = text
            if category is None or amount is None:
                await update.message.reply_text("Session expired. Use /menu.")
                return
            response = self.expense_manager.add_expense(category, amount, note)
            user_state.clear()
            await update.message.reply_text(response, reply_markup=self.keyboards.main_menu())
            return

        if user_state.get('action') == 'add_income':
            try:
                source, amount, note = ExpenseParser.parse_income(text)
                response = self.expense_manager.add_income(source, amount, note)
                user_state.clear()
                await update.message.reply_text(response, reply_markup=self.keyboards.main_menu())
            except ValueError as exc:
                await update.message.reply_text(f"❌ {exc}")
            return

        if user_state.get('action') == 'set_projected_income':
            try:
                source, amount, _ = ExpenseParser.parse_income(text)
                now = datetime.now()
                response = self.expense_manager.set_projected_income(now.year, now.month, source, amount)
                user_state.clear()
                await update.message.reply_text(response, reply_markup=self.keyboards.main_menu())
            except ValueError as exc:
                await update.message.reply_text(f"❌ {exc}")
            return

        if user_state.get('action') == 'set_budget' and 'category' in user_state:
            try:
                amount = float(text.replace('$', '').replace(',', ''))
                now = datetime.now()
                response = self.expense_manager.set_budget(now.year, now.month, user_state['category'], amount)
                user_state.clear()
                await update.message.reply_text(response, reply_markup=self.keyboards.main_menu())
            except ValueError:
                await update.message.reply_text("❌ Invalid amount. Enter a number.")
            return

        try:
            category_raw, amount, note = ExpenseParser.parse_expense(text)
        except ValueError as exc:
            await update.message.reply_text(f"❌ {exc}\nUse /menu for guided entry.")
            return

        matched_category = self.expense_manager.match_category(category_raw)
        if not matched_category:
            categories_list = "\n".join(self.keyboards.categories)
            await update.message.reply_text(f"❌ Category '{category_raw}' not recognized.\n\nAvailable:\n{categories_list}")
            return

        response = self.expense_manager.add_expense(matched_category, amount, note)
        await update.message.reply_text(response, reply_markup=self.keyboards.main_menu())

    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        caption = update.message.caption
        if not caption:
            await update.message.reply_text("Add a caption like `groceries 45.50 note`", parse_mode='Markdown')
            return
        try:
            category_raw, amount, note = ExpenseParser.parse_expense(caption)
        except ValueError as exc:
            await update.message.reply_text(f"❌ {exc}")
            return

        matched_category = self.expense_manager.match_category(category_raw)
        if not matched_category:
            await update.message.reply_text(f"❌ Category '{category_raw}' not recognized.")
            return

        photo = update.message.photo[-1]
        receipt_file_id = photo.file_id
        response = self.expense_manager.add_expense(matched_category, amount, note, receipt_file_id)
        await update.message.reply_text(response, reply_markup=self.keyboards.main_menu())

    async def send_daily_report(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        users = self.expense_manager.get_all_registered_users()
        for chat_id in users:
            try:
                summary, chart_data = self.expense_manager.get_summary("week")
                daily_data = self.expense_manager.get_daily_breakdown("week")
                await context.bot.send_message(chat_id=chat_id, text=f"🌙 End of Day Report\n\n{summary}")
                if chart_data:
                    chart = self.viz.pie_chart(chart_data, "This Week So Far")
                    if chart:
                        await context.bot.send_photo(chat_id=chat_id, photo=InputFile(chart, filename="daily_report.png"))
                if daily_data:
                    bar = self.viz.bar_chart(daily_data, "Daily Spending This Week")
                    if bar:
                        await context.bot.send_photo(chat_id=chat_id, photo=InputFile(bar, filename="daily_trend.png"))
            except Exception as exc:
                logger.error("Failed daily report to %s: %s", chat_id, exc)

    async def send_monthly_report(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        users = self.expense_manager.get_all_registered_users()
        for chat_id in users:
            try:
                status = self.expense_manager.get_budget_status()
                plan = self.expense_manager.get_monthly_plan()
                await context.bot.send_message(chat_id=chat_id, text=f"📅 Monthly Budget Report\n\n{status}")
                chart = self.viz.budget_chart(plan)
                if chart:
                    await context.bot.send_photo(chat_id=chat_id, photo=InputFile(chart, filename="monthly_budget.png"))
            except Exception as exc:
                logger.error("Failed monthly report to %s: %s", chat_id, exc)

    async def _send_summary_with_charts(self, update: Update, timeframe: str, include_trend: bool) -> None:
        summary, chart_data = self.expense_manager.get_summary(timeframe)
        await update.message.reply_text(summary)
        if chart_data:
            chart = self.viz.pie_chart(chart_data, f"This {timeframe.title()} Spending")
            if chart:
                await update.message.reply_photo(photo=InputFile(chart, filename=f"{timeframe}_breakdown.png"), caption="📊 Category Breakdown")
        if include_trend:
            daily_data = self.expense_manager.get_daily_breakdown(timeframe)
            if daily_data:
                bar = self.viz.bar_chart(daily_data, f"Daily Spending This {timeframe.title()}")
                if bar:
                    await update.message.reply_photo(photo=InputFile(bar, filename=f"{timeframe}_trend.png"), caption="📈 Daily Trend")


def main() -> None:
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        raise ValueError(
            "❌ TELEGRAM_BOT_TOKEN not set.\nGet it from @BotFather and export TELEGRAM_BOT_TOKEN='your-token'",
        )

    expense_manager = ExpenseManager()
    config = BotConfig(token=token)
    viz = VisualizationService()
    keyboards = KeyboardFactory(expense_manager.CATEGORIES)
    bot = BudgetBot(expense_manager, config, viz, keyboards)
    bot.run()


if __name__ == '__main__':
    main()
