# AI_NEXUS_Hermes 代理服務系統完整規劃 (2026-07-21 Night)

## 🎯 專案核心情境
使用者（透過前端）問：「張哲瑜今天出勤如何？」
1. **Hermes Agent** 接收到訊息。
2. **Hermes Agent** 自動發現並調用內建的 `query_phison_expert` 工具。
3. **橋接層** 自動執行 `recommend-experts` 找到「企業AI智能秘書」，並使用當前有效的 **Token** 呼叫 `expert-response` 取得結果。
4. **Hermes Agent** 將結果回覆給使用者。
5. **全程無需使用者手動介入**，Token 由系統啟動時注入或動態更新。

---

## 📂 專案目錄結構 (`AI_NEXUS_hermes/`)

```
AI_NEXUS_hermes/
├── docker_manager.py     # 模組 A：Docker 容器生命週期管理（創建、狀態、檔案掛載）
├── chat_gateway.py       # 模組 B：聊天訊息傳送與模擬測試（POST/GET）
├── phison_mcp_bridge.py  # 模組 C：Phison AINexus API 橋接（MCP Server 實現）
├── main.py               # 模組 D：FastAPI 主入口，聚合所有 Router
└── README.md             # 說明文件
```

---

## 🛠 任務目標 1：Docker 代理服務 (`docker_manager.py`)

**目標**：負責根據 `userId` 創建、管理 Hermes Agent 容器，並自動寫入配置。

### 1. 技術選型
- FastAPI (監聽 `5000` 埠)
- `docker` SDK for Python

### 2. 核心端點

#### A. `POST /api/v1/workers` (創建 Agent 容器)
1. **接收 Payload**：
   ```json
   {
     "userId": 12090,
     "image": "nousresearch/hermes-agent:latest",
     "environment": {},
     "volumes": {
       "/home/<userId>/hermes-workspace": "/opt/data"
     },
     "llm_key": "YOUR_CLAUDE_OR_PHISON_KEY",
     "model": "hermes-agent"
   }
   ```

2. **執行邏輯**：
   - **目錄建立**：在 Host 端建立 `/home/<userId>/hermes-workspace`。
   - **檔案寫入**：將配置文件寫入 Host 目錄。
     - **config.yaml 規範**：
       ```yaml
       provider: custom
       base_url: "https://ainexus.phison.com/api/external/v1"
       api_key: "<USER_PROVIDED_KEY>"
       default: "hermes-agent"
       ```
     - **mcp.json 規範**：
       見下方 `phison_mcp_bridge.py` 的配套配置。
   - **橋接腳本寫入**：將 `phison_mcp_bridge.py` 寫入 `/home/<userId>/hermes-workspace/phison_mcp_bridge.py`。
   - **容器啟動**：
     - 掛載路徑：`/home/<userId>/hermes-workspace` → `/opt/data`。
     - **環境變數注入**：
       - `PHISON_TOKEN`: 使用者在創建時提供的 Token。
       - `PHISON_API_URL`: 預設 `http://192.168.41.133:1145/api/v1/hermes/ainexus`。
     - **Agent 命名**：預設 profile 為 `default`。

#### B. `GET /api/v1/workers/{userId}` (查詢狀態)
- 返回容器 ID、狀態、名稱、Image、userId、baseUrl、exitCode，格式嚴格如下：
  ```json
  {
    "id": "container_id",
    "name": "agent-worker-xxx",
    "image": "nousresearch/hermes-agent:latest",
    "userId": 12090,
    "status": "running",
    "baseUrl": "http://agent-worker-xxx:8080",
    "exitCode": null
  }
  ```

---

## 🛠 任務目標 2：聊天測試模組 (`chat_gateway.py`)

**目標**：模擬外部使用者發送訊息，並測試 Hermes 的回應。

### 1. 技術選型
- FastAPI Router

### 2. 核心端點

#### A. `POST /chat/send` (發送聊天訊息)
1. **接收參數**：
   ```json
   {
     "userId": 12090,
     "message": "張哲瑜今天出勤如何?",
     "token": "eyJhbG...s..."  // 當前會話的有效 Token
   }
   ```
2. **執行邏輯**：
   - 透過 Docker SDK 獲取該 userId 對應容器的內部 IP。
   - 假設 Hermes 容器內暴露了 OpenAI 兼容的 `/v1/chat/completions`。
   - **關鍵**：在 Header 中加入 `Authorization: Bearer *** Token`。
   - 返回容器的回應內容。

#### B. `GET /chat/status/{userId}` (狀態模擬)
- 預留給其他系統呼叫，返回最近一次聊天狀態。

---

## 🛠 任務目標 3：Phison 專家橋接 (`phison_mcp_bridge.py`)

**目標**：提供一個標準的 MCP Server，讓 Hermes 能夠無縫調用 Phison 的 REST API。

### 1. 核心邏輯 (MCP Server 實現)

**請將此內容寫入專案根目錄的 `phison_mcp_bridge.py` 文件中。**

```python
#!/usr/bin/env python3
"""
Phison AI Nexus MCP Bridge
這是一個輕量級的 MCP Server，負責將 Hermes 的標準 MCP 請求轉換為 Phison 的 REST API 調用。
"""
import os
import json
import requests
from mcp.server.fastmcp import FastMCP

# 從環境變數讀取配置，這樣就不需要硬編碼 Token 或 URL
API_BASE = os.getenv("PHISON_API_URL", "http://192.168.41.133:1145/api/v1/hermes/ainexus")
TOKEN = os.getenv("PHISON_TOKEN", "")

# 設置 HTTP Headers，自動帶入 Token
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {TOKEN}",
    "accept": "application/json"
}

# 創建 MCP Server 實例
mcp = FastMCP("Phison AI Nexus")

@mcp.tool()
def query_phison_expert(query: str):
    """
    自動查詢 Phison AI 專家。
    此工具內部執行兩步流程：
    1. 根據 query 推薦最適合的專家。
    2. 呼叫該專家獲取回答。
    """
    if not TOKEN:
        return "Error: PHISON_TOKEN environment variable is not set."
    
    try:
        # Step 1: 推薦專家 (GetRecommendedExperts)
        rec_url = f"{API_BASE}/tools/recommend-experts"
        rec_resp = requests.post(rec_url, json={"query": query}, headers=headers)
        rec_resp.raise_for_status()
        rec_data = rec_resp.json()
        
        experts = rec_data.get("experts", [])
        if not experts:
            return "No relevant experts found."
        
        # 選擇相似度最高的專家
        top_expert = experts[0]
        expert_id = top_expert["id"]
        
        # Step 2: 呼叫專家 (GetExpertResponse)
        exec_url = f"{API_BASE}/tools/expert-response"
        exec_payload = {
            "expertId": expert_id,
            "query": query
        }
        exec_resp = requests.post(exec_url, json=exec_payload, headers=headers)
        exec_resp.raise_for_status()
        
        # 返回專家回答
        return exec_resp.text
        
    except requests.exceptions.RequestException as e:
        return f"Network error: {str(e)}"
    except Exception as e:
        return f"Internal error: {str(e)}"

if __name__ == "__main__":
    # 使用 stdio 傳輸，這是 Hermes 最標準的 MCP 連接方式
    mcp.run(transport="stdio")
```

---

## 📄 配套配置文件：`mcp.json`

**請將此內容寫入容器內的 `/opt/data/mcp.json` 文件中。**

```json
{
  "mcpServers": {
    "phison-ainexus": {
      "command": "python3",
      "args": ["/opt/data/phison_mcp_bridge.py"],
      "transport": "stdio",
      "env": {
        "PHISON_API_URL": "http://192.168.41.133:1145/api/v1/hermes/ainexus",
        "PHISON_TOKEN": "${PHISON_TOKEN}"
      }
    }
  }
}
```

---

## 🚀 執行指令

1. **實作 `docker_manager.py`**：確保它在創建容器時，將 `phison_mcp_bridge.py` 和 `mcp.json` 正確掛載到容器的 `/opt/data/` 目錄。
2. **實作 `chat_gateway.py`**：確保它能透過 Docker 容器 IP 正確發送聊天請求。
3. **實作 `main.py`**：聚合所有 Router，提供 Swagger UI。
4. **測試流程**：
   - 啟動 `main.py`。
   - 使用 Swagger 創建一個 Worker，傳入 `userId` 和 `token`。
   - 創建成功後，使用 Swagger 發送聊天訊息測試。
   - 觀察 Hermes Agent 是否自動調用了 `query_phison_expert` 並返回正確結果。

---

## 💡 關鍵技術決策說明

1. **為什麼需要 `phison_mcp_bridge.py`？**
   - Phison 的 REST API 不是標準的 MCP Server。Hermes 無法直接透過 HTTP 連接非標準 MCP 端點。
   - 透過這個輕量級橋接，我們將 REST API 包裝成標準 MCP Tool，符合 Hermes 的設計哲學。

2. **Token 如何注入？**
   - Token 在容器創建時作為環境變數 `PHISON_TOKEN` 注入。
   - `phison_mcp_bridge.py` 在啟動時讀取該變數，並用於後續的所有 REST API 呼叫。
   - 這樣做既安全，又符合最小權限原則。

3. **為什麼不直接寫 REST API 到配置檔？**
   - Hermes 的 MCP Client 期望的是 JSON-RPC 協議，而非普通的 HTTP POST。
   - 直接寫 REST API 配置會導致通訊協定不匹配，無法執行。

4. **擴展性**
   - 如果未來 Phison 提供標準 MCP Endpoint，我們可以輕鬆將 `phison_mcp_bridge.py` 替換為直接連接該 Endpoint，無需修改 Hermes 核心配置。
