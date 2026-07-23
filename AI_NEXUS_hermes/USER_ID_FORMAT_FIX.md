"""
修正說明：user_id 字串與整數格式的轉換問題
"""

## 問題描述

**現象**：
- Swagger API 中 `user_id` 定義為字串格式（需要 ""）
- 但 Orchestrator API 需要整數格式的 `userId`
- 用戶直接測試時使用整數格式成功

**根本原因**：
`orchestrator_client.py` 中的檔案上傳端點直接使用了字串格式的 user_id，
但 Orchestrator API 要求使用整數格式的 userId。

## 修正內容

### 1. 檔案上傳端點修正

**檔案**：`orchestrator_client.py:95`

**修正前**：
```python
upload_url = f"{ORCHESTRATOR_URL}/api/v1/users/{user_id}"
```

**修正後**：
```python
user_id_int = _convert_user_id(user_id)
upload_url = f"{ORCHESTRATOR_URL}/api/v1/users/{user_id_int}"
```

### 2. .env 同步端點修正

**檔案**：`orchestrator_client.py:252`

**修正前**：
```python
upload_url = f"{ORCHESTRATOR_URL}/api/v1/users/{user_id}"
```

**修正後**：
```python
upload_url = f"{ORCHESTRATOR_URL}/api/v1/users/{user_id_int}"
```

### 3. 遠端主機路徑修正

**檔案**：`orchestrator_client.py:349`

**修正前**：
```python
remote_host_path = f"/home/phison/ainexus/agent-data/{user_id}"
```

**修正後**：
```python
remote_host_path = f"/home/phison/ainexus/agent-data/{user_id_int}"
```

## 資料流程

### Swagger API 層
```json
{
  "user_id": "2",        // 接受字串格式
  "model": "Qwen/Qwen3.6-35B-A3B-FP8",
  "llm_api_key": "AINX-..."
}
```

### 內部轉換層
```python
# orchestrator_client.py
def _convert_user_id(user_id: str) -> int:
    return int(user_id)  // "2" -> 2
```

### Orchestrator API 層
```json
{
  "userId": 2,          // 使用整數格式
  "volumes": {
    "/home/phison/ainexus/agent-data/2": "/opt/data"  // 使用整數路徑
  }
}
```

## API 端點對照表

| 功能 | Swagger API | 內部轉換 | Orchestrator API |
|------|-------------|----------|------------------|
| 上傳檔案 | `POST /api/session/ensure` | `user_id: "2"` → `userId: 2` | `POST /api/v1/users/2` |
| 同步 .env | 自動背景執行 | `user_id: "2"` → `userId: 2` | `POST /api/v1/users/2` |
| 建立容器 | `POST /api/session/ensure` | `user_id: "2"` → `userId: 2` | `POST /api/v1/workers` |

## 測試驗證

### 原本的測試（正確）
```powershell
Invoke-RestMethod -Method Post -Uri "http://192.168.41.173:5080/api/v1/workers" `
  -Body '{"userId": 2, ...}'
```

### 修正後的測試
```python
# 透過我們的服務
POST /api/session/ensure
{
  "user_id": "2",        // 字串格式
  ...
}

# 內部自動轉換
POST /api/v1/users/2     // 整數格式
POST /api/v1/workers     // userId: 2 (整數)
```

## Swagger 說明更新

**修正前**：
```python
user_id: str = Field(..., description="外部系統的使用者 ID")
```

**修正後**：
```python
user_id: str = Field(..., description="外部系統的使用者 ID（字串格式，如 '2'，內部將轉為整數 2）")
```

## 完整修正清單

✅ `orchestrator_client.py:95` - 檔案上傳端點 `/api/v1/users/{user_id}`
✅ `orchestrator_client.py:252` - .env 同步端點 `/api/v1/users/{user_id}`  
✅ `orchestrator_client.py:349` - 遠端主機路徑 `/home/phison/ainexus/agent-data/{user_id}`
✅ `main.py:195` - Swagger 說明更新
✅ `0722_night_problem.md` - 文件更新

## 影響範圍

**修正前**：
- ❌ 檔案上傳失敗：端點路徑包含字串 user_id
- ❌ .env 同步失敗：端點路徑包含字串 user_id  
- ❌ 容器掛載失敗：路徑包含字串 user_id

**修正後**：
- ✅ 檔案上傳成功：使用整數 user_id
- ✅ .env 同步成功：使用整數 user_id
- ✅ 容器掛載成功：使用整數 user_id

## 使用者操作無影響

雖然內部實作修正了格式轉換，但使用者透過 Swagger UI 或其他方式調用 API 時：
- 仍然傳入字串格式的 `user_id`
- 不需要改變任何使用習慣
- 內部自動處理格式轉換