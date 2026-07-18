from sqlalchemy.orm import Session
from backend.services.focus_engine import generate_daily_brief


def generate_morning_brief(db: Session) -> dict:
    """Delegate to focus_engine for full brief."""
    return generate_daily_brief(db)
