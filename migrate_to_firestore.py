#!/usr/bin/env python3
"""One-time migration: SQLite databases → Firestore.

Reads every ``user_data/*.db`` file and the ``merchant_map.json``,
then writes everything into Firestore collections.

Usage:
    export GOOGLE_CLOUD_PROJECT=your-project-id
    python migrate_to_firestore.py
"""

import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from google.cloud import firestore


DATA_DIR = Path("user_data")
MERCHANT_MAP_FILE = DATA_DIR / "merchant_map.json"


def _parse_date(date_str: str) -> datetime:
    """Best-effort parse of the date strings stored in SQLite."""
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt)
        except (ValueError, TypeError):
            continue
    return datetime.now()


def migrate_user(db_path: Path, user_id: str, db: firestore.Client) -> None:
    """Migrate a single user's SQLite database into Firestore."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    user_ref = db.collection("users").document(user_id)

    # ---- transactions ----
    cursor.execute("SELECT date, category, amount, note, receipt_file_id FROM transactions ORDER BY date")
    count = 0
    for row in cursor.fetchall():
        user_ref.collection("transactions").add({
            "date": _parse_date(row["date"]),
            "category": row["category"],
            "amount": row["amount"],
            "note": row["note"] or "",
            "receipt_file_id": row["receipt_file_id"],
        })
        count += 1
    print(f"  transactions: {count}")

    # ---- income ----
    cursor.execute("SELECT date, source, amount, note, is_projected FROM income ORDER BY date")
    count = 0
    for row in cursor.fetchall():
        user_ref.collection("income").add({
            "date": _parse_date(row["date"]),
            "source": row["source"],
            "amount": row["amount"],
            "note": row["note"] or "",
            "is_projected": bool(row["is_projected"]),
        })
        count += 1
    print(f"  income: {count}")

    # ---- budget_plans ----
    cursor.execute("SELECT year, month, category, planned_amount FROM budget_plans")
    count = 0
    for row in cursor.fetchall():
        doc_id = f"{row['year']:04d}-{row['month']:02d}_{row['category']}"
        user_ref.collection("budget_plans").document(doc_id).set({
            "year": row["year"],
            "month": row["month"],
            "category": row["category"],
            "planned_amount": row["planned_amount"],
        })
        count += 1
    print(f"  budget_plans: {count}")

    # ---- projected_income ----
    cursor.execute("SELECT year, month, source, amount FROM projected_income")
    count = 0
    for row in cursor.fetchall():
        doc_id = f"{row['year']:04d}-{row['month']:02d}_{row['source']}"
        user_ref.collection("projected_income").document(doc_id).set({
            "year": row["year"],
            "month": row["month"],
            "source": row["source"],
            "amount": row["amount"],
        })
        count += 1
    print(f"  projected_income: {count}")

    # ---- user_settings → user profile document ----
    cursor.execute(
        "SELECT chat_id, daily_report_enabled, report_time, onboarding_completed "
        "FROM user_settings LIMIT 1"
    )
    settings = cursor.fetchone()
    if settings:
        user_ref.set(
            {
                "chat_id": settings["chat_id"],
                "daily_report_enabled": bool(settings["daily_report_enabled"]),
                "report_time": settings["report_time"] or "21:00",
                "onboarding_completed": bool(settings["onboarding_completed"]),
            },
            merge=True,
        )
        print(f"  user_settings: migrated (chat_id={settings['chat_id']})")

    conn.close()


def migrate_merchant_map(db: firestore.Client) -> None:
    """Migrate merchant_map.json to the ``merchant_map`` Firestore collection."""
    if not MERCHANT_MAP_FILE.exists():
        print("No merchant_map.json found – skipping.")
        return

    with MERCHANT_MAP_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)

    batch = db.batch()
    count = 0
    for merchant, category in data.items():
        batch.set(
            db.collection("merchant_map").document(merchant),
            {"category": category},
        )
        count += 1
    batch.commit()
    print(f"merchant_map: {count} entries migrated")


def main() -> None:
    db = firestore.Client()
    print(f"Connected to project: {db.project}\n")

    if not DATA_DIR.exists():
        print(f"No {DATA_DIR}/ directory found. Nothing to migrate.")
        sys.exit(0)

    db_files = sorted(DATA_DIR.glob("*.db"))
    if not db_files:
        print("No .db files found in user_data/.")
    else:
        for db_path in db_files:
            user_id = db_path.stem
            print(f"Migrating user: {user_id} ({db_path})")
            migrate_user(db_path, user_id, db)
            print()

    migrate_merchant_map(db)
    print("\nMigration complete.")


if __name__ == "__main__":
    main()
