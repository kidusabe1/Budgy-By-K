"""Parsing helpers for expenses/income."""

from typing import Tuple


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


__all__ = ["ExpenseParser"]
