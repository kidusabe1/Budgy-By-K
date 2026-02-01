"""Shim to packaged SQLite backend."""

from my_budget.database.sqlite import ExpenseManager

__all__ = ["ExpenseManager"]
