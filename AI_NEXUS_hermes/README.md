# AI_NEXUS_hermes

`hermes-agent/` 業務邏輯層的獨立版本：hermes config.yaml/mcp_servers 產生、ACP 對話執行、
「一個帳號一個容器」的 ensure/建立邏輯（`runtime_manager.py`）都在這支服務裡。**不**包含
前端、後端、資料庫；也不管容器實際存在哪台機器、docker.sock/volume 怎麼掛進來——那是
部署這支服務的人決定的基礎設施（docker.sock 本身要從外部掛進容器）。

## 架構：兩段式呼叫（跟 hermes-agent 正式系統已驗證的模式一致）

```
[別人的前端/後端]
   │ ① POST /api/session/ensure {user_id}   ← 只打一次，登入/第一次進聊天室時
   ▼
[這支服務，此時扮演「入口」]
   │  ensure 該 user_id 專屬容器（runtime_manager.py，docker.sock）
   │  → 呼叫該容器自己的 /api/agent/prepare 把 config.yaml 等先寫好
   │  → 預設把 phison-ainexus 設成 resident
   ▼
回傳 { agent_id, base_url, chat_endpoint }
   │
   │ ② 之後每一輪對話，直接打 base_url 的 /api/agent/chat/stream
   ▼         不再經過步驟①打的那個入口
[user_id 專屬的容器，此時扮演「這個使用者的 runtime」——跑的是同一份程式碼]
```

一個帳號目前對應一個 agent_id（`user_{user_id}`），multi-agent 沒做，但 `EnsureSessionPayload`
之後要加 `agent_id` 覆寫欄位就能拓展，不用大改。

## 容器怎麼建：docker.sock 或同事的 orchestrator（可切換）

`runtime_manager.py::ensure_user_runtime()` 有兩條路，開關是 `ORCHESTRATOR_URL` 環境變數：

- **沒設定**（預設）：自己用 docker.sock 建容器，就是上面驗證過的那條路。
- **有設定**：整個委派給 `orchestrator_client.py`，POST 到 `{ORCHESTRATOR_URL}/api/v1/workers`，
  用同事服務建的容器，回傳的 `base_url` 直接沿用。main.py/其他所有程式碼完全不用改。

⚠️ `orchestrator_client.py` 裡的 payload/回應欄位名稱是根據草案 `hermes_dockerPOST架構.txt`
猜的，**不是同事確認過的正式規格**——跟同事對齊實際 URL/欄位後，只要改這一支檔案。
走 orchestrator 模式時，CRUD 的 `GET /api/users`（列表）/`GET /api/users/{id}`/`DELETE` 還沒有
對應的委派邏輯（草案沒定義這幾支），呼叫會直接報錯，等同事有等效端點再補。

## 跟 hermes-agent/ 的關係

大部分檔案是從 `../hermes-agent/` 已驗證過的原始碼直接複製或小幅裁切而來，**不是重寫**：

| 檔案 | 來源 | 差異 |
|---|---|---|
| `acp_client.py` | 逐字複製 | 無（已包含 0720 resume_session bug 修復） |
| `expert_catalog.py` | 逐字複製 | 無 |
| `mcp_services.py` | 逐字複製 | 無 |
| `approval_settings.py` | 逐字複製 | 無 |
| `services.py` | 參考 `services.py::ensure_hermes_profile_exists` 改寫 | 拿掉 `hermes profile create` CLI 呼叫（見下）；多加 per-turn `model` 覆寫 |
| `main.py` | 參考 `main.py::agent_chat_stream` 改寫 | 拿掉 `runtime_manager.py`／`/api/runtime/ensure`；MCP 商店端點precisely 對齊 |
| `phison_mcp_bridge.py` | **新增** | AINexus 動態專家路由（recommend-experts → expert-response） |
| `mock_ainexus_server.py` | **新增，僅供本機測試** | 模擬 AINexus 的兩支 REST API |
| `runtime_manager.py` | 逐字複製，只改容器命名前綴 | 避免跟 hermes-agent 自己 clone 出來的 `hermes-runtime-<id>` 撞名 |

### 一個今晚驗證出來、跟正式 `hermes-agent/services.py` 不同的地方

`services.py::ensure_hermes_profile_exists` 原本會呼叫 `hermes profile create` CLI（即使
明知它在新路徑上一律誤報「已存在」，見 `hermes-agent/docs` 的既有筆記）。今晚實測：
全新的 `HERMES_HOME` 目錄只要有 `config.yaml` + `SOUL.md`，`hermes mcp list/test` 和
`hermes chat`/`hermes acp` 都能正常運作，完全不需要先跑這支 CLI。所以這支服務**省略了
這一步**。這不影響 `hermes-agent/services.py`（那邊沒動），只是這支獨立服務用了更簡單、
一樣驗證過可行的作法。

## 今晚已經用真實元件端到端驗證過的東西

不是憑推論寫的，是實際跑起來看到結果的：

1. `hermes mcp list` / `hermes mcp test phison-ainexus` — 在真的 `hermes` CLI（容器內
   `hermes-agent==0.18.2`）裡確認 `mcp_servers.<name>.enabled: true` 這個 schema 正確、
   `phison_mcp_bridge.py` 能被正確發現並列出 `query_phison_expert` 工具。
2. 完整一輪 `POST /api/agent/chat/stream`（走這支新 `main.py`，不是手改的設定檔）——
   Claude（`LLM_PROVIDER=native`）主動呼叫 `query_phison_expert`，該工具打了兩支 REST
   （`recommend-experts` → `expert-response`，指向本機 `mock_ainexus_server.py`），結果
   正確串流回來。
3. MCP 憑證的 `${MCP_<NAME>_<FIELD>}` 間接引用機制——`config.yaml` 產出內容跟預期完全
   一致：
   ```yaml
   mcp_servers:
     phison-ainexus:
       command: python3
       args: ["/opt/data/phison_mcp_bridge.py"]
       enabled: true
       env:
         PHISON_API_URL: ${MCP_PHISON_AINEXUS_PHISON_API_URL}
         PHISON_TOKEN: ${MCP_PHISON_AINEXUS_PHISON_TOKEN}
   ```
4. per-turn `model` 欄位——這輪請求帶的 `model` 值，直接反映在這輪重寫出的 `config.yaml`
   的 `model.default`。
5. `/api/agent/prepare` 真的能在第一句聊天之前，就把 config.yaml/SOUL.md 寫好（不用等
   `/api/agent/chat/stream` 才觸發）。
6. `docker build` 真的能把這支服務自己 build 成 image（`ai-nexus-hermes:latest`）。
7. **完整 `/api/session/ensure` 流程**——在真的 Docker 網路上，用這個 image 起一個
   「入口」容器（掛 docker.sock + `/opt/data`），呼叫 `/api/session/ensure {user_id}`：
   真的用 docker.sock 自己 clone 自己的 image、建立 `ainexus-hermes-<user_id>` 子容器、
   子容器內部自動把 `config.yaml`/`SOUL.md`/`mcp.json` 寫好（沒等第一句聊天）；重複呼叫
   同一個 `user_id` 正確回傳 `"status":"existing"`（冪等）；子容器的 `/health`/
   `/api/agent/chat/stream` 可以被同網路上的其他服務用容器名稱直接打，不用再經過
   入口容器。（測試用 `docker network create` 建的獨立網路，第一次沒接自訂網路時
   會因為 Docker 預設 bridge 網路沒有內建 DNS 而連不到容器名稱——這不是程式碼問題，
   正式部署一定是 docker-compose 或其他自訂網路，跟現有 hermes-agent 的部署方式一樣。）

## 已知缺口（誠實列出，不是漏做沒發現）

- **LLM 沒有穩定「主動」呼叫 `query_phison_expert`**：明確下指令（「請用 xxx 工具查」）
  時 100% 會呼叫，且結果正確；但只說「幫我查一下出勤」這種模糊問法，Claude Haiku 有時
  會先反問細節而不是先呼叫工具，即使 SOUL.md 已經加了強制規則也沒完全穩定。這是
  prompt/模型層面的行為，不是 MCP 或程式碼有問題（配線已經證實正確）。正式環境會換成
  Phison 的模型，行為可能不同，建議用真的目標模型重新調 SOUL.md 措辭，而不是繼續用
  Haiku 硬調。
- **容器生命週期**：`ensure_user_runtime` 只做到冪等 ensure + 掛掉自動重啟，沒有閒置
  自動關閉/刪除——這在 `hermes-agent/docs/01_orchestrator_split_plan.md` 本來就是標記
  未解決的項目，這裡維持一樣的範圍，等真的有資源壓力再回頭做。
- **真實 Phison 內網沒測過**：`phison_mcp_bridge.py` 對真實 `192.168.41.133:1145` 端點、
  真實 Token、正式模型端點（`https://ainexus.phison.com/...`）都沒驗證過，只驗證了本機
  mock server + Claude 代替模型那條路。

## 環境變數

複製 `.env.example` 成 `.env`：

- `LLM_PROVIDER=native` + `LLM_NATIVE_PROVIDER=anthropic` + `LLM_MODEL=anthropic/...` +
  `ANTHROPIC_API_KEY=...`：本機測試用 Claude。**不要把 Claude API key 寫進任何會被 commit
  的檔案**，這把 key 之前已經在別的檔案裡外洩過一次。
- 不設定 `LLM_PROVIDER` 就照舊打 Phison 的 `custom` 端點（正式路徑）。
- 每個 agent 各自的 `PHISON_TOKEN`（AINexus bearer token）透過
  `POST /api/agent/{agent_id}/mcp/phison-ainexus/credentials` 設定，不是全域環境變數——
  這樣不同使用者可以用不同的 AINexus 帳號。

## API 端點

**入口角色用（① 建立/Ensure，需要 docker.sock）**
- `POST /api/session/ensure` — body `{user_id, system_prompt?, model?, phison_token?}`，
  回傳 `{agent_id, base_url, chat_endpoint}`

**④ 使用者 CRUD（也是入口角色，需要 docker.sock）**
- `POST /api/users` — Create，跟 `/api/session/ensure` 是同一套邏輯，只是 REST 風格命名
- `GET /api/users` — Read，列出所有使用者（容器名稱/狀態）
- `GET /api/users/{user_id}` — Read，查單一使用者
- `DELETE /api/users/{user_id}?wipe_data=false` — Delete，停止並移除容器；
  `wipe_data=true` 才會連 profile 資料夾一起刪，預設不刪（安全預設值）

**每個使用者的 runtime 用（步驟②，Swagger 也可以單獨測）**
- 聊天請求可以帶 `user_id`（自動換算成 `f"user_{user_id}"`），或直接帶 `agent_id`
  （保留給未來 multi-agent 用）——不用兩個都記，帶 `user_id` 最簡單。
- `POST /api/agent/prepare` — 提前把 config.yaml/SOUL.md 寫好，不用等第一句聊天
- `POST /api/agent/chat/stream` — 核心對話端點，body 見 `config.py::ChatRequest`
  （`agent_id`, `room_id`, `system_prompt`, `message`, 可選的 `model`）
- `POST /api/agent/approve-write` — 核准 hermes 觸發的 request_permission
- `GET /api/mcp/catalog` — 母版 MCP 目錄
- `GET /api/agent/{agent_id}/mcp` — 這個 agent 的 MCP 選擇狀態
- `POST /api/agent/{agent_id}/mcp/{mcp_name}/selection` — 設為 resident/optional/移除
- `POST /api/agent/{agent_id}/mcp/{mcp_name}/credentials` — 填入憑證（如 `PHISON_TOKEN`）
- `GET /health` — 檔案系統寫入失敗回 503（硬依賴）；docker.sock 連不到只降級成
  `"docker": "unavailable (...)"`，不影響整體 healthy（純 runtime 角色不需要它）

所有端點都有內建 Swagger UI，啟動後開 `http://<host>:8643/docs` 就能直接點著測，
不用額外裝東西。

## 本機測試流程

```bash
python mock_ainexus_server.py   # 起本機假 AINexus（response_1784630885607.json 當假資料）
docker build -t ai-nexus-hermes:latest .
docker run -d --name ai-nexus-hermes-proxy \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v <host路徑>:/opt/data -p 8643:8643 \
  -e LLM_PROVIDER=native -e LLM_NATIVE_PROVIDER=anthropic \
  -e LLM_MODEL=anthropic/claude-haiku-4-5-20251001 -e ANTHROPIC_API_KEY=... \
  ai-nexus-hermes:latest
# 開 http://localhost:8643/docs 用 Swagger 測 /api/session/ensure
```
