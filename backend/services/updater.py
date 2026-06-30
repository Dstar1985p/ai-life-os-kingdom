"""
Auto-update service — checks GitHub releases for a newer version,
downloads the zip, and replaces the running installation.
"""
import logging
import os
import sys
import zipfile
import subprocess
import threading
import tempfile

import requests

logger = logging.getLogger(__name__)

from backend.version import VERSION as CURRENT_VERSION  # noqa: E402
GITHUB_REPO = "Dstar1985p/ai-life-os-kingdom"
RELEASES_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

_update_state = {
    "checking": False,
    "latest_version": None,
    "update_available": False,
    "download_url": None,
    "error": None,
    "applying": False,
    "apply_done": False,
}


def _version_tuple(v: str):
    try:
        return tuple(int(x) for x in v.lstrip("v").split("."))
    except Exception:
        return (0, 0, 0)


def check_for_update() -> dict:
    """
    Hits the GitHub releases API and returns update state.
    Non-blocking — result cached in module-level dict.
    """
    _update_state["checking"] = True
    _update_state["error"] = None
    try:
        resp = requests.get(
            RELEASES_API,
            timeout=8,
            headers={"Accept": "application/vnd.github+json"},
        )
        resp.raise_for_status()
        data = resp.json()
        latest = data.get("tag_name", "").lstrip("v")
        _update_state["latest_version"] = latest

        if _version_tuple(latest) > _version_tuple(CURRENT_VERSION):
            _update_state["update_available"] = True
            # Find the zip asset
            for asset in data.get("assets", []):
                if asset["name"].endswith(".zip"):
                    _update_state["download_url"] = asset["browser_download_url"]
                    break
            # Fallback: zipball from GitHub
            if not _update_state["download_url"]:
                _update_state["download_url"] = data.get("zipball_url")
        else:
            _update_state["update_available"] = False
            _update_state["download_url"] = None

    except Exception as exc:
        _update_state["error"] = str(exc)
        logger.warning("Update check failed: %s", exc)
    finally:
        _update_state["checking"] = False

    return get_update_status()


def get_update_status() -> dict:
    return {
        "current_version": CURRENT_VERSION,
        "latest_version": _update_state["latest_version"],
        "update_available": _update_state["update_available"],
        "checking": _update_state["checking"],
        "applying": _update_state["applying"],
        "apply_done": _update_state["apply_done"],
        "error": _update_state["error"],
    }


def _do_apply_update(download_url: str, install_dir: str):
    """Downloads zip, extracts beside install_dir, writes restart script."""
    _update_state["applying"] = True
    try:
        logger.info("Downloading update from %s", download_url)
        resp = requests.get(download_url, timeout=120, stream=True)
        resp.raise_for_status()

        tmp = tempfile.mkdtemp()
        zip_path = os.path.join(tmp, "kingdom_update.zip")
        with open(zip_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                f.write(chunk)

        extract_dir = os.path.join(tmp, "extracted")
        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(extract_dir)

        # GitHub zipballs have a top-level folder like Dstar1985p-ai-life-os-kingdom-<hash>/
        contents = os.listdir(extract_dir)
        source = os.path.join(extract_dir, contents[0]) if len(contents) == 1 else extract_dir

        # Write a helper batch that replaces files and relaunches
        exe_path = os.path.join(install_dir, "Kingdom.exe")
        bat = os.path.join(tmp, "apply_update.bat")
        with open(bat, "w") as f:
            f.write(f"""@echo off
timeout /t 2 /nobreak >nul
xcopy /E /Y /I "{source}" "{install_dir}"
start "" "{exe_path}"
del "%~f0"
""")

        subprocess.Popen(["cmd", "/c", bat], creationflags=0x00000008)  # DETACHED_PROCESS
        _update_state["apply_done"] = True
        logger.info("Update applied — restarting")

        # Give the batch a moment to launch before we exit
        threading.Timer(1.5, lambda: os._exit(0)).start()

    except Exception as exc:
        _update_state["error"] = str(exc)
        logger.error("Update apply failed: %s", exc)
    finally:
        _update_state["applying"] = False


def apply_update() -> dict:
    """Start download + apply in a background thread."""
    url = _update_state.get("download_url")
    if not url:
        return {"ok": False, "error": "No download URL — run check first"}
    if _update_state["applying"]:
        return {"ok": False, "error": "Already applying"}

    # install_dir = folder containing Kingdom.exe (or the project root when dev)
    install_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.getcwd()
    threading.Thread(target=_do_apply_update, args=(url, install_dir), daemon=True).start()
    return {"ok": True, "message": "Update download started"}


def check_for_update_async():
    """Fire-and-forget background check — called at app startup."""
    threading.Thread(target=check_for_update, daemon=True).start()
