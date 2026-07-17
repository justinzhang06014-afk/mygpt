# Session: 2026-07-15 — Snake Game Frontend Build

## API Endpoints Consumed

| Method | Path | Body | Response |
|--------|------|------|----------|
| POST | `/api/games` | `{ player_name }` | `{ game_id, player_name, score: 0, status: "running" }` |
| PUT | `/api/games/{id}/score` | `{ score }` | `{ game_id, score, rank, status: "finished" }` |
| GET | `/api/leaderboard?limit=10` | — | `[{ rank, player_name, score, finished_at }, ...]` |

## Client-side API wrapper pattern

```js
const API_BASE = 'http://localhost:9000/api';
async function _apiRequest(method, path, body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method, headers: { 'Content-Type': 'application/json' },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`API ${method} ${path} failed (${res.status})`);
  return res.json();
}
window.ApiClient = { startGame, submitScore, getLeaderboard };
```

## Screen flow

```
screen-name (active) → click Start → POST /api/games → screen-game (active)
screen-game → gameover event → PUT /api/games/{id}/score → screen-over (active)
screen-over → click Play Again → screen-name (active, name pre-filled)
```

## Graceful fallback when backend offline

- `startGame` fails → use `crypto.randomUUID()` for local game_id
- `submitScore` fails → show "Score recorded locally" message
- `getLeaderboard` fails → show "Leaderboard unavailable" message
