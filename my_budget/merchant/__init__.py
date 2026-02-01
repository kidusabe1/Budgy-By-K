"""Merchant mapping backend selector."""

import os


def _use_firestore() -> bool:
	return os.getenv("USE_FIRESTORE", "").lower() in ("true", "1", "yes")


if _use_firestore():
	from .firestore_store import load_map, normalize_merchant, save_map, set_db, update_mapping  # noqa: F401
	MAP_FILE = None
else:
	from .file_store import MAP_FILE, load_map, normalize_merchant, save_map, update_mapping  # noqa: F401

__all__ = [
	"load_map",
	"normalize_merchant",
	"save_map",
	"update_mapping",
]

if not _use_firestore():
	__all__.append("MAP_FILE")

# set_db is only available for the Firestore backend (tests can import explicitly)
