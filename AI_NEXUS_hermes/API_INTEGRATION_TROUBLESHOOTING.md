# API 對接錯誤排查指南

## ❌ 錯誤訊息分析

```
Error: Internal Server Error
{
  "detail": "容器 ensure 失敗: 呼叫 orchestrator 失敗: 400 Client Error: Bad Request for url: http://192.168.41.173:5080/api/v1/workers"
}
```

**400 Bad Request** 表示我們發送的格式不符合對方的 API 預期。

---

## 🔍 可能的原因和修正方案

### **原因1: userId 格式問題** ⭐ 最可能

**問題**: 你的 `user_id="demo001"` 是字串，但對方 API 可能只接受數字

**檢查對方 API**:
```http
GET http://192.168.41.173:5080/api/v1/agents
```
先看看對方的 agents whitelist 有哪些可用 image。

**修正方案A: 轉換為數字**
```python
# 在 orchestrator_client.py 中修改
import re

def _convert_user_id_to_numeric(user_id: str) -> int | str:
    """當 user_id 包含數字時提取數字部分"""
    match = re.search(r'\d+', user_id)
    if match:
        return int(match.group())
    return user_id

# 在 ensure_user_runtime 中使用
numeric_user_id = _convert_user_id_to_numeric(user_id)
payload = {
    "userId": numeric_user_id if numeric_user_id != user_id else user_id,
    ...
}
```

**修正方案B: 改用純數字 ID**
```http
POST /api/session/ensure
{
  "user_id": "1234",  # 改用純數字
  ...
}
```

---

### **原因2: image 不在 whitelist** ⭐ 很可能

**問題**: `HERMES_IMAGE="nousresearch/hermes-agent:latest"` 可能不在對方的 whitelist 中

**檢查對方 whitelist**:
```http
GET http://192.168.41.173:5080/api/v1/agents
```

**預期回應**:
```json
[
  { "image": "nousresearch/hermes-agent:latest" }
]
```
或者
```json
[
  { "image": "hermes-agent:latest" }
]
```

**修正方案**:
```bash
# 方法1: 修改環境變數使用對方 whitelist 中的 image
export HERMES_IMAGE=hermes-agent:latest

# 方法2: 直接修改 HAERME_IMAGE 預設值
# 在 orchestrator_client.py 中：
HERMES_IMAGE = os.getenv("HERMES_IMAGE", "hermes-agent:latest")
```

---

### **原因3: volumes 路徑格式問題** 

**問題**: 路徑可能不符合對方的 `AllowedBindPrefixes` 設定

**對方可能的設定**:
```json
{
  "AllowedBindPrefixes": ["/home/phison/ainexus", "/shared/nexus"]
}
```

**修正方案**: 確保路徑在允許的前綴內
```bash
# 檢查你的 HERMES_DATA_ROOT 是否在對方允許的前綴內
export HERMES_DATA_ROOT=/home/phison/ainexus
```

---

### **原因4: environment 變數問題**

**問題**: `PHISON_API_KEY` 可能不是對方預期的環境變數

**對方可能預期的變數**:
```json
{
  "environment": {
    "LOG_LEVEL": "info"  // 文件範例
  }
}
```

**修正方案**: 嘗試簡化 environment
```python
# 在 orchestrator_client.py 中修改
payload = {
    "userId": user_id,
    "image": HERMES_IMAGE,
    # "environment": {  // 先試試不提供 environment
    #     "PHISON_API_KEY": os.getenv("PHISON_API_KEY", ""),
    # },
    "volumes": {
        remote_host_path: "/data",
    },
}
```

---

## 🧪 逐步測試流程

### **步驟1: 檢查對方的能清單**
```http
GET http://192.168.41.173:5080/api/v1/agents
```
確認有哪些可用的 image。

### **步驟2: 測試最簡單的請求**
使用 curl 直接測試：
```bash
curl -X POST http://192.168.41.173:5080/api/v1/workers \
  -H "Content-Type: application/json" \
  -d '{
    "userId": 123,
    "image": "hermes-agent:latest",
    "volumes": {
      "/home/phison/ainexus/users/test123": "/data"
    }
  }'
```

### **步驟3: 修正後再測試**

根據步驟1和2的結果調整你的 orchestrator_client.py。

---

## 📝 立即可以嘗試的修正

### **方法1: 改用純數字 userId**
在你的 Swagger 測試時使用：
```json
{
  "user_id": "1234",
  "llm_api_key": "AINX-...",
  "model": "Qwen/Qwen3.6-35B-A3B-FP8",
  "phison_token": "eyJ...",
  "system_prompt": "你是一個得力的辦公助理"
}
```

### **方法2: 移除 environment 欄位**
修改 `orchestrator_client.py`:
```python
payload = {
    "userId": user_id,
    "image": HERMES_IMAGE,
    # 先不提供 environment 測試
    "volumes": {
        remote_host_path: "/data",
    },
}
```

### **方法3: 檢查 image 名稱**
```bash
# 先查詢對方的 whitelist
curl http://192.168.41.173:5080/api/v1/agents

# 然後修改環境變數匹配對方的格式
export HERMES_IMAGE=hermes-agent:latest  # 根據查詢結果調整
```

---

## 🎯 建議的調查順序

1. **查詢對方 agents whitelist** → GET http://192.168.41.173:5080/api/v1/agents
2. **用純數字 userId 測試** → "user_id": "1234"
3. **簡化 payload** → 先移除 environment
4. **檢查日誌輸出** → 查看實際發送的詳細內容
5. **用 curl 直接測試** → 排除程式碼層面的問題