from collections import Counter
from sqlalchemy.orm import Session
from backend.models.tables import Opportunity, EtsyOrder, EtsyListing


def get_revenue_insights(db: Session) -> dict:
    orders = db.query(EtsyOrder).all()
    opps = db.query(Opportunity).filter(Opportunity.status != "archived").all()

    # Find top category
    categories = [o.category for o in orders] + [o.category for o in opps]
    cat_counter = Counter(categories)
    top_category = cat_counter.most_common(1)[0][0] if cat_counter else "Unknown"

    # Find top theme (based on opportunities)
    top_opp = sorted(opps, key=lambda x: x.kingdom_score, reverse=True)
    top_theme = top_opp[0].title if top_opp else "Revenue Recon"

    # Revenue concentration
    total_revenue = sum(o.revenue_estimate for o in orders) if orders else 0
    if orders:
        cat_revenue = {}
        for o in orders:
            cat_revenue[o.category] = cat_revenue.get(o.category, 0) + o.revenue_estimate
        if cat_revenue:
            top_cat_rev = max(cat_revenue.values())
            concentration = round(top_cat_rev / total_revenue * 100, 1) if total_revenue > 0 else 0
        else:
            concentration = 0
    else:
        concentration = 0

    # Recommended next product
    listings = db.query(EtsyListing).all()
    if listings:
        avg_price = sum(listing.price for listing in listings) / len(listings)
        recommended = f"Create a new listing in {top_category} at ~£{avg_price:.0f}"
    else:
        recommended = f"Validate demand in {top_category} with a test listing"

    return {
        "top_theme": top_theme,
        "top_category": top_category,
        "total_estimated_revenue": round(total_revenue, 2),
        "concentration_pct": concentration,
        "recommended_next_product": recommended,
        "confidence": 65 if orders else 40,
        "data_points": len(orders),
    }


def get_revenue_trends(db: Session) -> list:
    orders = db.query(EtsyOrder).order_by(EtsyOrder.imported_at.asc()).all()

    if not orders:
        return []

    # Group by month
    monthly = {}
    for o in orders:
        key = o.imported_at.strftime("%Y-%m") if o.imported_at else "unknown"
        if key not in monthly:
            monthly[key] = {"month": key, "revenue": 0, "orders": 0}
        monthly[key]["revenue"] += o.revenue_estimate
        monthly[key]["orders"] += 1

    trends = list(monthly.values())
    for t in trends:
        t["revenue"] = round(t["revenue"], 2)
    return trends


def validate_revenue(db: Session) -> dict:
    orders = db.query(EtsyOrder).all()
    issues = []
    confidence = 90

    # Check for pence errors (value > 10000 likely in pence)
    pence_errors = [o for o in orders if o.item_price > 10000]
    if pence_errors:
        issues.append(f"{len(pence_errors)} orders may have prices in pence (value > 10000)")
        confidence -= 20

    # Check for duplicates
    order_ids = [o.order_id for o in orders]
    duplicates = len(order_ids) - len(set(order_ids))
    if duplicates > 0:
        issues.append(f"{duplicates} duplicate order IDs detected")
        confidence -= 15

    # Check for zero revenue
    zero_rev = [o for o in orders if o.revenue_estimate == 0]
    if zero_rev:
        issues.append(f"{len(zero_rev)} orders have zero revenue estimate")
        confidence -= 10

    return {
        "confidence": max(0, confidence),
        "issues": issues,
        "total_orders": len(orders),
        "issues_count": len(issues),
        "is_clean": len(issues) == 0,
    }
