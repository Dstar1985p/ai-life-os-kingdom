#!/usr/bin/env bash
set -e

echo "=== Clean Install Test ==="
python --version
pip install -r requirements.txt

python - <<'PY'
import importlib
for module in ["fastapi", "pydantic", "sqlalchemy"]:
    importlib.import_module(module)
print("Core imports OK")
PY

echo "Clean install test passed."
