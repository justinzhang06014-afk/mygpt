# Config.py 筆記 — Hermes Agent Proxy 全域配置

> 生成日期：2026-07-21
> 對比基準：Hermes Agent 官方文檔（hermes-agent.nousresearch.com）
> 專案：hermes-agent-proxy（企業級多租戶包裝平台）

---

## 1. 原始檔案

```python
import os

# API Keys (透過環境變數注入)
PHISON_API_KEY = os.getenv("PHISON_API_KEY")
AINEXUS_API_KEY = os.getenv("AINEXUS_API_KEY")

# 基礎設定
BASE_URL = "http://10.1.11.118:8002/v1"
PROFILES_BASE_DIR = "/app/hermes_core_data"
PROXY_PORT = 8643

# 管理員 Token
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "default_token")
```

---

## 2. 官方 Hermes Agent 配置規範

### 2.1 配置優先級（官方）

| 順序 | 來源 | 說明 |
|------|------|------|
| 1 | CLI arguments | 單次執行覆蓋 |
| 2 | `~/.hermes/config.yaml` | 所有非敏感設定 |
| 3 | `~/.hermes/.env` | 環境變數與金鑰 |
| 4 | Built-in defaults | 安全預設值 |

### 2.2 目錄結構（官方）

```
~/.hermes/
├── config.yaml       # 非敏感設定
├── .env              # API 金鑰與憑證
├── auth.json         # OAuth 憑證
├── SOUL.md           # Agent 身份
├── memories/         # 持久記憶
├── skills/           # Agent 技能
├── cron/             # 排程任務
├── sessions/         # Gateway 會話
├── logs/             # 日誌
└── mcp.json          # MCP 伺服器清單
```

### 2.3 模型提供商配置（官方）

```yaml
# 官方 config.yaml 範例
model:
  provider: "openrouter"          # 或 anthropic, google, openai, custom 等
  default: "anthropic/claude-sonnet-4"
  base_url: "https://api.openrouter.ai/v1"  # 可選自訂端點
  api_key: "${OPENROUTER_API_KEY}"          # 建議引用 .env

terminal:
  backend: "local"                # 或 docker, ssh, modal, daytona

# 其他設定
compression:
  enabled: true
```

### 2.4 敏感資訊處理（官方）

- **API 金鑰 → `.env`**：`hermes config set` 會自動路由
- **Never commit `.env`**：版本控制排除
- **外部 Secret Manager**：支援 Bitwarden、1Password
- **Secret Redaction**：生產環境可過濾工具輸出中的敏感資訊

### 2.5 多租戶/多 Profile（官方）

- **s6-overlay**：容器內 PID 1 進程管理員
- **Per-profile isolation**：每個 profile 獨立 HOME、config、memory、session
- **Per-profile gateway**：s6-overlay 自動註冊 gateway 服務
- **Enterprise pinning**：管理員可鎖定特定配置值防止使用者覆蓋

---

## 3. Config.py vs 官方規範 對比

### 3.1 對照表

| 項目 | Config.py 做法 | 官方建議 | 差異分析 |
|------|---------------|----------|---------|
| **API Key 儲存** | `os.getenv()` 讀取，不硬編碼 | `.env` 檔案 + `hermes config set` | ✅ 一致，都採環境變數 |
| **BASE_URL 寫死** | `"http://10.1.11.118:8002/v1"` 硬編碼 | `config.yaml` 中 `model.base_url` 或 `.env` 引用 | ⚠️ 風險：修改需改碼重部署 |
| **無 config.yaml** | 完全不產生或讀取 Hermes config.yaml | 主要配置來源 | ⚠️ 差異：proxy 與 hermes 各自獨立管理 |
| **ADMIN_TOKEN** | `os.getenv("ADMIN_TOKEN", "default_token")` | 無直接對應，但建議不寫預設值 | 🔴 **高風險**：預設值可被猜測 |
| **PROFILES_BASE_DIR** | `"/app/hermes_core_data"` 硬編碼 | 每個 profile 獨立 HOME | ⚠️ 與官方多 profile 概念不同 |
| **無 model provider** | 完全不涉及模型層配置 | `config.yaml` 中 `model.provider/default` | ℹ️ Proxy 不管理模型層 |
| **無 terminal backend** | 完全不涉及 | `config.yaml` 中 `terminal.backend` | ℹ️ Proxy 不管理執行環境 |
| **無 compression** | 完全不涉及 | `config.yaml` 中 `compression.enabled` | ℹ️ Proxy 不管理壓縮層 |

### 3.2 Config.py 在整體架構中的定位

```
┌─────────────────────────────────────┐
│  hermes-agent-proxy (FastAPI)       │
│  ──────────────────────────────     │
│  config.py  ← 僅管理 Proxy 層       │
│    ├── API Keys (讀 .env)           │
│    ├── 網路端點 (硬編碼)            │
│    └── 管理員 Token                │
│                                     │
│  services.py  ← 動態生成 each agent │
│    └── config.yaml（寫入容器內）    │
│                                     │
├─────────────────────────────────────┤
│  hermes-agent (容器內)              │
│  ──────────────────────────────     │
│  ~/.hermes/config.yaml  ← 官方配置  │
│  ~/.hermes/.env              ← 金鑰  │
│  ~/.hermes/mcp.json        ← MCP    │
└─────────────────────────────────────┘
```

**結論**：Config.py 僅是 **Proxy 層** 的組態，Hermes Agent 層的配置由 `services.py` 動態生成後寫入每個容器的 `config.yaml`。兩者各司其職。

---

## 4. 你的方法 vs 其他方法 對比

### 4.1 方法對比表

| 維度 | 你的方法 | 方法 A：單一 Container | 方法 B：純 s6-overlay 多 Profile | 方法 C：直接 API 呼叫 |
|------|---------|---------------------|---------------------------|-------------------|
| **架構** | FastAPI Proxy → 動態生成多容器 | 單一容器 + 路由 | 單一容器 + s6-overlay 多 profile | 前端直接調用 Hermes API |
| **Isolation** | Docker per-user 完全隔離 | 共享環境，無隔離 | Profile 級隔離 | 無隔離 |
| **動態配置** | 每用戶獨立 config.yaml + mcp.json | 共用一份配置 | 每 profile 獨立 | N/A |
| **擴展性** | 可無限擴充 agent | 受限於單機資源 | 受限於單機資源 | 受限 |
| **管理複雜度** | 高（需管理 proxy + docker） | 低 | 中 | 低 |
| **安全邊界** | Docker 邊界 + Proxy 驗證 | 無 | Profile 邊界 | 無 |

### 4.2 為什麼你的方法比較適合企業場景

1. **真正的 Isolation**：Docker per-user → 任何一個 agent 的資源耗用、命令執行、檔案存取完全不會影響其他用戶
2. **動態配置**：`services.py` 為每個 agent 即時生成 `config.yaml` 和 `mcp.json`，不需預先設定
3. **MCP 商店系統**：母版目錄 + per-agent selection → 管理員集中管理，使用者按需選擇
4. **ACP 人機協同**：`acp_client.py` 整合了權限請求 + approve/deny 流程，這是標準 Hermes 沒有包裝的

### 4.3 你的方法相比其他方法的風險

#### 🔴 高風險

| 風險 | 說明 | 影響 |
|------|------|------|
| **ADMIN_TOKEN 預設值** | `os.getenv("ADMIN_TOKEN", "default_token")` → 若未設定，任何人可用 "default_token" 登入管理員後台 | 任意 MCP catalog 增刪改、技能清單篡改 |
| **BASE_URL 硬編碼** | `"http://10.1.11.118:8002/v1"` 寫死在程式碼 → 環境變遷需重編/重部署 | 無法透過環境變數切換不同環境 |
| **PROFILES_BASE_DIR 硬編碼** | `"/app/hermes_core_data"` 寫死 → 與官方 `~/.hermes/` 路徑不一致 | 若官方 CLI 直接操作會找不到目錄 |

#### 🟡 中風險

| 風險 | 說明 | 影響 |
|------|------|------|
| **Docker 權限** | Proxy 直接執行 `docker run` 創建容器 → 若 Proxy 以 root 執行，所有容器也以 root | 容器逃逸風險增加 |
| **config.yaml 動態生成** | `services.py` 動態寫入 agent config → 若注入點未消毒，可注入惡意 YAML | Agent 行為被操控 |
| **無 rate limiting** | Proxy 層無限流 → DDoS 或暴力破解 ADMIN_TOKEN | 服務中斷 |
| **HTTP (非 HTTPS)** | 管理員後台 `/admin` 以 HTTP 傳輸 token | Token 可被 Network sniffing 竊取 |

#### 🟢 低風險

| 風險 | 說明 | 影響 |
|------|------|------|
| **無 config.yaml 對齊檢查** | Proxy config.py 不檢查 agent 的 config.yaml 格式 | 動態生成失敗時錯誤不直觀 |
| **技能 catalog 依賴外部** | 依賴 `hermes skills search --json` 的真實 identifier | 若市集 API 變更，精選清單失效 |

---

## 5. Config.py 每行解析

```python
import os
```
- **用途**：讀取環境變數
- **官方對照**：Hermes Agent 也用 `os.getenv()` 讀取 `.env`，兩者模式一致
- **建議**：可考慮改用 `python-dotenv` 自動載入 `.env` 檔案（非必須）

```python
PHISON_API_KEY = os.getenv("PHISON_API_KEY")
AINEXUS_API_KEY = os.getenv("AINEXUS_API_KEY")
```
- **用途**：讀取外部模型/API 服務的憑證
- **官方對照**：與 Hermes Agent 的 `.env` 模式一致 → `api_key: "${PHISON_API_KEY}"`
- **風險**：若未設定，`None` 值會被傳入 downstream 導致 500 錯誤，應增加 empty check

```python
BASE_URL = "http://10.1.11.118:8002/v1"
```
- **用途**：模型 API 端點（PHISON/AINEXUS 的 gateway URL）
- **官方對照**：官方建議寫在 `config.yaml` 的 `model.base_url` 或 `.env` 引用
- **風險**：🔴 環境相關值硬編碼，無法透過 CI/CD 環境變數覆蓋

```python
PROFILES_BASE_DIR = "/app/hermes_core_data"
```
- **用途**：所有 agent profile 資料的根目錄（替代官方 `~/.hermes/`）
- **官方對照**：官方每個 profile 在 `~/.hermes/profiles/<name>/`
- **風險**：🟡 自訂路徑與官方不同，官方 CLI 工具（如 `hermes doctor`）無法直接檢查 proxy 管理的 profile

```python
PROXY_PORT = 8643
```
- **用途**：FastAPI Proxy 服務端口
- **官方對照**：官方 Hermes Gateway 預設 port 未固定，可自訂
- **風險**：無特別風險，但需確保防火牆開啟

```python
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "default_token")
```
- **用途**：管理員後台驗證 token
- **官方對照**：官方無此概念（Hermes Gateway 用 OAuth/user allowlist）
- **風險**：🔴 **預設值 "default_token" 是嚴重安全問題**
  - 任何人若猜到此值，可完全接管 MCP catalog 與技能精選清單
  - 無 rate limiting 保護，可暴力猜測
  - 無 HTTPS，token 傳輸可被攔截

---

## 6. 建議改進清單

### 優先級：P0（立即處理）

| # | 改進 | 原因 | 建議做法 |
|---|------|------|---------|
| 1 | 移除 ADMIN_TOKEN 預設值 | 安全漏洞 | `ADMIN_TOKEN = os.getenv("ADMIN_TOKEN")` + startup check 若為 None 則 crash |
| 2 | BASE_URL 改為環境變數 | 環境隔離需求 | `BASE_URL = os.getenv("BASE_URL", "http://10.1.11.118:8002/v1")` |

### 優先級：P1（短期處理）

| # | 改進 | 原因 | 建議做法 |
|---|------|------|---------|
| 3 | 引入 python-dotenv | 統一 .env 管理 | `from dotenv import load_dotenv; load_dotenv()` |
| 4 | PROFILES_BASE_DIR 改為環境變數 | 部署靈活性 | `os.getenv("PROFILES_BASE_DIR", "/app/hermes_core_data")` |
| 5 | 加入 API Key 空值檢查 | 防止 None 傳播 | 啟動時 check 必要 key 是否已設定 |

### 優先級：P2（中期改進）

| # | 改進 | 原因 | 建議做法 |
|---|------|------|---------|
| 6 | 管理員後台加 HTTPS / Reverse Proxy | 傳輸安全 | Nginx reverse proxy + TLS |
| 7 | 加入 rate limiting | 防暴力破解 | `slowapi` 或 Nginx rate limit |
| 8 | Proxy config 與 agent config.yaml 對齊檢查 | 一致性 | 驗證動態生成的 config 符合官方 schema |

---

## 7. 與其他 Hermes 架構的關鍵差異總結

| 維度 | 官方 Hermes Agent | 你的 Proxy 架構 |
|------|------------------|----------------|
| **配置入口** | `~/.hermes/config.yaml` + `hermes config` CLI | Proxy `config.py` + `services.py` 動態生成 |
| **多租戶** | s6-overlay + multi-profile（單容器內） | Docker per-user（完全隔離） |
| **MCP 管理** | 每個 agent 自己的 `mcp.json` | 母版目錄 + per-agent selection（有管理後台） |
| **Skill 管理** | `hermes skills install/search` | 精選清單 + 安裝審核流程 |
| **安全模型** | 內建 approval、secret redaction、寫入沙箱 | Docker 邊界 + ADMIN_TOKEN + 無內建 approval |
| **人機協同** | 原生 ACP 支援 | 完整包裝的 approve/deny UI 流程 |
| **監控** | 無內建 Docker 監控 | `monitor.py` + `monitor_dashboard.py` 自訂監控 |

---

*本筆記基於 Hermes Agent 官方文檔（hermes-agent.nousresearch.com）生成，對比資料截至 2026-07-21。*
