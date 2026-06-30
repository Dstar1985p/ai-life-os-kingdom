"""Revenue scenario modelling — pure maths, no LLM calls."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from backend.models.tables import EtsyListing, RevenueEntry


def _current_monthly_gbp(db: Session) -> float:
    """Estimate current monthly revenue from the last 30 days of income entries."""
    from datetime import timedelta

    cutoff = datetime.utcnow() - timedelta(days=30)
    entries = (
        db.query(RevenueEntry)
        .filter(RevenueEntry.entry_type == "income", RevenueEntry.recorded_at >= cutoff)
        .all()
    )
    return round(sum(e.amount for e in entries), 2)


def _avg_revenue_per_listing(db: Session) -> float:
    from datetime import timedelta

    cutoff = datetime.utcnow() - timedelta(days=30)
    income = (
        db.query(RevenueEntry)
        .filter(
            RevenueEntry.venture == "Pitwall Classics",
            RevenueEntry.entry_type == "income",
            RevenueEntry.recorded_at >= cutoff,
        )
        .all()
    )
    listing_count = db.query(EtsyListing).filter(EtsyListing.status == "active").count()
    total_income = sum(e.amount for e in income)
    if listing_count == 0:
        return 2.50  # sensible default
    return round(total_income / listing_count, 4)


def run_scenario(db: Session, scenario_type: str, params: dict[str, Any]) -> dict:
    current = _current_monthly_gbp(db)

    if scenario_type == "double_listings":
        listing_count = db.query(EtsyListing).filter(EtsyListing.status == "active").count()
        avg_rev = _avg_revenue_per_listing(db)
        new_count = (listing_count or 10) * 2
        projected = round(avg_rev * new_count, 2)
        delta = round(projected - current, 2)
        delta_pct = round((delta / current * 100) if current > 0 else 0, 1)
        return {
            "scenario_type": scenario_type,
            "current_monthly_gbp": current,
            "projected_monthly_gbp": projected,
            "delta_gbp": delta,
            "delta_pct": delta_pct,
            "time_to_first_revenue_days": 7,
            "confidence": "medium",
            "assumptions": [
                f"Current active listings: {listing_count}",
                f"Average revenue per listing/month: £{avg_rev}",
                f"Doubling listings to {new_count} maintains same conversion rate",
                "No increase in marketing spend assumed",
            ],
        }

    elif scenario_type == "viral_track":
        track_title = params.get("track_title", "Unnamed Track")
        price_per_license = float(params.get("price_per_license", 25.0))
        license_count = 1000
        projected_extra = round(price_per_license * license_count, 2)
        projected = round(current + projected_extra, 2)
        delta = round(projected_extra, 2)
        delta_pct = round((delta / current * 100) if current > 0 else 0, 1)
        return {
            "scenario_type": scenario_type,
            "current_monthly_gbp": current,
            "projected_monthly_gbp": projected,
            "delta_gbp": delta,
            "delta_pct": delta_pct,
            "time_to_first_revenue_days": 1,
            "confidence": "low",
            "assumptions": [
                f"Track: '{track_title}'",
                f"Price per license: £{price_per_license}",
                f"1,000 licenses sold in month of virality",
                "Viral event probability is not modelled here",
                "Assumes non-exclusive licensing",
            ],
        }

    elif scenario_type == "new_product_type":
        margin = float(params.get("margin_pct", 35.0)) / 100.0
        volume = int(params.get("monthly_volume", 50))
        avg_price = float(params.get("avg_price_gbp", 18.0))
        projected_extra = round(avg_price * margin * volume, 2)
        projected = round(current + projected_extra, 2)
        delta = projected_extra
        delta_pct = round((delta / current * 100) if current > 0 else 0, 1)
        return {
            "scenario_type": scenario_type,
            "current_monthly_gbp": current,
            "projected_monthly_gbp": projected,
            "delta_gbp": delta,
            "delta_pct": delta_pct,
            "time_to_first_revenue_days": 14,
            "confidence": "medium",
            "assumptions": [
                f"New POD category at avg price £{avg_price}",
                f"Margin: {params.get('margin_pct', 35)}%",
                f"Estimated monthly volume: {volume} units",
                "Setup and design costs not included",
                "Printify production time 5-10 days",
            ],
        }

    elif scenario_type == "reduce_prices":
        discount_pct = float(params.get("discount_pct", 20.0))
        volume_uplift_pct = float(params.get("volume_uplift_pct", discount_pct * 1.5))
        new_revenue = current * (1 - discount_pct / 100) * (1 + volume_uplift_pct / 100)
        projected = round(new_revenue, 2)
        delta = round(projected - current, 2)
        delta_pct = round((delta / current * 100) if current > 0 else 0, 1)
        return {
            "scenario_type": scenario_type,
            "current_monthly_gbp": current,
            "projected_monthly_gbp": projected,
            "delta_gbp": delta,
            "delta_pct": delta_pct,
            "time_to_first_revenue_days": 3,
            "confidence": "low",
            "assumptions": [
                f"Price reduction: {discount_pct}%",
                f"Assumed volume uplift: {volume_uplift_pct:.0f}% (1.5× the discount rate)",
                "Price elasticity assumption is unvalidated",
                "Assumes no competitor response",
            ],
        }

    elif scenario_type == "add_platform":
        platform_name = params.get("platform_name", "New Platform")
        estimated_monthly_gbp = float(params.get("estimated_monthly_gbp", 50.0))
        projected = round(current + estimated_monthly_gbp, 2)
        delta = estimated_monthly_gbp
        delta_pct = round((delta / current * 100) if current > 0 else 0, 1)
        return {
            "scenario_type": scenario_type,
            "current_monthly_gbp": current,
            "projected_monthly_gbp": projected,
            "delta_gbp": delta,
            "delta_pct": delta_pct,
            "time_to_first_revenue_days": 30,
            "confidence": "low",
            "assumptions": [
                f"Platform: {platform_name}",
                f"Estimated monthly revenue: £{estimated_monthly_gbp}",
                "30-day ramp-up before first payout typical",
                "Catalogue upload time not modelled",
                "Platform acceptance not guaranteed",
            ],
        }

    else:
        return {
            "scenario_type": scenario_type,
            "error": f"Unknown scenario type: {scenario_type}",
            "valid_types": [
                "double_listings",
                "viral_track",
                "new_product_type",
                "reduce_prices",
                "add_platform",
            ],
        }


def get_scenario_presets(db: Session) -> list[dict]:
    listing_count = db.query(EtsyListing).filter(EtsyListing.status == "active").count()
    return [
        run_scenario(db, "double_listings", {}),
        run_scenario(db, "viral_track", {"track_title": "Midnight Rally", "price_per_license": 25.0}),
        run_scenario(db, "new_product_type", {"margin_pct": 35, "monthly_volume": 50, "avg_price_gbp": 18.0}),
        run_scenario(db, "reduce_prices", {"discount_pct": 15.0}),
        run_scenario(db, "add_platform", {"platform_name": "Musicbed", "estimated_monthly_gbp": 75.0}),
    ]
