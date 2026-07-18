from fastapi import APIRouter
from backend.services.updater import check_for_update, get_update_status, apply_update

router = APIRouter(prefix="/update", tags=["update"])


@router.get("/status")
def update_status():
    return get_update_status()


@router.post("/check")
def update_check():
    return check_for_update()


@router.post("/apply")
def update_apply():
    return apply_update()
