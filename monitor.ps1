# ⚙️ 設定檔
$OUTPUT_PATH = "D:\mygpt\hermes_core_data\monitor_stats.json"
$INTERVAL = 10  # 每 10 秒抓一次

# 強制將 Windows 終端機編碼改為 UTF-8，解決亂碼問題
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "📊 Windows 自動 Docker 監控已啟動... 寫入路徑: $OUTPUT_PATH" -ForegroundColor Green

while ($true) {
    try {
        # 1. 直接執行最傳統的 docker stats，並跳過第一行表格標題
        $rawLines = docker stats --no-stream | Select-Object -Skip 1
        
        $containersObj = @{}
        
        foreach ($line in $rawLines) {
            # 用連續空白字元把欄位切開
            $cols = $line -split '\s{2,}'
            if ($cols.Count -lt 4) { continue }
            
            $name = $cols[1].Trim()
            
            # 唯有名稱包含 hermes 的容器才抓取
            if ($name -like "*hermes*") {
                $userId = $name -replace "hermes-runtime-", "" -replace "lm_", ""
                
                $containersObj[$userId] = @{
                    container_name = $name
                    current = @{
                        cpu_percent   = $cols[2].Trim()  # CPU %
                        mem_usage     = $cols[3].Trim()  # MEM USAGE / LIMIT
                        net_io        = $cols[4].Trim()  # NET I/O
                        block_io      = $cols[5].Trim()  # BLOCK I/O
                    }
                }
            }
        }

        # 2. 組合網頁後台專用格式
        $output = @{
            timestamp = (Get-Date -Format "yyyy-MM-ddTHH:mm:ssZ")
            sample_interval_seconds = $INTERVAL
            containers = $containersObj
        }

        # 3. 輸出並覆寫 JSON 檔案
        $output | ConvertTo-Json -Depth 10 | Out-File -FilePath $OUTPUT_PATH -Encoding utf8 -Force
    }
    catch {
        Write-Host "⚠️ 擷取 Docker 數據發生異常: $_" -ForegroundColor Red
    }

    Start-Sleep -Seconds $INTERVAL
}
