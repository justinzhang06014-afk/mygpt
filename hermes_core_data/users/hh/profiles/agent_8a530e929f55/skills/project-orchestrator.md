---
name: project-orchestrator
description: Multi-agent project orchestration skill. Coordinates frontend and backend sub-agents to collaboratively build full-stack applications.
---

# Project Orchestrator Skill

## Role

You are the **Project Orchestrator**. Your job is to:
1. Define the API contract between frontend and backend
2. Dispatch parallel sub-agents via `delegate_task` (batch mode)
3. Collect their deliverables
4. Run integration tests
5. Produce an acceptance report for the human

## Workflow

### Phase 1: Requirements Gathering

Ask the human (via `clarify`) for:
- Project type (Web App / Dashboard / API service)
- Tech stack preference (or pick sensible defaults)
- Core features list

### Phase 2: API Contract Definition

Create the shared contract file at the project's shared directory:

```
{workdir}/shared/api_spec.json
```

Minimum structure:
```json
{
  "version": "1.0",
  "base_url": "http://localhost:8000/api",
  "endpoints": [
    {
      "method": "GET|POST|PUT|DELETE",
      "path": "/api/resource",
      "request_body": {},
      "response": {},
      "description": "what this endpoint does"
    }
  ],
  "shared_models": {
    "Resource": { "id": "int", "name": "string" }
  }
}
```

Also create status tracking:
```
{workdir}/shared/status.md        # tracking file
{workdir}/shared/backend_report.md   # backend writes here when done
{workdir}/shared/frontend_report.md  # frontend writes here when done
```

### Phase 3: Dispatch Sub-Agents

Use `delegate_task` in **batch mode** to spawn both agents simultaneously:

```
delegate_task(tasks=[
  {
    "goal": "<backend developer prompt>",
    "context": "Full context including API spec path, tech stack, requirements"
  },
  {
    "goal": "<frontend developer prompt>",
    "context": "Full context including API spec path, tech stack, requirements"
  }
])
```

**Important**: Both sub-agents are leaf agents (cannot delegate further). They run in isolation. The only communication channel is through shared files on disk.

### Phase 4: Collect and Verify

After both sub-agents complete:
1. Read `{workdir}/shared/backend_report.md`
2. Read `{workdir}/shared/frontend_report.md`
3. Verify file structure exists in both `/backend/` and `/frontend/`
4. Attempt to start both servers and run a basic health check

### Phase 5: Acceptance Report

Generate a report at `{workdir}/shared/acceptance_report.md`:

```markdown
# Acceptance Report: {project_name}
Date: {date}

## Architecture
- Backend: {stack}
- Frontend: {stack}

## Completed Features
- [x] Feature 1
- [x] Feature 2

## API Endpoints Implemented
| Method | Path | Status |
|--------|------|--------|
| GET    | /api/items | Done |

## Known Issues
- Issue 1 (if any)

## How to Run
1. cd backend && pip install -r requirements.txt && uvicorn main:app
2. cd frontend && npm install && npm run dev

## Verdict: PASS / NEEDS_REVISION
```

## Template Prompts for Sub-Agents

### Backend Agent Goal Template

```
You are a Backend Developer. Build a complete backend service.

API SPEC: Read the contract at /app/shared/api_spec.json
WORKDIR: /app/backend

Requirements:
- Use {backend_stack} (e.g. FastAPI + SQLite)
- Implement ALL endpoints defined in the API spec
- Write requirements.txt
- Include a main entry point that can be started with one command
- Add basic error handling and input validation

When done:
1. Write a completion report to /app/shared/backend_report.md listing:
   - All implemented endpoints
   - How to start the server
   - Any known issues
2. Verify the project by running `python -c "import your_main"` or equivalent
```

### Frontend Agent Goal Template

```
You are a Frontend Developer. Build a complete frontend application.

API SPEC: Read the contract at /app/shared/api_spec.json
WORKDIR: /app/frontend

Requirements:
- Use {frontend_stack} (e.g. vanilla HTML/JS or React)
- Consume ALL backend endpoints defined in the API spec
- Create a clean, functional UI
- Include all dependencies and a start command

When done:
1. Write a completion report to /app/shared/frontend_report.md listing:
   - All pages/components created
   - How to start the development server
   - Any known issues
2. Verify file structure is complete
```

## Pitfalls

1. **Sub-agents cannot talk to each other directly**. All coordination happens through shared files on disk.
2. **Sub-agents have no chat history**. The `context` field must contain ALL information they need.
3. **Keep prompts self-contained**. Do not reference "as we discussed earlier" — the sub-agent has no prior context.
4. **Use absolute paths**. Sub-agents run in their own sessions with potentially different working directories.
5. **Set a reasonable scope**. Each sub-agent should be able to complete in one session. Break large projects into phases.
6. **Backend should write API spec first** if you want sequential execution, or define it yourself before dispatching for parallel execution.
