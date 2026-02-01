"""Keyboard factory helpers."""

from typing import List

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup


class KeyboardFactory:
	"""Builds inline keyboards."""

	def __init__(self, categories: List[str]):
		self.categories = categories

	def menu_button(self) -> ReplyKeyboardMarkup:
		keyboard = [[KeyboardButton("📱 Menu")]]
		return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, is_persistent=True)

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
			[InlineKeyboardButton("�️ Delete Data", callback_data="menu_delete")],
			[InlineKeyboardButton("🔙 Back to Menu", callback_data="back_menu")],
		]
		return InlineKeyboardMarkup(keyboard)

	@staticmethod
	def delete_keyboard() -> InlineKeyboardMarkup:
		keyboard = [
			[InlineKeyboardButton("💸 Delete All Expenses", callback_data="delete_expenses")],
			[InlineKeyboardButton("💰 Delete All Income", callback_data="delete_income")],
			[InlineKeyboardButton("📋 Delete All Budgets", callback_data="delete_budgets")],
			[InlineKeyboardButton("🔙 Delete Last 5", callback_data="delete_last_5"), InlineKeyboardButton("🔙 Delete Last 10", callback_data="delete_last_10")],
			[InlineKeyboardButton("⚠️ DELETE EVERYTHING", callback_data="delete_all_confirm")],
			[InlineKeyboardButton("🔙 Back to Settings", callback_data="menu_settings")],
		]
		return InlineKeyboardMarkup(keyboard)

	@staticmethod
	def confirm_delete_keyboard(delete_type: str) -> InlineKeyboardMarkup:
		keyboard = [
			[InlineKeyboardButton("✅ Yes, Delete", callback_data=f"confirm_{delete_type}")],
			[InlineKeyboardButton("❌ Cancel", callback_data="menu_delete")],
		]
		return InlineKeyboardMarkup(keyboard)

	@staticmethod
	def income_source_keyboard() -> InlineKeyboardMarkup:
		keyboard = [
			[InlineKeyboardButton("💼 Salary", callback_data="inc_src_Salary"), InlineKeyboardButton("💻 Freelance", callback_data="inc_src_Freelance")],
			[InlineKeyboardButton("🎯 Bonus", callback_data="inc_src_Bonus"), InlineKeyboardButton("💰 Investment", callback_data="inc_src_Investment")],
			[InlineKeyboardButton("🎁 Gift", callback_data="inc_src_Gift"), InlineKeyboardButton("🔄 Refund", callback_data="inc_src_Refund")],
			[InlineKeyboardButton("➕ Other", callback_data="inc_src_Other"), InlineKeyboardButton("✏️ Custom", callback_data="inc_src_custom")],
			[InlineKeyboardButton("❌ Cancel", callback_data="cancel")],
		]
		return InlineKeyboardMarkup(keyboard)

	@staticmethod
	def income_amount_keyboard() -> InlineKeyboardMarkup:
		keyboard = [
			[InlineKeyboardButton("$100", callback_data="inc_amt_100"), InlineKeyboardButton("$250", callback_data="inc_amt_250"), InlineKeyboardButton("$500", callback_data="inc_amt_500")],
			[InlineKeyboardButton("$1000", callback_data="inc_amt_1000"), InlineKeyboardButton("$1500", callback_data="inc_amt_1500"), InlineKeyboardButton("$2000", callback_data="inc_amt_2000")],
			[InlineKeyboardButton("$2500", callback_data="inc_amt_2500"), InlineKeyboardButton("$3000", callback_data="inc_amt_3000"), InlineKeyboardButton("$5000", callback_data="inc_amt_5000")],
			[InlineKeyboardButton("✏️ Custom Amount", callback_data="inc_amt_custom")],
			[InlineKeyboardButton("❌ Cancel", callback_data="cancel")],
		]
		return InlineKeyboardMarkup(keyboard)

	@staticmethod
	def income_note_keyboard() -> InlineKeyboardMarkup:
		keyboard = [
			[InlineKeyboardButton("⏭️ Skip Note", callback_data="inc_skip_note")],
			[InlineKeyboardButton("❌ Cancel", callback_data="cancel")],
		]
		return InlineKeyboardMarkup(keyboard)


__all__ = ["KeyboardFactory"]
