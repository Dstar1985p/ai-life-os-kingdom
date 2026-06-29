# AI Life OS Kingdom — Alpha Starter Repo

AI Life OS Kingdom is a decision-intelligence and business operating system designed to help Daniel:

- make better business decisions
- save time
- discover opportunities
- track lessons
- avoid low-value distractions

This Alpha starter uses:

- Python 3.12
- FastAPI
- SQLite
- SQLAlchemy
- Pydantic
- Pytest

## Alpha 0.1 Scope

Build only:

1. Agent Registry
2. Quest Engine
3. Opportunity Vault
4. Decision Journal
5. Knowledge Graph
6. Council Engine
7. Morning Brief Generator
8. Basic Command Nexus API

Do not build:

- pixel kingdom
- live Etsy scraping
- payments
- autonomous external actions
- production deployment
- mobile app

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.main:app --reload
```

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn backend.main:app --reload
```

## Tests

```bash
pytest -q
bash scripts/clean_install_test.sh
bash scripts/release_gate.sh
```

## API

Open:

```text
http://127.0.0.1:8000/docs
```

## First Test

Open:

```text
http://127.0.0.1:8000/brief/morning
```

You should receive a basic Morning Kingdom Brief.
