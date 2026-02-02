"""Local JSON-file merchant map."""

import json
import os
import string
from pathlib import Path
from typing import Dict

MAP_FILE = Path(os.getenv("APPLE_PAY_DB_DIR", "user_data")) / "merchant_map.json"
MAP_FILE.parent.mkdir(parents=True, exist_ok=True)


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
	if not MAP_FILE.exists():
		return {}
	try:
		with MAP_FILE.open("r", encoding="utf-8") as f:
			return json.load(f)
	except Exception:
		return {}


def save_map(data: Dict[str, str]) -> None:
	MAP_FILE.parent.mkdir(parents=True, exist_ok=True)
	with MAP_FILE.open("w", encoding="utf-8") as f:
		json.dump(data, f, ensure_ascii=False, indent=2)


def update_mapping(merchant: str, category: str) -> None:
	normalized = normalize_merchant(merchant)
	if not normalized:
		return
	data = load_map()
	data[normalized] = category
	save_map(data)
