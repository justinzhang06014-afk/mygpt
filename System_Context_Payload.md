# 🧬 MyGPT-MultiAgent-Platform | System Context Payload

## 📌 1. 系統核心定位 (System Identity)
* **專案名稱**：MyGPT-MultiAgent-Platform (代號: Hermes)
* **核心架構**：Multi-Agent 房間協同、高防禦型前後端分離系統
* **本檔用途**：提供 Agent 載入時的最高指導憲法，防止脫軌、確保技術棧一致性

## 💻 2. 技術棧與防禦邊界 (Tech Stack & Guards)
### 前端：LMFrontend
* **核心框架**：Vue 3 + Vite
* **狀態管理**：Pinia (採用防禦性設計，嚴格禁止跳頁/重整時遺失 Token 與房間 Context)
* **通訊機制**：WebSocket 斷線自動重連機制

### 後端：LMBackend
* **主控核心**：.NET 10 Web API + Controller 模式 (非 Minimal API)
* **代理大腦**：Python FastAPI (負責 Agent 調度、LangChain、LlamaIndex 運算)
* **資料儲存**：PostgreSQL (主資料) + ChromaDB (向量 RAG 資料)

## 🗂️ 3. 核心資料特徵 (Core Schema Index)
### 房間與對話 (Room & Message)
* **Room (房間)**：獨立的 Agent 運行環境。綁定特定 Model、Temperature、Prompt 字典。
* **Room-Agent 綁定**：一個房間可配置單一或多個 Agent 協同運作。
* **跨房間記憶 (Cross-Room Memory)**：全域長短期記憶庫，允許經授權的 Agent 跨房提取使用者偏好。

### 擴充生態 (Plugins & MCP)
* **MCP 市集 (Model Context Protocol Market)**：
  * 標準化 Plugin 接入規範 (Tools / Prompts / Resources)
  * 所有自定義外掛、爬蟲、API 串接皆須封裝為標準 MCP 服務
  * 後端提供動態註冊與權限控管機制

## 🛡️ 4. 運行鐵律 (System Guardrails)
1. **防脫軌機制**：AI 產生程式碼時，必須嚴格遵守上述技術棧（.NET 10 Controller、Vue 3 Pinia），嚴禁幻想不存在的套件。
2. **前後端分離防禦**：API 回傳格式必須統一為 `{ success: boolean, data: T, error: string }`。
3. **安全審查**：所有透過 MCP 執行的外部指令與 RAG 注入內容，必須經過 Token 邊界審查，防止 Prompt Injection。
