# Hermes Docker 對接規劃（問題1 主文件）

> 這份文件是給你慢慢看、之後再逐段回來跟我討論用的。所有結論都對照了實際原始碼行號，
> 不是憑空推論。日期：2026-07-20。

## 1. 現況：誰已經在做什麼

`LlmController.cs:518` 的註解已經寫明現在的設計：「backend 完全不碰 Docker，權限收斂
在 hermes-agent-proxy 那一側」。實際流程：

```
C# CreateAgentRoom 聊天前
  → POST http://hermes-agent-proxy:8643/api/runtime/ensure { user_id }
  → hermes-agent-proxy 用 docker.sock 建立/確認 hermes-runtime-<user_id> 容器
  → 回傳 base_url，C# 之後打這個 base_url 的 /api/agent/chat/stream
```

也就是說 `hermes-agent-proxy` 現在自己身兼兩個角色：

1. **業務邏輯層**：config.yaml / mcp.json / skills_catalog / approvals / session
   mapping / ACP 串流（`services.py`、`mcp_services.py`、`skills_catalog.py`、
   `approval_settings.py`、`acp_client.py`）
2. **基礎設施層**：`runtime_manager.py` 直接用 `docker.sock` 建立/管理容器

你朋友要接手的，就是把「角色 2」整個切出去，變成一個獨立的 orchestrator 服務。
切完之後職責表：

| 職責 | 誰負責 |
|---|---|
| config.yaml / mcp.json / skills 內容產生 | 你（hermes-agent） |
| approvals / session_mapping / ACP 串流邏輯 | 你（hermes-agent） |
| Docker 容器建立/啟停/刪除/健康檢查/資源限制 | 你朋友的 orchestrator |
| 檔案存放（存檔）、簡易 CRUD 查詢 | 你朋友的 orchestrator（視是否共用 volume 而定，見下） |

## 2. `hermes_dockerPOST架構.txt` 逐欄解讀

```json
{
  "userId": "42",
  "agentId": "agent_a26dcad41262",
  "environment": {
    "AINEXUS_API_KEY": "example-key",
    "LOG_LEVEL": "info",
    "HERMES_HOME": "/opt/data/profiles/agent_a26dcad41262"
  },
  "volumes": { "/host/path/to/user-data": "/opt/data:rw" },
  "resource_limits": { "nano_cpus": 1000000000, "mem_limit": "2g", "mem_reservation": "1g" }
}
```

| 欄位 | 對照現有程式碼 | 評語 |
|---|---|---|
| `userId` | `runtime_manager.py:82` 的 `hermes-runtime-{user_id}` | 一致，沒問題 |
| `agentId` | — | **需要跟朋友確認**：見下方「granularity 問題」 |
| `environment.HERMES_API_KEY`/`OPENAI_API_KEY` | `main.py:237-238` 用 `PHISON_API_KEY` | 範例寫的 `AINEXUS_API_KEY` 跟現有變數名不一樣，要對齊 |
| `environment.HERMES_HOME` | `services.py:135` 每次請求動態設定 | **這格範例是錯的**，見下 |
| `volumes` | `runtime_manager.py:100` `host_data_root/users/<user_id>` → `/opt/data` | 一致，沒問題 |
| `resource_limits` | `runtime_manager.py` 目前完全沒有設定任何限制 | 朋友加這個是對的，數值要自己拍板 |
| 回應 `baseUrl`/`port` | `runtime_manager.py:91` `http://{container_name}:8643` | 一致，用容器名稱走內部 DNS，不對外開 port |

### 2.1 關鍵問題：容器 granularity 是 per-user 還是 per-agent？

範例的 `environment.HERMES_HOME` 指到單一 agent 的資料夾
（`.../profiles/agent_a26dcad41262`），但現在的架構是**一個容器服務一個使用者底下
所有 agent**——每次對話時才在 subprocess 層動態把 `HERMES_HOME` 指到當下那個 agent
的資料夾（`services.py:135`），容器本身完全不綁死單一 agent。

如果照範例做成「一個 agent 一個容器」，代表規模假設完全不同：1000 人 × 每人多個
agent，容器數量會爆炸性增加，而且跟現有 `runtime_manager.py`（一人一容器）的假設
直接衝突。

**這是要先問清楚朋友的第一個關鍵問題**：他的 POST 設計是 per-user 還是 per-agent？
我的建議是維持 per-user（跟現在一樣），`HERMES_HOME` 只需要設到
`PROFILES_BASE_DIR`（如 `/opt/data/profiles`）這一層當預設值，實際每次對話用哪個
agent 由 `hermes-agent` 這邊在 subprocess 呼叫時再動態覆蓋（現有機制已經在做，
不用改）。

### 2.2 關鍵問題：CRUD API 到底需不需要

`docker-compose.yaml:83` 顯示 `hermes-agent-proxy` 現在跟核心容器**共用同一個 host
資料夾**（`./hermes_core_data:/opt/data`），所以現在寫 config.yaml/mcp.json 是
**直接寫檔案**，完全不需要經過任何 API。

朋友提到「CRUD 簡易查詢」意味著新架構下 `hermes-agent-proxy` 可能不再跟容器共用
同一個檔案系統（例如未來 orchestrator 跑在不同主機、或用真正的 volume 管理而非
bind mount）。**這件事必須先問清楚**：

- 如果還是同一台機器、同一個 shared volume → 完全不需要 CRUD API，繼續直接寫檔
  最簡單，CRUD 當備援/除錯用途就好。
- 如果之後會拆到不同主機/不共享檔案系統 → 那所有 config.yaml/mcp.json/
  approvals.json/session_mapping.json 的讀寫都要改走他的 CRUD API，這是牽動
  `services.py`/`mcp_services.py`/`skills_catalog.py`/`approval_settings.py`/
  `services.py` 的 session mapping 全部 5 個模組的大改，要先確認再動手。

我建議：**先假設維持 shared volume（風險最低、改動最少）**，等真的要拆主機再升級
成走 CRUD API。

## 3. 與這份文件配套的第二份文件

生命週期定義、跟朋友的溝通策略、以及「hermes 本身有沒有處理這塊」的研究結果，
寫在同資料夾的 `02_lifecycle_and_communication.md`，避免這份文件太長。
