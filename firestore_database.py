"""Shim to packaged Firestore backend."""

from my_budget.database.firestore import FirestoreExpenseManager

__all__ = ["FirestoreExpenseManager"]
