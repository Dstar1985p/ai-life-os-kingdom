from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.services.etsy_csv import import_etsy_orders, import_etsy_listings

router = APIRouter(tags=["Import"])


@router.post("/import/etsy/orders")
async def import_orders(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    content = await file.read()
    count = import_etsy_orders(content.decode("utf-8"), db)
    return {"imported": count, "filename": file.filename}


@router.post("/import/etsy/listings")
async def import_listings(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    content = await file.read()
    count = import_etsy_listings(content.decode("utf-8"), db)
    return {"imported": count, "filename": file.filename}


@router.get("/data-sources")
def list_data_sources(db: Session = Depends(get_db)):
    from backend.models.tables import EtsyOrder, EtsyListing
    orders_count = db.query(EtsyOrder).count()
    listings_count = db.query(EtsyListing).count()
    return [
        {
            "name": "Etsy Orders",
            "type": "etsy_orders_csv",
            "record_count": orders_count,
            "status": "active" if orders_count > 0 else "empty",
        },
        {
            "name": "Etsy Listings",
            "type": "etsy_listings_csv",
            "record_count": listings_count,
            "status": "active" if listings_count > 0 else "empty",
        },
    ]
