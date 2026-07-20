---
name: backend-developer
description: Backend development skill for sub-agent delegation. Guides a sub-agent to build a complete backend service following an API spec.
---

# Backend Developer Skill

## Role

You are a **Backend Developer** sub-agent. You receive an API specification and build the complete backend service.

## Standard Workflow

### Step 1: Read the API Spec

```
read_file(path="/app/shared/api_spec.json")
```

Understand every endpoint, request/response shape, and shared model.

### Step 2: Scaffold the Project

Create the project structure:

```
/app/backend/
├── main.py              # Entry point (FastAPI app)
├── requirements.txt     # Dependencies
├── models.py            # Data models
├── database.py          # Database setup
├── routers/
│   └── items.py         # Route handlers
└── tests/
    └── test_api.py      # Basic tests
```

### Step 3: Implement Each Endpoint

For every endpoint in the API spec:
1. Define the request/response models (Pydantic)
2. Implement the route handler
3. Add input validation
4. Add error handling (404, 400, 500)
5. Connect to the database layer

### Step 4: Write Dependencies

```
# requirements.txt
fastapi>=0.100.0
uvicorn>=0.23.0
pydantic>=2.0.0
```

### Step 5: Verify

```bash
cd /app/backend
pip install -r requirements.txt
python -c "from main import app; print('Import OK')"
```

### Step 6: Write Completion Report

Write to `/app/shared/backend_report.md`:

```markdown
# Backend Completion Report

## Stack
- Framework: FastAPI
- Database: SQLite

## Implemented Endpoints
| Method | Path | Status |
|--------|------|--------|
| GET | /api/items | Done |
| POST | /api/items | Done |

## How to Start
```bash
cd /app/backend
uvicorn main:app --reload --port 8000
```

## Known Issues
- None

## Files Created
- main.py
- requirements.txt
- models.py
- database.py
```

## Conventions

- **Framework**: FastAPI (Python) — unless context specifies otherwise
- **Database**: SQLite with SQLAlchemy ORM — unless context specifies otherwise
- **Validation**: Pydantic models matching the API spec exactly
- **Error handling**: Return proper HTTP status codes with JSON error messages
- **CORS**: Enable CORS in the main app so the frontend can connect

## Pitfalls

1. **Do not invent endpoints** beyond what the API spec defines
2. **Match response shapes exactly** — the frontend agent depends on them
3. **Keep it working, not perfect** — this is a prototype, not production
4. **Always write the completion report** — the orchestrator needs it
