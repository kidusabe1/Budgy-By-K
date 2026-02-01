"""Shared constants and helpers for My Budget."""

from difflib import get_close_matches
from typing import List, Dict, Optional

CATEGORIES: List[str] = [
    "🛒 Groceries",
    "🍽️ Dining Out",
    "🚗 Transportation",
    "🎬 Entertainment",
    "💅 Personal Care",
    "🏠 Housing",
    "💊 Healthcare",
    "📚 Education",
    "🎁 Gifts",
    "📱 Subscriptions",
    "🔧 Other",
]

CATEGORY_ALIASES: Dict[str, str] = {
    "groceries": "🛒 Groceries",
    "groc": "🛒 Groceries",
    "food": "🛒 Groceries",
    "dining": "🍽️ Dining Out",
    "restaurant": "🍽️ Dining Out",
    "eat": "🍽️ Dining Out",
    "transport": "🚗 Transportation",
    "transportation": "🚗 Transportation",
    "gas": "🚗 Transportation",
    "fuel": "🚗 Transportation",
    "uber": "🚗 Transportation",
    "bus": "🚗 Transportation",
    "taxi": "🚗 Transportation",
    "entertainment": "🎬 Entertainment",
    "fun": "🎬 Entertainment",
    "movie": "🎬 Entertainment",
    "games": "🎬 Entertainment",
    "personal": "💅 Personal Care",
    "care": "💅 Personal Care",
    "beauty": "💅 Personal Care",
    "housing": "🏠 Housing",
    "rent": "🏠 Housing",
    "utilities": "🏠 Housing",
    "electric": "🏠 Housing",
    "water": "🏠 Housing",
    "healthcare": "💊 Healthcare",
    "medical": "💊 Healthcare",
    "doctor": "💊 Healthcare",
    "pharmacy": "💊 Healthcare",
    "education": "📚 Education",
    "books": "📚 Education",
    "course": "📚 Education",
    "gifts": "🎁 Gifts",
    "gift": "🎁 Gifts",
    "present": "🎁 Gifts",
    "subscriptions": "📱 Subscriptions",
    "subscription": "📱 Subscriptions",
    "netflix": "📱 Subscriptions",
    "spotify": "📱 Subscriptions",
    "other": "🔧 Other",
    "misc": "🔧 Other",
}


def create_progress_bar(percentage: float, length: int = 8) -> str:
    """Create a text progress bar."""
    filled_length = int(length * percentage / 100)
    return "█" * filled_length + "░" * (length - filled_length)


def match_category(user_input: str) -> Optional[str]:
    """Match user input to a category using aliases and fuzzy matching."""
    user_input_lower = user_input.lower().strip()
    if not user_input_lower:
        return None
    if user_input_lower in CATEGORY_ALIASES:
        return CATEGORY_ALIASES[user_input_lower]
    for category in CATEGORIES:
        cat_name = category.split(" ", 1)[1].lower() if " " in category else category.lower()
        if user_input_lower in cat_name or cat_name in user_input_lower:
            return category
    all_names = list(CATEGORY_ALIASES.keys())
    matches = get_close_matches(user_input_lower, all_names, n=1, cutoff=0.6)
    if matches:
        return CATEGORY_ALIASES[matches[0]]
    return None
