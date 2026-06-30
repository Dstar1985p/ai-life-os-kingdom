"""Database backup routes — creates timestamped SQLite snapshots."""
from __future__ import annotations

import logging
import os
import shutil
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/backup", tags=["Backup"])

_data_dir = Path(os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", "."))
_db_path = _data_dir / "kingdom_alpha.db"
_backup_dir = _data_dir / "backups"


def _ensure_backup_dir() -> Path:
    _backup_dir.mkdir(parents=True, exist_ok=True)
    return _backup_dir


def _list_backups() -> list[dict]:
    bdir = _ensure_backup_dir()
    files = sorted(bdir.glob("kingdom_alpha_*.db"), reverse=True)
    results = []
    for f in files:
        stat = f.stat()
        results.append({
            "id": f.stem,
            "filename": f.name,
            "created_at": datetime.utcfromtimestamp(stat.st_mtime).isoformat(),
            "size_kb": round(stat.st_size / 1024, 1),
        })
    return results


@router.get("/create")
def backup_create():
    """Create a timestamped copy of the SQLite database."""
    if not _db_path.exists():
        raise HTTPException(status_code=404, detail="Database file not found")
    bdir = _ensure_backup_dir()
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    dest = bdir / f"kingdom_alpha_{ts}.db"
    try:
        shutil.copy2(_db_path, dest)
    except Exception as exc:
        logger.exception("Backup failed")
        raise HTTPException(status_code=500, detail=f"Backup failed: {exc}")
    stat = dest.stat()
    logger.info("Backup created: %s (%.1f KB)", dest.name, stat.st_size / 1024)
    # Keep only last 10 backups
    all_backups = sorted(bdir.glob("kingdom_alpha_*.db"))
    for old in all_backups[:-10]:
        old.unlink(missing_ok=True)
    return {
        "status": "ok",
        "backup_id": f"kingdom_alpha_{ts}",
        "filename": dest.name,
        "size_kb": round(stat.st_size / 1024, 1),
        "created_at": datetime.utcnow().isoformat(),
    }


@router.get("/list")
def backup_list():
    """List all available backups."""
    return {"backups": _list_backups(), "count": len(_list_backups())}


@router.delete("/{backup_id}")
def backup_delete(backup_id: str):
    """Delete a specific backup by ID (stem)."""
    bdir = _ensure_backup_dir()
    target = bdir / f"{backup_id}.db"
    if not target.exists():
        raise HTTPException(status_code=404, detail="Backup not found")
    target.unlink()
    return {"status": "ok", "deleted": backup_id}
