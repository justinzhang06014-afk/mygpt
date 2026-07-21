# AI_NEXUS Hermes 測試環境

依照 hermes-agent 架構初始化 hermes 容器並進行測試

## 功能特色

- ✅ 自動初始化 hermes profile
- ✅ 支援 MCP (Model Context Protocol) 配置
- ✅ 支援 Agentic Hub 專家匯入
- ✅ 自動建立 config.yaml, SOUL.md, mcp.json
- ✅ Docker 容器管理
- ✅ 串流聊天測試客戶端
- ✅ 支援記憶功能、工具使用測試

## 專案結構

```
AI_NEXUS_hermes/
├── main.py           # 主程式：初始化 hermes 容器
├── test.py           # 測試客戶端：模擬 POST 訊息和接收訊息
├── requirements.txt  # Python 依賴
├── data/             # 資料目錄
│   ├── profiles/     # hermes profiles
│   ├── uploads/      # 上傳檔案暫存
│   └── static/       # 靜態檔案
├── mcp.json          # MCP 伺服器配置母版
├── response.json     # Agentic Hub 專家清單
└── skills_catalog.json # 技能目錄
```

## 安裝步驟

### 1. 安裝依賴

```bash
cd AI_NEXUS_hermes
pip install -r requirements.txt
```

### 2. 配置檔案

程式會自動從 `../hermes-agent/` 複製以下檔案：
- `mcp.json` - MCP 伺服器配置
- `response.json` - Agentic Hub 專家清單
- `skills_catalog.json` - 技能目錄

### 3. 執行主程式初始化

```bash
python main.py
```

這會：
1. 建立必要的目錄結構
2. 複製 hermes 配置檔案
3. 初始化測試 Agent
4. 建立 Docker 容器
5. 啟動 hermes 服務

## 使用測試客戶端

### 啟動測試客戶端

```bash
python test.py
```

### 測試模式

測試客戶端提供四種測試模式：

1. **基本對話測試** - 測試基本文字對話
2. **MCP 工具測試** - 測試網頁搜尋、圖片生成等 MCP 工具
3. **記憶功能測試** - 測試 hermes 的長期記憶功能
4. **互動式聊天** - 手動輸入訊息進行對話

### 自訂測試

您可以在 `test.py` 中修改以下設定：

```python
# 修改測試 Agent ID
agent_id = "agent_test_001"

# 修改測試 Room ID
room_id = "room_test_001"

# 修改系統提示詞
system_prompt = "你是一位專業的 AI 助理..."
```

## 部署設定

### 本地端測試

預設連接到本地端 Docker 容器：

```python
BASE_URL = "http://localhost:8643"
```

### 生產環境部署

修改 `test.py` 中的設定連接到生產伺服器：

```python
BASE_URL = "http://192.168.41.173:5080"
```

或直接修改主機設定：

```python
# main.py 或 test.py
FUTURE_HOST = "http://192.168.41.173:5080"
FUTURE_API_ENDPOINT = f"{FUTURE_HOST}/api/v1/workers"
```

## 設定檔案說明

### config.yaml

Hermes 的主配置檔案，包含：
- 模型設定
- 記憶體設定
-核准模式設定
- 終端機設定
- 工具設定
- MCP 伺服器設定

### mcp.json

MCP 伺服器配置檔案，包含：
- 伺服器清單
- 連線設定
- 憑證欄位
- 選擇狀態（resident/optional_installed）

### SOUL.md

Agent 的系統提示詞檔案，定義 Agent 的個性和行為模式。

## Docker 容器設定

### 容器配置

```json
{
  "userId": 1,
  "image": "nousresearch/hermes-agent:latest",
  "environment": {
    "PROFILES_BASE_DIR": "/opt/data/profiles"
  },
  "volumes": {
    "/path/to/hermes-workspace": "/opt/data"
  }
}
```

### 掛載的目錄

- `/opt/data` - 資料根目錄
- `/opt/data/profiles` - Agent profiles
- `/opt/data/uploads` - 上傳檔案
- `/opt/data/static` - 靜態檔案

## 環境變數

可透過環境變數調整設定：

```bash
# API 金鑰
export PHISON_API_KEY="your_api_key"

# 模型設定
export LLM_MODEL="Qwen/Qwen3.6-35B-A3B-FP8"
export LLM_BASE_URL="https://ainexus.phison.com/api/external/v1"
```

## 故障排除

### 容器無法啟動

檢查 Docker 是否執行：
```bash
docker ps
```

查看容器日誌：
```bash
docker logs hermes-worker-1
```

### 連線失敗

確認容器正在運作：
```bash
curl http://localhost:8643/
```

### 配置檔案錯誤

檢查複製的配置檔案：
```bash
ls -la data/
```

## 進階功能

### 新增預設 MCP 伺服器

在 `main.py` 的 `initialize_hermes_profile()` 中加入：

```python
mcp_state = get_agent_mcp_state(agent_id)
mcp_state["server_name"]["selection"] = "resident"
write_agent_mcp_state(agent_id, mcp_state)
```

### 自訂記憶設定

修改 `write_isolated_config()` 中的記憶設定：

```python
"memory": {
    "memory_enabled": True,
    "user_profile_enabled": True,
    "nudge_interval": 10,  # 每 10 輪對話提醒更新記憶
    "write_approval": True,  # 啟用寫入前確認
}
```

## API 端點

Hermes 服務提供以下 API：

- `POST /api/agent/chat/stream` - 串流聊天
- `GET /api/monitor/stats` - 監控統計
- `POST /api/runtime/ensure` - 確保 Runtime 存在

## 授權

MIT License

## 聯絡方式

如有問題請聯開發團隊。