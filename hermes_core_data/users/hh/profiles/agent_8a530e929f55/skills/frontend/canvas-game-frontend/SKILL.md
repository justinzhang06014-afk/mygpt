---
name: canvas-game-frontend
description: Building self-contained HTML5 Canvas game frontends with vanilla JS, screen transitions, and backend API integration for scores/leaderboards
---
# Canvas Game Frontend

**Trigger:** Building a game frontend (or any Canvas-based interactive app) using vanilla HTML5 + CSS3 + JavaScript that integrates with a backend API for score/leaderboard.

## Workflow

1. **Read the API spec** — extract endpoints, request/response shapes, shared models. The spec drives what the frontend consumes vs. what runs locally.
2. **Read the game rules** — grid size, cell size, speed, controls, scoring, game-over conditions. These become constants in the game engine.
3. **Create all files in parallel** — `index.html`, CSS, and all JS modules — using `write_file` batch calls.
4. **Ad-hoc verification** — write a focused temp script under `/tmp/hermes-verify-<name>.py` to validate structure, serve the files, and confirm content. Summarize as "ad-hoc verification."

## File Structure

```
frontend/
├── index.html          # Single-page layout with all screens
├── css/style.css       # All styling
├── js/
│   ├── api.js          # API client (fetch wrapper)
│   ├── game.js         # Game engine (Canvas, game loop, collision)
│   └── app.js          # App controller (screen transitions, UI, leaderboard)
└── README.md           # How to run
```

## Key Patterns

### Script loading — classic, no modules
- Use plain `<script src="...">` tags (no `type="module"`).
- Expose globals via `window.SomeName = ...` — do NOT use `export`/`import`.
- Load order matters: API client first, then game engine, then app controller.

### Game engine separation
- `game.js` is pure Canvas + game loop — no DOM manipulation, no API calls.
- Expose via `window.SnakeGame` constructor and `window.GAME_DIR` direction constants.
- Use a simple event emitter (`on`/`emit`) so the app layer reacts to `score` and `gameover` events.

### API client
- `_apiRequest(method, path, body)` generic wrapper with JSON parsing and error throwing.
- Expose named functions via `window.ApiClient = { startGame, submitScore, getLeaderboard }`.
- Target `http://localhost:9000/api` — the backend port from the spec.

### Screen transitions
- Three `<section class="screen">` elements; toggle `.active` class to show/hide.
- `showScreen(screen)` helper removes `.active` from all, adds to target.

### Game rules (canonical from spec)
- Grid: 20×20 cells, 20px each (400×400 canvas)
- Snake starts at length 3, moving right
- Speed: 150ms per tick
- Arrow key controls with 180° reversal prevention
- Apple spawns randomly, never on snake body
- Score = apples eaten (+1 per apple, snake grows 1 cell)
- Game over: wall collision or self-collision

## Pitfalls

- **`export`/`import` with classic scripts:** If HTML uses `<script src="...">` (not `type="module"`), `export` throws a syntax error. Use `window.X = ...` instead.
- **Script load order:** `app.js` depends on `ApiClient` and `SnakeGame`/`GAME_DIR` being globals — load `api.js` first, then `game.js`, then `app.js`.
- **Don't sync game state with backend:** Game logic is fully client-side. API is only for: (1) recording player name, (2) submitting final score, (3) fetching leaderboard.
- **Apple placement collision:** Use a `Set` of occupied cells and retry random positions — don't just pick random.
- **Leaderboard auto-refresh:** Load on page init AND re-fetch after each game ends.
- **Graceful degradation:** If backend is offline, console.warn and keep game running. Don't block gameplay on API failures.
- **`python -m http.server` for local serving:** `cd /app/frontend && python3 -m http.server 9100` — simplest way to serve static files with correct MIME types.

### References
- `references/session-2026-07-15-snake.md` — Snake game build: exact API shapes, screen flow, fallback patterns.

## Verification Checklist

Write an ad-hoc Python script that checks:
- All files exist
- HTML contains required elements (canvas, inputs, buttons, leaderboard table)
- Script tags load in correct order
- CSS contains required colors
- Game engine has correct constants (grid, speed, cell size)
- API client hits correct endpoints
- All files serve correctly via `http.server` with expected content
