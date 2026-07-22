# Agent Orchestrator

Independent ASP.NET Core service that starts / stops / lists agent worker containers (Hermes, OpenClaw, …) on the same Docker host via `Docker.DotNet` and `/var/run/docker.sock`.

Compose service: `agent-orchestrator` · Internal URL: `http://agent-orchestrator:8080` · Host port: `5080`

## API

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/agents` | List allowed agent images (`Orchestrator:Agents` whitelist) |
| `POST` | `/api/v1/workers` | Create + start; waits for per-image readiness |
| `GET` | `/api/v1/workers` | List owned workers |
| `GET` | `/api/v1/workers/{id}` | Get one worker |
| `DELETE` | `/api/v1/workers/{id}` | Stop + remove |
| `*` | `/api/v1/workers/{id}/proxy/{**path}` | External reverse proxy to worker (when enabled; SSE-safe) |
| `GET` | `/health` | Liveness |
| `GET` | `/metrics` | Prometheus metrics (MVP admission + create/ready/delete) |
| — | `/swagger` | Swagger UI (OpenAPI at `/swagger/v1/swagger.json`) |

### List agents example

```http
GET /api/v1/agents
```

```json
[
  { "image": "nousresearch/hermes-agent:latest" }
]
```

Only `image` is returned (create must use one of these exact values).

### Create example

```http
POST /api/v1/workers
Content-Type: application/json

{
  "userId": 42,
  "image": "hermes-agent:latest",
  "environment": { "LOG_LEVEL": "info" },
  "volumes": {
    "/home/phison/ainexus/agent-data/user-42/session-1": "/data"
  }
}
```

```json
{
  "id": "a1b2c3d4e5f6",
  "name": "agent-worker-a1b2c3d4e5f6",
  "image": "hermes-agent:latest",
  "userId": 42,
  "status": "running",
  "baseUrl": "http://agent-worker-a1b2c3d4e5f6:8080",
  "externalBaseUrl": null,
  "exitCode": null
}
```

Workers are named `agent-worker-{id}` and labeled (`com.ainexus.orchestrator=agent`, `com.ainexus.worker.id`, `com.ainexus.user.id`, …).

## Metrics (`GET /metrics`)

Prometheus text exposition (OpenTelemetry Prometheus exporter). Observable gauges appear at zero; counters and histograms appear after the first recorded event.

| Prometheus name | Type | Description |
|-----------------|------|-------------|
| `agent_orchestrator_workers_running` | gauge | Owned workers in running state |
| `agent_orchestrator_admission_in_flight` | gauge | Creates starting or waiting for ready |
| `agent_orchestrator_admission_waiting` | gauge | Create requests waiting for a slot |
| `agent_orchestrator_admission_occupied_slots` | gauge | `workers_running` + `in_flight` |
| `agent_orchestrator_admission_max_concurrent` | gauge | Configured `MaxConcurrentWorkers` |
| `agent_orchestrator_admission_max_queue` | gauge | Configured `MaxQueueLength` |
| `agent_orchestrator_docker_up` | gauge | `1` if last Docker refresh succeeded, else `0` |
| `agent_orchestrator_worker_creates` | counter | Create attempts; label `result`: `success`, `conflict`, `queue_full`, `admission_timeout`, `ready_timeout`, `canceled`, `docker_error` |
| `agent_orchestrator_worker_deletes` | counter | Successful deletes |
| `agent_orchestrator_worker_ready_duration` | histogram | Seconds from container start until ReadyPath OK |

Per-worker CPU and memory are **not** exported here (use cAdvisor or `docker stats` and filter by label `com.ainexus.orchestrator=agent`).

- **Same Docker network:** call chat via `baseUrl` (e.g. `http://agent-worker-…:8080/v1/chat/completions`).
- **Outside that network:** enable `ExternalAccess` and use `externalBaseUrl` + path (see below).

**One worker per user + image:** `POST` reserves `(userId, image)` before the admission queue. A second create for the same pair returns `409 Conflict` (existing container, or another create still queued/in-flight). Delete the worker to create again.

## External access proxy

Orchestrator and workers stay on the **same host / Docker network**. Proxy only exposes worker HTTP (including **SSE / streaming** chat completion) through the orchestrator — no host port mapping on workers.

Set in config / env:

```json
"ExternalAccess": {
  "Enabled": true,
  "ApiKey": "change-me",
  "PublicBaseUrl": "http://localhost:5080",
  "RequestTimeoutSeconds": 600
}
```

When `Enabled` is true, create/get/list include e.g.:

`externalBaseUrl`: `http://localhost:5080/api/v1/workers/a1b2c3d4e5f6/proxy`

Chat example (SSE supported; do not buffer on the client):

```http
POST /api/v1/workers/a1b2c3d4e5f6/proxy/v1/chat/completions
X-Api-Key: change-me
Content-Type: application/json

{ "model": "…", "stream": true, "messages": [ … ] }
```

| Setting | Meaning |
|---------|---------|
| `Enabled` | `false` (default) → proxy returns **404**; `externalBaseUrl` is null |
| `ApiKey` | If non-empty, require `X-Api-Key` or `Authorization: Bearer` on **proxy** routes only |
| `PublicBaseUrl` | Origin used to build `externalBaseUrl`; empty → derive from the request |
| `RequestTimeoutSeconds` | Upstream timeout (default 600 for long streams) |

## Error responses

All failure bodies are JSON objects. Most include at least `error` (string message).

### `POST /api/v1/workers`

| Status | When | Body |
|--------|------|------|
| **400** Bad Request | Invalid `userId`, image not in whitelist, bad env/volumes, missing `ReadyPath`, etc. | `{ "error": "..." }` |
| **409** Conflict | Same `userId` + `image` already has a container, or another create is queued/in-flight | see below |
| **429** Too Many Requests | Admission wait queue is full (`MaxQueueLength`) | `{ "error": "Admission wait queue is full." }` |
| **503** Service Unavailable | Waited for a free slot longer than `WaitTimeoutSeconds` | `{ "error": "Timed out waiting for a worker slot." }` |
| **502** Bad Gateway | Docker create/start failed, readiness timed out / container died during ready, or Docker engine unreachable | `{ "error": "..." }` |

**409 body**

```json
{
  "error": "User 42 already has worker 'a1b2c3d4e5f6' for image 'hermes-agent:latest'.",
  "userId": 42,
  "image": "hermes-agent:latest",
  "existingWorkerId": "a1b2c3d4e5f6",
  "reason": "exists"
}
```

| Field | Meaning |
|-------|---------|
| `error` | Human-readable message |
| `userId` | Requested AINexus user id |
| `image` | Requested image string |
| `existingWorkerId` | Worker id if a container already exists; `null` when `reason` is `pending` |
| `reason` | `exists` — container already present (any state until DELETE); `pending` — create already reserved (in queue or starting) |

### `GET /api/v1/workers`

| Status | When | Body |
|--------|------|------|
| **502** Bad Gateway | Docker list timed out / unreachable | `{ "error": "Docker unavailable: ..." }` |

### `GET /api/v1/workers/{id}`

| Status | When | Body |
|--------|------|------|
| **404** Not Found | No owned worker with that id | `{ "error": "Worker '{id}' was not found." }` |
| **502** Bad Gateway | Docker inspect/list unreachable | `{ "error": "Docker unavailable: ..." }` |

### `DELETE /api/v1/workers/{id}`

| Status | When | Body |
|--------|------|------|
| **404** Not Found | No owned worker with that id | `{ "error": "Worker '{id}' was not found." }` |
| **502** Bad Gateway | Stop/remove failed, or Docker unreachable | `{ "error": "..." }` |

### `*/api/v1/workers/{id}/proxy/{**path}`

| Status | When | Body |
|--------|------|------|
| **404** | `ExternalAccess.Enabled` is false | `{ "error": "External access proxy is disabled." }` |
| **401** | `ApiKey` configured but missing/wrong | `{ "error": "Invalid or missing API key." }` |
| **404** | Worker id not found | `{ "error": "Worker '{id}' was not found." }` |
| **502** | Worker not running, or upstream request failed | `{ "error": "..." }` |
| **(upstream)** | Success / other | Status and body streamed from the worker (incl. `text/event-stream`) |

### Success codes (for reference)

| Method | Success |
|--------|---------|
| `POST` | **201** Created — worker body (ready + `baseUrl`) |
| `GET` list/get | **200** OK |
| `DELETE` | **204** No Content |
| `GET /health` | **200** `{ "status": "ok" }` |

Model validation failures from ASP.NET (e.g. missing required JSON fields) may return **400** with the framework’s default problem-details shape instead of `{ "error": "..." }`.

## Config (`Orchestrator` section)

- **Agents[]** — whitelist: `Image`, `HttpPort`, `ReadyPath`, optional `ReadyTimeoutSeconds` / `Cmd` / `User` / `CapDrop` / `CapAdd`
  - `User`: omit → global `WorkerUser` (`1000:1000`); `""` → image default user (needed for many agent images like Hermes)
  - `OmitCapDrop`: `true` for Hermes/s6 (never send CapDrop; do not rely on `CapDrop: []` — empty JSON arrays can bind as null and fall back to global `["ALL"]`)
  - `CapDrop` / `CapAdd`: optional list overrides when not omitting
  - `NoNewPrivileges`: omit → global; `false` for s6-overlay images (Hermes needs `setgroups`; otherwise cont-init fails)
  - `Cmd`: e.g. `["gateway","run"]`; omit → image default
- **MaxConcurrentWorkers** / **WaitTimeoutSeconds** / **MaxQueueLength** — admission queue (no host free-CPU/mem probe)
- **AllowedBindPrefixes** — host paths allowed for POST `volumes` (bind mounts only)
- **DockerNetwork** / **DockerEndpoint** — network for worker DNS; socket or npipe
- **ExternalAccess** — proxy on/off, optional ApiKey, PublicBaseUrl, RequestTimeoutSeconds
- Per-container limits & hardening: 1 CPU / 2 GiB, non-root, `CapDrop=ALL`, `PidsLimit`, `no-new-privileges`, `RestartPolicy=no`

## Local / compose

```bash
# From repo root
docker compose up -d --build agent-orchestrator
curl http://localhost:5080/health
```

Requires Docker socket mount and a matching `DockerNetwork` name so spawned workers are reachable as `http://agent-worker-*:port` from AINexus.
