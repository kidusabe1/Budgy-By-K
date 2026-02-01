"""Database backend selector for My Budget."""

import os


def _use_firestore() -> bool:
	return os.getenv("USE_FIRESTORE", "").lower() in ("true", "1", "yes")


if _use_firestore():
	from .firestore import FirestoreExpenseManager as ExpenseManager  # noqa: F401
else:
	from .sqlite import ExpenseManager  # noqa: F401

__all__ = ["ExpenseManager"]
