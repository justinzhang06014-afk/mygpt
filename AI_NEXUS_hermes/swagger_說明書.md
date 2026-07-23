# Swagger API 說明書

Swagger UI：`http://<部署主機>:8643/docs`（例如 `http://192.168.85.82:8643/docs`）

服務啟動後，端點在 Swagger 上按下面分類分組（跟 `main.py` 裡 `TAGS_METADATA` 一致），照順序測就對了：**① 建立 → ② 聊天 → ③ MCP 設定 → ④ 使用者管理 → ⑤ 遠端 Orchestrator 直連（測試/除錯用）→ 系統**。

---

## 系統

### `GET /`
服務資訊。回應：
```json
{"service": "AI_NEXUS Hermes Core", "status": "running", "profiles_base_dir": "/opt/data/profiles"}
```

### `GET /health`
健康檢查。檔案系統寫不進去一律回 503（硬依賴）；`docker.sock`/orchestrator 連不到只降級成 warning，不會讓整支服務被判定不健康。
```json
{"status": "healthy", "profiles_base_dir": "...", "container_backend": "orchestrator (http://192.168.41.173:5080)"}
```
`container_backend` 會顯示現在走 orchestrator 還是本機 `docker.sock (connected)`。

---

## ① 建立/Ensure（入口角色）

### `POST /api/session/ensure`
使用者登入後、開始第一句對話前呼叫一次。

**Request：**
```json
{
  "user_id": "demo001",
  "system_prompt": "你是一位專業的 AI 助理，能夠協助使用者處理各種任務。",
  "model": "Qwen/Qwen3.6-35B-A3B-FP8",
  "llm_api_key": "AINX-...",
  "phison_token": "eyJhbGciOi..."
}
```
| 欄位 | 型別 | 必填 | 說明 |
|---|---|---|---|
| `user_id` | string | ✅ | 換算成 `agent_id = user_{user_id}` |
| `system_prompt` | string\|null | ✗ | 留空用系統預設通用助理人設 |
| `model` | string\|null | ✗ | 留空用環境變數 `LLM_MODEL` |
| `llm_api_key` | string\|null | ✗ | 留空用系統共用 key |
| `phison_token` | string\|null | ✗ | AINexus bearer token |

**做的事：** 1) 本地寫好 `config.yaml`/`SOUL.md`/`mcp.json`（+ 有帶 token 就寫 `.env`）2) 呼叫 orchestrator 或本機 `docker.sock` 建立/確認容器 3) 本機模式才會額外呼叫容器的 `/api/agent/prepare` + MCP 設定端點（orchestrator 模式的容器沒有這些端點，不會呼叫）。

**Response：**
```json
{
  "status": "running",
  "user_id": "demo001",
  "agent_id": "user_demo001",
  "base_url": "http://agent-worker-xxxx:8080",
  "chat_endpoint": "http://192.168.85.82:8643/api/agent/chat/stream",
  "message": "使用既有容器",
  "external_base_url": null,
  "worker_id": "a1b2c3d4e5f6",
  "swagger_url": "http://agent-worker-xxxx:8643/docs"
}
```
`chat_endpoint` 一律指回這支服務自己（orchestrator 模式下 `base_url` 是容器內部位址，使用者端不該直接打）。

---

## ② 聊天 Chat

### `POST /api/agent/chat/stream`
核心對話端點，`media_type: text/plain` 純文字串流回應。

**Request：**
```json
{
  "message": "你好，請自我介紹一下",
  "user_id": "demo001",
  "agent_id": "agent_default",
  "room_id": "room_default",
  "system_prompt": null,
  "model": null,
  "llm_api_key": null,
  "phison_token": null
}
```
| 欄位 | 型別 | 必填 | 說明 |
|---|---|---|---|
| `message` | string | ✅ | 使用者這輪輸入 |
| `user_id` | string\|null | 強烈建議帶 | 帶了會覆寫 `agent_id`，換算成跟 ensure 一致的 `user_{user_id}` |
| `agent_id` | string | ✗ | 預設 `agent_default`；只有沒帶 `user_id` 的 multi-agent 情境才需要自己指定 |
| `room_id` | string | ✗ | 預設 `room_default`，對應 hermes session，同房間才會 resume 上下文 |
| `system_prompt`／`model`／`llm_api_key` | ✗ | 這輪要換人設/模型才需要帶，SOUL.md/config.yaml 每輪都會重寫 |
| `phison_token` | string\|null | 建議每輪都帶最新的 | 浮動/會過期 |

**執行邏輯：**
- Orchestrator 模式：先確認/建立遠端容器（不存在就建、已存在就補傳最新 `.env`），成功就把這輪轉發到容器的 `/v1/chat/completions`（OpenAI 格式 SSE），解析成純文字串流吐回；拿不到遠端資訊才退回下面的本機邏輯。
- 本機 `docker.sock` 模式：走 ACP，本地直接執行 hermes 對話，用 `__ACP_TOOL__`/`__ACP_THOUGHT__`/`__ACP_PLAN__`/`__ACP_USAGE__`/`__APPROVAL_REQUIRED__` 這幾種前綴標記把工具呼叫、思考過程、計畫更新、用量、危險操作核准請求都內嵌在文字串流裡。

**回應（純文字串流範例）：**
```
你好！我是一個 AI 助理，可以幫你...
```
失敗/截斷會額外顯示（不會靜默斷掉）：
```
⚠️ 這輪回覆不完整（error）：底層 agent 執行失敗
```

**429 Too Many Requests：** 同一個 `room_id` 上一輪還沒回完、又沒有 session 可以 resume 時觸發，代表「Hermes 正在思考中，請稍候」。

### `POST /api/agent/prepare`
提前寫好 `config.yaml`/`SOUL.md`（不用等第一句聊天才觸發），`/api/session/ensure` 建好容器後會呼叫這支（只在本機模式），也可以單獨呼叫來重寫設定。
```json
{"agent_id": "agent_default", "system_prompt": null, "model": null, "llm_api_key": null}
```
回應：`{"status": "success", "agent_id": "...", "agent_dir": "..."}`

### `POST /api/agent/approve-write?room_id=...&option_id=...`
核准 hermes 觸發的危險操作請求（對應聊天串流裡的 `__APPROVAL_REQUIRED__` 標記）。回應：`{"status": "success"}`；沒有正在等待核准的請求回 404。

---

## ③ MCP 專家路由設定

### `GET /api/mcp/catalog`
母版 MCP 目錄（管理員在 `mcp.json` 維護的所有可用工具清單）。
```json
{"status": "success", "mcpServers": {"phison-ainexus": {...}, "websearch": {...}}}
```

### `GET /api/agent/{agent_id}/mcp`
這個 agent 目前的 MCP 選擇狀態。`{"status": "success", "servers": [...]}`

### `POST /api/agent/{agent_id}/mcp/{mcp_name}/selection`
設為 resident/optional/移除。
```json
{"selection": "resident"}
```
`selection` 可以是 `null`（移除）/`"resident"`/`"optional_installed"`。404：agent 或 mcp_name 不存在；400：無效的 selection 值。

### `POST /api/agent/{agent_id}/mcp/{mcp_name}/credentials`
填入憑證（如 `PHISON_TOKEN`），實際寫進 `$HERMES_HOME/.env`。
```json
{"credentials": {"PHISON_TOKEN": "..."}}
```

---

## ④ 使用者管理 User CRUD

> ⚠️ **已知落差**：這四支目前只走本機 `runtime_manager.py`（`docker.sock`），**沒有依 orchestrator 模式分岔**。Orchestrator 模式下呼叫 `GET`/`DELETE` 會出錯（實測回 500，因為內部呼叫的是本機 docker client，orchestrator 模式沒有 docker.sock 可用）。要在 orchestrator 模式查/刪使用者，目前只能直接打 Docker 管理端本身的 `GET/DELETE /api/v1/workers/{id}`（見下方⑤）。`POST /api/users`（Create）不受影響，跟 `/api/session/ensure` 是同一套邏輯。

### `GET /api/users`
列出所有使用者。`{"status": "success", "count": N, "users": [...]}`（本機模式限定）

### `GET /api/users/{user_id}`
查詢單一使用者狀態，找不到回 404。（本機模式限定）

### `POST /api/users`
建立使用者，等同 `/api/session/ensure`，request/response 格式完全一樣。

### `DELETE /api/users/{user_id}?wipe_data=false`
刪除使用者（停止並移除容器）。預設只刪容器不刪資料（`wipe_data=false`），之後同一個 `user_id` 再 ensure 一次，設定/記憶都還在。要連資料夾一起刪乾淨才把 `wipe_data` 設 `true`。（本機模式限定）

---

## ⑤ 遠端 Orchestrator API（直連對方主機，測試/除錯用）

這組是直接代理打 Docker 管理端本身的 API，不經過我方的 ensure/chat 邏輯，方便測試和除錯。

> ⚠️ **重複註冊提醒**：`main.py` 裡這四支端點目前被定義了兩次（一模一樣的 path/邏輯），FastAPI 只會吃到第一次註冊的那份，第二份是死碼，不影響功能但值得之後清掉。

### `GET /api/orchestrator/swagger`
取得對方 Orchestrator 的 Swagger/OpenAPI 文件。
```json
{"status": "success", "orchestrator_url": "...", "swagger_url": "...", "info": {...}, "paths_count": N, "tags": [...], "full_swagger": {...}}
```

### `GET /api/orchestrator/workers`
查看對方主機所有使用者容器（不篩選）。
```json
{"status": "success", "orchestrator_url": "...", "workers": [{"id": "...", "name": "...", "userId": ..., "status": "running", "baseUrl": "..."}], "count": N}
```

### `GET /api/orchestrator/workers/{worker_id}`
取得對方單一容器詳細資訊。`{"status": "success", "worker": {...}}`；查不到回 502。

### `DELETE /api/orchestrator/workers/{worker_id}`
刪除對方容器。成功：`{"status": "success", "worker_id": "...", "message": "容器已成功刪除"}`；容器不存在：`{"status": "error", "error": "..."}`（回應本身仍是 200，用 `status` 欄位判斷）。

---

## 附：Request/Response 共用型別備忘

- `EnsureSessionPayload`：`user_id`(必填) / `system_prompt` / `model` / `llm_api_key` / `phison_token`
- `ChatRequest`：`message`(必填) / `user_id` / `agent_id`(預設`agent_default`) / `room_id`(預設`room_default`) / `system_prompt` / `model` / `llm_api_key` / `phison_token`
- `PrepareAgentPayload`：`agent_id`(預設`agent_default`) / `system_prompt` / `model` / `llm_api_key`
- `McpSelectionPayload`：`selection`（`null`/`"resident"`/`"optional_installed"`）
- `McpCredentialsPayload`：`credentials`（`{field_key: value}` 字典，例如 `{"PHISON_TOKEN": "..."}`）
