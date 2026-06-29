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


def import_etsy_orders(file_content: str, db: Session) -> int:
    """Parse Etsy orders CSV and create/update EtsyOrder records. Returns count imported."""
    reader = csv.DictReader(io.StringIO(file_content))
    count = 0

    for row in reader:
        # Normalize column names (Etsy uses various formats)
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

        # Strip currency symbols
        price_str = price_str.replace("£", "").replace("$", "").replace(",", "").strip()
        try:
            item_price = float(price_str)
        except ValueError:
            item_price = 0.0

        # Detect pence error
        if item_price > 10000:
            item_price = item_price / 100

        category = _guess_category(title)
        revenue_estimate = item_price * quantity

        # Check if order already exists
        existing = db.query(EtsyOrder).filter(EtsyOrder.order_id == order_id).first()
        if existing:
            existing.product_title = title
            existing.quantity = quantity
            existing.item_price = item_price
            existing.revenue_estimate = revenue_estimate
            existing.category = category
        else:
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
    return count


def import_etsy_listings(file_content: str, db: Session) -> int:
    """Parse Etsy listings CSV and create/update EtsyListing records. Returns count imported."""
    reader = csv.DictReader(io.StringIO(file_content))
    count = 0

    for row in reader:
        listing_id = (
            row.get("Listing ID") or row.get("listing_id") or row.get("id") or ""
        ).strip()
        if not listing_id:
            continue

        title = (row.get("Title") or row.get("title") or "").strip()
        price_str = (row.get("Price") or row.get("price") or "0").strip()
        status = (row.get("State") or row.get("status") or "active").strip().lower()

        price_str = price_str.replace("£", "").replace("$", "").replace(",", "").strip()
        try:
            price = float(price_str)
        except ValueError:
            price = 0.0

        category = _guess_category(title)

        existing = db.query(EtsyListing).filter(EtsyListing.listing_id == listing_id).first()
        if existing:
            existing.title = title
            existing.price = price
            existing.status = status
            existing.category = category
        else:
            db.add(EtsyListing(
                listing_id=listing_id,
                title=title,
                category=category,
                price=price,
                status=status,
            ))
            count += 1

    db.commit()
    return count
