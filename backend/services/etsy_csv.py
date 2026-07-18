import csv
import io
from sqlalchemy.orm import Session
from backend.models.tables import EtsyOrder, EtsyListing


def _guess_category(title: str) -> str:
    title_lower = title.lower()
    if any(w in title_lower for w in ["motorsport", "f1", "racing", "car", "motor", "bmw", "ford", "ferrari"]):
        return "Motorsport"
    elif any(w in title_lower for w in ["dog", "cat", "pet", "animal"]):
        return "Pet Prints"
    elif any(w in title_lower for w in ["landscape", "nature", "flower", "botanical"]):
        return "Nature"
    elif any(w in title_lower for w in ["abstract", "geometric", "pattern"]):
        return "Abstract"
    else:
        return "General"


def _sanitise_price(value: float) -> tuple[float, bool]:
    """Return (corrected_value, was_corrected).

    If value > 500 we assume it was supplied in pence and divide by 100.
    Values 500 or below are kept as-is.
    """
    if value > 500:
        return value / 100, True
    return value, False


def import_etsy_orders(file_content: str, db: Session) -> dict:
    """Parse Etsy orders CSV and create EtsyOrder records. Skips duplicate order_ids.

    Returns dict with keys: imported, corrected_pence_errors, skipped_duplicates.
    """
    reader = csv.DictReader(io.StringIO(file_content))
    count = 0
    corrected = 0
    skipped = 0

    for row in reader:
        order_id = (
            row.get("Order ID") or row.get("order_id") or row.get("id") or ""
        ).strip()
        if not order_id:
            continue

        title = (row.get("Item Name") or row.get("product_title") or row.get("title") or "").strip()
        quantity_str = (row.get("Quantity") or row.get("quantity") or "1").strip()
        price_str = (row.get("Item Total") or row.get("Price") or row.get("item_price") or "0").strip()

        try:
            quantity = int(quantity_str)
        except ValueError:
            quantity = 1

        price_str = price_str.replace("\xa3", "").replace("£", "").replace("$", "").replace(",", "").strip()
        try:
            raw_price = float(price_str)
        except ValueError:
            raw_price = 0.0

        item_price, was_corrected = _sanitise_price(raw_price)
        if was_corrected:
            corrected += 1

        category = _guess_category(title)
        revenue_estimate = item_price * quantity

        existing = db.query(EtsyOrder).filter(EtsyOrder.order_id == order_id).first()
        if existing:
            skipped += 1
            continue

        db.add(EtsyOrder(
            order_id=order_id,
            product_title=title,
            category=category,
            quantity=quantity,
            item_price=item_price,
            revenue_estimate=revenue_estimate,
        ))
        count += 1

    db.commit()
    return {
        "imported": count,
        "corrected_pence_errors": corrected,
        "skipped_duplicates": skipped,
    }


def import_etsy_listings(file_content: str, db: Session) -> dict:
    """Parse Etsy listings CSV and create EtsyListing records. Skips duplicate listing_ids.

    Returns dict with keys: imported, corrected_pence_errors, skipped_duplicates.
    """
    reader = csv.DictReader(io.StringIO(file_content))
    count = 0
    corrected = 0
    skipped = 0

    for row in reader:
        listing_id = (
            row.get("Listing ID") or row.get("listing_id") or row.get("id") or ""
        ).strip()
        if not listing_id:
            continue

        title = (row.get("Title") or row.get("title") or "").strip()
        price_str = (row.get("Price") or row.get("price") or "0").strip()
        status = (row.get("State") or row.get("status") or "active").strip().lower()

        price_str = price_str.replace("\xa3", "").replace("£", "").replace("$", "").replace(",", "").strip()
        try:
            raw_price = float(price_str)
        except ValueError:
            raw_price = 0.0

        price, was_corrected = _sanitise_price(raw_price)
        if was_corrected:
            corrected += 1

        category = _guess_category(title)

        existing = db.query(EtsyListing).filter(EtsyListing.listing_id == listing_id).first()
        if existing:
            skipped += 1
            continue

        db.add(EtsyListing(
            listing_id=listing_id,
            title=title,
            category=category,
            price=price,
            status=status,
        ))
        count += 1

    db.commit()
    return {
        "imported": count,
        "corrected_pence_errors": corrected,
        "skipped_duplicates": skipped,
    }
