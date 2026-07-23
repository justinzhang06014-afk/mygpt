# 檔案上傳診斷腳本 - PowerShell

# 測試 1：手動上傳單個檔案到 Orchestrator
Write-Host "=== 測試 1：手動上傳 config.yaml ===" -ForegroundColor Yellow
try {
    $configPath = "D:\mygpt\AI_NEXUS_hermes\hermes_core_data_test\profiles\user_2\config.yaml"
    if (Test-Path $configPath) {
        $response = Invoke-RestMethod -Method Post -Uri "http://192.168.41.173:5080/api/v1/users/2/files" `
            -Form @{
                "files" = Get-Item $configPath | Get-Content -Raw
            }
        Write-Host "✅ 檔案上傳成功: $($response | ConvertTo-Json -Depth 3)" -ForegroundColor Green
    } else {
        Write-Host "❌ 檔案不存在: $configPath" -ForegroundColor Red
    }
} catch {
    Write-Host "❌ 檔案上傳失敗: $($_.Exception.Message)" -ForegroundColor Red
    if ($_.Exception.Response) {
        $errorBody = $_.Exception.Response.GetResponseStream() | ForEach-Object { (New-Object System.IO.StreamReader($_)).ReadToEnd() }
        Write-Host "錯誤詳情: $errorBody" -ForegroundColor Red
    }
}

# 測試 2：使用正確的 multipart/tablename 格式
Write-Host "`n=== 測試 2：正確格式上傳多個檔案 ===" -ForegroundColor Yellow
try {
    $configPath = "D:\mygpt\AI_NEXUS_hermes\hermes_core_data_test\profiles\user_2\config.yaml"
    $soulPath = "D:\mygpt\AI_NEXUS_hermes\hermes_core_data_test\profiles\user_2\SOUL.md"

    $formData = @{
        "files" = Get-Item $configPath
    }
    
    $response = Invoke-RestMethod -Method Post -Uri "http://192.168.41.173:5080/api/v1/users/2/files" -Form $formData
    Write-Host "✅ 檔案上傳成功: $($response | ConvertTo-Json -Depth 3)" -ForegroundColor Green
} catch {
    Write-Host "❌ 檔案上傳失敗: $($_.Exception.Message)" -ForegroundColor Red
}

# 測試 3：測試 Python requests 格式
Write-Host "`n=== 測試 3：檢查 Python 能否連線 ===" -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Method Get -Uri "http://192.168.41.173:5080/api/v1/workers"
    Write-Host "✅ 可以連線到 Orchestrator，當前有 $($response.Count) 個 workers" -ForegroundColor Green
} catch {
    Write-Host "❌ 無法連線到 Orchestrator: $($_.Exception.Message)" -ForegroundColor Red
}

# 測試 4：檢查本地檔案完整性
Write-Host "`n=== 測試 4：檢查本地檔案 ===" -ForegroundColor Yellow
$requiredFiles = @("config.yaml", "SOUL.md", "mcp.json", "phison_mcp_bridge.py")
foreach ($file in $requiredFiles) {
    $filePath = "D:\mygpt\AI_NEXUS_hermes\hermes_core_data_test\profiles\user_2\$file"
    if (Test-Path $filePath) {
        $fileSize = (Get-Item $filePath).Length
        Write-Host "✅ $file 存在 ($fileSize bytes)" -ForegroundColor Green
    } else {
        Write-Host "❌ $file 不存在" -ForegroundColor Red
    }
}