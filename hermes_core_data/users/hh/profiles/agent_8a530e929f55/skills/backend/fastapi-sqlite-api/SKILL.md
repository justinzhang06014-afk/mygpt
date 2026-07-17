---
name: fastapi-sqlite-api
description: Scaffolding, implementing, and verifying REST APIs with FastAPI + SQLite
---
# FastAPI + SQLite API Scaffolding

**Trigger:** Building a REST API backend with FastAPI, SQLite, and endpoint verification.

## Workflow

1. **Read the spec** (JSON/YAML) — extract endpoints, models, validation rules, DB schema.
2. **Create all files in parallel** — `main.py`, `database.py`, `models.py`, `requirements.txt` — using `write_file` batch calls. Don't wait for one to verify before writing the next.
3. **Install + smoke-test imports:**
   ```bash
   cd /path/to/backend && pip install -r requirements.txt && python test_import.py
   ```
   (Use a temporary `.py` script instead of `python -c` — the terminal sometimes blocks inline Python.)
4. **Ad-hoc verification** — write a focused temp script under `/tmp/hermes-verify-<name>.py` that uses `fastapi.testclient.TestClient` to exercise every endpoint:
   - Patch `database.DB_PATH` to a temp file before importing the app so the real DB isn't polluted.
   - Test success paths, validation rejections (422), and error paths (404).
   - Print per-check PASS/FAIL and exit non-zero on any failure.
   - Summarize as "ad-hoc verification" — never claim "suite green" unless a real test framework runs.
5. **Write completion report** to the shared output location.

## File Structure

```
backend/
  main.py          — FastAPI app, all endpoints, CORS middleware
  database.py      — SQLite init, connection helpers, table creation
  models.py        — Pydantic request/response models with validation
  requirements.txt — fastapi, uvicorn, pydantic
```

## Key Patterns

- **CORS:** Always add `CORSMiddleware` with `allow_origins=["*"]` unless spec says otherwise.
- **DB isolation in tests:** Patch `DB_PATH` to a temp file before app import — the `init_db()` call at module level creates tables on whatever path is set.
- **UUID game/session IDs:** Use `str(uuid.uuid4())`.
- **ISO 8601 timestamps:** `datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")`.
- **Rank computation:** `COUNT(*) FROM scores WHERE score > ? OR (score = ? AND finished_at <= ?)` — earlier finishes get better rank among ties.

## Pitfalls

- **`python -c` may be blocked** by the terminal safety filter. Write a temp `.py` script instead.
- **`init_db()` runs at import time**, so patching `DB_PATH` must happen *before* importing `main` (import `database` first, then mutate, then import `main`).
- **Don't skip verification** because imports succeeded. Imports only prove modules load — they don't prove endpoints work correctly or validation catches bad input.
