# 🚀 測試流程修正方案

## 🔍 目前 `/api/session/ensure` 流程分析

### 現有實作流程
```python
async def _ensure_session_impl(payload: EnsureSessionPayload) -> dict:
    # 1. 建立容器
    runtime = await asyncio.to_thread(runtime_manager.ensure_user_runtime, payload.user_id)
    # -> 如果啟用 orchestrator，會 POST http://192.168.41.173:5080/api/v1/workers
    
    # 2. 呼叫容器自己的 prepare 寫入設定檔
    prep_resp = requests.post(f"{base_url}/api/agent/prepare", json={...})
```

### ⚠️ 關鍵問題
1. **本地檔案準備**: `services.ensure_hermes_profile_exists()` 產生本地的 config.yaml 等
2. **遠端容器建立**: 對方 orchestrator 建立容器時，volumes 掛載遠端主機路徑  
3. **檔案同步缺口**: 本地檔案沒有自動傳送到遠端主機

---

## 🔄 正確的流程應該是

### 遠端部署成功流程
```
1. [本地] services.ensure_hermes_profile_exists() 產生檔案
   ↓
   /本地路徑/users/demo001/profiles/config.yaml
   /本地路徑/users/demo001/profiles/SOUL.md  
   /本地路徑/users/demo001/profiles/mcp.json
   /本地路徑/users/demo001/phison_mcp_bridge.py
   
4. [本地] 同步到遠端主機
   → 透過 SSH/SCP 或共享儲存傳到 192.168.41.173:/home/phison/ainexus/users/demo001/
   
5. [本地] 呼叫對方 orchestrator 建立容器
   POST http://192.168.41.173:5080/api/v1/workers
   {
     "userId": "demo001",
     "volumes": {
       "/home/phison/ainexus/users/demo001": "/data"  // 掛載已有檔案的路徑
     }
   }
   
6. [對方] 容器啟動，/data 已有檔案
   ↓
7. [本地] 呼叫容器自己的 /api/agent/prepare 
   → 容器內的 /data/profiles/config.yaml 已存在，可以讀取
```

### 本地部署成功流程 (不用 orchestrator)
```  
1. [本地] services.ensure_hermes_profile_exists() 產生檔案
   ↓
2. [本地] runtime_manager.ensure_user_runtime() 建立本地容器
   volumes: {
     "/本地路徑/users/demo001": "/opt/data"
   }
   ↓
3. [本地] 呼叫容器自己的 /api/agent/prepare
   → 容器內的 /opt/data 已有本地準備的檔案
```

---

## 🚧 目前缺失

### 檔案同步機制沒有實作
```python
# 需要新增這段功能
async def sync_files_to_remote_host(user_id: str, remote_host: str, remote_path: str):
    """將本地的 hermes 檔案同步到遠端主機"""
    local_user_path = f"{os.getenv('HERMES_BASE_ROOT')}/users/{user_id}"
    remote_user_path = f"{remote_host}:{remote_path}/users/{user_id}"
    
    # 方法1: 使用 SSH (如果本機有 ssh keys)
    subprocess.run(["scp", "-r", local_user_path, remote_user_path])
    
    # 方法2: 使用共享儲存網路磁碟機
    # shutil.copytree(local_user_path, shared_storage_path + f"/users/{user_id}")
    
    # 方法3: 透過對方 orchestrator 的外部 API 上傳檔案 (如果支援)
    pass
```

---

## 🎯 立即可用的測試方式

### 手動測試流程
1. **準備遠端檔案**
   ```bash
   # 手動 SSH 到 192.168.41.173
   ssh user@192.168.41.173
   
   # 建立目錄結構
   mkdir -p /home/phison/ainexus/users/demo001/profiles
   
   # 複製檔案（從你的本地機器）
   scp D:/mygpt/AI_NEXUS_hermes/hermes_core_data_test/users/demo001/* \
       user@192.168.41.173:/home/phison/ainexus/users/demo001/
   ```

2. **透過你的 Swagger 測試**
   ```http
   POST http://你的系統:8643/api/session/ensure
   {
     "user_id": "demo001",
     "llm_api_key": "AINX-...",
     "model": "Qwen/Qwen3.6-35B-A3B-FP8",
     "phison_token": "eyJ...",
     "system_prompt": "你是一個得力的辦公助理"
   }
   ```

3. **驗證容器建立**
   - 使用新增的 `/api/orchestrator/workers` 查看
   - 確認容器的 `userId` = `demo001`

---

## ✅ 結論

**目前可以嗎？**
- 🟡 **部分可以**: 容器建立可以連線，但遠端容器內沒有檔案
- 🔴 **需要手動準備**: 遠端檔案同步需要手動處理
- 🟢 **API 功能完成**: 所有的 API 端點都已正確實作

**需要改進的地方**:
1. 新增自動檔案同步功能
2. 錯誤處理（當遠端檔案準備不完整的提示）

**建議測試順序**:
1. 手動準備遠端檔案
2. 測試容器建立（驗證連線成功）
3. 測試聊天功能（驗證檔案掛載正確）
4. 再實作自動檔案同步