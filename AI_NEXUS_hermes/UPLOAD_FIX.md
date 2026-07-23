# 檔案上傳問題 - 診斷與解決方案

## 問題分析

你直接調用 Orchestrator 的 `/api/v1/workers` 端點成功，但透過我們的程式「檔案上傳到遠端 Orchestrator 失敗」，這表示：

✅ **正常部分**：
- Orchestrator 服務正常運作
- 網路連線沒有問題
- 容器建立邏輯正常

❌ **問題部分**：
- 檔案上傳步驟失敗 (`_upload_files_to_orchestrator`)

## 可能的原因

### 1. API 端點格式錯誤 (最可能)
**問題**：`orchestrator_client.py:95` 使用的端點：
```python
upload_url = f"{ORCHESTRATOR_URL}/api/v1/users/{user_id}/files"
```

**實際可能需要**（根據 `0722_night_problem.md:32`）：
```bash
curl -F "files=@<檔案名稱>;filename=<檔案名稱>" http://localhost:5080/api/v1/users/<user_id>
```
注意：**可能沒有 `/files` 後綴**

### 2. Files 參數格式問題
Python `requests.post` 的 `files` 參數格式可能不匹配 Orchestrator 預期格式。

### 3. 檔案路徑問題
可能在 Windows 上檔案路徑處理有問題。

## 解決方案

### 方案 1：修改檔案上傳端點（推薦）

**檔案**：`orchestrator_client.py:95`

**修改前**：
```python
upload_url = f"{ORCHESTRATOR_URL}/api/v1/users/{user_id}/files"
```

**修改後**：
```python
upload_url = f"{ORCHESTRATOR_URL}/api/v1/users/{user_id}"
```

### 方案 2：測試確定的端點

使用提供的 PowerShell 測試腳本：
```powershell
# 執行測試腳本
.\test_upload.ps1

# 或手動測試
Invoke-RestMethod -Post -Uri "http://192.168.41.173:5080/api/v1/users/2/files" -Form @{
    "files" = Get-Item "D:\mygpt\AI_NEXUS_hermes\hermes_core_data_test\profiles\user_2\config.yaml"
}
```

### 方案 3：檢查 Orchestrator 文件

確認 Orchestrator 的實際檔案上傳端點：
```bash
# 檢查 Orchestrator API 文件
curl http://192.168.41.173:5080/docs
# 或
curl http://192.168.41.173:5080/swagger
```

### 方案 4：增加診斷日誌

在 `orchestrator_client.py:109-131` 中增加詳細日誌：
```python
try:
    logger.info(f"📤 [Orchestrator] 開始上傳檔案到: {upload_url}")
    logger.info(f"📤 [Orchestrator] 準備上傳的檔案: {required_files}")
    logger.info(f"📤 [Orchestrator] agent_dir 實際路徑: {agent_dir}")
    
    upload_resp = requests.post(
        upload_url,
        files=files_to_upload,
        timeout=ORCHESTRATOR_TIMEOUT_SECONDS,
    )
    
    # 記錄詳細回應
    logger.info(f"📤 [Orchestrator] 回應狀態碼: {upload_resp.status_code}")
    logger.info(f"📤 [Orchestrator] 回應內容: {upload_resp.text}")
    
    upload_resp.raise_for_status()
```

## 快速驗證步驟

1. **先手動測試確定正確的端點**：
   ```powershell
   # 測試有 /files 的端點
   Invoke-RestMethod -Post -Uri "http://192.168.41.173:5080/api/v1/users/2/files" -Form @{
       "files" = Get-Item "D:\mygpt\AI_NEXUS_hermes\hermes_core_data_test\profiles\user_2\config.yaml"
   }

   # 測試沒有 /files 的端點
   Invoke-RestMethod -Post -Uri "http://192.168.41.173:5080/api/v1/users/2" -Form @{
       "files" = Get-Item "D:\mygpt\AI_NEXUS_hermes\hermes_core_data_test\profiles\user_2\config.yaml"
   }
   ```

2. **根據測試結果修改 `orchestrator_client.py`**

3. **重新啟動服務並測試**

## 關鍵檢查點

1. **檔案端點**：是 `/api/v1/users/{user_id}` 還是 `/api/v1/files/{user_id}`？
2. **請求方法**：確保用 `POST` 方法
3. **檔案參數名**：是 `"files"` 還是 `"file"`？
4. **回應格式**：檢查 Orchestrator 實際返回的 JSON 格式

你想要先執行測試腳本確定正確的端點，還是直接修改程式碼試試看？