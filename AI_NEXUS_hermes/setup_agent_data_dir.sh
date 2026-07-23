#!/bin/bash
# 在 Orchestrator 主機 (192.168.41.173) 上執行此腳本
# 目的：建立 Agent 資料目錄結構並設定正確權限

# 1. 建立 agent-data 目錄結構
sudo mkdir -p /home/phison/ainexus/agent-data

# 2. 設定目錄權限 (讓 Orchestrator 和容器可以讀寫)
sudo chown -R phison:phison /home/phison/ainexus/agent-data
sudo chmod -R 755 /home/phison/ainexus/agent-data

# 3. 驗證目錄是否建立成功
ls -la /home/phison/ainexus/agent-data

# 4. 測試建立使用者目錄 (user_2)
sudo mkdir -p /home/phison/ainexus/agent-data/2
sudo chown -R phison:phison /home/phison/ainexus/agent-data/2

echo "✅ 目錄結構建立完成："
echo "   /home/phison/ainexus/agent-data/"
echo "   /home/phison/ainexus/agent-data/2/"