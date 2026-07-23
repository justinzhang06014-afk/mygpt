# 0723 進度整理

延續 `0722_night_problem.md` 的問題往下查，今天最主要的產出是**確認了一個 0722 報告完全沒發現的架構性問題**，並依此重新設計、實作、驗證了整條遠端聊天轉發鏈路。

---

## 1. 今天最關鍵的發現：main.py 不會被烤進 docker 管理端的 image

一開始沿用 0722 報告的假設——遠端容器跟本機 docker.sock 模式一樣，跑的是我們自己這份 `ai-nexus-hermes` wrapper（main.py 在容器裡），聊天靠 ACP+CLI。追查後發現這個假設是錯的：

- **docker 管理端實際沒有拿到 main.py**：我們透過 `/api/v1/users/{user_id}/files` 傳給對方的，一直都只有 `config.yaml`／`SOUL.md`／`mcp.json`／`phison_mcp_bridge.py` 這 4 個「資料」檔案。這個端點的本質是掛一個資料 volume 進容器，不是把程式碼塞進 image——這兩件事在 docker 的世界裡是完全不同的機制。
- **ACP 協定天生沒辦法跨主機**：翻了 hermes-agent 套件自己內建的 ACP 進入點 `acp_adapter/entry.py`，第 4 行寫明「stdout is reserved for ACP JSON-RPC transport」——ACP 就是父子行程之間的 stdio 管道，只能本機直接 spawn 子行程才能用。而 docker_README.md 給的 orchestrator API 只有 create/list/get/delete/proxy 這幾支 HTTP 端點，**沒有任何 exec/attach 這種「連進容器內部跟裡面的行程講話」的能力**。
- 結論：要嘛把 main.py 真的包成 image 交給 docker 管理端（需要協調對方把白名單加進去，屬於部署層級的事），要嘛接受遠端容器就是**原生 hermes-agent**（沒有 main.py），改用它自己內建的 HTTP 介面（Gateway 的 `api_server` 平台）來橋接聊天。

**決定走後者**：main.py 只留在我們自己系統（192.168.85.82），遠端容器維持原生 hermes-agent，聊天用 HTTP 打過去。

---

## 2. 確認 Gateway 的真實 API 規格（不是憑空猜的，逐行對照原始碼）

翻了實際安裝的 `gateway/platforms/api_server.py`：

- 認證：`Authorization: Bearer {API_SERVER_KEY}`，逐字比對（`_check_auth`，約第1049-1071行）。**沒有 `API_SERVER_KEY` 這個 server 甚至不會啟動**（第817行原文：`connect() refuses to start without API_SERVER_KEY`）。
- 聊天端點：`POST /v1/chat/completions`，OpenAI Chat Completions 格式，`X-Hermes-Session-Id` header 帶 session/房間延續。
- SSE 格式：逐段 `data: {json}\n\n`，`choices[0].delta.content` 放文字，正常結束送 `data: [DONE]\n\n`（第2436-2564行）。
- **重要細節**：如果這輪 agent 執行失敗/被截斷，最後一個 chunk 的 `delta` 是空的，改成用 `finish_reason`（非 `"stop"`）+ 頂層 `error.message` 表達失敗原因——一開始沒處理這塊，會導致「回答莫名斷掉、使用者不知道為什麼」，後來有補上。

---

## 3. 具體改了什麼

### `orchestrator_client.py`
- `API_SERVER_ENABLED`/`API_SERVER_HOST`/`API_SERVER_KEY`/`API_SERVER_CORS_ORIGINS` 四個環境變數放回容器建立 payload（中途因為以為要走 ACP+CLI 拿掉過一次，確認架構後放回來）。
- `API_SERVER_KEY` 改成每次建容器隨機生成，並新增 `_store_api_key`/`get_stored_api_key`：生成的 key 存到本地 `agent_dir/.api_server_key`——因為 orchestrator 的 `GET /api/v1/workers(/{id})` 不會把 `environment` 內容吐回來，這把 key 只有建立當下這一次機會拿到，之後要轉發聊天只能靠本地存的這份。409 撞到既有容器時改讀舊檔案，不覆寫成這次沒被用到的新值。
- 新增 `find_user_worker()`：查這個 user 在遠端是否已有 worker，不篩狀態。
- 新增 `sync_env_token()`：只重傳 `.env`（裝 token 的檔案），不動其他 4 個檔案。
- 新增 `ensure_user_runtime_synced()`：每輪聊天前呼叫——容器不存在就走完整建立流程，已存在就只補傳最新 `.env`，回傳格式跟 `ensure_user_runtime()` 統一（都是 `base_url`/`worker_id`/`api_server_key` 這種 snake_case 命名，呼叫端不用管這輪是新建還是既有）。
- `ensure_user_runtime()` 現在會在建容器前，順手把本地已經存在的 `.env`（如果有）一起上傳——修好一個測試中發現的洞：原本第一次 `ensure` 帶的 phison_token 從來沒有真的送到遠端，只有等到「容器已存在」那個分支才會傳。
- **修好兩個會讓上傳 100% 失敗的既有 bug**：
  1. `_upload_files_to_orchestrator` 的 `finally` 區塊 tuple 解包寫錯（`for _, (_, file_obj) in files_to_upload`），每次上傳結束都會拋例外蓋掉原本該回傳的結果。
  2. 判斷上傳成功與否是看 `upload_data.get("writtenCount", 0)`，但真實 API 回應根本沒有這個欄位，永遠會判定「數量不符」而回傳失敗，即使檔案全部寫成功了。已改成看 `files[].status` 逐筆判斷。
- **改回 Phison 正式規格**：容器 `environment` 裡的 `LLM_BASE_URL`/`LLM_MODEL` 原本寫死指向一台測試推論機（`http://10.102.196.43:18299/InferenceModel43/v1`），現在改成跟 `config.py` 的正式預設值同一套（Phison AINexus 正式端點、`Qwen/Qwen3.6-35B-A3B-FP8`），可用環境變數覆寫。

### `main.py`
- 新增 `_orchestrator_chat_stream()`：把聊天轉發到 `{base_url}/v1/chat/completions`，帶 `Authorization: Bearer {api_server_key}` + `X-Hermes-Session-Id: {room_id}`，SSE 逐段解析成純文字串流吐回去（跟本機 ACP 那條路輸出格式一致，呼叫端不用管這輪走哪條路）；失敗/截斷的 `finish_reason` 也會顯示成可讀的警告訊息，不會靜默吞掉。
- `agent_chat_stream`：orchestrator 模式下，先確認/建立遠端容器（`ensure_user_runtime_synced`），拿到 `base_url`+`api_server_key` 就走上面的 HTTP 橋接，本機 ACP 只在拿不到才當退路。
- `_ensure_session_impl`：**拿掉了容器建立後打 `/api/agent/prepare` + MCP selection/credentials 這三支呼叫**（遠端模式專用）——這是這次連續測試炸出來的阻塞性 bug，容器一建好就去打一個原生 hermes-agent 根本沒有的端點，直接 502，情境A完全跑不完。本機 docker.sock 模式（`runtime_manager.py`）維持原樣不變，那條路的容器真的有這些端點。
- `chat_endpoint` 修正：遠端模式下回傳我們自己服務的位址（用 `request.base_url` 組），不是容器的 `base_url`——使用者不該、也打不通容器（沒有 `api_server_key`）。
- Swagger 範例的 `model` 欄位改回 Phison 正式模型名稱（`Qwen/Qwen3.6-35B-A3B-FP8`），拿掉測試用的 `InferenceModel43`。

### `requirements.txt`
- 新增 `httpx`（main.py 轉發聊天要用到，之前只是別人套件的間接依賴，沒有直接宣告）。

---

## 4. 怎麼驗證的

專案自帶的 venv 壞了（`pyvenv.cfg` 記的 base python 路徑是舊使用者資料夾，已經不存在），沒辦法直接跑。改用系統 Python 3.14 補裝缺的套件（`mcp`、`agent-client-protocol`、`docker`、`httpx` 等），**確認 main.py 整支服務可以真的用系統 Python 啟動起來**，不是只測獨立函式。

搭了一個符合 `docker_README.md` 合約的假 orchestrator（模擬 `/api/v1/users/{id}/files`、`/api/v1/workers` CRUD），外加模擬容器內原生 gateway 的 `/v1/chat/completions`（含 Bearer 認證檢查、SSE 串流、可模擬錯誤 finish_reason）。

**情境A（ensure）驗證通過**：呼叫 → 4個檔案 + `.env`（token）都正確上傳 → 容器建立 → 回應正確帶回我們自己的 `chat_endpoint`，不是容器位址。也測了「沒帶 token」「同時開兩個不同使用者」兩個邊界情況，正常。

**情境B（chat）驗證通過**：呼叫 → 正確轉發到假容器的 `/v1/chat/completions`，認證 header／session header 都對 → 拿到回覆 → 帶新 token 再打一次，確認容器沒有被重建（同一個 worker id）、遠端 `.env` 確實更新成新 token → 模擬遠端執行失敗的情況，確認錯誤訊息會顯示出來、不會靜默斷掉。

---

## 5. 明天實測前，需要注意、我這台機器測不到的事

1. **`HERMES_IMAGE` 是否真的對得上 docker 管理端的白名單**——這個假 orchestrator 不會幫你檢查，只有打真的 192.168.41.173 才知道（`GET /api/v1/agents` 可以查）。
2. **真實 hermes-agent gateway 的行為是否跟讀原始碼得出的結論完全一致**——`Authorization: Bearer`、`/v1/chat/completions`、SSE 格式這些都是從套件原始碼讀出來的，邏輯上該是對的，但沒有實機驗證過。
3. **長駐 MCP 子行程的 token 沒辦法「活著換」**（今天稍早已經用真的 MCP stdio session 實測驗證過）：容器一旦開機、`phison_mcp_bridge.py` 子行程一旦啟動，就凍結住當時的 `PHISON_TOKEN`，之後不管怎麼更新 `.env`，這個活著的子行程都讀不到新值，除非改成「每次工具呼叫時才讀檔案」（目前先不動這支檔案，維持現狀）。
4. **遠端容器的 `/opt/data` 目錄結構要不要跟本機 `PROFILES_BASE_DIR` 完全一致**——這個還沒實測確認過，之前提過待確認。

---

## 6. 總結

今天最大的價值不是修 bug（雖然確實修了 3 個既有的、會讓整個流程 100% 失敗的 bug），而是**把「遠端容器到底跑什麼、聊天到底怎麼橋接過去」這個從 0722 就沒人問過的根本問題問出來、查清楚、定案**，並且照這個定案重新接好整條線、真的跑過一次完整流程。剩下的風險都是「這台機器連不到真環境」造成的，邏輯層面已經盡量驗證過了。
