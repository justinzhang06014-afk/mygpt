# "Readiness timed out" 錯誤診斷和解決方案

## 錯誤訊息
```
Readiness timed out for agent-worker-9e79065d0dd7 at http://agent-worker-9e79065d0dd7:8642/health
```

## 問題分析

**容器已建立**：`agent-worker-9e79065d0dd7` 容器已成功建立
**健康檢查失敗**：容器內的 hermes-agent 服務 (8642端口) 在超時時間內無法回應
**根本原因**：容器啟動了，但內部的 hermes-agent 程式沒有正確啟動或無法訪問

## 可能的原因

### 1. 環境變數配置錯誤
容器啟動時的環境變數問題導致 hermes-agent 無法正確啟動

### 2. 配置檔案問題
上傳到遠端的 config.yaml, SOUL.md 等檔案有格式錯誤

### 3. 映像問題
hermes-agent 映像中有問題或版本不匹配

### 4. 資源限制
CPU或記憶體不足導致程式啟動失敗

### 5. 網絡問題
容器內DNS解析或網絡連接問題

## 診斷步驟

### 步驟 1：檢查容器狀態
```bash
# SSH 到 Orchestrator 主機
ssh phison@192.168.41.173

# 檢查容器狀態
docker ps -a | grep agent-worker-9e79065d0dd7

# 查看容器日誌
docker logs agent-worker-9e79065d0dd7
```

### 步驟 2：檢查容器內服務狀態
```bash
# 進入容器
docker exec -it agent-worker-9e79065d0dd7 /bin/bash

# 檢查進程
ps aux | grep hermes

# 檢查端口
netstat -tlnp | grep 8642

# 手動測試健康檢查
curl http://localhost:8642/health
```

### 步驟 3：檢查上傳的檔案
```bash
# 檢查配置檔案是否存在
ls -la /opt/data

# 檢查檔案內容
cat /opt/data/config.yaml
cat /opt/data/SOUL.md
```

### 步驟 4：檢查環境變數
```bash
# 在容器內檢查環境變數
docker exec agent-worker-9e79065d0dd7 env | grep -E "HERMES|LLM|API"

# 關鍵環境變數：
# - PHISON_API_KEY
# - LLM_PROVIDER
# - LLM_BASE_URL  
# - LLM_MODEL
# - API_SERVER_ENABLED
# - API_SERVER_HOST
# - API_SERVER_KEY
```

## 快速解決方案

### 方案 1：增加超時時間
修改 `orchestrator_client.py` 中的環境變數：
```bash
export ORCHESTRATOR_TIMEOUT_SECONDS=300
```

### 方案 2：檢查環境變數配置
確保容器建立時的環境變數正確：
```python
# orchestrator_client.py:369-379
"environment": {
    "PHISON_API_KEY": "...",            # 必須正確
    "LLM_PROVIDER": "custom",
    "LLM_BASE_URL": "...",               # 必須可訪問
    "LLM_MODEL": "...",                  # 必須正確
    "LLM_API_KEY": "...",                # 可選
    "API_SERVER_ENABLED": "true",        # 必須為 true
    "API_SERVER_HOST": "0.0.0.0",        # 必須為 0.0.0.0
    "API_SERVER_KEY": "",                # 空字串
    "API_SERVER_CORS_ORIGINS": "*",      # 必須包含
}
```

### 方案 3：手動啟動容器測試
```bash
# 殺掉失敗的容器
docker rm -f agent-worker-9e79065d0dd7

# 手動啟動測試
docker run -d \
  --name test-hermes \
  -e PHISON_API_KEY="AINX-..." \
  -e LLM_PROVIDER="custom" \
  -e LLM_BASE_URL="https://ainexus.phison.com/api/external/v1" \
  -e LLM_MODEL="Qwen/Qwen3.6-35B-A3B-FP8" \
  -e API_SERVER_ENABLED="true" \
  -e API_SERVER_HOST="0.0.0.0" \
  -e API_SERVER_KEY="" \
  -e API_SERVER_CORS_ORIGINS="*" \
  -v /home/phison/ainexus/agent-data/2:/opt/data \
  nousresearch/hermes-agent:latest

# 檢查日誌
docker logs -f test-hermes

# 測試健康檢查
curl http://$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' test-hermes):8642/health
```

### 方案 4：檢查映像版本
```bash
# 檢查使用的映像
docker images | grep hermes-agent

# 拉取最新版本
docker pull nousresearch/hermes-agent:latest
```

## 常見問題修正

### 問題：LLM_BASE_URL 無法訪問
```bash
# 測試 LLM API 連接
curl -H "Authorization: Bearer AINX-..." https://ainexus.phison.com/api/external/v1/models

# 確認 URL 正確
# ✅ 正確：https://ainexus.phison.com/api/external/v1
# ❌ 錯誤：https://ainexus.phison.com/api/v1
```

### 問題：配置檔案格式錯誤
```bash
# 檢查 YAML 語法
cat /opt/data/config.yaml | python3 -c "import sys, yaml; yaml.safe_load(sys.stdin)"

# 重新上傳正確的配置檔案
```

### 問題：端口衝突
```bash
# 檢查端口占用
netstat -tlnp | grep 8642

# 確保 API_SERVER_ENABLED=true
```

## 監控和日誌

### 啟動監控
```bash
# 實時監控容器日誌
docker logs -f $(docker ps -q -f name=agent-worker-)

# 監控容器資源使用
docker stats $(docker ps -q -f name=agent-worker-)
```

### 詳細調試
```bash
# 啟動調試模式
docker run -it \
  --entrypoint /bin/bash \
  nousresearch/hermes-agent:latest

# 手動啟動 hermes 服務
python3 -m hermes --debug
```

## 如果問題持續

1. **檢查 Orchestrator 日誌**
2. **檢查系統資源** (CPU、記憶體、磁碟空間)
3. **檢查網絡連接** (DNS、防火牆)
4. **嘗試重新啟動 Orchestrator 服務**
5. **聯系系統管理員檢查主機狀態**

## 預期結果成功的狀態

```json
{
  "status": "healthy",
  "gateway_state": "running",
  "pid": 12345,
  "version": "hermes-agent:latest"
}
```

調用健康檢查端點應該返回上述格式的 JSON 回應。