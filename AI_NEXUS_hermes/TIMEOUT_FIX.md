# 建立容器時間過長問題 - 解決方案

## 問題根本原因

**發現位置**：`orchestrator_client.py:390-394`

**問題**：所有關鍵的 LLM 相關環境變數都被註解掉了：
```python
"environment": {
    # ❌ 這些環境變數被註解掉，導致容器啟動失敗
    # "PHISON_API_KEY": os.getenv("PHISON_API_KEY", PHISON_LLM_KEY),
    # "LLM_PROVIDER": "custom",  
    # "LLM_BASE_URL": os.getenv("LLM_BASE_URL", TARGET_BASE_URL),
    # "LLM_MODEL": os.getenv("LLM_MODEL", TARGET_MODEL),
    # "LLM_API_KEY": os.getenv("LLM_API_KEY", ""),
    
    "API_SERVER_ENABLED": "true",
    "API_SERVER_HOST": "0.0.0.0",
    ...
}
```

**影響**：
- hermes-agent 啟動時沒有正確的 LLM 配置
- 嘗試連接無效的預設 API 端點
- 等待 LLM 回應超過 120 秒
- 健康檢查失敗 → Readiness timed out

## 修正內容

**檔案**：`orchestrator_client.py:390-399`

**修正前**（環境變數全被註解）：
```python
"environment": {
    # "PHISON_API_KEY": os.getenv("PHISON_API_KEY", PHISON_LLM_KEY),
    # "LLM_PROVIDER": "custom",
    # "LLM_BASE_URL": os.getenv("LLM_BASE_URL", TARGET_BASE_URL),
    # "LLM_MODEL": os.getenv("LLM_MODEL", TARGET_MODEL),
    # "LLM_API_KEY": os.getenv("LLM_API_KEY", ""),
    "API_SERVER_ENABLED": "true",
    "API_SERVER_HOST": "0.0.0.0",
    "API_SERVER_KEY": api_server_key,
    "API_SERVER_CORS_ORIGINS": "*",
},
```

**修正後**（恢復所有必要環境變數）：
```python
"environment": {
    "PHISON_API_KEY": os.getenv("PHISON_API_KEY", PHISON_LLM_KEY),
    "LLM_PROVIDER": os.getenv("LLM_PROVIDER", "custom"),
    "LLM_BASE_URL": os.getenv("LLM_BASE_URL", TARGET_BASE_URL),
    "LLM_MODEL": os.getenv("LLM_MODEL", TARGET_MODEL),
    "LLM_API_KEY": os.getenv("LLM_API_KEY", ""),
    "API_SERVER_ENABLED": "true",
    "API_SERVER_HOST": "0.0.0.0",
    "API_SERVER_KEY": api_server_key,
    "API_SERVER_CORS_ORIGINS": "*",
},
```

## 預設環境變數值

**檔案**：`config.py:14-16`

```python
PHISON_LLM_KEY = "AINX-F78D2FCD53915EE37BD0871392FFBFFAF648C53C388950FC6A1F2ED8C534B249"
TARGET_BASE_URL = "https://ainexus.phison.com/api/external/v1"
TARGET_MODEL = "Qwen/Qwen3.6-35B-A3B-FP8"
```

## 完整的 Payload 對比

### 修正前（會導致超時）
```json
{
  "userId": 2,
  "image": "nousresearch/hermes-agent:latest",
  "environment": {
    "API_SERVER_ENABLED": "true",
    "API_SERVER_HOST": "0.0.0.0", 
    "API_SERVER_KEY": "",
    "API_SERVER_CORS_ORIGINS": "*"
  },
  "volumes": {
    "/home/phison/ainexus/agent-data/2": "/opt/data"
  }
}
```

### 修正後（正常運作）
```json
{
  "userId": 2,
  "image": "nousresearch/hermes-agent:latest", 
  "environment": {
    "PHISON_API_KEY": "AINX-F78D2FCD53915EE37BD0871392FFBFFAF648C53C388950FC6A1F2ED8C534B249",
    "LLM_PROVIDER": "custom",
    "LLM_BASE_URL": "https://ainexus.phison.com/api/external/v1",
    "LLM_MODEL": "Qwen/Qwen3.6-35B-A3B-FP8",
    "LLM_API_KEY": "",
    "API_SERVER_ENABLED": "true",
    "API_SERVER_HOST": "0.0.0.0",
    "API_SERVER_KEY": "",
    "API_SERVER_CORS_ORIGINS": "*"
  },
  "volumes": {
    "/home/phison/ainexus/agent-data/2": "/opt/data"
  }
}
```

## 修復後的預期行為

### 修正前的問題流程
1. 容器成功建立 ✅
2. hermes-agent 啟動，但缺少 LLM 配置 ❌
3. 嘗試連接無效的 API 端點 ❌  
4. 持續等待回應（超過 120 秒）❌
5. 健康檢查失敗 → Readiness timed out ❌

### 修正後的正常流程
1. 容器建立 ✅
2. hermes-agent 啟動，使用正確的 LLM 配置 ✅
3. 成功連接到 Phison API ✅
4. gateway 服務在幾秒內準備就緒 ✅
5. 健康檢查通過，返回容器資訊 ✅

## 測試驗證步驟

### 1. 重新啟動服務
```powershell
# 停止舊服務
# 啟動新服務
```

### 2. 檢查日誌確認修正生效
```powershell
Get-Content D:\mygpt\AI_NEXUS_hermes\logs\service.log -Tail 20
```

**應該看到**：
```
📤 [Orchestrator] 發送的 Payload: {
  "userId": 2,
  "environment": {
    "PHISON_API_KEY": "AINX...",
    "LLM_PROVIDER": "custom",
    "LLM_BASE_URL": "https://ainexus...",
    "LLM_MODEL": "Qwen/Qwen...",
    ...
  }
}
```

### 3. 測試容器建立
```powershell
POST /api/session/ensure
{
  "user_id": "2",
  "llm_api_key": "AINX-F78D2FCD53915EE37BD0871392FFBFFAF648C53C388950FC6A1F2ED8C534B249",
  "model": "Qwen/Qwen3.6-35B-A3B-FP8",
  "phison_token": "eyJ...",
  "system_prompt": "你是一個很強的辦公助理"
}
```

### 4. 驗證成功回應
```json
{
  "status": "created",
  "user_id": "2",  
  "base_url": "http://agent-worker-xxx:8642",
  "external_base_url": "http://192.168.41.173:5080/workers/xxx",
  "chat_endpoint": "https://your-server:port/api/agent/chat/stream",
  "worker_id": "xxx"
}
```

## 解決建議

### 如果仍然超時，考慮以下因素

**1. 網絡延遲**：
```bash
# 檢查到 Phison API 的連接速度
curl -w time_total -o /dev/null -s https://ainexus.phison.com/api/external/v1/models
```

**2. 增加超時時間**（如果網絡環境較慢）：
```bash
export ORCHESTRATOR_TIMEOUT_SECONDS=300
```

**3. 檢查容器啟動日誌**：
```bash
ssh phison@192.168.41.173
docker logs -f agent-worker-xxx
```

### 預期啟動時間
- **修複後**：5-15 秒
- **修複前**：120+ 秒然後失敗

## 關鍵總結

✅ **問題**：LLM 環境變數被註解導致容器啟動失敗  
✅ **解決**：恢復所有必要環境變數  
✅ **預期**：容器在 5-15 秒內成功建立並通過健康檢查  
✅ **驗證**：重新測試 `/api/session/ensure` API  

現在重新啟動服務並測試，應該就不會再遇到"Readiness timed out"的問題了！