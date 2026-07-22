# 0722 Night Problem Report

## 1. 現在使用者 create 進來格式

使用 `POST /api/session/ensure` 或 `POST /api/users` 端點：

```json
{
  "user_id": "demo001",
  "system_prompt": "你是一位專業的 AI 助理，能夠協助使用者處理各種任務。",
  "model": "Qwen/Qwen3.6-35B-A3B-FP8",
  "llm_api_key": "AINX-F78D2FCD53915EE37BD0871392FFBFFAF648C53C388950FC6A1F2ED8C534B249"
}
```

**欄位說明：**
- `user_id`: 使用者 ID（必填），會轉換為 agent_id = `user_{user_id}`
- `system_prompt`: 系統提示詞（選填），留空用系統預設的通用助理人設
- `model`: 模型名稱（選填），留空用環境變數 `LLM_MODEL` 預設值
- `llm_api_key`: 模型 API 金鑰（選填），留空用環境變數 `PHISON_API_KEY` 預設值

---

## 2. 現在 POST 檔案的格式

**端點：** `POST http://localhost:5080/api/v1/users/<user_id>/files`

**檔案儲存位置：** `/home/phison/ainexus/agent-data/<user_id>`

**Curl 指令：**
```bash
curl -F "files=@<檔案名稱>;filename=<檔案名稱>" http://localhost:5080/api/v1/users/<user_id>
```

**成功/失敗回應格式：**
```json
{
  "userId": 42,
  "root": "/home/phison/ainexus/agent-data/42",
  "files": [
    {
      "path": "workspace/settings.json",
      "absolutePath": "/home/phison/ainexus/agent-data/42/workspace/settings.json",
      "status": "written",
      "bytes": 128
    },
    {
      "path": "../evil.txt",
      "absolutePath": null,
      "status": "failed",
      "error": "Path is not allowed."
    }
  ]
}
```

**欄位說明：**
- `userId`: 使用者 ID（整數格式）
- `root`: 遠端主機路徑
- `files`: 檔案處理結果陣列
  - `path`: 檔案相對路徑
  - `absolutePath`: 檔案絕對路徑（失敗時為 null）
  - `status`: 檔案狀態（"written" 或 "failed"）
  - `bytes`: 檔案大小（僅成功時有值）
  - `error`: 錯誤訊息（僅失敗時有值）

---

## 3. 現在 POST 給遠端 Orchestrator 格式

**端點：** `POST {ORCHESTRATOR_URL}/api/v1/workers`

**完整 Payload：**
```json
{
  "userId": 42,
  "image": "hermes-agent:latest",
  "environment": {
    "PHISON_API_KEY": "AINX-F78D2FCD53915EE37BD0871392FFBFFAF648C53C388950FC6A1F2ED8C534B249",
    "LLM_PROVIDER": "custom",
    "LLM_BASE_URL": "http://10.102.196.43:18299/InferenceModel43/v1",
    "LLM_MODEL": "InferenceModel43",
    "LLM_API_KEY": "",
    "API_SERVER_ENABLED": "true",
    "API_SERVER_HOST": "0.0.0.0",
    "API_SERVER_KEY": "<隨機產生的 key>",
    "API_SERVER_CORS_ORIGINS": "*"
  },
  "volumes": {
    "/home/phison/ainexus/agent-data/42": "/opt/data"
  }
}
```

**欄位說明：**
- `userId`: 使用者 ID（整數格式，使用 CRC32 雜湊從字串轉換）
- `image`: Docker 容器映像名稱
- `environment`: 容器環境變數
  - `PHISON_API_KEY`: Phison API 金鑰
  - `LLM_PROVIDER`: LLM 提供商（預設 "custom"）
  - `LLM_BASE_URL`: LLM 端點基礎 URL
  - `LLM_MODEL`: LLM 模型名稱
  - `API_SERVER_ENABLED`: API 服務啟用狀態
  - `API_SERVER_HOST`: API 服務主機位址
  - `API_SERVER_KEY`: API 服務金鑰
  - `API_SERVER_CORS_ORIGINS`: CORS 來源設定
- `volumes`: 容器掛載設定
  - 鍵為宿主機路徑，值為容器內路徑

---

## 4. 現在使用者 chat 格式

**端點：** `POST /api/agent/chat/stream`

**請求格式：**
```json
{
  "message": "你好，請自我介紹一下",
  "user_id": "demo001",
  "agent_id": "agent_default",
  "room_id": "room_default",
  "system_prompt": "你是一位專業的 AI 助理，能夠協助使用者處理各種任務。",
  "model": "Qwen/Qwen3.6-35B-A3B-FP8",
  "llm_api_key": "AINX-F78D2FCD53915EE37BD0871392FFBFFAF648C53C388950FC6A1F2ED8C534B249",
  "phison_token": "AINEXUS-TOKEN-123456"
}
```

**欄位說明：**
- `message`: 使用者輸入的訊息（必填）
- `user_id`: 使用者 ID（選填），傳入後會自動轉換為 `user_{user_id}` 作為 agent_id
- `agent_id`: Agent ID（預設值 "agent_default"），有傳 user_id 時會被覆寫
- `room_id`: 聊天房間 ID（預設值 "room_default"），對應 hermes 原生 session
- `system_prompt`: 系統提示詞（選填），留空用系統預設的通用助理人設
- `model`: 模型名稱（選填），留空用環境變數 `LLM_MODEL` 預設值
- `llm_api_key`: 模型 API 金鑰（選填），留空用環境變數 `PHISON_API_KEY` 預設值
- `phison_token`: AINexus bearer token（選填），浮動/會過期，建議每輪都帶最新的

---

## 5. 使用者 chat 進來要發給 Orchestrator 格式

當使用者聊天請求進來時，系統會：

1. **轉接到容器端點：** 透過容器的 `/api/agent/chat/stream` 端點
2. **優先使用 External Access：** 如果 `external_base_url` 存在，使用它來避免內部網路限制
3. **使用內部網路：** 如果沒有 `external_base_url`，使用內部 `base_url`

**實際轉發端點：**
```
{external_base_url or base_url}/api/agent/chat/stream
```

**轉發時的處理：**
- 自動計算 `agent_id`（從 `user_id` 轉換）
- 設定環境變數（包括 MCP token、模型設定等）
- 處理 session 續傳（透過 `room_id`）

---

## 6. 我的系統接收到 Hermes 標準的 chat complete 格式

**端點：** `POST /v1/chat/completions`（Hermes 標準端點）

**請求格式（OpenAI Chat Completions 格式）：**
```json
{
  "model": "Qwen/Qwen3.6-35B-A3B-FP8",
  "messages": [
    {
      "role": "system",
      "content": "你是一位專業的 AI 助理，能夠協助使用者處理各種任務。"
    },
    {
      "role": "user",
      "content": "你好，請自我介紹一下"
    }
  ],
  "stream": true,
  "temperature": 0.7,
  "max_tokens": 1024
}
```

**回應格式（SSE Streaming）：**
```
data: {"choices":[{"delta":{"content":"你好"},"index":0}]}

data: {"choices":[{"delta":{"content":"！我是一個 AI 助理，專門協助使用者處理各種任務。"},"index":0}]}

data: [DONE]
```

**特點：**
- 支援 SSE（Server-Sent Events）串流回應
- 符合 OpenAI Chat Completions API 格式
- 支援續傳 session（透過 `X-Hermes-Session-Id` header）
- 支援長期記憶（透過 `X-Hermes-Session-Key` header）

---

## 7. 明天要測試情境：使用者輸入到我的系統再到 Orchestrator

**測試流程：**
1. **使用者登入** → 前端取得 `user_id`
2. **第一次呼叫** → `POST /api/session/ensure` 建立容器
3. **拿到 chat_endpoint** → 系統回傳容器的聊天端點
4. **使用者輸入訊息** → 前端 POST `/api/agent/chat/stream`
5. **系統轉發** → 透過 `external_base_url` 或 `base_url` 轉發到容器
6. **容器處理** → Hermes 處理對話並回傳 SSE stream
7. **系統回傳** → 將 SSE stream 轉發給前端
8. **前端顯示** → 即時顯示 AI 回應

**測試重點：**
- 容器建立是否成功
- 檔案上傳是否正常（config.yaml, SOUL.md, mcp.json, phison_mcp_bridge.py）
- 聊天轉發是否流暢
- SSE streaming 是否正常
- Model 選擇是否生效
- MCP token 是否正確傳遞

---

## 8. 經 Orchestrator 建立好回應給我的系統最後給使用者

**完整流程：**
1. **建立容器** → `POST /api/session/ensure` 呼叫 orchestrator 建立容器
2. **上傳檔案** → `POST /api/v1/users/{user_id}/files` 上傳必要的檔案
3. **啟動容器** → Orchestrator 啟動容器並回傳容器資訊
4. **取得容器資訊** → 系統解析 `baseUrl` 和 `externalBaseUrl`
5. **寫入設定** → 透過容器的 `/api/agent/prepare` 端點寫入設定
6. **回傳給使用者** → 系統回傳 `chat_endpoint` 給前端
7. **聊天生效** → 前端使用 `chat_endpoint` 進行後續對話

**關鍵回應格式：**
```json
{
  "status": "created",
  "base_url": "http://agent-worker-xxxx:8080",
  "external_base_url": "http://orchestrator:5080/workers/xxxx",
  "chat_endpoint": "http://agent-worker-xxxx:8080/api/agent/chat/stream",
  "swagger_url": "http://localhost:xxxxx/docs",
  "agent_id": "user_demo001",
  "user_id": "demo001"
}
```

---

## 9. Orchestrator 回復 Hermes 標準格式轉給使用者

**回應格式（從 Orchestrator）：**
```json
{
  "id": "a1b2c3d4e5f6",
  "name": "agent-worker-a1b2c3d4e5f6",
  "image": "hermes-agent:latest",
  "userId": 42,
  "status": "running",
  "baseUrl": "http://agent-worker-a1b2c3d4e5f6:8080",
  "externalBaseUrl": "http://orchestrator:5080/workers/a1b2c3d4e5f6",
  "exitCode": null
}
```

**轉換給使用者格式：**
```json
{
  "status": "created",
  "base_url": "http://agent-worker-a1b2c3d4e5f6:8080",
  "external_base_url": "http://orchestrator:5080/workers/a1b2c3d4e5f6",
  "chat_endpoint": "http://agent-worker-a1b2c3d4e5f6:8080/api/agent/chat/stream",
  "swagger_url": "http://localhost:xxxxx/docs",
  "agent_id": "user_demo001",
  "user_id": "demo001"
}
```

**轉換邏輯：**
- 解析 `status`：created 或 existing
- 解析 `baseUrl` 作為內部網路 URL
- 解析 `externalBaseUrl` 作為外部訪問 URL（如果存在）
- 生成 `chat_endpoint`：`{base_url}/api/agent/chat/stream`
- 生成 `swagger_url`：如果啟用 `PUBLISH_CHILD_PORTS`，提供可訪問的 swagger URL

---

## 10. 規劃：每一次使用者聊天都調用查詢這個使用者容器有沒有在

**實作策略：**
1. **容器存在檢查：** 在每次聊天前調用 `/api/v1/workers` 端點
2. **容器狀態檢查：** 確認容器狀態為 "running"
3. **自動重啟：** 如果容器存在但未運行，自動啟動容器
4. **重新建立：** 如果容器不存在，自動重新建立容器
5. **優化：** 使用 caching 減少不必要的查詢

**實作位置：**
- 在 `/api/agent/chat/stream` 端點開始時加入容器檢查邏輯
- 可以新增 `ensure_user_runtime` 函式來統一處理容器狀態

**偽代碼：**
```python
async def ensure_container_running(user_id: str) -> dict:
    # 查詢容器是否存在
    workers = requests.get(f"{ORCHESTRATOR_URL}/api/v1/workers")
    
    # 檢查容器狀態
    for worker in workers:
        if worker["userId"] == convert_user_id(user_id):
            if worker["status"] != "running":
                # 嘗試啟動容器
                # 如果啟動失敗，重新建立
                pass
            return worker
    
    # 容器不存在，建立新容器
    return orchestrator_client.ensure_user_runtime(user_id, agent_dir)
```

---

## 11. 規劃：每一次聊天都要更新檔案能否透過上面內容更新上去

**實作策略：**
1. **檔案同步檢查：** 在每次聊天前檢查本地檔案是否已更新
2. **增量上傳：** 只上傳變更的檔案，減少網路傳輸
3. **強制重新上傳：** 如果設定檔有重大變更，強制重新上傳所有檔案
4. **檔案版本管理：** 記錄檔案版本，避免重複上傳相同檔案
5. **錯誤處理：** 如果上傳失敗，提供重試機制

**實作位置：**
- 在 `services.ensure_hermes_profile_exists` 函式中加入檔案同步邏輯
- 新增 `sync_files_to_orchestrator` 函式來處理檔案同步

**偽代碼：**
```python
async def sync_files_to_orchestrator(user_id: str, agent_dir: str) -> bool:
    # 取得遠端檔案列表
    remote_files = get_remote_files(user_id)
    
    # 比較本地和遠端檔案
    for filename in required_files:
        local_file = Path(agent_dir) / filename
        if not remote_files.get(filename) or file_has_changed(local_file, remote_files[filename]):
            # 上傳變更的檔案
            upload_file(user_id, local_file)
    
    return True
```

**檔案變更檢測：**
- 使用檔案修改時間（mtime）
- 使用檔案內容雜湊（SHA-256）
- 結合兩種方式提高準確性

---

## 12. 目前問題總結

### 11.1. "容器 ensure 失敗: too many values to unpack (expected 2)"

**錯誤位置：** `orchestrator_client.py:308`

**錯誤描述：**
```
"detail": "容器 ensure 失敗: too many values to unpack (expected 2)"
```

**推測原因：**
1. **API 回應格式異常：** Orchestrator 的 POST `/api/v1/workers` 端點返回的資料格式不符合預期
2. **陣列解包錯誤：** `_extract_base_url` 函式返回的陣列長度超過 2，但代碼只準備了 2 個變數接收
3. **欄位名稱變更：** API 回應中可能沒有 `baseUrl` 或 `externalBaseUrl` 欄位，改用其他欄位名稱
4. **回應類型錯誤：** API 可能返回非 JSON 格式的回應（例如純字串的 worker ID）

**已修復方案：**
- 明確解包前 2 個元素：`base_url, external_base_url = extract_result[0], extract_result[1]`
- 加入非 JSON 回應處理邏輯，當 POST 返回字串時解析為 worker ID 再 GET 完整資料
- 強化 URL 欄位提取，兼容不同命名慣例（`baseUrlInternal`, `internalUrl`, `url`, `externalUrl`, `publicUrl`）
- 加入對長度 0 和 1 的特殊處理

### 11.2. 檔案上傳時出現 evil.txt 錯誤

**錯誤現象：**
```json
{
  "path": "../evil.txt",
  "absolutePath": null,
  "status": "failed",
  "error": "Path is not allowed."
}
```

**推測原因：**
1. **路徑安全檢查：** Orchestrator 有路徑安全檢查，阻止檢案跳出指定目錄
2. **檔名包含路徑遍歷：** 檔名中包含 `../` 路徑遍歷字元
3. **權限限制：** 檔案沒有寫入 `/home/phison/ainexus/agent-data/{user_id}` 目錄的權限

**已修復方案：**
- 更新檔案狀態檢查，從 `"success"` 改為支持 `"written"` 或 `"success"`
- 確保上傳的檔案都是安全的檔名，不包含路徑遍歷字元

### 11.3. 檔案上傳數量不符

**錯誤現象：**
```
檔案上傳數量不符: 預期 4, 實際 3
```

**推測原因：**
1. **檔案上傳失敗：** 其中一個檔案上傳失敗
2. **檔案狀態檢查錯誤：** 狀態檢查邏輯錯誤，誤判上傳失敗的檔案為成功
3. **API 回應格式變更：** API 回應中的 `writtenCount` 欄位不準確

**已修復方案：**
- 更新檔案狀態檢查邏輯，支持 `"written"` 和 `"success"` 兩種狀態
- 加入詳細的日誌記錄，顯示每個檔案的上傳結果

---

## 13. 未修改項目（僅記載）

**未修改檔案和功能：**
1. `/api/session/ensure` 端點的主要邏輯（僅修復 orchestrator 回應處理）
2. `/api/agent/chat/stream` 端點的主要邏輯
3. 檔案上傳流程（僅修復狀態檢查）
4. MCP 設定相關功能
5. Session 處理邏輯
6. Room 鎖定機制

**需要後續實作的功能：**
1. 每次聊天前的容器狀態檢查（第 10 點）
2. 每次聊天前的檔案同步邏輯（第 11 點）
3. 健康檢查端點
4. 盡控和日誌系統
5. 錯誤重試機制
6. 負載均衡和連線池

**測試項目：**
1. 容器建立流程的完整測試
2. 聊天轉發流程的端到端測試
3. 檔案上傳和同步的測試
4. 錯誤處理和重試的測試
5. 效能測試和壓力測試

---

## 總結

本報告記載了 0722 晚間遇到的技術問題和相關的 API 格式：
1. 詳細記載了所有 API 端點的輸入輸出格式
2. 紀錄了完整的系統流程和測試情境
3. 列出了所有已知問題和推測原因
4. 提供了未來實作的規劃和測試項目
5. 已修復了 "too many values to unpack" 和檔案上傳相關問題

**關鍵修復：**
- 修復了 Orchestrator 回應格式解析錯誤
- 加入了非 JSON 回應處理邏輯
- 強化了 URL 欄位提取機制
- 更新了檔案狀態檢查邏輯

**下一步行動：**
1. 執行完整系統測試
2. 實作容器狀態檢查機制
3. 實作檔案同步機制
4. 加入盡控和日誌系統
5. 優化錯誤處理和重試邏輯