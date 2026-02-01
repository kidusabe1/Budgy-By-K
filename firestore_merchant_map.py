"""Firestore-backed merchant→category mapping.

Drop-in replacement for ``merchant_map.py``.  Uses a top-level
``merchant_map`` Firestore collection instead of a local JSON file.
"""

import string
from typing import Dict


# ---------------------------------------------------------------------------
# Module-level Firestore client (lazy-initialised, overridable for tests)
# ---------------------------------------------------------------------------

_db = None
COLLECTION = "merchant_map"


def _get_db():
    global _db
    if _db is None:
        from google.cloud import firestore
        _db = firestore.Client()
    return _db


def set_db(client) -> None:
    """Override the Firestore client (used in tests)."""
    global _db
    _db = client


# ---------------------------------------------------------------------------
# Public API – identical signatures to merchant_map.py
# ---------------------------------------------------------------------------


def normalize_merchant(name: str) -> str:
    """Normalize merchant names for consistent matching."""
    if not name:
        return ""
    cleaned = name.strip().lower()
    cleaned = cleaned.strip(string.punctuation)
    while "  " in cleaned:
        cleaned = cleaned.replace("  ", " ")
    return cleaned


def load_map() -> Dict[str, str]:
    """Load the full merchant→category map from Firestore."""
    db = _get_db()
    docs = db.collection(COLLECTION).stream()
    return {doc.id: doc.to_dict().get("category", "") for doc in docs}


def save_map(data: Dict[str, str]) -> None:
    """Overwrite the entire merchant map collection with *data*."""
    db = _get_db()
    col = db.collection(COLLECTION)

    # Delete existing docs
    batch = db.batch()
    for doc in col.stream():
        batch.delete(doc.reference)
    batch.commit()

    # Write new docs
    batch = db.batch()
    for merchant, category in data.items():
        batch.set(col.document(merchant), {"category": category})
    if data:
        batch.commit()


def update_mapping(merchant: str, category: str) -> None:
    """Set (or update) the category for a single merchant."""
    normalized = normalize_merchant(merchant)
    if not normalized:
        return
    db = _get_db()
    db.collection(COLLECTION).document(normalized).set({"category": category})
