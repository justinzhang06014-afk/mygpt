# Hermes 生命週期定義 + 跟對接方的溝通策略（問題1 第二份文件）

> 日期：2026-07-20。這份文件回答兩件事：(a) hermes 本身有沒有處理容器生命週期，
> (b) 有/沒有的話，我們該怎麼定義、怎麼跟朋友溝通。

## 1. 研究結論：hermes 官方確實有一套原生 lifecycle，但跟我們現在的用法不對齊

我查了 NousResearch 官方文件（`hermes-agent.nousresearch.com/docs`），重點如下
（來源見文末，**這是官方文件描述的「官方 Docker image」行為，還沒有對照我們自己
`hermes-agent/Dockerfile` 實際跑出來的版本做實測驗證，只能當作研究起點，正式採用
前一定要進容器裡對照**）：

### 1.1 官方推薦架構：一個容器裝所有 profile，不是一個容器一個 profile

官方文件明講：**"one container hosting all profiles"** 是推薦作法，理由是引入
`s6-overlay` 當容器 PID 1 之後，能做到：

- 建立新 profile（`hermes profile create <name>`）是「動態註冊，不用重建容器」
- 每個 profile 有自己的 s6 監督服務槽（`/run/service/gateway-<name>/`），當掉會
  自動重啟，不用等 Docker 重啟容器
- 共用同一份 Python/Node 執行環境快取，減少磁碟/記憶體重複開銷
- log 集中管理（`docker logs -f hermes` + 每個 profile 自己的
  `logs/gateways/<profile>/current`）

生命週期指令長這樣（在容器內部執行）：

```bash
docker exec hermes hermes -p coder gateway start
docker exec hermes hermes -p coder gateway stop
docker exec hermes hermes -p coder gateway restart
```

狀態存在 `gateway_state.json`，容器重啟後，boot-time reconciler 只會自動復原「明確
還在跑」的 profile。

### 1.2 這跟我們現在的架構不一樣，而且**不建議照抄**

這裡要老實說清楚一個矛盾，不能只挑對我們有利的部分講：

- 官方這套「一個容器裝所有 profile」的前提，是**所有 profile 互相信任**（同一個
  操作者、同一套風險等級）。
- 我們的場景是 **1000 個互不相識的使用者**，每個 agent 的 `tools.enabled` 都開了
  `bash`（`services.py:255`）、`terminal.backend: local`——也就是每個使用者的
  agent 都能在容器裡執行任意 shell 指令。如果照官方建議把所有使用者的 profile
  塞進同一個容器，等於讓 1000 個互不信任的使用者共用同一個 Linux kernel
  namespace、共用同一個容器裡的 bash——這不是效能問題，是資安邊界問題。

**結論：現在 `runtime_manager.py` 選擇「一人一容器」是對的，不要因為官方建議
「一容器多 profile」就改成大家共用。** 官方建議適用於「同一個人/團隊管理自己的
多個 profile」，不適用於多租戶 SaaS。

但官方文件裡有兩個東西，值得**在我們自己的「一人一容器」模型裡借用**：

1. **資源限制的合理數值參考**：官方建議記憶體 2-4GB、CPU 2 核心（如果用到瀏覽器
   自動化類技能如 Playwright 會需要更多，沒用到的話 1GB 也夠）。這可以直接拿來
   當 `resource_limits` 的預設值起點，比我們自己憑感覺猜數字可靠。
2. **s6 式監督（自動重啟）的精神**：容器層級的「當掉自動重啟」現在
   `runtime_manager.py:115` 已經有 `restart_policy={"Name": "always"}`，這部分
   概念上已經對齊了，不用另外做。

### 1.3 Session/上下文管理：hermes 有原生機制，但兩份官方文件說法有出入

- Sessions 文件說：resume 時「模型看到的是選定的 system prompt + 目前的對話視窗
  + 這輪明確注入的內容」，而且提到**長對話是靠手動 `/compress` 指令**去壓縮，
  文件裡沒看到「自動依 token 門檻觸發壓縮」的設定鍵。
- 但另一份搜尋摘要（非官方文件本身，是聚合的部落格摘要）提到
  `~/.hermes/config.yaml` 有壓縮門檻設定，預設 0.50（用到 50% context 就自動壓縮）。

這兩個說法互相矛盾，**我沒有辦法只憑網路資料判斷哪個對我們實際安裝的版本是真的**
——這正是你在 handoff 裡一直強調的「沒有實測驗證前不要宣稱完成」的情況。等 Docker
環境可以用，我會建議直接進容器查 `hermes_cli/config.py`（跟你們之前查
`nudge_interval`/`memory.provider` 用同一招),把真正的 schema key 抓出來，而不是
相信網路上的說法。

## 2. 我們自己該怎麼定義生命週期（因為 per-user 容器這塊 hermes 沒有現成方案）

因為官方的 s6/gateway 模型不適用於我們的多租戶隔離需求，這塊**我們必須自己定義**，
不能指望 hermes 幫我們做。建議跟朋友談的 lifecycle 狀態機：

| 狀態 | 觸發時機 | 誰呼叫 |
|---|---|---|
| `ensure`（冪等建立或取得） | 使用者第一次聊天前 | 現有 `/api/runtime/ensure`，改成打朋友的 API |
| `status`（健康檢查） | 定期監控、或每次呼叫前快速確認還活著 | 建議新增，現在完全沒有 |
| `stop`（優雅停止，不刪資料） | 使用者長時間不活動、或管理員手動維護 | 建議新增 |
| `restart` | 容器異常但資料還在 | 建議新增，取代目前「壞了才手動 docker restart」 |
| `delete`（真正刪除，連資料一起處理或保留視需求） | 使用者刪除帳號、或管理員清理 | 一定要有明確的二次確認機制，這是高風險操作 |

跟朋友溝通時，我建議明確問這 4 個問題（這就是「怎麼溝通比較好」的具體做法——
把模糊的「他會做生命週期管理」拆成可以逐條核對的規格）：

1. **granularity**：他的 API 是 per-user 還是 per-agent？（見文件 1 的 2.1 節，
   這是最優先要對齊的，不對齊後面全部要重談）
2. **資源限制的實際數字**：他有沒有預設建議值？我們可以拿官方文件的 2-4GB/2 核心
   當起點討論，不用完全照抄。
3. **檔案存取模式**：走 shared volume 直接讀寫，還是一定要走他的 CRUD API？
   （見文件 1 的 2.2 節）
4. **`ensure` 的冪等性**：重複呼叫同一個 userId 會不會重建容器、還是回傳既有的？
   現有 `runtime_manager.py:86-91` 是後者（已存在就直接回傳/重啟，不重建），這個
   行為要維持一致，不然 C# 那邊的呼叫模式會壞掉。

## 資料來源

- [Docker | Hermes Agent](https://hermes-agent.nousresearch.com/docs/user-guide/docker)
- [Sessions | Hermes Agent](https://hermes-agent.nousresearch.com/docs/user-guide/sessions)
- [Configuration | Hermes Agent](https://hermes-agent.nousresearch.com/docs/user-guide/configuration/)
- GitHub issues（已知的相關 bug，供風險評估參考）：
  [#32423 Context window changes to 256K after interrupted compaction and resume](https://github.com/NousResearch/hermes-agent/issues/32423)、
  [#8506 Memory nudge never triggers when smart model routing is enabled](https://github.com/NousResearch/hermes-agent/issues/8506)
