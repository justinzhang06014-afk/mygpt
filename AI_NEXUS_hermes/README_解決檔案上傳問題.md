# 檔案上傳到遠端 Orchestrator 失敗 - 解決方案

## 問題分析
- **現象**：`檔案上傳到遠端 Orchestrator 失敗`
- **根本原因**：Orchestrator 主機上缺少 `/home/phison/ainexus/agent-data/` 目錄結構
- **檔案流程**：本機 `user_2` → 上傳 → 遠端 `/home/phison/ainexus/agent-data/2/`

## 解決步驟 (在 Orchestrator 主機 192.168.41.173 上執行)

### 方法 1：SSH 手動執行指令
```bash
ssh phison@192.168.41.173
```

然後執行：
```bash
# 建立 agent-data 根目錄
sudo mkdir -p /home/phison/ainexus/agent-data

# 設定權限
sudo chown -R phison:phison /home/phison/ainexus/agent-data
sudo chmod -R 755 /home/phison/ainexus/agent-data

# 建立測試目錄 (user 2)
sudo mkdir -p /home/phison/ainexus/agent-data/2
sudo chown -R phison:phison /home/phison/ainexus/agent-data/2

# 驗證建立成功
ls -la /home/phison/ainexus/agent-data
```

### 方法 2：使用提供的腳本
將 `setup_agent_data_dir.sh` 上傳到 Orchestrator 主機並執行：
```bash
ssh phison@192.168.41.173 "bash setup_agent_data_dir.sh"
```

## 驗證目錄建立
```bash
# 檢查目錄是否存在
ls -la /home/phison/ainexus/agent-data

# 應該看到：
# drwxr-xr-x 2 phison phison 4096 Jul 23 12:00 2
```

## 檢查 Orchestrator 配置

確認 Orchestrator 的 `AllowedBindPrefixes` 設定允許這個路徑：
```bash
# 檢查 Orchestrator 設定檔
cat /etc/orchestrator/config.json  # 或其他設定檔位置
```

設定應該包含：
```json
{
  "AllowedBindPrefixes": [
    "/home/phison/ainexus/agent-data"
  ]
}
```

## 重新測試

建立目錄後，重新執行原本的 `/api/session/ensure` 請求：

```json
{
  "user_id": "2",
  "llm_api_key": "AINX-F78D2FCD53915EE37BD0871392FFBFFAF648C53C388950FC6A1F2ED8C534B249",
  "model": "Qwen/Qwen3.6-35B-A3B-FP8",
  "phison_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "system_prompt": "你是一個很強的辦公助理"
}
```

## 輔助診斷指令

如果還有問題，可以手動測試檔案上傳：

```bash
# 測試 API 連線
curl http://192.168.41.173:5080/api/v1/workers

# 測試檔案上傳 (從你的本機)
curl -X POST http://192.168.41.173:5080/api/v1/users/2/files \
  -F "files=@config.yaml;filename=config.yaml" \
  -F "files=@SOUL.md;filename=SOUL.md"
```

## 結構說明

建立完成後的目錄結構：
```
/home/phison/ainexus/agent-data/
├── 2/                    # user_id = 2 的目錄
│   ├── config.yaml      # 配置檔
│   ├── SOUL.md          # 系統提示詞
│   ├── mcp.json         # MCP 設定
│   └── phison_mcp_bridge.py  # MCP 源接腳本
```

## 注意事項

1. **權限**：確保 Orchestrator 服務有讀寫這個目錄的權限
2. **磁碟空間**：確保 `/home/phison/ainexus/` 有足夠的磁碟空間
3. **備份**：定期備份重要的 agent 資料
4. **清理**：定期清理不再使用的 user_id 目錄