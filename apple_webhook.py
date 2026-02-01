import base64
import json
import logging
import os
import urllib.parse
import urllib.request
from datetime import datetime
from difflib import get_close_matches
from typing import Optional

from dotenv import load_dotenv

from flask import Flask, jsonify, request

if os.getenv("USE_FIRESTORE", "").lower() in ("true", "1", "yes"):
    from firestore_database import FirestoreExpenseManager as ExpenseManager
    from firestore_merchant_map import load_map, normalize_merchant, save_map, update_mapping
else:
    from database import ExpenseManager
    from merchant_map import MAP_FILE, load_map, normalize_merchant, save_map, update_mapping


load_dotenv()
logger = logging.getLogger(__name__)

# Allow overriding DB location and target user for testing or multi-user setups
if not os.getenv("USE_FIRESTORE", "").lower() in ("true", "1", "yes"):
    ExpenseManager.DB_DIR = os.getenv("APPLE_PAY_DB_DIR", ExpenseManager.DB_DIR)
DEFAULT_USER_KEY = os.getenv("APPLE_PAY_USER_KEY", "default_user")

# Map merchants to categories (extend as needed)
MERCHANT_MAP = {
    "uber": "🚗 Transportation",
    "lyft": "🚗 Transportation",
    "mta": "🚗 Transportation",
    "whole foods": "🛒 Groceries",
    "trader joe": "🛒 Groceries",
    "target": "🏠 Housing",
    "netflix": "📱 Subscriptions",
    "spotify": "📱 Subscriptions",
    "starbucks": "🍽️ Dining Out",
    "dunkin": "🍽️ Dining Out",
}

ALLOWED_CATEGORIES = ExpenseManager.CATEGORIES
SHORT_OPTIONS = [
    "🛒 Groceries",
    "🍽️ Dining Out",
    "🚗 Transportation",
    "💊 Healthcare",
    "📱 Subscriptions",
    "🏠 Housing",
    "🎬 Entertainment",
    "🔧 Other",
]


def _match_allowed(label: str) -> str:
    """Map a free-form label to one of the allowed categories."""
    if not label:
        return "🔧 Other"
    l = label.lower().strip()
    # Direct emoji match
    for cat in ALLOWED_CATEGORIES:
        if l == cat.lower():
            return cat
    # Keyword to category mapping
    keyword_map = {
        "grocery": "🛒 Groceries",
        "grocer": "🛒 Groceries",
        "market": "🛒 Groceries",
        "super": "🛒 Groceries",
        "food": "🛒 Groceries",
        "dining": "🍽️ Dining Out",
        "restaurant": "🍽️ Dining Out",
        "coffee": "🍽️ Dining Out",
        "cafe": "🍽️ Dining Out",
        "transport": "🚗 Transportation",
        "taxi": "🚗 Transportation",
        "bus": "🚗 Transportation",
        "train": "🚗 Transportation",
        "fuel": "🚗 Transportation",
        "gas": "🚗 Transportation",
        "health": "💊 Healthcare",
        "pharm": "💊 Healthcare",
        "med": "💊 Healthcare",
        "doctor": "💊 Healthcare",
        "rent": "🏠 Housing",
        "home": "🏠 Housing",
        "housing": "🏠 Housing",
        "subscription": "📱 Subscriptions",
        "subs": "📱 Subscriptions",
        "entertain": "🎬 Entertainment",
        "movie": "🎬 Entertainment",
    }
    for key, cat in keyword_map.items():
        if key in l:
            return cat
    # Fuzzy to allowed categories
    close = get_close_matches(l, [c.lower() for c in ALLOWED_CATEGORIES], n=1, cutoff=0.6)
    if close:
        for cat in ALLOWED_CATEGORIES:
            if cat.lower() == close[0]:
                return cat
    return "🔧 Other"


def _predict_with_gemini(name: str) -> Optional[str]:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        logger.info("GOOGLE_API_KEY not set; skipping Gemini categorization")
        return None
    try:
        import google.generativeai as genai
    except Exception:
        logger.exception("Failed to import google.generativeai; install google-generativeai")
        return None

    genai.configure(api_key=api_key)
    prompt = (
        "You categorize merchant names into one of these categories: "
        f"{', '.join(ALLOWED_CATEGORIES)}. "
        "Return ONLY the category text without explanation."
    )
    examples = [
        ("שופרסל אונליין", "🛒 Groceries"),
        ("רמי לוי", "🛒 Groceries"),
        ("yellow", "🚗 Transportation"),
        ("דן אוטובוסים", "🚗 Transportation"),
        ("ארומה סנטר", "🍽️ Dining Out"),
        ("netflix", "📱 Subscriptions"),
        ("paz תחנת דלק", "🚗 Transportation"),
    ]
    few_shot = "\n".join(f"{q} -> {a}" for q, a in examples)
    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        resp = model.generate_content(
            f"{prompt}\n\nExamples:\n{few_shot}\n\nMerchant: {name}\nCategory:",
            safety_settings={
                genai.types.HarmCategory.HARM_CATEGORY_HATE_SPEECH: genai.types.HarmBlockThreshold.BLOCK_NONE,
                genai.types.HarmCategory.HARM_CATEGORY_HARASSMENT: genai.types.HarmBlockThreshold.BLOCK_NONE,
                genai.types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: genai.types.HarmBlockThreshold.BLOCK_NONE,
                genai.types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: genai.types.HarmBlockThreshold.BLOCK_NONE,
            },
        )
        text = (resp.candidates[0].content.parts[0].text or "").strip() if resp.candidates else ""
        return _match_allowed(text)
    except Exception:
        logger.exception("Gemini categorization failed")
        return None


def _send_unknown_prompt(merchant: str):
    token = os.getenv("APPLE_PAY_BOT_TOKEN")
    chat_id = os.getenv("APPLE_PAY_CHAT_ID")
    if not token or not chat_id:
        return

    encoded_merchant = urllib.parse.quote_plus(merchant)
    keyboard = [[{"text": cat, "callback_data": f"mapcat:{encoded_merchant}:{idx}"}] for idx, cat in enumerate(SHORT_OPTIONS)]
    payload = {
        "chat_id": chat_id,
        "text": f"Unknown merchant: {merchant}\nTap to categorize:",
        "reply_markup": json.dumps({"inline_keyboard": keyboard}),
    }
    data = urllib.parse.urlencode(payload).encode("utf-8")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass


def predict_category(merchant: str) -> str:
    """Predict a category using map, fuzzy, optional LLM, then fallback."""
    normalized = normalize_merchant(merchant)
    if not normalized:
        return "🔧 Other"

    # 1) Persistent map
    cached = load_map()
    if normalized in cached:
        cached_cat = cached[normalized]
        if cached_cat != "🔧 Other":
            return cached_cat
        # Drop stale "Other" so we can re-evaluate via heuristics/LLM
        cached.pop(normalized, None)
        save_map(cached)

    # 2) Exact/contains map
    for key, cat in MERCHANT_MAP.items():
        if key in normalized:
            update_mapping(normalized, cat)
            return cat

    # 3) Fuzzy against known keys (map + cache keys)
    candidates = set(MERCHANT_MAP.keys()) | set(cached.keys())
    close = get_close_matches(normalized, candidates, n=1, cutoff=0.8)
    if close:
        cat = cached.get(close[0], MERCHANT_MAP.get(close[0], "🔧 Other"))
        update_mapping(normalized, cat)
        return cat

    # 4) Keyword heuristics
    if "coffee" in normalized or "cafe" in normalized or "קפה" in normalized:
        return "🍽️ Dining Out"
    if "market" in normalized or "grocery" in normalized or "סופר" in normalized:
        return "🛒 Groceries"
    if any(k in normalized for k in ["uber", "lyft", "taxi", "bus", "train", "דלק", "מונית", "רכבת"]):
        return "🚗 Transportation"
    if "pharm" in normalized or "drug" in normalized or "pharmacy" in normalized or "קופה" in normalized:
        return "💊 Healthcare"
    if "rent" in normalized or "apt" in normalized or "שכירות" in normalized:
        return "🏠 Housing"

    # 5) Gemini (optional)
    llm_cat = _predict_with_gemini(normalized)
    if llm_cat:
        update_mapping(normalized, llm_cat)
        return llm_cat

    # 6) Fallback
    _send_unknown_prompt(merchant)
    return "🔧 Other"


app = Flask(__name__)


@app.route("/webhook/apple_pay", methods=["POST"])
def apple_pay_webhook():
    data = request.get_json(silent=True) or {}
    merchant = data.get("merchant", "Unknown")
    raw_amount = data.get("amount", 0)
    try:
        amount = float(raw_amount)
    except (TypeError, ValueError):
        amount = 0.0

    card = data.get("card_name", "Apple Pay")
    date_str = data.get("date")
    tx_date = None
    if date_str:
        try:
            tx_date = datetime.fromisoformat(str(date_str))
        except Exception:
            tx_date = None

    category = predict_category(merchant)
    note = f"Apple Pay ({card})"

    # Save into the per-user database configured via env
    manager = ExpenseManager(user_id=DEFAULT_USER_KEY)
    manager.add_expense(category=category, amount=amount, note=note, date_override=tx_date)
    # Cache the mapping only when we have a confident category (avoid locking "Other")
    if category != "🔧 Other":
        update_mapping(normalize_merchant(merchant), category)

    return jsonify({"status": "success", "category": category}), 200


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
