"""Merchant mapping backend selector.

Always writes to the local JSON map so tests that monkeypatch ``MAP_FILE``
continue to work, and optionally mirrors to Firestore when enabled.
"""

import os

from .file_store import MAP_FILE, load_map as _file_load_map, normalize_merchant, save_map as _file_save_map, update_mapping as _file_update_mapping


def _use_firestore() -> bool:
	return os.getenv("USE_FIRESTORE", "").lower() in ("true", "1", "yes")


def _try_firestore_import():
	try:
		from . import firestore_store as _fs  # noqa: WPS433 (runtime import)
		return _fs
	except Exception:
		return None


def load_map():
	fs = _try_firestore_import() if _use_firestore() else None
	if fs:
		try:
			return fs.load_map()
		except Exception:
			pass
	return _file_load_map()


def save_map(data):
	# Always persist locally for tests/dev.
	_file_save_map(data)
	fs = _try_firestore_import() if _use_firestore() else None
	if fs:
		try:
			fs.save_map(data)
		except Exception:
			pass


def update_mapping(merchant: str, category: str):
	# Always write to local file so MAP_FILE monkeypatches are honored.
	_file_update_mapping(merchant, category)
	fs = _try_firestore_import() if _use_firestore() else None
	if fs:
		try:
			fs.update_mapping(merchant, category)
		except Exception:
			pass


def set_db(client):
	fs = _try_firestore_import()
	if fs and hasattr(fs, "set_db"):
		return fs.set_db(client)
	return None


__all__ = [
	"MAP_FILE",
	"load_map",
	"normalize_merchant",
	"save_map",
	"update_mapping",
	"set_db",
]
