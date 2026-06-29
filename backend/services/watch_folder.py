"""Watch folder service — auto-imports Etsy CSV files."""
from __future__ import annotations

import csv
import io
import shutil
from pathlib import Path

from sqlalchemy.orm import Session

from backend.models.tables import Lesson
from backend.services.etsy_csv import import_etsy_orders, import_etsy_listings

_WATCH_DIR = Path("etsy_imports")
_PROCESSED_DIR = _WATCH_DIR / "processed"


def _ensure_dirs() -> None:
    _WATCH_DIR.mkdir(exist_ok=True)
    _PROCESSED_DIR.mkdir(exist_ok=True)


def _detect_csv_type(content: str) -> str:
    """Detect whether CSV is orders or listings based on headers."""
    reader = csv.reader(io.StringIO(content))
    try:
        headers = [h.lower() for h in next(reader)]
    except StopIteration:
        return "unknown"
    if any(h in headers for h in ["order id", "order_id", "item name", "item total"]):
        return "orders"
    if any(h in headers for h in ["listing id", "listing_id", "state", "title"]):
        return "listings"
    return "unknown"


def process_watch_folder(db: Session) -> dict:
    """Scan watch folder, import any new CSVs, move to processed/."""
    _ensure_dirs()

    csv_files = list(_WATCH_DIR.glob("*.csv"))
    results = []

    for csv_path in csv_files:
        try:
            with open(csv_path, newline="", encoding="utf-8-sig") as f:
                content = f.read()

            csv_type = _detect_csv_type(content)

            if csv_type == "orders":
                count = import_etsy_orders(content, db)
            elif csv_type == "listings":
                count = import_etsy_listings(content, db)
            else:
                count = 0

            # Move to processed
            dest = _PROCESSED_DIR / csv_path.name
            shutil.move(str(csv_path), str(dest))

            # Log lesson
            lesson_text = (
                f"Auto-imported Etsy CSV '{csv_path.name}': "
                f"{count} {csv_type} records imported."
            )
            lesson = Lesson(
                lesson=lesson_text,
                source="watch_folder",
                confidence_score=80.0,
            )
            db.add(lesson)
            db.commit()

            results.append(
                {
                    "file": csv_path.name,
                    "type": csv_type,
                    "imported": count,
                    "status": "ok",
                }
            )
        except Exception as exc:  # noqa: BLE001
            results.append(
                {
                    "file": csv_path.name,
                    "status": "error",
                    "error": str(exc),
                }
            )

    return {"files_processed": len(results), "results": results}
